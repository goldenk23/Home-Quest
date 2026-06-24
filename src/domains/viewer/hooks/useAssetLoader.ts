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
  /**
   * Optional path to a real glTF model (served from /public/models). When set, the 3D viewer
   * renders this model — scaled to fit the footprint and grounded — instead of a procedural
   * prefab. When absent, the procedural prefab for this id is used.
   */
  model?: string;
  /**
   * For packed plant files that hold several plants, the index of the individual plant to use.
   * When set, the model is split into its plants and this one is picked; when absent, the whole
   * file is treated as a single object (the normal case for furniture).
   */
  modelVariant?: number;
  /**
   * Optional secondary model rendered resting on TOP of the main model, centred on its footprint
   * (e.g. a television sitting on a TV unit). `widthFrac` scales the topper to that fraction of
   * the item's footprint width (default 0.7) so it looks proportionate.
   */
  topper?: { model: string; widthFrac?: number };
  /** Catalog grouping for the editor palette UI. */
  group?: 'Living' | 'Dining' | 'Bedroom' | 'Kitchen' | 'Bath' | 'Climate' | 'Outdoor' | 'Plants' | 'Decor';
}

const M = '/models';
/** Kenney Furniture Kit (CC0) — low-poly fills for items Poly Haven doesn't offer. */
const K = '/models/kenney';

export const FURNITURE_CATALOG: Record<string, FurnitureCatalogEntry> = {
  // Living
  'sofa-3seat': { label: 'Sofa (3-seat)', color: '#5f6b7a', bounds: { width: 220, depth: 95, height: 82 }, group: 'Living', model: `${M}/Sofa_01/Sofa_01_1k.gltf` },
  'armchair': { label: 'Accent Chair', color: '#3f7c84', bounds: { width: 80, depth: 82, height: 80 }, group: 'Living', model: `${M}/ArmChair_01/ArmChair_01_1k.gltf` },
  'coffee-table': { label: 'Coffee Table', color: '#c8a27c', bounds: { width: 110, depth: 60, height: 42 }, group: 'Living', model: `${M}/CoffeeTable_01/CoffeeTable_01_1k.gltf` },
  'tv-unit': { label: 'TV Unit', color: '#15171c', bounds: { width: 180, depth: 45, height: 55 }, group: 'Living', model: `${K}/tv-unit.glb`, topper: { model: `${K}/television.glb`, widthFrac: 0.72 } },
  'tv-unit-doors': { label: 'TV Unit (Cabinet)', color: '#15171c', bounds: { width: 160, depth: 45, height: 60 }, group: 'Living', model: `${K}/tv-unit-doors.glb`, topper: { model: `${K}/television.glb`, widthFrac: 0.72 } },
  'sideboard': { label: 'Sideboard', color: '#6f5641', bounds: { width: 150, depth: 42, height: 80 }, group: 'Living', model: `${M}/modern_wooden_cabinet/modern_wooden_cabinet_1k.gltf` },
  'ottoman': { label: 'Ottoman', color: '#7c6f63', bounds: { width: 70, depth: 70, height: 42 }, group: 'Living', model: `${M}/Ottoman_01/Ottoman_01_1k.gltf` },
  // Dining
  'dining-table': { label: 'Dining Table', color: '#c8a27c', bounds: { width: 160, depth: 90, height: 75 }, group: 'Dining', model: `${M}/WoodenTable_01/WoodenTable_01_1k.gltf` },
  'dining-round': { label: 'Round Table', color: '#c8a27c', bounds: { width: 120, depth: 120, height: 75 }, group: 'Dining', model: `${M}/round_wooden_table_01/round_wooden_table_01_1k.gltf` },
  'dining-chair': { label: 'Dining Chair', color: '#c8a27c', bounds: { width: 48, depth: 52, height: 92 }, group: 'Dining', model: `${M}/WoodenChair_01/WoodenChair_01_1k.gltf` },
  'bar-stool': { label: 'Bar Stool', color: '#c8a27c', bounds: { width: 40, depth: 40, height: 105 }, group: 'Dining', model: `${M}/bar_chair_round_01/bar_chair_round_01_1k.gltf` },
  'chair-office': { label: 'Office Chair', color: '#2b2f36', bounds: { width: 60, depth: 60, height: 112 }, group: 'Dining' },
  // Bedroom
  'bed-queen': { label: 'Queen Bed', color: '#8a98a8', bounds: { width: 165, depth: 210, height: 120 }, group: 'Bedroom', model: `${M}/GothicBed_01/GothicBed_01_1k.gltf` },
  'bed-single': { label: 'Single Bed', color: '#8a98a8', bounds: { width: 100, depth: 200, height: 55 }, group: 'Bedroom' },
  'wardrobe': { label: 'Wardrobe', color: '#6f5641', bounds: { width: 100, depth: 45, height: 200 }, group: 'Bedroom', model: `${K}/wardrobe.glb` },
  'nightstand': { label: 'Nightstand', color: '#c8a27c', bounds: { width: 48, depth: 42, height: 50 }, group: 'Bedroom', model: `${M}/ClassicNightstand_01/ClassicNightstand_01_1k.gltf` },
  'bookshelf': { label: 'Bookshelf', color: '#6f5641', bounds: { width: 80, depth: 35, height: 190 }, group: 'Bedroom', model: `${M}/wooden_bookshelf_worn/wooden_bookshelf_worn_1k.gltf` },
  // Kitchen
  'kitchen-counter': { label: 'Kitchen Counter', color: '#3b4654', bounds: { width: 100, depth: 62, height: 90 }, group: 'Kitchen', model: `${K}/kitchen-counter.glb` },
  'kitchen-counter-end': { label: 'Counter (End/Corner)', color: '#3b4654', bounds: { width: 62, depth: 62, height: 90 }, group: 'Kitchen', model: `${K}/kitchen-counter-end.glb` },
  'stove': { label: 'Stove / Range', color: '#2b2f36', bounds: { width: 60, depth: 62, height: 92 }, group: 'Kitchen', model: `${M}/electric_stove/electric_stove_1k.gltf` },
  'fridge': { label: 'Fridge', color: '#c7ccd1', bounds: { width: 72, depth: 70, height: 182 }, group: 'Kitchen', model: `${K}/fridge.glb` },
  // Climate
  'ac-split': { label: 'AC (Split Unit)', color: '#ffffff', bounds: { width: 90, depth: 22, height: 30 }, group: 'Climate' },
  // Bathroom / Utility
  'toilet': { label: 'Toilet', color: '#f5f5f4', bounds: { width: 42, depth: 68, height: 80 }, group: 'Bath', model: `${K}/toilet.glb` },
  'bathtub': { label: 'Bathtub', color: '#f7f7f6', bounds: { width: 78, depth: 170, height: 58 }, group: 'Bath', model: `${K}/bathtub.glb` },
  'shower': { label: 'Shower', color: '#bcd4df', bounds: { width: 95, depth: 95, height: 210 }, group: 'Bath' },
  'vanity': { label: 'Vanity Sink', color: '#3b4654', bounds: { width: 80, depth: 50, height: 90 }, group: 'Bath' },
  'washer': { label: 'Washing Machine', color: '#eef0f2', bounds: { width: 62, depth: 62, height: 85 }, group: 'Bath', model: `${K}/washer.glb` },
  // Outdoor
  'sun-lounger': { label: 'Sun Lounger', color: '#b9925e', bounds: { width: 65, depth: 198, height: 72 }, group: 'Outdoor' },
  // Plants — real models, placed manually like furniture
  'plant': { label: '🪴 Potted Plant', color: '#3f9d57', bounds: { width: 55, depth: 55, height: 80 }, group: 'Plants', model: `${M}/potted_plant_01/potted_plant_01_1k.gltf`, modelVariant: 0 },
  'plant-leafy': { label: '🪴 Leafy Plant', color: '#3f9d57', bounds: { width: 50, depth: 50, height: 90 }, group: 'Plants', model: `${M}/potted_plant_02/potted_plant_02_1k.gltf`, modelVariant: 0 },
  'shrub': { label: '🌳 Shrub', color: '#3f7d33', bounds: { width: 110, depth: 110, height: 95 }, group: 'Plants', model: `${M}/shrub_01/shrub_01_1k.gltf`, modelVariant: 0 },
  'shrub-broad': { label: '🌳 Broad Shrub', color: '#3f7d33', bounds: { width: 120, depth: 120, height: 100 }, group: 'Plants', model: `${M}/shrub_02/shrub_02_1k.gltf`, modelVariant: 0 },
  'shrub-round': { label: '🌳 Round Shrub', color: '#3f7d33', bounds: { width: 90, depth: 90, height: 80 }, group: 'Plants', model: `${M}/shrub_03/shrub_03_1k.gltf`, modelVariant: 0 },
  'fern': { label: '🌿 Fern', color: '#4c8c3a', bounds: { width: 70, depth: 70, height: 55 }, group: 'Plants', model: `${M}/fern_02/fern_02_1k.gltf`, modelVariant: 0 },
  'tree-money': { label: '🌳 Money Tree', color: '#36702c', bounds: { width: 150, depth: 150, height: 230 }, group: 'Plants', model: `${M}/pachira_aquatica_01/pachira_aquatica_01_1k.gltf`, modelVariant: 0 },
  // Decor
  'rug': { label: 'Rug', color: '#9aa1ad', bounds: { width: 220, depth: 160, height: 2 }, group: 'Decor' },
  'lightbulb': { label: '💡 Light Bulb', color: '#fde68a', bounds: { width: 12, depth: 12, height: 18 }, group: 'Decor', model: `${M}/lightbulb_01/lightbulb_01_1k.gltf` },
};

/** Convenience: ordered list of catalog ids for building UI menus. */
export const FURNITURE_CATALOG_IDS = Object.keys(FURNITURE_CATALOG);

/** Returns the catalog entry for an id, falling back to the sofa if unknown. */
export function getCatalogEntry(catalogId: string): FurnitureCatalogEntry {
  return FURNITURE_CATALOG[catalogId] ?? FURNITURE_CATALOG['sofa-3seat'];
}
