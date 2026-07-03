// src/store/slices/historySlice.ts
//
// Snapshot-based undo/redo. The previous version exposed a command stack but nothing ever
// pushed a command into it, so undo/redo never activated. This version records a snapshot
// of the floor-plan at each action boundary, so the buttons light up as soon as the user
// makes an undoable change.

import type { StateCreator } from 'zustand';
import { castDraft } from 'immer';
import type { AppStore } from '..';
import { captureSnapshot, snapshotsEqual, type FloorPlanSnapshot } from '../history/snapshot';

const MAX_HISTORY = 100;

interface HistoryEntry {
  label: string;
  snap: FloorPlanSnapshot;
}

export interface HistorySlice {
  // Reactive flags consumed by the toolbar / buttons.
  canUndo: boolean;
  canRedo: boolean;
  undoLabel: string | null;
  redoLabel: string | null;

  /**
   * Run `fn` (which mutates the store) as a single undoable step. The plan state *before*
   * `fn` runs becomes the undo target. No-ops (fn that doesn't change the plan) are skipped.
   */
  recordHistory: (label: string, fn: () => void) => void;

  /** Begin a multi-step / continuous action (e.g. a drag). Captures the "before" state. */
  beginTransaction: () => void;
  /** Finish a transaction, recording one undo step (auto-skips if nothing changed). */
  commitTransaction: (label: string) => void;
  /** Abandon a transaction without recording anything. */
  cancelTransaction: () => void;

  undo: () => void;
  redo: () => void;
  clearHistory: () => void;
}

export const createHistorySlice: StateCreator<
  AppStore,
  [['zustand/immer', never], ['zustand/devtools', never]],
  [],
  HistorySlice
> = (set, get) => {
  // These stacks live outside reactive state on purpose: they hold immutable snapshot
  // references and we don't want subscribers re-rendering when they change. The reactive
  // mirror lives in canUndo/canRedo/undoLabel/redoLabel.
  let past: HistoryEntry[] = [];
  let future: HistoryEntry[] = [];
  let pending: FloorPlanSnapshot | null = null;

  const syncFlags = () => {
    set((state) => {
      state.canUndo = past.length > 0;
      state.canRedo = future.length > 0;
      state.undoLabel = past.at(-1)?.label ?? null;
      state.redoLabel = future.at(-1)?.label ?? null;
    });
  };

  const applySnapshot = (snap: FloorPlanSnapshot) => {
    set((state) => {
      state.vertices = castDraft(snap.vertices);
      state.walls = castDraft(snap.walls);
      state.rooms = castDraft(snap.rooms);
      state.furniture = castDraft(snap.furniture);
      state.openings = castDraft(snap.openings);
      state.roads = castDraft(snap.roads);
      state.pillars = castDraft(snap.pillars);
      state.beams = castDraft(snap.beams);
      state.deckSlabs = castDraft(snap.deckSlabs);
      state.railings = castDraft(snap.railings);
      // Selection may point at entities that no longer exist after a restore — clear it.
      state.selectedIds = [];
    });
  };

  const pushPast = (entry: HistoryEntry) => {
    past.push(entry);
    if (past.length > MAX_HISTORY) past.shift();
    future = [];
  };

  return {
    canUndo: false,
    canRedo: false,
    undoLabel: null,
    redoLabel: null,

    recordHistory: (label, fn) => {
      const before = captureSnapshot(get());
      fn();
      const after = captureSnapshot(get());
      if (snapshotsEqual(before, after)) return; // nothing changed → don't record
      pushPast({ label, snap: before });
      syncFlags();
    },

    beginTransaction: () => {
      // Idempotent within a gesture: keep the earliest "before" state.
      if (pending === null) pending = captureSnapshot(get());
    },

    commitTransaction: (label) => {
      if (pending === null) return;
      const before = pending;
      pending = null;
      const after = captureSnapshot(get());
      if (snapshotsEqual(before, after)) return;
      pushPast({ label, snap: before });
      syncFlags();
    },

    cancelTransaction: () => {
      pending = null;
    },

    undo: () => {
      const entry = past.pop();
      if (!entry) return;
      const current = captureSnapshot(get());
      future.push({ label: entry.label, snap: current });
      applySnapshot(entry.snap);
      syncFlags();
    },

    redo: () => {
      const entry = future.pop();
      if (!entry) return;
      const current = captureSnapshot(get());
      past.push({ label: entry.label, snap: current });
      applySnapshot(entry.snap);
      syncFlags();
    },

    clearHistory: () => {
      past = [];
      future = [];
      pending = null;
      syncFlags();
    },
  };
};
