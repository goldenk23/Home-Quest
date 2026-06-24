// src/domains/viewer/components/SceneEnvironment.tsx

import React from 'react';
import { ContactShadows, Environment, Lightformer } from '@react-three/drei';

/**
 * All the lighting + atmosphere for the 3D view, in one place. Tuned to look like a soft
 * studio render rather than a flat game scene, while staying cheap enough to run on any
 * machine: no HDRI files, no post-processing passes, no soft-shadow sampling.
 *
 * - A warm directional light is the "sun" / key light and casts the shadows. It sits in
 *   the east/high position (positive X, high Y) — the Vastu-ideal morning-sun direction.
 * - A small PROCEDURAL environment (a few glowing panels rendered ONCE to a 128px cube)
 *   gives every surface soft image-based fill light and gentle reflections. This is the
 *   single biggest "looks real" win and costs almost nothing at runtime — it's just an
 *   env-map texture lookup in the standard material shader. `background={false}` keeps it
 *   for lighting only; the visible backdrop is the solid colour below.
 * - Hemisphere + a low ambient lift the shadows so they never go pure black.
 * - A soft background colour + matching fog replace the old black void and let the ground
 *   fade into the horizon, which reads as depth/atmosphere instead of a flat plane.
 * - ContactShadows draws soft contact darkening under objects so they feel grounded.
 */
export const SceneEnvironment: React.FC = () => {
  return (
    <>
      {/* Soft, neutral "studio" backdrop + matching fog so distance reads as depth. */}
      <color attach="background" args={['#dfe4ea']} />
      <fog attach="fog" args={['#dfe4ea', 30, 85]} />

      {/* Warm key light (the sun) — casts the scene's shadows. */}
      <directionalLight
        position={[15, 20, 10]}
        intensity={2.0}
        color="#fff4e6"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-far={50}
        shadow-camera-left={-20}
        shadow-camera-right={20}
        shadow-camera-top={20}
        shadow-camera-bottom={-20}
        shadow-bias={-0.0001}
      />

      {/* Sky/ground bounce + a gentle ambient floor so nothing is crushed to black. */}
      <hemisphereLight args={['#cfe6ff', '#9a8366', 0.45]} />
      <ambientLight intensity={0.22} />

      {/*
       * Procedural image-based lighting. Rendered a single time (frames={1}) at a tiny
       * resolution, then reused — negligible ongoing cost. The panels act like softboxes:
       * a big neutral one overhead, a cool one on one side and a warm one on the other,
       * which is what gives surfaces a believable, slightly directional sheen.
       */}
      <Environment resolution={128} frames={1} background={false}>
        <Lightformer
          form="rect"
          intensity={2.2}
          color="#ffffff"
          position={[0, 9, 0]}
          rotation={[Math.PI / 2, 0, 0]}
          scale={[12, 12, 1]}
        />
        <Lightformer
          form="rect"
          intensity={0.9}
          color="#cfe0ff"
          position={[-9, 4, 5]}
          rotation={[0, Math.PI / 3, 0]}
          scale={[7, 7, 1]}
        />
        <Lightformer
          form="rect"
          intensity={0.8}
          color="#ffe7c7"
          position={[9, 4, -5]}
          rotation={[0, -Math.PI / 3, 0]}
          scale={[7, 7, 1]}
        />
      </Environment>

      <ContactShadows position={[0, 0.01, 0]} opacity={0.45} scale={40} blur={2.4} far={4} />
    </>
  );
};
