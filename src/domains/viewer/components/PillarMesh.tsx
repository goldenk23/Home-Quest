import React, { useMemo } from 'react';
import { getMaterial } from '../services/materials';
import type { Pillar } from '@/types/editor';

const CM_TO_M = 0.01;

// A pillar's stored `height` is the structural bearing height (what beams/decks use to
// compute their own resting elevation). Rendering the shaft to exactly that height leaves
// its flat top exactly coplanar with the beam/deck bottom face — that coincidence is what
// caused the "chewed" z-fighting notch and unfinished-looking seam at every joint.
// A real post doesn't just butt against the underside of a beam/deck either: it's notched
// or capped so the two members visibly lock together. CAP_EMBED_M sinks the cap slightly
// into whatever sits above (beam depth / deck thickness are always well over 1cm), and
// CAP_OVERHANG_M makes the cap read as a proper post cap/bearing plate.
const CAP_EMBED_M = 0.015;
const CAP_THICKNESS_M = 0.03;
const CAP_OVERHANG_M = 0.02;

export const PillarMesh: React.FC<{ pillar: Pillar }> = React.memo(({ pillar }) => {
  const material = useMemo(() => getMaterial(pillar.materialId).clone(), [pillar.materialId]);
  React.useEffect(() => () => material.dispose(), [material]);

  const x = pillar.position.x * CM_TO_M;
  const z = -pillar.position.y * CM_TO_M;
  const base = pillar.elevationCm * CM_TO_M;
  const h = pillar.height * CM_TO_M;
  const w = pillar.width * CM_TO_M;
  const d = pillar.depth * CM_TO_M;
  const top = base + h;

  return (
    <group>
      <mesh position={[x, base + h / 2, z]} material={material} castShadow receiveShadow>
        {pillar.shape === 'round'
          ? <cylinderGeometry args={[Math.max(w, d) / 2, Math.max(w, d) / 2, h, 24]} />
          : <boxGeometry args={[w, h, d]} />}
      </mesh>
      {/* Bearing cap: a small post-cap plate straddling the shaft top and embedding a
          little into the beam/deck resting on it, so the joint reads as one real
          construction detail instead of two boxes touching on a bare plane. */}
      <mesh position={[x, top + CAP_THICKNESS_M / 2 - CAP_EMBED_M, z]} material={material} castShadow receiveShadow>
        {pillar.shape === 'round'
          ? <cylinderGeometry args={[Math.max(w, d) / 2 + CAP_OVERHANG_M, Math.max(w, d) / 2 + CAP_OVERHANG_M, CAP_THICKNESS_M, 24]} />
          : <boxGeometry args={[w + CAP_OVERHANG_M * 2, CAP_THICKNESS_M, d + CAP_OVERHANG_M * 2]} />}
      </mesh>
    </group>
  );
});

PillarMesh.displayName = 'PillarMesh';