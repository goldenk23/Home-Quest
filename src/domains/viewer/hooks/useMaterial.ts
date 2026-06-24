// src/domains/viewer/hooks/useMaterial.ts

import { useMemo } from 'react';
import type * as THREE from 'three';
import { getMaterial, getFloorMaterial } from '../services/materials';

/** Returns the cached wall material for an id, stable across re‑renders. */
export function useMaterial(materialId: string): THREE.Material {
  return useMemo(() => getMaterial(materialId), [materialId]);
}

/** Returns the cached floor material for an id (floor-specific depth bias). */
export function useFloorMaterial(materialId: string): THREE.Material {
  return useMemo(() => getFloorMaterial(materialId), [materialId]);
}
