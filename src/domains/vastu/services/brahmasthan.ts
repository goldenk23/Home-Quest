// src/domains/vastu/services/brahmasthan.ts

import type { Point2D } from '@/types/geometry';
import { computeSignedArea } from '@/domains/editor/services/roomDetection';

/** Average of points — used only as a fallback for degenerate inputs. */
function vertexAverage(points: Point2D[]): Point2D {
  const sum = points.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 });
  return { x: sum.x / points.length, y: sum.y / points.length };
}

/**
 * Area centroid of a polygon (the Brahmasthan). Falls back to a vertex average for
 * polygons with <3 points or (near-zero) area.
 */
export function calculateBrahmasthan(boundary: Point2D[]): Point2D {
  if (boundary.length < 3) return vertexAverage(boundary);

  const area = computeSignedArea(boundary);
  if (Math.abs(area) < 1e-10) return vertexAverage(boundary);

  let cx = 0;
  let cy = 0;
  const n = boundary.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const cross = boundary[i].x * boundary[j].y - boundary[j].x * boundary[i].y;
    cx += (boundary[i].x + boundary[j].x) * cross;
    cy += (boundary[i].y + boundary[j].y) * cross;
  }
  const factor = 1 / (6 * area);
  return { x: cx * factor, y: cy * factor };
}

/**
 * The central Brahmasthan zone (kept open in Vastu). Returns a center + radius, where the
 * radius is one-third of the distance to the nearest boundary edge.
 */
export function calculateBrahmasthanZone(boundary: Point2D[], center: Point2D): { center: Point2D; radius: number } {
  let minDist = Infinity;
  const n = boundary.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    minDist = Math.min(minDist, pointToSegmentDistance(center, boundary[i], boundary[j]));
  }
  return { center, radius: minDist / 3 };
}

function pointToSegmentDistance(p: Point2D, a: Point2D, b: Point2D): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y);
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}
