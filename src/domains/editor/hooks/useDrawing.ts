/**
 * ============================================================================
 * PURPOSE: High-Performance Live Drawing
 * ============================================================================
 * 
 * WHY IT EXISTS:
 * When you are dragging your mouse to draw a wall, the screen needs to update
 * 60 times a second. If we asked React to redraw the whole app 60 times a second,
 * your computer would lag and freeze.
 * 
 * WHAT IT DOES:
 * This file handles the "rubber-band" line you see when dragging a wall. 
 * Instead of asking React to redraw the screen, this code reaches directly into
 * the web browser and physically moves the end of the line to match your mouse.
 * 
 * MENTAL MODEL:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                                                                 │
 * │   Start Dot ────────────(Rubber Band Line)────────► Mouse X,Y   │
 * │   (Pinned down)                                    (Moving fast)│
 * │                                                                 │
 * └─────────────────────────────────────────────────────────────────┘
 */

import { useRef, useEffect } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';

export function useTransientDrawing() {
  // Memory (What we remember without triggering React to redraw)
  // previewRef acts as a direct physical handle to the line on the screen
  const previewRef = useRef<SVGLineElement>(null);
  
  // drawStart remembers the exact X,Y coordinate where you first clicked
  const drawStart = useRef<Point2D | null>(null);

  useEffect(() => {
    // We subscribe to the global memory to listen for the mouse moving.
    // By using `subscribe` directly, we bypass React entirely so it doesn't freeze!
    const unsub = useAppStore.subscribe((state, prevState) => {
      const mousePos = state.currentMouseWorld;
      
      // Only do the work if the mouse actually moved to a new position
      if (mousePos !== prevState.currentMouseWorld) {
        // If we have our handle to the line, and we started drawing, and we have a mouse position:
        if (previewRef.current && drawStart.current && mousePos) {
          // DIRECT DOM MANIPULATION:
          // We reach straight into the browser and yank the end of the line 
          // to exactly where the mouse is. It's incredibly fast!
          previewRef.current.setAttribute('x2', String(mousePos.x));
          previewRef.current.setAttribute('y2', String(-mousePos.y));
        }
      }
    });
    
    // When we are done, we clean up our listener so we don't cause memory leaks
    return unsub;
  }, []);

  return { previewRef, drawStart };
}
