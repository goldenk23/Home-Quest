// src/domains/viewer/components/RoadMesh.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { useTexture } from '@react-three/drei';
import { useThree } from '@react-three/fiber';
import { useShallow } from 'zustand/react/shallow';
import { useAppStore } from '@/store';

const CM_TO_M = 0.01;
/** Physical size, in metres, that one asphalt texture tile covers along the road. */
const ASPHALT_TILE_METERS = 4;

/**
 * Real, photographed CC0 asphalt PBR set from Poly Haven (albedo + OpenGL normal + packed
 * AO/Rough/Metal, 2K). Replaces the old flat dark-grey slab so roads read as genuine paving —
 * grainy, light-catching tarmac — instead of a cartoon strip. Files live in
 * /public/textures/asphalt_02 (see SOURCE.md there for licensing).
 */
const ASPHALT_TEXTURES = {
  map: '/textures/asphalt_02/diff.jpg',
  normalMap: '/textures/asphalt_02/nor.jpg',
  roughnessMap: '/textures/asphalt_02/arm.jpg',
} as const;

/**
 * Renders all roads/paving as flat asphalt strips lying just above the lawn. Each road is a
 * thin plane whose length spans its centerline and whose breadth is its width, rotated to
 * align with the segment. A pair of dashed lane markings runs down the centre. Roads sit a
 * hair above the ground plane (and carry a polygon offset) so they never z-fight with the lawn.
 */
export const RoadMesh: React.FC = () => {
  const roads = useAppStore(useShallow((s) => Object.values(s.roads)));
  const gl = useThree((s) => s.gl);

  // Shared base maps — decoded once (we're already inside the canvas Suspense). Per-road tiling
  // is handled by cloning these in each RoadSurface so each segment tiles to its own length.
  const base = useTexture(ASPHALT_TEXTURES);

  useMemo(() => {
    base.map.colorSpace = THREE.SRGBColorSpace;
    const maxAniso = gl.capabilities.getMaxAnisotropy();
    for (const tex of [base.map, base.normalMap, base.roughnessMap]) {
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.anisotropy = maxAniso;
      tex.needsUpdate = true;
    }
  }, [base, gl]);

  if (roads.length === 0) return null;

  return (
    <group>
      {roads.map((road) => {
        const sx = road.start.x * CM_TO_M;
        const sz = -road.start.y * CM_TO_M;
        const ex = road.end.x * CM_TO_M;
        const ez = -road.end.y * CM_TO_M;
        const dx = ex - sx;
        const dz = ez - sz;
        const len = Math.hypot(dx, dz) || 0.01;
        const widthM = road.width * CM_TO_M;
        const cx = (sx + ex) / 2;
        const cz = (sz + ez) / 2;
        // Angle of the segment around the vertical Y axis (atan2 over the X/Z plane).
        const angle = Math.atan2(dz, dx);

        return (
          <RoadSurface
            key={road.id}
            base={base}
            len={len}
            widthM={widthM}
            position={[cx, 0, cz]}
            yRotation={-angle}
          />
        );
      })}
    </group>
  );
};

interface RoadSurfaceProps {
  base: { map: THREE.Texture; normalMap: THREE.Texture; roughnessMap: THREE.Texture };
  len: number;
  widthM: number;
  position: [number, number, number];
  yRotation: number;
}

/** A single asphalt strip with its own correctly-tiled clone of the shared maps. */
const RoadSurface: React.FC<RoadSurfaceProps> = ({ base, len, widthM, position, yRotation }) => {
  // Clone the shared maps so this strip can tile to its own real-world length/width without
  // disturbing other roads. Clones share the decoded image, so this is cheap.
  const { map, normalMap, roughnessMap } = useMemo(() => {
    const repeatX = Math.max(1, len / ASPHALT_TILE_METERS);
    const repeatY = Math.max(1, widthM / ASPHALT_TILE_METERS);
    const clone = (src: THREE.Texture, srgb: boolean) => {
      const tex = src.clone();
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(repeatX, repeatY);
      tex.anisotropy = src.anisotropy;
      if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
      tex.needsUpdate = true;
      return tex;
    };
    return {
      map: clone(base.map, true),
      normalMap: clone(base.normalMap, false),
      roughnessMap: clone(base.roughnessMap, false),
    };
  }, [base, len, widthM]);

  const dashes = Math.max(1, Math.floor(len / 1.2));

  return (
    <group position={position} rotation={[0, yRotation, 0]}>
      {/* Asphalt slab (length along local X, width along local Z). */}
      <mesh position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[len, widthM]} />
        <meshStandardMaterial
          map={map}
          normalMap={normalMap}
          roughnessMap={roughnessMap}
          roughness={1}
          metalness={0}
          envMapIntensity={0.5}
          polygonOffset
          polygonOffsetFactor={-2}
          polygonOffsetUnits={-4}
        />
      </mesh>
      {/* Dashed centre lane marking. */}
      {Array.from({ length: dashes }).map((_, i) => {
        const x = -len / 2 + (len * (i + 0.5)) / dashes;
        return (
          <mesh key={i} position={[x, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[(len / dashes) * 0.5, Math.min(0.15, widthM * 0.06)]} />
            <meshStandardMaterial
              color="#e8c84d"
              roughness={0.7}
              metalness={0}
              polygonOffset
              polygonOffsetFactor={-3}
              polygonOffsetUnits={-6}
            />
          </mesh>
        );
      })}
    </group>
  );
};
