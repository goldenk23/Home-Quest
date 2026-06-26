// src/domains/viewer/components/SlabMesh.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { polygonToShape } from '../services/transform';
import type { Point2D } from '@/types/geometry';

const CM_TO_M = 0.01;

/**
 * The slab that caps a storey: it sits on top of the floor's walls and fills the space up to
 * the floor above (the inter-storey gap). It is the ceiling of this floor AND the structural
 * floor of the storey above. Rendered as an extruded room polygon so it lines up exactly with
 * the floor finish and walls (same plan→3D mapping as FloorMesh, see transform.ts).
 *
 * Shared, untextured plaster look — the underside reads as a plain ceiling. Cached at module
 * scope so painting a hundred rooms reuses one material/GPU program.
 * ponytail: per-room slab (meets neighbours at the shared wall centreline, like the floor
 * finish). The outer half of an exterior wall's top is left uncapped — upgrade to a unioned
 * building footprint if a flush roof edge is ever needed.
 */
export const ceilingMaterial = new THREE.MeshStandardMaterial({
  color: '#e8e6e1',
  roughness: 0.95,
  metalness: 0,
});

interface SlabMeshProps {
  /** Room boundary in 2D plan coordinates (cm). */
  polygon: Point2D[];
  /** Local Y of the slab underside within the floor group (cm above this floor's base). */
  baseCm: number;
  /** Slab thickness (cm). Its top lands at baseCm + thicknessCm = the floor above. */
  thicknessCm: number;
}

export const SlabMesh: React.FC<SlabMeshProps> = React.memo(({ polygon, baseCm, thicknessCm }) => {
  const geometry = useMemo(() => {
    if (polygon.length < 3 || thicknessCm <= 0) return new THREE.BufferGeometry();
    // Extrude along +Z; after the flat rotation below, +Z becomes +Y, so the slab grows
    // upward from its base into the gap.
    return new THREE.ExtrudeGeometry(polygonToShape(polygon), {
      depth: thicknessCm * CM_TO_M,
      bevelEnabled: false,
    });
  }, [polygon.map((p) => `${p.x},${p.y}`).join(';'), thicknessCm]); // eslint-disable-line react-hooks/exhaustive-deps

  if (polygon.length < 3 || thicknessCm <= 0) return null;

  return (
    <mesh
      geometry={geometry}
      material={ceilingMaterial}
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, baseCm * CM_TO_M, 0]}
      castShadow
      receiveShadow
    />
  );
});

SlabMesh.displayName = 'SlabMesh';
