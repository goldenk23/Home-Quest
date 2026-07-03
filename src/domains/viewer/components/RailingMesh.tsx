import React, { useMemo } from 'react';
import * as THREE from 'three';
import { getMaterial } from '../services/materials';
import type { Railing } from '@/types/editor';

const CM_TO_M = 0.01;

export const RailingMesh: React.FC<{ railing: Railing }> = React.memo(({ railing }) => {
  const material = useMemo(() => getMaterial(railing.materialId).clone(), [railing.materialId]);
  React.useEffect(() => () => material.dispose(), [material]);

  const geometry = useMemo(() => {
    const dx = railing.end.x - railing.start.x;
    const dy = railing.end.y - railing.start.y;
    const length = Math.sqrt(dx * dx + dy * dy) * CM_TO_M;
    const angle = Math.atan2(dy, dx);
    
    // Create box geometry for railing
    const railWidth = railing.style === 'solid' ? 0.08 : 0.03; // 8cm or 3cm
    const geom = new THREE.BoxGeometry(length, railing.height * CM_TO_M, railWidth);
    
    return {
      geometry: geom,
      angle,
      midX: (railing.start.x + railing.end.x) / 2 * CM_TO_M,
      midZ: -(railing.start.y + railing.end.y) / 2 * CM_TO_M,
    };
  }, [railing]);

  React.useEffect(() => {
    return () => geometry.geometry.dispose();
  }, [geometry.geometry]);

  return (
    <mesh
      geometry={geometry.geometry}
      material={material}
      position={[geometry.midX, (railing.elevationCm + railing.height / 2) * CM_TO_M, geometry.midZ]}
      rotation={[0, -geometry.angle, 0]}
      castShadow
      receiveShadow
    />
  );
});

RailingMesh.displayName = 'RailingMesh';
