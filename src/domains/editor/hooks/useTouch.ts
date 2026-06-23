// src/domains/editor/hooks/useTouch.ts

import { useRef, useCallback } from 'react';
import type { RefObject } from 'react';
import type { Point2D, ViewTransform } from '@/types/geometry';

interface TouchState {
  touches: Map<number, Point2D>;
  initialDistance: number;
  initialScale: number;
  initialCenter: Point2D;
  gesture: 'none' | 'pan' | 'pinch' | 'drag' | 'longpress';
  longPressTimer: ReturnType<typeof setTimeout> | null;
}

const LONG_PRESS_DURATION = 500; // ms
const MIN_PINCH_DISTANCE = 10; // px

export function useTouchGestures(
  svgRef: RefObject<SVGSVGElement>,
  viewTransform: ViewTransform,
  setViewTransform: (vt: ViewTransform) => void,
  onTap: (worldPos: Point2D) => void,
  onLongPress: (worldPos: Point2D) => void,
  onDrag: (worldPos: Point2D) => void,
  onDragEnd: () => void
) {
  const state = useRef<TouchState>({
    touches: new Map(),
    initialDistance: 0,
    initialScale: 1,
    initialCenter: { x: 0, y: 0 },
    gesture: 'none',
    longPressTimer: null,
  });

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      e.preventDefault();
      const s = state.current;
      for (const touch of Array.from(e.changedTouches)) {
        s.touches.set(touch.identifier, { x: touch.clientX, y: touch.clientY });
      }

      if (s.touches.size === 1) {
        const pos = Array.from(s.touches.values())[0];
        s.longPressTimer = setTimeout(() => {
          s.gesture = 'longpress';
          if (svgRef.current) onLongPress(screenToWorldTouch(pos, svgRef.current, viewTransform));
        }, LONG_PRESS_DURATION);
      } else if (s.touches.size === 2) {
        cancelLongPress(s);
        const pts = Array.from(s.touches.values());
        s.initialDistance = distance(pts[0], pts[1]);
        s.initialScale = viewTransform.scale;
        s.initialCenter = midpoint(pts[0], pts[1]);
        s.gesture = 'pinch';
      } else if (s.touches.size === 3) {
        cancelLongPress(s);
        s.gesture = 'none';
      }
    },
    [viewTransform, onLongPress, svgRef]
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      e.preventDefault();
      const s = state.current;
      for (const touch of Array.from(e.changedTouches)) {
        s.touches.set(touch.identifier, { x: touch.clientX, y: touch.clientY });
      }

      if (s.touches.size === 1 && s.gesture !== 'longpress') {
        cancelLongPress(s);
        s.gesture = 'drag';
        const pos = Array.from(s.touches.values())[0];
        if (svgRef.current) onDrag(screenToWorldTouch(pos, svgRef.current, viewTransform));
      } else if (s.touches.size === 2) {
        const pts = Array.from(s.touches.values());
        const currentDist = distance(pts[0], pts[1]);
        const currentCenter = midpoint(pts[0], pts[1]);

        if (Math.abs(currentDist - s.initialDistance) > MIN_PINCH_DISTANCE) {
          const scaleFactor = currentDist / s.initialDistance;
          const newScale = Math.min(10, Math.max(0.1, s.initialScale * scaleFactor));
          setViewTransform({
            scale: newScale,
            offsetX: viewTransform.offsetX + (currentCenter.x - s.initialCenter.x),
            offsetY: viewTransform.offsetY + (currentCenter.y - s.initialCenter.y),
          });
        } else {
          setViewTransform({
            ...viewTransform,
            offsetX: viewTransform.offsetX + (currentCenter.x - s.initialCenter.x),
            offsetY: viewTransform.offsetY + (currentCenter.y - s.initialCenter.y),
          });
          s.initialCenter = currentCenter;
        }
      }
    },
    [viewTransform, setViewTransform, onDrag, svgRef]
  );

  const handleTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      const s = state.current;
      for (const touch of Array.from(e.changedTouches)) s.touches.delete(touch.identifier);

      if (s.touches.size === 0) {
        if (s.gesture === 'none') {
          const last = e.changedTouches[0];
          if (last && svgRef.current) onTap(screenToWorldTouch({ x: last.clientX, y: last.clientY }, svgRef.current, viewTransform));
        }
        if (s.gesture === 'drag') onDragEnd();
        cancelLongPress(s);
        s.gesture = 'none';
      }
    },
    [viewTransform, onTap, onDragEnd, svgRef]
  );

  return { onTouchStart: handleTouchStart, onTouchMove: handleTouchMove, onTouchEnd: handleTouchEnd };
}

function cancelLongPress(state: TouchState): void {
  if (state.longPressTimer) {
    clearTimeout(state.longPressTimer);
    state.longPressTimer = null;
  }
}
function distance(a: Point2D, b: Point2D): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}
function midpoint(a: Point2D, b: Point2D): Point2D {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}
function screenToWorldTouch(screen: Point2D, svg: SVGSVGElement, view: ViewTransform): Point2D {
  const rect = svg.getBoundingClientRect();
  return {
    x: (screen.x - rect.left - view.offsetX) / view.scale,
    y: -(screen.y - rect.top - view.offsetY) / view.scale, // Y-flip, as with the mouse
  };
}
