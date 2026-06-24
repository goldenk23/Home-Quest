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
export type FinishTexture = 'tile' | 'wood' | 'marble' | 'granite' | 'terrazzo';

export interface FinishMaterial {
  /** Stable id — also the `materialId`/`floorMaterialId` value in the store. */
  readonly id: string;
  /** Human label shown in the palette. */
  readonly name: string;
  /** Whether this paints a wall or tiles a floor. */
  readonly category: FinishCategory;
  /** Hex color used for the 2D editor swatch/fill. */
  readonly swatch: string;
  /** Hex color the viewer's MeshStandardMaterial is tinted. */
  readonly color: string;
  /** Optional procedural texture. */
  readonly texture?: FinishTexture;
  /** Physical tile/plank size in meters. Floor geometry UVs are in meters, so setting
   *  `repeat = 1 / repeatMeters` tiles every floor at a correct real-world size. */
  readonly repeatMeters?: number;
  /** Surface roughness for the 3D material (0 glossy … 1 matte). */
  readonly roughness?: number;
}

/**
 * Wall paints. Solid colors only (no texture) — walls are small enough that a flat,
 * even paint reads cleanly in both 2D and 3D. The first two reuse the legacy brick ids so
 * existing plans (and the default wall on `addWall`) keep rendering identically.
 */
export const WALL_FINISHES: readonly FinishMaterial[] = [
  { id: 'default-wall', name: 'Brick', category: 'wall', swatch: '#b34730', color: '#b34730', texture: 'tile', repeatMeters: 0.25, roughness: 0.9 },
  { id: 'paint-white', name: 'White', category: 'wall', swatch: '#f8fafc', color: '#f5f5f0', roughness: 0.85 },
  { id: 'paint-cream', name: 'Cream', category: 'wall', swatch: '#f5ecd9', color: '#f0e6cf', roughness: 0.85 },
  { id: 'paint-grey', name: 'Light Grey', category: 'wall', swatch: '#cbd5e1', color: '#c2c8d0', roughness: 0.8 },
  { id: 'paint-slate', name: 'Slate', category: 'wall', swatch: '#475569', color: '#445063', roughness: 0.8 },
  { id: 'paint-sage', name: 'Sage', category: 'wall', swatch: '#9caf88', color: '#8fa07a', roughness: 0.85 },
  { id: 'paint-terracotta', name: 'Terracotta', category: 'wall', swatch: '#c2643f', color: '#b85a37', roughness: 0.85 },
  { id: 'paint-mustard', name: 'Mustard', category: 'wall', swatch: '#d4a017', color: '#c99515', roughness: 0.85 },
  { id: 'paint-navy', name: 'Navy', category: 'wall', swatch: '#1e3a5f', color: '#1c365a', roughness: 0.8 },
  { id: 'paint-sky', name: 'Sky', category: 'wall', swatch: '#7dd3fc', color: '#74c8f5', roughness: 0.8 },
  { id: 'paint-lavender', name: 'Lavender', category: 'wall', swatch: '#c4b5fd', color: '#b8a8f5', roughness: 0.85 },
];

/**
 * Floor tiles. Each carries a procedural texture + a physical size so the tiling density is
 * the same in every room regardless of room dimensions. The first entry reuses the legacy
 * `default-floor` id so unpainted rooms render exactly as before.
 */
export const FLOOR_FINISHES: readonly FinishMaterial[] = [
  { id: 'default-floor', name: 'Concrete', category: 'floor', swatch: '#d4c5a9', color: '#d4c5a9', roughness: 0.7 },
  { id: 'floor-ceramic', name: 'Ceramic', category: 'floor', swatch: '#eef2f7', color: '#e8eef5', texture: 'tile', repeatMeters: 0.45, roughness: 0.35 },
  { id: 'floor-vitrified', name: 'Vitrified', category: 'floor', swatch: '#e2d8c8', color: '#dccfb8', texture: 'tile', repeatMeters: 0.60, roughness: 0.30 },
  { id: 'floor-wood', name: 'Wood Plank', category: 'floor', swatch: '#9c6b3f', color: '#92643c', texture: 'wood', repeatMeters: 0.18, roughness: 0.6 },
  { id: 'floor-marble', name: 'Marble', category: 'floor', swatch: '#f1efe9', color: '#eceae3', texture: 'marble', repeatMeters: 1.5, roughness: 0.25 },
  { id: 'floor-granite', name: 'Granite', category: 'floor', swatch: '#3a3a40', color: '#36363c', texture: 'granite', repeatMeters: 1.0, roughness: 0.4 },
  { id: 'floor-terrazzo', name: 'Terrazzo', category: 'floor', swatch: '#d8d4cc', color: '#d2cdc4', texture: 'terrazzo', repeatMeters: 1.2, roughness: 0.45 },
];

/** All finishes flattened, for a single lookup table. */
export const ALL_FINISHES: readonly FinishMaterial[] = [...WALL_FINISHES, ...FLOOR_FINISHES];

/** Quick id → finish lookup. Falls back to undefined for unknown ids (e.g. legacy ids). */
const FINISH_INDEX: ReadonlyMap<string, FinishMaterial> = new Map(
  ALL_FINISHES.map((f) => [f.id, f])
);

/** Returns the finish registered under `id`, or null when no finish uses that id. */
export function getFinishById(id: string): FinishMaterial | null {
  return FINISH_INDEX.get(id) ?? null;
}

/** The category of a finish id; null when the id isn't a registered finish. */
export function categoryOf(id: string): FinishCategory | null {
  return FINISH_INDEX.get(id)?.category ?? null;
}

/**
 * 2D swatch color for a material id. Used by the editor layers so the plan reflects the
 * chosen finish. `fallback` is returned for unknown ids (e.g. a legacy `materialId` that
 * isn't in the palette) so the layer keeps its previous look instead of going transparent.
 */
export function getFinishSwatch(id: string | undefined, fallback: string): string {
  if (!id) return fallback;
  return FINISH_INDEX.get(id)?.swatch ?? fallback;
}

/** True when `id` is one of the default/legacy ids a surface starts with (not a paint). */
export function isDefaultFinish(id: string | undefined): boolean {
  return id == null || id === '' || id === 'default-wall' || id === 'default-floor';
}
