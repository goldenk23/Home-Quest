// src/domains/editor/hooks/usePan.ts

import { useState, useCallback, useRef, useEffect } from 'react';
import type { RefObject } from 'react';
import type { ViewTransform } from '@/types/geometry';

const MIN_SCALE = 0.1;
const MAX_SCALE = 10;
const ZOOM_FACTOR = 1.1; // each wheel notch zooms by 10%

/**
 * Owns pan/zoom state for the editor SVG.
 *
 * @param svgRef - ref to the <svg> element, needed to map the cursor position into
 *                 element‑local coordinates so we can zoom toward the pointer.
 */
export function usePanZoom(svgRef: RefObject<SVGSVGElement | null>) {
  const [viewTransform, setViewTransform] = useState<ViewTransform>({
    scale: 1,
    offsetX: 0,
    offsetY: 0,
  });

  // Refs hold "in‑flight" gesture data without causing re‑renders on every mouse move.
  const isPanning = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  // Wheel zoom MUST be a native, non-passive listener — React's synthetic onWheel is
  // registered as passive, so e.preventDefault() there is ignored and the page scrolls.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault(); // stop the page from scrolling while zooming the canvas
      const factor = e.deltaY > 0 ? 1 / ZOOM_FACTOR : ZOOM_FACTOR;
      setViewTransform((prev) => {
        const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.scale * factor));
        const rect = el.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const ratio = newScale / prev.scale;
        return {
          scale: newScale,
          offsetX: mx - (mx - prev.offsetX) * ratio,
          offsetY: my - (my - prev.offsetY) * ratio,
        };
      });
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [svgRef]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    // Pan with middle mouse, or Alt + left click (keeps left click free for drawing).
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanning.current = true;
      lastMouse.current = { x: e.clientX, y: e.clientY };
      e.preventDefault();
    }
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastMouse.current.x;
    const dy = e.clientY - lastMouse.current.y;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    setViewTransform((prev) => ({
      ...prev,
      offsetX: prev.offsetX + dx,
      offsetY: prev.offsetY + dy,
    }));
  }, []);

  const handleMouseUp = useCallback(() => {
    isPanning.current = false;
  }, []);

  /** Pan the view by a pixel delta (used for left-drag "grab" panning in the canvas). */
  const panBy = useCallback((dx: number, dy: number) => {
    setViewTransform((prev) => ({ ...prev, offsetX: prev.offsetX + dx, offsetY: prev.offsetY + dy }));
  }, []);

  return {
    viewTransform,
    panBy,
    handlers: {
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
    },
  };
}
