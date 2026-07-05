// src/domains/viewer/components/GroundPlane.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { useTexture } from '@react-three/drei';
import { useThree } from '@react-three/fiber';
import { useAppStore } from '@/store';

/**
 * The outdoor lawn the house sits on.
 *
 * Uses a real, photographed CC0 grass PBR set from Poly Haven (albedo + OpenGL normal +
 * roughness, 2K) instead of the old hand-drawn canvas texture, so from the top-down orbit
 * view it reads as natural turf rather than a flat "game floor". The realism comes from
 * three things working together:
 *   1. a high-res photographic albedo with genuine colour variation (no obvious repeat),
 *   2. a normal map so the blades/clumps catch the moving sun with real micro-shadow, and
 *   3. max anisotropic filtering so the lawn stays crisp at the grazing angles a big ground
 *      plane is mostly seen at, instead of smearing into mush.
 *
 * Files live in /public/textures/grass (see SOURCE.md there for licensing).
 */

/** Physical size, in metres, that one texture tile covers on the ground. */
const GRASS_TILE_METERS = 5;
/**
 * Side length of the (square) ground plane, in metres. Sized for campus-scale plans
 * (Hall-1 spans roughly 66 m × 110 m) with generous margin on every side.
 */
const GROUND_SIZE = 400;

const GRASS_TEXTURES = {
  map: '/textures/grass/aerial_grass_rock_diff_2k.jpg',
  normalMap: '/textures/grass/aerial_grass_rock_nor_gl_2k.jpg',
  roughnessMap: '/textures/grass/aerial_grass_rock_rough_2k.jpg',
} as const;

export const GroundPlane: React.FC = () => {
  const gl = useThree((s) => s.gl);

  // Keep the lawn centered under the plan so buildings never hang off the edge of the
  // field, wherever they were drawn. Falls back to the world origin for empty plans.
  const planCentroid3D = useAppStore((s) => s.planCentroid3D);
  const cx = planCentroid3D?.x ?? 0;
  const cz = planCentroid3D?.z ?? 0;

  // Suspends until the three maps are decoded (we're already inside the canvas Suspense).
  const { map, normalMap, roughnessMap } = useTexture(GRASS_TEXTURES);

  // Configure the maps once they're loaded: tile them across the plane, crank anisotropy,
  // and flag the albedo as sRGB (the normal/roughness maps stay linear, which is the default).
  useMemo(() => {
    const repeat = GROUND_SIZE / GRASS_TILE_METERS;
    const maxAniso = gl.capabilities.getMaxAnisotropy();
    map.colorSpace = THREE.SRGBColorSpace;
    for (const tex of [map, normalMap, roughnessMap]) {
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(repeat, repeat);
      tex.anisotropy = maxAniso;
      tex.needsUpdate = true;
    }
  }, [map, normalMap, roughnessMap, gl]);

  // Sits a few cm below the room floors AND carries a positive polygonOffset, so from a
  // top-down orbit view the lawn can never win the depth test and bleed through a floor.
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, -0.06, cz]} receiveShadow>
      <planeGeometry args={[GROUND_SIZE, GROUND_SIZE]} />
      <meshStandardMaterial
        map={map}
        normalMap={normalMap}
        roughnessMap={roughnessMap}
        roughness={1}
        metalness={0}
        envMapIntensity={0.4}
        polygonOffset
        polygonOffsetFactor={4}
        polygonOffsetUnits={24}
      />
    </mesh>
  );
};
