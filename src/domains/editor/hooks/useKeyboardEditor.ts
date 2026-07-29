// src/domains/editor/hooks/useKeyboardEditor.ts

import { useEffect, useCallback } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types';

const NUDGE_AMOUNT = 10; // cm
const FINE_NUDGE = 1; // cm with Shift
const PASTE_OFFSET = 40; // cm — nudge pasted copies so they don't sit exactly on the originals

export function useKeyboardEditor(): void {
  const selectedIds = useAppStore((s) => s.selectedIds);
  const moveVertex = useAppStore((s) => s.moveVertex);
  const moveFurniture = useAppStore((s) => s.moveFurniture);
  const removeWall = useAppStore((s) => s.removeWall);
  const removeFurniture = useAppStore((s) => s.removeFurniture);
  const removeOpening = useAppStore((s) => s.removeOpening);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Ignore when typing in a field.
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      // Copy/paste (furniture) — handled before the selection guard so paste works with an
      // empty selection. Ctrl (Windows/Linux) or Cmd (macOS).
      const mod = e.ctrlKey || e.metaKey;
      if (mod && (e.key === 'c' || e.key === 'C')) {
        const state = useAppStore.getState();
        const items = state.selectedIds.map((id) => state.furniture[id]).filter(Boolean);
        if (items.length > 0) {
          state.setClipboard(items.map((it) => ({ ...it, bounds: { ...it.bounds }, position: { ...it.position } })));
          e.preventDefault();
        }
        return;
      }
      if (mod && (e.key === 'v' || e.key === 'V')) {
        pasteClipboard();
        e.preventDefault();
        return;
      }

      if (selectedIds.length === 0) return;
      const nudge = e.shiftKey ? FINE_NUDGE : NUDGE_AMOUNT;

      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault();
          useAppStore.getState().recordHistory('Nudge', () =>
            nudgeSelection(selectedIds, { x: 0, y: nudge }, moveVertex, moveFurniture)
          );
          announcePosition('up', nudge);
          break;
        case 'ArrowDown':
          e.preventDefault();
          useAppStore.getState().recordHistory('Nudge', () =>
            nudgeSelection(selectedIds, { x: 0, y: -nudge }, moveVertex, moveFurniture)
          );
          announcePosition('down', nudge);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          useAppStore.getState().recordHistory('Nudge', () =>
            nudgeSelection(selectedIds, { x: -nudge, y: 0 }, moveVertex, moveFurniture)
          );
          announcePosition('left', nudge);
          break;
        case 'ArrowRight':
          e.preventDefault();
          useAppStore.getState().recordHistory('Nudge', () =>
            nudgeSelection(selectedIds, { x: nudge, y: 0 }, moveVertex, moveFurniture)
          );
          announcePosition('right', nudge);
          break;
        case 'Delete':
        case 'Backspace':
          e.preventDefault();
          useAppStore.getState().recordHistory('Delete', () =>
            deleteSelection(selectedIds, removeWall, removeFurniture, removeOpening)
          );
          break;
      }
    },
    [selectedIds, moveVertex, moveFurniture, removeWall, removeFurniture, removeOpening]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

/**
 * Paste the furniture clipboard as new items. Positions the group's centroid at the cursor
 * (currentMouseWorld) when known, else offsets each copy by a fixed nudge. New items are
 * selected so they can be immediately moved. One undo step.
 */
function pasteClipboard(): void {
  const state = useAppStore.getState();
  const clip = state.clipboard;
  if (clip.length === 0) return;

  // Centroid of the copied group (for cursor-anchored paste).
  const cx = clip.reduce((s, it) => s + it.position.x, 0) / clip.length;
  const cy = clip.reduce((s, it) => s + it.position.y, 0) / clip.length;
  const cursor = state.currentMouseWorld;
  const dx = cursor ? cursor.x - cx : PASTE_OFFSET;
  const dy = cursor ? cursor.y - cy : PASTE_OFFSET;

  const newIds: string[] = [];
  state.recordHistory('Paste', () => {
    const s = useAppStore.getState();
    for (const it of clip) {
      const id = s.addFurniture({
        position: { x: it.position.x + dx, y: it.position.y + dy },
        rotation: it.rotation,
        scale: it.scale,
        catalogId: it.catalogId,
        roomId: null,
        bounds: { width: it.bounds.width, depth: it.bounds.depth },
      });
      if (id) newIds.push(id);
    }
  });
  if (newIds.length > 0) useAppStore.getState().select(newIds);
}

function nudgeSelection(
  ids: string[],
  delta: Point2D,
  moveVertex: (id: string, pos: Point2D) => void,
  moveFurniture: (id: string, pos: Point2D) => void
): void {
  const state = useAppStore.getState();
  for (const id of ids) {
    if (state.vertices[id]) {
      const p = state.vertices[id].position;
      moveVertex(id, { x: p.x + delta.x, y: p.y + delta.y });
    } else if (state.furniture[id]) {
      const p = state.furniture[id].position;
      moveFurniture(id, { x: p.x + delta.x, y: p.y + delta.y });
    }
  }
}

function deleteSelection(
  ids: string[],
  removeWall: (id: string) => void,
  removeFurniture: (id: string) => void,
  removeOpening: (id: string) => void
): void {
  const state = useAppStore.getState();
  for (const id of ids) {
    if (state.walls[id]) removeWall(id);
    else if (state.furniture[id]) removeFurniture(id);
    else if (state.openings[id]) removeOpening(id);
  }
  useAppStore.getState().clearSelection();
}

function announcePosition(direction: string, amount: number): void {
  const el = document.getElementById('sr-announcer');
  if (el) el.textContent = `Moved ${direction} by ${amount} centimeters`;
}
