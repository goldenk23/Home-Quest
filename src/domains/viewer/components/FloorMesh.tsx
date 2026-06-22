// src/domains/viewer/components/FloorMesh.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { polygonToShape } from '../services/transform';
import { useMaterial } from '../hooks/useMaterial';
import type { Point2D } from '@/types/geometry';

interface FloorMeshProps {
  /** Room boundary in 2D plan coordinates (cm). */
  polygon: Point2D[];
  materialId: string;
}

export const FloorMesh: React.FC<FloorMeshProps> = React.memo(({ polygon, materialId }) => {
  // Rebuild only when the polygon actually changes. We key the memo on a compact string
  // of the coordinates so a new array with identical points doesn't force a rebuild.
  const geometry = useMemo(() => {
    if (polygon.length < 3) return new THREE.BufferGeometry();
    return new THREE.ShapeGeometry(polygonToShape(polygon));
  }, [polygon.map((p) => `${p.x},${p.y}`).join(';')]); // eslint-disable-line react-hooks/exhaustive-deps

  const material = useMaterial(materialId);
  if (polygon.length < 3) return null;

  // Rotate the XY shape flat onto the ground; sit a hair above 0 to avoid z‑fighting
  // with the ground plane.
  return (
    <mesh geometry={geometry} material={material} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, 0]} receiveShadow />
  );
});

FloorMesh.displayName = 'FloorMesh';
