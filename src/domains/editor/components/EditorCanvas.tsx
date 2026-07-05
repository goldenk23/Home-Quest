// src/domains/editor/components/EditorCanvas.tsx

import React, { useRef, useCallback, useEffect, useState, useMemo } from 'react';
import { useAppStore } from '@/store';
import { useEndpoints, useFloorBelowGeometry } from '@/store/selectors/editorSelectors';
import { screenToWorld } from '../services/geometry';
import { applySnapping } from '../hooks/useSnapping';
import { usePanZoom } from '../hooks/usePan';
import { useWallDrawing } from '../hooks/useWallDrawing';
import { useRoadDrawing } from '../hooks/useRoadDrawing';
import { toWallSegments } from '../services/wallGuides';
import { categoryOf } from '@/domains/shared/materials/finishPalette';
import { getOpeningKind, resolveKind } from '@/domains/shared/openings/openingCatalog';
import { computeOpeningGeometry } from '../services/openingGeometry';
import type { OpeningFamily } from '@/domains/shared/openings/openingCatalog';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import type { Point2D } from '@/types/geometry';
import type { AppStore } from '@/store';
import { GridLayer } from './GridLayer';
import { RoomLayer } from './RoomLayer';
import { WallLayer } from './WallLayer';
import { RoadLayer } from './RoadLayer';
import { PillarLayer } from './PillarLayer';
import { BeamLayer } from './BeamLayer';
import { DeckLayer } from './DeckLayer';
import { RailingLayer } from './RailingLayer';
import { DimensionLayer } from './DimensionLayer';
import { OpeningsLayer } from './OpeningsLayer';
import { FurnitureLayer } from './FurnitureLayer';
import { SelectionLayer } from './SelectionLayer';
import { DrawingPreview } from './DrawingPreview';
import { GhostFloorLayer } from './GhostFloorLayer';
import { StairLayer } from './StairLayer';
import { StairToolOverlay } from './StairToolOverlay';
import { useStairTool } from '../hooks/useStairTool';
import { VastuOverlay2D } from '@/domains/vastu/components/VastuOverlay2D';
import { CompassRose } from './CompassRose';
import { PillarSnapIndicator } from './PillarSnapIndicator';
import { PillarAlignmentGuide } from './PillarAlignmentGuide';
import { snapDeckCornerOutward, extendBeamEndsToPillars } from '../services/structuralJoints';
import { useArrayTool } from '../hooks/useArrayTool';
import { ArrayPreview } from './ArrayPreview';

/** Find nearest pillar to a given point within a maximum distance */
function findNearestPillar(cursor: Point2D, state: AppStore, maxDistance: number = 50): { pillar: typeof state.pillars[string]; distance: number } | null {
  let nearest: { pillar: typeof state.pillars[string]; distance: number } | null = null;
  
  for (const pillar of Object.values(state.pillars)) {
    const dx = cursor.x - pillar.position.x;
    const dy = cursor.y - pillar.position.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    
    // Snap distance should be pillar radius/half-width + tolerance
    const snapRadius = Math.max(pillar.width, pillar.depth) / 2 + maxDistance;
    
    if (distance <= snapRadius && (!nearest || distance < nearest.distance)) {
      nearest = { pillar, distance };
    }
  }
  
  return nearest;
}

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
    if (Math.abs(lx) <= (item.bounds.width * item.scale) / 2 + margin && Math.abs(ly) <= (item.bounds.depth * item.scale) / 2 + margin) {
      return item.id;
    }
  }
  return null;
}

/** Gizmo hit test. Rotation handle is visually at top edge, scale handles at 4 corners. */
function hitTestGizmo(
  cursor: Point2D,
  state: AppStore,
  margin = 5
): { kind: 'gizmo-rotate' | 'gizmo-scale'; id: string } | null {
  for (const id of state.selectedIds) {
    const item = state.furniture[id];
    if (!item) continue;
    
    const dx = cursor.x - item.position.x;
    const dy = cursor.y - item.position.y;
    
    const cos = Math.cos(item.rotation);
    const sin = Math.sin(item.rotation);
    const lx = dx * cos + dy * sin;
    const ly = -dx * sin + dy * cos;
    
    const hw = (item.bounds.width * item.scale) / 2;
    const hd = (item.bounds.depth * item.scale) / 2;
    
    if (Math.abs(lx) <= 10 + margin && Math.abs(ly - (hd + 20)) <= 10 + margin) {
      return { kind: 'gizmo-rotate', id };
    }
    
    const corners = [
      {x: -hw, y: -hd}, {x: hw, y: -hd}, {x: -hw, y: hd}, {x: hw, y: hd}
    ];
    for (const corner of corners) {
      if (Math.abs(lx - corner.x) <= 10 + margin && Math.abs(ly - corner.y) <= 10 + margin) {
        return { kind: 'gizmo-scale', id };
      }
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

/** Distance-based hit test for road centerlines (within half the road width). */
function hitTestRoad(cursor: Point2D, state: AppStore): string | null {
  for (const road of Object.values(state.roads)) {
    const { start, end } = road;
    const l2 = (end.x - start.x) ** 2 + (end.y - start.y) ** 2;
    let t = 0;
    if (l2 > 0) {
      t = ((cursor.x - start.x) * (end.x - start.x) + (cursor.y - start.y) * (end.y - start.y)) / l2;
      t = Math.max(0, Math.min(1, t));
    }
    const projX = start.x + t * (end.x - start.x);
    const projY = start.y + t * (end.y - start.y);
    const dist = Math.sqrt((cursor.x - projX) ** 2 + (cursor.y - projY) ** 2);
    if (dist <= road.width / 2) return road.id;
  }
  return null;
}

function hitTestPillar(cursor: Point2D, state: AppStore, margin = 0): string | null {
  for (const pillar of Object.values(state.pillars)) {
    const dx = cursor.x - pillar.position.x;
    const dy = cursor.y - pillar.position.y;
    if (pillar.shape === 'round') {
      if (Math.hypot(dx, dy) <= Math.max(pillar.width, pillar.depth) / 2 + margin) return pillar.id;
    } else if (Math.abs(dx) <= pillar.width / 2 + margin && Math.abs(dy) <= pillar.depth / 2 + margin) {
      return pillar.id;
    }
  }
  return null;
}

function hitTestBeam(cursor: Point2D, state: AppStore, margin = 0): string | null {
  for (const beam of Object.values(state.beams)) {
    const { start, end } = beam;
    const l2 = (end.x - start.x) ** 2 + (end.y - start.y) ** 2;
    if (l2 <= 0.01) continue;
    let t = ((cursor.x - start.x) * (end.x - start.x) + (cursor.y - start.y) * (end.y - start.y)) / l2;
    t = Math.max(0, Math.min(1, t));
    const projX = start.x + t * (end.x - start.x);
    const projY = start.y + t * (end.y - start.y);
    if (Math.hypot(cursor.x - projX, cursor.y - projY) <= beam.width / 2 + margin) return beam.id;
  }
  return null;
}

function hitTestDeckSlab(cursor: Point2D, state: AppStore): string | null {
  for (const slab of Object.values(state.deckSlabs)) {
    if (pointInPolygon(cursor, slab.polygon)) return slab.id;
  }
  return null;
}

/**
 * Smart deck-corner attachment. A deck vertex snaps to a pillar's CENTER while drawing, so
 * the finished slab only covers half of each corner pillar — the pillar's outer half pokes
 * out past the deck edge (the "unfinished corner"). For every polygon vertex that sits on a
 * pillar, push it OUTWARD (away from the polygon centroid) to the pillar's outer corner so
 * the whole post top ends up beneath the slab and the deck edges meet the post faces cleanly.
 */
function adjustDeckCornersToPillars(polygon: Point2D[], state: AppStore): Point2D[] {
  if (polygon.length < 3) return polygon;
  const cx = polygon.reduce((s, p) => s + p.x, 0) / polygon.length;
  const cy = polygon.reduce((s, p) => s + p.y, 0) / polygon.length;
  const centroid = { x: cx, y: cy };

  return polygon.map((pt) => {
    // Snap radius 1cm: only vertices actually dropped on a pillar center are adjusted.
    const near = findNearestPillar(pt, state, 1);
    return near ? snapDeckCornerOutward(pt, centroid, near.pillar) : pt;
  });
}

function hitTestRailing(cursor: Point2D, state: AppStore, margin = 0): string | null {
  for (const railing of Object.values(state.railings)) {
    const { start, end } = railing;
    const l2 = (end.x - start.x) ** 2 + (end.y - start.y) ** 2;
    if (l2 <= 0.01) continue;
    let t = ((cursor.x - start.x) * (end.x - start.x) + (cursor.y - start.y) * (end.y - start.y)) / l2;
    t = Math.max(0, Math.min(1, t));
    const projX = start.x + t * (end.x - start.x);
    const projY = start.y + t * (end.y - start.y);
    if (Math.hypot(cursor.x - projX, cursor.y - projY) <= 10 + margin) return railing.id;
  }
  return null;
}

/** Distance-based hit test for an opening symbol (door/window/vent), within a grab radius. */
function hitTestOpening(cursor: Point2D, state: AppStore): string | null {
  let bestId: string | null = null;
  let bestDist = Infinity;
  for (const opening of Object.values(state.openings)) {
    const wall = state.walls[opening.wallId];
    if (!wall) continue;
    const start = state.vertices[wall.startVertexId]?.position;
    const end = state.vertices[wall.endVertexId]?.position;
    if (!start || !end) continue;
    const geo = computeOpeningGeometry(opening, start, end, wall.thickness);
    if (!geo) continue;
    const dist = Math.hypot(cursor.x - geo.center.x, cursor.y - geo.center.y);
    // Hit if within the opening's half-width (plus a small grace) of its centre.
    if (dist <= geo.halfW + 10 && dist < bestDist) {
      bestDist = dist;
      bestId = opening.id;
    }
  }
  return bestId;
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

/**
 * Which face of a wall the cursor lies on, used for room-aware paint. Side A is the wall's
 * +normal face — plan direction (dy,−dx), i.e. the +z face in 3D; side B is the other face.
 * The user clicks the wall on the side of the room they're standing in, so that face is
 * painted and the opposite (e.g. exterior) face is left untouched.
 */
function wallPaintSide(cursor: Point2D, wallId: string, state: AppStore): 'A' | 'B' {
  const wall = state.walls[wallId];
  if (!wall) return 'A';
  const start = state.vertices[wall.startVertexId]?.position;
  const end = state.vertices[wall.endVertexId]?.position;
  if (!start || !end) return 'A';
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const cx = (start.x + end.x) / 2;
  const cy = (start.y + end.y) / 2;
  // Signed projection of (cursor − centre) onto the +A normal (dy, −dx).
  const dot = (cursor.x - cx) * dy + (cursor.y - cy) * -dx;
  return dot >= 0 ? 'A' : 'B';
}

function isPerimeterWall(wallId: string, state: AppStore): boolean {
  let count = 0;
  const wall = state.walls[wallId];
  if (!wall) return true;
  const s = wall.startVertexId;
  const e = wall.endVertexId;

  for (const room of Object.values(state.rooms)) {
    const b = room.boundaryVertexIds;
    for (let i = 0; i < b.length; i++) {
      const next = b[(i + 1) % b.length];
      if ((b[i] === s && next === e) || (b[i] === e && next === s)) {
        count++;
        break;
      }
    }
  }
  return count <= 1;
}

export const EditorCanvas: React.FC = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const { viewTransform, panBy, handlers } = usePanZoom(svgRef);
  const endpoints = useEndpoints();
  // Corners of the floor below are also snap targets, so a new storey can be drawn aligned
  // to the one beneath it.
  const ghostGeo = useFloorBelowGeometry();
  const snapEndpoints = useMemo(() => {
    if (!ghostGeo) return endpoints;
    return [...endpoints, ...Object.values(ghostGeo.vertices).map((v) => v.position)];
  }, [endpoints, ghostGeo]);
  const snapConfig = useAppStore((s) => s.snapConfig);
  const activeTool = useAppStore((s) => s.activeTool);
  const showDimensions = useAppStore((s) => s.showDimensions);

  const { drawStart, chainOrigin, handleClick, cancel } = useWallDrawing();
  const { drawStart: roadStart, handleClick: handleRoadClick, cancel: cancelRoad } = useRoadDrawing();
  const [stairToolState, stairHandles] = useStairTool();
  const stairWidthCm = useAppStore((s) => s.stairWidthCm);
  const [deckPoints, setDeckPoints] = useState<Point2D[]>([]);

  // Array tool
  const currentMouseWorld = useAppStore((s) => s.currentMouseWorld);
  const { previewItems, commitAt, cancel: cancelArray } = useArrayTool(currentMouseWorld);

  const viewTransformRef = useRef(viewTransform);
  viewTransformRef.current = viewTransform;

  // Drag state (refs avoid re-renders on every mouse move).
  const dragRef = useRef<{ kind: 'furniture' | 'wall' | 'pillar' | 'beam' | 'deck' | 'railing' | 'road' | 'gizmo-rotate' | 'gizmo-scale'; id: string; baseScale?: number; baseDist?: number } | null>(null);
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
  const smartAlign = useCallback((drag: { kind: 'furniture' | 'wall' | 'pillar' | 'beam' | 'deck' | 'railing' | 'road' | 'gizmo-rotate' | 'gizmo-scale'; id: string }) => {
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

    if (drag.kind === 'pillar') {
      const pillar = st.pillars[drag.id];
      if (!pillar) return;
      st.movePillar(drag.id, { x: snap(pillar.position.x), y: snap(pillar.position.y) });
      return;
    }

    if (drag.kind === 'beam' || drag.kind === 'deck' || drag.kind === 'railing' || drag.kind === 'road') return;
    
    if (drag.kind === 'gizmo-rotate' || drag.kind === 'gizmo-scale') return;

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
      const origin = activeTool === 'wall' || activeTool === 'beam' ? drawStart : activeTool === 'deck' ? (deckPoints.at(-1) ?? null) : activeTool === 'road' ? roadStart : activeTool === 'stair' ? (stairToolState.pathPoints[stairToolState.pathPoints.length - 1] ?? null) : null;
      // When drawing, allow snapping onto existing wall centerlines so a wall drawn
      // across a room connects cleanly and splits it. (Not needed for select/furniture.)
      const st = useAppStore.getState();
      const wallSegments = activeTool === 'wall' || activeTool === 'beam' ? toWallSegments(st.walls, st.vertices) : [];
      return applySnapping(raw, snapEndpoints, snapConfig, origin, e.shiftKey, wallSegments);
    },
    [activeTool, drawStart, deckPoints, roadStart, snapEndpoints, snapConfig]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      handlers.onMouseDown(e); // pan (alt / middle) — no-ops otherwise
      if (e.button !== 0 || e.altKey) return;

      if (activeTool === 'select') {
        const cursor = computeWorld(e);
        if (!cursor) return;
        const state = useAppStore.getState();

        // 0) Check gizmo first so it takes priority over moving furniture
        const gizmo = hitTestGizmo(cursor, state, GRAB_MARGIN);
        if (gizmo) {
          const item = state.furniture[gizmo.id];
          if (item) {
            state.beginTransaction();
            dragRef.current = { 
              kind: gizmo.kind, 
              id: gizmo.id, 
              baseScale: item.scale,
              baseDist: Math.hypot(cursor.x - item.position.x, cursor.y - item.position.y)
            };
            dragLastWorldRef.current = cursor;
            didDragRef.current = false;
            setDragHud(null);
            return;
          }
        }

        // 1) Grab a specific component (furniture first, then walls) to move it.
        const furnitureId = hitTestFurniture(cursor, state.furniture, GRAB_MARGIN);
        if (furnitureId) {
          state.select([furnitureId]);
          state.beginTransaction();
          dragRef.current = { kind: 'furniture', id: furnitureId };
          dragLastWorldRef.current = cursor;
          didDragRef.current = false;
          setDragHud({ sx: cursor.x, sy: cursor.y, cx: cursor.x, cy: cursor.y });
          return;
        }
        const wallId = hitTestWall(cursor, state);
        if (wallId) {
          state.select([wallId]);
          state.beginTransaction();
          dragRef.current = { kind: 'wall', id: wallId };
          dragLastWorldRef.current = cursor;
          didDragRef.current = false;
          setDragHud({ sx: cursor.x, sy: cursor.y, cx: cursor.x, cy: cursor.y });
          return;
        }
        const pillarId = hitTestPillar(cursor, state, GRAB_MARGIN);
        if (pillarId) {
          state.select([pillarId]);
          state.beginTransaction();
          dragRef.current = { kind: 'pillar', id: pillarId };
          dragLastWorldRef.current = cursor;
          didDragRef.current = false;
          setDragHud({ sx: cursor.x, sy: cursor.y, cx: cursor.x, cy: cursor.y });
          return;
        }
        const beamId = hitTestBeam(cursor, state, GRAB_MARGIN);
        if (beamId) {
          state.select([beamId]);
          state.beginTransaction();
          dragRef.current = { kind: 'beam', id: beamId };
          dragLastWorldRef.current = cursor;
          didDragRef.current = false;
          setDragHud({ sx: cursor.x, sy: cursor.y, cx: cursor.x, cy: cursor.y });
          return;
        }
        const deckId = hitTestDeckSlab(cursor, state);
        if (deckId) {
          state.select([deckId]);
          state.beginTransaction();
          dragRef.current = { kind: 'deck', id: deckId };
          dragLastWorldRef.current = cursor;
          didDragRef.current = false;
          setDragHud({ sx: cursor.x, sy: cursor.y, cx: cursor.x, cy: cursor.y });
          return;
        }
        const railingId = hitTestRailing(cursor, state, GRAB_MARGIN);
        if (railingId) {
          state.select([railingId]);
          state.beginTransaction();
          dragRef.current = { kind: 'railing', id: railingId };
          dragLastWorldRef.current = cursor;
          didDragRef.current = false;
          setDragHud({ sx: cursor.x, sy: cursor.y, cx: cursor.x, cy: cursor.y });
          return;
        }
        const roadId = hitTestRoad(cursor, state);
        if (roadId) {
          state.select([roadId]);
          state.beginTransaction();
          dragRef.current = { kind: 'road', id: roadId };
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
      if (activeTool === 'stair') stairHandles.handleMove(snapped);

      // Drag the selected component by the world-space delta (smooth — no jump-to-cursor).
      const drag = dragRef.current;
      const last = dragLastWorldRef.current;
      if (drag && last) {
        const dx = snapped.x - last.x;
        const dy = snapped.y - last.y;
        if (dx !== 0 || dy !== 0) {
          const state = useAppStore.getState();
          if (drag.kind === 'gizmo-rotate') {
            const item = state.furniture[drag.id];
            if (item) {
              let angle = Math.atan2(snapped.y - item.position.y, snapped.x - item.position.x);
              state.rotateFurniture(drag.id, angle - Math.PI / 2);
            }
          } else if (drag.kind === 'gizmo-scale') {
            const item = state.furniture[drag.id];
            if (item && drag.baseDist && drag.baseScale) {
              const currentDist = Math.hypot(snapped.x - item.position.x, snapped.y - item.position.y);
              if (drag.baseDist > 0.01) {
                const ratio = currentDist / drag.baseDist;
                state.scaleFurniture(drag.id, drag.baseScale * ratio);
              }
            }
          } else if (drag.kind === 'furniture') {
            const item = state.furniture[drag.id];
            if (item) state.moveFurniture(drag.id, { x: item.position.x + dx, y: item.position.y + dy });
          } else if (drag.kind === 'pillar') {
            const pillar = state.pillars[drag.id];
            if (pillar) state.movePillar(drag.id, { x: pillar.position.x + dx, y: pillar.position.y + dy });
          } else if (drag.kind === 'beam') {
            state.moveBeam(drag.id, { x: dx, y: dy });
          } else if (drag.kind === 'deck') {
            state.moveDeckSlab(drag.id, { x: dx, y: dy });
          } else if (drag.kind === 'railing') {
            state.moveRailing(drag.id, { x: dx, y: dy });
          } else if (drag.kind === 'road') {
            state.moveRoad(drag.id, { x: dx, y: dy });
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
    [handlers, computeWorld, panBy, activeTool, stairHandles]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      handlers.onMouseUp();
      void e;
      // Smart-align the component we just dragged so the layout stays orthogonal.
      const drag = dragRef.current;
      const state = useAppStore.getState();
      if (drag && didDragRef.current) {
        smartAlign(drag);
        // Record the whole drag (move + smart-align) as one undo step.
        const label =
          drag.kind === 'gizmo-rotate' ? 'Rotate' :
          drag.kind === 'gizmo-scale' ? 'Scale' :
          drag.kind === 'wall' ? 'Move Wall' :
          drag.kind === 'beam' ? 'Move Beam' :
          drag.kind === 'deck' ? 'Move Deck' :
          drag.kind === 'railing' ? 'Move Railing' :
          drag.kind === 'pillar' ? 'Move Pillar' : 'Move Furniture';
        state.commitTransaction(label);
      } else {
        // A click that only selected/panned — nothing to record.
        state.cancelTransaction();
      }
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

      if (activeTool === 'stair') {
        stairHandles.handleClick(cursor);
        return;
      }

      if (activeTool === 'wall') {
        handleClick(cursor);
        return;
      }

      if (activeTool === 'beam') {
        if (!drawStart) {
          // Starting beam - snap to pillar if nearby
          const nearPillar = findNearestPillar(cursor, state);
          const startPoint = nearPillar ? nearPillar.pillar.position : cursor;
          handleClick(startPoint);
        } else {
          // Ending beam - snap to pillar if nearby
          const nearPillar = findNearestPillar(cursor, state);
          const endPoint = nearPillar ? nearPillar.pillar.position : cursor;
          const start = drawStart;
          const nearPillarStart = findNearestPillar(start, state);
          const nearPillarEnd = nearPillar;

          // Smart corner joint: a beam end snaps to a pillar's CENTER, so half the pillar top
          // is left uncovered and the beam stops mid-post. Extend each connected end outward
          // along the beam axis to the pillar's outer face so the beam fully bears on the
          // post (how a beam actually seats on a column), meeting the post face cleanly.
          const [adjStart, adjEnd] = extendBeamEndsToPillars(
            start, endPoint,
            nearPillarStart?.pillar ?? null,
            nearPillarEnd?.pillar ?? null,
          );

          // Elevation: honor the user's chosen beam height when set (>0), else rest the beam
          // on the tallest connecting pillar top (falling back to a sensible 280cm).
          const pillarTopStart = nearPillarStart ? nearPillarStart.pillar.height + nearPillarStart.pillar.elevationCm : 0;
          const pillarTopEnd = nearPillarEnd ? nearPillarEnd.pillar.height + nearPillarEnd.pillar.elevationCm : 0;
          const beamElevation = state.beamElevationCm > 0
            ? state.beamElevationCm
            : Math.max(pillarTopStart, pillarTopEnd, 280);
          let id = '';
          state.recordHistory('Add Beam', () => {
            id = state.addBeam({ start: adjStart, end: adjEnd, width: 25, depth: 35, elevationCm: beamElevation, materialId: 'paint-white' });
          });
          cancel();
          if (id) state.select([id]);
        }
        return;
      }

      if (activeTool === 'railing') {
        if (!drawStart) {
          // Starting railing
          handleClick(cursor);
        } else {
          // Ending railing
          const start = drawStart;
          let id = '';
          state.recordHistory('Add Railing', () => {
            id = state.addRailing({ 
              start, 
              end: cursor, 
              height: state.railingHeightCm, 
              elevationCm: state.railingElevationCm, 
              style: state.railingStyle, 
              materialId: 'paint-white' 
            });
          });
          cancel();
          if (id) state.select([id]);
        }
        return;
      }

      if (activeTool === 'array') {
        // Building mode (chosen via the panel) arrays the whole construction — skip entity picking.
        if (state.arrayConfig.entityType !== 'building') {
          // Click an entity on canvas → it becomes (or replaces) the replication source.
          // Only kinds supported by cloneComponent are hit-tested (no openings/rooms).
          const hitId =
            hitTestFurniture(cursor, state.furniture, GRAB_MARGIN) ??
            hitTestPillar(cursor, state, GRAB_MARGIN) ??
            hitTestBeam(cursor, state, GRAB_MARGIN) ??
            hitTestRailing(cursor, state, GRAB_MARGIN) ??
            hitTestWall(cursor, state) ??
            hitTestRoad(cursor, state) ??
            hitTestDeckSlab(cursor, state);
          if (hitId) {
            state.setArrayConfig({ entityType: 'component', referenceId: hitId, isPreviewing: true });
            return;
          }
        }
        // Clicked empty space: commit if a source is armed, otherwise stay in no-source state.
        commitAt(cursor);
        return;
      }

      if (activeTool === 'road') {
        handleRoadClick(cursor);
        return;
      }

      if (activeTool === 'deck') {
        // Snap deck points to pillars if nearby
        const nearPillar = findNearestPillar(cursor, state);
        const snappedPoint = nearPillar ? nearPillar.pillar.position : cursor;
        
        setDeckPoints((prev) => {
          if (prev.length >= 3 && Math.hypot(snappedPoint.x - prev[0].x, snappedPoint.y - prev[0].y) <= GRAB_MARGIN * 2) {
            // Compute elevation from the tallest pillar among the polygon points
            let maxPillarTop = 0;
            for (const pt of prev) {
              const p = findNearestPillar(pt, state, 35);
              if (p) maxPillarTop = Math.max(maxPillarTop, p.pillar.height + p.pillar.elevationCm);
            }
            const deckElevation = maxPillarTop > 0 ? maxPillarTop : 0;

            // Smart corner attachment: offset each polygon point from the pillar center to
            // the pillar's outer edge, so the deck face meets the pillar face cleanly instead
            // of cutting through the pillar's middle. The offset direction is from the
            // polygon's centroid outward through each corner.
            const adjustedPolygon = adjustDeckCornersToPillars(prev, state);

            state.recordHistory('Add Deck Slab', () => {
              const id = state.addDeckSlab({ polygon: adjustedPolygon, thicknessCm: 15, elevationCm: deckElevation, materialId: 'default-floor', type: 'custom' });
              if (id) state.select([id]);
            });
            return [];
          }
          return [...prev, snappedPoint];
        });
        return;
      }

      if (activeTool === 'furniture') {
        const catalogId = state.furnitureCatalogId;
        const entry = getCatalogEntry(catalogId);
        let id = '';
        state.recordHistory('Place Furniture', () => {
          id = state.addFurniture({
            position: cursor,
            rotation: 0,
            scale: 1,
            catalogId,
            roomId: null,
            bounds: { width: entry.bounds.width, depth: entry.bounds.depth },
          });
        });
        if (id) state.select([id]);
        return;
      }

      if (activeTool === 'pillar') {
        let id = '';
        state.recordHistory('Place Pillar', () => {
          id = state.addPillar({
            position: cursor,
            width: 35,
            depth: 35,
            height: 300,
            elevationCm: 0,
            shape: 'rect',
            materialId: 'paint-white',
          });
        });
        if (id) state.select([id]);
        return;
      }

      if (activeTool === 'door' || activeTool === 'window' || activeTool === 'vent' || activeTool === 'ac') {
        const wallId = hitTestWall(cursor, state);
        if (wallId) {
          const wall = state.walls[wallId];
          const start = state.vertices[wall.startVertexId]?.position;
          if (!start) return;

          // Resolve the specific kind the user picked for this tool's family.
          const kindId = state.selectedOpeningKinds[activeTool];
          const kind = getOpeningKind(kindId) ?? resolveKind(kindId, activeTool === 'ac' ? 'ac' : activeTool);

          // Windows and ventilation belong on perimeter walls only. Doors and ACs can go
          // on any wall (interior partitions, etc.).
          if (kind.type === 'window' || kind.type === 'vent') {
            if (!isPerimeterWall(wallId, state)) {
              alert('Windows and ventilation can only be placed on perimeter walls.');
              return;
            }
          }

          const offsetCm = Math.hypot(cursor.x - start.x, cursor.y - start.y);

          // Apply any user-set size overrides for this family (sill height, opening height,
          // width). Windows/vents expose these in the toolbar; unset values fall back to the
          // kind's catalog defaults.
          const ov = state.openingSizeOverrides[activeTool as OpeningFamily];
          const width = ov?.width ?? kind.width;
          const height = ov?.height ?? kind.height;
          const elevation = ov?.elevation ?? kind.elevation;

          state.recordHistory(`Add ${kind.label}`, () => {
            state.addOpening({
              wallId,
              type: kind.type,
              kind: kind.id,
              offsetCm,
              width,
              height,
              elevation,
            });
          });
        }
        return;
      }

      if (activeTool === 'paint') {
        // Apply the selected finish to whatever surface is under the cursor. The category
        // of the finish decides what we hit: wall paints target a wall, floor tiles target
        // a room's floor. Reuses the existing hit-testers so no new geometry math is needed.
        //
        // If the surface under the cursor doesn't match the active finish (e.g. a floor
        // tile is selected but the user clicked a wall, or nothing is selected yet), we
        // still SELECT that surface so the user can then pick a compatible finish — i.e.
        // "click the floor, then pick a tile, then it's applied" works as well as the
        // one-click "pick finish, then click surface" flow.
        const finishId = state.paintFinishId;
        const category = categoryOf(finishId);
        const wallId = hitTestWall(cursor, state);

        if (category === 'wall' && wallId) {
          const side = wallPaintSide(cursor, wallId, state);
          state.recordHistory('Paint Wall', () =>
            state.updateWall(wallId, side === 'A' ? { materialSideA: finishId } : { materialSideB: finishId })
          );
          state.select([wallId]);
          return;
        }

        const roomId = hitTestRoom(cursor, state);
        if (category === 'floor' && roomId) {
          state.recordHistory('Paint Floor', () => state.updateRoom(roomId, { floorMaterialId: finishId }));
          state.select([roomId]);
          return;
        }

        // Decks reuse the same floor-tile palette (default-floor materialId), so a floor
        // finish clicked onto a deck slab paints the deck the same way a room floor works.
        const deckId = hitTestDeckSlab(cursor, state);
        if (category === 'floor' && deckId) {
          state.recordHistory('Paint Deck', () => state.updateDeckSlab(deckId, { materialId: finishId }));
          state.select([deckId]);
          return;
        }

        // No finish/surface match: select the surface under the cursor (wall takes
        // priority since it sits on top), so a compatible swatch can be applied next.
        if (wallId) state.select([wallId]);
        else if (roomId) state.select([roomId]);
        else if (deckId) state.select([deckId]);
        else state.clearSelection();
        return;
      }

      if (activeTool === 'room') {
        // Dedicated room-naming tool: clicking inside a room selects it so the
        // RoomAssignmentPanel appears for naming / type assignment.
        const roomId = hitTestRoom(cursor, state);
        if (roomId) state.select([roomId]);
        else state.clearSelection();
        return;
      }

      if (activeTool === 'select') {
        const furnitureId = hitTestFurniture(cursor, state.furniture, GRAB_MARGIN);
        if (furnitureId) {
          state.select([furnitureId]);
          return;
        }
        // Openings (doors/gates/windows/vents) sit on walls, so test them before walls.
        const openingId = hitTestOpening(cursor, state);
        if (openingId) {
          state.select([openingId]);
          return;
        }
        const wallId = hitTestWall(cursor, state);
        if (wallId) {
          state.select([wallId]);
          return;
        }
        const roadId = hitTestRoad(cursor, state);
        if (roadId) {
          state.select([roadId]);
          return;
        }
        const pillarId = hitTestPillar(cursor, state, GRAB_MARGIN);
        if (pillarId) {
          state.select([pillarId]);
          return;
        }
        const beamId = hitTestBeam(cursor, state, GRAB_MARGIN);
        if (beamId) {
          state.select([beamId]);
          return;
        }
        const deckId = hitTestDeckSlab(cursor, state);
        if (deckId) {
          state.select([deckId]);
          return;
        }
        const railingId = hitTestRailing(cursor, state, GRAB_MARGIN);
        if (railingId) {
          state.select([railingId]);
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
    [activeTool, handleClick, handleRoadClick, stairHandles]
  );

  // Keyboard: Escape cancels drawing; Delete/Backspace erases selection; R rotates furniture.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;

      if (e.key === 'Escape') { cancel(); cancelRoad(); stairHandles.cancel(); setDeckPoints([]); cancelArray(); }

      if (e.key === 'Enter' && activeTool === 'stair' && stairToolState.inProgress) {
        const pts = stairToolState.pathPoints;
        if (pts.length >= 2) stairHandles.handleFinish(pts[pts.length - 1]);
        return;
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        const state = useAppStore.getState();
        if (state.selectedIds.length > 0) {
          state.recordHistory('Delete', () => {
            state.selectedIds.forEach((id) => {
              if (state.walls[id]) state.removeWall(id);
              if (state.furniture[id]) state.removeFurniture(id);
              if (state.roads[id]) state.removeRoad(id);
              if (state.openings[id]) state.removeOpening(id);
              if (state.stairs[id]) state.removeStair(id);
              if (state.pillars[id]) state.removePillar(id);
              if (state.beams[id]) state.removeBeam(id);
              if (state.deckSlabs[id]) state.removeDeckSlab(id);
              if (state.railings[id]) state.removeRailing(id);
            });
            state.clearSelection();
          });
        }
      }

      if (e.key === 'r' || e.key === 'R') {
        const state = useAppStore.getState();
        const delta = (e.shiftKey ? -1 : 1) * (Math.PI / 12); // ±15°
        if (state.selectedIds.some((id) => state.furniture[id])) {
          state.recordHistory('Rotate', () => {
            state.selectedIds.forEach((id) => {
              const item = state.furniture[id];
              if (item) state.rotateFurniture(id, item.rotation + delta);
            });
          });
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [cancel, cancelRoad, stairHandles, stairToolState, activeTool]);

  const cursorClass =
    activeTool === 'wall' || activeTool === 'road' || activeTool === 'pillar' || activeTool === 'beam' || activeTool === 'deck' || activeTool === 'furniture' || activeTool === 'paint' || activeTool === 'stair'
      ? 'cursor-crosshair'
      : 'cursor-grab';

  return (
    <svg
      ref={svgRef}
      className={`w-full h-full bg-neutral-900 ${cursorClass}`}
      onMouseMove={handleMouseMove}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        handlers.onMouseUp();
        const drag = dragRef.current;
        const state = useAppStore.getState();
        if (drag && didDragRef.current) {
          smartAlign(drag);
          const label =
            drag.kind === 'gizmo-rotate' ? 'Rotate' :
            drag.kind === 'gizmo-scale' ? 'Scale' :
            drag.kind === 'wall' ? 'Move Wall' :
            drag.kind === 'beam' ? 'Move Beam' :
            drag.kind === 'deck' ? 'Move Deck' :
            drag.kind === 'railing' ? 'Move Railing' :
            drag.kind === 'road' ? 'Move Road' :
            drag.kind === 'pillar' ? 'Move Pillar' : 'Move Furniture';
          state.commitTransaction(label);
        } else {
          state.cancelTransaction();
        }
        dragRef.current = null;
        dragLastWorldRef.current = null;
        panningRef.current = false;
        setDragHud(null);
        if (svgRef.current) svgRef.current.style.cursor = '';
      }}
      onClick={handleSvgClick}
      onDoubleClick={(e) => {
        const state = useAppStore.getState();
        const cursor = state.currentMouseWorld;
        
        if (activeTool === 'stair') {
          if (cursor) stairHandles.handleFinish(cursor);
          e.preventDefault();
          return;
        }
        
        if (activeTool === 'deck' && deckPoints.length >= 3) {
          // Double-click to close deck polygon — compute pillar elevation
          let maxPillarTopDbl = 0;
          for (const pt of deckPoints) {
            const p = findNearestPillar(pt, state, 35);
            if (p) maxPillarTopDbl = Math.max(maxPillarTopDbl, p.pillar.height + p.pillar.elevationCm);
          }
          const deckElevationDbl = maxPillarTopDbl > 0 ? maxPillarTopDbl : 0;
          const adjustedPolygonDbl = adjustDeckCornersToPillars(deckPoints, state);
          state.recordHistory('Add Deck Slab', () => {
            const id = state.addDeckSlab({ 
              polygon: adjustedPolygonDbl, 
              thicknessCm: 15, 
              elevationCm: deckElevationDbl, 
              materialId: 'default-floor', 
              type: 'custom' 
            });
            if (id) state.select([id]);
          });
          setDeckPoints([]);
          e.preventDefault();
          return;
        }
      }}
      onContextMenu={(e) => {
        e.preventDefault();
        cancel();
        setDeckPoints([]);
        stairHandles.cancel();
      }}
    >
      <g transform={`translate(${viewTransform.offsetX}, ${viewTransform.offsetY}) scale(${viewTransform.scale})`}>
        <GridLayer gridSize={snapConfig.gridSize} />
        <GhostFloorLayer />
        <RoadLayer />
        <DeckLayer />
        <RailingLayer />
        <PillarLayer />
        <BeamLayer />
        <RoomLayer />
        <WallLayer />
        <OpeningsLayer />
        <StairLayer />
        <FurnitureLayer />
        <SelectionLayer />
        {showDimensions && <DimensionLayer />}
        <VastuOverlay2D />
        {activeTool === 'wall' && <DrawingPreview start={drawStart} chainOrigin={chainOrigin} />}
        {activeTool === 'beam' && <DrawingPreview start={drawStart} chainOrigin={null} />}
        {activeTool === 'beam' && <PillarSnapIndicator activeTool="beam" currentPoint={useAppStore.getState().currentMouseWorld} />}
        {activeTool === 'deck' && <DeckPreview points={deckPoints} cursor={useAppStore.getState().currentMouseWorld} />}
        {activeTool === 'deck' && <PillarSnapIndicator activeTool="deck" currentPoint={useAppStore.getState().currentMouseWorld} />}
        {activeTool === 'pillar' && <PillarAlignmentGuide cursor={useAppStore.getState().currentMouseWorld} />}
        {activeTool === 'road' && <DrawingPreview start={roadStart} />}
        {activeTool === 'stair' && (
          <StairToolOverlay toolState={stairToolState} stairWidthCm={stairWidthCm} />
        )}
        {activeTool === 'array' && <ArrayPreview items={previewItems} />}
        {dragHud && <DragReadout {...dragHud} />}
      </g>
      {/* Screen-anchored compass (outside the pan/zoom group) so it never moves or scales. */}
      <CompassRose />
    </svg>
  );
};

const DeckPreview: React.FC<{ points: Point2D[]; cursor: Point2D | null }> = ({ points, cursor }) => {
  if (points.length === 0) return null;
  const preview = cursor ? [...points, cursor] : points;
  const d = preview.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${-p.y}`).join(' ');
  return (
    <g pointerEvents="none">
      <path d={points.length >= 3 ? `${d} Z` : d} fill="rgba(14,165,233,0.14)" stroke="#38bdf8" strokeWidth={2} strokeDasharray="8 6" />
      {points.map((p, i) => <circle key={i} cx={p.x} cy={-p.y} r={5} fill="#38bdf8" />)}
    </g>
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
