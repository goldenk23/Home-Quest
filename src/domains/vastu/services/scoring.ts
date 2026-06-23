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
  /** One-line summary (kept for backward compatibility). */
  readonly reason: string;
  /** Status keyword for the badge: ideal / acceptable / neutral / adverse / center / unset. */
  readonly status: 'ideal' | 'acceptable' | 'neutral' | 'adverse' | 'center' | 'unset';
  /** What is already right about this placement (always present, even if minimal). */
  readonly whatsCorrect: string;
  /** What is wrong / sub-optimal. Empty string when nothing is wrong. */
  readonly whatsWrong: string;
  /** Plain, step-by-step guidance on how to fix or improve it. Empty when already ideal. */
  readonly howToFix: string;
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
    let status: RoomVastuScore['status'];
    let whatsCorrect: string;
    let whatsWrong: string;
    let howToFix: string;

    const idealText = dirLabel(rules.ideal);
    const cellName = cell === 'CENTER' ? 'the centre (Brahmasthan)' : DIR_NAME[cell];

    if (room.roomType === 'custom') {
      score = 50;
      status = 'unset';
      whatsCorrect = `“${room.label}” is detected as a valid enclosed room.`;
      whatsWrong = `It has no room type assigned, so Vastu placement can't be evaluated.`;
      howToFix = `In the Rooms panel, pick what this room is (kitchen, bedroom, puja, etc.). The Vastu check will then tell you if its direction is correct.`;
      reason = `${whatsCorrect} ${whatsWrong}`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: `Set a type for “${room.label}” to enable Vastu scoring.` });
    } else if (singleRoomPlan) {
      score = 60;
      status = 'neutral';
      whatsCorrect = `The ${roomName.toLowerCase()} is a properly closed room with a measurable area.`;
      whatsWrong = `It currently fills the entire plan, so it has no specific compass direction to judge — Vastu direction only means something once a room occupies one part of the house.`;
      howToFix = `Add interior walls to split the house into separate rooms. Aim to place this ${roomName.toLowerCase()} in the ${idealText} zone, which is its ideal Vastu location.`;
      reason = `${whatsCorrect} ${whatsWrong}`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: `Add interior walls so the ${roomName.toLowerCase()} occupies the ${idealText} zone.` });
    } else if (cell === 'CENTER') {
      score = 35;
      status = 'center';
      whatsCorrect = `The ${roomName.toLowerCase()} is a valid, enclosed room.`;
      whatsWrong = `It sits over the Brahmasthan — the sacred centre of the house. Vastu Shastra says the centre should stay open and unburdened, so any room here is a dosha (defect).`;
      howToFix = `Move the ${roomName.toLowerCase()} outward, toward the ${idealText} part of the house, and leave the central zone as open space (a courtyard, hall, or light well).`;
      reason = `${whatsCorrect} ${whatsWrong}`;
      recommendations.push({ severity: 'critical', roomId: room.id, message: `Move the ${roomName.toLowerCase()} off the central Brahmasthan toward the ${idealText}; keep the centre open.` });
    } else if (rules.ideal.includes(cell)) {
      score = 100;
      isIdeal = true;
      status = 'ideal';
      whatsCorrect = `The ${roomName.toLowerCase()} is in the ${DIR_NAME[cell]}, which is the ideal Vastu direction for it. ${rules.note}`;
      whatsWrong = '';
      howToFix = '';
      reason = whatsCorrect;
    } else if (rules.acceptable.includes(cell)) {
      score = 78;
      status = 'acceptable';
      whatsCorrect = `The ${roomName.toLowerCase()} is in the ${DIR_NAME[cell]}, which is an acceptable location — it does not cause a Vastu defect.`;
      whatsWrong = `It is not in the most auspicious spot. According to Vastu Shastra the ideal direction for a ${roomName.toLowerCase()} is the ${idealText}.`;
      howToFix = `If you can, shift the ${roomName.toLowerCase()} toward the ${idealText} zone. If relocating is impractical, leaving it here is still fine.`;
      reason = `${whatsCorrect} ${whatsWrong}`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: `Optional: move the ${roomName.toLowerCase()} from the ${DIR_NAME[cell]} toward the ${idealText} for a stronger result.` });
    } else if (rules.adverse.includes(cell)) {
      score = 22;
      status = 'adverse';
      whatsCorrect = `The ${roomName.toLowerCase()} is a valid, enclosed room and its area is being measured correctly.`;
      whatsWrong = `Its direction is wrong: it is in the ${DIR_NAME[cell]}, which Vastu Shastra considers adverse (a dosha) for a ${roomName.toLowerCase()}. ${rules.note}`;
      howToFix = `Relocate the ${roomName.toLowerCase()} to the ${idealText} zone of the house. Practically: redraw its walls so its centre falls in the ${idealText} third of the plan, and use the ${DIR_NAME[cell]} space for a room that suits it instead.`;
      reason = `${whatsCorrect} ${whatsWrong}`;
      recommendations.push({ severity: 'critical', roomId: room.id, message: `Relocate the ${roomName.toLowerCase()} out of the ${DIR_NAME[cell]} (adverse) to the ${idealText}.` });
    } else {
      score = 55;
      status = 'neutral';
      whatsCorrect = `The ${roomName.toLowerCase()} is in the ${DIR_NAME[cell]}, which is neutral — not a defect, so it won't harm the layout.`;
      whatsWrong = `It is not the recommended direction. The ideal Vastu location for a ${roomName.toLowerCase()} is the ${idealText}.`;
      howToFix = `For a better score, move the ${roomName.toLowerCase()} toward the ${idealText} zone. If that isn't possible, this position is acceptable to keep.`;
      reason = `${whatsCorrect} ${whatsWrong}`;
      recommendations.push({ severity: 'warning', roomId: room.id, message: `The ${roomName.toLowerCase()} in the ${DIR_NAME[cell]} is not ideal; prefer the ${idealText}.` });
    }
    void cellName;

    roomScores[room.id] = {
      roomId: room.id,
      roomType: room.roomType,
      direction,
      score,
      isIdeal,
      idealDirections: rules.ideal,
      reason,
      status,
      whatsCorrect,
      whatsWrong,
      howToFix,
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
