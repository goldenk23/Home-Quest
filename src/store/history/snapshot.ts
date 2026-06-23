// src/store/history/snapshot.ts
//
// Snapshot-based undo/redo. We capture the *floor-plan data* (the only thing that should
// be undoable) at action boundaries and restore it wholesale on undo/redo.
//
// Why snapshots instead of per-operation command objects: the editor mutations are deeply
// intertwined (drawing a wall can implicitly create vertices AND split other walls;
// scalePlan transforms every vertex/opening at once; smart-align rewrites several
// vertices on drop). Reversing each of those as a bespoke command is error-prone. A plan
// has only hundreds of entities and Immer gives us cheap structural sharing, so storing
// whole-plan snapshots is both simple and correct.

import type { EntityId, Vertex, Wall, Room, FurnitureItem, Opening } from '@/types/editor';

export interface FloorPlanSnapshot {
  readonly vertices: Record<EntityId, Vertex>;
  readonly walls: Record<EntityId, Wall>;
  readonly rooms: Record<EntityId, Room>;
  readonly furniture: Record<EntityId, FurnitureItem>;
  readonly openings: Record<EntityId, Opening>;
}

/** The subset of the store that a snapshot reads from. */
export interface SnapshotSource {
  vertices: Record<EntityId, Vertex>;
  walls: Record<EntityId, Wall>;
  rooms: Record<EntityId, Room>;
  furniture: Record<EntityId, FurnitureItem>;
  openings: Record<EntityId, Opening>;
}

/**
 * Capture the current floor-plan as a snapshot. Because every store mutation goes through
 * Immer (copy-on-write), these top-level record objects are immutable — later edits create
 * NEW objects rather than mutating these — so holding the references is a safe snapshot.
 */
export function captureSnapshot(src: SnapshotSource): FloorPlanSnapshot {
  return {
    vertices: src.vertices,
    walls: src.walls,
    rooms: src.rooms,
    furniture: src.furniture,
    openings: src.openings,
  };
}

/**
 * True when two snapshots reference the same plan data (no structural change happened).
 * Used to skip recording no-op "transactions" (e.g. a click that only changed selection,
 * or a drag that didn't actually move anything).
 */
export function snapshotsEqual(a: FloorPlanSnapshot, b: FloorPlanSnapshot): boolean {
  return (
    a.vertices === b.vertices &&
    a.walls === b.walls &&
    a.rooms === b.rooms &&
    a.furniture === b.furniture &&
    a.openings === b.openings
  );
}
