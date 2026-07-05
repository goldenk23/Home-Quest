// src/domains/editor/services/sampleHall1.ts

import { useAppStore } from '@/store';
import type { RoomType, EntityId, Vertex } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { detectRooms } from './roomDetection';

/**
 * Loads the "Hall-1" hostel campus, recreated from the reference map: seven 3-storey hostel
 * blocks (A–G) arranged in two rows, a central MESS hall, an open (green) area, and a
 * canteen — all connected by a covered pillar-and-beam corridor like the reference photos.
 *
 * Construction strategy (as requested): the base storey of the blocks is drawn once, then
 * replicated upward twice with duplicateFloor() to make each block 3 storeys. The ground
 * floor additionally carries the single-storey MESS, canteen, open area and the corridors.
 *
 * Coordinate system: centimeters, x→right, y→down (matching the map image).
 *
 *   Top row    (y  500–1620): B Block | MESS (y 500–1350) | E Block | G Block
 *   Corridor   (y 1620–1820): main covered walkway spanning x 500–5000
 *   Bottom row (y 1820–2940): A Block | C Block | open area + canteen | D Block | F Block
 */

/** Block footprint width (cm). */
const BW = 400;
/** Top-row blocks span this y range; their south face sits ON the corridor. */
const TOP = { y1: 500, y2: 1620 };
/** Bottom-row blocks; their north face sits ON the corridor. */
const BOT = { y1: 1820, y2: 2940 };
/** Main corridor band. */
const COR = { y1: 1620, y2: 1820, x1: 500, x2: 5000 };
/** Storey height for pillars/beams (cm). */
const H = 300;

interface BlockDef { label: string; x1: number; row: 'top' | 'bottom' }

const BLOCKS: BlockDef[] = [
  { label: 'B Block', x1: 900, row: 'top' },
  { label: 'E Block', x1: 3600, row: 'top' },
  { label: 'G Block', x1: 4600, row: 'top' },
  { label: 'A Block', x1: 400, row: 'bottom' },
  { label: 'C Block', x1: 1300, row: 'bottom' },
  { label: 'D Block', x1: 3600, row: 'bottom' },
  { label: 'F Block', x1: 4600, row: 'bottom' },
];

const MESS = { x1: 2200, y1: 500, x2: 3300, y2: 1350 };
const CANTEEN = { x1: 2050, y1: 2500, x2: 3300, y2: 2950 };
const OPEN_AREA = { x1: 2350, y1: 1900, x2: 3300, y2: 2400 };

export function loadSampleHall1(): void {
  const store = useAppStore.getState();
  store.resetFloors(); // fresh baseline
  store.clearAll();
  const groundFloorId = useAppStore.getState().activeFloorId;

  // ---------------------------------------------------------------------------
  // 1) BASE STOREY OF THE BLOCKS (the part that repeats on every floor).
  // ---------------------------------------------------------------------------
  buildBlocks();
  labelRooms(blockMappingsOnly());
  paintAllWalls();

  // 2) Replicate the base storey upward twice → every block becomes 3 storeys.
  const firstFloorId = useAppStore.getState().duplicateFloor();
  useAppStore.getState().renameFloor(firstFloorId, 'First Floor');
  const secondFloorId = useAppStore.getState().duplicateFloor();
  useAppStore.getState().renameFloor(secondFloorId, 'Second Floor');

  // 3) Back to the ground floor for the single-storey campus fabric.
  useAppStore.getState().setActiveFloor(groundFloorId);
  buildMessAndCanteen();
  buildCorridors();

  // Re-detect (mess/canteen walls were added) and label everything on the ground floor.
  labelRooms([...blockMappingsOnly(), ...groundOnlyMappings()]);
  paintAllWalls();

  useAppStore.getState().clearHistory();
  useAppStore.getState().requestFitView();
}

// ---------------------------------------------------------------------------
// Blocks (repeated storey)
// ---------------------------------------------------------------------------

function buildBlocks(): void {
  const { addWall, addOpening } = useAppStore.getState();
  const W = (x1: number, y1: number, x2: number, y2: number) =>
    addWall({ x: x1, y: y1 }, { x: x2, y: y2 });

  for (const b of BLOCKS) {
    const x1 = b.x1, x2 = b.x1 + BW;
    const { y1, y2 } = b.row === 'top' ? TOP : BOT;

    const north = W(x1, y1, x2, y1);
    const east = W(x2, y1, x2, y2);
    const south = W(x1, y2, x2, y2);
    const west = W(x1, y1, x1, y2);

    // Entrance door on the corridor-facing wall, centered.
    const entryWall = b.row === 'top' ? south : north;
    addOpening({ wallId: entryWall, type: 'door', offsetCm: (BW - 90) / 2, width: 90, height: 210, elevation: 0 });

    // Windows on both long side walls (the block facades) + one on the outer short wall.
    for (const wall of [east, west]) {
      addOpening({ wallId: wall, type: 'window', offsetCm: 220, width: 120, height: 130, elevation: 90 });
      addOpening({ wallId: wall, type: 'window', offsetCm: 660, width: 120, height: 130, elevation: 90 });
    }
    const outerWall = b.row === 'top' ? north : south;
    addOpening({ wallId: outerWall, type: 'window', offsetCm: (BW - 140) / 2, width: 140, height: 130, elevation: 90 });
  }
}

// ---------------------------------------------------------------------------
// Mess + canteen (ground floor only)
// ---------------------------------------------------------------------------

function buildMessAndCanteen(): void {
  const { addWall, addOpening } = useAppStore.getState();
  const W = (x1: number, y1: number, x2: number, y2: number) =>
    addWall({ x: x1, y: y1 }, { x: x2, y: y2 });

  // MESS: large hall, main door on the south wall (facing its corridor stub).
  const m = MESS;
  const mNorth = W(m.x1, m.y1, m.x2, m.y1);
  const mEast = W(m.x2, m.y1, m.x2, m.y2);
  const mSouth = W(m.x1, m.y2, m.x2, m.y2);
  const mWest = W(m.x1, m.y1, m.x1, m.y2);
  addOpening({ wallId: mSouth, type: 'door', offsetCm: (m.x2 - m.x1 - 160) / 2, width: 160, height: 220, elevation: 0 });
  addOpening({ wallId: mNorth, type: 'window', offsetCm: 200, width: 160, height: 140, elevation: 90 });
  addOpening({ wallId: mNorth, type: 'window', offsetCm: 700, width: 160, height: 140, elevation: 90 });
  addOpening({ wallId: mEast, type: 'window', offsetCm: 340, width: 140, height: 140, elevation: 90 });
  addOpening({ wallId: mWest, type: 'window', offsetCm: 340, width: 140, height: 140, elevation: 90 });

  // Canteen: door on the north wall near its corridor stub (west end).
  const c = CANTEEN;
  const cNorth = W(c.x1, c.y1, c.x2, c.y1);
  const cEast = W(c.x2, c.y1, c.x2, c.y2);
  const cSouth = W(c.x1, c.y2, c.x2, c.y2);
  W(c.x1, c.y1, c.x1, c.y2); // west wall
  addOpening({ wallId: cNorth, type: 'door', offsetCm: 60, width: 100, height: 210, elevation: 0 });
  addOpening({ wallId: cSouth, type: 'window', offsetCm: 260, width: 160, height: 130, elevation: 90 });
  addOpening({ wallId: cSouth, type: 'window', offsetCm: 820, width: 160, height: 130, elevation: 90 });
  addOpening({ wallId: cEast, type: 'window', offsetCm: 160, width: 120, height: 130, elevation: 90 });
}

// ---------------------------------------------------------------------------
// Covered corridors: floor slab + pillar rows + beams + roof slab
// ---------------------------------------------------------------------------

function buildCorridors(): void {
  const s = useAppStore.getState();

  const rect = (x1: number, y1: number, x2: number, y2: number): Point2D[] => [
    { x: x1, y: y1 }, { x: x2, y: y1 }, { x: x2, y: y2 }, { x: x1, y: y2 },
  ];

  // Corridor floor + roof slabs. Main east–west walkway plus the two stubs that reach the
  // MESS (north) and the canteen (south, alongside the open area) — mirroring the map.
  const corridors: { poly: Point2D[] }[] = [
    { poly: rect(COR.x1, COR.y1, COR.x2, COR.y2) },              // main walkway
    { poly: rect(2650, MESS.y2, 2850, COR.y1) },                 // stub → MESS
    { poly: rect(CANTEEN.x1, COR.y2, CANTEEN.x1 + 200, CANTEEN.y1) }, // stub → canteen
  ];
  for (const c of corridors) {
    s.addDeckSlab({ polygon: c.poly, thicknessCm: 12, elevationCm: 0, materialId: 'floor-ceramic', type: 'corridor' });
    s.addDeckSlab({ polygon: c.poly, thicknessCm: 12, elevationCm: H, materialId: 'floor-vinyl', type: 'roof' });
  }

  // Open (green) area between the corridor and the canteen.
  s.addDeckSlab({
    polygon: rect(OPEN_AREA.x1, OPEN_AREA.y1, OPEN_AREA.x2, OPEN_AREA.y2),
    thicknessCm: 8, elevationCm: 0, materialId: 'floor-mat', type: 'custom',
  });

  const pillar = (x: number, y: number) =>
    s.addPillar({ position: { x, y }, width: 30, depth: 30, height: H, elevationCm: 0, shape: 'rect', materialId: 'paint-white' });
  const beam = (x1: number, y1: number, x2: number, y2: number) =>
    s.addBeam({ start: { x: x1, y: y1 }, end: { x: x2, y: y2 }, width: 20, depth: 30, elevationCm: H - 30, materialId: 'paint-white' });

  // Main walkway: two pillar rows (15cm inside each slab edge) with a beam running along
  // the top of each row — the covered-corridor rhythm from the reference photo.
  const rowN = COR.y1 + 15, rowS = COR.y2 - 15;
  for (let x = COR.x1 + 25; x <= COR.x2 - 25; x += 300) {
    pillar(x, rowN);
    pillar(x, rowS);
  }
  beam(COR.x1, rowN, COR.x2, rowN);
  beam(COR.x1, rowS, COR.x2, rowS);

  // Stub → MESS: pillar pairs down both edges + beams.
  for (const y of [MESS.y2 + 60, MESS.y2 + 180]) {
    pillar(2665, y);
    pillar(2835, y);
  }
  beam(2665, MESS.y2, 2665, COR.y1);
  beam(2835, MESS.y2, 2835, COR.y1);

  // Stub → canteen.
  const sx1 = CANTEEN.x1 + 15, sx2 = CANTEEN.x1 + 185;
  for (let y = COR.y2 + 80; y < CANTEEN.y1 - 20; y += 220) {
    pillar(sx1, y);
    pillar(sx2, y);
  }
  beam(sx1, COR.y2, sx1, CANTEEN.y1);
  beam(sx2, COR.y2, sx2, CANTEEN.y1);
}

// ---------------------------------------------------------------------------
// Room detection + labelling
// ---------------------------------------------------------------------------

interface RoomMapping { cx: number; cy: number; label: string; type: RoomType; floor: string }

function blockMappingsOnly(): RoomMapping[] {
  return BLOCKS.map((b) => {
    const { y1, y2 } = b.row === 'top' ? TOP : BOT;
    return {
      cx: b.x1 + BW / 2,
      cy: (y1 + y2) / 2,
      label: b.label,
      type: 'bedroom' as RoomType,
      floor: 'floor-ceramic',
    };
  });
}

function groundOnlyMappings(): RoomMapping[] {
  return [
    { cx: (MESS.x1 + MESS.x2) / 2, cy: (MESS.y1 + MESS.y2) / 2, label: 'Mess', type: 'living', floor: 'floor-checker' },
    { cx: (CANTEEN.x1 + CANTEEN.x2) / 2, cy: (CANTEEN.y1 + CANTEEN.y2) / 2, label: 'Canteen', type: 'kitchen', floor: 'floor-vitrified' },
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

function paintAllWalls(): void {
  const s = useAppStore.getState();
  for (const wallId of Object.keys(s.walls)) {
    s.updateWall(wallId, { materialId: 'wall-plaster' });
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
