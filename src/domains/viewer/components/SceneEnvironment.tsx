// src/domains/viewer/components/SceneEnvironment.tsx

import React from 'react';
import { ContactShadows } from '@react-three/drei';

/**
 * All the lighting for the 3D view, in one place.
 *
 * - A single directional light acts as the sun and casts shadows. It is placed in the
 *   east/high position (positive X, high Y) — the Vastu‑ideal morning‑sun direction.
 * - Hemisphere + ambient lights lift the shadows so they never go pure black.
 * - ContactShadows draws soft contact darkening under objects so they feel grounded.
 *
 * Note: we deliberately avoid drei's <Environment> HDRI preset here — it fetches an HDR
 * file over the network and would blank the viewport when offline. The explicit lights
 * below give consistent, dependency‑free lighting that always renders.
 */
export const SceneEnvironment: React.FC = () => {
  return (
    <>
      <directionalLight
        position={[15, 20, 10]}
        intensity={1.8}
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

      <hemisphereLight args={['#b1e1ff', '#b97a20', 0.6]} />
      <ambientLight intensity={0.4} />

      <ContactShadows position={[0, 0.01, 0]} opacity={0.4} scale={40} blur={2} far={4} />
    </>
  );
};
