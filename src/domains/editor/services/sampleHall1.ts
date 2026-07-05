// src/domains/editor/services/sampleHall1.ts

import { useAppStore } from '@/store';
import type { RoomType, EntityId, Vertex } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { detectRooms } from './roomDetection';
import { buildStair } from './stairBuilder';

/**
 * "Hall-1" hostel campus, recreated from the reference map + facade photos:
 *
 * - Seven 3-storey hostel blocks (A–G), each a long rectangle of N_ROOMS equal rooms with a
 *   blue door opening onto an open GALLERY CORRIDOR that runs along the block's front
 *   face on EVERY floor (cream pillars, maroon solid railing panels — like the photos).
 * - The central MESS hall (with the campus centered on it), the canteen, and the open
 *   (green) area, connected by covered walkway stubs.
 * - A main east–west corridor between the two block rows at BOTH ground and first floor
 *   (a two-level bridge like the night photo), with staircases connecting ground → first
 *   at the corridor and first → second inside two block galleries.
 * - A compound boundary (solid parapet) around the whole hall with a main gate + posts
 *   at the south, and a paved path from the gate into campus.
 *
 * Construction strategy: the block storey (rooms + gallery slab/pillars/beams/railings)
 * is drawn once and replicated upward twice with duplicateFloor(). Everything single- or
 * two-storey (mess, canteen, corridors, boundary, stairs) is added afterwards per floor.
 *
 * Coordinates: centimeters, x→right, y→down (same orientation as the map image).
 */

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

/** Room size: 300cm wide along the block length × 450cm deep. */
const ROOM_W = 300;
const ROOM_D = 450;
/** Rooms per block (equal split along the length). */
const N_ROOMS = 12;
/** Block length. */
const BLOCK_L = N_ROOMS * ROOM_W;
/** Gallery corridor width along the block front face. */
const GAL_W = 200;
/** Storey height. */
const H = 300;

/** Row bands: block length runs along y. The main corridor separates the rows. */
const TOP = { y1: 700, y2: 700 + BLOCK_L };
const BOT = { y1: TOP.y2 + 200, y2: TOP.y2 + 200 + BLOCK_L };
/** Main east–west corridor band between the rows (both ground + first floor). */
const COR = { y1: TOP.y2, y2: BOT.y1, x1: 950, x2: 6050 };

interface BlockDef {
  letter: string;
  /** West edge of the room strip. */
  rx1: number;
  row: 'top' | 'bottom';
  /** Which side the gallery corridor (front face) is on. */
  front: 'east' | 'west';
}

const BLOCKS: BlockDef[] = [
  { letter: 'A', rx1: 500, row: 'bottom', front: 'east' },
  { letter: 'B', rx1: 1600, row: 'top', front: 'east' },
  { letter: 'C', rx1: 1600, row: 'bottom', front: 'east' },
  { letter: 'E', rx1: 4950, row: 'top', front: 'west' },
  { letter: 'D', rx1: 4950, row: 'bottom', front: 'west' },
  { letter: 'G', rx1: 6050, row: 'top', front: 'west' },
  { letter: 'F', rx1: 6050, row: 'bottom', front: 'west' },
];

// Campus rectangles are anchored to the row bands so the layout scales with N_ROOMS.
const MESS = { x1: 2700, y1: TOP.y1 + 300, x2: 4300, y2: TOP.y1 + 2300 };
const CANTEEN = { x1: 2800, y1: BOT.y1 + 1500, x2: 4200, y2: BOT.y1 + 2700 };
const OPEN_AREA = { x1: 3300, y1: BOT.y1 + 300, x2: 4200, y2: BOT.y1 + 1200 };
/** Compound boundary (solid parapet railings — not walls, so no giant room is detected). */
const BOUND = { x1: 200, y1: 300, x2: 6800, y2: BOT.y2 + 700 };
/** Main gate gap in the south boundary. */
const GATE = { x1: 3300, x2: 3700 };

/** Colors matched to the facade photos. */
const C_STRUCTURE = 'paint-cream'; // cream concrete frame + walls
const C_PANEL = 'paint-rust';      // maroon railing panels
const F_GALLERY = 'floor-ceramic';
const F_ROOM = 'floor-vitrified';

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export function loadSampleHall1(): void {
  const store = useAppStore.getState();
  store.resetFloors();
  store.clearAll();
  const groundId = useAppStore.getState().activeFloorId;

  // 1) Base storey: the seven blocks with their front gallery corridors.
  const groundGalleryRailings = buildBlockStorey();
  labelRooms(blockRoomMappings());
  paintWalls(C_STRUCTURE);

  // 2) Replicate the storey upward twice — galleries repeat on every floor.
  const firstId = useAppStore.getState().duplicateFloor();
  useAppStore.getState().renameFloor(firstId, 'First Floor');
  const secondId = useAppStore.getState().duplicateFloor();
  useAppStore.getState().renameFloor(secondId, 'Second Floor');

  // 3) Second floor: roof slabs over the open galleries (top of the building).
  addGalleryRoofs();

  // 4) Ground floor: open colonnade (photo shows no panels at ground), campus fabric.
  useAppStore.getState().setActiveFloor(groundId);
  for (const id of groundGalleryRailings) useAppStore.getState().removeRailing(id);
  buildMessAndCanteen();
  buildGroundCorridors();
  buildBoundaryAndGate();
  addStairPair(groundId, firstId, 0);
  labelRooms([...blockRoomMappings(), ...groundMappings()]);
  paintWalls(C_STRUCTURE);

  // 5) First floor: the corridor bridge deck + stairs up to the second floor.
  useAppStore.getState().setActiveFloor(firstId);
  buildFirstFloorBridge();
  addUpperStairs(firstId, secondId);

  useAppStore.getState().setActiveFloor(groundId);
  useAppStore.getState().clearHistory();
  useAppStore.getState().requestFitView();
}

// ---------------------------------------------------------------------------
// Blocks: N_ROOMS rooms + front gallery corridor (the storey that repeats)
// ---------------------------------------------------------------------------

/** Returns the gallery railing ids so the caller can strip them from the ground floor. */
function buildBlockStorey(): EntityId[] {
  const s = useAppStore.getState();
  const railingIds: EntityId[] = [];

  for (const b of BLOCKS) {
    const { y1 } = b.row === 'top' ? TOP : BOT;
    const rx2 = b.rx1 + ROOM_D;
    // Front (gallery side) x and back x of the room strip.
    const fx = b.front === 'east' ? rx2 : b.rx1;
    const bx = b.front === 'east' ? b.rx1 : rx2;
    // Gallery strip.
    const gx1 = b.front === 'east' ? rx2 : b.rx1 - GAL_W;
    const gx2 = gx1 + GAL_W;
    // Outer gallery edge (colonnade line), inset 15cm.
    const colX = b.front === 'east' ? gx2 - 15 : gx1 + 15;

    // --- Room strip walls. Long walls are built as N_ROOMS segments so partitions share
    // vertices with them (required for room detection).
    for (let i = 0; i < N_ROOMS; i++) {
      const ys = y1 + i * ROOM_W;
      const ye = ys + ROOM_W;
      const frontSeg = s.addWall({ x: fx, y: ys }, { x: fx, y: ye });
      const backSeg = s.addWall({ x: bx, y: ys }, { x: bx, y: ye });
      // Blue room door onto the gallery + window on the back facade.
      s.addOpening({ wallId: frontSeg, type: 'door', kind: 'door-room-blue', offsetCm: (ROOM_W - 90) / 2, width: 90, height: 210, elevation: 0 });
      s.addOpening({ wallId: backSeg, type: 'window', kind: 'window-standard', offsetCm: (ROOM_W - 120) / 2, width: 120, height: 120, elevation: 90 });
    }
    // End walls + the interior partitions.
    s.addWall({ x: bx, y: y1 }, { x: fx, y: y1 });
    s.addWall({ x: bx, y: y1 + BLOCK_L }, { x: fx, y: y1 + BLOCK_L });
    for (let i = 1; i < N_ROOMS; i++) {
      const y = y1 + i * ROOM_W;
      s.addWall({ x: bx, y }, { x: fx, y });
    }

    // --- Gallery corridor: floor slab + colonnade pillars + edge beam + maroon railing.
    s.addDeckSlab({
      polygon: [
        { x: gx1, y: y1 }, { x: gx2, y: y1 },
        { x: gx2, y: y1 + BLOCK_L }, { x: gx1, y: y1 + BLOCK_L },
      ],
      thicknessCm: 12, elevationCm: 0, materialId: F_GALLERY, type: 'corridor',
    });
    // Cream pillars every 2 rooms (600cm bay rhythm, like the facade photo).
    for (let y = y1; y <= y1 + BLOCK_L; y += 2 * ROOM_W) {
      s.addPillar({ position: { x: colX, y }, width: 30, depth: 30, height: H, elevationCm: 0, shape: 'rect', materialId: C_STRUCTURE });
    }
    // Edge beam along the colonnade top.
    s.addBeam({ start: { x: colX, y: y1 }, end: { x: colX, y: y1 + BLOCK_L }, width: 22, depth: 35, elevationCm: H - 35, materialId: C_STRUCTURE });
    // Maroon solid railing panel along the open edge (removed on the ground floor).
    railingIds.push(
      s.addRailing({ start: { x: colX, y: y1 }, end: { x: colX, y: y1 + BLOCK_L }, height: 90, elevationCm: 0, style: 'solid', materialId: C_PANEL }),
    );
  }

  return railingIds;
}

/** Roof slabs over every gallery, added on the (top) second floor. */
function addGalleryRoofs(): void {
  const s = useAppStore.getState();
  for (const b of BLOCKS) {
    const { y1 } = b.row === 'top' ? TOP : BOT;
    const gx1 = b.front === 'east' ? b.rx1 + ROOM_D : b.rx1 - GAL_W;
    s.addDeckSlab({
      polygon: [
        { x: gx1, y: y1 }, { x: gx1 + GAL_W, y: y1 },
        { x: gx1 + GAL_W, y: y1 + BLOCK_L }, { x: gx1, y: y1 + BLOCK_L },
      ],
      thicknessCm: 12, elevationCm: H, materialId: 'floor-vinyl', type: 'roof',
    });
  }
}

// ---------------------------------------------------------------------------
// Mess + canteen (single storey, ground only)
// ---------------------------------------------------------------------------

function buildMessAndCanteen(): void {
  const s = useAppStore.getState();
  const W = (x1: number, y1: number, x2: number, y2: number) =>
    s.addWall({ x: x1, y: y1 }, { x: x2, y: y2 });

  // MESS: large central hall; double door on the south wall facing its walkway stub.
  const m = MESS;
  const mNorth = W(m.x1, m.y1, m.x2, m.y1);
  const mEast = W(m.x2, m.y1, m.x2, m.y2);
  const mSouth = W(m.x1, m.y2, m.x2, m.y2);
  const mWest = W(m.x1, m.y1, m.x1, m.y2);
  s.addOpening({ wallId: mSouth, type: 'door', kind: 'door-double', offsetCm: (m.x2 - m.x1 - 150) / 2, width: 150, height: 215, elevation: 0 });
  for (const off of [250, 700, 1150]) {
    s.addOpening({ wallId: mNorth, type: 'window', kind: 'window-large', offsetCm: off, width: 220, height: 150, elevation: 75 });
  }
  s.addOpening({ wallId: mEast, type: 'window', kind: 'window-sliding', offsetCm: 900, width: 180, height: 130, elevation: 85 });
  s.addOpening({ wallId: mWest, type: 'window', kind: 'window-sliding', offsetCm: 900, width: 180, height: 130, elevation: 85 });

  // Canteen: door on the north wall near its walkway stub.
  const c = CANTEEN;
  const cNorth = W(c.x1, c.y1, c.x2, c.y1);
  const cEast = W(c.x2, c.y1, c.x2, c.y2);
  const cSouth = W(c.x1, c.y2, c.x2, c.y2);
  W(c.x1, c.y1, c.x1, c.y2);
  s.addOpening({ wallId: cNorth, type: 'door', kind: 'door-standard', offsetCm: 150, width: 100, height: 210, elevation: 0 });
  s.addOpening({ wallId: cSouth, type: 'window', kind: 'window-sliding', offsetCm: 300, width: 180, height: 130, elevation: 85 });
  s.addOpening({ wallId: cSouth, type: 'window', kind: 'window-sliding', offsetCm: 900, width: 180, height: 130, elevation: 85 });
  s.addOpening({ wallId: cEast, type: 'window', kind: 'window-standard', offsetCm: 500, width: 120, height: 120, elevation: 90 });
}

// ---------------------------------------------------------------------------
// Ground corridors, boundary, gate
// ---------------------------------------------------------------------------

const rect = (x1: number, y1: number, x2: number, y2: number): Point2D[] => [
  { x: x1, y: y1 }, { x: x2, y: y1 }, { x: x2, y: y2 }, { x: x1, y: y2 },
];

function buildGroundCorridors(): void {
  const s = useAppStore.getState();
  const pillar = (x: number, y: number) =>
    s.addPillar({ position: { x, y }, width: 30, depth: 30, height: H, elevationCm: 0, shape: 'rect', materialId: C_STRUCTURE });
  const beam = (x1: number, y1: number, x2: number, y2: number) =>
    s.addBeam({ start: { x: x1, y: y1 }, end: { x: x2, y: y2 }, width: 22, depth: 35, elevationCm: H - 35, materialId: C_STRUCTURE });

  // Main corridor, ground level: floor slab + pillar rows on both edges. The first-floor
  // bridge deck (added later) is its roof, exactly like the night photo.
  s.addDeckSlab({ polygon: rect(COR.x1, COR.y1, COR.x2, COR.y2), thicknessCm: 12, elevationCm: 0, materialId: F_GALLERY, type: 'corridor' });
  const rowN = COR.y1 + 15, rowS = COR.y2 - 15;
  for (let x = COR.x1 + 25; x <= COR.x2 - 25; x += 600) {
    pillar(x, rowN);
    pillar(x, rowS);
  }
  beam(COR.x1, rowN, COR.x2, rowN);
  beam(COR.x1, rowS, COR.x2, rowS);

  // Covered stub: main corridor → MESS door (single storey, with its own roof).
  const ms = { x1: 3400, x2: 3600, y1: MESS.y2, y2: COR.y1 };
  s.addDeckSlab({ polygon: rect(ms.x1, ms.y1, ms.x2, ms.y2), thicknessCm: 12, elevationCm: 0, materialId: F_GALLERY, type: 'corridor' });
  s.addDeckSlab({ polygon: rect(ms.x1, ms.y1, ms.x2, ms.y2), thicknessCm: 12, elevationCm: H, materialId: 'floor-vinyl', type: 'roof' });
  for (let y = ms.y1 + 60; y < ms.y2; y += 600) {
    pillar(ms.x1 + 15, y);
    pillar(ms.x2 - 15, y);
  }
  beam(ms.x1 + 15, ms.y1, ms.x1 + 15, ms.y2);
  beam(ms.x2 - 15, ms.y1, ms.x2 - 15, ms.y2);

  // Covered stub: main corridor → canteen door, alongside the open area.
  const cs = { x1: 2900, x2: 3100, y1: COR.y2, y2: CANTEEN.y1 };
  s.addDeckSlab({ polygon: rect(cs.x1, cs.y1, cs.x2, cs.y2), thicknessCm: 12, elevationCm: 0, materialId: F_GALLERY, type: 'corridor' });
  s.addDeckSlab({ polygon: rect(cs.x1, cs.y1, cs.x2, cs.y2), thicknessCm: 12, elevationCm: H, materialId: 'floor-vinyl', type: 'roof' });
  for (let y = cs.y1 + 60; y < cs.y2; y += 600) {
    pillar(cs.x1 + 15, y);
    pillar(cs.x2 - 15, y);
  }
  beam(cs.x1 + 15, cs.y1, cs.x1 + 15, cs.y2);
  beam(cs.x2 - 15, cs.y1, cs.x2 - 15, cs.y2);

  // Open (green) area next to the canteen stub.
  s.addDeckSlab({ polygon: rect(OPEN_AREA.x1, OPEN_AREA.y1, OPEN_AREA.x2, OPEN_AREA.y2), thicknessCm: 8, elevationCm: 0, materialId: 'floor-mat', type: 'custom' });

  // Paved path: main gate → canteen.
  s.addDeckSlab({ polygon: rect(3350, CANTEEN.y2, 3650, BOUND.y2), thicknessCm: 8, elevationCm: 0, materialId: 'floor-sandstone', type: 'custom' });
}

/**
 * Compound boundary as solid parapet railings (not walls — a closed wall loop would be
 * detected as one giant room). The main gate is a gap in the south run with two posts.
 */
function buildBoundaryAndGate(): void {
  const s = useAppStore.getState();
  const parapet = (x1: number, y1: number, x2: number, y2: number) =>
    s.addRailing({ start: { x: x1, y: y1 }, end: { x: x2, y: y2 }, height: 220, elevationCm: 0, style: 'solid', materialId: C_STRUCTURE });

  parapet(BOUND.x1, BOUND.y1, BOUND.x2, BOUND.y1);            // north
  parapet(BOUND.x2, BOUND.y1, BOUND.x2, BOUND.y2);            // east
  parapet(BOUND.x1, BOUND.y1, BOUND.x1, BOUND.y2);            // west
  parapet(BOUND.x1, BOUND.y2, GATE.x1, BOUND.y2);             // south, left of gate
  parapet(GATE.x2, BOUND.y2, BOUND.x2, BOUND.y2);             // south, right of gate

  // Gate posts.
  for (const x of [GATE.x1, GATE.x2]) {
    s.addPillar({ position: { x, y: BOUND.y2 }, width: 45, depth: 45, height: 270, elevationCm: 0, shape: 'rect', materialId: C_STRUCTURE });
  }
}

// ---------------------------------------------------------------------------
// First-floor corridor bridge + staircases
// ---------------------------------------------------------------------------

/** Bridge deck at first-floor level: slab, maroon railings, pillars, and its roof. */
function buildFirstFloorBridge(): void {
  const s = useAppStore.getState();
  s.addDeckSlab({ polygon: rect(COR.x1, COR.y1, COR.x2, COR.y2), thicknessCm: 15, elevationCm: 0, materialId: F_GALLERY, type: 'corridor' });
  const rowN = COR.y1 + 15, rowS = COR.y2 - 15;
  s.addRailing({ start: { x: COR.x1, y: rowN }, end: { x: COR.x2, y: rowN }, height: 90, elevationCm: 0, style: 'solid', materialId: C_PANEL });
  s.addRailing({ start: { x: COR.x1, y: rowS }, end: { x: COR.x2, y: rowS }, height: 90, elevationCm: 0, style: 'solid', materialId: C_PANEL });
  for (let x = COR.x1 + 25; x <= COR.x2 - 25; x += 600) {
    s.addPillar({ position: { x, y: rowN }, width: 30, depth: 30, height: H, elevationCm: 0, shape: 'rect', materialId: C_STRUCTURE });
    s.addPillar({ position: { x, y: rowS }, width: 30, depth: 30, height: H, elevationCm: 0, shape: 'rect', materialId: C_STRUCTURE });
  }
  s.addBeam({ start: { x: COR.x1, y: rowN }, end: { x: COR.x2, y: rowN }, width: 22, depth: 35, elevationCm: H - 35, materialId: C_STRUCTURE });
  s.addBeam({ start: { x: COR.x1, y: rowS }, end: { x: COR.x2, y: rowS }, width: 22, depth: 35, elevationCm: H - 35, materialId: C_STRUCTURE });
  s.addDeckSlab({ polygon: rect(COR.x1, COR.y1, COR.x2, COR.y2), thicknessCm: 12, elevationCm: H, materialId: 'floor-vinyl', type: 'roof' });
}

/** Two straight staircases inside the main corridor band: ground → first floor. */
function addStairPair(lowerId: EntityId, upperId: EntityId, lowerElevationCm: number): void {
  const s = useAppStore.getState();
  const yMid = (COR.y1 + COR.y2) / 2;
  const runs: [Point2D, Point2D][] = [
    [{ x: 1500, y: yMid }, { x: 2050, y: yMid }],
    [{ x: 4950, y: yMid }, { x: 5500, y: yMid }],
  ];
  for (const [a, b] of runs) {
    const result = buildStair([a, b], 120, H, lowerId, upperId, lowerElevationCm);
    if (result.ok) s.addStair(result.stair);
  }
}

/** Two staircases inside block galleries: first → second floor (stored on first floor). */
function addUpperStairs(firstId: EntityId, secondId: EntityId): void {
  const s = useAppStore.getState();
  const runs: [Point2D, Point2D][] = [
    // B block gallery (top row, east gallery: x 2050–2250).
    [{ x: 2150, y: TOP.y1 + 500 }, { x: 2150, y: TOP.y1 + 1050 }],
    // D block gallery (bottom row, west gallery: x 4750–4950).
    [{ x: 4850, y: BOT.y1 + 500 }, { x: 4850, y: BOT.y1 + 1050 }],
  ];
  for (const [a, b] of runs) {
    const result = buildStair([a, b], 110, H, firstId, secondId, H);
    if (result.ok) s.addStair(result.stair);
  }
}

// ---------------------------------------------------------------------------
// Room labelling + painting
// ---------------------------------------------------------------------------

interface RoomMapping { cx: number; cy: number; label: string; type: RoomType; floor: string }

/** One mapping per room per block: "A-01" … "G-{N_ROOMS}". */
function blockRoomMappings(): RoomMapping[] {
  const mappings: RoomMapping[] = [];
  for (const b of BLOCKS) {
    const { y1 } = b.row === 'top' ? TOP : BOT;
    const cx = b.rx1 + ROOM_D / 2;
    for (let i = 0; i < N_ROOMS; i++) {
      mappings.push({
        cx,
        cy: y1 + i * ROOM_W + ROOM_W / 2,
        label: `${b.letter}-${String(i + 1).padStart(2, '0')}`,
        type: 'bedroom',
        floor: F_ROOM,
      });
    }
  }
  return mappings;
}

function groundMappings(): RoomMapping[] {
  return [
    { cx: (MESS.x1 + MESS.x2) / 2, cy: (MESS.y1 + MESS.y2) / 2, label: 'Mess', type: 'living', floor: 'floor-checker' },
    { cx: (CANTEEN.x1 + CANTEEN.x2) / 2, cy: (CANTEEN.y1 + CANTEEN.y2) / 2, label: 'Canteen', type: 'kitchen', floor: F_ROOM },
  ];
}

function labelRooms(mappings: RoomMapping[]): void {
  const fresh = useAppStore.getState();
  const detected = detectRooms(fresh.vertices, fresh.walls);
  const nextRooms: Record<string, typeof detected[number]> = {};
  for (const room of detected) {
    const c = centroidOfIds(room.boundaryVertexIds, fresh.vertices);
    let best = mappings[0];
    let minD = Infinity;
    for (const m of mappings) {
      const dist = Math.hypot(c.x - m.cx, c.y - m.cy);
      if (dist < minD) { minD = dist; best = m; }
    }
    nextRooms[room.id] = { ...room, roomType: best.type, label: best.label, floorMaterialId: best.floor };
  }
  fresh.setRooms(nextRooms);
}

function paintWalls(materialId: string): void {
  const s = useAppStore.getState();
  for (const wallId of Object.keys(s.walls)) {
    s.updateWall(wallId, { materialId });
  }
}

function centroidOfIds(ids: readonly EntityId[], vertices: Record<EntityId, Vertex>): Point2D {
  let x = 0, y = 0, n = 0;
  for (const id of ids) {
    const p = vertices[id]?.position;
    if (p) { x += p.x; y += p.y; n++; }
  }
  return n ? { x: x / n, y: y / n } : { x: 0, y: 0 };
}
