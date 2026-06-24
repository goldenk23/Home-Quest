// src/domains/editor/services/openingGeometry.ts
//
// Shared geometry for wall openings (doors / windows / vents). Both the WallLayer (which
// cuts a gap in the wall for doors) and the OpeningsLayer (which draws the door swing
// symbol) derive their geometry from here so the gap and the symbol always line up.

import type { Point2D } from '@/types/geometry';
import type { Opening } from '@/types/editor';

export interface OpeningGeometry {
  /** Opening centre point in world space (cm). */
  center: Point2D;
  /** Unit vector along the wall, from start vertex → end vertex. */
  v: Point2D;
  /** Unit normal to the wall. */
  n: Point2D;
  /** Half the opening width (cm). */
  halfW: number;
  /** Half the wall thickness (cm). */
  halfThick: number;
  /** Jamb at (offset − halfW) along the wall — the "near" side. */
  j1: Point2D;
  /** Jamb at (offset + halfW) along the wall — the "far" side. */
  j2: Point2D;
}

/**
 * Resolves an opening's placement on its wall into reusable vectors and jamb points.
 * Returns null for degenerate (zero-length) walls.
 *
 * `offsetCm` is the distance from the wall's start vertex to the opening CENTRE.
 */
export function computeOpeningGeometry(
  opening: Pick<Opening, 'offsetCm' | 'width'>,
  start: Point2D,
  end: Point2D,
  thickness: number
): OpeningGeometry | null {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy);
  if (length === 0) return null;

  const v: Point2D = { x: dx / length, y: dy / length };
  const n: Point2D = { x: -v.y, y: v.x };

  const center: Point2D = { x: start.x + v.x * opening.offsetCm, y: start.y + v.y * opening.offsetCm };
  const halfW = opening.width / 2;
  const halfThick = thickness / 2;

  const j1: Point2D = { x: center.x - v.x * halfW, y: center.y - v.y * halfW };
  const j2: Point2D = { x: center.x + v.x * halfW, y: center.y + v.y * halfW };

  return { center, v, n, halfW, halfThick, j1, j2 };
}
