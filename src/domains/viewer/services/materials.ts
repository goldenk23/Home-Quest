// src/domains/viewer/services/materials.ts

import * as THREE from 'three';
import {
  ALL_FINISHES,
  getFinishById,
  type FinishMaterial,
  type FinishTexture,
} from '@/domains/shared/materials/finishPalette';

const materialCache = new Map<string, THREE.Material>();

// ----------------------------------------------------------------------------
// Procedural texture generators. Each draws a 512×512 tile onto a <canvas> (works in
// any browser; no external image assets to load) and returns a RepeatWrapping
// CanvasTexture. The tile is authored to cover a 1m × 1m area; the caller sets
// texture.repeat to (1/repeatMeters) so the pattern lands at the right physical size on
// every surface (floor geometry UVs are already in meters).
// ----------------------------------------------------------------------------

function makeCanvas(size = 512): { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D } | null {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  return { canvas, ctx };
}

function finalizeTexture(canvas: HTMLCanvasElement, repeatMeters: number): THREE.CanvasTexture {
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  // A "1m tile" repeated `1/repeatMeters` times per meter = repeatMeters-meter tiles.
  const r = repeatMeters > 0 ? 1 / repeatMeters : 1;
  texture.repeat.set(r, r);
  return texture;
}

function createBrickTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.25);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#b34730';
  ctx.fillRect(0, 0, 512, 512);

  for (let i = 0; i < 10000; i++) {
    ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.1})`;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, 2, 2);
  }

  ctx.fillStyle = '#e0dbd1';
  const brickW = 128;
  const brickH = 64;
  const mortarW = 6;

  for (let y = 0; y < 512; y += brickH) {
    ctx.fillRect(0, y, 512, mortarW);
    const offset = (y / brickH) % 2 === 0 ? 0 : brickW / 2;
    for (let x = -brickW; x < 512 + brickW; x += brickW) {
      ctx.fillRect(x + offset, y, mortarW, brickH);
    }
  }

  return finalizeTexture(canvas, 0.25);
}

function createBrickBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.25);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  ctx.fillStyle = '#000000';
  const brickW = 128;
  const brickH = 64;
  const mortarW = 6;

  for (let y = 0; y < 512; y += brickH) {
    ctx.fillRect(0, y, 512, mortarW);
    const offset = (y / brickH) % 2 === 0 ? 0 : brickW / 2;
    for (let x = -brickW; x < 512 + brickW; x += brickW) {
      ctx.fillRect(x + offset, y, mortarW, brickH);
    }
  }

  return finalizeTexture(canvas, 0.25);
}

/** Square floor tiles with thin grout lines. Tinted by the material color at build time. */
function createTileTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.45);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  // Subtle per-tile variation so a large floor isn't a flat sheet.
  for (let i = 0; i < 4000; i++) {
    ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.04})`;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, 3, 3);
  }

  // Grout lines (drawn as a grid; the tile is a single unit so one set of lines reads as
  // the seam between four tiles when repeated).
  ctx.fillStyle = 'rgba(60,60,60,0.55)';
  ctx.fillRect(0, 0, 512, 4);
  ctx.fillRect(0, 0, 4, 512);

  return finalizeTexture(canvas, 0.45);
}

/** Horizontal wood planks with grain noise and a darker seam between boards. */
function createWoodTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.18);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  const plankH = 64; // 8 planks across the 1m tile
  for (let y = 0; y < 512; y += plankH) {
    // Long grain streaks inside each plank.
    for (let i = 0; i < 60; i++) {
      ctx.fillStyle = `rgba(60,40,20,${Math.random() * 0.10})`;
      const yy = y + Math.random() * plankH;
      ctx.fillRect(0, yy, 512, 1 + Math.random() * 2);
    }
    // Dark seam between boards.
    ctx.fillStyle = 'rgba(40,25,10,0.5)';
    ctx.fillRect(0, y, 512, 2);
  }

  return finalizeTexture(canvas, 0.18);
}

/** Soft diagonal veining on a light field — reads as marble when tinted. */
function createMarbleTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 1.5);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  ctx.lineCap = 'round';
  for (let v = 0; v < 14; v++) {
    ctx.strokeStyle = `rgba(120,120,130,${0.08 + Math.random() * 0.12})`;
    ctx.lineWidth = 1 + Math.random() * 3;
    ctx.beginPath();
    let x = Math.random() * 512;
    let y = Math.random() * 512;
    ctx.moveTo(x, y);
    for (let s = 0; s < 12; s++) {
      x += (Math.random() - 0.5) * 120;
      y += (Math.random() - 0.5) * 120;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  return finalizeTexture(canvas, 1.5);
}

/** Fine speckle — granite. Dense small dots over a dark field. */
function createGraniteTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 1.0);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  for (let i = 0; i < 18000; i++) {
    const shade = Math.random();
    ctx.fillStyle =
      shade < 0.5 ? `rgba(0,0,0,${0.15 + Math.random() * 0.25})`
        : shade < 0.8 ? `rgba(255,255,255,${0.05 + Math.random() * 0.1})`
          : `rgba(120,120,140,${0.1 + Math.random() * 0.15})`;
    const r = Math.random() * 2.5;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, r, r);
  }

  return finalizeTexture(canvas, 1.0);
}

/** Marble-chip terrazzo: scattered color chips over a light binder. */
function createTerrazzoTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 1.2);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  const chipColors = ['rgba(180,180,190,0.85)', 'rgba(120,120,140,0.8)', 'rgba(200,190,170,0.8)', 'rgba(90,90,100,0.7)'];
  for (let i = 0; i < 260; i++) {
    ctx.fillStyle = chipColors[i % chipColors.length];
    ctx.save();
    ctx.translate(Math.random() * 512, Math.random() * 512);
    ctx.rotate(Math.random() * Math.PI);
    const w = 8 + Math.random() * 26;
    const h = 5 + Math.random() * 12;
    ctx.fillRect(-w / 2, -h / 2, w, h);
    ctx.restore();
  }

  return finalizeTexture(canvas, 1.2);
}

// ----------------------------------------------------------------------------
// Texture singletons. Cached so painting a hundred rooms with the same tile reuses one
// GPU texture. Keyed by FinishTexture kind.
// ----------------------------------------------------------------------------

const textureCache = new Map<FinishTexture, THREE.CanvasTexture>();

function getTexture(kind: FinishTexture): THREE.CanvasTexture {
  const existing = textureCache.get(kind);
  if (existing) return existing;
  let tex: THREE.CanvasTexture;
  switch (kind) {
    case 'tile': tex = createTileTexture(); break;
    case 'wood': tex = createWoodTexture(); break;
    case 'marble': tex = createMarbleTexture(); break;
    case 'granite': tex = createGraniteTexture(); break;
    case 'terrazzo': tex = createTerrazzoTexture(); break;
  }
  textureCache.set(kind, tex);
  return tex;
}

/**
 * Returns the shared procedural texture for a kind, CLONED and re-tinted to a neutral base
 * so callers (e.g. furniture tabletops) can apply their own material colour over it. Reuses
 * the cached texture data, so this adds no new GPU memory per call. `repeatMeters` sets the
 * physical tile/plank size on the surface.
 */
export function getProceduralTexture(kind: FinishTexture, repeatMeters: number): THREE.CanvasTexture {
  const base = getTexture(kind);
  const tex = base.clone();
  tex.needsUpdate = true;
  const r = repeatMeters > 0 ? 1 / repeatMeters : 1;
  tex.repeat.set(r, r);
  return tex;
}

// Brick is shared with the legacy 'default-wall'/'brick-wall' ids, so it has its own cache.
let sharedBrickTexture: THREE.CanvasTexture | null = null;
let sharedBrickBumpMap: THREE.CanvasTexture | null = null;

function getBrickTexture(): THREE.CanvasTexture {
  if (!sharedBrickTexture) sharedBrickTexture = createBrickTexture();
  return sharedBrickTexture;
}

function getBrickBumpMap(): THREE.CanvasTexture {
  if (!sharedBrickBumpMap) sharedBrickBumpMap = createBrickBumpMap();
  return sharedBrickBumpMap;
}

// ----------------------------------------------------------------------------
// Material construction.
// ----------------------------------------------------------------------------

/**
 * Stable index per finish, used to give every finish a unique, tiny depth bias.
 *
 * Why: at a mitred corner, two neighbouring walls extend to meet and end up with
 * coincident, coplanar faces (same position, same height). When both walls share a
 * material the overlap is invisible, but as soon as one wall is painted a different
 * finish the two coincident surfaces have different colours and the depth test can't
 * decide which is in front — so it flickers ("blinks") frame-to-frame as the camera moves.
 *
 * Giving each finish a distinct `polygonOffset` makes one of any two *different*
 * coincident faces win the depth test deterministically, so the corner renders a single
 * stable colour instead of shimmering. Two faces of the *same* finish keep the same bias,
 * but they look identical anyway, so no flicker is visible.
 */
const FINISH_OFFSET_INDEX: ReadonlyMap<string, number> = new Map(
  ALL_FINISHES.map((f, i) => [f.id, i])
);

/** Applies the per-finish depth bias described above. Magnitudes are tiny — they only
 *  break depth-test ties between coincident faces; nothing visibly shifts position. */
function applyDepthBias(material: THREE.MeshStandardMaterial, finishId: string): void {
  const idx = FINISH_OFFSET_INDEX.get(finishId) ?? 0;
  // Spread biases symmetrically around 0 so the set stays close to neutral depth.
  const bias = idx - (ALL_FINISHES.length - 1) / 2;
  material.polygonOffset = true;
  material.polygonOffsetFactor = bias * 0.1;
  material.polygonOffsetUnits = bias;
}

/**
 * How strongly a surface picks up the scene's (procedural) environment map. Glossier
 * finishes (low roughness — marble, tile, vitrified) get more sheen/reflection; matte
 * paints get only a whisper. This is what makes floors look polished and walls look
 * painted instead of everything reading as flat plastic. Costs nothing extra at runtime.
 */
function envIntensityFor(roughness: number): number {
  // roughness 0.2 → ~0.85, roughness 0.9 → ~0.3. Clamped to a tasteful range.
  const v = 1.0 - roughness * 0.75;
  return Math.max(0.25, Math.min(0.9, v));
}

/**
 * Builds the shared THREE material for a palette finish.
 * - Solid paints → flat MeshStandardMaterial tinted `color`.
 * - Textured floors/walls → a cached white-base procedural texture tinted `color`, so one
 *   texture (e.g. the tile grid) can serve many color variants.
 */
function buildFinishMaterial(finish: FinishMaterial): THREE.Material {
  const roughness = finish.roughness ?? 0.7;
  let material: THREE.MeshStandardMaterial;

  if (!finish.texture) {
    material = new THREE.MeshStandardMaterial({ color: finish.color, roughness, metalness: 0 });
  } else if (finish.id === 'default-wall') {
    // The brick id keeps its dedicated brick texture + bump map (legacy look).
    material = new THREE.MeshStandardMaterial({
      map: getBrickTexture(),
      bumpMap: getBrickBumpMap(),
      bumpScale: 0.05,
      roughness,
      metalness: 0,
    });
  } else {
    // Generic textured finish: reuse the cached procedural tile for this kind, tinted.
    const texture = getTexture(finish.texture).clone();
    texture.needsUpdate = true;
    const r = finish.repeatMeters && finish.repeatMeters > 0 ? 1 / finish.repeatMeters : 1;
    texture.repeat.set(r, r);
    material = new THREE.MeshStandardMaterial({
      map: texture,
      color: finish.color,
      roughness,
      metalness: 0,
    });
  }

  applyDepthBias(material, finish.id);
  material.envMapIntensity = envIntensityFor(roughness);
  return material;
}

/**
 * Returns the one shared material instance for an id.
 *
 * Resolution order:
 *   1. Palette finish (registered in finishPalette) → built once and cached.
 *   2. Legacy aliases ('brick-wall', 'tile-floor') → mapped to their palette counterpart.
 *   3. Anything else → falls back to the default wall material (unchanged prior behavior).
 *
 * Note: brick-wall and tile-floor are kept as explicit aliases so old persisted plans that
 * stored those ids keep rendering as before.
 */
export function getMaterial(materialId: string): THREE.Material {
  const cached = materialCache.get(materialId);
  if (cached) return cached;

  // Legacy aliases → canonical palette id.
  const alias: Record<string, string> = {
    'brick-wall': 'default-wall',
    'tile-floor': 'default-floor',
  };
  const resolvedId = alias[materialId] ?? materialId;

  const finish = getFinishById(resolvedId);
  const material = finish
    ? buildFinishMaterial(finish)
    : buildFinishMaterial(ALL_FINISHES[0]); // default-wall fallback (unchanged semantics)

  materialCache.set(materialId, material);
  return material;
}

/** True when the given id is a registered finish in the palette. */
export function isKnownFinish(materialId: string): boolean {
  return getFinishById(materialId) != null;
}
