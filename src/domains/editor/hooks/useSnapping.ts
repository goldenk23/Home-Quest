
import type { Point2D } from '@/types/geometry';

export interface SnapConfig {
    /** Grid cell size in world units (cm) */
    gridSize: number;

    /** Maximum snap distance for snapping to grid cells, in world units (cm) */
    snapRadius: number;

    /** Whether Grid snapping is enabled  */
    gridSnapEnabled: boolean;

    /** Whether endpoint snapping is enabled  */
    endpointSnapEnabled: boolean;
}

const defaultSnapConfig: SnapConfig = {
    gridSize: 10,// 10 cm grid cells
    snapRadius:15,// 15 cm snap radius
    gridSnapEnabled: true,
    endpointSnapEnabled: true
};

/**
 * Snap a point to the nearest grid point and/or vertex(grid intersection), based on the provided snapping configuration.
 * 
 * Algorithm: Round to nearest multiple of gridSize
 * 
 * This uses Math.round rather than Math.floor to ensure
 * the point snaps to the NEAREST intersection, not always
 * the lower-left one.
 * 
 * EXAMPLE:
 * x = Math.round(23 / 10) * 10
  = Math.round(2.3) * 10
  = 2 * 10
  = 20

y = Math.round(37 / 10) * 10
  = Math.round(3.7) * 10
  = 4 * 10
  = 40
 */

  export function snapPoint(point: Point2D, gridSize: number): Point2D {
    return {
        x: Math.round(point.x / gridSize) * gridSize,
        y: Math.round(point.y / gridSize) * gridSize
    };
  }

  /**
 * Snaps to the nearest existing endpoint(existing point already placed in the drawing) within snapRadius.
 * Returns the original point if no endpoint is close enough.
 *
 * Uses squared distance comparison to avoid sqrt per candidate.
 * For large point sets (>1000), replace with spatial index (grid hash).
 */
 export function snapToEndpoints(
    point: Point2D,
    endpoints: readonly Point2D[],// readonly means we won't modify this array
    snapRadius: number
 ): Point2D {
    const radiusSq= snapRadius * snapRadius;
    let closestPoint: Point2D | null = null;
    let closestDistSq = radiusSq; 

    for(const endpoint of endpoints) {
        const dx = endpoint.x - point.x;
        const dy = endpoint.y - point.y;
        const distSq = dx * dx + dy * dy;

        if(distSq < closestDistSq){
            closestDistSq = distSq;
            closestPoint = endpoint;
        }
    }
    return closestPoint ?? point;// If we found a close enough endpoint, return it; otherwise return the original point
 }

 /**
  * combine both snapping methods: Priority: endpoint snap > grid snap > raw position
  */
 export function applySnapping(
    rawpoint: Point2D,
    endpoints: readonly Point2D[],
    config: SnapConfig = defaultSnapConfig
 ): Point2D {
    if(config.endpointSnapEnabled){
        const endpointSnapped = snapToEndpoints(rawpoint, endpoints, config.snapRadius);
        if(endpointSnapped !== rawpoint){
            return endpointSnapped;
        }
    }
    if(config.gridSnapEnabled){
        return snapPoint(rawpoint, config.gridSize);
    }
    return rawpoint;
 }
export {}; // Makes the file a valid module