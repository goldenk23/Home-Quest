import React, { useMemo } from 'react';
import * as THREE from 'three';
import { getFloorMaterial } from '../services/materials';
import { shapeWithHoles } from '../services/transform';
import type { DeckSlab } from '@/types/editor';

const CM_TO_M = 0.01;

export const DeckSlabMesh: React.FC<{ slab: DeckSlab }> = React.memo(({ slab }) => {
  const material = useMemo(() => getFloorMaterial(slab.materialId).clone(), [slab.materialId]);
  React.useEffect(() => () => material.dispose(), [material]);

  const geometry = useMemo(() => {
    if (slab.polygon.length < 3 || slab.thicknessCm <= 0) return new THREE.BufferGeometry();
    return new THREE.ExtrudeGeometry(shapeWithHoles(slab.polygon, []), {
      depth: slab.thicknessCm * CM_TO_M,
      bevelEnabled: false,
    });
  }, [slab.polygon, slab.thicknessCm]);

  if (slab.polygon.length < 3 || slab.thicknessCm <= 0) return null;

  return (
    <mesh
      geometry={geometry}
      material={material}
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, slab.elevationCm * CM_TO_M, 0]}
      castShadow
      receiveShadow
    />
  );
});

DeckSlabMesh.displayName = 'DeckSlabMesh';