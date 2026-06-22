
import type { Point2D } from '@/types/geometry';

export interface SnapConfig {
    /** Grid cell size in world units (cm) */
    gridSize: number;

    /** Maximum snap distance in world units (cm) */
    snapRadius: number;

    /** Whether grid snapping is enabled */
    gridEnabled: boolean;

    /** Whether endpoint snapping is enabled */
    endpointEnabled: boolean;
}

const defaultSnapConfig: SnapConfig = {
    gridSize: 10,      // 10 cm grid cells
    snapRadius: 15,    // snap within 15 cm
    gridEnabled: true,
    endpointEnabled: true,
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
 * Combined snapping pipeline.
 * Priority: endpoint snap > angle snap > grid snap > raw position.
 * 
 * Endpoint snapping takes priority because connecting walls
 * at exact shared vertices is essential for room detection.
 */
export function applySnapping(
    rawPoint: Point2D,
    endpoints: readonly Point2D[],
    config: SnapConfig = defaultSnapConfig,
    origin: Point2D | null = null,
    shiftPressed: boolean = false
): Point2D {
    // 1. Endpoint Snapping (Highest Priority)
    if (config.endpointEnabled) {
        const snapped = snapToEndpoints(rawPoint, endpoints, config.snapRadius);
        if (snapped !== rawPoint) return snapped;
    }

    let pointToSnap = rawPoint;

    // 2. Angle Snapping (If we have a start point)
    // Snap to 15 degree increments if holding Shift, or if close to 90 degree increments automatically.
    if (origin) {
        const dx = rawPoint.x - origin.x;
        const dy = rawPoint.y - origin.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance > 0) {
            let angle = Math.atan2(dy, dx);
            // Convert to degrees for easier math
            let angleDeg = angle * (180 / Math.PI);
            
            // Snap to nearest 15 degrees if shift is pressed, otherwise snap to 90 degree axes if within 5 degrees
            if (shiftPressed) {
                angleDeg = Math.round(angleDeg / 15) * 15;
            } else {
                const nearest90 = Math.round(angleDeg / 90) * 90;
                if (Math.abs(angleDeg - nearest90) < 5) {
                    angleDeg = nearest90;
                } else {
                    const nearest45 = Math.round(angleDeg / 45) * 45;
                    if (Math.abs(angleDeg - nearest45) < 3) {
                        angleDeg = nearest45;
                    }
                }
            }

            // Convert back to radians and apply
            const snappedAngle = angleDeg * (Math.PI / 180);
            pointToSnap = {
                x: origin.x + Math.cos(snappedAngle) * distance,
                y: origin.y + Math.sin(snappedAngle) * distance
            };
        }
    }

    // 3. Grid Snapping
    if (config.gridEnabled) {
        return snapPoint(pointToSnap, config.gridSize);
    }

    return pointToSnap;
}
export {}; // Makes the file a valid module