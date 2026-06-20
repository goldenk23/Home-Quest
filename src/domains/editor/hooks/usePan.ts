/**
 * ============================================================================
 * WHAT IS THIS FILE FOR?
 * ============================================================================
 * 
 * This file handles the "Camera" controls for the 2D floor plan editor.
 * It lets the user zoom in/out with the mouse wheel, and pan (drag the map 
 * around) by holding the middle mouse button or the Alt key.
 *
 * THE MENTAL MODEL:
 * 
 * Think of your floor plan as a giant paper map, and the computer screen as 
 * a small rectangular window you are looking through.
 * 
 * 1. PANNING (Dragging): 
 *    You are sliding the paper map around underneath the window. 
 *    We track this using "offsetX" and "offsetY".
 * 
 * 2. ZOOMING (Scrolling): 
 *    You are moving the window closer to or further from the map. 
 *    We track this using "scale".
 * 
 * 3. ZOOM-TO-CURSOR (The Magic Trick): 
 *    When you scroll the mouse wheel, the point on the map exactly underneath 
 *    your mouse pointer stays perfectly still, while everything else expands 
 *    or shrinks around it. This feels natural and keeps you from getting lost!
 *
 * DIAGRAM: PAN/ZOOM EVENT LOGIC
 *
 * To view the interactive flowchart of how the event handlers interact,
 * simply Ctrl+Click the link below to open it in Mermaid Live Editor:
 * 
 * https://mermaid.live/view#base64:eyJjb2RlIjoiZ3JhcGggVERcbiAgICAlJSBVc2VyIElucHV0c1xuICAgIHN1YmdyYXBoIElucHV0cyBbXCJVc2VyIEV2ZW50c1wiXVxuICAgICAgICBXaGVlbChbTW91c2UgU2Nyb2xsXSlcbiAgICAgICAgRG93bihbTW91c2UgRG93bl0pXG4gICAgICAgIE1vdmUoW01vdXNlIE1vdmVdKVxuICAgICAgICBVcChbTW91c2UgVXBdKVxuICAgIGVuZFxuXG4gICAgJSUgV2hlZWwgTG9naWNcbiAgICBzdWJncmFwaCBab29tIFtcIm9uV2hlZWwgKFpvb20gTG9naWMpXCJdXG4gICAgICAgIFcxe1Njcm9sbCBEaXJlY3Rpb24/fVxuICAgICAgICBXMltGYWN0b3IgPSAxLjE8YnIvPlpvb20gSW5dXG4gICAgICAgIFczW0ZhY3RvciA9IDAuOTxici8+Wm9vbSBPdXRdXG4gICAgICAgIFc0W0NsYW1wIFNjYWxlPGJyLz5NaW46IDAuMSwgTWF4OiAxMF1cbiAgICAgICAgVzVbQ2FsY3VsYXRlIG5ldyBPZmZzZXQ8YnIvPktlZXAgbWFwIGZpeGVkIHVuZGVyIEN1cnNvcl1cbiAgICAgICAgVzZbKFVwZGF0ZSBTdGF0ZTo8YnIvPnZpZXdUcmFuc2Zvcm0pXVxuICAgIGVuZFxuXG4gICAgV2hlZWwgLS0+fFRyaWdnZXJzfCBXMVxuICAgIFcxIC0tPnxTY3JvbGwgVXB8IFcyXG4gICAgVzEgLS0+fFNjcm9sbCBEb3dufCBXM1xuICAgIFcyIC0tPiBXNFxuICAgIFczIC0tPiBXNFxuICAgIFc0IC0tPiBXNVxuICAgIFc1IC0tPiBXNlxuXG4gICAgJSUgTW91c2UgRG93biBMb2dpY1xuICAgIHN1YmdyYXBoIERvd25Mb2dpYyBbXCJvbk1vdXNlRG93biAoU3RhcnQgUGFuKVwiXVxuICAgICAgICBEMXtNaWRkbGUgQ2xpY2sgT1I8YnIvPkFsdCArIExlZnQgQ2xpY2s/fVxuICAgICAgICBEMltTZXQgaXNQYW5uaW5nID0gdHJ1ZV1cbiAgICAgICAgRDNbUmVjb3JkIGxhc3RNb3VzZSBYLCBZXVxuICAgIGVuZFxuXG4gICAgRG93biAtLT58VHJpZ2dlcnN8IEQxXG4gICAgRDEgLS0+fFllc3wgRDJcbiAgICBEMiAtLT4gRDNcbiAgICBEMSAtLT58Tm98IElnbm9yZTFbSWdub3JlIEV2ZW50XVxuXG4gICAgJSUgTW91c2UgTW92ZSBMb2dpY1xuICAgIHN1YmdyYXBoIE1vdmVMb2dpYyBbXCJvbk1vdXNlTW92ZSAoRXhlY3V0ZSBQYW4pXCJdXG4gICAgICAgIE0xe2lzUGFubmluZyA9PSB0cnVlP31cbiAgICAgICAgTTJbQ2FsYyBkeCA9IGN1cnJlbnRYIC0gbGFzdFg8YnIvPkNhbGMgZHkgPSBjdXJyZW50WSAtIGxhc3RZXVxuICAgICAgICBNM1soVXBkYXRlIFN0YXRlOjxici8+b2Zmc2V0WCArPSBkeCwgb2Zmc2V0WSArPSBkeSldXG4gICAgICAgIE00W1VwZGF0ZSBsYXN0TW91c2UgWCwgWV1cbiAgICBlbmRcblxuICAgIE1vdmUgLS0+fFRyaWdnZXJzfCBNMVxuICAgIE0xIC0tPnxZZXN8IE0yXG4gICAgTTIgLS0+IE0zXG4gICAgTTMgLS0+IE00XG4gICAgTTEgLS0+fE5vfCBJZ25vcmUyW0lnbm9yZSBFdmVudF1cblxuICAgICUlIE1vdXNlIFVwIExvZ2ljXG4gICAgc3ViZ3JhcGggVXBMb2dpYyBbXCJvbk1vdXNlVXAgKEVuZCBQYW4pXCJdXG4gICAgICAgIFUxW1NldCBpc1Bhbm5pbmcgPSBmYWxzZV1cbiAgICBlbmRcblxuICAgIFVwIC0tPnxUcmlnZ2Vyc3wgVTEiLCJtZXJtYWlkIjoie1widGhlbWVcIjogXCJkZWZhdWx0XCJ9IiwiYXV0b1N5bmMiOnRydWUsInVwZGF0ZURpYWdyYW0iOnRydWV9
 * ============================================================================
 * 
 *  Mouse scroll: event when the user scrolls the mouse wheel (or trackpad) while hovering over the SVG.
 * *  Mouse down: event when the user presses a mouse button down on the SVG.
 * *  Mouse move: event when the user moves the mouse while a button is pressed down on the SVG.
 * *  Mouse up: event when the user releases a mouse button that was pressed down on the SVG
 */

import { useState, useCallback, useRef } from 'react';
import type { RefObject, WheelEvent, MouseEvent } from 'react';
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
export function usePanZoom(svgRef: RefObject<SVGSVGElement>) {
  const [viewTransform, setViewTransform] = useState<ViewTransform>({
    scale: 1,
    offsetX: 0,
    offsetY: 0,
  });

  // Refs hold "in‑flight" gesture data without causing re‑renders on every mouse move.
  const isPanning = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  const handleWheel = useCallback(
    (e: WheelEvent) => {
      e.preventDefault();
      // Scroll up = zoom in, scroll down = zoom out.
      const factor = e.deltaY > 0 ? 1 / ZOOM_FACTOR : ZOOM_FACTOR;

      setViewTransform((prev) => {
        const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.scale * factor));
        if (!svgRef.current) return { ...prev, scale: newScale };

        // Keep the point under the cursor fixed while zooming ("zoom to cursor").
        const rect = svgRef.current.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const ratio = newScale / prev.scale;

        return {
          scale: newScale,
          offsetX: mx - (mx - prev.offsetX) * ratio,
          offsetY: my - (my - prev.offsetY) * ratio,
        };
      });
    },
    [svgRef]
  );

  const handleMouseDown = useCallback((e: MouseEvent) => {
    // Pan with middle mouse, or Alt + left click (keeps left click free for drawing).
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanning.current = true;
      lastMouse.current = { x: e.clientX, y: e.clientY };
      e.preventDefault();
    }
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
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

  return {
    viewTransform,
    handlers: {
      onWheel: handleWheel,
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
    },
  };
}