// src/types/index.ts — public type barrel
// Lets modules import shared types from a single path (`@/types`).

export type {
  Point2D,
  Point3D,
  ScreenPoint,
  ViewTransform,
  AABB,
  OBB,
} from './geometry';

export type {
  EntityId,
  Vertex,
  Wall,
  Room,
  RoomType,
  FurnitureItem,
  OpeningType,
  Opening,
  Pillar,
  Beam,
  DeckSlab,
  FloorPlan,
  Floor,
  FloorGeometry,
} from './editor';
