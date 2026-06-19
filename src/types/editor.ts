import type { Point2D } from '@/types/geometry';

/** Unique identifier for all entities */
export type EntityId = string;

/** A vertex in the floor plan graph */
export interface Vertex {
  readonly id: EntityId;
  readonly position: Point2D;
  /** IDs of walls connected to this vertex (mutable via Immer drafts) */
  connectedWalls: EntityId[];
}

/** A wall segment connecting two vertices */
export interface Wall {
  readonly id: EntityId;
  readonly startVertexId: EntityId;
  readonly endVertexId: EntityId;
  /** Wall thickness in centimeters */
  readonly thickness: number;
  /** Wall height in centimeters */
  readonly height: number;
  /** Material identifier for 3D rendering */
  readonly materialId: string;
  /** Whether this is a load-bearing wall (affects Vastu) */
  readonly isLoadBearing: boolean;
}

/** 
 * A room is a closed polygon formed by connected walls.
 * Stored as an ordered list of vertex IDs forming the boundary.
 */
export interface Room {
  readonly id: EntityId;
  /** Ordered vertex IDs forming closed polygon (first ≠ last; closure implied) */
  readonly boundaryVertexIds: readonly EntityId[];
  /** Room type affects Vastu scoring */
  readonly roomType: RoomType;
  /** Display name */
  readonly label: string;
  /** Floor material for 3D */
  readonly floorMaterialId: string;
}

export type RoomType =
  | 'living'
  | 'bedroom'
  | 'kitchen'
  | 'bathroom'
  | 'puja'
  | 'study'
  | 'dining'
  | 'storage'
  | 'garage'
  | 'balcony'
  | 'entrance'
  | 'corridor'
  | 'custom';

/** A placed furniture item */
export interface FurnitureItem {
  readonly id: EntityId;
  /** Position in 2D world space (center point) */
  readonly position: Point2D;
  /** Rotation in radians around Y-axis */
  readonly rotation: number;
  /** Scale multiplier */
  readonly scale: number;
  /** Reference to asset catalog entry */
  readonly catalogId: string;
  /** Which room this belongs to (for Vastu analysis) */
  readonly roomId: EntityId | null;
  /** Bounding box dimensions in cm (for collision) */
  readonly bounds: { width: number; depth: number };
}

/** Complete floor plan state */
export interface FloorPlan {
  readonly vertices: Record<EntityId, Vertex>;
  readonly walls: Record<EntityId, Wall>;
  readonly rooms: Record<EntityId, Room>;
  readonly furniture: Record<EntityId, FurnitureItem>;
}
