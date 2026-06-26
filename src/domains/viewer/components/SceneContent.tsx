// src/domains/viewer/components/SceneContent.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { FloorScene } from './FloorScene';
import { RoadMesh } from './RoadMesh';
import { VastuOverlay3D } from './VastuOverlay3D';
import { GroundPlane } from './GroundPlane';
import { emptyFloorGeometry } from '@/store/slices/floorsSlice';

/**
 * The active floor, rendered live from the working set so edits appear instantly. Subscribes
 * to each geometry map directly (stable Zustand refs ⇒ re-renders only when that map changes).
 */
const ActiveFloorScene: React.FC<{ elevationCm: number; ceilingTopCm?: number }> = ({
  elevationCm,
  ceilingTopCm,
}) => {
  const vertices = useAppStore((s) => s.vertices);
  const walls = useAppStore((s) => s.walls);
  const rooms = useAppStore((s) => s.rooms);
  const furniture = useAppStore((s) => s.furniture);
  const openings = useAppStore((s) => s.openings);
  return (
    <FloorScene
      vertices={vertices}
      walls={walls}
      rooms={rooms}
      furniture={furniture}
      openings={openings}
      elevationCm={elevationCm}
      ceilingTopCm={ceilingTopCm}
      isActive
    />
  );
};

/**
 * Orchestrates the whole building: the ground/lawn, the active floor (live), and every other
 * storey rendered from its parked geometry — each lifted to its own elevation so the floors
 * stack into a multi-storey house. Furniture/vastu overlays for the active floor only.
 */
export const SceneContent: React.FC = () => {
  const floors = useAppStore((s) => s.floors);
  const activeFloorId = useAppStore((s) => s.activeFloorId);
  const floorData = useAppStore((s) => s.floorData);
  const showVastu = useAppStore((s) => s.showVastuOverlay3D);

  return (
    <group>
      {/* Outdoor lawn — real CC0 grass PBR textures with anisotropic filtering. */}
      <GroundPlane />

      {/* Exterior paving / driveways laid with the Road tool (active floor). */}
      <RoadMesh />

      {floors.map((floor) => {
        // The floor directly above (smallest elevation strictly greater) caps this storey.
        // The distance to it is the ceiling height; the top floor has none and stays open.
        const above = floors.reduce<typeof floor | null>((best, f) => {
          if (f.elevationCm <= floor.elevationCm) return best;
          return !best || f.elevationCm < best.elevationCm ? f : best;
        }, null);
        const ceilingTopCm = above ? above.elevationCm - floor.elevationCm : undefined;

        if (floor.id === activeFloorId) {
          return (
            <ActiveFloorScene
              key={floor.id}
              elevationCm={floor.elevationCm}
              ceilingTopCm={ceilingTopCm}
            />
          );
        }
        const data = floorData[floor.id] ?? emptyFloorGeometry();
        return (
          <FloorScene
            key={floor.id}
            vertices={data.vertices}
            walls={data.walls}
            rooms={data.rooms}
            furniture={data.furniture}
            openings={data.openings}
            elevationCm={floor.elevationCm}
            ceilingTopCm={ceilingTopCm}
          />
        );
      })}

      {showVastu && <VastuOverlay3D />}
    </group>
  );
};
