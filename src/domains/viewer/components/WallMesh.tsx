// src/domains/viewer/components/WallMesh.tsx

import React, { useMemo } from 'react';
import { useAppStore } from '@/store';
import { createWallGeometry } from '../services/extrusion';
import { useMaterial } from '../hooks/useMaterial';
import type { Point2D } from '@/types/geometry';
import type { MiterOffsets } from '@/domains/editor/services/wallOps';

interface WallMeshProps {
  id: string;
  start: Point2D;
  end: Point2D;
  thickness: number;
  height: number;
  materialId: string;
  offsets?: MiterOffsets;
}
import { useShallow } from 'zustand/react/shallow';

const CM_TO_M = 0.01;

const OpeningFrames: React.FC<{ wallId: string; thickness: number; start: Point2D; end: Point2D }> = React.memo(({ wallId, thickness, start, end }) => {
  const openings = useAppStore(useShallow(s => {
    const wall = s.walls[wallId];
    if (!wall || !wall.openingIds) return [];
    return wall.openingIds.map(oid => s.openings[oid]).filter(Boolean);
  }));

  if (openings.length === 0) return null;

  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const angle = Math.atan2(dy, dx);
  const sx = start.x * CM_TO_M;
  const sz = -start.y * CM_TO_M;
  const thickM = thickness * CM_TO_M;

  return (
    <group position={[sx, 0, sz]} rotation={[0, angle, 0]}>
      {openings.map(opening => {
        if (opening.type === 'door') return null; // Doors remain open or have their own logic
        
        const ox = opening.offsetCm * CM_TO_M;
        const oy = opening.elevation * CM_TO_M;
        const ow = opening.width * CM_TO_M;
        const oh = opening.height * CM_TO_M;
        
        const isWindow = opening.type === 'window';
        const frameDepth = thickM * 0.8;
        const border = 0.05; // 5cm frame border
        
        // Materials
        const frameMaterial = <meshStandardMaterial color="#f8fafc" roughness={0.3} metalness={0.1} />;
        const glassMaterial = <meshStandardMaterial color="#bae6fd" transparent opacity={0.4} roughness={0.05} metalness={0.8} />;
        const louvreMaterial = <meshStandardMaterial color="#cbd5e1" roughness={0.6} metalness={0.4} />;

        return (
          <group key={opening.id} position={[ox, oy + oh / 2, 0]}>
            {/* Outer Frame (Jambs, Head, Sill) */}
            <mesh position={[-ow / 2 + border / 2, 0, 0]}>
              <boxGeometry args={[border, oh, frameDepth]} />
              {frameMaterial}
            </mesh>
            <mesh position={[ow / 2 - border / 2, 0, 0]}>
              <boxGeometry args={[border, oh, frameDepth]} />
              {frameMaterial}
            </mesh>
            <mesh position={[0, oh / 2 - border / 2, 0]}>
              <boxGeometry args={[ow - 2 * border, border, frameDepth]} />
              {frameMaterial}
            </mesh>
            <mesh position={[0, -oh / 2 + border / 2, 0]}>
              <boxGeometry args={[ow - 2 * border, border, frameDepth]} />
              {frameMaterial}
            </mesh>

            {isWindow ? (
              // Realistic Window (2 panels with central mullion)
              <group>
                {/* Central Mullion */}
                <mesh position={[0, 0, 0]}>
                  <boxGeometry args={[border, oh - 2 * border, frameDepth * 0.5]} />
                  {frameMaterial}
                </mesh>
                {/* Left Glass */}
                <mesh position={[-(ow - border) / 4, 0, 0]}>
                  <boxGeometry args={[(ow - 3 * border) / 2, oh - 2 * border, 0.02]} />
                  {glassMaterial}
                </mesh>
                {/* Right Glass */}
                <mesh position={[(ow - border) / 4, 0, 0]}>
                  <boxGeometry args={[(ow - 3 * border) / 2, oh - 2 * border, 0.02]} />
                  {glassMaterial}
                </mesh>
              </group>
            ) : (
              // Realistic Ventilation (Slanted Louvres)
              <group>
                {Array.from({ length: Math.floor((oh - 2 * border) / 0.06) }).map((_, i, arr) => {
                  const spacing = (oh - 2 * border) / arr.length;
                  const yPos = (oh / 2 - border) - spacing * (i + 0.5);
                  return (
                    <mesh key={i} position={[0, yPos, 0]} rotation={[Math.PI / 6, 0, 0]}>
                      <boxGeometry args={[ow - 2 * border, 0.01, frameDepth * 0.7]} />
                      {louvreMaterial}
                    </mesh>
                  );
                })}
              </group>
            )}
          </group>
        );
      })}
    </group>
  );
});

export const WallMesh: React.FC<WallMeshProps> = React.memo(
  ({ id, start, end, thickness, height, materialId, offsets }) => {
    // We must subscribe to the openings of this specific wall so the mesh regenerates when an opening is added
    useAppStore(s => s.walls[id]?.openingIds);
    // Deep map the openings so we re-render if any opening dimensions change
    const openingsStr = useAppStore(s => {
       const wall = s.walls[id];
       if (!wall || !wall.openingIds) return '';
       return wall.openingIds.map(oid => {
          const o = s.openings[oid];
          return o ? `${o.id}-${o.offsetCm}-${o.width}-${o.height}-${o.elevation}` : '';
       }).join(',');
    });

    const geometry = useMemo(
      () => createWallGeometry(start, end, thickness, height, offsets, id),
      [start.x, start.y, end.x, end.y, thickness, height, offsets?.startLeft, offsets?.startRight, offsets?.endLeft, offsets?.endRight, id, openingsStr]
    );
    const material = useMaterial(materialId);
    return (
      <group>
        <mesh geometry={geometry} material={material} castShadow receiveShadow />
        <OpeningFrames wallId={id} thickness={thickness} start={start} end={end} />
      </group>
    );
  }
);

WallMesh.displayName = 'WallMesh';
