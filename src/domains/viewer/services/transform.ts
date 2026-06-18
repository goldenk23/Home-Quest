import type { Point2D, Point3D } from '../../../types/geometry';

/**
 * Converts 2D world coordinates (centimeters) to 3D world coordinates (meters).
 * 
 * Mapping:
 *   2D X → 3D X (lateral)
 *   2D Y → 3D Z (depth, negated for right-hand convention)
 *   Height parameter → 3D Y (vertical)
 */
export function planTo3D(point2D: Point2D, heightInMeters: number = 0): Point3D {
  return {
    x: point2D.x / 100, // cm to m
    y: heightInMeters,
    z: -point2D.y / 100, // Negated for Three.js right-hand coordinate system
  };
}
