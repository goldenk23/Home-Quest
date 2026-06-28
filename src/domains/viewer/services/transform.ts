// src/domains/viewer/services/transform.ts

import type { Point2D, Point3D } from '@/types/geometry';
import * as THREE from 'three';

const CM_TO_M = 0.01;

/**
 * The core mapping: a 2D plan point (centimeters, Y‑up/north) → a 3D world point
 * (meters). 2D‑Y becomes 3D‑(−Z) so "north on the plan" stays "north in 3D" while
 * keeping Three.js's right‑handed system. `elevationCm` lifts the point onto the Y axis
 * (floors at 0, wall tops at the wall height, etc.).
 */
export function planTo3D(point: Point2D, elevationCm = 0): Point3D {
  return { x: point.x * CM_TO_M, y: elevationCm * CM_TO_M, z: -point.y * CM_TO_M };
}

/** Inverse of planTo3D (drops the vertical/elevation component). */
export function threeDToPlan(point: Point3D): Point2D {
  const M_TO_CM = 1 / CM_TO_M;
  return { x: point.x * M_TO_CM, y: -point.z * M_TO_CM };
}

/** Convenience: a Three.js Vector3 straight from a plan point. */
export function planToVec3(point: Point2D, elevationCm = 0): THREE.Vector3 {
  return new THREE.Vector3(point.x * CM_TO_M, elevationCm * CM_TO_M, -point.y * CM_TO_M);
}

/**
 * Height (m) a player stands at on a straight staircase, or null if they're outside its
 * footprint. The stair is an oriented box on the plan: centre (cx, cz) in 3D metres,
 * `rotationY` radians about Y, half-extents `halfW` (local-X / width) and `halfD` (local-Z /
 * ascent). It climbs `riseM` above `baseM` along local +Z, so local z = -halfD is the bottom
 * step and +halfD the top — matching the StairsPrefab geometry.
 */
export function stairRampHeightAt(
  x: number,
  z: number,
  cx: number,
  cz: number,
  rotationY: number,
  halfW: number,
  halfD: number,
  baseM: number,
  riseM: number
): number | null {
  if (halfD <= 0 || halfW <= 0) return null;
  const cos = Math.cos(rotationY);
  const sin = Math.sin(rotationY);
  const vx = x - cx;
  const vz = z - cz;
  const lx = vx * cos - vz * sin; // local width axis
  const lz = vx * sin + vz * cos; // local ascent axis (+Z = top)
  if (Math.abs(lx) > halfW || Math.abs(lz) > halfD) return null;
  const progress = (lz + halfD) / (2 * halfD); // 0 bottom (-Z) → 1 top (+Z)
  return baseM + progress * riseM;
}

/**
 * Builds a THREE.Shape from a room polygon, in meters.
 *
 * The shape is created in its own 2D space using (x, y). When the resulting mesh is laid
 * flat with rotation [-π/2, 0, 0], a shape point (x, y) lands at world (x, 0, −y) — which
 * is exactly what planTo3D produces. So floors built this way line up perfectly with walls.
 */
export function polygonToShape(vertices: Point2D[]): THREE.Shape {
  const shape = new THREE.Shape();
  if (vertices.length === 0) return shape;
  shape.moveTo(vertices[0].x * CM_TO_M, vertices[0].y * CM_TO_M);
  for (let i = 1; i < vertices.length; i++) {
    shape.lineTo(vertices[i].x * CM_TO_M, vertices[i].y * CM_TO_M);
  }
  shape.closePath();
  return shape;
}

/** Twice the signed area of a plan polygon (sign = winding: >0 one way, <0 the other). */
function signedArea2(poly: Point2D[]): number {
  let s = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    s += (poly[j].x - poly[i].x) * (poly[j].y + poly[i].y);
  }
  return s;
}

/** Ray-casting point-in-polygon test (point and polygon in the same plan units). */
export function pointInPolygon(p: Point2D, poly: Point2D[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y, xj = poly[j].x, yj = poly[j].y;
    if (yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/**
 * The four plan-cm corners of a straight staircase's footprint. The stair is an oriented box
 * on the plan centred at (cx, cy), rotated `rotationY` about Y, with half-extents `halfWcm`
 * (local width / X) and `halfDcm` (local ascent / Z). Same convention as stairRampHeightAt
 * and the StairsPrefab, so the footprint lines up with the rendered flight.
 */
export function stairFootprint(
  cx: number,
  cy: number,
  rotationY: number,
  halfWcm: number,
  halfDcm: number
): Point2D[] {
  const cos = Math.cos(rotationY);
  const sin = Math.sin(rotationY);
  const corner = (sx: number, sz: number): Point2D => ({
    x: cx + sx * halfWcm * cos + sz * halfDcm * sin,
    y: cy + sx * halfWcm * sin - sz * halfDcm * cos,
  });
  return [corner(-1, -1), corner(1, -1), corner(1, 1), corner(-1, 1)];
}

/**
 * Builds a flat THREE.Shape for `polygon` (plan cm → m) with each polygon in `holes` punched
 * through it (e.g. a stairwell void cut in a floor/ceiling slab). Holes are re-wound opposite
 * to the outer ring so the triangulator subtracts them cleanly. Holes are assumed to lie
 * fully inside the polygon; a hole that crosses the boundary is the caller's responsibility
 * to filter out (see pointInPolygon).
 */
export function shapeWithHoles(polygon: Point2D[], holes: Point2D[][] = []): THREE.Shape {
  const shape = polygonToShape(polygon);
  const outerSign = Math.sign(signedArea2(polygon)) || 1;
  for (const hole of holes) {
    if (hole.length < 3) continue;
    const ring = Math.sign(signedArea2(hole)) === outerSign ? [...hole].reverse() : hole;
    const path = new THREE.Path();
    path.moveTo(ring[0].x * CM_TO_M, ring[0].y * CM_TO_M);
    for (let i = 1; i < ring.length; i++) path.lineTo(ring[i].x * CM_TO_M, ring[i].y * CM_TO_M);
    path.closePath();
    shape.holes.push(path);
  }
  return shape;
}

/** Stable string key for a hole set, for memoising geometry that depends on it. */
export function holesKey(holes: Point2D[][] = []): string {
  return holes.map((h) => h.map((p) => `${Math.round(p.x)},${Math.round(p.y)}`).join(' ')).join('|');
}

/**
 * Where a storey's ceiling slab sits: resting on the wall tops and filling up to the floor
 * above (`ceilingTopCm`, measured from this floor's base). The slab's top always lands flush
 * at `ceilingTopCm` so the floor above sits on it with no gap; `minThicknessCm` keeps it from
 * collapsing when the walls already reach the gap. Returns cm in the floor's local space.
 */
export function ceilingSlabRange(
  wallTopCm: number,
  ceilingTopCm: number,
  minThicknessCm = 8
): { baseCm: number; thicknessCm: number } {
  const baseCm = Math.max(0, Math.min(wallTopCm, ceilingTopCm - minThicknessCm));
  return { baseCm, thicknessCm: ceilingTopCm - baseCm };
}
