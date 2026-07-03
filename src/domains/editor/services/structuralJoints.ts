// src/domains/editor/services/structuralJoints.ts
//
// Pure geometry for making pillar↔deck and pillar↔beam joints seat like real construction:
// a member snaps to a pillar's CENTER while drawing, which leaves half the post uncovered
// (deck) or the member stopping mid-post (beam). These helpers push the member out to the
// pillar's outer face so the post ends up fully beneath/inside the member and the faces meet
// cleanly. Pure (no store/THREE) so both are trivially testable.

import type { Point2D } from '@/types/geometry';

export interface PillarFootprint {
  shape: 'rect' | 'round';
  width: number;
  depth: number;
}

/**
 * Push a deck polygon vertex sitting on a pillar center OUTWARD (away from the polygon
 * centroid) to the pillar's outer corner, so the whole post top lands beneath the slab.
 * Rect posts reach their outer corner per-axis; round posts reach the radius along the
 * outward direction.
 */
export function snapDeckCornerOutward(pt: Point2D, centroid: Point2D, pillar: PillarFootprint): Point2D {
  const ox = pt.x - centroid.x;
  const oy = pt.y - centroid.y;
  if (pillar.shape === 'round') {
    const len = Math.hypot(ox, oy) || 1;
    const r = Math.max(pillar.width, pillar.depth) / 2;
    return { x: pt.x + (ox / len) * r, y: pt.y + (oy / len) * r };
  }
  const sx = ox === 0 ? 1 : Math.sign(ox);
  const sy = oy === 0 ? 1 : Math.sign(oy);
  return { x: pt.x + sx * (pillar.width / 2), y: pt.y + sy * (pillar.depth / 2) };
}

/** How far along a unit direction a pillar reaches from its center to its outer face. */
export function pillarReachAlong(pillar: PillarFootprint, ux: number, uy: number): number {
  if (pillar.shape === 'round') return Math.max(pillar.width, pillar.depth) / 2;
  return Math.abs(ux) * (pillar.width / 2) + Math.abs(uy) * (pillar.depth / 2);
}

/**
 * Extend a beam's endpoints out to the outer faces of the pillars they connect to, so the
 * beam fully spans and bears on each post instead of stopping at its center. Ends with no
 * pillar are left unchanged.
 */
export function extendBeamEndsToPillars(
  start: Point2D,
  end: Point2D,
  startPillar: PillarFootprint | null,
  endPillar: PillarFootprint | null,
): [Point2D, Point2D] {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const len = Math.hypot(dx, dy);
  if (len < 1e-6) return [start, end];
  const ux = dx / len;
  const uy = dy / len;

  const adjStart = startPillar
    ? { x: start.x - ux * pillarReachAlong(startPillar, ux, uy), y: start.y - uy * pillarReachAlong(startPillar, ux, uy) }
    : start;
  const adjEnd = endPillar
    ? { x: end.x + ux * pillarReachAlong(endPillar, ux, uy), y: end.y + uy * pillarReachAlong(endPillar, ux, uy) }
    : end;
  return [adjStart, adjEnd];
}
