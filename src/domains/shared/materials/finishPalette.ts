// src/domains/shared/materials/finishPalette.ts
//
// Pure data registry of the finishes (wall paints + floor tiles) the user can apply with
// the Paint tool. Deliberately framework-free (no THREE, no React) so both the editor
// domain (2D swatch colors, category lookup) and the viewer domain (3D material build)
// can depend on it without either domain importing from the other. The viewer's
// materials.ts turns these data entries into real THREE materials.
//
// Ids here are the SAME ids stored on `Wall.materialId` / `Room.floorMaterialId`, so
// everything persisted, rendered, and selected shares one vocabulary.

export type FinishCategory = 'wall' | 'floor';

/**
 * Procedural texture kind. The viewer builds each as a cached 512×512 CanvasTexture.
 * Omitted for solid paints (no texture, just color).
 */
export type FinishTexture =
  | 'tile'
  | 'wood'
  | 'marble'
  | 'granite'
  | 'terrazzo'
  | 'grass'
  // Newer, richer finishes (floors + textured walls).
  | 'mat'
  | 'vinyl'
  | 'herringbone'
  | 'checker'
  | 'slate'
  | 'cork'
  | 'sandstone'
  | 'carpet'
  | 'concrete'
  | 'stone'
  | 'woodpanel';

export interface FinishMaterial {
  /** Stable id — also the `materialId`/`floorMaterialId` value in the store. */
  readonly id: string;
  /** Human label shown in the palette. */
  readonly name: string;
  /** Whether this paints a wall or tiles a floor. */
  readonly category: FinishCategory;
  /** Hex color used for the 2D editor swatch/fill. */
  readonly swatch: string;
  /** Hex color the viewer's MeshStandardMaterial is tinted. Also shown while a GLB loads. */
  readonly color: string;
  /** Optional procedural texture. Ignored when `glbPath` is set. */
  readonly texture?: FinishTexture;
  /** Physical tile/plank size in meters. Floor geometry UVs are in meters, so setting
   *  `repeat = 1 / repeatMeters` tiles every floor at a correct real-world size. */
  readonly repeatMeters?: number;
  /** Surface roughness for the 3D material (0 glossy … 1 matte). */
  readonly roughness?: number;
  /**
   * Path to a GLB file served from public/ (e.g. '/walls/brick-wall.glb').
   * When set, the viewer loads the GLB on first use and extracts texture maps
   * (map, normalMap, roughnessMap, metalnessMap) from its first mesh material.
   * The `color` is rendered as a solid placeholder until the file finishes loading.
   * The `swatch` is always used in the 2D editor (plan view) — no change there.
   *
   * To add a new GLB wall finish:
   *   1. Drop the .glb file in public/walls/
   *   2. Add an entry here: { id: 'wall-my-finish', name: '...', category: 'wall',
   *        swatch: '#hex', color: '#hex', glbPath: '/walls/my-finish.glb', roughness: 0.8 }
   *   3. The finish appears in the Paint tool palette automatically.
   */
  readonly glbPath?: string;
}

/**
 * Wall paints. Solid colors only (no texture) — walls are small enough that a flat,
 * even paint reads cleanly in both 2D and 3D. The first two reuse the legacy brick ids so
 * existing plans (and the default wall on `addWall`) keep rendering identically.
 */
export const WALL_FINISHES: readonly FinishMaterial[] = [
  { id: 'default-wall', name: 'Brick', category: 'wall', swatch: '#b34730', color: '#b34730', texture: 'tile', repeatMeters: 0.25, roughness: 0.9 },
  // --- Solid paints (neutrals) ---------------------------------------------
  { id: 'paint-white', name: 'White', category: 'wall', swatch: '#f8fafc', color: '#f5f5f0', roughness: 0.85 },
  { id: 'paint-cream', name: 'Cream', category: 'wall', swatch: '#f5ecd9', color: '#f0e6cf', roughness: 0.85 },
  { id: 'paint-ivory', name: 'Ivory', category: 'wall', swatch: '#fbf6ea', color: '#f6efdd', roughness: 0.85 },
  { id: 'paint-linen', name: 'Linen', category: 'wall', swatch: '#efe7dc', color: '#e8dfd1', roughness: 0.85 },
  { id: 'paint-greige', name: 'Greige', category: 'wall', swatch: '#d8cfc2', color: '#cfc6b8', roughness: 0.85 },
  { id: 'paint-grey', name: 'Light Grey', category: 'wall', swatch: '#cbd5e1', color: '#c2c8d0', roughness: 0.8 },
  { id: 'paint-graphite', name: 'Graphite', category: 'wall', swatch: '#3f4651', color: '#3a414b', roughness: 0.8 },
  { id: 'paint-charcoal', name: 'Charcoal', category: 'wall', swatch: '#2a2f37', color: '#272c33', roughness: 0.8 },
  { id: 'paint-slate', name: 'Slate', category: 'wall', swatch: '#475569', color: '#445063', roughness: 0.8 },
  { id: 'paint-taupe', name: 'Taupe', category: 'wall', swatch: '#b8a99a', color: '#b0a191', roughness: 0.85 },
  // --- Solid paints (warm) -------------------------------------------------
  { id: 'paint-sand', name: 'Sand', category: 'wall', swatch: '#e5d3ad', color: '#dfcaa0', roughness: 0.85 },
  { id: 'paint-mustard', name: 'Mustard', category: 'wall', swatch: '#d4a017', color: '#c99515', roughness: 0.85 },
  { id: 'paint-ochre', name: 'Ochre', category: 'wall', swatch: '#c98a2b', color: '#bd8126', roughness: 0.85 },
  { id: 'paint-terracotta', name: 'Terracotta', category: 'wall', swatch: '#c2643f', color: '#b85a37', roughness: 0.85 },
  { id: 'paint-coral', name: 'Coral', category: 'wall', swatch: '#e07a5f', color: '#d96f54', roughness: 0.85 },
  { id: 'paint-rust', name: 'Rust', category: 'wall', swatch: '#a4502c', color: '#9a4827', roughness: 0.85 },
  { id: 'paint-blush', name: 'Blush', category: 'wall', swatch: '#edc7c2', color: '#e7bdb7', roughness: 0.85 },
  { id: 'paint-plum', name: 'Plum', category: 'wall', swatch: '#6b4763', color: '#63415b', roughness: 0.8 },
  // --- Solid paints (cool) -------------------------------------------------
  { id: 'paint-sage', name: 'Sage', category: 'wall', swatch: '#9caf88', color: '#8fa07a', roughness: 0.85 },
  { id: 'paint-olive', name: 'Olive', category: 'wall', swatch: '#73762f', color: '#6b6e2b', roughness: 0.85 },
  { id: 'paint-forest', name: 'Forest', category: 'wall', swatch: '#2f5a3f', color: '#2b533a', roughness: 0.8 },
  { id: 'paint-mint', name: 'Mint', category: 'wall', swatch: '#bfe3d0', color: '#b4dcc6', roughness: 0.85 },
  { id: 'paint-teal', name: 'Teal', category: 'wall', swatch: '#1f7a8c', color: '#1d7283', roughness: 0.8 },
  { id: 'paint-sky', name: 'Sky', category: 'wall', swatch: '#7dd3fc', color: '#74c8f5', roughness: 0.8 },
  { id: 'paint-powder', name: 'Powder Blue', category: 'wall', swatch: '#bcd4e6', color: '#b2cce0', roughness: 0.85 },
  { id: 'paint-navy', name: 'Navy', category: 'wall', swatch: '#1e3a5f', color: '#1c365a', roughness: 0.8 },
  { id: 'paint-lavender', name: 'Lavender', category: 'wall', swatch: '#c4b5fd', color: '#b8a8f5', roughness: 0.85 },
  // --- Textured / material accent walls ------------------------------------
  // GLB example (uncomment + drop the file in public/walls/ to activate):
  // { id: 'wall-glb-brick', name: 'Brick (GLB)', category: 'wall', swatch: '#b34730', color: '#b34730', glbPath: '/walls/brick-wall.glb', roughness: 0.9 },
  { id: 'wall-concrete', name: 'Concrete', category: 'wall', swatch: '#9a9a98', color: '#9a9a98', texture: 'concrete', repeatMeters: 1.5, roughness: 0.9 },
  { id: 'wall-plaster', name: 'Venetian Plaster', category: 'wall', swatch: '#e6ddd0', color: '#e6ddd0', texture: 'concrete', repeatMeters: 2.0, roughness: 0.7 },
  { id: 'wall-stone', name: 'Stone Cladding', category: 'wall', swatch: '#8d8579', color: '#8d8579', texture: 'stone', repeatMeters: 0.5, roughness: 0.95 },
  { id: 'wall-brick-white', name: 'White Brick', category: 'wall', swatch: '#e8e4dd', color: '#e8e4dd', texture: 'tile', repeatMeters: 0.25, roughness: 0.9 },
  { id: 'wall-brick-charcoal', name: 'Charcoal Brick', category: 'wall', swatch: '#54585f', color: '#54585f', texture: 'tile', repeatMeters: 0.25, roughness: 0.9 },
  { id: 'wall-wood-panel', name: 'Wood Panel', category: 'wall', swatch: '#9c6b3f', color: '#92643c', texture: 'woodpanel', repeatMeters: 0.22, roughness: 0.6 },
];

/**
 * Floor tiles. Each carries a procedural texture + a physical size so the tiling density is
 * the same in every room regardless of room dimensions. The first entry reuses the legacy
 * `default-floor` id so unpainted rooms render exactly as before.
 */
export const FLOOR_FINISHES: readonly FinishMaterial[] = [
  { id: 'default-floor', name: 'Concrete', category: 'floor', swatch: '#d4c5a9', color: '#d4c5a9', roughness: 0.7 },
  // --- Tiles ---------------------------------------------------------------
  { id: 'floor-ceramic', name: 'Ceramic', category: 'floor', swatch: '#eef2f7', color: '#e8eef5', texture: 'tile', repeatMeters: 0.45, roughness: 0.35 },
  { id: 'floor-vitrified', name: 'Vitrified', category: 'floor', swatch: '#e2d8c8', color: '#dccfb8', texture: 'tile', repeatMeters: 0.60, roughness: 0.30 },
  { id: 'floor-checker', name: 'Checkerboard', category: 'floor', swatch: '#cfcfcf', color: '#ffffff', texture: 'checker', repeatMeters: 0.60, roughness: 0.3 },
  { id: 'floor-hex', name: 'Hexagon Tile', category: 'floor', swatch: '#dfe6ec', color: '#e6ecf2', texture: 'tile', repeatMeters: 0.30, roughness: 0.35 },
  // --- Stone ---------------------------------------------------------------
  { id: 'floor-marble', name: 'Marble', category: 'floor', swatch: '#f1efe9', color: '#eceae3', texture: 'marble', repeatMeters: 1.5, roughness: 0.25 },
  { id: 'floor-marble-black', name: 'Black Marble', category: 'floor', swatch: '#2b2c31', color: '#34353b', texture: 'marble', repeatMeters: 1.5, roughness: 0.22 },
  { id: 'floor-granite', name: 'Granite', category: 'floor', swatch: '#3a3a40', color: '#36363c', texture: 'granite', repeatMeters: 1.0, roughness: 0.4 },
  { id: 'floor-slate', name: 'Slate', category: 'floor', swatch: '#4a4f57', color: '#454a52', texture: 'slate', repeatMeters: 0.5, roughness: 0.6 },
  { id: 'floor-sandstone', name: 'Sandstone', category: 'floor', swatch: '#d8c08c', color: '#d2b985', texture: 'sandstone', repeatMeters: 0.6, roughness: 0.7 },
  { id: 'floor-terrazzo', name: 'Terrazzo', category: 'floor', swatch: '#d8d4cc', color: '#d2cdc4', texture: 'terrazzo', repeatMeters: 1.2, roughness: 0.45 },
  // --- Wood ----------------------------------------------------------------
  { id: 'floor-wood', name: 'Wood Plank', category: 'floor', swatch: '#9c6b3f', color: '#92643c', texture: 'wood', repeatMeters: 0.18, roughness: 0.6 },
  { id: 'floor-wood-light', name: 'Oak Plank', category: 'floor', swatch: '#c7a173', color: '#c19c6e', texture: 'wood', repeatMeters: 0.18, roughness: 0.55 },
  { id: 'floor-wood-dark', name: 'Walnut Plank', category: 'floor', swatch: '#5c3d24', color: '#573a22', texture: 'wood', repeatMeters: 0.18, roughness: 0.55 },
  { id: 'floor-herringbone', name: 'Herringbone', category: 'floor', swatch: '#a9794b', color: '#a07346', texture: 'herringbone', repeatMeters: 0.5, roughness: 0.55 },
  { id: 'floor-laminate', name: 'Laminate', category: 'floor', swatch: '#b89b76', color: '#b39571', texture: 'wood', repeatMeters: 0.22, roughness: 0.4 },
  // --- Resilient / soft ----------------------------------------------------
  { id: 'floor-vinyl', name: 'Vinyl', category: 'floor', swatch: '#b9bcc2', color: '#b6b9bf', texture: 'vinyl', repeatMeters: 0.30, roughness: 0.45 },
  { id: 'floor-cork', name: 'Cork', category: 'floor', swatch: '#b07d4b', color: '#a97746', texture: 'cork', repeatMeters: 0.30, roughness: 0.7 },
  { id: 'floor-mat', name: 'Mat (Coir)', category: 'floor', swatch: '#a98a5c', color: '#a48555', texture: 'mat', repeatMeters: 0.25, roughness: 0.95 },
  { id: 'floor-mat-grey', name: 'Mat (Grey)', category: 'floor', swatch: '#8a8d92', color: '#85888d', texture: 'mat', repeatMeters: 0.25, roughness: 0.95 },
  { id: 'floor-carpet', name: 'Carpet', category: 'floor', swatch: '#7f8a99', color: '#7b8593', texture: 'carpet', repeatMeters: 0.5, roughness: 1.0 },
  { id: 'floor-carpet-beige', name: 'Carpet (Beige)', category: 'floor', swatch: '#cbbda3', color: '#c6b89e', texture: 'carpet', repeatMeters: 0.5, roughness: 1.0 },
];

/** All finishes flattened, for a single lookup table. */
export const ALL_FINISHES: readonly FinishMaterial[] = [...WALL_FINISHES, ...FLOOR_FINISHES];

/** Quick id → finish lookup. Falls back to undefined for unknown ids (e.g. legacy ids). */
const FINISH_INDEX: ReadonlyMap<string, FinishMaterial> = new Map(
  ALL_FINISHES.map((f) => [f.id, f])
);

// ---------------------------------------------------------------------------
// Dynamic finish registry — populated at runtime from discovered GLB/GLTF
// files in public/walls/. Supplements the static WALL_FINISHES above.
// ---------------------------------------------------------------------------

const _dynamicFinishes: FinishMaterial[] = [];
const _dynamicIndex = new Map<string, FinishMaterial>();

/** Register a GLB-discovered finish at runtime. Skips if an id already exists. */
export function registerDynamicFinish(finish: FinishMaterial): void {
  if (FINISH_INDEX.has(finish.id) || _dynamicIndex.has(finish.id)) return;
  _dynamicFinishes.push(finish);
  _dynamicIndex.set(finish.id, finish);
}

/** Returns all dynamically registered finishes (GLB wall textures). */
export function getDynamicFinishes(): readonly FinishMaterial[] {
  return _dynamicFinishes;
}

/** Returns the finish registered under `id`, or null when no finish uses that id. */
export function getFinishById(id: string): FinishMaterial | null {
  return FINISH_INDEX.get(id) ?? _dynamicIndex.get(id) ?? null;
}

/** The category of a finish id; null when the id isn't a registered finish. */
export function categoryOf(id: string): FinishCategory | null {
  return (FINISH_INDEX.get(id) ?? _dynamicIndex.get(id))?.category ?? null;
}

/**
 * 2D swatch color for a material id. Used by the editor layers so the plan reflects the
 * chosen finish. `fallback` is returned for unknown ids (e.g. a legacy `materialId` that
 * isn't in the palette) so the layer keeps its previous look instead of going transparent.
 */
export function getFinishSwatch(id: string | undefined, fallback: string): string {
  if (!id) return fallback;
  return (FINISH_INDEX.get(id) ?? _dynamicIndex.get(id))?.swatch ?? fallback;
}

/** True when `id` is one of the default/legacy ids a surface starts with (not a paint). */
export function isDefaultFinish(id: string | undefined): boolean {
  return id == null || id === '' || id === 'default-wall' || id === 'default-floor';
}
