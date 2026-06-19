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


export function computeWallQuad(
    start: Point2D,
    end: Point2D,
    thickness: number
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

    // Perpendicular unit vector (rotate direction 90° CCW)
    const nx = -dy / length;
    const ny = dx / length;

    const halfThick = thickness / 2;

    return {
        topLeft: { x: start.x + nx * halfThick, y: start.y + ny * halfThick },
        topRight: { x: end.x + nx * halfThick, y: end.y + ny * halfThick },
        bottomRight: { x: end.x - nx * halfThick, y: end.y - ny * halfThick },
        bottomLeft: { x: start.x - nx * halfThick, y: start.y - ny * halfThick },
    };
}

export { planTo3D as world2DTo3D } from '@/domains/viewer/services/transform';