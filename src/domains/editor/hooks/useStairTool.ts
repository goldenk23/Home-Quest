// src/domains/editor/hooks/useStairTool.ts
//
// Manages the multi-point 2D drawing interaction for the Stair tool.
// Mirrors the pattern of useWallDrawing / useRoadDrawing: exposes imperative
// handles that EditorCanvas calls from its pointer/keyboard event handlers.

import { useCallback, useRef, useState } from 'react';
import { useAppStore } from '@/store';
import { buildStair } from '../services/stairBuilder';
import type { Point2D } from '@/types/geometry';

/** Minimum distance (cm) between two path points for them to be distinct. */
const MIN_DIST_CM = 1;

function dist(a: Point2D, b: Point2D) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

export interface StairToolState {
  /** Whether a stair path is currently being drawn. */
  inProgress: boolean;
  /** Points confirmed so far (≥ 1 while drawing). */
  pathPoints: Point2D[];
  /** Live cursor position, shown as the ghost "next point". */
  ghostPoint: Point2D | null;
  /** Validation error from the last failed commit attempt. */
  error: string | null;
}

export interface StairToolHandles {
  /** Add a point (or start a new path if none in progress). Called on single click. */
  handleClick: (world: Point2D) => void;
  /** Finish the stair (must have ≥2 points). Called on double-click or Enter. */
  handleFinish: (world: Point2D) => void;
  /** Update the ghost preview (cursor move). */
  handleMove: (world: Point2D) => void;
  /** Discard the in-progress path and reset. */
  cancel: () => void;
}

export function useStairTool(): [StairToolState, StairToolHandles] {
  const [pathPoints, setPathPoints] = useState<Point2D[]>([]);
  const [ghostPoint, setGhostPoint] = useState<Point2D | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Ref copy of pathPoints to avoid stale closures in callbacks.
  const pathRef = useRef<Point2D[]>([]);
  pathRef.current = pathPoints;

  const reset = useCallback(() => {
    setPathPoints([]);
    setGhostPoint(null);
    setError(null);
    pathRef.current = [];
  }, []);

  const handleClick = useCallback((world: Point2D) => {
    const pts = pathRef.current;
    // Ignore if the new point is too close to the last one.
    if (pts.length > 0 && dist(pts[pts.length - 1], world) < MIN_DIST_CM) return;
    const next = [...pts, world];
    // Update the ref immediately so handleFinish (called from dblclick, which fires before
    // re-render) always sees the latest list even before React flushes the state update.
    pathRef.current = next;
    setPathPoints(next);
    setError(null);
  }, []);

  const handleFinish = useCallback((world: Point2D) => {
    const pts = pathRef.current;
    // Build candidate full path (add world only if it's a new distinct point).
    const finalPts =
      pts.length > 0 && dist(pts[pts.length - 1], world) < MIN_DIST_CM
        ? pts
        : [...pts, world];

    if (finalPts.length < 2) {
      setError('Draw at least two points before finishing the staircase.');
      return;
    }

    const state = useAppStore.getState();
    const { floors, activeFloorId } = state;

    // Find the floor above the active floor (smallest elevation strictly greater).
    const activeFloor = floors.find((f) => f.id === activeFloorId);
    if (!activeFloor) return;

    const upperFloor = floors.reduce<typeof activeFloor | null>((best, f) => {
      if (f.elevationCm <= activeFloor.elevationCm) return best;
      return !best || f.elevationCm < best.elevationCm ? f : best;
    }, null);

    if (!upperFloor) {
      // Fatal: can't place a stair without a floor above. Reset and alert so the user
      // isn't left stuck in drawing mode with a cryptic silent error.
      reset();
      alert('Add a second floor first — a staircase needs two floors to connect.');
      return;
    }

    const totalRiseCm = upperFloor.elevationCm - activeFloor.elevationCm;
    const result = buildStair(
      finalPts,
      state.stairWidthCm,
      totalRiseCm,
      activeFloorId,
      upperFloor.id,
      activeFloor.elevationCm
    );

    if (!result.ok) {
      setError(result.error);
      return;
    }

    state.recordHistory('Place Staircase', () => {
      state.addStair(result.stair);
    });
    reset();
  }, [reset]);

  const handleMove = useCallback((world: Point2D) => {
    setGhostPoint(world);
  }, []);

  const cancel = useCallback(() => {
    reset();
  }, [reset]);

  const state: StairToolState = {
    inProgress: pathPoints.length > 0,
    pathPoints,
    ghostPoint,
    error,
  };

  return [state, { handleClick, handleFinish, handleMove, cancel }];
}
