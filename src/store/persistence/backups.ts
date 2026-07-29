// src/store/persistence/backups.ts

import { get, set, keys } from 'idb-keyval';
import { useAppStore } from '@/store';
import { captureSnapshot } from '@/store/history/snapshot';

/**
 * Rolling autosave backups for crash safety (Python `LocalAutosave` with keep_last=10). Separate
 * from the primary persist blob: we keep a ring of the last N floor-plan snapshots in IndexedDB
 * under `backup-0..N`, writing on a throttle from a store subscription. Restoring loads a ring
 * entry back into the live store.
 *
 * ponytail: stores only the ACTIVE floor's geometry (same scope as the undo snapshot). Parked
 * floors are covered by the primary persist; backups are a last-resort recovery of live work.
 */

const RING_SIZE = 10;
const THROTTLE_MS = 15000; // at most one backup every 15s
const KEY = (i: number) => `backup-${i}`;
const META_KEY = 'backup-meta';

export interface BackupEntry {
  index: number;
  label: string;
  savedAt: string; // ISO
}

interface BackupMeta {
  next: number; // ring cursor
  entries: BackupEntry[];
}

async function readMeta(): Promise<BackupMeta> {
  return (await get(META_KEY)) ?? { next: 0, entries: [] };
}

let lastWrite = 0;
let pending: ReturnType<typeof setTimeout> | null = null;

/** Write a backup now (bypasses the throttle). */
export async function writeBackupNow(): Promise<void> {
  const state = useAppStore.getState();
  const snap = captureSnapshot(state);
  const meta = await readMeta();
  const index = meta.next;
  const wallCount = Object.keys(snap.walls).length;
  const entry: BackupEntry = {
    index,
    label: `${wallCount} walls, ${Object.keys(snap.furniture).length} items`,
    savedAt: new Date().toISOString(),
  };
  await set(KEY(index), snap);
  const entries = meta.entries.filter((e) => e.index !== index);
  entries.push(entry);
  await set(META_KEY, { next: (index + 1) % RING_SIZE, entries } satisfies BackupMeta);
  lastWrite = Date.now();
}

/** Throttled backup trigger (call from a store subscription). */
function scheduleBackup(): void {
  const now = Date.now();
  const wait = Math.max(0, THROTTLE_MS - (now - lastWrite));
  if (pending) return;
  pending = setTimeout(() => {
    pending = null;
    void writeBackupNow();
  }, wait);
}

/** List existing backups, newest first. */
export async function listBackups(): Promise<BackupEntry[]> {
  const meta = await readMeta();
  return [...meta.entries].sort((a, b) => b.savedAt.localeCompare(a.savedAt));
}

/** Restore a backup into the live store (replaces the active floor's geometry). */
export async function restoreBackup(index: number): Promise<boolean> {
  const snap = await get(KEY(index));
  if (!snap) return false;
  const s = useAppStore.getState();
  s.recordHistory('Restore Backup', () => {
    useAppStore.setState({
      vertices: snap.vertices,
      walls: snap.walls,
      rooms: snap.rooms,
      furniture: snap.furniture,
      openings: snap.openings,
      roads: snap.roads,
      pillars: snap.pillars,
      beams: snap.beams,
      deckSlabs: snap.deckSlabs,
      railings: snap.railings,
      annotations: snap.annotations,
    });
  });
  return true;
}

let started = false;
/**
 * Begin autosaving. Subscribes to plan-geometry changes and writes a throttled backup. Safe to
 * call once at app start; returns an unsubscribe.
 */
export function startAutosaveBackups(): () => void {
  if (started) return () => undefined;
  started = true;
  void keys(); // warm the store
  const unsub = useAppStore.subscribe((state, prev) => {
    if (
      state.walls !== prev.walls ||
      state.vertices !== prev.vertices ||
      state.furniture !== prev.furniture ||
      state.rooms !== prev.rooms ||
      state.annotations !== prev.annotations
    ) {
      scheduleBackup();
    }
  });
  return () => {
    unsub();
    started = false;
  };
}
