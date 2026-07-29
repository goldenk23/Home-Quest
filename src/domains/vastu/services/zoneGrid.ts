// src/domains/vastu/services/zoneGrid.ts

import type { Point2D } from '@/types/geometry';
import type { VastuZoneCount, VastuChakraMode } from '@/store/slices/vastuSlice';

/**
 * Pure geometry for the Vastu authoring chakra grid: given the plan boundary polygon, a center
 * (Brahmasthan), a zone count (8/16/32), a north offset, and a label scheme, produce the sector
 * division lines (center → boundary) and per-zone label anchors + names.
 *
 * All angles are world-space (Y up). North points to world +Y (90°); `northDeg` rotates the
 * whole rose clockwise (compass convention). Port of the Python editor's `draw_vastu_grid` /
 * `draw_vastu_division_lines` (re-expressed as pure data, no canvas).
 */

/** Clockwise-from-North compass labels for each zone count. */
const DIRS_8 = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
const DIRS_16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
const DIRS_32 = [
  'N', 'NbE', 'NNE', 'NEbN', 'NE', 'NEbE', 'ENE', 'EbN',
  'E', 'EbS', 'ESE', 'SEbE', 'SE', 'SEbS', 'SSE', 'SbE',
  'S', 'SbW', 'SSW', 'SWbS', 'SW', 'SWbW', 'WSW', 'WbS',
  'W', 'WbN', 'WNW', 'NWbW', 'NW', 'NWbN', 'NNW', 'NbW',
];

/** Traditional Vedic (Sanskrit) names for the 8 principal directions, clockwise from North. */
const VEDIC_8 = ['Kubera', 'Ishanya', 'Indra', 'Agni', 'Yama', 'Nairutya', 'Varuna', 'Vayavya'];

function labelsFor(count: VastuZoneCount, mode: VastuChakraMode): string[] {
  if (count === 8) return mode === 'vedic' ? VEDIC_8 : DIRS_8;
  // ponytail: Vedic pada names for 16/32 aren't tabulated here — fall back to compass labels.
  return count === 16 ? DIRS_16 : DIRS_32;
}

export interface ZoneGrid {
  center: Point2D;
  /** Division line segments from the center to the boundary, one per sector edge. */
  divisions: { a: Point2D; b: Point2D }[];
  /** Per-zone label text + anchor point. */
  labels: { text: string; at: Point2D }[];
}

/**
 * Cast a ray from `origin` in direction `dir` (unit) and return the distance to the nearest
 * boundary-polygon edge, or a large fallback when the origin is outside/degenerate.
 */
function rayToBoundary(origin: Point2D, dir: Point2D, poly: Point2D[], fallback: number): number {
  let best = Infinity;
  const n = poly.length;
  for (let i = 0; i < n; i++) {
    const p1 = poly[i];
    const p2 = poly[(i + 1) % n];
    const ex = p2.x - p1.x;
    const ey = p2.y - p1.y;
    // Solve origin + t*dir = p1 + u*edge, 0<=u<=1, t>0.
    const denom = dir.x * ey - dir.y * ex;
    if (Math.abs(denom) < 1e-9) continue; // parallel
    const dx = p1.x - origin.x;
    const dy = p1.y - origin.y;
    const t = (dx * ey - dy * ex) / denom;
    const u = (dx * dir.y - dy * dir.x) / denom;
    if (t > 1e-6 && u >= -1e-6 && u <= 1 + 1e-6) best = Math.min(best, t);
  }
  return Number.isFinite(best) ? best : fallback;
}

export function computeZoneGrid(
  boundary: Point2D[],
  center: Point2D,
  zoneCount: VastuZoneCount,
  northDeg: number,
  mode: VastuChakraMode
): ZoneGrid {
  const labels = labelsFor(zoneCount, mode);
  const span = (2 * Math.PI) / zoneCount;
  // North = world +Y (90°); northDeg rotates the rose clockwise.
  const northAngle = Math.PI / 2 - (northDeg * Math.PI) / 180;
  const fallback = boundary.reduce((m, p) => Math.max(m, Math.hypot(p.x - center.x, p.y - center.y)), 100) * 1.1;

  const divisions: { a: Point2D; b: Point2D }[] = [];
  const outLabels: { text: string; at: Point2D }[] = [];

  for (let k = 0; k < zoneCount; k++) {
    // Division edge angle sits between sector k and k+1 (clockwise → subtract).
    const edgeAngle = northAngle - (k + 0.5) * span;
    const ed = { x: Math.cos(edgeAngle), y: Math.sin(edgeAngle) };
    const edLen = rayToBoundary(center, ed, boundary, fallback);
    divisions.push({ a: center, b: { x: center.x + ed.x * edLen, y: center.y + ed.y * edLen } });

    // Label at the sector center angle, ~0.72 of the way to the boundary.
    const labelAngle = northAngle - k * span;
    const ld = { x: Math.cos(labelAngle), y: Math.sin(labelAngle) };
    const lLen = rayToBoundary(center, ld, boundary, fallback) * 0.72;
    outLabels.push({ text: labels[k] ?? '', at: { x: center.x + ld.x * lLen, y: center.y + ld.y * lLen } });
  }

  return { center, divisions, labels: outLabels };
}
