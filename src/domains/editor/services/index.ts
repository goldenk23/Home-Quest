// src/domains/editor/services/index.ts — public API
//
// Domains talk through these barrels, never by importing another domain's component
// directly. Export names use the corrected names from Installment 1.

export { computeWallQuad } from './geometry';
export { detectRooms, computeSignedArea, validateRoomPolygon } from './roomDetection';
export { findWallIntersections, splitWallAtPoint, computeCornerAngles } from './wallOps';
export { applySnapping, snapPoint, snapToEndpoints } from '../hooks/useSnapping';
export {
  aabbOverlaps,
  obbIntersects,
  furnitureToAABB,
  SpatialHashGrid,
  checkFurnitureCollisions,
  wallToOBB,
  furnitureIntersectsAnyWall,
} from './collision';
