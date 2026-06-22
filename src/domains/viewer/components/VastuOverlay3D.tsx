// src/domains/viewer/components/VastuOverlay3D.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { useAppStore } from '@/store';
import { VASTU_ZONES_8 } from '@/domains/vastu/services/zones';
import { calculateBrahmasthan } from '@/domains/vastu/services/brahmasthan';

const CM_TO_M = 0.01;
const OVERLAY_HEIGHT = 0.05; // 5cm above floor
const SEGMENTS_PER_ZONE = 16;

export const VastuOverlay3D: React.FC = () => {
  const planBoundary = useAppStore((s) => s.planBoundary);

  const { brahmasthan, radius } = useMemo(() => {
    if (!planBoundary || planBoundary.length < 3) return { brahmasthan: null, radius: 0 };
    const center = calculateBrahmasthan(planBoundary);
    const maxDist = planBoundary.reduce((max, p) => Math.max(max, Math.hypot(p.x - center.x, p.y - center.y)), 0);
    return { brahmasthan: center, radius: maxDist * CM_TO_M };
  }, [planBoundary]);

  if (!brahmasthan) return null;
  const centerX = brahmasthan.x * CM_TO_M;
  const centerZ = -brahmasthan.y * CM_TO_M;

  return (
    <group position={[0, OVERLAY_HEIGHT, 0]}>
      {VASTU_ZONES_8.map((zone) => (
        <ZoneMesh3D
          key={zone.direction}
          centerX={centerX}
          centerZ={centerZ}
          radius={radius}
          startAngle={zone.startAngle}
          spanAngle={zone.spanAngle}
          color={zone.color}
        />
      ))}
    </group>
  );
};

const ZoneMesh3D: React.FC<{
  centerX: number;
  centerZ: number;
  radius: number;
  startAngle: number;
  spanAngle: number;
  color: string;
}> = React.memo(({ centerX, centerZ, radius, startAngle, spanAngle, color }) => {
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const vertices: number[] = [];
    for (let i = 0; i < SEGMENTS_PER_ZONE; i++) {
      const a1 = startAngle + (i / SEGMENTS_PER_ZONE) * spanAngle;
      const a2 = startAngle + ((i + 1) / SEGMENTS_PER_ZONE) * spanAngle;
      vertices.push(centerX, 0, centerZ); // fan center
      vertices.push(centerX + radius * Math.cos(a1), 0, centerZ - radius * Math.sin(a1)); // 2D-Y -> 3D-(-Z)
      vertices.push(centerX + radius * Math.cos(a2), 0, centerZ - radius * Math.sin(a2));
    }
    geo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geo.computeVertexNormals();
    return geo;
  }, [centerX, centerZ, radius, startAngle, spanAngle]);

  return (
    <mesh geometry={geometry}>
      {/* depthWrite off so overlapping zones blend predictably; DoubleSide so it's visible from below */}
      <meshBasicMaterial color={color} transparent opacity={0.25} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  );
});

ZoneMesh3D.displayName = 'ZoneMesh3D';
