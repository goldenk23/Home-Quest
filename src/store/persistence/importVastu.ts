// src/store/persistence/importVastu.ts

import type {
  DeckSlab, EntityId, Floor, FloorGeometry, FurnitureItem, Opening, Pillar,
  Railing, Room, RoomType, TextAnnotation, Vertex, Wall,
} from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import type { StairEntity } from '@/types/stair';
import { generateId } from '@/utils/id';
import { buildStair } from '@/domains/editor/services/stairBuilder';
import { FURNITURE_CATALOG, getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import { getOpeningKind } from '@/domains/shared/openings/openingCatalog';
import { FURNITURE_NAME_TO_CATALOG, FLOORING_TYPE_TO_MATERIAL } from '@/domains/shared/assets/pythonAssetMap';
import { categoryOf, type FinishCategory } from '@/domains/shared/materials/finishPalette';
import { useAppStore } from '@/store';

/**
 * Importer for the Python "VastuCraft" 2D editor's NATIVE layout JSON (the output of
 * `layout_serializer.serialize_layout()` — keys: metadata, rooms, furniture, shapes, text,
 * compass). It converts px → cm (flipping Y: Python screen-Y is down, our world-Y is up)
 * and maps every field into this app's widened `version: 9` schema so the existing 2D→3D
 * pipeline renders it without a separate 3D conversion step.
 *
 * What is imported:
 *  - rect rooms        → 4 walls + Room (type/fill/flooring preserved)
 *  - polygon shapes    → wall loop + Room (label from the group's `polygon_label` text)
 *  - 2-point lines     → standalone walls
 *  - door furniture    → wall Openings (claims the matching wall gap when one exists,
 *                        otherwise projects onto the closest wall)
 *  - wall_erased_regions (gaps cut in walls_only room walls) → window Openings;
 *                        a fully erased side means "no wall there" and is skipped entirely
 *  - furniture         → catalog items (unknown names are skipped and reported)
 *  - text              → annotations (polygon labels become room labels instead)
 *  - compass           → Vastu north offset
 *
 * Geometry cleanup so the 3D result is clean: near-coincident corners are snapped to one
 * vertex (adjacent rooms share a wall instead of doubling it), duplicate walls between the
 * same vertices are dropped, and walls are split wherever another vertex lands mid-segment
 * (T-junctions) so miters and room-face detection behave exactly like natively drawn plans.
 *
 * IMPORTANT: consume the NATIVE file, NOT a converted `.hq.json` (that already dropped
 * fill_mode/flooring/text and applies its own lossy mapping).
 */

const UNIT_TO_CM: Record<string, number> = {
  ft: 30.48,
  foot: 30.48,
  feet: 30.48,
  m: 100,
  cm: 1,
  in: 2.54,
  yd: 91.44,
  yard: 91.44,
  yards: 91.44,
};

const DEFAULT_WALL_THICKNESS_CM = 20;
const DEFAULT_WALL_HEIGHT_CM = 280;
const VERTEX_SNAP_CM = 5;
const TJUNCTION_TOL_CM = 2;
const DOOR_SNAP_CM = 60;
// Explicit windows/vents are placed on the wall centreline in the editor, but after the
// coordinate flip + T-junction splitting the projected foot can drift a little, so allow a
// generous snap radius before giving up.
const OPENING_SNAP_CM = 150;
const MIN_OPENING_WIDTH_CM = 40;
const MAX_LAYOUT_ENTITIES = 2_000;
const MAX_GEOMETRY_POINTS = 4_000;
const MAX_ABS_COORDINATE = 10_000_000;
export const MAX_VASTU_FILE_BYTES = 5 * 1024 * 1024;

export type ConvertedGeometry = FloorGeometry;

export interface ConvertedVastuProject {
  floors: Floor[];
  activeFloorId: EntityId;
  geometryByFloor: Record<EntityId, FloorGeometry>;
  crossFloorReferences: Array<{
    id: EntityId;
    type: string;
    sourceFloorId: EntityId;
    sourceEntityId: EntityId;
    targetFloorId: EntityId;
    targetEntityId: EntityId;
  }>;
  northDeg: number;
  sunSettings: {
    timeHours: number;
    azimuthDeg: number;
    directionOverride: boolean;
  };
}

export interface ImportReport {
  rooms: number;
  walls: number;
  furniture: number;
  openings: number;
  annotations: number;
  northDeg: number;
  /** Python furniture names skipped because they do not resolve to a catalog item. */
  unmapped: string[];
  /** Data that could not be represented exactly or was deliberately skipped. */
  residuals: string[];
}

export interface ConvertResult {
  /** Active-floor geometry; retained for v1 callers. */
  geometry: ConvertedGeometry;
  northDeg: number;
  report: ImportReport;
  /** Complete validated candidate for native v2 projects. */
  project?: ConvertedVastuProject;
}

/** Map a Python compass direction to Home Quest degrees (clockwise from screen-up). */
const DIRECTION_TO_DEG: Record<string, number> = {
  N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315,
};

type RawObject = Record<string, unknown>;

interface ValidatedVastuLayout extends RawObject {
  version: '1.0';
  metadata: RawObject;
  rooms: RawObject[];
  furniture: RawObject[];
  shapes: RawObject[];
  text: RawObject[];
  wall_openings?: RawObject[];
  compass?: RawObject;
}

interface ValidatedV2Layout extends RawObject {
  version: '2.0';
  metadata: RawObject;
  active_floor_id: string;
  floors: RawObject[];
  sun_settings: RawObject;
  cross_floor_references: RawObject[];
}

type ValidatedNativeLayout = ValidatedVastuLayout | ValidatedV2Layout;

function isObject(value: unknown): value is RawObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function finiteNumber(value: unknown, path: string, positive = false): number {
  const number = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(number) || Math.abs(number) > MAX_ABS_COORDINATE || (positive && number <= 0)) {
    throw new Error(`${path} must be a ${positive ? 'positive ' : ''}finite number`);
  }
  return number;
}

/** Validate the untrusted Python JSON before conversion or any store mutation. */
export function assertVastuLayout(layout: unknown): asserts layout is ValidatedNativeLayout {
  if (isObject(layout) && layout.version === '2.0') {
    assertV2Layout(layout);
    return;
  }
  if (!isObject(layout)) throw new Error('Python layout must be a JSON object');
  if (layout.version !== '1.0') {
    throw new Error(`Unsupported Python layout version '${String(layout.version ?? 'missing')}' (expected 1.0 or 2.0)`);
  }
  if (!isObject(layout.metadata)) throw new Error('Python layout metadata is missing');

  const unit = String(layout.metadata.unit ?? '').toLowerCase();
  if (!UNIT_TO_CM[unit]) throw new Error(`Unsupported layout unit '${unit || 'missing'}'`);
  finiteNumber(layout.metadata.grid_spacing, 'metadata.grid_spacing', true);
  finiteNumber(layout.metadata.zoom_level ?? 1, 'metadata.zoom_level', true);
  finiteNumber(layout.metadata.unit_scale ?? 1, 'metadata.unit_scale', true);
  if (layout.metadata.wall_height_cm != null) {
    finiteNumber(layout.metadata.wall_height_cm, 'metadata.wall_height_cm', true);
  }

  const collections = ['rooms', 'furniture', 'shapes', 'text'] as const;
  let itemCount = 0;
  for (const name of collections) {
    const value = layout[name];
    if (!Array.isArray(value)) throw new Error(`Python layout '${name}' must be an array`);
    itemCount += value.length;
  }
  if (itemCount > MAX_LAYOUT_ENTITIES) {
    throw new Error(`Python layout has ${itemCount} items; maximum is ${MAX_LAYOUT_ENTITIES}`);
  }

  for (const [index, value] of (layout.rooms as unknown[]).entries()) {
    if (!isObject(value)) throw new Error(`rooms[${index}] must be an object`);
    finiteNumber(value.x0 ?? value.x, `rooms[${index}].x0`);
    finiteNumber(value.y0 ?? value.y, `rooms[${index}].y0`);
    finiteNumber(value.x1 ?? value.width, `rooms[${index}].x1/width`);
    finiteNumber(value.y1 ?? value.height, `rooms[${index}].y1/height`);
    if (value.wall_thickness_ft != null) finiteNumber(value.wall_thickness_ft, `rooms[${index}].wall_thickness_ft`, true);
    if (value.wall_erased_regions != null) {
      if (!isObject(value.wall_erased_regions)) throw new Error(`rooms[${index}].wall_erased_regions must be an object`);
      for (const intervals of Object.values(value.wall_erased_regions)) {
        if (!Array.isArray(intervals)) throw new Error(`rooms[${index}] has invalid wall erasures`);
        for (const interval of intervals) {
          if (!Array.isArray(interval) || interval.length < 2) throw new Error(`rooms[${index}] has an invalid wall interval`);
          finiteNumber(interval[0], `rooms[${index}].wall interval start`);
          finiteNumber(interval[1], `rooms[${index}].wall interval end`);
        }
      }
    }
  }

  let pointCount = 0;
  for (const [index, value] of (layout.shapes as unknown[]).entries()) {
    if (!isObject(value) || !Array.isArray(value.points)) throw new Error(`shapes[${index}].points must be an array`);
    pointCount += value.points.length;
    for (const [pointIndex, point] of value.points.entries()) {
      if (!Array.isArray(point) || point.length < 2) throw new Error(`shapes[${index}].points[${pointIndex}] is invalid`);
      finiteNumber(point[0], `shapes[${index}].points[${pointIndex}][0]`);
      finiteNumber(point[1], `shapes[${index}].points[${pointIndex}][1]`);
    }
  }
  if (pointCount > MAX_GEOMETRY_POINTS) {
    throw new Error(`Python layout has ${pointCount} shape points; maximum is ${MAX_GEOMETRY_POINTS}`);
  }

  for (const [index, value] of (layout.furniture as unknown[]).entries()) {
    if (!isObject(value)) throw new Error(`furniture[${index}] must be an object`);
    finiteNumber(value.x, `furniture[${index}].x`);
    finiteNumber(value.y, `furniture[${index}].y`);
    if (value.scale != null) finiteNumber(value.scale, `furniture[${index}].scale`, true);
    if (value.angle != null) finiteNumber(value.angle, `furniture[${index}].angle`);
  }

  for (const [index, value] of (layout.text as unknown[]).entries()) {
    if (!isObject(value)) throw new Error(`text[${index}] must be an object`);
    finiteNumber(value.x, `text[${index}].x`);
    finiteNumber(value.y, `text[${index}].y`);
  }

  if (layout.wall_openings != null) {
    if (!Array.isArray(layout.wall_openings)) throw new Error("Python layout 'wall_openings' must be an array");
    for (const [index, value] of (layout.wall_openings as unknown[]).entries()) {
      if (!isObject(value)) throw new Error(`wall_openings[${index}] must be an object`);
      finiteNumber(value.x, `wall_openings[${index}].x`);
      finiteNumber(value.y, `wall_openings[${index}].y`);
      if (value.width_cm != null) finiteNumber(value.width_cm, `wall_openings[${index}].width_cm`, true);
    }
  }

  if (layout.compass != null) {
    if (!isObject(layout.compass)) throw new Error('compass must be an object');
    if (layout.compass.north_deg_clockwise != null) {
      finiteNumber(layout.compass.north_deg_clockwise, 'compass.north_deg_clockwise');
    } else if (!DIRECTION_TO_DEG[String(layout.compass.direction ?? '').toUpperCase()] &&
      String(layout.compass.direction ?? '').toUpperCase() !== 'N') {
      throw new Error('compass.direction must be N, NE, E, SE, S, SW, W, or NW');
    }
  }
}

/** Infer a room type from a free-text room name (English + a few Hindi aliases). */
function labelToRoomType(name: string): RoomType {
  const t = (name || '').toLowerCase();
  const pairs: [string, RoomType][] = [
    ['rasoi', 'kitchen'], ['kitchen', 'kitchen'],
    // bathrooms before bedrooms: 'master bath' must not match 'master' first
    ['washroom', 'bathroom'], ['bathroom', 'bathroom'], ['toilet', 'bathroom'], ['bath', 'bathroom'],
    ['master', 'bedroom'], ['bedroom', 'bedroom'], ['bed', 'bedroom'], ['shayan', 'bedroom'],
    ['baithak', 'living'], ['living', 'living'], ['hall', 'living'], ['drawing', 'living'],
    ['dining', 'dining'], ['bhojan', 'dining'],
    ['study', 'study'], ['office', 'study'],
    ['puja', 'puja'], ['pooja', 'puja'], ['mandir', 'puja'],
    ['store', 'storage'], ['storage', 'storage'], ['bhandar', 'storage'],
    ['balcony', 'balcony'], ['garage', 'garage'], ['parking', 'garage'],
    ['entrance', 'entrance'], ['foyer', 'entrance'], ['corridor', 'corridor'],
  ];
  for (const [k, v] of pairs) if (t.includes(k)) return v;
  return 'custom';
}

const FILL_MODE_MAP: Record<string, Room['fillMode']> = {
  filled: 'filled',
  transparent: 'transparent',
  walls_only: 'walls-only',
};

/* ---------------------------------- helpers ---------------------------------- */

function dist(a: Point2D, b: Point2D): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** Distance from p to the infinite line through a→b. */
function pointLineDist(p: Point2D, a: Point2D, b: Point2D): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy);
  if (len < 1e-9) return dist(p, a);
  return Math.abs(dy * p.x - dx * p.y + b.x * a.y - b.y * a.x) / len;
}

/** Projection parameter (in cm along a→b from a) of p onto the line a→b. */
function lineParam(p: Point2D, a: Point2D, b: Point2D): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy);
  if (len < 1e-9) return 0;
  return ((p.x - a.x) * dx + (p.y - a.y) * dy) / len;
}

/** A gap cut into a wall, waiting to be classified as door (claimed) or window (default). */
interface PendingGap {
  wallId: EntityId;
  offsetCm: number;
  widthCm: number;
  center: Point2D;
}

/**
 * Split every wall wherever another vertex lies on its interior (T-junction), so imported
 * plans get the same clean graph the native editor produces (it splits at crossings too).
 * Runs before openings are placed, so no opening bookkeeping is needed here.
 */
function splitWallsAtTJunctions(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>,
): void {
  const worklist = Object.keys(walls);
  while (worklist.length > 0) {
    const wid = worklist.pop()!;
    const w = walls[wid];
    if (!w) continue;
    const a = vertices[w.startVertexId]?.position;
    const b = vertices[w.endVertexId]?.position;
    if (!a || !b) continue;

    // Nearest non-endpoint vertex strictly inside the segment.
    let hit: { vid: EntityId; t: number; d: number } | null = null;
    for (const [vid, v] of Object.entries(vertices)) {
      if (vid === w.startVertexId || vid === w.endVertexId) continue;
      const lenSq = (b.x - a.x) ** 2 + (b.y - a.y) ** 2;
      if (lenSq < 1e-9) continue;
      const t = ((v.position.x - a.x) * (b.x - a.x) + (v.position.y - a.y) * (b.y - a.y)) / lenSq;
      if (t <= 1e-6 || t >= 1 - 1e-6) continue;
      const px = a.x + t * (b.x - a.x);
      const py = a.y + t * (b.y - a.y);
      const d = Math.hypot(v.position.x - px, v.position.y - py);
      if (d < TJUNCTION_TOL_CM && (!hit || d < hit.d)) hit = { vid, t, d };
    }
    if (!hit) continue;

    // First half keeps the original id; second half gets a new one.
    const endId = w.endVertexId;
    const secondId = generateId('w');
    const firstHalf: Wall = { ...w, endVertexId: hit.vid };
    walls[wid] = firstHalf;
    vertices[endId].connectedWalls = vertices[endId].connectedWalls.filter((x) => x !== wid);
    walls[secondId] = { ...firstHalf, id: secondId, startVertexId: hit.vid, endVertexId: endId, openingIds: [] };
    vertices[hit.vid].connectedWalls.push(wid, secondId);
    vertices[endId].connectedWalls.push(secondId);
    // The halves may still cross other vertices — re-check them.
    worklist.push(wid, secondId);
  }
}

/** Drop duplicate walls between the same vertex pair (T-junction splits can create them
 *  when a room's side was already drawn as its neighbour's partial boundary). */
function dedupeWalls(vertices: Record<EntityId, Vertex>, walls: Record<EntityId, Wall>): void {
  const seen = new Map<string, EntityId>();
  for (const [id, w] of Object.entries(walls)) {
    const key = w.startVertexId < w.endVertexId ? `${w.startVertexId}|${w.endVertexId}` : `${w.endVertexId}|${w.startVertexId}`;
    if (!seen.has(key)) { seen.set(key, id); continue; }
    delete walls[id];
    for (const vid of [w.startVertexId, w.endVertexId]) {
      vertices[vid].connectedWalls = vertices[vid].connectedWalls.filter((x) => x !== id);
    }
  }
}

/**
 * Re-stitch room boundaries after T-junction splitting: if a room edge was split into
 * several collinear walls, insert the intermediate vertices into `boundaryVertexIds`.
 * Room detection keys rooms by their exact vertex set, so without this the imported
 * label/type/flooring would be dropped the moment the editor re-detects faces.
 */
function rebuildRoomBoundaries(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>,
  rooms: Record<EntityId, Room>,
): void {
  const adj = new Map<EntityId, EntityId[]>();
  const link = (a: EntityId, b: EntityId) => {
    const l = adj.get(a);
    if (l) l.push(b); else adj.set(a, [b]);
  };
  for (const w of Object.values(walls)) {
    link(w.startVertexId, w.endVertexId);
    link(w.endVertexId, w.startVertexId);
  }

  for (const [roomId, room] of Object.entries(rooms)) {
    const ids = [...room.boundaryVertexIds];
    if (ids.length < 3) continue;
    const out: EntityId[] = [];
    let ok = true;
    for (let i = 0; i < ids.length && ok; i++) {
      const a = ids[i];
      const b = ids[(i + 1) % ids.length];
      out.push(a);
      if ((adj.get(a) ?? []).includes(b)) continue; // direct wall — edge intact
      // Walk a → b through collinear intermediate vertices introduced by splitting.
      const pa = vertices[a]?.position;
      const pb = vertices[b]?.position;
      if (!pa || !pb) { ok = false; break; }
      const edgeLen = dist(pa, pb);
      let cur = a;
      const guard = new Set<EntityId>([a]);
      while (cur !== b) {
        const curParam = lineParam(vertices[cur].position, pa, pb);
        let next: EntityId | null = null;
        let nextParam = Infinity;
        for (const n of adj.get(cur) ?? []) {
          if (guard.has(n)) continue;
          const pn = vertices[n]?.position;
          if (!pn || pointLineDist(pn, pa, pb) > TJUNCTION_TOL_CM) continue;
          const t = lineParam(pn, pa, pb);
          if (t > curParam + 1e-6 && t < edgeLen + 1e-6 && t < nextParam) {
            next = n;
            nextParam = t;
          }
        }
        if (!next) { ok = false; break; }
        guard.add(next);
        if (next !== b) out.push(next);
        cur = next;
      }
    }
    if (ok) rooms[roomId] = { ...room, boundaryVertexIds: out };
  }
}

/** Translate imported content to a stable origin; canvas pan/zoom offsets are not model data. */
function normalizeGeometryOrigin(geometry: ConvertedGeometry): void {
  const points = [
    ...Object.values(geometry.vertices).map((value) => value.position),
    ...Object.values(geometry.furniture).map((value) => value.position),
    ...Object.values(geometry.annotations).map((value) => value.position),
  ];
  if (points.length === 0) return;
  const minX = Math.min(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  for (const [id, vertex] of Object.entries(geometry.vertices)) {
    geometry.vertices[id] = {
      ...vertex,
      position: { x: vertex.position.x - minX, y: vertex.position.y - minY },
    };
  }
  for (const [id, item] of Object.entries(geometry.furniture)) {
    geometry.furniture[id] = {
      ...item,
      position: { x: item.position.x - minX, y: item.position.y - minY },
    };
  }
  for (const [id, annotation] of Object.entries(geometry.annotations)) {
    geometry.annotations[id] = {
      ...annotation,
      position: { x: annotation.position.x - minX, y: annotation.position.y - minY },
    };
  }
}

/**
 * Convert a native Python layout object into this app's geometry (pure — no store writes).
 */
export function convertVastuLayout(layout: unknown): ConvertResult {
  if (isObject(layout) && layout.version === '2.0') return convertV2Layout(layout);
  return convertV1Layout(layout);
}

/** Shared v1 conversion; v2 defers normalization until every floor has been assembled. */
function convertV1Layout(layout: unknown, normalizeOrigin = true): ConvertResult {
  assertVastuLayout(layout);
  if (layout.version !== '1.0') throw new Error('Expected a nested Python layout version 1.0');
  const v1Layout = layout as ValidatedVastuLayout;
  const meta = v1Layout.metadata;
  const unit = String(meta.unit).toLowerCase();
  const gridSpacing = Number(meta.grid_spacing);
  const zoomLevel = Number(meta.zoom_level ?? 1);
  const unitScale = Number(meta.unit_scale ?? 1);
  const unitCm = UNIT_TO_CM[unit];
  const px2cm = (px: number) => (px * unitScale / (gridSpacing * zoomLevel)) * unitCm;
  const defaultWallHeightCm = Number(meta.wall_height_cm ?? DEFAULT_WALL_HEIGHT_CM);

  const vertices: Record<EntityId, Vertex> = {};
  const walls: Record<EntityId, Wall> = {};
  const rooms: Record<EntityId, Room> = {};
  const furniture: Record<EntityId, FurnitureItem> = {};
  const openings: Record<EntityId, Opening> = {};
  const annotations: Record<EntityId, TextAnnotation> = {};
  const unmapped: string[] = [];
  const residuals: string[] = [];

  // Python world Y grows downward on screen; our world Y is up. Flip Y so the plan isn't
  // mirrored vertically after import.
  const toWorld = (pxX: number, pxY: number): Point2D => ({ x: px2cm(pxX), y: -px2cm(pxY) });

  // A tiny spatial hash keeps snapping linear for normal plans instead of rescanning every corner.
  const cornerBuckets = new Map<string, { p: Point2D; id: EntityId }[]>();
  const bucketKey = (x: number, y: number) => `${x},${y}`;
  const getVertex = (p: Point2D): EntityId => {
    const bx = Math.floor(p.x / VERTEX_SNAP_CM);
    const by = Math.floor(p.y / VERTEX_SNAP_CM);
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        for (const corner of cornerBuckets.get(bucketKey(bx + dx, by + dy)) ?? []) {
          if (dist(corner.p, p) < VERTEX_SNAP_CM) return corner.id;
        }
      }
    }
    const id = generateId('v');
    vertices[id] = { id, position: { x: p.x, y: p.y }, connectedWalls: [] };
    const key = bucketKey(bx, by);
    cornerBuckets.set(key, [...(cornerBuckets.get(key) ?? []), { p, id }]);
    return id;
  };

  const wallByPair = new Map<string, EntityId>();
  const addWall = (
    a: EntityId,
    b: EntityId,
    thickness = DEFAULT_WALL_THICKNESS_CM,
    height = defaultWallHeightCm,
  ): EntityId | null => {
    if (a === b) return null;
    const key = a < b ? `${a}|${b}` : `${b}|${a}`;
    const existing = wallByPair.get(key);
    if (existing) {
      const wall = walls[existing];
      walls[existing] = { ...wall, thickness: Math.max(wall.thickness, thickness), height: Math.max(wall.height, height) };
      return existing;
    }
    const id = generateId('w');
    walls[id] = {
      id,
      startVertexId: a,
      endVertexId: b,
      thickness,
      height,
      materialId: 'default-wall',
      isLoadBearing: false,
      openingIds: [],
    };
    vertices[a].connectedWalls.push(id);
    vertices[b].connectedWalls.push(id);
    wallByPair.set(key, id);
    return id;
  };

  /* ------------------------- erased-region pre-scan ------------------------- */
  // wall_erased_regions: {top|bottom|left|right: [[axisStartPx, axisEndPx], ...]} — gaps cut
  // into a walls_only room's walls, in canvas px measured along that side. A gap spanning
  // the whole side means the wall itself was erased (open plan) → don't build that wall.
  //
  // IMPORTANT: the Python serializer emits this field for EVERY room, but for 'filled' /
  // 'transparent' rooms there are no wall-stroke rectangles to diff, so every side comes
  // out as a bogus FULL gap. Honouring those would delete all four walls of the room —
  // erased regions are only meaningful for 'walls_only' rooms.
  type Side = 'top' | 'bottom' | 'left' | 'right';
  interface RoomErasure { fullSides: Set<Side>; gaps: { side: Side; g0: number; g1: number }[] }

  // Canvas-px width of a room's wall stroke (mirrors RoomEntity._wall_thickness_pixels).
  const strokePxFor = (raw: RawObject): number => {
    const thicknessFt = Number(raw?.wall_thickness_ft ?? 0.2);
    const thicknessInUnit = unit === 'm' ? thicknessFt * 0.3048
      : unit === 'cm' ? thicknessFt * 30.48
        : unit === 'in' ? thicknessFt * 12
          : ['yd', 'yard', 'yards'].includes(unit) ? thicknessFt / 3
            : thicknessFt;
    return thicknessInUnit / unitScale * gridSpacing * zoomLevel;
  };
  const wallThicknessCmFor = (raw: RawObject): number =>
    Math.max(1, Number(raw.wall_thickness_ft ?? DEFAULT_WALL_THICKNESS_CM / 30.48) * 30.48);

  const rectRooms = v1Layout.rooms;
  const roomRects = rectRooms.map((r) => {
    const x0 = Number(r.x0 ?? r.x ?? 0);
    const y0 = Number(r.y0 ?? r.y ?? 0);
    const x1 = r.x1 != null ? Number(r.x1) : x0 + Number(r.width ?? 0);
    const y1 = r.y1 != null ? Number(r.y1) : y0 + Number(r.height ?? 0);
    return { raw: r, x0, y0, x1, y1 };
  });

  const erasures: RoomErasure[] = roomRects.map(({ x0, y0, x1, y1, raw }) => {
    const info: RoomErasure = { fullSides: new Set(), gaps: [] };
    if (String(raw?.fill_mode ?? 'filled') !== 'walls_only') return info;
    const wer = raw.wall_erased_regions;
    if (!isObject(wer)) return info;
    const strokePx = strokePxFor(raw);
    // The serializer insets the left/right axes by one wall stroke at each end.
    const axisSpan: Record<Side, number> = {
      top: Math.abs(x1 - x0),
      bottom: Math.abs(x1 - x0),
      left: Math.abs(y1 - y0) - 2 * strokePx,
      right: Math.abs(y1 - y0) - 2 * strokePx,
    };
    for (const side of ['top', 'bottom', 'left', 'right'] as Side[]) {
      const intervals: number[][] = Array.isArray(wer[side]) ? wer[side] : [];
      for (const iv of intervals) {
        if (!Array.isArray(iv) || iv.length < 2) continue;
        const g0 = Math.min(Number(iv[0]), Number(iv[1]));
        const g1 = Math.max(Number(iv[0]), Number(iv[1]));
        if (!(g1 > g0)) continue;
        if (g1 - g0 >= axisSpan[side] - 2) info.fullSides.add(side);
        else info.gaps.push({ side, g0, g1 });
      }
    }
    return info;
  });

  /* ------------------------------ walls ---------------------------------- */
  // Rect rooms → 4 walls (skipping fully erased sides) + Room.
  roomRects.forEach(({ raw: r, x0, y0, x1, y1 }, ri) => {
    if (Math.abs(x1 - x0) < 1 || Math.abs(y1 - y0) < 1) return;

    const corners = [toWorld(x0, y0), toWorld(x1, y0), toWorld(x1, y1), toWorld(x0, y1)];
    const ids = corners.map(getVertex);
    // Side order matches the corner order: 0=top, 1=right, 2=bottom, 3=left.
    const sideOfEdge: Side[] = ['top', 'right', 'bottom', 'left'];
    const wallThicknessCm = wallThicknessCmFor(r);
    for (let i = 0; i < 4; i++) {
      if (erasures[ri].fullSides.has(sideOfEdge[i])) continue;
      addWall(ids[i], ids[(i + 1) % 4], wallThicknessCm, defaultWallHeightCm);
    }

    const flooring = isObject(r.flooring) ? r.flooring : {};
    const flooringType = flooring.has_flooring ? String(flooring.flooring_type ?? '') : '';
    const label = String(r.name ?? 'Room');
    const roomId = generateId('room');
    rooms[roomId] = {
      id: roomId,
      boundaryVertexIds: ids,
      roomType: labelToRoomType(label),
      label,
      floorMaterialId: FLOORING_TYPE_TO_MATERIAL[flooringType] ?? 'default-floor',
      fillMode: FILL_MODE_MAP[String(r.fill_mode ?? 'filled')] ?? 'filled',
      ...(r.fill_color ? { fillColor: String(r.fill_color) } : {}),
    };
  });

  // Shapes → polygon wall loops (+ Room) or standalone 2-point wall lines. Helper shapes
  // (`polygon_vertex` ovals, `polygon_label` texts) are canvas decorations — skipped.
  const texts = v1Layout.text;
  const polygonLabelFor = (groupTag: string | undefined): string | null => {
    if (!groupTag) return null;
    for (const t of texts) {
      const tags = Array.isArray(t.tags) ? t.tags.map(String) : [];
      if (tags.includes(groupTag) && tags.includes('polygon_label')) {
        const content = String(t.content ?? '').trim();
        if (content) return content.split('\n')[0];
      }
    }
    return null;
  };

  const shapes = v1Layout.shapes;
  const unsupportedShapeTypes = new Set<string>();
  for (const s of shapes) {
    const pts = s.points as number[][];
    const tags = Array.isArray(s.tags) ? s.tags.map(String) : [];
    if (pts.length === 2 && (tags.includes('wall_line') || tags.includes('line'))) {
      const a = getVertex(toWorld(pts[0][0], pts[0][1]));
      const b = getVertex(toWorld(pts[1][0], pts[1][1]));
      addWall(a, b);
    } else if (pts.length >= 3 && (s.type === 'polygon' || tags.includes('closed_shape') || tags.includes('polygon_shape'))) {
      const vids = pts.map((p) => getVertex(toWorld(p[0], p[1])));
      for (let i = 0; i < vids.length; i++) addWall(vids[i], vids[(i + 1) % vids.length]);

      const groupTag = tags.find((tag) => tag.startsWith('polygon_group_'));
      const label = polygonLabelFor(groupTag) ?? 'Room';
      const flooring = isObject(s.flooring) ? s.flooring : {};
      const flooringType = flooring.has_flooring ? String(flooring.flooring_type ?? '') : '';
      const rid = generateId('room');
      rooms[rid] = {
        id: rid,
        boundaryVertexIds: vids,
        roomType: labelToRoomType(label),
        label,
        floorMaterialId: FLOORING_TYPE_TO_MATERIAL[flooringType] ?? 'default-floor',
        fillMode: 'filled',
      };
    } else if (String(s.type) !== 'text' && !tags.some((tag) => tag === 'polygon_vertex' || tag === 'polygon_label')) {
      unsupportedShapeTypes.add(String(s.type ?? 'unknown'));
    }
  }
  if (unsupportedShapeTypes.size > 0) {
    residuals.push(`unsupported shape types skipped: ${[...unsupportedShapeTypes].sort().join(', ')}`);
  }

  // T-junction splitting (+ dedup of halves that duplicate existing walls) — must run
  // before openings are placed. Room boundaries are then re-stitched through the new
  // intermediate vertices so the rooms survive the editor's face re-detection.
  splitWallsAtTJunctions(vertices, walls);
  dedupeWalls(vertices, walls);
  rebuildRoomBoundaries(vertices, walls, rooms);

  /* ------------------------------ openings -------------------------------- */
  const pendingGaps: PendingGap[] = [];

  // Partial erased gaps → candidate openings on whichever wall segment overlaps them
  // (a side split by a T-junction yields one opening per overlapping piece).
  roomRects.forEach(({ x0, y0, x1, y1 }, ri) => {
    for (const gap of erasures[ri].gaps) {
      // Side endpoints in px, then to world (axis runs start→end in px space).
      const sidePx: Record<Side, [number, number, number, number]> = {
        top: [x0, y0, x1, y0],
        bottom: [x0, y1, x1, y1],
        left: [x0, y0, x0, y1],
        right: [x1, y0, x1, y1],
      };
      const [ax, ay, bx, by] = sidePx[gap.side];
      const t0 = (gap.g0 - (gap.side === 'top' || gap.side === 'bottom' ? ax : ay)) /
        ((gap.side === 'top' || gap.side === 'bottom' ? bx - ax : by - ay) || 1);
      const t1 = (gap.g1 - (gap.side === 'top' || gap.side === 'bottom' ? ax : ay)) /
        ((gap.side === 'top' || gap.side === 'bottom' ? bx - ax : by - ay) || 1);
      const w0 = toWorld(ax + (bx - ax) * t0, ay + (by - ay) * t0);
      const w1 = toWorld(ax + (bx - ax) * t1, ay + (by - ay) * t1);
      const gapLenCm = dist(w0, w1);
      if (gapLenCm < MIN_OPENING_WIDTH_CM) continue;

      for (const w of Object.values(walls)) {
        const p = vertices[w.startVertexId].position;
        const q = vertices[w.endVertexId].position;
        if (pointLineDist(p, w0, w1) > VERTEX_SNAP_CM || pointLineDist(q, w0, w1) > VERTEX_SNAP_CM) continue;
        // Overlap between the wall's span and the gap's span, along the gap axis.
        const pP = lineParam(p, w0, w1);
        const pQ = lineParam(q, w0, w1);
        const lo = Math.max(Math.min(pP, pQ), 0);
        const hi = Math.min(Math.max(pP, pQ), gapLenCm);
        if (hi - lo < MIN_OPENING_WIDTH_CM) continue;
        // Opening.offsetCm is the CENTRE of the hole, measured from the wall's startVertex.
        const offsetCm = Math.abs(pP - (lo + hi) / 2);
        const widthCm = hi - lo;
        const midT = (lo + hi) / 2 / (gapLenCm || 1);
        const candidate: PendingGap = {
          wallId: w.id,
          offsetCm,
          widthCm,
          center: { x: w0.x + (w1.x - w0.x) * midT, y: w0.y + (w1.y - w0.y) * midT },
        };
        const duplicate = pendingGaps.some((existing) =>
          existing.wallId === candidate.wallId &&
          Math.abs(existing.offsetCm - candidate.offsetCm) < 1 &&
          Math.abs(existing.widthCm - candidate.widthCm) < 1
        );
        if (!duplicate) pendingGaps.push(candidate);
      }
    }
  });

  const addOpening = (wallId: EntityId, type: Opening['type'], kind: string, offsetCm: number, widthCm?: number): EntityId => {
    const k = getOpeningKind(kind);
    const id = generateId('opening');
    openings[id] = {
      id,
      wallId,
      type,
      kind,
      offsetCm: Math.max(0, Math.round(offsetCm * 100) / 100),
      width: Math.round((widthCm ?? k?.width ?? 90) * 10) / 10,
      height: k?.height ?? 210,
      elevation: k?.elevation ?? 0,
    };
    walls[wallId].openingIds.push(id);
    return id;
  };

  // Door furniture → door openings. A door placed on a walls_only room recuts the wall in
  // the Python editor, so there is usually a matching gap to claim (exact position/width);
  // otherwise project onto the closest wall like the old Python converter did.
  const furnList = v1Layout.furniture;
  for (const f of furnList) {
    const name = String(f.image_name ?? f.image_filename ?? '');
    if (!/door/i.test(name)) continue;
    const c = toWorld(Number(f.x ?? 0), Number(f.y ?? 0));
    const kind = /gate/i.test(name) ? 'door-main-gate' : /doublehand|double/i.test(name) ? 'door-double' : 'door-standard';

    // 1) claim a pending gap near the door centre
    let bestGap: PendingGap | null = null;
    let bestGapDist = DOOR_SNAP_CM;
    for (const g of pendingGaps) {
      const d = dist(g.center, c);
      if (d < bestGapDist) { bestGap = g; bestGapDist = d; }
    }
    if (bestGap) {
      addOpening(bestGap.wallId, 'door', kind, bestGap.offsetCm, bestGap.widthCm);
      pendingGaps.splice(pendingGaps.indexOf(bestGap), 1);
      continue;
    }

    // 2) closest-wall projection fallback
    let bestWall: Wall | null = null;
    let bestT = 0;
    let bestDist = DOOR_SNAP_CM;
    for (const w of Object.values(walls)) {
      const p = vertices[w.startVertexId].position;
      const q = vertices[w.endVertexId].position;
      const len = dist(p, q);
      if (len < 1e-9) continue;
      const t = Math.max(0, Math.min(1, lineParam(c, p, q) / len));
      const proj = { x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t };
      const d = dist(c, proj);
      if (d < bestDist) { bestWall = w; bestT = t; bestDist = d; }
    }
    if (bestWall) {
      const p = vertices[bestWall.startVertexId].position;
      const q = vertices[bestWall.endVertexId].position;
      addOpening(bestWall.id, 'door', kind, bestT * dist(p, q));
    } else {
      residuals.push(`door '${name}' not near any wall — skipped`);
    }
  }

  // Unclaimed gaps are windows.
  for (const g of pendingGaps) {
    addOpening(g.wallId, 'window', 'window-standard', g.offsetCm, g.widthCm);
  }

  // Explicit windows / ventilation placed on hand-drawn walls with the editor's
  // "Windows & Ventilation" tool. These are symbols (no wall gap), so project each onto the
  // nearest wall — the same closest-wall fallback doors use — and render it in 3D.
  for (const [index, raw] of (v1Layout.wall_openings ?? []).entries()) {
    const type: Opening['type'] = raw.type === 'vent' ? 'vent' : 'window';
    const kind = String(raw.kind ?? (type === 'vent' ? 'vent-normal' : 'window-standard'));
    const c = toWorld(Number(raw.x ?? 0), Number(raw.y ?? 0));
    const widthCm = Number(raw.width_cm) > 0 ? Number(raw.width_cm) : undefined;
    let bestWall: Wall | null = null;
    let bestT = 0;
    let bestDist = OPENING_SNAP_CM;
    for (const w of Object.values(walls)) {
      const p = vertices[w.startVertexId].position;
      const q = vertices[w.endVertexId].position;
      const len = dist(p, q);
      if (len < 1e-9) continue;
      const t = Math.max(0, Math.min(1, lineParam(c, p, q) / len));
      const proj = { x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t };
      const d = dist(c, proj);
      if (d < bestDist) { bestWall = w; bestT = t; bestDist = d; }
    }
    if (bestWall) {
      const p = vertices[bestWall.startVertexId].position;
      const q = vertices[bestWall.endVertexId].position;
      addOpening(bestWall.id, type, kind, bestT * dist(p, q), widthCm);
    } else {
      residuals.push(`${type} opening[${index}] not near any wall — skipped`);
    }
  }

  /* ------------------------------ furniture ------------------------------- */
  for (const f of furnList) {
    const name = String(f.image_name ?? f.image_filename ?? '');
    if (/door/i.test(name)) continue; // doors became openings above
    const catalogId = FURNITURE_NAME_TO_CATALOG[name] ?? FURNITURE_NAME_TO_CATALOG[name.toLowerCase()];
    if (!catalogId) {
      const unavailableName = name || '(unnamed furniture)';
      unmapped.push(unavailableName);
      const markerId = generateId('text');
      annotations[markerId] = {
        id: markerId,
        position: toWorld(Number(f.x), Number(f.y)),
        text: `⚠ ASSET UNAVAILABLE: ${unavailableName}`,
        fontSizeCm: 18,
        color: '#ef4444',
      };
      continue;
    }
    const entry = getCatalogEntry(catalogId);
    const id = generateId('furniture');
    furniture[id] = {
      id,
      position: toWorld(Number(f.x), Number(f.y)),
      rotation: -(Number(f.angle ?? 0) * Math.PI) / 180,
      scale: Number(f.scale ?? 1),
      catalogId,
      roomId: null,
      bounds: { width: entry.bounds.width, depth: entry.bounds.depth },
    };
  }

  /* ----------------------------- annotations ------------------------------ */
  const generatedTextTags = new Set([
    'grid', 'room_label', 'dimension_item', 'dimension_label',
    'dimension_text_bg', 'room_dimensions', 'compass', 'canonical_v2_mirror',
  ]);
  for (const t of texts) {
    const tags = Array.isArray(t.tags) ? t.tags.map(String) : [];
    if (tags.includes('polygon_label')) continue;
    if (tags.some((tag) => generatedTextTags.has(String(tag)))) continue;
    const content = String(t.content ?? t.text ?? '').trim();
    if (!content) continue;
    const fontPt = parseFloat(String(t.font ?? 'Arial 10').replace(/[^\d.]/g, '')) || 10;
    const id = generateId('text');
    annotations[id] = {
      id,
      position: toWorld(Number(t.x), Number(t.y)),
      text: content,
      fontSizeCm: Math.max(15, px2cm(fontPt * 1.6)),
      color: String(t.color ?? '#fde68a'),
    };
  }

  /* ------------------------------- compass -------------------------------- */
  const compass = v1Layout.compass;
  const dir = String(compass?.direction ?? '').toUpperCase();
  const numericNorth = compass?.north_deg_clockwise;
  const northDeg = numericNorth != null
    ? ((Number(numericNorth) % 360) + 360) % 360
    : DIRECTION_TO_DEG[dir] ?? 0;
  if (numericNorth == null && !dir) residuals.push('north orientation was not configured; defaulted to 0°');

  const geometry: ConvertedGeometry = {
    vertices, walls, rooms, furniture, openings, annotations,
    roads: {}, stairs: {}, pillars: {}, beams: {}, deckSlabs: {}, railings: {},
  };
  if (normalizeOrigin) normalizeGeometryOrigin(geometry);

  const report: ImportReport = {
    rooms: Object.keys(rooms).length,
    walls: Object.keys(walls).length,
    furniture: Object.keys(furniture).length,
    openings: Object.keys(openings).length,
    annotations: Object.keys(annotations).length,
    northDeg,
    unmapped: [...new Set(unmapped)],
    residuals: [...new Set(residuals)],
  };

  return { geometry, northDeg, report };
}

/**
 * Convert AND load a native Python layout into the live store (single-floor). Returns the
 * import report. Resets floors/history so the imported plan is a clean baseline.
 */
export function importVastuLayout(layout: unknown): ImportReport {
  const { geometry, northDeg, report, project } = convertVastuLayout(layout);
  const active = project?.geometryByFloor[project.activeFloorId] ?? geometry;
  const floorId = project?.activeFloorId ?? generateId('floor');
  const floorData = project
    ? Object.fromEntries(Object.entries(project.geometryByFloor).filter(([id]) => id !== project.activeFloorId))
    : {};

  // Conversion and validation above are pure. This is the only observable project write.
  useAppStore.setState({
    floors: project?.floors ?? [{ id: floorId, name: 'Ground Floor', elevationCm: 0 }],
    activeFloorId: floorId,
    floorData,
    vertices: active.vertices,
    walls: active.walls,
    rooms: active.rooms,
    furniture: active.furniture,
    openings: active.openings,
    annotations: active.annotations,
    roads: active.roads,
    stairs: active.stairs,
    pillars: active.pillars,
    beams: active.beams,
    deckSlabs: active.deckSlabs,
    railings: active.railings,
    selectedIds: [],
    vastuNorthDeg: northDeg,
    ...(project ? {
      sunTimeHours: project.sunSettings.timeHours,
      sunAzimuthDeg: project.sunSettings.azimuthDeg,
      sunDirectionOverride: project.sunSettings.directionOverride,
    } : {}),
  });
  useAppStore.getState().clearHistory();
  return report;
}


/* ----------------------------- native v2 ----------------------------- */

const V2_COLLECTIONS = [
  'vertices', 'walls', 'rooms', 'openings', 'furniture', 'shapes', 'text',
  'pillars', 'beams', 'deck_slabs', 'railings', 'stairs',
] as const;
const ROOM_TYPES = new Set<RoomType>([
  'living', 'bedroom', 'kitchen', 'bathroom', 'puja', 'study', 'dining',
  'storage', 'garage', 'balcony', 'entrance', 'corridor', 'custom',
]);
const REFERENCE_FIELDS = new Set([
  'start_vertex_id', 'end_vertex_id', 'boundary_vertex_ids', 'opening_ids',
  'wall_id', 'wall_ids', 'room_id', 'host_id', 'deck_slab_id', 'post_ids',
]);

function requiredText(value: unknown, path: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${path} must be a non-empty string`);
  return value;
}

function rawArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${path} must be an array`);
  return value;
}

function rawPoint(value: unknown, path: string): Point2D {
  if (Array.isArray(value) && value.length === 2) {
    return { x: finiteNumber(value[0], `${path}[0]`), y: finiteNumber(value[1], `${path}[1]`) };
  }
  if (isObject(value)) {
    return { x: finiteNumber(value.x, `${path}.x`), y: finiteNumber(value.y, `${path}.y`) };
  }
  throw new Error(`${path} must be an {x, y} object or two-number array`);
}

function v2Metadata(layout: RawObject): { px2cm: (value: number) => number; wallHeightCm: number } {
  if (!isObject(layout.metadata)) throw new Error('Python layout metadata is missing');
  const unit = String(layout.metadata.unit ?? '').toLowerCase();
  const unitCm = UNIT_TO_CM[unit];
  if (!unitCm) throw new Error(`Unsupported layout unit '${unit || 'missing'}'`);
  const gridSpacing = finiteNumber(layout.metadata.grid_spacing, 'metadata.grid_spacing', true);
  const zoomLevel = finiteNumber(layout.metadata.zoom_level ?? 1, 'metadata.zoom_level', true);
  const unitScale = finiteNumber(layout.metadata.unit_scale ?? 1, 'metadata.unit_scale', true);
  const wallHeightCm = finiteNumber(
    layout.metadata.wall_height_cm ?? DEFAULT_WALL_HEIGHT_CM,
    'metadata.wall_height_cm',
    true,
  );
  return { px2cm: (value) => value * unitScale / (gridSpacing * zoomLevel) * unitCm, wallHeightCm };
}

function validateSimplePolygon(value: unknown, path: string): void {
  const raw = rawArray(value, path);
  let points = raw.map((point, index) => rawPoint(point, `${path}[${index}]`));
  if (points.length > 1 && points[0].x === points.at(-1)!.x && points[0].y === points.at(-1)!.y) {
    points = points.slice(0, -1);
  }
  if (points.length < 3 || new Set(points.map((point) => `${point.x},${point.y}`)).size < 3) {
    throw new Error(`${path} must contain at least three distinct points`);
  }
  const cross = (a: Point2D, b: Point2D, c: Point2D) =>
    (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  const area2 = points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point.x * next.y - next.x * point.y;
  }, 0);
  if (Math.abs(area2) <= 1e-9) throw new Error(`${path} must have non-zero area`);
  const onSegment = (a: Point2D, b: Point2D, point: Point2D) =>
    point.x >= Math.min(a.x, b.x) - 1e-9 && point.x <= Math.max(a.x, b.x) + 1e-9 &&
    point.y >= Math.min(a.y, b.y) - 1e-9 && point.y <= Math.max(a.y, b.y) + 1e-9;
  const intersects = (a: Point2D, b: Point2D, c: Point2D, d: Point2D) => {
    const values = [cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)];
    if (values[0] * values[1] < 0 && values[2] * values[3] < 0) return true;
    return (Math.abs(values[0]) <= 1e-9 && onSegment(a, b, c)) ||
      (Math.abs(values[1]) <= 1e-9 && onSegment(a, b, d)) ||
      (Math.abs(values[2]) <= 1e-9 && onSegment(c, d, a)) ||
      (Math.abs(values[3]) <= 1e-9 && onSegment(c, d, b));
  };
  // ponytail: imported deck polygons are small; a sweep-line is only worthwhile for large CAD files.
  for (let first = 0; first < points.length; first++) {
    const a = points[first];
    const b = points[(first + 1) % points.length];
    if (a.x === b.x && a.y === b.y) throw new Error(`${path}[${first}] edge must have non-zero length`);
    for (let second = first + 1; second < points.length; second++) {
      if (second === first + 1 || (first === 0 && second === points.length - 1)) continue;
      if (intersects(a, b, points[second], points[(second + 1) % points.length])) {
        throw new Error(`${path} must not self-intersect`);
      }
    }
  }
}

function assertV2Layout(layout: RawObject): asserts layout is ValidatedV2Layout {
  if (layout.version !== '2.0') throw new Error(`Unsupported Python layout version '${String(layout.version)}'`);
  const projectPx2cm = v2Metadata(layout).px2cm;
  const floors = rawArray(layout.floors, 'floors');
  if (floors.length === 0) throw new Error('floors must contain at least one floor');
  const floorIds = new Set<string>();
  const floorNames = new Set<string>();
  const elevations = new Set<number>();
  const floorElevations = new Map<string, number>();
  const entityOwner = new Map<string, string>();
  const entityKind = new Map<string, string>();
  const entities: Array<{ raw: RawObject; path: string; floorId: string }> = [];
  const stairEntities: Array<{ raw: RawObject; path: string; floorId: string }> = [];
  let totalEntities = 0;
  let totalPoints = 0;
  let groundFloors = 0;

  floors.forEach((value, floorIndex) => {
    const base = `floors[${floorIndex}]`;
    if (!isObject(value)) throw new Error(`${base} must be an object`);
    const floorId = requiredText(value.id, `${base}.id`);
    if (floorIds.has(floorId) || entityOwner.has(floorId)) throw new Error(`${base}.id must be globally unique`);
    floorIds.add(floorId);
    const name = requiredText(value.name, `${base}.name`);
    if (name !== name.trim()) throw new Error(`${base}.name must be trimmed`);
    if (floorNames.has(name.toLowerCase())) throw new Error(`${base}.name must be unique`);
    floorNames.add(name.toLowerCase());
    const elevation = finiteNumber(value.elevation_cm, `${base}.elevation_cm`);
    if (elevation < 0 || elevations.has(elevation)) throw new Error(`${base}.elevation_cm must be unique and non-negative`);
    elevations.add(elevation);
    floorElevations.set(floorId, elevation);
    if (elevation === 0) groundFloors++;
    if (!isObject(value.geometry)) throw new Error(`${base}.geometry must be an object`);
    if (value.geometry.canvas != null) {
      const canvasPath = `${base}.geometry.canvas`;
      if (!isObject(value.geometry.canvas) || value.geometry.canvas.version !== '1.0') {
        throw new Error(`${canvasPath} must be a native version 1.0 layout`);
      }
      try {
        assertVastuLayout(value.geometry.canvas);
      } catch (error) {
        throw new Error(`${canvasPath}: ${error instanceof Error ? error.message : String(error)}`, { cause: error });
      }
    }
    const floorPx2cm = isObject(value.geometry.canvas)
      ? v2Metadata(value.geometry.canvas).px2cm
      : projectPx2cm;
    for (const collection of V2_COLLECTIONS) {
      const values = value.geometry[collection] == null ? [] : rawArray(value.geometry[collection], `${base}.geometry.${collection}`);
      totalEntities += values.length;
      values.forEach((raw, entityIndex) => {
        const path = `${base}.geometry.${collection}[${entityIndex}]`;
        if (!isObject(raw)) throw new Error(`${path} must be an object`);
        const id = requiredText(raw.id, `${path}.id`);
        if (floorIds.has(id) || entityOwner.has(id)) throw new Error(`${path}.id must be globally unique`);
        entityOwner.set(id, floorId);
        entityKind.set(id, collection);
        entities.push({ raw, path, floorId });
        if (collection === 'stairs') stairEntities.push({ raw, path, floorId });

        if (collection === 'vertices') rawPoint(raw.position ?? { x: raw.x, y: raw.y }, `${path}.position`);
        if (collection === 'walls') {
          finiteNumber(raw.thickness_cm, `${path}.thickness_cm`, true);
          finiteNumber(raw.height_cm, `${path}.height_cm`, true);
        }
        if (collection === 'rooms') {
          const boundary = rawArray(raw.boundary_vertex_ids, `${path}.boundary_vertex_ids`);
          if (boundary.length < 3) throw new Error(`${path}.boundary_vertex_ids must contain at least three vertices`);
        }
        if (collection === 'openings') {
          const type = requiredText(raw.type, `${path}.type`);
          if (!['door', 'window', 'vent', 'ac'].includes(type)) throw new Error(`${path}.type is unsupported`);
          finiteNumber(raw.offset_cm, `${path}.offset_cm`);
          finiteNumber(raw.width_cm, `${path}.width_cm`, true);
          finiteNumber(raw.height_cm, `${path}.height_cm`, true);
          finiteNumber(raw.elevation_cm ?? 0, `${path}.elevation_cm`);
          const kind = raw.kind == null ? null : getOpeningKind(String(raw.kind));
          if (kind && kind.type !== type) throw new Error(`${path}.kind is incompatible with type`);
        }
        if (collection === 'furniture') {
          rawPoint(raw.position ?? { x: raw.x, y: raw.y }, `${path}.position`);
          if (raw.scale != null) finiteNumber(raw.scale, `${path}.scale`, true);
          if (raw.angle_deg != null) finiteNumber(raw.angle_deg, `${path}.angle_deg`);
          if (raw.angle != null) finiteNumber(raw.angle, `${path}.angle`);
          if (raw.rotation_rad != null) finiteNumber(raw.rotation_rad, `${path}.rotation_rad`);
          if (raw.bounds != null) {
            if (!isObject(raw.bounds)) throw new Error(`${path}.bounds must be an object`);
            finiteNumber(raw.bounds.width, `${path}.bounds.width`, true);
            finiteNumber(raw.bounds.depth, `${path}.bounds.depth`, true);
          }
        }
        if (collection === 'text') {
          rawPoint(raw.position ?? { x: raw.x, y: raw.y }, `${path}.position`);
          if (raw.font_size_cm != null) finiteNumber(raw.font_size_cm, `${path}.font_size_cm`, true);
          if (raw.rotation_deg != null) finiteNumber(raw.rotation_deg, `${path}.rotation_deg`);
        }
        if (collection === 'pillars') {
          rawPoint(raw.position, `${path}.position`);
          for (const field of ['width_cm', 'depth_cm', 'height_cm'] as const) finiteNumber(raw[field], `${path}.${field}`, true);
          finiteNumber(raw.elevation_cm ?? 0, `${path}.elevation_cm`);
          if (raw.shape != null && !['rect', 'round'].includes(String(raw.shape))) throw new Error(`${path}.shape is unsupported`);
        }
        if (collection === 'beams') {
          const start = rawPoint(raw.start, `${path}.start`);
          const end = rawPoint(raw.end, `${path}.end`);
          if (dist(start, end) <= 1e-9) throw new Error(`${path}.end must differ from start`);
          finiteNumber(raw.width_cm, `${path}.width_cm`, true);
          finiteNumber(raw.depth_cm, `${path}.depth_cm`, true);
          finiteNumber(raw.elevation_cm ?? 0, `${path}.elevation_cm`);
        }
        if (collection === 'deck_slabs') {
          const polygon = rawArray(raw.polygon, `${path}.polygon`);
          totalPoints += polygon.length;
          validateSimplePolygon(polygon, `${path}.polygon`);
          finiteNumber(raw.thickness_cm, `${path}.thickness_cm`, true);
          finiteNumber(raw.elevation_cm ?? 0, `${path}.elevation_cm`);
          if (raw.type != null && !['corridor', 'balcony', 'landing', 'roof', 'custom'].includes(String(raw.type))) {
            throw new Error(`${path}.type is unsupported`);
          }
        }
        if (collection === 'railings') {
          const start = rawPoint(raw.start, `${path}.start`);
          const end = rawPoint(raw.end, `${path}.end`);
          if (dist(start, end) <= 1e-9) throw new Error(`${path}.end must differ from start`);
          finiteNumber(raw.height_cm, `${path}.height_cm`, true);
          finiteNumber(raw.elevation_cm ?? 0, `${path}.elevation_cm`);
          if (raw.style != null && !['open', 'solid'].includes(String(raw.style))) throw new Error(`${path}.style is unsupported`);
        }
        if (collection === 'stairs') {
          const rawPoints = rawArray(raw.path_points, `${path}.path_points`);
          if (rawPoints.length < 2) throw new Error(`${path}.path_points must contain at least two points`);
          totalPoints += rawPoints.length;
          const points = rawPoints.map((point, index) => rawPoint(point, `${path}.path_points[${index}]`));
          for (let index = 1; index < points.length; index++) {
            const dxCm = floorPx2cm(points[index].x - points[index - 1].x);
            const dyCm = floorPx2cm(points[index].y - points[index - 1].y);
            if (Math.hypot(dxCm, dyCm) < 1) {
              throw new Error(`${path}.path_points[${index}] must be at least 1 cm from the previous point`);
            }
          }
          const width = finiteNumber(raw.width_cm, `${path}.width_cm`, true);
          if (width < 60 || width > 500) throw new Error(`${path}.width_cm must be in [60, 500]`);
          requiredText(raw.lower_floor_id, `${path}.lower_floor_id`);
          requiredText(raw.upper_floor_id, `${path}.upper_floor_id`);
        }
      });
    }
  });
  if (groundFloors !== 1) throw new Error('floors must contain exactly one floor at elevation 0');
  if (totalEntities > MAX_LAYOUT_ENTITIES) throw new Error(`Python layout has ${totalEntities} items; maximum is ${MAX_LAYOUT_ENTITIES}`);
  if (totalPoints > MAX_GEOMETRY_POINTS) throw new Error(`Python layout has ${totalPoints} geometry points; maximum is ${MAX_GEOMETRY_POINTS}`);
  const activeFloorId = requiredText(layout.active_floor_id, 'active_floor_id');
  if (!floorIds.has(activeFloorId)) throw new Error('active_floor_id must reference an existing floor');
  const activeFloor = floors.find((value) => isObject(value) && value.id === activeFloorId) as RawObject;
  const activeGeometry = activeFloor.geometry as RawObject;
  const compass = isObject(layout.compass) ? layout.compass : isObject(activeGeometry.compass) ? activeGeometry.compass : undefined;
  if (compass?.north_deg_clockwise != null) finiteNumber(compass.north_deg_clockwise, 'compass.north_deg_clockwise');
  if (compass && compass.north_deg_clockwise == null) {
    const direction = String(compass.direction ?? '').toUpperCase();
    if (!(direction in DIRECTION_TO_DEG)) throw new Error('compass.direction must be N, NE, E, SE, S, SW, W, or NW');
  }

  for (const { raw, path, floorId } of stairEntities) {
    const lowerFloorId = requiredText(raw.lower_floor_id, `${path}.lower_floor_id`);
    const upperFloorId = requiredText(raw.upper_floor_id, `${path}.upper_floor_id`);
    if (lowerFloorId !== floorId) {
      throw new Error(`${path}.lower_floor_id must equal the floor containing the staircase`);
    }
    const lowerElevation = floorElevations.get(lowerFloorId);
    const upperElevation = floorElevations.get(upperFloorId);
    if (upperElevation == null) throw new Error(`${path}.upper_floor_id must reference an existing floor`);
    if (lowerElevation == null || upperElevation <= lowerElevation) {
      throw new Error(`${path}.upper_floor_id must reference a floor above the staircase`);
    }
  }

  const requireReference = (value: unknown, path: string, owner: string, kind?: string) => {
    const id = requiredText(value, path);
    if (entityOwner.get(id) !== owner) throw new Error(`${path} must reference an entity on the same floor`);
    if (kind && entityKind.get(id) !== kind) throw new Error(`${path} must reference ${kind}`);
    return id;
  };
  for (const { raw, path, floorId } of entities) {
    const kind = entityKind.get(String(raw.id));
    if (kind === 'walls') {
      const startId = requireReference(raw.start_vertex_id, `${path}.start_vertex_id`, floorId, 'vertices');
      const endId = requireReference(raw.end_vertex_id, `${path}.end_vertex_id`, floorId, 'vertices');
      if (startId === endId) throw new Error(`${path}.end_vertex_id must differ from start_vertex_id`);
      for (const [index, id] of rawArray(raw.opening_ids ?? [], `${path}.opening_ids`).entries()) {
        requireReference(id, `${path}.opening_ids[${index}]`, floorId, 'openings');
      }
    } else if (kind === 'rooms') {
      const boundary = rawArray(raw.boundary_vertex_ids, `${path}.boundary_vertex_ids`);
      if (new Set(boundary.map(String)).size < 3) throw new Error(`${path}.boundary_vertex_ids must contain three distinct vertices`);
      for (const [index, id] of boundary.entries()) {
        requireReference(id, `${path}.boundary_vertex_ids[${index}]`, floorId, 'vertices');
      }
    } else if (kind === 'openings') {
      const wallId = requireReference(raw.wall_id, `${path}.wall_id`, floorId, 'walls');
      const wall = entities.find((entry) => entry.raw.id === wallId)?.raw;
      if (wall && Array.isArray(wall.opening_ids) && !wall.opening_ids.includes(raw.id)) {
        throw new Error(`${path}.wall_id does not list this opening in opening_ids`);
      }
    } else if (kind === 'furniture' && raw.room_id != null) {
      requireReference(raw.room_id, `${path}.room_id`, floorId, 'rooms');
    }
    for (const [field, value] of Object.entries(raw)) {
      if (!REFERENCE_FIELDS.has(field) || ['start_vertex_id', 'end_vertex_id', 'opening_ids', 'boundary_vertex_ids', 'wall_id', 'room_id'].includes(field)) continue;
      const references = field.endsWith('_ids') ? rawArray(value, `${path}.${field}`) : value == null ? [] : [value];
      references.forEach((id, index) => requireReference(id, `${path}.${field}${field.endsWith('_ids') ? `[${index}]` : ''}`, floorId));
    }
  }

  if (!isObject(layout.sun_settings)) throw new Error('sun_settings must be an object');
  const time = finiteNumber(layout.sun_settings.time_hours, 'sun_settings.time_hours');
  const azimuth = finiteNumber(layout.sun_settings.azimuth_deg, 'sun_settings.azimuth_deg');
  if (time < 0 || time > 24) throw new Error('sun_settings.time_hours must be in [0, 24]');
  if (azimuth < 0 || azimuth >= 360) throw new Error('sun_settings.azimuth_deg must be in [0, 360)');
  if (typeof layout.sun_settings.direction_override !== 'boolean') throw new Error('sun_settings.direction_override must be a boolean');

  const crossReferences = rawArray(layout.cross_floor_references, 'cross_floor_references');
  const allIds = new Set([...floorIds, ...entityOwner.keys()]);
  crossReferences.forEach((value, index) => {
    const path = `cross_floor_references[${index}]`;
    if (!isObject(value)) throw new Error(`${path} must be an object`);
    const id = requiredText(value.id, `${path}.id`);
    if (allIds.has(id)) throw new Error(`${path}.id must be globally unique`);
    allIds.add(id);
    requiredText(value.type, `${path}.type`);
    const sourceFloor = requiredText(value.source_floor_id, `${path}.source_floor_id`);
    const targetFloor = requiredText(value.target_floor_id, `${path}.target_floor_id`);
    if (!floorIds.has(sourceFloor) || !floorIds.has(targetFloor) || sourceFloor === targetFloor) {
      throw new Error(`${path} must connect two existing different floors`);
    }
    if (entityOwner.get(requiredText(value.source_entity_id, `${path}.source_entity_id`)) !== sourceFloor) {
      throw new Error(`${path}.source_entity_id must resolve on source_floor_id`);
    }
    if (entityOwner.get(requiredText(value.target_entity_id, `${path}.target_entity_id`)) !== targetFloor) {
      throw new Error(`${path}.target_entity_id must resolve on target_floor_id`);
    }
  });
}

function emptyConvertedGeometry(): ConvertedGeometry {
  return {
    vertices: {}, walls: {}, rooms: {}, furniture: {}, openings: {}, roads: {}, stairs: {},
    pillars: {}, beams: {}, deckSlabs: {}, railings: {}, annotations: {},
  };
}

function finishId(raw: unknown, category: FinishCategory, fallback: string, path: string, warnings: string[]): string {
  const id = typeof raw === 'string' && raw ? raw : fallback;
  if (categoryOf(id) === category) return id;
  warnings.push(`${path}: finish '${id}' is unavailable or incompatible; used '${fallback}'`);
  return fallback;
}

function v2North(layout: ValidatedV2Layout): number {
  const floor = layout.floors.find((candidate) => candidate.id === layout.active_floor_id);
  const geometry = isObject(floor?.geometry) ? floor.geometry : {};
  const canvas = isObject(geometry.canvas) ? geometry.canvas : undefined;
  const compass = isObject(layout.compass)
    ? layout.compass
    : isObject(geometry.compass)
      ? geometry.compass
      : isObject(canvas?.compass)
        ? canvas.compass
        : undefined;
  if (!compass) return 0;
  if (compass.north_deg_clockwise != null) return ((Number(compass.north_deg_clockwise) % 360) + 360) % 360;
  return DIRECTION_TO_DEG[String(compass.direction ?? '').toUpperCase()] ?? 0;
}

function shiftProjectOrigin(geometryByFloor: Record<EntityId, FloorGeometry>): void {
  const points: Point2D[] = [];
  for (const geometry of Object.values(geometryByFloor)) {
    points.push(
      ...Object.values(geometry.vertices).map((item) => item.position),
      ...Object.values(geometry.furniture).map((item) => item.position),
      ...Object.values(geometry.annotations).map((item) => item.position),
      ...Object.values(geometry.pillars).map((item) => item.position),
      ...Object.values(geometry.beams).flatMap((item) => [item.start, item.end]),
      ...Object.values(geometry.deckSlabs).flatMap((item) => item.polygon),
      ...Object.values(geometry.railings).flatMap((item) => [item.start, item.end]),
      ...Object.values(geometry.stairs).flatMap((item) => item.pathPoints),
    );
  }
  if (points.length === 0) return;
  const dx = -Math.min(...points.map((point) => point.x));
  const dy = -Math.min(...points.map((point) => point.y));
  const shift = (point: Point2D): Point2D => ({ x: point.x + dx, y: point.y + dy });
  for (const geometry of Object.values(geometryByFloor)) {
    for (const [id, item] of Object.entries(geometry.vertices)) {
      geometry.vertices[id] = { ...item, position: shift(item.position) };
    }
    for (const [id, item] of Object.entries(geometry.furniture)) {
      geometry.furniture[id] = { ...item, position: shift(item.position) };
    }
    for (const [id, item] of Object.entries(geometry.annotations)) {
      geometry.annotations[id] = { ...item, position: shift(item.position) };
    }
    for (const item of Object.values(geometry.pillars)) item.position = shift(item.position);
    for (const item of Object.values(geometry.beams)) { item.start = shift(item.start); item.end = shift(item.end); }
    for (const item of Object.values(geometry.deckSlabs)) item.polygon = item.polygon.map(shift);
    for (const item of Object.values(geometry.railings)) { item.start = shift(item.start); item.end = shift(item.end); }
    for (const [id, item] of Object.entries(geometry.stairs)) {
      geometry.stairs[id] = {
        ...item,
        pathPoints: item.pathPoints.map(shift),
        flights: item.flights.map((flight) => ({
          ...flight, startPoint: shift(flight.startPoint), endPoint: shift(flight.endPoint),
        })),
        landings: item.landings.map((landing) => ({ ...landing, center: shift(landing.center) })),
        stairwellVoid: item.stairwellVoid.map(shift),
      };
    }
  }
}

function applyCanvasFinishOverlays(
  geometry: ConvertedGeometry,
  rawGeometry: RawObject,
  toWorld: (value: unknown, path: string) => Point2D,
  base: string,
  warnings: string[],
): Map<string, string> {
  const rawVertexItems = (rawGeometry.vertices ?? []) as RawObject[];
  const rawVertices = new Map(
    rawVertexItems.map((raw, index) => [
      String(raw.id),
      toWorld(raw.position ?? { x: raw.x, y: raw.y }, `${base}.vertices[${index}].position`),
    ]),
  );
  const idMap = new Map<string, string>();
  rawVertexItems.forEach((raw) => {
    if (raw.source_canvas_id == null) return;
    const point = rawVertices.get(String(raw.id));
    const match = point && Object.values(geometry.vertices).find((vertex) => dist(point, vertex.position) <= VERTEX_SNAP_CM);
    if (match) idMap.set(String(raw.id), match.id);
  });
  const onSegment = (point: Point2D, start: Point2D, end: Point2D) => {
    const length = dist(start, end);
    const offset = lineParam(point, start, end);
    return pointLineDist(point, start, end) <= VERTEX_SNAP_CM &&
      offset >= -VERTEX_SNAP_CM && offset <= length + VERTEX_SNAP_CM;
  };

  ((rawGeometry.walls ?? []) as RawObject[]).forEach((raw, index) => {
    if (raw.source_canvas_id == null) return;
    const start = rawVertices.get(String(raw.start_vertex_id));
    const end = rawVertices.get(String(raw.end_vertex_id));
    if (!start || !end) return;
    for (const [id, wall] of Object.entries(geometry.walls)) {
      const wallStart = geometry.vertices[wall.startVertexId]?.position;
      const wallEnd = geometry.vertices[wall.endVertexId]?.position;
      if (!wallStart || !wallEnd || !onSegment(wallStart, start, end) || !onSegment(wallEnd, start, end)) continue;
      if (!idMap.has(String(raw.id))) idMap.set(String(raw.id), id);
      geometry.walls[id] = {
        ...wall,
        ...(raw.material_id != null ? { materialId: finishId(raw.material_id, 'wall', 'default-wall', `${base}.walls[${index}].material_id`, warnings) } : {}),
        ...(raw.material_side_a != null ? { materialSideA: finishId(raw.material_side_a, 'wall', 'default-wall', `${base}.walls[${index}].material_side_a`, warnings) } : {}),
        ...(raw.material_side_b != null ? { materialSideB: finishId(raw.material_side_b, 'wall', 'default-wall', `${base}.walls[${index}].material_side_b`, warnings) } : {}),
      };
    }
  });

  ((rawGeometry.rooms ?? []) as RawObject[]).forEach((raw, index) => {
    if (raw.source_canvas_id == null || !Array.isArray(raw.boundary_vertex_ids)) return;
    const sourcePoints = raw.boundary_vertex_ids.map((id) => rawVertices.get(String(id))).filter((point): point is Point2D => Boolean(point));
    if (sourcePoints.length < 3) return;
    const room = Object.values(geometry.rooms).find((candidate) => {
      const boundary = candidate.boundaryVertexIds.map((id) => geometry.vertices[id]?.position).filter((point): point is Point2D => Boolean(point));
      return sourcePoints.every((point) => boundary.some((candidatePoint) => dist(point, candidatePoint) <= VERTEX_SNAP_CM));
    });
    if (room) idMap.set(String(raw.id), room.id);
    if (room && (raw.floor_material_id != null || raw.material_id != null)) {
      geometry.rooms[room.id] = {
        ...room,
        floorMaterialId: finishId(raw.floor_material_id ?? raw.material_id, 'floor', 'default-floor', `${base}.rooms[${index}].floor_material_id`, warnings),
      };
    }
  });
  return idMap;
}

function convertV2Layout(layout: RawObject): ConvertResult {
  assertV2Layout(layout);
  const { px2cm, wallHeightCm } = v2Metadata(layout);
  const geometryByFloor: Record<EntityId, FloorGeometry> = {};
  const canonicalIdMap = new Map<string, string>();
  const warnings: string[] = [];
  const unmapped: string[] = [];
  const toWorld = (value: unknown, path: string) => {
    const point = rawPoint(value, path);
    return { x: px2cm(point.x), y: -px2cm(point.y) };
  };

  for (const [floorIndex, floor] of layout.floors.entries()) {
    const rawGeometry = floor.geometry as RawObject;
    const base = `floors[${floorIndex}].geometry`;
    const canvas = isObject(rawGeometry.canvas) ? rawGeometry.canvas : undefined;
    const canvasResult = canvas ? convertV1Layout(canvas, false) : undefined;
    const geometry = canvasResult?.geometry ?? emptyConvertedGeometry();
    if (canvasResult) {
      unmapped.push(...canvasResult.report.unmapped);
      warnings.push(...canvasResult.report.residuals);
    }
    const isMirroredText = (raw: RawObject) =>
      Array.isArray(raw.tags) && raw.tags.map(String).includes('canonical_v2_mirror');
    const collection = (name: typeof V2_COLLECTIONS[number]) => {
      const values = (rawGeometry[name] ?? []) as RawObject[];
      if (!canvas) return values;
      return values.filter((raw) => raw.source_canvas_id == null && !(name === 'text' && isMirroredText(raw)));
    };
    const canvasPx2cm = canvas ? v2Metadata(canvas).px2cm : px2cm;
    const sourceIdMap = canvas
      ? applyCanvasFinishOverlays(
        geometry,
        rawGeometry,
        (value, path) => {
          const point = rawPoint(value, path);
          return { x: canvasPx2cm(point.x), y: -canvasPx2cm(point.y) };
        },
        base,
        warnings,
      )
      : new Map<string, string>();
    sourceIdMap.forEach((value, key) => canonicalIdMap.set(key, value));
    const resolveId = (value: unknown) => sourceIdMap.get(String(value)) ?? String(value);

    for (const [index, raw] of collection('vertices').entries()) {
      const id = String(raw.id);
      geometry.vertices[id] = { id, position: toWorld(raw.position ?? { x: raw.x, y: raw.y }, `${base}.vertices[${index}].position`), connectedWalls: [] };
    }
    for (const [index, raw] of collection('walls').entries()) {
      const id = String(raw.id);
      const materialId = finishId(raw.material_id, 'wall', 'default-wall', `${base}.walls[${index}].material_id`, warnings);
      geometry.walls[id] = {
        id,
        startVertexId: resolveId(raw.start_vertex_id),
        endVertexId: resolveId(raw.end_vertex_id),
        thickness: Number(raw.thickness_cm),
        height: Number(raw.height_cm ?? wallHeightCm),
        materialId,
        ...(raw.material_side_a != null ? { materialSideA: finishId(raw.material_side_a, 'wall', 'default-wall', `${base}.walls[${index}].material_side_a`, warnings) } : {}),
        ...(raw.material_side_b != null ? { materialSideB: finishId(raw.material_side_b, 'wall', 'default-wall', `${base}.walls[${index}].material_side_b`, warnings) } : {}),
        isLoadBearing: Boolean(raw.is_load_bearing ?? false),
        openingIds: ((raw.opening_ids ?? []) as unknown[]).map(resolveId),
      };
      geometry.vertices[resolveId(raw.start_vertex_id)].connectedWalls.push(id);
      geometry.vertices[resolveId(raw.end_vertex_id)].connectedWalls.push(id);
    }
    for (const [index, raw] of collection('rooms').entries()) {
      const id = String(raw.id);
      const roomType = String(raw.room_type ?? labelToRoomType(String(raw.label ?? raw.name ?? 'Room'))) as RoomType;
      geometry.rooms[id] = {
        id,
        boundaryVertexIds: (raw.boundary_vertex_ids as unknown[]).map(resolveId),
        roomType: ROOM_TYPES.has(roomType) ? roomType : 'custom',
        label: String(raw.label ?? raw.name ?? 'Room'),
        floorMaterialId: finishId(raw.floor_material_id ?? raw.material_id, 'floor', 'default-floor', `${base}.rooms[${index}].floor_material_id`, warnings),
        ...(raw.fill_mode != null ? { fillMode: FILL_MODE_MAP[String(raw.fill_mode)] ?? 'filled' } : {}),
        ...(raw.fill_color != null ? { fillColor: String(raw.fill_color) } : {}),
      };
    }
    for (const [index, raw] of collection('openings').entries()) {
      const id = String(raw.id);
      const type = String(raw.type) as Opening['type'];
      const knownKind = getOpeningKind(raw.kind == null ? undefined : String(raw.kind));
      geometry.openings[id] = {
        id,
        wallId: resolveId(raw.wall_id),
        type,
        ...(knownKind ? { kind: knownKind.id } : {}),
        offsetCm: Number(raw.offset_cm),
        width: Number(raw.width_cm),
        height: Number(raw.height_cm),
        elevation: Number(raw.elevation_cm ?? 0),
      };
      const wall = geometry.walls[resolveId(raw.wall_id)];
      if (!wall.openingIds.includes(id)) wall.openingIds.push(id);
      if (raw.kind != null && !knownKind) warnings.push(`${base}.openings[${index}].kind: unknown kind '${String(raw.kind)}' was omitted`);
    }
    for (const [index, raw] of collection('furniture').entries()) {
      const id = String(raw.id);
      const catalogId = String(raw.catalog_id ?? raw.catalogId ?? '');
      const catalog = FURNITURE_CATALOG[catalogId];
      if (!catalog) {
        warnings.push(`${base}.furniture[${index}].catalog_id: unknown furniture '${catalogId}' was skipped`);
        continue;
      }
      const bounds = isObject(raw.bounds) ? raw.bounds : {};
      geometry.furniture[id] = {
        id,
        position: toWorld(raw.position ?? { x: raw.x, y: raw.y }, `${base}.furniture[${index}].position`),
        rotation: raw.rotation_rad != null ? -Number(raw.rotation_rad) : -(Number(raw.angle_deg ?? raw.angle ?? 0) * Math.PI) / 180,
        scale: Number(raw.scale ?? 1),
        catalogId,
        roomId: raw.room_id == null ? null : resolveId(raw.room_id),
        bounds: {
          width: raw.bounds == null ? catalog.bounds.width : Number(bounds.width),
          depth: raw.bounds == null ? catalog.bounds.depth : Number(bounds.depth),
        },
      };
    }
    for (const [index, raw] of collection('text').entries()) {
      const id = String(raw.id);
      geometry.annotations[id] = {
        id,
        position: toWorld(raw.position ?? { x: raw.x, y: raw.y }, `${base}.text[${index}].position`),
        text: String(raw.content ?? raw.text ?? ''),
        fontSizeCm: Number(raw.font_size_cm ?? 15),
        color: String(raw.color ?? '#fde68a'),
        ...(raw.rotation_deg != null ? { rotation: -(Number(raw.rotation_deg) * Math.PI) / 180 } : {}),
      };
    }
    for (const [index, raw] of collection('pillars').entries()) {
      const id = String(raw.id);
      geometry.pillars[id] = {
        id,
        position: toWorld(raw.position, `${base}.pillars[${index}].position`),
        width: Number(raw.width_cm), depth: Number(raw.depth_cm), height: Number(raw.height_cm),
        elevationCm: Number(raw.elevation_cm ?? 0),
        shape: String(raw.shape ?? 'rect') as Pillar['shape'],
        materialId: finishId(raw.material_id, 'wall', 'default-wall', `${base}.pillars[${index}].material_id`, warnings),
      };
    }
    for (const [index, raw] of collection('beams').entries()) {
      const id = String(raw.id);
      geometry.beams[id] = {
        id,
        start: toWorld(raw.start, `${base}.beams[${index}].start`),
        end: toWorld(raw.end, `${base}.beams[${index}].end`),
        width: Number(raw.width_cm), depth: Number(raw.depth_cm), elevationCm: Number(raw.elevation_cm ?? 0),
        materialId: finishId(raw.material_id, 'wall', 'default-wall', `${base}.beams[${index}].material_id`, warnings),
      };
    }
    for (const [index, raw] of collection('deck_slabs').entries()) {
      const id = String(raw.id);
      let polygon = (raw.polygon as unknown[]).map((point, pointIndex) => toWorld(point, `${base}.deck_slabs[${index}].polygon[${pointIndex}]`));
      if (polygon.length > 1 && polygon[0].x === polygon.at(-1)!.x && polygon[0].y === polygon.at(-1)!.y) polygon = polygon.slice(0, -1);
      geometry.deckSlabs[id] = {
        id, polygon, thicknessCm: Number(raw.thickness_cm), elevationCm: Number(raw.elevation_cm ?? 0),
        materialId: finishId(raw.material_id, 'floor', 'default-floor', `${base}.deck_slabs[${index}].material_id`, warnings),
        type: String(raw.type ?? 'custom') as DeckSlab['type'],
      };
    }
    for (const [index, raw] of collection('railings').entries()) {
      const id = String(raw.id);
      geometry.railings[id] = {
        id,
        start: toWorld(raw.start, `${base}.railings[${index}].start`),
        end: toWorld(raw.end, `${base}.railings[${index}].end`),
        height: Number(raw.height_cm), elevationCm: Number(raw.elevation_cm ?? 0),
        style: String(raw.style ?? 'open') as Railing['style'],
        materialId: finishId(raw.material_id, 'wall', 'default-wall', `${base}.railings[${index}].material_id`, warnings),
      };
    }
    for (const [index, raw] of collection('stairs').entries()) {
      const id = String(raw.id);
      const lowerFloorId = String(raw.lower_floor_id);
      const upperFloorId = String(raw.upper_floor_id);
      const lowerFloor = layout.floors.find((candidate) => String(candidate.id) === lowerFloorId)!;
      const upperFloor = layout.floors.find((candidate) => String(candidate.id) === upperFloorId)!;
      const pathPoints = (raw.path_points as unknown[]).map((point, pointIndex) =>
        toWorld(point, `${base}.stairs[${index}].path_points[${pointIndex}]`)
      );
      const built = buildStair(
        pathPoints,
        Number(raw.width_cm),
        Number(upperFloor.elevation_cm) - Number(lowerFloor.elevation_cm),
        lowerFloorId,
        upperFloorId,
        Number(lowerFloor.elevation_cm),
      );
      if (!built.ok) throw new Error(`${base}.stairs[${index}]: ${built.error}`);
      geometry.stairs[id] = { ...built.stair, id } as StairEntity;
    }
    if (collection('shapes').length > 0) warnings.push(`${base}.shapes: canvas-only shapes were skipped`);
    geometryByFloor[String(floor.id)] = geometry;
  }

  // Remove the shared canvas viewport offset once for the whole project. Per-floor
  // normalization would erase the horizontal relationship between storeys.
  shiftProjectOrigin(geometryByFloor);
  const northDeg = v2North(layout);
  const project: ConvertedVastuProject = {
    floors: layout.floors.map((floor) => ({ id: String(floor.id), name: String(floor.name), elevationCm: Number(floor.elevation_cm) })),
    activeFloorId: layout.active_floor_id,
    geometryByFloor,
    crossFloorReferences: layout.cross_floor_references.map((reference) => ({
      id: String(reference.id),
      type: String(reference.type),
      sourceFloorId: String(reference.source_floor_id),
      sourceEntityId: canonicalIdMap.get(String(reference.source_entity_id)) ?? String(reference.source_entity_id),
      targetFloorId: String(reference.target_floor_id),
      targetEntityId: canonicalIdMap.get(String(reference.target_entity_id)) ?? String(reference.target_entity_id),
    })),
    northDeg,
    sunSettings: {
      timeHours: Number(layout.sun_settings.time_hours),
      azimuthDeg: Number(layout.sun_settings.azimuth_deg),
      directionOverride: Boolean(layout.sun_settings.direction_override),
    },
  };
  const allGeometry = Object.values(geometryByFloor);
  const report: ImportReport = {
    rooms: allGeometry.reduce((sum, item) => sum + Object.keys(item.rooms).length, 0),
    walls: allGeometry.reduce((sum, item) => sum + Object.keys(item.walls).length, 0),
    furniture: allGeometry.reduce((sum, item) => sum + Object.keys(item.furniture).length, 0),
    openings: allGeometry.reduce((sum, item) => sum + Object.keys(item.openings).length, 0),
    annotations: allGeometry.reduce((sum, item) => sum + Object.keys(item.annotations).length, 0),
    northDeg,
    unmapped: [...new Set(unmapped)],
    residuals: [...new Set(warnings)],
  };
  return { geometry: geometryByFloor[project.activeFloorId] as ConvertedGeometry, northDeg, report, project };
}
