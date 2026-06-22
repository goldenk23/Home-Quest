// src/domains/viewer/hooks/useAssetLoader.ts

import { useGLTF } from '@react-three/drei';
import { useMemo } from 'react';
import * as THREE from 'three';

/** Maps a catalog id to its model file, base scale, and vertical offset. */
export const FURNITURE_CATALOG: Record<string, { path: string; scale: number; yOffset: number }> = {
  'sofa-3seat': { path: '/models/sofa-3seat.glb', scale: 0.01, yOffset: 0 },
  'dining-table': { path: '/models/dining-table.glb', scale: 0.01, yOffset: 0 },
  'bed-queen': { path: '/models/bed-queen.glb', scale: 0.01, yOffset: 0 },
  'chair-office': { path: '/models/chair-office.glb', scale: 0.01, yOffset: 0 },
  'toilet': { path: '/models/toilet.glb', scale: 0.01, yOffset: 0 },
  'kitchen-counter': { path: '/models/kitchen-counter.glb', scale: 0.01, yOffset: 0 },
};

/** Warm the cache for commonly used models so first placement isn't laggy. */
export function preloadCommonModels(): void {
  for (const id of ['sofa-3seat', 'dining-table', 'bed-queen']) {
    const entry = FURNITURE_CATALOG[id];
    if (entry) useGLTF.preload(entry.path);
  }
}

/**
 * Loads a model and returns an independent CLONE per furniture instance.
 * A Three.js Object3D can only have one parent, so two pieces sharing the same model must
 * each get their own clone — otherwise the second one "steals" the mesh from the first.
 */
export function useFurnitureModel(catalogId: string, instanceId: string): THREE.Object3D {
  const entry = FURNITURE_CATALOG[catalogId];
  const { scene } = useGLTF(entry?.path ?? '/models/placeholder.glb');

  return useMemo(() => {
    const clone = scene.clone(true);
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });
    return clone;
  }, [scene, instanceId]); // instanceId keeps clones unique per piece
}
