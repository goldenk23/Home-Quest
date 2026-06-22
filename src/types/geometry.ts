/** Immutable 2D point in world space (centimeters) */

// interface enforceas what proerties an object must have.
// readonly enforces that the properties cannot be changed after initialization.
export interface Point2D {
  readonly x: number;
  readonly y: number;
}

/** Immutable 3D point in world space (meters) */
export interface Point3D {
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

/** Screen-space pixel coordinate */
export interface ScreenPoint {
  readonly px: number;
  readonly py: number;
}

/** Immutable 2D rectangle in world space (cent */
export interface ViewTransform {
  readonly scale: number;
  readonly offsetX: number;
  readonly offsetY: number;
}

/** Axis-Aligned Bounding Box — a box whose sides line up with the world axes. */
export interface AABB {
  readonly min: Point2D;
  readonly max: Point2D;
}

/** Oriented Bounding Box — a box that can be rotated (furniture footprint). */
export interface OBB {
  readonly center: Point2D;
  readonly halfExtents: Point2D; // half-width, half-depth
  readonly rotation: number; // radians
}
