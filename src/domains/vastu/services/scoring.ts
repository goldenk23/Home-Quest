// src/domains/vastu/services/scoring.ts

import type { Room, RoomType } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { type VastuDirection, getRoomDirection } from './zones';
import { calculateBrahmasthan, calculateBrahmasthanZone } from './brahmasthan';

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
const DIR_NAME: Record<VastuDirection, string> = {
  N: 'North',
  NE: 'North-East (Ishanya)',
  E: 'East',
  SE: 'South-East (Agneya)',
  S: 'South',
  SW: 'South-West (Nairutya)',
  W: 'West',
  NW: 'North-West (Vayavya)',
};

const ROOM_NAME: Record<RoomType, string> = {
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
const VASTU_RULES: Record<
  RoomType,
  { ideal: VastuDirection[]; acceptable: VastuDirection[]; adverse: VastuDirection[]; note: string }
> = {
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

/** Weight a room contributes to the overall score (more critical rooms count more). */
const ROOM_WEIGHT: Record<RoomType, number> = {
  kitchen: 3, bedroom: 3, puja: 3, entrance: 3,
  bathroom: 2, living: 2, study: 2,
  dining: 1, storage: 1, garage: 1, balcony: 1, corridor: 1, custom: 0,
};

/**
 * Full Vastu analysis for a plan. `roomPolygons` maps room id → its boundary points (cm);
 * `planBoundary` is the outer outline used to find the Brahmasthan.
 */
export function computeVastuScore(
  rooms: Room[],
  roomPolygons: Record<string, Point2D[]>,
  planBoundary: Point2D[]
): VastuScore {
  const brahmasthan = calculateBrahmasthan(planBoundary);
  const centreZone = calculateBrahmasthanZone(planBoundary, brahmasthan);
  const roomScores: Record<string, RoomVastuScore> = {};
  const recommendations: VastuRecommendation[] = [];

  let weightedSum = 0;
  let weightTotal = 0;

  for (const room of rooms) {
    const polygon = roomPolygons[room.id];
    if (!polygon || polygon.length < 3) continue;

    const rules = VASTU_RULES[room.roomType];
    const roomName = ROOM_NAME[room.roomType];
    const dir = getRoomDirection(polygon, brahmasthan);

    // Distance of the room centroid from the plan centre, to flag Brahmasthan obstruction.
    const n = polygon.length;
    const centroid = polygon.reduce((a, p) => ({ x: a.x + p.x / n, y: a.y + p.y / n }), { x: 0, y: 0 });
    const distToCentre = Math.hypot(centroid.x - brahmasthan.x, centroid.y - brahmasthan.y);
    const inBrahmasthan = dir === null || distToCentre <= centreZone.radius;

    let score: number;
    let isIdeal = false;
    let reason: string;
    const direction: VastuDirection | 'CENTER' = dir ?? 'CENTER';

    if (room.roomType === 'custom') {
      // No authentic rule to apply — stay neutral and don't penalise.
      score = 50;
      reason = `${room.label}: set a specific room type to get a Vastu placement check.`;
    } else if (inBrahmasthan) {
      // The centre (Brahmasthan) should stay open; a room sitting on it is a real issue.
      score = 30;
      reason = `${roomName} sits over the Brahmasthan (the sacred centre), which should be kept open and uncluttered. Shift it toward ${dirLabel(rules.ideal)}.`;
      recommendations.push({ severity: 'critical', roomId: room.id, message: reason });
    } else if (rules.ideal.includes(dir!)) {
      score = 100;
      isIdeal = true;
      reason = `${roomName} is correctly placed in the ${DIR_NAME[dir!]}. ${rules.note}`;
    } else if (rules.acceptable.includes(dir!)) {
      score = 75;
      reason = `${roomName} in the ${DIR_NAME[dir!]} is acceptable. The ideal location is ${dirLabel(rules.ideal)}. ${rules.note}`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: `Consider moving the ${roomName.toLowerCase()} from the ${DIR_NAME[dir!]} toward ${dirLabel(rules.ideal)} for a better result.` });
    } else if (rules.adverse.includes(dir!)) {
      score = 20;
      reason = `${roomName} in the ${DIR_NAME[dir!]} is a Vastu dosha (adverse). ${rules.note} Move it to ${dirLabel(rules.ideal)}.`;
      recommendations.push({ severity: 'critical', roomId: room.id, message: `Relocate the ${roomName.toLowerCase()} out of the ${DIR_NAME[dir!]} (adverse) to ${dirLabel(rules.ideal)}.` });
    } else {
      score = 55;
      reason = `${roomName} in the ${DIR_NAME[dir!]} is neutral. The ideal location is ${dirLabel(rules.ideal)}.`;
      recommendations.push({ severity: 'warning', roomId: room.id, message: `The ${roomName.toLowerCase()} in the ${DIR_NAME[dir!]} is not ideal; ${dirLabel(rules.ideal)} is recommended.` });
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

  // Order recommendations by severity so the most important fixes surface first.
  const sevRank = { critical: 0, warning: 1, suggestion: 2 } as const;
  recommendations.sort((a, b) => sevRank[a.severity] - sevRank[b.severity]);

  return { overall, roomScores, recommendations };
}
