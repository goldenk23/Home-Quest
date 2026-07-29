// src/domains/editor/hooks/useWallDrawing.ts

import { useState, useCallback } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';
import { findWallIntersections, splitWallAtPoint, splitWallsAtPoint } from '../services/wallOps';
import { endpointFromLength } from '../services/geometry';

const MIN_WALL_LENGTH_SQ = 1; // reject sub‑1cm walls (squared, so 1 = 1cm²)

export function useWallDrawing() {
  // The pending start point. null ⇒ we're idle (no wall in progress).
  const [drawStart, setDrawStart] = useState<Point2D | null>(null);
  // The FIRST point of the current chain. Lets us snap the chain closed back onto its
  // origin so rectangles/rooms close exactly (and the loop is detected as a room).
  const [chainOrigin, setChainOrigin] = useState<Point2D | null>(null);
  const chainMode = useAppStore(s => s.isChainModeEnabled);

  /**
   * Place a wall from the current `drawStart` to `end`, splitting crossed/T-junction walls,
   * as one undo step. Shared by click-to-place and typed exact-length entry. Advances the
   * chain (or goes idle) exactly like a normal click. No-op if there is no active start.
   */
  const placeWallTo = useCallback(
    (end: Point2D) => {
      const start = drawStart;
      if (!start) return;
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      if (dx * dx + dy * dy < MIN_WALL_LENGTH_SQ) return; // ignore accidental tiny walls

      // Read FRESH state (not a stale closure) for accurate intersection tests.
      const store = useAppStore.getState();
      const { walls, vertices, addWall } = store;

      // Record the entire wall placement (crossings + T-junction splits + the new wall)
      // as a single undo step.
      store.recordHistory('Draw Wall', () => {
        // Split every existing wall this new wall CROSSES (interior crossings), in order.
        const crossings = findWallIntersections(start, end, walls, vertices);
        for (const c of crossings) {
          splitWallAtPoint(c.wallId, c.point);
        }

        // T-junctions: if either ENDPOINT lands on an existing wall, split that wall so the
        // new wall shares a real vertex with it (otherwise the enclosed area is never split).
        splitWallsAtPoint(start);
        splitWallsAtPoint(end);

        // Add the new wall (the store action finds/creates shared vertices for us).
        addWall(start, end);
      });

      // If we just closed the loop back onto the chain origin, the room is complete.
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
      placeWallTo(worldPos);
    },
    [drawStart, placeWallTo]
  );

  /**
   * Place the wall endpoint at an exact distance (cm) and direction. `directionRad` defaults
   * to the current cursor direction from `drawStart`; pass an explicit angle to override.
   * World Y is up, so a positive angle rotates counter-clockwise (screen shows it flipped).
   */
  const placeWallByLength = useCallback(
    (lengthCm: number, directionRad: number) => {
      if (!drawStart || !(lengthCm > 0)) return;
      placeWallTo(endpointFromLength(drawStart, lengthCm, directionRad));
    },
    [drawStart, placeWallTo]
  );

  /** Cancel the in‑progress wall (e.g. on Escape). */
  const cancel = useCallback(() => {
    setDrawStart(null);
    setChainOrigin(null);
  }, []);

  return { drawStart, chainOrigin, chainMode, handleClick, placeWallTo, placeWallByLength, cancel };
}
