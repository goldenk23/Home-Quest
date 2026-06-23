// src/domains/editor/services/wallGuides.ts
//
// Pure geometry helpers that power the "smart wall drawing" experience:
//   1. findParallelGuide  - while drawing, find the nearest EXISTING wall that runs
//                           parallel to the segment being drawn, and report how its
//                           length compares (so the user can match opposite sides of a
//                           rectangle/room exactly).
//   2. snapToWallEdge     - snap a raw point onto the closest existing wall centerline
//                           when it is within a radius. This is what lets a wall drawn
//                           THROUGH a room land exactly on the boundary walls, so the
//                           crossing is detected and the room is split into two.
//
// Everything here is pure (no store access) so it is trivially testable and reusable.

import type { Point2D } from '@/types/geometry';
import type { EntityId, Wall, Vertex } from '@/types/editor';

export interface WallSegment {
  id: EntityId;
  start: Point2D;
  end: Point2D;
}

export interface ParallelGuide {
  /** The existing wall that runs parallel to the segment being drawn. */
  wallId: EntityId;
  /** Endpoints of that existing wall (world cm). */
  start: Point2D;
  end: Point2D;
  /** Length of the existing parallel wall (cm). */
  length: number;
  /** Length of the segment currently being drawn (cm). */
  currentLength: number;
  /** currentLength - length (cm). ~0 means the two sides match. */
  delta: number;
  /** True when the two lengths are within `equalTolerance`. */
  isEqual: boolean;
}

/** Build plain segments from the wall/vertex graph (skips walls with missing vertices). */
export function toWallSegments(
  walls: Record<EntityId, Wall>,
  vertices: Record<EntityId, Vertex>
): WallSegment[] {
  const out: WallSegment[] = [];
  for (const w of Object.values(walls)) {
    const s = vertices[w.startVertexId]?.position;
    const e = vertices[w.endVertexId]?.position;
    if (s && e) out.push({ id: w.id, start: s, end: e });
  }
  return out;
}

function length2D(a: Point2D, b: Point2D): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

/** Smallest absolute angle (radians, 0..PI/2) between two directions, ignoring sign/flip. */
function parallelAngle(ax: number, ay: number, bx: number, by: number): number {
  const la = Math.hypot(ax, ay);
  const lb = Math.hypot(bx, by);
  if (la < 1e-9 || lb < 1e-9) return Math.PI; // degenerate ⇒ "not parallel"
  // |cos| handles the 180° flip; clamp guards against fp drift outside [-1,1].
  const cos = Math.min(1, Math.abs((ax * bx + ay * by) / (la * lb)));
  return Math.acos(cos); // 0 = perfectly parallel
}

/**
 * Find the existing wall most parallel to (start→end) and closest to it, so the UI can
 * show "opposite side is X m". Walls are considered parallel within `angleToleranceDeg`.
 * Among parallel candidates the nearest one (by midpoint distance) wins.
 */
export function findParallelGuide(
  start: Point2D,
  end: Point2D,
  segments: WallSegment[],
  opts: { angleToleranceDeg?: number; equalTolerance?: number } = {}
): ParallelGuide | null {
  const angleTol = ((opts.angleToleranceDeg ?? 6) * Math.PI) / 180;
  const equalTol = opts.equalTolerance ?? 2; // cm

  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const currentLength = Math.hypot(dx, dy);
  if (currentLength < 1) return null; // nothing meaningful to compare yet

  const mid = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };

  let best: ParallelGuide | null = null;
  let bestDist = Infinity;

  for (const seg of segments) {
    const sdx = seg.end.x - seg.start.x;
    const sdy = seg.end.y - seg.start.y;
    if (parallelAngle(dx, dy, sdx, sdy) > angleTol) continue; // not parallel enough

    const segMid = { x: (seg.start.x + seg.end.x) / 2, y: (seg.start.y + seg.end.y) / 2 };
    const dist = length2D(mid, segMid);
    if (dist < bestDist) {
      const segLen = Math.hypot(sdx, sdy);
      bestDist = dist;
      best = {
        wallId: seg.id,
        start: seg.start,
        end: seg.end,
        length: segLen,
        currentLength,
        delta: currentLength - segLen,
        isEqual: Math.abs(currentLength - segLen) <= equalTol,
      };
    }
  }

  return best;
}

/** Closest point on segment a→b to p, plus the (squared) distance to it. */
function closestOnSegment(p: Point2D, a: Point2D, b: Point2D): { point: Point2D; distSq: number } {
  const abx = b.x - a.x;
  const aby = b.y - a.y;
  const l2 = abx * abx + aby * aby;
  let t = 0;
  if (l2 > 0) {
    t = ((p.x - a.x) * abx + (p.y - a.y) * aby) / l2;
    t = Math.max(0, Math.min(1, t));
  }
  const point = { x: a.x + t * abx, y: a.y + t * aby };
  const ddx = p.x - point.x;
  const ddy = p.y - point.y;
  return { point, distSq: ddx * ddx + ddy * ddy };
}

/**
 * Snap `point` onto the nearest existing wall centerline if it lies within `radius`.
 * Returns the original point when nothing is close. This is the key to feature 2:
 * the endpoints of a wall drawn across a room land exactly on the boundary walls, so
 * the crossing is found and the enclosed area is divided into two rooms.
 */
export function snapToWallEdge(
  point: Point2D,
  segments: readonly WallSegment[],
  radius: number
): Point2D {
  const radiusSq = radius * radius;
  let bestPoint: Point2D | null = null;
  let bestDistSq = radiusSq;

  for (const seg of segments) {
    const { point: cp, distSq } = closestOnSegment(point, seg.start, seg.end);
    if (distSq < bestDistSq) {
      bestDistSq = distSq;
      bestPoint = cp;
    }
  }

  return bestPoint ?? point;
}
