// src/domains/editor/hooks/useRoadDrawing.ts
//
// Two-click road drawing, mirroring useWallDrawing but for standalone paving segments.
// Roads aren't part of the wall/vertex graph — each segment is an independent centerline
// with a width — so this hook is simpler: click to start, click to finish. Chain mode keeps
// drawing connected paths (driveways, garden walkways) from the last point.

import { useState, useCallback } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';

const MIN_ROAD_LENGTH_SQ = 1; // reject sub-1cm roads (squared, so 1 = 1cm²)

export function useRoadDrawing() {
  const [drawStart, setDrawStart] = useState<Point2D | null>(null);
  const chainMode = useAppStore((s) => s.isChainModeEnabled);

  /** Call this with a SNAPPED world point on each editor click while the Road tool is active. */
  const handleClick = useCallback(
    (worldPos: Point2D) => {
      if (!drawStart) {
        setDrawStart(worldPos);
        return;
      }

      const start = drawStart;
      const end = worldPos;
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      if (dx * dx + dy * dy < MIN_ROAD_LENGTH_SQ) return; // ignore accidental tiny roads

      const store = useAppStore.getState();
      store.recordHistory('Draw Road', () => {
        store.addRoad(start, end, store.roadWidth);
      });

      // Chain mode keeps drawing from the point we just placed; otherwise go idle.
      setDrawStart(chainMode ? end : null);
    },
    [drawStart, chainMode]
  );

  /** Cancel the in-progress road (e.g. on Escape / right-click). */
  const cancel = useCallback(() => {
    setDrawStart(null);
  }, []);

  return { drawStart, chainMode, handleClick, cancel };
}
