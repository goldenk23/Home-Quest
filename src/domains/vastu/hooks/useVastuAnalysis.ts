// src/domains/vastu/hooks/useVastuAnalysis.ts

import { useEffect } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';
import { computePlanBoundary } from '../services/planBoundary';
import { computeVastuScore } from '../services/scoring';
import { planTo3D } from '@/domains/viewer/services/transform';

/**
 * Recomputes the plan boundary and Vastu score whenever the geometry changes, then stores
 * them. Also keeps `planCentroid3D` (used by the orbit camera) in sync with the geometry.
 * Renders nothing — mount once where the editor/viewer lives.
 */
export function useVastuAnalysis(): void {
  const walls = useAppStore((s) => s.walls);
  const vertices = useAppStore((s) => s.vertices);
  const rooms = useAppStore((s) => s.rooms);

  useEffect(() => {
    const boundary = computePlanBoundary(vertices, walls);
    useAppStore.getState().setPlanBoundary(boundary);

    // Keep the orbit camera target centered on the current geometry. We use the average
    // of all vertices so the camera recenters even before a closed loop exists.
    const verts = Object.values(vertices);
    if (verts.length > 0) {
      const avg = verts.reduce(
        (acc, v) => ({ x: acc.x + v.position.x, y: acc.y + v.position.y }),
        { x: 0, y: 0 }
      );
      const center2D: Point2D = { x: avg.x / verts.length, y: avg.y / verts.length };
      useAppStore.getState().setPlanCentroid3D(planTo3D(center2D, 0));
    } else {
      useAppStore.getState().setPlanCentroid3D(null);
    }

    if (!boundary) {
      useAppStore.getState().setVastuScore(null);
      return;
    }

    // Resolve each room's boundary vertex ids → positions for the scorer.
    const roomList = Object.values(rooms);
    const roomPolygons: Record<string, Point2D[]> = {};
    for (const room of roomList) {
      roomPolygons[room.id] = room.boundaryVertexIds
        .map((id) => vertices[id]?.position)
        .filter((p): p is Point2D => Boolean(p));
    }

    useAppStore.getState().setVastuScore(computeVastuScore(roomList, roomPolygons, boundary));
  }, [walls, vertices, rooms]);
}
