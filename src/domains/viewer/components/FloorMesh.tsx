// src/domains/viewer/components/FloorMesh.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { shapeWithHoles, holesKey } from '../services/transform';
import { useFloorMaterial } from '../hooks/useMaterial';
import type { Point2D } from '@/types/geometry';

interface FloorMeshProps {
  /** Room boundary in 2D plan coordinates (cm). */
  polygon: Point2D[];
  materialId: string;
  /** Stairwell voids (plan-cm polygons) cut through the floor finish so a flight rising from
   *  the storey below opens onto this floor instead of being capped by it. */
  holes?: Point2D[][];
}

export const FloorMesh: React.FC<FloorMeshProps> = React.memo(({ polygon, materialId, holes = [] }) => {
  // Rebuild only when the polygon (or its stairwell holes) actually change. We key the memo
  // on a compact string of the coordinates so a new array with identical points doesn't force
  // a rebuild.
  const geometry = useMemo(() => {
    if (polygon.length < 3) return new THREE.BufferGeometry();
    return new THREE.ShapeGeometry(shapeWithHoles(polygon, holes));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [polygon.map((p) => `${p.x},${p.y}`).join(';'), holesKey(holes)]);

  const material = useFloorMaterial(materialId);
  if (polygon.length < 3) return null;

  // Rotate the XY shape flat onto the ground; sit clearly above the grass plane (which is at
  // y=-0.06 and depth-biased behind) so a top-down orbit view always shows the floor finish,
  // never the green lawn bleeding through.
  return (
    <mesh geometry={geometry} material={material} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]} receiveShadow />
  );
});

FloorMesh.displayName = 'FloorMesh';
