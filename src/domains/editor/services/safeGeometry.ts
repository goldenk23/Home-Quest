// src/domains/editor/services/safeGeometry.ts
// Guards against NaN/Infinity and out-of-bounds coordinates poisoning the math.

import type { Point2D } from '@/types/geometry';
import { GeometryError } from '@/utils/errors';

const MAX_COORD = 1_000_000; // 10km in cm

/** Throws if a point is non-finite or absurdly far from origin; otherwise returns it. */
export function validatePoint(point: Point2D, label = 'point'): Point2D {
  if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) {
    throw new GeometryError(`Invalid ${label}: non-finite value`, { point, label });
  }
  if (Math.abs(point.x) > MAX_COORD || Math.abs(point.y) > MAX_COORD) {
    throw new GeometryError(`${label} exceeds max coordinate bounds`, { point, maxAllowed: MAX_COORD });
  }
  return point;
}

/** Division that returns a fallback instead of Infinity/NaN. */
export function safeDivide(numerator: number, denominator: number, fallback = 0): number {
  if (Math.abs(denominator) < Number.EPSILON) return fallback;
  const result = numerator / denominator;
  return Number.isFinite(result) ? result : fallback;
}

/** Validates vertex count and that every vertex is finite/in-bounds. */
export function validatePolygon(vertices: Point2D[], minVertices = 3, label = 'polygon'): void {
  if (vertices.length < minVertices) {
    throw new GeometryError(`${label} needs >=${minVertices} vertices, got ${vertices.length}`, { vertexCount: vertices.length, minVertices });
  }
  vertices.forEach((v, i) => validatePoint(v, `${label}[${i}]`));
}

/** Runs a geometry op, returning null (and warning) on GeometryError; re-throws others. */
export function safeGeometryOp<T>(operation: () => T, context: string): T | null {
  try {
    return operation();
  } catch (error) {
    if (error instanceof GeometryError) {
      console.warn(`[Geometry] ${context}:`, error.message, error.context);
      return null;
    }
    throw error;
  }
}
