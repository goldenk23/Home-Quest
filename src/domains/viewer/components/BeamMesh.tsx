import React, { useMemo } from 'react';
import { getMaterial } from '../services/materials';
import type { Beam } from '@/types/editor';

const CM_TO_M = 0.01;

export const BeamMesh: React.FC<{ beam: Beam }> = React.memo(({ beam }) => {
  const material = useMemo(() => getMaterial(beam.materialId).clone(), [beam.materialId]);
  React.useEffect(() => () => material.dispose(), [material]);
  const dx = beam.end.x - beam.start.x;
  const dy = beam.end.y - beam.start.y;
  const len = Math.hypot(dx, dy) * CM_TO_M;
  if (len <= 0.001) return null;
  const angle = Math.atan2(dy, dx);
  const cx = ((beam.start.x + beam.end.x) / 2) * CM_TO_M;
  const cz = -((beam.start.y + beam.end.y) / 2) * CM_TO_M;
  const w = beam.width * CM_TO_M;
  const d = beam.depth * CM_TO_M;
  const y = beam.elevationCm * CM_TO_M;
  return (
    <mesh position={[cx, y, cz]} rotation={[0, angle, 0]} material={material} castShadow receiveShadow>
      <boxGeometry args={[len, d, w]} />
    </mesh>
  );
});

BeamMesh.displayName = 'BeamMesh';