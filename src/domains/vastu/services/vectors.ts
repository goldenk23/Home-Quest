// src/domains/vastu/services/vectors.ts

import type { Point2D } from '@/types/geometry';

/**
 * Unit vectors for the 16-direction model (each 22.5° apart). North = +Y, East = +X.
 * Used for fine-grained zone work and as a lookup when drawing direction markers.
 */
export const DIRECTION_VECTORS_16: Record<string, Point2D> = {
  E: { x: 1.0, y: 0.0 },
  ENE: { x: 0.924, y: 0.383 },
  NE: { x: 0.707, y: 0.707 },
  NNE: { x: 0.383, y: 0.924 },
  N: { x: 0.0, y: 1.0 },
  NNW: { x: -0.383, y: 0.924 },
  NW: { x: -0.707, y: 0.707 },
  WNW: { x: -0.924, y: 0.383 },
  W: { x: -1.0, y: 0.0 },
  WSW: { x: -0.924, y: -0.383 },
  SW: { x: -0.707, y: -0.707 },
  SSW: { x: -0.383, y: -0.924 },
  S: { x: 0.0, y: -1.0 },
  SSE: { x: 0.383, y: -0.924 },
  SE: { x: 0.707, y: -0.707 },
  ESE: { x: 0.924, y: -0.383 },
};

/** Angular midpoint between two direction vectors (handles the 0°/360° wrap). */
export function angularMidpoint(a: Point2D, b: Point2D): Point2D {
  const ax = Math.atan2(a.y, a.x);
  const bx = Math.atan2(b.y, b.x);
  let diff = bx - ax;
  if (diff > Math.PI) diff -= 2 * Math.PI;
  if (diff < -Math.PI) diff += 2 * Math.PI;
  const mid = ax + diff / 2;
  return { x: Math.cos(mid), y: Math.sin(mid) };
}

/**
 * Tests whether an angle falls inside a sector, correctly handling sectors that straddle
 * 0°/360° (e.g. the East sector running 337.5°→22.5°).
 */
export function isAngleInSector(angle: number, sectorStart: number, sectorSpan: number): boolean {
  const TWO_PI = Math.PI * 2;
  const normAngle = ((angle % TWO_PI) + TWO_PI) % TWO_PI;
  const normStart = ((sectorStart % TWO_PI) + TWO_PI) % TWO_PI;
  const end = normStart + sectorSpan;
  return end <= TWO_PI ? normAngle >= normStart && normAngle < end : normAngle >= normStart || normAngle < end - TWO_PI;
}
