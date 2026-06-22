// src/domains/viewer/hooks/useMaterial.ts

import { useMemo } from 'react';
import type * as THREE from 'three';
import { getMaterial } from '../services/materials';

/** Returns the cached material for an id, stable across re‑renders. */
export function useMaterial(materialId: string): THREE.Material {
  return useMemo(() => getMaterial(materialId), [materialId]);
}
