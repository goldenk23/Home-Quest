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
    for (const room of detected) {
      const prior = previousByBoundary.get(boundaryKey(room.boundaryVertexIds));
      const merged = prior
        ? { ...room, id: prior.id, roomType: prior.roomType, label: prior.label, floorMaterialId: prior.floorMaterialId }
        : room;
      next[merged.id] = merged;
    }

    useAppStore.getState().setRooms(next);
    // Re‑run only when the geometry references change. Zustand gives us stable refs
    // unless walls/vertices actually changed, so this won't loop.
  }, [walls, vertices]);
}
