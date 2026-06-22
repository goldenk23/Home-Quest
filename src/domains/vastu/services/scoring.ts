// src/domains/vastu/services/scoring.ts

import type { Room, RoomType } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { type VastuDirection, getRoomDirection } from './zones';
import { calculateBrahmasthan } from './brahmasthan';

export interface VastuScore {
  readonly overall: number; // 0-100
  readonly roomScores: Record<string, RoomVastuScore>;
  readonly recommendations: VastuRecommendation[];
}

export interface RoomVastuScore {
  readonly roomId: string;
  readonly roomType: RoomType;
  readonly direction: VastuDirection;
  readonly score: number;
  readonly isIdeal: boolean;
  readonly idealDirections: VastuDirection[];
  readonly reason: string;
}

export interface VastuRecommendation {
  readonly severity: 'critical' | 'warning' | 'suggestion';
  readonly roomId: string;
  readonly message: string;
}

/** Ideal / acceptable / adverse placements per room type (traditional Vastu). */
const VASTU_RULES: Record<RoomType, { ideal: VastuDirection[]; acceptable: VastuDirection[]; adverse: VastuDirection[] }> = {
  living: { ideal: ['N', 'NE', 'E'], acceptable: ['NW', 'SE'], adverse: ['SW', 'S'] },
  bedroom: { ideal: ['SW', 'S', 'W'], acceptable: ['NW'], adverse: ['NE', 'SE'] },
  kitchen: { ideal: ['SE'], acceptable: ['S', 'E', 'NW'], adverse: ['NE', 'SW'] },
  bathroom: { ideal: ['NW', 'W'], acceptable: ['SE'], adverse: ['NE', 'SW', 'E'] },
  puja: { ideal: ['NE'], acceptable: ['N', 'E'], adverse: ['S', 'SW', 'SE'] },
  study: { ideal: ['NE', 'N', 'E'], acceptable: ['W', 'NW'], adverse: ['SW', 'S', 'SE'] },
  dining: { ideal: ['W', 'E'], acceptable: ['N', 'S'], adverse: ['NE', 'SW'] },
  storage: { ideal: ['SW', 'S', 'W'], acceptable: ['NW'], adverse: ['NE', 'N'] },
  garage: { ideal: ['NW', 'SE'], acceptable: ['W', 'S'], adverse: ['NE'] },
  balcony: { ideal: ['N', 'E', 'NE'], acceptable: ['NW', 'SE'], adverse: ['SW', 'W'] },
  entrance: { ideal: ['N', 'E', 'NE'], acceptable: ['NW'], adverse: ['S', 'SW', 'SE'] },
  corridor: { ideal: ['N', 'E'], acceptable: ['W', 'S'], adverse: [] },
  custom: { ideal: [], acceptable: [], adverse: [] },
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
  const roomScores: Record<string, RoomVastuScore> = {};
  const recommendations: VastuRecommendation[] = [];

  for (const room of rooms) {
    const polygon = roomPolygons[room.id];
    if (!polygon || polygon.length < 3) continue;

    const direction = getRoomDirection(polygon, brahmasthan);
    const rules = VASTU_RULES[room.roomType];

    let score: number;
    let isIdeal = false;
    let reason: string;

    if (rules.ideal.includes(direction)) {
      score = 100;
      isIdeal = true;
      reason = `${room.label} is perfectly placed in the ${direction}.`;
    } else if (rules.acceptable.includes(direction)) {
      score = 70;
      reason = `${room.label} is acceptably placed in the ${direction}. Ideal: ${rules.ideal.join(', ')}.`;
    } else if (rules.adverse.includes(direction)) {
      score = 20;
      reason = `${room.label} in the ${direction} is adverse. Prefer: ${rules.ideal.join(', ')}.`;
      recommendations.push({ severity: 'critical', roomId: room.id, message: reason });
    } else {
      score = 50;
      reason = `${room.label} is neutral in the ${direction}. Ideal: ${rules.ideal.join(', ')}.`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: reason });
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
  }

  const entries = Object.values(roomScores);
  const overall = entries.length ? entries.reduce((s, r) => s + r.score, 0) / entries.length : 0;
  return { overall, roomScores, recommendations };
}
