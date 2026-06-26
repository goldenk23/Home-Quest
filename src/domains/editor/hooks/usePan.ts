// src/domains/editor/hooks/usePan.ts

import { useState, useCallback, useRef, useEffect } from 'react';
import type { RefObject } from 'react';
import type { ViewTransform, Point2D } from '@/types/geometry';
import { useAppStore } from '@/store';

const MIN_SCALE = 0.1;
const MAX_SCALE = 10;
const ZOOM_FACTOR = 1.1; // each wheel notch zooms by 10%
const FIT_PADDING = 0.12; // keep ~12% breathing room around the plan when fitting

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

  /**
   * Center and zoom the view so the whole active-floor plan fits in the SVG with padding.
   * Plotting maps world (x, y) → screen (x·scale + offsetX, −y·scale + offsetY), so the
   * offsets place the plan's center at the element's center. No-op when the plan is empty.
   */
  const fitToContent = useCallback(() => {
    const el = svgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    const st = useAppStore.getState();
    const pts: Point2D[] = [];
    for (const v of Object.values(st.vertices)) pts.push(v.position);
    for (const f of Object.values(st.furniture)) pts.push(f.position);
    for (const r of Object.values(st.roads)) { pts.push(r.start); pts.push(r.end); }
    if (pts.length === 0) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const p of pts) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }
    const worldW = Math.max(maxX - minX, 1);
    const worldH = Math.max(maxY - minY, 1);
    const usableW = rect.width * (1 - 2 * FIT_PADDING);
    const usableH = rect.height * (1 - 2 * FIT_PADDING);
    const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.min(usableW / worldW, usableH / worldH)));

    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    setViewTransform({
      scale,
      offsetX: rect.width / 2 - cx * scale,
      offsetY: rect.height / 2 + cy * scale,
    });
  }, [svgRef]);

  // Re-fit whenever something asks (sample load, import, manual "Center view" button).
  const fitViewNonce = useAppStore((s) => s.fitViewNonce);
  useEffect(() => {
    if (fitViewNonce === 0) return; // 0 is the initial value — nothing requested yet
    fitToContent();
  }, [fitViewNonce, fitToContent]);

  // Auto-fit once when the plan first appears (covers async load from IndexedDB on refresh,
  // so a saved plan opens centered instead of off in a corner). Guarded so it never fights
  // the user's panning afterwards.
  const didInitialFit = useRef(false);
  const wallCount = useAppStore((s) => Object.keys(s.walls).length);
  useEffect(() => {
    if (didInitialFit.current || wallCount === 0) return;
    didInitialFit.current = true;
    // Defer one frame so the SVG has its final layout size.
    const id = requestAnimationFrame(() => fitToContent());
    return () => cancelAnimationFrame(id);
  }, [wallCount, fitToContent]);

  return {
    viewTransform,
    panBy,
    fitToContent,
    handlers: {
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
    },
  };
}
