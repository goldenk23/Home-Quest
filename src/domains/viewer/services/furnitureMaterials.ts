// src/domains/viewer/services/furnitureMaterials.ts
//
// Tuned material parameters for furniture, keyed by "part kind" rather than per-piece. This
// is the single biggest "modern, not gamey" lever for furniture: until now every prefab used
// a flat inline <meshStandardMaterial> with no env-map response, so nothing caught the light
// or the sky. By giving each material family a hand-picked roughness/metalness and a tuned
// `envMapIntensity`, the same procedural meshes suddenly read as fabric vs. metal vs. glass —
// with ZERO extra geometry, ZERO new GPU textures, and no per-pixel cost.
//
// "envMapIntensity" is free: the scene's procedural Environment is already being rendered,
// so we're just dialling how strongly each material samples it (mates fabric → low, polished
// glass/metal → high). Real glass would use MeshPhysicalMaterial.transmission, but that is a
// per-pixel cost — deliberately avoided to keep the GPU load negligible.

import * as THREE from 'three';
import { getProceduralTexture } from './materials';
import type { FinishTexture } from '@/domains/shared/materials/finishPalette';

export type FurniturePartKind =
  | 'fabric'
  | 'lightWood'
  | 'darkWood'
  | 'white'
  | 'metal'
  | 'matteBlack'
  | 'glass'
  | 'quartz'
  | 'foliage'
  | 'screen';

export interface FurnitureMaterialProps {
  color: string;
  roughness: number;
  metalness: number;
  /** How strongly this material samples the scene's environment map (reflections/fill). */
  envMapIntensity: number;
  /** Optional translucent glass-like surface. */
  transparent?: boolean;
  opacity?: number;
  /** Optional procedural texture applied to the surface (reuses cached textures). */
  texture?: { kind: FinishTexture; repeatMeters: number };
}

/**
 * Per-kind tuned params + a default colour. The colour passed at the call site (e.g. the
 * catalog colour for upholstery) overrides `color`; the rest of the tuning always applies.
 */
const PART_DEFAULTS: Record<FurniturePartKind, Omit<FurnitureMaterialProps, 'color'>> = {
  fabric: { roughness: 0.92, metalness: 0.0, envMapIntensity: 0.35 }, // matte cloth — barely reflective
  lightWood: { roughness: 0.55, metalness: 0.05, envMapIntensity: 0.5, texture: { kind: 'wood', repeatMeters: 0.18 } },
  darkWood: { roughness: 0.62, metalness: 0.05, envMapIntensity: 0.5, texture: { kind: 'wood', repeatMeters: 0.18 } },
  white: { roughness: 0.45, metalness: 0.06, envMapIntensity: 0.6 }, // glossy ceramic/laminate
  metal: { roughness: 0.28, metalness: 0.9, envMapIntensity: 1.0 }, // brushed metal — strong reflections
  matteBlack: { roughness: 0.4, metalness: 0.55, envMapIntensity: 0.7 }, // appliances/screens
  glass: { roughness: 0.06, metalness: 0.0, envMapIntensity: 1.0, transparent: true, opacity: 0.28 },
  quartz: { roughness: 0.32, metalness: 0.12, envMapIntensity: 0.85, texture: { kind: 'marble', repeatMeters: 1.2 } },
  foliage: { roughness: 0.8, metalness: 0.0, envMapIntensity: 0.4 }, // plant leaves
  screen: { roughness: 0.2, metalness: 0.6, envMapIntensity: 0.9 }, // TV/monitor panel
};

const DEFAULT_COLOR: Record<FurniturePartKind, string> = {
  fabric: '#5f6b7a',
  lightWood: '#c8a27c',
  darkWood: '#6f5641',
  white: '#f5f5f4',
  metal: '#b8bcc4',
  matteBlack: '#15171c',
  glass: '#cfe8f5',
  quartz: '#e7e5e4',
  foliage: '#3f9d57',
  screen: '#0b0d12',
};

/**
 * Resolve the full material props for a part kind, with an optional colour override. Returns
 * a plain object the prefab helpers spread into <meshStandardMaterial {...props} />. Keeps
 * the collision → red override trivial (caller swaps `color` to red and ignores the rest).
 */
export function furnitureMaterialProps(
  kind: FurniturePartKind,
  colorOverride?: string
): FurnitureMaterialProps {
  const defaults = PART_DEFAULTS[kind];
  return {
    ...defaults,
    color: colorOverride ?? DEFAULT_COLOR[kind],
  };
}

/**
 * Build (and cache) a real THREE.MeshStandardMaterial for a part kind. Used when a component
 * needs a material instance rather than JSX props — e.g. reusable textured tops. Cached per
 * (kind, color) so 20 sofas with the same fabric share ONE material instance.
 */
const materialInstanceCache = new Map<string, THREE.MeshStandardMaterial>();

export function getFurnitureMaterial(kind: FurniturePartKind, colorOverride?: string): THREE.MeshStandardMaterial {
  const color = colorOverride ?? DEFAULT_COLOR[kind];
  const key = `${kind}:${color}`;
  const cached = materialInstanceCache.get(key);
  if (cached) return cached;

  const props = furnitureMaterialProps(kind, color);
  const mat = new THREE.MeshStandardMaterial({
    color: props.color,
    roughness: props.roughness,
    metalness: props.metalness,
    transparent: props.transparent ?? false,
    opacity: props.opacity ?? 1,
    envMapIntensity: props.envMapIntensity,
  });
  if (props.texture) {
    mat.map = getProceduralTexture(props.texture.kind, props.texture.repeatMeters);
  }
  materialInstanceCache.set(key, mat);
  return mat;
}
