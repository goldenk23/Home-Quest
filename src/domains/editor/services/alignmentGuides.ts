// src/domains/editor/services/alignmentGuides.ts

import type { Point2D } from '@/types/geometry';

/**
 * Figma-style alignment: given a dragged point (usually a furniture center) and a set of
 * candidate anchor points (other entities' centers/vertices), find the nearest X and Y within
 * tolerance to snap to, plus the guide-line coordinates to render.
 *
 * Pure and framework-free. Port of the Python editor's `get_room_alignment_snap` /
 * `draw_room_alignment_guides`, simplified to point anchors.
 */

export interface AlignmentResult {
  /** World X to snap the dragged point to (a vertical guide), when a match is within tolerance. */
  snapX?: number;
  /** World Y to snap the dragged point to (a horizontal guide). */
  snapY?: number;
}

export function computeAlignment(point: Point2D, anchors: readonly Point2D[], tolerance = 8): AlignmentResult {
  let bestX: number | undefined;
  let bestXd = tolerance;
  let bestY: number | undefined;
  let bestYd = tolerance;

  for (const a of anchors) {
    const dx = Math.abs(a.x - point.x);
    if (dx < bestXd) {
      bestXd = dx;
      bestX = a.x;
    }
    const dy = Math.abs(a.y - point.y);
    if (dy < bestYd) {
      bestYd = dy;
      bestY = a.y;
    }
  }

  const result: AlignmentResult = {};
  if (bestX !== undefined) result.snapX = bestX;
  if (bestY !== undefined) result.snapY = bestY;
  return result;
}
