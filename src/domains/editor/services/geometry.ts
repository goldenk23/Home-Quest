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
export { planTo3D as world2DTo3D } from '@/domains/viewer/services/transform';