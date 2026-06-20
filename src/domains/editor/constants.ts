/*
 * ============================================================================
 * WHAT IS THIS FILE FOR?
 * ============================================================================
 * 
 * This file holds the visual "paint" and styling rules for our 2D floor plan 
 * editor. Instead of scattering colors and sizes throughout our code, we keep 
 * them all right here. If you ever want to change how thick a wall looks, or 
 * the color of a bedroom, this is the only file you need to update!
 *
 * THE MENTAL MODEL:
 * 
 * 1. Real-World Sizes: Every number here (like wallStrokeWidth or vertexRadius) 
 *    is measured in real-world Centimeters (cm). Our zoom engine automatically 
 *    scales everything for the screen!
 * 2. See-Through Colors: Room colors are intentionally made slightly transparent
 *    (low saturation) so you can still easily see walls and furniture on top.
 *
 * DIAGRAM: HOW THIS FILE FEEDS THE CANVAS
 *
 *     [ Real-World Centimeters ] ------+
 *                                      |
 *     [ Theme Colors ] ----------------+-----> [ This File (constants.ts) ]
 *                                      |                    |
 *     [ Room Types ] ------------------+                    |
 *                                                           | (Provides styles to)
 *                                                           v
 *    +-----------------------------------------------------------------+
 *    |                         EDITOR CANVAS                           |
 *    |                                                                 |
 *    |  [SelectionLayer] <-- Uses selectionStroke & glow               |
 *    |  [FurnitureLayer]                                               |
 *    |  [WallLayer]      <-- Uses wallFill, wallStroke, vertexRadius   |
 *    |  [RoomLayer]      <-- Uses ROOM_FILL_COLORS (bedroom, kitchen)  |
 *    |  [GridLayer]                                                    |
 *    +-----------------------------------------------------------------+
 * ============================================================================
 */

import type { RoomType } from '@/types/editor';

/**
 * Visual styling for the 2D editor layers.
 * All sizes are in WORLD units (centimeters) unless noted, because layers render
 * inside the zoom/pan <g> transform where 1 unit = 1 cm.
 */
export const EDITOR_STYLE = {
  /** Wall fill color (walls are filled quads, not stroked lines). */
  wallFill: '#e5e7eb',
  wallStroke: '#9ca3af',
  wallStrokeWidth: 1, // cm

  /** Vertex dots drawn at wall junctions. */
  vertexRadius: 4, // cm
  vertexFill: '#60a5fa',

  /** Selection highlight. */
  selectionStroke: '#f59e0b',
  selectionStrokeWidth: 3, // cm
  selectionGlow: 'rgba(245, 158, 11, 0.25)',

  /** Live drawing preview line (Part 6). */
  previewStroke: '#34d399',
  previewStrokeWidth: 2, // cm
  previewDash: '12 8', // dash pattern in cm
} as const;

/**
 * Fill color per room type. Used by RoomLayer to tint room polygons so a glance
 * communicates layout. Colors are intentionally low‑saturation so walls/furniture
 * stay legible on top.
 */
export const ROOM_FILL_COLORS: Record<RoomType, string> = {
  living: 'rgba(96, 165, 250, 0.18)',
  bedroom: 'rgba(167, 139, 250, 0.18)',
  kitchen: 'rgba(251, 146, 60, 0.18)',
  bathroom: 'rgba(45, 212, 191, 0.18)',
  puja: 'rgba(250, 204, 21, 0.20)',
  study: 'rgba(129, 140, 248, 0.18)',
  dining: 'rgba(248, 113, 113, 0.16)',
  storage: 'rgba(148, 163, 184, 0.18)',
  garage: 'rgba(100, 116, 139, 0.18)',
  balcony: 'rgba(74, 222, 128, 0.16)',
  entrance: 'rgba(244, 114, 182, 0.16)',
  corridor: 'rgba(203, 213, 225, 0.14)',
  custom: 'rgba(148, 163, 184, 0.14)',
};