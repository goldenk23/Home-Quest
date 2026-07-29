// src/domains/shared/assets/pythonAssetMap.ts

/**
 * Canonical mapping between the Python "VastuCraft" 2D editor's asset names and this web
 * project's catalog ids + asset paths. ONE source of truth so both the editor (2D symbols,
 * flooring) and the Phase-7 importer resolve references identically.
 *
 * Python furniture is referenced by `image_name` (e.g. "double_bed", "Sofa_Set_with_Centre_Table")
 * and flooring by `flooring_type` (e.g. "wood"). We keep the original Python names verbatim
 * (including case/underscore aliases) so no reference misses.
 */

/** Python furniture `image_name` (and aliases) → web furniture catalog id. */
export const FURNITURE_NAME_TO_CATALOG: Record<string, string> = {
  // Beds
  double_bed: 'bed-queen',
  circular_bed: 'bed-queen',
  bed_with_side_table: 'bed-queen',
  single_bed: 'bed-single',
  // Seating
  sofa: 'sofa-3seat',
  Sofa_Set_with_Centre_Table: 'sofa-3seat',
  sofa_set_with_centre_table: 'sofa-3seat',
  single_sofa: 'armchair',
  Chair: 'dining-chair',
  chair: 'dining-chair',
  // Tables
  coffee_table: 'coffee-table',
  dining_table_4_seat: 'dining-table',
  dining_table_6_seat: 'dining-table',
  dining_table_8_seat: 'dining-table',
  Table_Chair_Set: 'dining-table',
  table_chair_set: 'dining-table',
  Study_Table_Chair: 'desk',
  study_table_chair: 'desk',
  desk: 'desk',
  // Storage
  wardrobe: 'wardrobe',
  Wardrobe: 'wardrobe',
  Standing_Cabinet: 'sideboard',
  standing_cabinet: 'sideboard',
  // Electronics
  tv: 'tv-unit',
  TV: 'tv-unit',
  // Kitchen
  fridge: 'fridge',
  Fridge: 'fridge',
  stove: 'stove',
  sink: 'vanity',
  kitchen_platform: 'kitchen-counter',
  kitchen_platform_2: 'kitchen-counter',
  kitchen_platform_3: 'kitchen-counter',
  kitchen_platform_4: 'kitchen-counter',
  // Bathroom
  Toilet: 'toilet',
  toilet: 'toilet',
  'Bath Tub': 'bathtub',
  bathtub: 'bathtub',
  Bath_Tub: 'bathtub',
  shower: 'shower',
  Wash_Basin: 'vanity',
  Wash_basin: 'vanity',
  wash_basin: 'vanity',
};

/** Web catalog id → top-view 2D symbol PNG (served from /public/furniture-2d). */
export const SYMBOL2D_PATH: Record<string, string> = {
  'sofa-3seat': '/furniture-2d/sofa.png',
  armchair: '/furniture-2d/single-sofa.png',
  'tv-unit': '/furniture-2d/tv.png',
  'tv-unit-doors': '/furniture-2d/tv.png',
  sideboard: '/furniture-2d/standing-cabinet.png',
  'dining-table': '/furniture-2d/dining-table-6-seat.png',
  'dining-round': '/furniture-2d/dining-table-6-seat.png',
  'dining-chair': '/furniture-2d/chair.png',
  'bed-queen': '/furniture-2d/double-bed.png',
  'bed-single': '/furniture-2d/single-bed.png',
  wardrobe: '/furniture-2d/wardrobe.png',
  desk: '/furniture-2d/study-table-chair.png',
  'kitchen-counter': '/furniture-2d/kitchen-platform.png',
  'kitchen-counter-end': '/furniture-2d/kitchen-platform.png',
  stove: '/furniture-2d/stove.png',
  fridge: '/furniture-2d/fridge.png',
  toilet: '/furniture-2d/toilet.png',
  bathtub: '/furniture-2d/bath-tub.png',
  vanity: '/furniture-2d/wash-basin.png',
};

/** Python `flooring_type` → web floor material id (see shared/materials/floorPalette). */
export const FLOORING_TYPE_TO_MATERIAL: Record<string, string> = {
  wood: 'floor-wood',
  Wood: 'floor-wood',
  marble: 'floor-marble',
  Marble: 'floor-marble',
  tile: 'floor-tile',
  Tile: 'floor-tile',
  garden: 'floor-grass',
  grass: 'floor-grass',
  Garden: 'floor-grass',
};
