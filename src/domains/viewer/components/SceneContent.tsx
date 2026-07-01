// src/domains/viewer/components/SceneContent.tsx

import React, { useMemo } from 'react';
import { useAppStore } from '@/store';
import { FloorScene } from './FloorScene';
import { RoadMesh } from './RoadMesh';
import { VastuOverlay3D } from './VastuOverlay3D';
import { GroundPlane } from './GroundPlane';
import { emptyFloorGeometry } from '@/store/slices/floorsSlice';
import { getCatalogEntry, STAIRS_CATALOG_ID } from '../hooks/useAssetLoader';
import { stairFootprint } from '../services/transform';
import type { EntityId, FurnitureItem } from '@/types/editor';
import type { StairEntity } from '@/types/stair';
import type { Point2D } from '@/types/geometry';

/** Extra footprint margin (cm) so the player and the railings clear the cut stairwell edges. */
const STAIR_WELL_MARGIN_CM = 10;

/** The plan-cm stairwell footprints of every staircase in a floor's furniture (legacy). */
function stairWellFootprints(furniture: Record<EntityId, FurnitureItem>): Point2D[][] {
  const wells: Point2D[][] = [];
  for (const item of Object.values(furniture)) {
    if (item.catalogId !== STAIRS_CATALOG_ID) continue;
    const cat = getCatalogEntry(item.catalogId);
    const halfW = (cat.bounds.width / 2) * item.scale + STAIR_WELL_MARGIN_CM;
    const halfD = (cat.bounds.depth / 2) * item.scale + STAIR_WELL_MARGIN_CM;
    wells.push(stairFootprint(item.position.x, item.position.y, item.rotation, halfW, halfD));
  }
  return wells;
}

/** Stairwell void polygons from new-style StairEntity records. */
function stairEntityWells(stairs: Record<EntityId, StairEntity>): Point2D[][] {
  return Object.values(stairs).map((s) => s.stairwellVoid).filter((v) => v.length >= 3);
}

/**
 * The active floor, rendered live from the working set so edits appear instantly. Subscribes
 * to each geometry map directly (stable Zustand refs ⇒ re-renders only when that map changes).
 */
const ActiveFloorScene: React.FC<{
  elevationCm: number;
  ceilingTopCm?: number;
  ceilingHoles?: Point2D[][];
  floorHoles?: Point2D[][];
}> = ({ elevationCm, ceilingTopCm, ceilingHoles, floorHoles }) => {
  const vertices = useAppStore((s) => s.vertices);
  const walls = useAppStore((s) => s.walls);
  const rooms = useAppStore((s) => s.rooms);
  const furniture = useAppStore((s) => s.furniture);
  const openings = useAppStore((s) => s.openings);
  const stairs = useAppStore((s) => s.stairs);
  const pillars = useAppStore((s) => s.pillars);
  const beams = useAppStore((s) => s.beams);
  const deckSlabs = useAppStore((s) => s.deckSlabs);
  return (
    <FloorScene
      vertices={vertices}
      walls={walls}
      rooms={rooms}
      furniture={furniture}
      openings={openings}
      pillars={pillars}
      beams={beams}
      deckSlabs={deckSlabs}
      stairs={stairs}
      elevationCm={elevationCm}
      ceilingTopCm={ceilingTopCm}
      ceilingHoles={ceilingHoles}
      floorHoles={floorHoles}
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
  const activeFurniture = useAppStore((s) => s.furniture);
  const activeStairs = useAppStore((s) => s.stairs);
  const showVastu = useAppStore((s) => s.showVastuOverlay3D);

  // Each storey's stairwell footprints: legacy furniture-based stairs + new StairEntity voids.
  // A flight cuts a void in its OWN ceiling slab and in the floor finish of the storey directly
  // above, so it reads as one continuous shaft connecting the two levels.
  const wellsByFloor = useMemo(() => {
    const map: Record<EntityId, Point2D[][]> = {};
    for (const f of floors) {
      const fur = f.id === activeFloorId ? activeFurniture : floorData[f.id]?.furniture ?? {};
      const sta = f.id === activeFloorId ? activeStairs : floorData[f.id]?.stairs ?? {};
      map[f.id] = [...stairWellFootprints(fur), ...stairEntityWells(sta)];
    }
    return map;
  }, [floors, activeFloorId, activeFurniture, activeStairs, floorData]);

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

        // The floor directly below (largest elevation strictly smaller): its staircases rise
        // into this floor, so their footprints are cut in this floor's floor finish.
        const below = floors.reduce<typeof floor | null>((best, f) => {
          if (f.elevationCm >= floor.elevationCm) return best;
          return !best || f.elevationCm > best.elevationCm ? f : best;
        }, null);
        const ceilingHoles = wellsByFloor[floor.id] ?? [];
        const floorHoles = below ? wellsByFloor[below.id] ?? [] : [];

        if (floor.id === activeFloorId) {
          return (
            <ActiveFloorScene
              key={floor.id}
              elevationCm={floor.elevationCm}
              ceilingTopCm={ceilingTopCm}
              ceilingHoles={ceilingHoles}
              floorHoles={floorHoles}
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
            pillars={data.pillars ?? {}}
            beams={data.beams ?? {}}
            deckSlabs={data.deckSlabs ?? {}}
            stairs={data.stairs ?? {}}
            elevationCm={floor.elevationCm}
            ceilingTopCm={ceilingTopCm}
            ceilingHoles={ceilingHoles}
            floorHoles={floorHoles}
          />
        );
      })}

      {showVastu && <VastuOverlay3D />}
    </group>
  );
};
