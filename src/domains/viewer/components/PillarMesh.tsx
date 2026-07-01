import React, { useMemo } from 'react';
import { getMaterial } from '../services/materials';
import type { Pillar } from '@/types/editor';

const CM_TO_M = 0.01;

export const PillarMesh: React.FC<{ pillar: Pillar }> = React.memo(({ pillar }) => {
  const material = useMemo(() => getMaterial(pillar.materialId).clone(), [pillar.materialId]);
  React.useEffect(() => () => material.dispose(), [material]);

  const x = pillar.position.x * CM_TO_M;
  const z = -pillar.position.y * CM_TO_M;
  const base = pillar.elevationCm * CM_TO_M;
  const h = pillar.height * CM_TO_M;
  const w = pillar.width * CM_TO_M;
  const d = pillar.depth * CM_TO_M;

  return (
    <mesh position={[x, base + h / 2, z]} material={material} castShadow receiveShadow>
      {pillar.shape === 'round'
        ? <cylinderGeometry args={[Math.max(w, d) / 2, Math.max(w, d) / 2, h, 24]} />
        : <boxGeometry args={[w, h, d]} />}
    </mesh>
  );
});

PillarMesh.displayName = 'PillarMesh';