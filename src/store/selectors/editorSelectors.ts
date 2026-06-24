/**
 *  Selector for editor state management with Memoization
 */
import { useAppStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';// it prevents unnecessary re-renders by doing a shallow comparison of the
 import type {Point2D} from '@/types/geometry';


import { useMemo } from 'react';

import { computeMiterOffsets } from '@/domains/editor/services/wallOps';

/**
 * We are creating a helper called useWallSegments. Its only job is to gather all the walls so the 2D screen can draw them. It calls the global memory (useAppStore) and asks to look at everything currently remembered (state).
 */
export function useWallSegments() {
  const walls = useAppStore((state) => state.walls);
  const vertices = useAppStore((state) => state.vertices);

  return useMemo(() => {
    return Object.values(walls).map((wall) => ({
      id: wall.id,
      start: vertices[wall.startVertexId]?.position ?? { x: 0, y: 0 },
      end: vertices[wall.endVertexId]?.position ?? { x: 0, y: 0 },
      thickness: wall.thickness,
      offsets: computeMiterOffsets(wall.id, walls, vertices),
    }));
  }, [walls, vertices]);
}

/**
 * Helper specifically for the "magnetic snapping" feature.
 * When you are drawing a new wall, your mouse magnetically snaps to an existing corner.
 * This asks the memory to go through every single corner in the house and hands back 
 * a simple list of their x and y coordinates. 
 * We use the `useShallow` performance trick so it doesn't recalculate this unless a corner actually moved!
 */
export function useEndpoints(): Point2D[] {
  return useAppStore(useShallow((state) => 
    Object.values(state.vertices).map((v) => v.position)
  ));
}

/**
 * Acts as a translator between the 2D drawing board and the 3D viewer.
 * The 3D viewer needs to know how to build the house, but it doesn't care about the UI or tools.
 */
export function useViewerWalls() {
  const walls = useAppStore((state) => state.walls);
  const vertices = useAppStore((state) => state.vertices);

  return useMemo(() => {
    return Object.values(walls).map((w) => ({
      id: w.id,
      start: vertices[w.startVertexId]?.position,
      end: vertices[w.endVertexId]?.position,
      thickness: w.thickness,
      height: w.height,
      materialId: w.materialId,
      materialSideA: w.materialSideA,
      materialSideB: w.materialSideB,
      offsets: computeMiterOffsets(w.id, walls, vertices),
    }));
  }, [walls, vertices]);
}

export function useViewerRooms() {
  const rooms = useAppStore((state) => state.rooms);
  const vertices = useAppStore((state) => state.vertices);

  return useMemo(() => {
    return Object.values(rooms).map((r) => ({
      id: r.id,
      polygon: r.boundaryVertexIds.map(
        (vid) => vertices[vid]?.position ?? { x: 0, y: 0 }
      ),
      floorMaterialId: r.floorMaterialId,
    }));
  }, [rooms, vertices]);
}