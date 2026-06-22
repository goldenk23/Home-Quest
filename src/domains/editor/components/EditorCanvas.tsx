// src/domains/editor/components/EditorCanvas.tsx  (Part 6 version — adds drawing)

import React, { useRef, useCallback, useEffect } from 'react';
import { useAppStore } from '@/store';
import { useEndpoints } from '@/store/selectors/editorSelectors';
import { screenToWorld } from '../services/geometry';
import { applySnapping } from '../hooks/useSnapping';
import { usePanZoom } from '../hooks/usePan';
import { useWallDrawing } from '../hooks/useWallDrawing';
import { GridLayer } from './GridLayer';
import { RoomLayer } from './RoomLayer';
import { WallLayer } from './WallLayer';
import { FurnitureLayer } from './FurnitureLayer';
import { SelectionLayer } from './SelectionLayer';
import { DrawingPreview } from './DrawingPreview';

export const EditorCanvas: React.FC = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const { viewTransform, handlers } = usePanZoom(svgRef);
  const endpoints = useEndpoints();
  const snapConfig = useAppStore((s) => s.snapConfig);
  const activeTool = useAppStore((s) => s.activeTool); // from the UI slice (Part 4)

  const { drawStart, handleClick, cancel } = useWallDrawing();

  const viewTransformRef = useRef(viewTransform);
  viewTransformRef.current = viewTransform;

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current) return;
      handlers.onMouseMove(e);
      const rect = svgRef.current.getBoundingClientRect();
      const raw = screenToWorld({ px: e.clientX, py: e.clientY }, rect, viewTransformRef.current);
      
      const origin = activeTool === 'wall' ? drawStart : null;
      const snapped = applySnapping(raw, endpoints, snapConfig, origin, e.shiftKey);
      
      useAppStore.setState({ currentMouseWorld: snapped });
    },
    [endpoints, snapConfig, handlers, activeTool, drawStart]
  );

  const handleSvgClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (e.button !== 0 || e.altKey) return; // ignore pan gestures
      const state = useAppStore.getState();
      const cursor = state.currentMouseWorld;
      if (!cursor) return;

      if (activeTool === 'wall') {
        handleClick(cursor);
        return;
      }

      if (activeTool === 'select') {
        // Hit-testing for walls
        let clickedWallId = null;
        for (const wall of Object.values(state.walls)) {
          const start = state.vertices[wall.startVertexId]?.position;
          const end = state.vertices[wall.endVertexId]?.position;
          if (!start || !end) continue;

          // Distance from point to line segment
          const l2 = (end.x - start.x) ** 2 + (end.y - start.y) ** 2;
          let t = 0;
          if (l2 > 0) {
            t = ((cursor.x - start.x) * (end.x - start.x) + (cursor.y - start.y) * (end.y - start.y)) / l2;
            t = Math.max(0, Math.min(1, t));
          }
          const projX = start.x + t * (end.x - start.x);
          const projY = start.y + t * (end.y - start.y);
          const dist = Math.sqrt((cursor.x - projX) ** 2 + (cursor.y - projY) ** 2);

          if (dist <= wall.thickness / 2 + 5) { // 5cm grace area for clicking
            clickedWallId = wall.id;
            break;
          }
        }

        if (clickedWallId) {
          state.select([clickedWallId]);
        } else {
          state.clearSelection();
        }
      }
    },
    [activeTool, handleClick]
  );

  // Keyboard shortcuts: Escape to cancel drawing, Delete/Backspace to erase selected walls
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cancel();
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const state = useAppStore.getState();
        if (state.selectedIds.length > 0) {
          state.selectedIds.forEach((id) => {
            if (state.walls[id]) state.removeWall(id);
          });
          state.clearSelection();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [cancel]);

  return (
    <svg
      ref={svgRef}
      className="w-full h-full bg-neutral-900 cursor-crosshair"
      onMouseMove={handleMouseMove}
      onWheel={handlers.onWheel}
      onMouseDown={handlers.onMouseDown}
      onMouseUp={handlers.onMouseUp}
      onClick={handleSvgClick}
      onContextMenu={(e) => {
        e.preventDefault(); // prevent browser right-click menu
        cancel(); // finish/drop the wall tool chain
      }}
    >
      <g transform={`translate(${viewTransform.offsetX}, ${viewTransform.offsetY}) scale(${viewTransform.scale})`}>
        <GridLayer gridSize={snapConfig.gridSize} />
        <RoomLayer />
        <WallLayer />
        <FurnitureLayer />
        <SelectionLayer />
        {activeTool === 'wall' && <DrawingPreview start={drawStart} />}
      </g>
    </svg>
  );
};
