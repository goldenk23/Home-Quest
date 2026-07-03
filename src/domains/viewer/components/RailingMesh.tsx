import React, { useMemo } from 'react';
import * as THREE from 'three';
import { getMaterial } from '../services/materials';
import type { Railing } from '@/types/editor';

const CM_TO_M = 0.01;

export const RailingMesh: React.FC<{ railing: Railing }> = React.memo(({ railing }) => {
  const mat = useMemo(() => getMaterial(railing.materialId).clone(), [railing.materialId]);
  React.useEffect(() => () => mat.dispose(), [mat]);

  const parts = useMemo(() => {
    const dx = (railing.end.x - railing.start.x) * CM_TO_M;
    const dz = -(railing.end.y - railing.start.y) * CM_TO_M;
    const totalLength = Math.sqrt(dx * dx + dz * dz);
    const angle = Math.atan2(-dz, dx);
    const h = railing.height * CM_TO_M;
    const baseY = railing.elevationCm * CM_TO_M;
    const isSolid = railing.style === 'solid';
    const postSize = isSolid ? 0.06 : 0.04;
    const railThickness = isSolid ? 0.06 : 0.03;
    const midX = (railing.start.x + railing.end.x) / 2 * CM_TO_M;
    const midZ = -(railing.start.y + railing.end.y) / 2 * CM_TO_M;

    // Number of posts: roughly one every 1 meter, minimum 2
    const postCount = Math.max(2, Math.ceil(totalLength / 1.0) + 1);
    const postSpacing = totalLength / (postCount - 1);
    const halfLen = totalLength / 2;

    return {
      totalLength,
      h,
      baseY,
      midX,
      midZ,
      angle,
      isSolid,
      postSize,
      railThickness,
      postCount,
      postSpacing,
      halfLen,
    };
  }, [railing]);

  if (parts.totalLength <= 0) return null;

  return (
    <group
      position={[parts.midX, 0, parts.midZ]}
      rotation={[0, -parts.angle, 0]}
    >
      {/* Top rail */}
      <mesh
        geometry={useMemo(() => new THREE.BoxGeometry(parts.totalLength, parts.railThickness, parts.railThickness), [parts.totalLength, parts.railThickness])}
        material={mat}
        position={[0, parts.baseY + parts.h - parts.railThickness / 2, 0]}
        castShadow
        receiveShadow
      />
      {/* Posts */}
      {Array.from({ length: parts.postCount }).map((_, i) => (
        <mesh
          key={i}
          geometry={useMemo(() => new THREE.BoxGeometry(parts.postSize, parts.h, parts.postSize), [parts.postSize, parts.h])}
          material={mat}
          position={[-parts.halfLen + i * parts.postSpacing, parts.baseY + parts.h / 2, 0]}
          castShadow
          receiveShadow
        />
      ))}
      {/* Solid panel / middle rail for open style */}
      {parts.isSolid ? (
        <mesh
          geometry={useMemo(() => new THREE.BoxGeometry(parts.totalLength, parts.h - parts.railThickness * 2, 0.02), [parts.totalLength, parts.h, parts.railThickness])}
          material={mat}
          position={[0, parts.baseY + parts.h / 2, 0]}
          castShadow
          receiveShadow
        />
      ) : (
        <mesh
          geometry={useMemo(() => new THREE.BoxGeometry(parts.totalLength, parts.railThickness, parts.railThickness), [parts.totalLength, parts.railThickness])}
          material={mat}
          position={[0, parts.baseY + parts.h * 0.5, 0]}
          castShadow
          receiveShadow
        />
      )}
    </group>
  );
});

RailingMesh.displayName = 'RailingMesh';
