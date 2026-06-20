import React, { useRef, useCallback } from 'react';
import { useAppStore } from '@/store';
import { useEndpoints } from '@/store/selectors/editorSelector';
import { screenToWorld } from '../services/geometry';
import { applySnapping } from '../hooks/useSnapping';
import { usePanZoom } from '../hooks/usePan';
import { GridLayer } from './GridLayer';
import { RoomLayer } from './RoomLayer';
import { WallLayer } from './WallLayer';
import { FurnitureLayer } from './FurnitureLayer';
import { SelectionLayer } from './SelectionLayer';

/**
 * ============================================================================
 * WHAT IS THIS FILE FOR?
 * ============================================================================
 * 
 * This is the master "Canvas". It holds everything together! Think of it as 
 * the actual physical piece of paper that all the other layers draw on.
 * 
 * THE MENTAL MODEL:
 * 
 * 1. THE CAMERA: It fetches the pan/zoom math from `usePanZoom()` and wraps 
 *    EVERYTHING inside a master `<g>` layer. When you zoom or pan, it simply 
 *    moves this single master layer, dragging all the walls and rooms with it!
 * 
 * 2. THE MOUSE: It listens to exactly where your mouse is moving across the 
 *    screen. It mathematically converts your screen pixels into "World Coordinates"
 *    (centimeters in the house). 
 * 
 * 3. THE MAGNETS: It takes those World Coordinates and passes them to the 
 *    Snapping engine. If your mouse gets close to a corner, the engine acts 
 *    like a magnet and snaps your coordinates exactly to that corner!
 * 
 * DIAGRAM: HOW THE CANVAS WORKS
 *
 * To view a visual flowchart of this architecture, simply Ctrl+Click 
 * the link below to open it in Mermaid Live Editor:
 * 
 * https://mermaid.live/view#base64:eyJjb2RlIjoiZ3JhcGggVERcbiAgICBjbGFzc0RlZiBsb2dpYyBmaWxsOiM0ZjQ2ZTUsc3Ryb2tlOiMzMTJlODEsc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG4gICAgY2xhc3NEZWYgc3ZnIGZpbGw6I2Y1OWUwYixzdHJva2U6Izc4MzUwZixzdHJva2Utd2lkdGg6MnB4LGNvbG9yOiNmZmZcbiAgICBjbGFzc0RlZiBsYXllciBmaWxsOiMxMGI5ODEsc3Ryb2tlOiMwNjRlM2Isc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG5cbiAgICBzdWJncmFwaCBTdGVwMSBbXCJTdGVwIDE6IFRoZSBNb3VzZSBIYW5kbGVyXCJdXG4gICAgICAgIE0xW1wiTW91c2UgTW92ZXMhXCJdOjo6bG9naWNcbiAgICAgICAgTTJbXCJDYWxjdWxhdGUgcmVhbCBXb3JsZCBDb29yZGluYXRlPGJyLz4odXNpbmcgc2NyZWVuVG9Xb3JsZClcIl06Ojpsb2dpY1xuICAgICAgICBNM1tcIkFwcGx5IE1hZ25ldGljIFNuYXBwaW5nPGJyLz4ocHVsbHMgY3Vyc29yIHRoZSBuZWFyZXN0IGNvcm5lcilcIl06Ojpsb2dpY1xuICAgICAgICBNNFsS2F2ZSB0byBnbG9iYWwgc3RvcmU8YnIvPmN1cnJlbnRNb3VzZVdvcmxkXCJdOjo6bG9naWNcbiAgICAgICAgTTEgLS0+IE0yIC0tPiBNMyAtLT4gTTRcbiAgICBlbmRcblxuICAgIHN1YmdyYXBoIFN0ZXAyIFtcIlN0ZXAgMjogVGhlIENhbWVyYSBUcmFuc2Zvcm1cIl1cbiAgICAgICAgQzFbXCJHZXQgY2FtZXJhIChQYW4vWm9vbSk8YnIvPmZyb20gdXNlUGFuWm9vbSgpXCJdOjo6bG9naWNcbiAgICAgICAgQzJbXCJBcHBseSB0byBtYXN0ZXIgJmx0O2cmZ3Q7IGxheWVyPGJyLz50cmFuc2xhdGUoeCx5KSBzY2FsZShzKVwiXTo6OnN2Z1xuICAgICAgICBDMSAtLT4gQzJcbiAgICBlbmRcblxuICAgIHN1YmdyYXBoIFN0ZXAzIFtcIlN0ZXAgMzogVGhlIERyYXdpbmcgTGF5ZXJzXCJdXG4gICAgICAgIEwxW1wiR3JpZExheWVyXCJdOjo6bGF5ZXJcbiAgICAgICAgTDJbXCJSb29tTGF5ZXJcIl06OjpsYXllclxuICAgICAgICBMM1tcIldhbGxMYXllclwiXTo6OmxheWVyXG4gICAgICAgIEw0W1wiRnVybml0dXJlTGF5ZXJcIl06OjpsYXllclxuICAgICAgICBMNVtcIlNlbGVjdGlvbkxheWVyXCJdOjo6bGF5ZXJcbiAgICAgICAgQzIgLS4tPnxMYXllciAxfCBMMVxuICAgICAgICBDMiAtLi0+fExheWVyIDJ8IEwyXG4gICAgICAgIEMyIC0uLT58TGF5ZXIgM3wgTDNcbiAgICAgICAgQzIgLS4tPnxMYXllciA0fCBMNFxuICAgICAgICBDMiAtLi0+fExheWVyIDV8IEw1XG4gICAgZW5kIiwibWVybWFpZCI6IntcInRoZW1lXCI6IFwiZGVmYXVsdFwifSIsImF1dG9TeW5jIjp0cnVlLCJ1cGRhdGVEaWFncmFtIjp0cnVlfQ==
 * ============================================================================
 */
export const EditorCanvas: React.FC = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const { viewTransform, handlers } = usePanZoom(svgRef as React.RefObject<SVGSVGElement>);
  const endpoints = useEndpoints();
  const snapConfig = useAppStore((s) => s.snapConfig);

  // Keep the latest transform in a ref so handleMouseMove doesn't need to be
  // recreated on every pan/zoom frame (avoids re-binding the SVG listener constantly).
  const viewTransformRef = useRef(viewTransform);
  React.useLayoutEffect(() => {
    viewTransformRef.current = viewTransform;
  }, [viewTransform]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current) return;
      // Let the pan handler run first (it no‑ops unless a pan gesture is active).
      handlers.onMouseMove(e);

      const rect = svgRef.current.getBoundingClientRect();
      const raw = screenToWorld({ px: e.clientX, py: e.clientY }, rect, viewTransformRef.current);
      const snapped = applySnapping(raw, endpoints, snapConfig);
      // Transient, high‑frequency value: set it directly without an action.
      useAppStore.setState({ currentMouseWorld: snapped });
    },
    [endpoints, snapConfig, handlers]
  );

  return (
    <svg
      ref={svgRef}
      className="w-full h-full bg-neutral-900 cursor-crosshair"
      onMouseMove={handleMouseMove}
      onWheel={handlers.onWheel}
      onMouseDown={handlers.onMouseDown}
      onMouseUp={handlers.onMouseUp}
    >
      <g transform={`translate(${viewTransform.offsetX}, ${viewTransform.offsetY}) scale(${viewTransform.scale})`}>
        <GridLayer gridSize={snapConfig.gridSize} />
        <RoomLayer />
        <WallLayer />
        <FurnitureLayer />
        <SelectionLayer />
      </g>
    </svg>
  );
};