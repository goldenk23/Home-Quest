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
  // `elevationCm` is the bearing surface the beam rests ON (the pillar top), so the beam's
  // BOTTOM face — not its center — belongs there. Centering at elevationCm (the old code)
  // sank half the beam into the pillar and left the other half floating above it, which is
  // the gap/misalignment seen at every pillar-beam joint.
  const y = beam.elevationCm * CM_TO_M + d / 2;
  return (
    <mesh position={[cx, y, cz]} rotation={[0, angle, 0]} material={material} castShadow receiveShadow>
      <boxGeometry args={[len, d, w]} />
    </mesh>
  );
});

BeamMesh.displayName = 'BeamMesh';