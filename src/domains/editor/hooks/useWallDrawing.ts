// src/domains/editor/hooks/useWallDrawing.ts

import { useState, useCallback } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';
import { findWallIntersections, splitWallAtPoint, splitWallsAtPoint } from '../services/wallOps';

const MIN_WALL_LENGTH_SQ = 1; // reject sub‑1cm walls (squared, so 1 = 1cm²)

export function useWallDrawing() {
  // The pending start point. null ⇒ we're idle (no wall in progress).
  const [drawStart, setDrawStart] = useState<Point2D | null>(null);
  // The FIRST point of the current chain. Lets us snap the chain closed back onto its
  // origin so rectangles/rooms close exactly (and the loop is detected as a room).
  const [chainOrigin, setChainOrigin] = useState<Point2D | null>(null);
  const chainMode = useAppStore(s => s.isChainModeEnabled);

  /** Call this with a SNAPPED world point on each editor click. */
  const handleClick = useCallback(
    (worldPos: Point2D) => {
      // First click: remember where the wall starts (and where the chain began).
      if (!drawStart) {
        setDrawStart(worldPos);
        setChainOrigin(worldPos);
        return;
      }

      // Second click: finish the wall.
      const start = drawStart;
      const end = worldPos;
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      if (dx * dx + dy * dy < MIN_WALL_LENGTH_SQ) return; // ignore accidental tiny walls

      // Read FRESH state (not a stale closure) for accurate intersection tests.
      const { walls, vertices, addWall } = useAppStore.getState();

      // Split every existing wall this new wall CROSSES (interior crossings), in order.
      const crossings = findWallIntersections(start, end, walls, vertices);
      for (const c of crossings) {
        splitWallAtPoint(c.wallId, c.point);
      }

      // T-junctions: if either ENDPOINT lands on an existing wall (e.g. a wall drawn
      // through a room and ending on its far boundary), split that boundary wall so the
      // new wall shares a real vertex with it. Without this the new wall connects to
      // nothing and the enclosed area is never divided into two rooms.
      splitWallsAtPoint(start);
      splitWallsAtPoint(end);

      // Add the new wall (the store action finds/creates shared vertices for us; because
      // of the splits above, those vertices now already exist at start/end).
      addWall(start, end);

      // If we just closed the loop back onto the chain origin, the room is complete —
      // stop drawing so the user doesn't keep extending past the closed rectangle.
      const closedLoop =
        chainMode &&
        chainOrigin != null &&
        (end.x - chainOrigin.x) ** 2 + (end.y - chainOrigin.y) ** 2 < MIN_WALL_LENGTH_SQ;

      if (closedLoop) {
        setDrawStart(null);
        setChainOrigin(null);
        return;
      }

      // Chain mode keeps drawing from the point we just placed; otherwise go idle.
      setDrawStart(chainMode ? end : null);
      if (!chainMode) setChainOrigin(null);
    },
    [drawStart, chainMode, chainOrigin]
  );

  /** Cancel the in‑progress wall (e.g. on Escape). */
  const cancel = useCallback(() => {
    setDrawStart(null);
    setChainOrigin(null);
  }, []);

  return { drawStart, chainOrigin, chainMode, handleClick, cancel };
}
