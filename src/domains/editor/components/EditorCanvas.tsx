// src/domains/editor/components/EditorCanvas.tsx

import React, { useRef, useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import { useEndpoints } from '@/store/selectors/editorSelectors';
import { screenToWorld } from '../services/geometry';
import { applySnapping } from '../hooks/useSnapping';
import { usePanZoom } from '../hooks/usePan';
import { useWallDrawing } from '../hooks/useWallDrawing';
import { toWallSegments } from '../services/wallGuides';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import type { Point2D } from '@/types/geometry';
import type { AppStore } from '@/store';
import { GridLayer } from './GridLayer';
import { RoomLayer } from './RoomLayer';
import { WallLayer } from './WallLayer';
import { FurnitureLayer } from './FurnitureLayer';
import { SelectionLayer } from './SelectionLayer';
import { DrawingPreview } from './DrawingPreview';
import { VastuOverlay2D } from '@/domains/vastu/components/VastuOverlay2D';
import { CompassRose } from './CompassRose';

/** Point-in-(rotated)-rectangle test for furniture footprints (with a grab margin in cm). */
function hitTestFurniture(cursor: Point2D, furniture: AppStore['furniture'], margin = 0): string | null {
  for (const item of Object.values(furniture)) {
    const dx = cursor.x - item.position.x;
    const dy = cursor.y - item.position.y;
    // Rotate the delta into the item's local frame (inverse of its rotation).
    const cos = Math.cos(item.rotation);
    const sin = Math.sin(item.rotation);
    const lx = dx * cos + dy * sin;
    const ly = -dx * sin + dy * cos;
    if (Math.abs(lx) <= item.bounds.width / 2 + margin && Math.abs(ly) <= item.bounds.depth / 2 + margin) {
      return item.id;
    }
  }
  return null;
}

/** Distance-based hit test for wall centerlines (with a small grace radius). */
function hitTestWall(cursor: Point2D, state: AppStore): string | null {
  for (const wall of Object.values(state.walls)) {
    const start = state.vertices[wall.startVertexId]?.position;
    const end = state.vertices[wall.endVertexId]?.position;
    if (!start || !end) continue;
    const l2 = (end.x - start.x) ** 2 + (end.y - start.y) ** 2;
    let t = 0;
    if (l2 > 0) {
      t = ((cursor.x - start.x) * (end.x - start.x) + (cursor.y - start.y) * (end.y - start.y)) / l2;
      t = Math.max(0, Math.min(1, t));
    }
    const projX = start.x + t * (end.x - start.x);
    const projY = start.y + t * (end.y - start.y);
    const dist = Math.sqrt((cursor.x - projX) ** 2 + (cursor.y - projY) ** 2);
    if (dist <= wall.thickness / 2 + 5) return wall.id;
  }
  return null;
}

/** Ray-casting point-in-polygon test (polygon points in world cm). */
function pointInPolygon(p: Point2D, polygon: Point2D[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y;
    const xj = polygon[j].x, yj = polygon[j].y;
    const intersect = yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/**
 * Finds the room whose polygon contains the cursor. When boxes are nested or overlap,
 * the smallest-area room wins so the innermost room is selectable.
 */
function hitTestRoom(cursor: Point2D, state: AppStore): string | null {
  let bestId: string | null = null;
  let bestArea = Infinity;
  for (const room of Object.values(state.rooms)) {
    const poly = room.boundaryVertexIds
      .map((id) => state.vertices[id]?.position)
      .filter((pt): pt is Point2D => Boolean(pt));
    if (poly.length < 3) continue;
    if (!pointInPolygon(cursor, poly)) continue;
    // Shoelace area (abs) to pick the tightest containing room.
    let area = 0;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      area += poly[j].x * poly[i].y - poly[i].x * poly[j].y;
    }
    area = Math.abs(area) / 2;
    if (area < bestArea) {
      bestArea = area;
      bestId = room.id;
    }
  }
  return bestId;
}

export const EditorCanvas: React.FC = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const { viewTransform, panBy, handlers } = usePanZoom(svgRef);
  const endpoints = useEndpoints();
  const snapConfig = useAppStore((s) => s.snapConfig);
  const activeTool = useAppStore((s) => s.activeTool);

  const { drawStart, chainOrigin, handleClick, cancel } = useWallDrawing();

  const viewTransformRef = useRef(viewTransform);
  viewTransformRef.current = viewTransform;

  // Drag state (refs avoid re-renders on every mouse move).
  const dragRef = useRef<{ kind: 'furniture' | 'wall'; id: string } | null>(null);
  const dragLastWorldRef = useRef<Point2D | null>(null);
  const didDragRef = useRef(false);
  // Grab-to-pan state (left-drag on empty space while using the Select tool).
  const panningRef = useRef(false);
  const panLastRef = useRef({ x: 0, y: 0 });

  const GRAB_MARGIN = 8; // cm of slack so components are easy to grab
  const ORTHO_THRESHOLD_DEG = 28; // walls within this of an axis get straightened on drop

  // Live drag readout (length + angle) shown while dragging a component.
  const [dragHud, setDragHud] = useState<{ sx: number; sy: number; cx: number; cy: number } | null>(null);

  /**
   * Smart alignment applied when a component drag ends, so the house keeps clean right
   * angles instead of drifting into arbitrary shapes.
   *  - Furniture: snaps position to the grid and rotation to the nearest 90°.
   *  - Walls: snaps the moved endpoints to the grid and straightens every wall meeting
   *    them that is near-axis-aligned (horizontal/vertical), restoring orthogonality.
   */
  const smartAlign = useCallback((drag: { kind: 'furniture' | 'wall'; id: string }) => {
    const st = useAppStore.getState();
    const grid = st.snapConfig.gridSize || 10;
    const snap = (v: number) => Math.round(v / grid) * grid;

    if (drag.kind === 'furniture') {
      const item = st.furniture[drag.id];
      if (!item) return;
      const step = Math.PI / 2;
      st.moveFurniture(drag.id, { x: snap(item.position.x), y: snap(item.position.y) });
      st.rotateFurniture(drag.id, Math.round(item.rotation / step) * step);
      return;
    }

    const wall = st.walls[drag.id];
    if (!wall) return;
    const movedIds = [wall.startVertexId, wall.endVertexId];

    // Compute final positions locally, then apply via moveVertex.
    const pos: Record<string, Point2D> = {};
    for (const vid of movedIds) {
      const p = st.vertices[vid]?.position;
      if (p) pos[vid] = { x: snap(p.x), y: snap(p.y) };
    }
    const getPos = (id: string): Point2D => pos[id] ?? st.vertices[id]?.position ?? { x: 0, y: 0 };

    for (const vid of movedIds) {
      const v = getPos(vid);
      const connected = st.vertices[vid]?.connectedWalls ?? [];
      for (const wid of connected) {
        const w = st.walls[wid];
        if (!w) continue;
        const otherId = w.startVertexId === vid ? w.endVertexId : w.startVertexId;
        const o = getPos(otherId);
        const dx = o.x - v.x;
        const dy = o.y - v.y;
        const angle = (Math.atan2(Math.abs(dy), Math.abs(dx)) * 180) / Math.PI; // 0=horiz, 90=vert
        if (angle <= ORTHO_THRESHOLD_DEG) {
          pos[vid] = { x: v.x, y: o.y }; // straighten to horizontal
        } else if (angle >= 90 - ORTHO_THRESHOLD_DEG) {
          pos[vid] = { x: o.x, y: v.y }; // straighten to vertical
        }
      }
    }

    for (const [id, p] of Object.entries(pos)) {
      st.moveVertex(id, p);
    }
  }, []);

  const computeWorld = useCallback(
    (e: React.MouseEvent<SVGSVGElement>): Point2D | null => {
      if (!svgRef.current) return null;
      const rect = svgRef.current.getBoundingClientRect();
      const raw = screenToWorld({ px: e.clientX, py: e.clientY }, rect, viewTransformRef.current);
      const origin = activeTool === 'wall' ? drawStart : null;
      // When drawing, allow snapping onto existing wall centerlines so a wall drawn
      // across a room connects cleanly and splits it. (Not needed for select/furniture.)
      const st = useAppStore.getState();
      const wallSegments = activeTool === 'wall' ? toWallSegments(st.walls, st.vertices) : [];
      return applySnapping(raw, endpoints, snapConfig, origin, e.shiftKey, wallSegments);
    },
    [activeTool, drawStart, endpoints, snapConfig]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      handlers.onMouseDown(e); // pan (alt / middle) — no-ops otherwise
      if (e.button !== 0 || e.altKey) return;

      if (activeTool === 'select') {
        const cursor = computeWorld(e);
        if (!cursor) return;
        const state = useAppStore.getState();

        // 1) Grab a specific component (furniture first, then walls) to move it.
        const furnitureId = hitTestFurniture(cursor, state.furniture, GRAB_MARGIN);
        if (furnitureId) {
          state.select([furnitureId]);
          dragRef.current = { kind: 'furniture', id: furnitureId };
          dragLastWorldRef.current = cursor;
          didDragRef.current = false;
          setDragHud({ sx: cursor.x, sy: cursor.y, cx: cursor.x, cy: cursor.y });
          return;
        }
        const wallId = hitTestWall(cursor, state);
        if (wallId) {
          state.select([wallId]);
          dragRef.current = { kind: 'wall', id: wallId };
          dragLastWorldRef.current = cursor;
          didDragRef.current = false;
          setDragHud({ sx: cursor.x, sy: cursor.y, cx: cursor.x, cy: cursor.y });
          return;
        }

        // 2) Empty space → grab the whole diagram to pan it.
        panningRef.current = true;
        panLastRef.current = { x: e.clientX, y: e.clientY };
        didDragRef.current = false;
        if (svgRef.current) svgRef.current.style.cursor = 'grabbing';
      }
    },
    [handlers, activeTool, computeWorld]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current) return;
      handlers.onMouseMove(e);

      // Grab-to-pan: drag the whole diagram around.
      if (panningRef.current) {
        const dx = e.clientX - panLastRef.current.x;
        const dy = e.clientY - panLastRef.current.y;
        panLastRef.current = { x: e.clientX, y: e.clientY };
        if (dx !== 0 || dy !== 0) {
          panBy(dx, dy);
          didDragRef.current = true;
        }
        return;
      }

      const snapped = computeWorld(e);
      if (!snapped) return;
      useAppStore.setState({ currentMouseWorld: snapped });

      // Drag the selected component by the world-space delta (smooth — no jump-to-cursor).
      const drag = dragRef.current;
      const last = dragLastWorldRef.current;
      if (drag && last) {
        const dx = snapped.x - last.x;
        const dy = snapped.y - last.y;
        if (dx !== 0 || dy !== 0) {
          const state = useAppStore.getState();
          if (drag.kind === 'furniture') {
            const item = state.furniture[drag.id];
            if (item) state.moveFurniture(drag.id, { x: item.position.x + dx, y: item.position.y + dy });
          } else {
            const wall = state.walls[drag.id];
            if (wall) {
              const sv = state.vertices[wall.startVertexId]?.position;
              const ev = state.vertices[wall.endVertexId]?.position;
              if (sv) state.moveVertex(wall.startVertexId, { x: sv.x + dx, y: sv.y + dy });
              if (ev) state.moveVertex(wall.endVertexId, { x: ev.x + dx, y: ev.y + dy });
            }
          }
          dragLastWorldRef.current = snapped;
          didDragRef.current = true;
        }
        setDragHud((prev) => (prev ? { ...prev, cx: snapped.x, cy: snapped.y } : prev));
      }
    },
    [handlers, computeWorld, panBy]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      handlers.onMouseUp();
      void e;
      // Smart-align the component we just dragged so the layout stays orthogonal.
      const drag = dragRef.current;
      if (drag && didDragRef.current) smartAlign(drag);
      dragRef.current = null;
      dragLastWorldRef.current = null;
      panningRef.current = false;
      setDragHud(null);
      if (svgRef.current) svgRef.current.style.cursor = '';
    },
    [handlers, smartAlign]
  );

  const handleSvgClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (e.button !== 0 || e.altKey) return;
      // If this "click" was actually the end of a furniture drag, don't treat it as a click.
      if (didDragRef.current) {
        didDragRef.current = false;
        return;
      }
      const state = useAppStore.getState();
      const cursor = state.currentMouseWorld;
      if (!cursor) return;

      if (activeTool === 'wall') {
        handleClick(cursor);
        return;
      }

      if (activeTool === 'furniture') {
        const catalogId = state.furnitureCatalogId;
        const entry = getCatalogEntry(catalogId);
        const id = state.addFurniture({
          position: cursor,
          rotation: 0,
          scale: 1,
          catalogId,
          roomId: null,
          bounds: { width: entry.bounds.width, depth: entry.bounds.depth },
        });
        state.select([id]);
        return;
      }

      if (activeTool === 'select') {
        const furnitureId = hitTestFurniture(cursor, state.furniture, GRAB_MARGIN);
        if (furnitureId) {
          state.select([furnitureId]);
          return;
        }
        const wallId = hitTestWall(cursor, state);
        if (wallId) {
          state.select([wallId]);
          return;
        }
        // Lowest priority: clicking inside a room selects that room (so it can be assigned).
        const roomId = hitTestRoom(cursor, state);
        if (roomId) {
          state.select([roomId]);
        } else {
          state.clearSelection();
        }
      }
    },
    [activeTool, handleClick]
  );

  // Keyboard: Escape cancels drawing; Delete/Backspace erases selection; R rotates furniture.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;

      if (e.key === 'Escape') cancel();

      if (e.key === 'Delete' || e.key === 'Backspace') {
        const state = useAppStore.getState();
        if (state.selectedIds.length > 0) {
          state.selectedIds.forEach((id) => {
            if (state.walls[id]) state.removeWall(id);
            if (state.furniture[id]) state.removeFurniture(id);
          });
          state.clearSelection();
        }
      }

      if (e.key === 'r' || e.key === 'R') {
        const state = useAppStore.getState();
        const delta = (e.shiftKey ? -1 : 1) * (Math.PI / 12); // ±15°
        state.selectedIds.forEach((id) => {
          const item = state.furniture[id];
          if (item) state.rotateFurniture(id, item.rotation + delta);
        });
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [cancel]);

  const cursorClass =
    activeTool === 'wall' || activeTool === 'furniture' ? 'cursor-crosshair' : 'cursor-grab';

  return (
    <svg
      ref={svgRef}
      className={`w-full h-full bg-neutral-900 ${cursorClass}`}
      onMouseMove={handleMouseMove}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        handlers.onMouseUp();
        dragRef.current = null;
        dragLastWorldRef.current = null;
        panningRef.current = false;
        setDragHud(null);
        if (svgRef.current) svgRef.current.style.cursor = '';
      }}
      onClick={handleSvgClick}
      onContextMenu={(e) => {
        e.preventDefault();
        cancel();
      }}
    >
      <g transform={`translate(${viewTransform.offsetX}, ${viewTransform.offsetY}) scale(${viewTransform.scale})`}>
        <GridLayer gridSize={snapConfig.gridSize} />
        <RoomLayer />
        <WallLayer />
        <FurnitureLayer />
        <SelectionLayer />
        <VastuOverlay2D />
        {activeTool === 'wall' && <DrawingPreview start={drawStart} chainOrigin={chainOrigin} />}
        {dragHud && <DragReadout {...dragHud} />}
      </g>
      {/* Screen-anchored compass (outside the pan/zoom group) so it never moves or scales. */}
      <CompassRose />
    </svg>
  );
};

/** Live "how far / what angle" readout drawn while dragging a component. */
const DragReadout: React.FC<{ sx: number; sy: number; cx: number; cy: number }> = ({ sx, sy, cx, cy }) => {
  const dx = cx - sx;
  const dy = cy - sy;
  const lengthM = Math.hypot(dx, dy) / 100;
  let angleDeg = (Math.atan2(dy, dx) * 180) / Math.PI;
  if (angleDeg < 0) angleDeg += 360;
  if (lengthM === 0) return null;
  return (
    <g pointerEvents="none">
      <line x1={sx} y1={-sy} x2={cx} y2={-cy} stroke="#f59e0b" strokeWidth={2} strokeDasharray="8 6" />
      <circle cx={sx} cy={-sy} r={4} fill="#f59e0b" />
      <text
        x={cx}
        y={-cy - 14}
        fill="#fff"
        stroke="#000"
        strokeWidth={0.5}
        paintOrder="stroke"
        fontSize={16}
        fontFamily="sans-serif"
        textAnchor="middle"
      >
        {`${lengthM.toFixed(2)} m  |  ${Math.round(angleDeg)}°`}
      </text>
    </g>
  );
};
