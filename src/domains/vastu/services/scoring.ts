// src/domains/vastu/services/scoring.ts

import type { Room, RoomType } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { type VastuDirection } from './zones';
import { computeSignedArea } from '@/domains/editor/services/roomDetection';

export interface VastuScore {
  readonly overall: number; // 0-100
  readonly roomScores: Record<string, RoomVastuScore>;
  readonly recommendations: VastuRecommendation[];
}

export interface RoomVastuScore {
  readonly roomId: string;
  readonly roomType: RoomType;
  readonly direction: VastuDirection | 'CENTER';
  readonly score: number;
  readonly isIdeal: boolean;
  readonly idealDirections: VastuDirection[];
  readonly reason: string;
}

/** Human-readable full names for clearer suggestions. */
export const DIR_NAME: Record<VastuDirection, string> = {
  N: 'North',
  NE: 'North-East (Ishanya)',
  E: 'East',
  SE: 'South-East (Agneya)',
  S: 'South',
  SW: 'South-West (Nairutya)',
  W: 'West',
  NW: 'North-West (Vayavya)',
};

export const ROOM_NAME: Record<RoomType, string> = {
  living: 'Living room',
  bedroom: 'Bedroom',
  kitchen: 'Kitchen',
  bathroom: 'Bathroom/Toilet',
  puja: 'Puja (prayer) room',
  study: 'Study',
  dining: 'Dining room',
  storage: 'Storage',
  garage: 'Garage',
  balcony: 'Balcony',
  entrance: 'Main entrance',
  corridor: 'Corridor',
  custom: 'Room',
};

function dirLabel(d: VastuDirection[]): string {
  return d.map((x) => DIR_NAME[x]).join(', ');
}

export interface VastuRecommendation {
  readonly severity: 'critical' | 'warning' | 'suggestion';
  readonly roomId: string;
  readonly message: string;
}

/**
 * Ideal / acceptable / adverse placements per room type.
 *
 * Sourced from traditional Vastu Shastra (the Vastu Purusha Mandala) as documented in
 * standard references — e.g. the principle that the kitchen (Agni/fire) belongs in the
 * South-East (Agneya), the master bedroom in the South-West (Nairutya), the puja room and
 * water sources in the North-East (Ishanya), and toilets away from the sacred NE.
 * Each `note` records the classical rationale so suggestions can cite an authentic reason.
 */
export interface VastuRule {
  ideal: VastuDirection[];
  acceptable: VastuDirection[];
  adverse: VastuDirection[];
  note: string;
}

export const VASTU_RULES: Record<RoomType, VastuRule> = {
  // Kitchen = fire element → Agneya (SE). NW acceptable as a secondary fire corner.
  kitchen: { ideal: ['SE'], acceptable: ['NW', 'S', 'E'], adverse: ['NE', 'SW', 'N'], note: 'The kitchen governs Agni (fire) and belongs in the South-East (Agneya).' },
  // Master bedroom = earth/stability → Nairutya (SW). Avoid the sacred NE.
  bedroom: { ideal: ['SW'], acceptable: ['S', 'W'], adverse: ['NE', 'SE', 'N'], note: 'The master bedroom seeks the stability of the South-West (Nairutya); the SE and NE are avoided for sleep.' },
  // Puja/prayer = most sacred → Ishanya (NE).
  puja: { ideal: ['NE'], acceptable: ['N', 'E'], adverse: ['S', 'SW', 'SE', 'W'], note: 'The puja room is most auspicious in the sacred North-East (Ishanya), facing the rising sun.' },
  // Toilets/bath: kept away from NE and SE; NW/W/SW (between corners) preferred.
  bathroom: { ideal: ['NW', 'W'], acceptable: ['S', 'SE'], adverse: ['NE', 'SW', 'E', 'N'], note: 'Toilets are kept out of the sacred North-East and away from the SW; the North-West/West is preferred.' },
  // Living/drawing room: bright NE/E/N.
  living: { ideal: ['N', 'NE', 'E'], acceptable: ['NW', 'W'], adverse: ['SW', 'SE'], note: 'The living room favours the open, light-filled North, North-East and East.' },
  // Study/office: NE/E/N for clarity and morning light.
  study: { ideal: ['NE', 'E', 'N'], acceptable: ['W'], adverse: ['SW', 'SE', 'S'], note: 'Study/office spaces benefit from the North-East and East for focus and morning light.' },
  // Dining: West/East/NW, near the kitchen.
  dining: { ideal: ['W', 'E'], acceptable: ['N', 'NW', 'S'], adverse: ['NE', 'SW'], note: 'The dining area is traditionally placed in the West or East, close to the kitchen.' },
  // Storage/store room: heavy mass in SW/S/W.
  storage: { ideal: ['SW', 'S', 'W'], acceptable: ['NW'], adverse: ['NE', 'N', 'E'], note: 'Heavy storage anchors the South-West, South and West; it must not burden the light North-East.' },
  // Garage/parking: NW or SE (vehicles = movement/fire).
  garage: { ideal: ['NW', 'SE'], acceptable: ['W', 'S', 'E'], adverse: ['NE', 'SW'], note: 'Parking suits the North-West (movement) or South-East; the NE and SW corners are kept clear.' },
  // Balcony/verandah & openings: N/E/NE for light and air.
  balcony: { ideal: ['N', 'E', 'NE'], acceptable: ['NW', 'W'], adverse: ['SW', 'S'], note: 'Balconies and large openings are best in the North, East and North-East for light and air.' },
  // Main entrance: N/E/NE most auspicious.
  entrance: { ideal: ['N', 'E', 'NE'], acceptable: ['W', 'NW'], adverse: ['SW', 'S', 'SE'], note: 'The main entrance is most auspicious in the North, East or North-East; the South-West is avoided.' },
  // Corridor/passage: flexible, slightly favouring N/E.
  corridor: { ideal: ['N', 'E', 'W'], acceptable: ['S', 'NW', 'NE', 'SE'], adverse: [], note: 'Corridors are flexible but flow best along the North–East side.' },
  custom: { ideal: [], acceptable: [], adverse: [], note: 'No Vastu rule is defined for a custom room type.' },
};

/**
 * The authentic Vastu placement rules as a display-ready list (excludes `custom`, which
 * has no rule). Used by the UI to show a reference table without needing a drawn plan.
 */
export const VASTU_RULES_LIST: ReadonlyArray<{ roomType: RoomType; roomName: string; rule: VastuRule }> =
  (Object.keys(VASTU_RULES) as RoomType[])
    .filter((t) => t !== 'custom')
    .map((t) => ({ roomType: t, roomName: ROOM_NAME[t], rule: VASTU_RULES[t] }));

/** Weight a room contributes to the overall score (more critical rooms count more). */
const ROOM_WEIGHT: Record<RoomType, number> = {
  kitchen: 3, bedroom: 3, puja: 3, entrance: 3,
  bathroom: 2, living: 2, study: 2,
  dining: 1, storage: 1, garage: 1, balcony: 1, corridor: 1, custom: 0,
};

/**
 * Full Vastu analysis for a plan. `roomPolygons` maps room id → its boundary points (cm);
 * `planBoundary` is the outer outline used to find the Brahmasthan and the directional grid.
 *
 * A room's direction is determined by which cell of the 3×3 Vastu Purusha Mandala grid its
 * centroid falls into, measured against the PLAN's bounding box (not the room's own centre).
 * This is the authentic way to read direction and, crucially, gives a meaningful, distinct
 * result for every room — unlike measuring a room against its own centroid, which collapses
 * to the centre for a single-room plan.
 */
export function computeVastuScore(
  rooms: Room[],
  roomPolygons: Record<string, Point2D[]>,
  planBoundary: Point2D[]
): VastuScore {
  const bbox = boundingBox(planBoundary);
  const planArea = Math.abs(computeSignedArea(planBoundary));
  const scoredRooms = rooms.filter((r) => {
    const p = roomPolygons[r.id];
    return p && p.length >= 3;
  });

  // Detect the "single room == whole plan" case: one room whose area is ~the whole plan.
  // Direction is undefined here (the room IS the house), so we guide instead of mis-scoring.
  const singleRoomPlan =
    scoredRooms.length === 1 &&
    Math.abs(computeSignedArea(roomPolygons[scoredRooms[0].id])) >= planArea * 0.9;

  const roomScores: Record<string, RoomVastuScore> = {};
  const recommendations: VastuRecommendation[] = [];
  let weightedSum = 0;
  let weightTotal = 0;

  for (const room of scoredRooms) {
    const polygon = roomPolygons[room.id];
    const rules = VASTU_RULES[room.roomType];
    const roomName = ROOM_NAME[room.roomType];
    const centroid = polygonCentroid(polygon);
    const cell = directionCell(centroid, bbox); // VastuDirection | 'CENTER'
    const direction: VastuDirection | 'CENTER' = cell;

    let score: number;
    let isIdeal = false;
    let reason: string;

    if (room.roomType === 'custom') {
      score = 50;
      reason = `“${room.label}” has no specific type yet. Assign a room type (kitchen, bedroom, …) to get an authentic Vastu placement check.`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: `Set a type for “${room.label}” to enable Vastu scoring.` });
    } else if (singleRoomPlan) {
      // The plan is a single room; there is no inner direction to evaluate yet.
      score = 60;
      reason = `“${room.label}” currently fills the whole plan, so its Vastu direction can't be judged. Add more rooms so the ${roomName.toLowerCase()} occupies a specific zone — ideally ${dirLabel(rules.ideal)}.`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: `Add interior walls so the ${roomName.toLowerCase()} sits in a specific direction (ideal: ${dirLabel(rules.ideal)}).` });
    } else if (cell === 'CENTER') {
      score = 35;
      reason = `${roomName} sits over the Brahmasthan (the sacred centre of the plan), which Vastu says should stay open. Shift it toward ${dirLabel(rules.ideal)}.`;
      recommendations.push({ severity: 'critical', roomId: room.id, message: `Move the ${roomName.toLowerCase()} off the central Brahmasthan toward ${dirLabel(rules.ideal)}; keep the centre open.` });
    } else if (rules.ideal.includes(cell)) {
      score = 100;
      isIdeal = true;
      reason = `${roomName} is correctly placed in the ${DIR_NAME[cell]}. ${rules.note}`;
    } else if (rules.acceptable.includes(cell)) {
      score = 78;
      reason = `${roomName} in the ${DIR_NAME[cell]} is acceptable. The ideal location is ${dirLabel(rules.ideal)}. ${rules.note}`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: `Optional: move the ${roomName.toLowerCase()} from the ${DIR_NAME[cell]} toward ${dirLabel(rules.ideal)} for a stronger result.` });
    } else if (rules.adverse.includes(cell)) {
      score = 22;
      reason = `${roomName} in the ${DIR_NAME[cell]} is a Vastu dosha (adverse). ${rules.note} Relocate it to ${dirLabel(rules.ideal)}.`;
      recommendations.push({ severity: 'critical', roomId: room.id, message: `Relocate the ${roomName.toLowerCase()} out of the ${DIR_NAME[cell]} (adverse) to ${dirLabel(rules.ideal)}.` });
    } else {
      score = 55;
      reason = `${roomName} in the ${DIR_NAME[cell]} is neutral — not harmful, but not ideal. ${dirLabel(rules.ideal)} is recommended.`;
      recommendations.push({ severity: 'warning', roomId: room.id, message: `The ${roomName.toLowerCase()} in the ${DIR_NAME[cell]} is not ideal; prefer ${dirLabel(rules.ideal)}.` });
    }

    roomScores[room.id] = {
      roomId: room.id,
      roomType: room.roomType,
      direction,
      score,
      isIdeal,
      idealDirections: rules.ideal,
      reason,
    };

    const w = ROOM_WEIGHT[room.roomType];
    weightedSum += score * w;
    weightTotal += w;
  }

  const overall = weightTotal > 0 ? weightedSum / weightTotal : 0;

  const sevRank = { critical: 0, warning: 1, suggestion: 2 } as const;
  recommendations.sort((a, b) => sevRank[a.severity] - sevRank[b.severity]);

  return { overall, roomScores, recommendations };
}

// ---- geometry helpers -----------------------------------------------------

interface BBox { minX: number; minY: number; maxX: number; maxY: number; }

function boundingBox(points: Point2D[]): BBox {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  return { minX, minY, maxX, maxY };
}

/** Area centroid of a polygon, with a vertex-average fallback for degenerate shapes. */
function polygonCentroid(polygon: Point2D[]): Point2D {
  const n = polygon.length;
  const avg = polygon.reduce((a, p) => ({ x: a.x + p.x / n, y: a.y + p.y / n }), { x: 0, y: 0 });
  if (n < 3) return avg;
  let area = 0, cx = 0, cy = 0;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const cross = polygon[i].x * polygon[j].y - polygon[j].x * polygon[i].y;
    area += cross;
    cx += (polygon[i].x + polygon[j].x) * cross;
    cy += (polygon[i].y + polygon[j].y) * cross;
  }
  area *= 0.5;
  if (Math.abs(area) < 1e-9) return avg;
  const f = 1 / (6 * area);
  return { x: cx * f, y: cy * f };
}

/**
 * Maps a point to one cell of the 3×3 Vastu Purusha Mandala grid laid over the plan's
 * bounding box. Columns are West→East (u), rows are South→North (v, since N = +Y). The
 * centre cell is the Brahmasthan; the eight surrounding cells are the compass directions.
 *
 * The centre band spans the middle third of each axis, matching the classical 9-part
 * (Padavinyasa) division of the plot.
 */
export function directionCell(p: Point2D, bbox: BBox): VastuDirection | 'CENTER' {
  const w = bbox.maxX - bbox.minX;
  const h = bbox.maxY - bbox.minY;
  if (w <= 0 || h <= 0) return 'CENTER';

  const u = (p.x - bbox.minX) / w; // 0 = West edge, 1 = East edge
  const v = (p.y - bbox.minY) / h; // 0 = South edge, 1 = North edge

  const col = u < 1 / 3 ? 0 : u < 2 / 3 ? 1 : 2; // 0=W 1=mid 2=E
  const row = v < 1 / 3 ? 0 : v < 2 / 3 ? 1 : 2; // 0=S 1=mid 2=N

  // grid[row][col]; row 2 = North band, row 0 = South band.
  const grid: (VastuDirection | 'CENTER')[][] = [
    ['SW', 'S', 'SE'],
    ['W', 'CENTER', 'E'],
    ['NW', 'N', 'NE'],
  ];
  return grid[row][col];
}
