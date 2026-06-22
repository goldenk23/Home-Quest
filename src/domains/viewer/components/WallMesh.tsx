// src/domains/viewer/components/WallMesh.tsx

import React, { useMemo } from 'react';
import { createWallGeometry } from '../services/extrusion';
import { useMaterial } from '../hooks/useMaterial';
import type { Point2D } from '@/types/geometry';
import type { MiterOffsets } from '@/domains/editor/services/wallOps';

interface WallMeshProps {
  start: Point2D;
  end: Point2D;
  thickness: number;
  height: number;
  materialId: string;
  offsets?: MiterOffsets;
}

export const WallMesh: React.FC<WallMeshProps> = React.memo(
  ({ start, end, thickness, height, materialId, offsets }) => {
    const geometry = useMemo(
      () => createWallGeometry(start, end, thickness, height, offsets),
      [start.x, start.y, end.x, end.y, thickness, height, offsets?.startLeft, offsets?.startRight, offsets?.endLeft, offsets?.endRight]
    );
    const material = useMaterial(materialId);
    return <mesh geometry={geometry} material={material} castShadow receiveShadow />;
  }
);

WallMesh.displayName = 'WallMesh';
