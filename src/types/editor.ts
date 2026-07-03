import type { Point2D } from '@/types/geometry';

/** Unique identifier for all entities */
export type EntityId = string;

/** A vertex in the floor plan graph */
export interface Vertex {
  readonly id: EntityId;
  readonly position: Point2D;
  /** IDs of walls connected to this vertex (mutable via Immer drafts) */
  connectedWalls: EntityId[];// This is actually an array of walls to which the current vertex is associated. 
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
  /** Material identifier for 3D rendering. Acts as the base/fallback finish for the whole
   *  wall and for any face that hasn't been painted individually. */
  readonly materialId: string;
  /**
   * Optional per-face paint. A wall has two large faces; painting from inside a room only
   * colours the face toward that room. Side A is the wall's +normal face (plan direction
   * (dy,-dx), i.e. local +z in 3D); side B is the −normal face. When unset, the face falls
   * back to `materialId` so legacy plans and unpainted faces render exactly as before.
   */
  readonly materialSideA?: string;
  readonly materialSideB?: string;
  /** Whether this is a load-bearing wall (affects Vastu) */
  readonly isLoadBearing: boolean;
  /** IDs of openings (doors, windows, vents) on this wall */
  readonly openingIds: EntityId[];
}

/** 
 * A road / paved path for exterior landscaping. Unlike walls, a road is a standalone
 * segment (not part of the vertex graph): a centerline from `start` to `end` with a width,
 * rendered as flat paving on the ground.
 */
export interface Road {
  readonly id: EntityId;
  readonly start: Point2D;
  readonly end: Point2D;
  /** Road width in centimeters. */
  readonly width: number;
}

/** A free-standing structural vertical member for columns/pillars. */
export interface Pillar {
  readonly id: EntityId;
  /** Centre point in 2D world space (cm). */
  position: Point2D;
  /** Footprint width in centimeters. */
  width: number;
  /** Footprint depth in centimeters. */
  depth: number;
  /** Vertical height in centimeters. */
  height: number;
  /** Base offset above the current storey's floor in centimeters. */
  elevationCm: number;
  /** Rectangular or circular column. */
  shape: 'rect' | 'round';
  /** Finish/material id; currently reuses wall finishes. */
  materialId: string;
}

/** A horizontal structural member connecting supports/walls at an elevation. */
export interface Beam {
  readonly id: EntityId;
  start: Point2D;
  end: Point2D;
  width: number;
  depth: number;
  elevationCm: number;
  materialId: string;
}

/** A custom exterior/interior horizontal slab/deck such as corridor, balcony, roof, or landing. */
export interface DeckSlab {
  readonly id: EntityId;
  polygon: Point2D[];
  thicknessCm: number;
  elevationCm: number;
  materialId: string;
  type: 'corridor' | 'balcony' | 'landing' | 'roof' | 'custom';
}

/** A safety railing/parapet for balconies, decks, stairs, or elevated areas. */
export interface Railing {
  readonly id: EntityId;
  start: Point2D;
  end: Point2D;
  height: number;
  elevationCm: number;
  style: 'open' | 'solid';
  materialId: string;
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

export type OpeningType = 'door' | 'window' | 'vent' | 'ac';

/** A wall opening or wall-mounted element (door, window, vent, or AC) */
export interface Opening {
  readonly id: EntityId;
  readonly wallId: EntityId;
  readonly type: OpeningType;
  /**
   * Specific kind id from the opening catalog (e.g. 'window-sliding', 'door-main-gate',
   * 'vent-kitchen', 'ac-split'). Optional for backward compatibility with plans saved
   * before kinds existed — renderers fall back to a default for the base `type`.
   */
  readonly kind?: string;
  /** Distance from the wall's startVertex in cm */
  readonly offsetCm: number;
  /** Width of the hole in cm */
  readonly width: number;
  /** Height of the hole in cm */
  readonly height: number;
  /** Elevation from floor in cm (0 for doors) */
  readonly elevation: number;
}

/** Complete floor plan state */
export interface FloorPlan {
  readonly vertices: Record<EntityId, Vertex>;
  readonly walls: Record<EntityId, Wall>;
  readonly rooms: Record<EntityId, Room>;
  readonly furniture: Record<EntityId, FurnitureItem>;
  readonly openings: Record<EntityId, Opening>;
  readonly pillars: Record<EntityId, Pillar>;
  readonly beams: Record<EntityId, Beam>;
  readonly deckSlabs: Record<EntityId, DeckSlab>;
  readonly railings: Record<EntityId, Railing>;
}

/**
 * A storey of the building. The geometry of each floor (vertices/walls/rooms/…) is stored
 * separately (see the floors slice); a `Floor` is just its identity + where it sits
 * vertically. `elevationCm` is the base height of this storey's ground above the building
 * base (ground floor = 0), so the 3D view can stack floors on top of each other.
 */
export interface Floor {
  readonly id: EntityId;
  name: string;
  /** Base elevation of this storey's floor in cm (ground floor = 0). */
  elevationCm: number;
}

/** The full geometry of a single floor — the parked/serialized form of one storey. */
export interface FloorGeometry {
  vertices: Record<EntityId, Vertex>;
  walls: Record<EntityId, Wall>;
  rooms: Record<EntityId, Room>;
  furniture: Record<EntityId, FurnitureItem>;
  openings: Record<EntityId, Opening>;
  roads: Record<EntityId, Road>;
  stairs: Record<EntityId, import('./stair').StairEntity>;
  pillars: Record<EntityId, Pillar>;
  beams: Record<EntityId, Beam>;
  deckSlabs: Record<EntityId, DeckSlab>;
  railings: Record<EntityId, Railing>;
}
