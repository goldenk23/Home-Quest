// src/domains/editor/services/stairBuilder.ts
//
// Pure service: converts a 2D path + configuration → a fully computed StairEntity.
// No React, no store access — takes all inputs as arguments and returns a value.

import type { EntityId } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import type { StairEntity, StairFlight, StairLanding } from '@/types/stair';
import { generateId } from '@/utils/id';

/** Valid rise range per step (cm). */
const MIN_RISE_CM = 15;
const MAX_RISE_CM = 19;
/** Preferred rise, used to pick the nearest valid step count. */
const TARGET_RISE_CM = 17;

export type StairBuildResult =
  | { ok: true; stair: StairEntity }
  | { ok: false; error: string };

/**
 * Builds a complete StairEntity from a path drawn in the 2D plan.
 *
 * @param pathPoints  Ordered plan-cm points; first = bottom step, last = top landing.
 * @param widthCm     Stair width (60–500 cm).
 * @param totalRiseCm Inter-storey height (e.g. 300 cm).
 * @param lowerFloorId  Floor where the bottom step sits.
 * @param upperFloorId  Floor where the top step lands.
 * @param lowerElevationCm  Absolute Y elevation of the lower floor base (cm).
 */
export function buildStair(
  pathPoints: Point2D[],
  widthCm: number,
  totalRiseCm: number,
  lowerFloorId: EntityId,
  upperFloorId: EntityId,
  lowerElevationCm: number
): StairBuildResult {
  if (pathPoints.length < 2) return err('A staircase needs at least 2 path points.');
  if (totalRiseCm <= 0) return err('Inter-storey height must be greater than 0.');
  if (widthCm < 60 || widthCm > 500) return err('Stair width must be 60–500 cm.');

  const stepCount = bestStepCount(totalRiseCm);
  if (stepCount === null) {
    return err(
      `Cannot produce uniform steps (${MIN_RISE_CM}–${MAX_RISE_CM} cm rise) for a ${totalRiseCm.toFixed(0)} cm storey.`
    );
  }
  const risePerStepCm = totalRiseCm / stepCount;

  // Build segments and measure lengths.
  const segments: { start: Point2D; end: Point2D; length: number }[] = [];
  let totalPlanLength = 0;
  for (let i = 0; i < pathPoints.length - 1; i++) {
    const dx = pathPoints[i + 1].x - pathPoints[i].x;
    const dy = pathPoints[i + 1].y - pathPoints[i].y;
    const length = Math.hypot(dx, dy);
    if (length < 1) return err(`Segment ${i + 1} is shorter than 1 cm.`);
    segments.push({ start: pathPoints[i], end: pathPoints[i + 1], length });
    totalPlanLength += length;
  }

  // Distribute steps proportionally across segments (at least 1 per segment).
  const stepsPerSeg = distributeSteps(stepCount, segments.map((s) => s.length));
  for (let i = 0; i < stepsPerSeg.length; i++) {
    if (stepsPerSeg[i] < 1) return err(`Segment ${i + 1} is too short to hold any steps.`);
  }

  // Build flights + landings.
  const flights: StairFlight[] = [];
  const landings: StairLanding[] = [];
  let curElevation = lowerElevationCm;

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const numSteps = stepsPerSeg[i];
    const flightRise = numSteps * risePerStepCm;
    const going = seg.length / numSteps;

    flights.push({
      id: generateId('stair-flight'),
      startPoint: seg.start,
      endPoint: seg.end,
      widthCm,
      bottomElevationCm: curElevation,
      topElevationCm: curElevation + flightRise,
      stepCount: numSteps,
      risePerStepCm,
      goingPerStepCm: going,
    });
    curElevation += flightRise;

    // Landing at every intermediate turn.
    if (i < segments.length - 1) {
      const incomingAngle = Math.atan2(
        seg.end.y - seg.start.y,
        seg.end.x - seg.start.x
      );
      landings.push({
        id: generateId('stair-landing'),
        center: seg.end,
        widthCm,
        depthCm: widthCm,
        elevationCm: curElevation,
        rotation: incomingAngle,
      });
    }
  }

  const stairwellVoid = pathStrokePolygon(pathPoints, widthCm / 2);

  return {
    ok: true,
    stair: {
      id: generateId('stair'),
      lowerFloorId,
      upperFloorId,
      pathPoints,
      widthCm,
      flights,
      landings,
      stairwellVoid,
    },
  };
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function err(msg: string): { ok: false; error: string } {
  return { ok: false, error: msg };
}

/**
 * Finds the integer step count closest to `totalRiseCm / TARGET_RISE_CM` such that
 * `totalRiseCm / stepCount` is within [MIN_RISE_CM, MAX_RISE_CM]. Returns null if none exists.
 */
function bestStepCount(totalRiseCm: number): number | null {
  const target = Math.round(totalRiseCm / TARGET_RISE_CM);
  for (let delta = 0; delta <= 20; delta++) {
    for (const sign of [1, -1]) {
      const n = target + sign * delta;
      if (n < 1) continue;
      const rise = totalRiseCm / n;
      if (rise >= MIN_RISE_CM && rise <= MAX_RISE_CM) return n;
    }
  }
  return null;
}

/**
 * Distributes `totalSteps` across segments proportionally to their lengths,
 * ensuring every segment gets at least 1 step and the sum is exact.
 */
function distributeSteps(totalSteps: number, lengths: number[]): number[] {
  const totalLen = lengths.reduce((a, b) => a + b, 0);
  const floored = lengths.map((l) => Math.max(1, Math.floor((l / totalLen) * totalSteps)));
  let remaining = totalSteps - floored.reduce((a, b) => a + b, 0);
  // Distribute remainder to segments with the largest fractional parts.
  const fractions = lengths.map((l, i) => ({
    i,
    frac: (l / totalLen) * totalSteps - floored[i],
  }));
  fractions.sort((a, b) => b.frac - a.frac);
  for (let k = 0; k < remaining; k++) floored[fractions[k % fractions.length].i]++;
  return floored;
}

/**
 * Computes a closed polygon that traces both sides of the multi-segment path at
 * `halfWidth` distance. Returns a simple polygon suitable for hole-cutting in slab geometry.
 *
 * For a 2-point (straight) path this is a rectangle. For an L/U/multi-segment path it
 * follows the exact contour, with mitered inner corners and flat end caps.
 */
export function pathStrokePolygon(points: Point2D[], halfWidth: number): Point2D[] {
  if (points.length < 2) return [];

  // Per-segment unit left-normal (perpendicular, pointing left of travel direction).
  const normals: Point2D[] = points.slice(0, -1).map((p, i) => {
    const nx = points[i + 1].x - p.x;
    const ny = points[i + 1].y - p.y;
    const len = Math.hypot(nx, ny) || 1;
    return { x: -ny / len, y: nx / len };
  });

  const leftSide: Point2D[] = [];
  const rightSide: Point2D[] = [];

  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    if (i === 0) {
      const n = normals[0];
      leftSide.push({ x: p.x + n.x * halfWidth, y: p.y + n.y * halfWidth });
      rightSide.push({ x: p.x - n.x * halfWidth, y: p.y - n.y * halfWidth });
    } else if (i === points.length - 1) {
      const n = normals[i - 1];
      leftSide.push({ x: p.x + n.x * halfWidth, y: p.y + n.y * halfWidth });
      rightSide.push({ x: p.x - n.x * halfWidth, y: p.y - n.y * halfWidth });
    } else {
      // Miter: bisector of the two adjacent normals, scaled to maintain halfWidth distance.
      const n1 = normals[i - 1];
      const n2 = normals[i];
      const bx = n1.x + n2.x;
      const by = n1.y + n2.y;
      const bLen = Math.hypot(bx, by);
      if (bLen < 1e-6) {
        // 180° turn (straight continuation) — just use one normal.
        leftSide.push({ x: p.x + n2.x * halfWidth, y: p.y + n2.y * halfWidth });
        rightSide.push({ x: p.x - n2.x * halfWidth, y: p.y - n2.y * halfWidth });
      } else {
        const ubx = bx / bLen;
        const uby = by / bLen;
        const dot = ubx * n1.x + uby * n1.y;
        // Cap the miter length at 3× halfWidth to prevent extreme inner corners.
        const miterLen = Math.min(halfWidth / Math.max(dot, 0.3), halfWidth * 3);
        leftSide.push({ x: p.x + ubx * miterLen, y: p.y + uby * miterLen });
        rightSide.push({ x: p.x - ubx * miterLen, y: p.y - uby * miterLen });
      }
    }
  }

  // Polygon: left side (forward), then right side (backward) → closed loop.
  return [...leftSide, ...rightSide.reverse()];
}
