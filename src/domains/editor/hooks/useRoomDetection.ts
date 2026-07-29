// src/domains/editor/hooks/useRoomDetection.ts

import { useEffect } from 'react';
import { useAppStore } from '@/store';
import type { EntityId, Room } from '@/types/editor';
import { detectRooms } from '../services/roomDetection';

/** A stable key for a loop, independent of which vertex it starts at or its direction. */
function boundaryKey(vertexIds: readonly EntityId[]): string {
  return [...vertexIds].sort().join('|');
}

/**
 * Recomputes rooms whenever wall geometry changes and merges in any user‑set metadata
 * from rooms that occupy the same boundary. Mount this once, high in the editor tree
 * (e.g. inside the editor screen). It renders nothing.
 */
export function useRoomDetection(): void {
  const walls = useAppStore((s) => s.walls);
  const vertices = useAppStore((s) => s.vertices);

  useEffect(() => {
    const detected = detectRooms(vertices, walls);

    // Index existing rooms by boundary so we can carry over user choices.
    const previous = useAppStore.getState().rooms;
    const previousByBoundary = new Map<string, Room>();
    for (const room of Object.values(previous)) {
      previousByBoundary.set(boundaryKey(room.boundaryVertexIds), room);
    }

    const next: Record<EntityId, Room> = {};
    const usedIds = new Set<EntityId>();
    const usedPriorKeys = new Set<string>();

    for (const room of detected) {
      const key = boundaryKey(room.boundaryVertexIds);
      const prior = previousByBoundary.get(key);

      // Only carry over a prior room's identity/metadata if:
      //  - a prior room actually shares this exact boundary, AND
      //  - we haven't already claimed that prior room for another detected room, AND
      //  - its id isn't already taken in this pass.
      // Otherwise keep the freshly generated id. This guarantees that splitting one room
      // into two yields two DISTINCT rooms with distinct ids (so they can be selected and
      // named independently) instead of both collapsing onto the old room's id.
      const canReusePrior =
        prior != null && !usedPriorKeys.has(key) && !usedIds.has(prior.id);

      const merged = canReusePrior
        ? { ...room, id: prior!.id, roomType: prior!.roomType, label: prior!.label, floorMaterialId: prior!.floorMaterialId, fillMode: prior!.fillMode, fillColor: prior!.fillColor }
        : room;

      if (canReusePrior) usedPriorKeys.add(key);
      usedIds.add(merged.id);
      next[merged.id] = merged;
    }

    useAppStore.getState().setRooms(next);
    // Re‑run only when the geometry references change. Zustand gives us stable refs
    // unless walls/vertices actually changed, so this won't loop.
  }, [walls, vertices]);
}
