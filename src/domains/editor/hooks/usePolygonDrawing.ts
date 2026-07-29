// src/domains/editor/hooks/usePolygonDrawing.ts

import { useState, useRef, useCallback } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';
import { findWallIntersections, splitWallAtPoint, splitWallsAtPoint } from '../services/wallOps';

/** Click within this distance (cm) of the first point closes the polygon. */
const CLOSE_DIST_SQ = 30 * 30;

/**
 * Free-form polygon room tool (Approach A: polygon → walls). Points are accumulated on click;
 * closing the loop emits a wall for every edge via the same crossing/T-split path as the wall
 * tool, so the existing room detection turns the closed loop into a Room (and the 2D→3D
 * extrusion renders it) with no new entity type.
 *
 * Port of the Python editor's polygon tool (`add_polygon_point`/`finish_polygon`).
 */
export function usePolygonDrawing() {
  const [points, setPoints] = useState<Point2D[]>([]);
  const pointsRef = useRef<Point2D[]>([]);
  pointsRef.current = points;

  /** Emit walls around a closed loop as ONE undo step. Reads fresh state per edge. */
  const finish = useCallback((pts: Point2D[]) => {
    if (pts.length < 3) return;
    const store = useAppStore.getState();
    store.recordHistory('Draw Polygon Room', () => {
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i];
        const b = pts[(i + 1) % pts.length];
        const s = useAppStore.getState();
        // Split any existing wall this edge crosses, then split at the endpoints so the new
        // edge shares real vertices (connects the room to whatever it touches).
        for (const c of findWallIntersections(a, b, s.walls, s.vertices)) {
          splitWallAtPoint(c.wallId, c.point);
        }
        splitWallsAtPoint(a);
        splitWallsAtPoint(b);
        s.addWall(a, b);
      }
    });
  }, []);

  /** Add a point, or close the loop when clicking near the first point. */
  const handleClick = useCallback(
    (worldPos: Point2D) => {
      const pts = pointsRef.current;
      if (pts.length >= 3) {
        const first = pts[0];
        const dx = worldPos.x - first.x;
        const dy = worldPos.y - first.y;
        if (dx * dx + dy * dy < CLOSE_DIST_SQ) {
          finish(pts);
          setPoints([]);
          return;
        }
      }
      setPoints([...pts, worldPos]);
    },
    [finish]
  );

  /** Close explicitly (Enter / double-click). */
  const closePolygon = useCallback(() => {
    finish(pointsRef.current);
    setPoints([]);
  }, [finish]);

  const undoLastPoint = useCallback(() => setPoints((pts) => pts.slice(0, -1)), []);
  const cancel = useCallback(() => setPoints([]), []);

  return { points, handleClick, closePolygon, undoLastPoint, cancel };
}
