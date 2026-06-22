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
  'sofa-3seat': { label: 'Sofa (3-seat)', color: '#8b6f47', bounds: { width: 200, depth: 90, height: 80 } },
  'dining-table': { label: 'Dining Table', color: '#9c6b3f', bounds: { width: 150, depth: 90, height: 75 } },
  'bed-queen': { label: 'Queen Bed', color: '#6b7280', bounds: { width: 160, depth: 210, height: 60 } },
  'chair-office': { label: 'Office Chair', color: '#374151', bounds: { width: 60, depth: 60, height: 110 } },
  'toilet': { label: 'Toilet', color: '#e5e7eb', bounds: { width: 40, depth: 70, height: 80 } },
  'kitchen-counter': { label: 'Kitchen Counter', color: '#4b5563', bounds: { width: 200, depth: 60, height: 90 } },
};

/** Convenience: ordered list of catalog ids for building UI menus. */
export const FURNITURE_CATALOG_IDS = Object.keys(FURNITURE_CATALOG);

/** Returns the catalog entry for an id, falling back to the sofa if unknown. */
export function getCatalogEntry(catalogId: string): FurnitureCatalogEntry {
  return FURNITURE_CATALOG[catalogId] ?? FURNITURE_CATALOG['sofa-3seat'];
}
