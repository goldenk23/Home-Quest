// eslint-disable-next-line @typescript-eslint/no-unused-vars

/**
 * Coordinate System Reference:
 *
 * | Space | Origin | Units | Y-Axis | Used By |
 * |-------|--------|-------|--------|---------|
 * | Screen Space | Top-left viewport | Pixels | Down | Mouse events, DOM |
 * | World Space (2D) | Center of canvas | Centimeters | Up | Floor plan model |
 * | World Space (3D) | Ground center | Meters | Up (Y in Three.js) | 3D scene |
 */

import type { Point2D, ScreenPoint, ViewTransform } from '../../../types/geometry';


export interface wallQuad {
    readonly topLeft: Point2D;
    readonly topRight: Point2D;
    readonly bottomLeft: Point2D;
    readonly bottomRight: Point2D;
}

/**
 *  convert screen pixel coordinates to world space coordinates
 */

/**
 * Browser Window
    +----------------------------------+
    |                                  |
    |  left = 100px                    |
    |      ↓                           |
    |      +-------------------+       |           
    |      |      Canvas       |       |
    |      +-------------------+       |
    |                                  |
    +----------------------------------+
 */


/**
 * Browser Window
  +----------------------------------+
  |                                  |
  |                                  |
  |  top = 50px                      |
  |      ↓                           |
  |      +-------------------+       |
  |      |      Canvas       |       |
  |      +-------------------+       |
  +----------------------------------+
 */
export function screenToWorld(
    screenPoint: ScreenPoint,
    canvasRect: DOMRect,// this is the bounding rectangle of the canvas element, which provides the position and size of the canvas in screen space
    viewTransform: ViewTransform
): Point2D {
    // Implementation for converting screen coordinates to world coordinates
    return {
        x: (screenPoint.px - canvasRect.left - viewTransform.offsetX) / viewTransform.scale,
        y: -(screenPoint.py - canvasRect.top - viewTransform.offsetY) / viewTransform.scale
    };
}


/**
 * convert 2D world coordinate back to screen pixel
 */

export function worldToScreen(
    world: Point2D,
    canvasRect: DOMRect,
    view: ViewTransform
): ScreenPoint {
    return {
        px: world.x * view.scale + view.offsetX + canvasRect.left,
        py: -world.y * view.scale + view.offsetY + canvasRect.top,
    };
}


import type { MiterOffsets } from './wallOps';

export function computeWallQuad(
    start: Point2D,
    end: Point2D,
    thickness: number,
    offsets?: MiterOffsets
): wallQuad {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.sqrt(dx * dx + dy * dy);

    if (length === 0) {
        // Degenerate wall (zero length) — return collapsed quad
        return {
            topLeft: start,
            topRight: start,
            bottomRight: start,
            bottomLeft: start,
        };
    }

    // Unit direction vector
    const vx = dx / length;
    const vy = dy / length;

    // Perpendicular unit vector (rotate direction 90° CCW)
    const nx = -vy;
    const ny = vx;

    const halfThick = thickness / 2;

    const sLeft = offsets?.startLeft ?? 0;
    const sRight = offsets?.startRight ?? 0;
    const eLeft = offsets?.endLeft ?? 0;
    const eRight = offsets?.endRight ?? 0;

    return {
        topLeft: { 
            x: start.x + nx * halfThick + vx * sLeft, 
            y: start.y + ny * halfThick + vy * sLeft 
        },
        topRight: { 
            x: end.x + nx * halfThick - vx * eRight, 
            y: end.y + ny * halfThick - vy * eRight 
        },
        bottomRight: { 
            x: end.x - nx * halfThick - vx * eLeft, 
            y: end.y - ny * halfThick - vy * eLeft 
        },
        bottomLeft: { 
            x: start.x - nx * halfThick + vx * sRight, 
            y: start.y - ny * halfThick + vy * sRight 
        },
    };
}

export { planTo3D as world2DTo3D } from '@/domains/viewer/services/transform';