// src/domains/viewer/components/SceneContent.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { useViewerWalls, useViewerRooms } from '@/store/selectors/editorSelectors';
import { WallMesh } from './WallMesh';
import { FloorMesh } from './FloorMesh';
import { FurnitureInstances } from './FurnitureModel';
import { VastuOverlay3D } from './VastuOverlay3D';

/**
 * Pure orchestrator: maps store geometry to meshes. Each child builds its own geometry,
 * so this component just lists what's in the scene.
 */
export const SceneContent: React.FC = () => {
  const walls = useViewerWalls();
  const rooms = useViewerRooms();
  const showVastu = useAppStore((s) => s.showVastuOverlay3D);

  return (
    <group>
      {/* Infinite ground plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} receiveShadow>
        <planeGeometry args={[100, 100]} />
        <meshStandardMaterial color="#3a5a40" />
      </mesh>

      {rooms.map((room) => (
        <FloorMesh key={room.id} polygon={room.polygon} materialId={room.floorMaterialId} />
      ))}

      {walls.map((wall) =>
        wall.start && wall.end ? (
          <WallMesh
            key={wall.id}
            start={wall.start}
            end={wall.end}
            thickness={wall.thickness}
            height={wall.height}
            materialId={wall.materialId}
            offsets={wall.offsets}
          />
        ) : null
      )}

      <FurnitureInstances />
      {showVastu && <VastuOverlay3D />}
    </group>
  );
};
