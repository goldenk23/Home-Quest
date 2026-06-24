// src/domains/viewer/components/SceneContent.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { useViewerWalls, useViewerRooms } from '@/store/selectors/editorSelectors';
import { WallMesh } from './WallMesh';
import { FloorMesh } from './FloorMesh';
import { FurnitureInstances } from './FurnitureModel';
import { RoadMesh } from './RoadMesh';
import { VastuOverlay3D } from './VastuOverlay3D';
import { GroundPlane } from './GroundPlane';

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
      {/* Outdoor lawn — real CC0 grass PBR textures with anisotropic filtering. */}
      <GroundPlane />

      {/* Exterior paving / driveways laid with the Road tool. */}
      <RoadMesh />

      {rooms.map((room) => (
        <FloorMesh key={room.id} polygon={room.polygon} materialId={room.floorMaterialId} />
      ))}

      {walls.map((wall) =>
        wall.start && wall.end ? (
          <WallMesh
            key={wall.id}
            id={wall.id}
            start={wall.start}
            end={wall.end}
            thickness={wall.thickness}
            height={wall.height}
            materialId={wall.materialId}
            materialSideA={wall.materialSideA}
            materialSideB={wall.materialSideB}
            offsets={wall.offsets}
          />
        ) : null
      )}

      <FurnitureInstances />
      {showVastu && <VastuOverlay3D />}
    </group>
  );
};
