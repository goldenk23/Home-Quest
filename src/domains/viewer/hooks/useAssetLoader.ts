// src/domains/viewer/hooks/useAssetLoader.ts

/**
 * Furniture catalog — the single source of truth for both the 2D footprint
 * (FurnitureLayer) and the 3D model (FurnitureModel).
 *
 * The original guide loaded GLTF (`.glb`) models via drei's `useGLTF`. Those binary
 * assets were never shipped in `/public/models`, so the furniture pipeline could never
 * actually render. To make the feature real and testable with zero external assets, we
 * render furniture as procedural boxes sized to real-world dimensions (cm) and colored
 * per type. Swapping back to GLTF later only requires changing `FurnitureModel`.
 */

export interface FurnitureCatalogEntry {
  /** Human-friendly name shown in the catalog UI. */
  label: string;
  /** Base color for the procedural 3D box and 2D footprint accent. */
  color: string;
  /** Real-world dimensions in centimeters. */
  bounds: { width: number; depth: number; height: number };
}

export const FURNITURE_CATALOG: Record<string, FurnitureCatalogEntry> = {
  // Living
  'sofa-3seat': { label: 'Sofa (3-seat)', color: '#5f6b7a', bounds: { width: 220, depth: 95, height: 82 } },
  'armchair': { label: 'Accent Chair', color: '#3f7c84', bounds: { width: 80, depth: 82, height: 80 } },
  'coffee-table': { label: 'Coffee Table', color: '#c8a27c', bounds: { width: 110, depth: 60, height: 42 } },
  'tv-unit': { label: 'TV Unit', color: '#15171c', bounds: { width: 180, depth: 40, height: 120 } },
  'sideboard': { label: 'Sideboard', color: '#6f5641', bounds: { width: 150, depth: 42, height: 80 } },
  // Dining
  'dining-table': { label: 'Dining Set', color: '#c8a27c', bounds: { width: 160, depth: 90, height: 75 } },
  'chair-office': { label: 'Office Chair', color: '#2b2f36', bounds: { width: 60, depth: 60, height: 112 } },
  // Bedroom
  'bed-queen': { label: 'Queen Bed', color: '#8a98a8', bounds: { width: 165, depth: 210, height: 55 } },
  'bed-single': { label: 'Single Bed', color: '#8a98a8', bounds: { width: 100, depth: 200, height: 55 } },
  'wardrobe': { label: 'Wardrobe', color: '#6f5641', bounds: { width: 140, depth: 60, height: 210 } },
  'nightstand': { label: 'Nightstand', color: '#c8a27c', bounds: { width: 48, depth: 42, height: 50 } },
  'bookshelf': { label: 'Bookshelf', color: '#6f5641', bounds: { width: 80, depth: 35, height: 190 } },
  // Kitchen
  'kitchen-counter': { label: 'Kitchen Counter', color: '#3b4654', bounds: { width: 240, depth: 62, height: 90 } },
  'fridge': { label: 'Fridge', color: '#c7ccd1', bounds: { width: 72, depth: 70, height: 182 } },
  // Bathroom / Utility
  'toilet': { label: 'Toilet', color: '#f5f5f4', bounds: { width: 42, depth: 68, height: 80 } },
  'shower': { label: 'Shower', color: '#bcd4df', bounds: { width: 95, depth: 95, height: 210 } },
  'vanity': { label: 'Vanity Sink', color: '#3b4654', bounds: { width: 80, depth: 50, height: 90 } },
  'washer': { label: 'Washing Machine', color: '#eef0f2', bounds: { width: 62, depth: 62, height: 85 } },
  // Decor
  'plant': { label: 'Potted Plant', color: '#3f9d57', bounds: { width: 55, depth: 55, height: 145 } },
  'rug': { label: 'Rug', color: '#9aa1ad', bounds: { width: 220, depth: 160, height: 2 } },
};

/** Convenience: ordered list of catalog ids for building UI menus. */
export const FURNITURE_CATALOG_IDS = Object.keys(FURNITURE_CATALOG);

/** Returns the catalog entry for an id, falling back to the sofa if unknown. */
export function getCatalogEntry(catalogId: string): FurnitureCatalogEntry {
  return FURNITURE_CATALOG[catalogId] ?? FURNITURE_CATALOG['sofa-3seat'];
}
