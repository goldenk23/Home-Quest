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
