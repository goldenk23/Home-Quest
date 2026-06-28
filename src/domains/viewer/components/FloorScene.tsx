// src/domains/viewer/components/FloorScene.tsx

import React, { useMemo } from 'react';
import { WallMesh } from './WallMesh';
import { FloorMesh } from './FloorMesh';
import { SlabMesh } from './SlabMesh';
import { WallCapMesh } from './WallCapMesh';
import { FurnitureInstances } from './FurnitureModel';
import { computeMiterOffsets } from '@/domains/editor/services/wallOps';
import { ceilingSlabRange, pointInPolygon } from '../services/transform';
import type { EntityId, Vertex, Wall, Room, FurnitureItem, Opening } from '@/types/editor';
import type { Point2D } from '@/types/geometry';

const CM_TO_M = 0.01;

// Polygon-offset unit palette for the 4-color wall adjacency graph coloring.
// Adjacent walls (sharing a vertex) get different palette entries, guaranteeing
// that no two walls at the same joint share a polygonOffsetUnits value.
const DEPTH_SLOT_PALETTE = [-12, -4, 4, 12];

export interface FloorSceneProps {
  vertices: Record<EntityId, Vertex>;
  walls: Record<EntityId, Wall>;
  rooms: Record<EntityId, Room>;
  furniture: Record<EntityId, FurnitureItem>;
  openings: Record<EntityId, Opening>;
  /** Base elevation of this storey in cm; the whole floor is lifted onto the Y axis by it. */
  elevationCm: number;
  /**
   * Distance (cm) from this floor's base up to the floor directly above it. When set, a
   * ceiling slab is built from the wall tops up to this height — capping this storey and
   * forming the floor of the one above, filling the inter-storey gap. Omitted on the top
   * floor (no storey above) so it stays open for the top-down editing/orbit view.
   */
  ceilingTopCm?: number;
  /** The active floor renders collision highlighting; parked floors don't. */
  isActive?: boolean;
  /**
   * Stairwell footprints (plan-cm polygons) of THIS floor's own staircases. Each is cut as a
   * void in this floor's ceiling slab so a flight can rise through the ceiling.
   */
  ceilingHoles?: Point2D[][];
  /**
   * Stairwell footprints (plan-cm polygons) of the staircases on the floor DIRECTLY BELOW.
   * Each is cut in this floor's floor finish so the flight rising from below opens onto this
   * storey instead of being sealed off by its floor.
   */
  floorHoles?: Point2D[][];
}

/**
 * Renders a single storey (rooms + walls + furniture) lifted to its elevation. Pure in its
 * inputs — it never reads the global store — so it renders both the live active floor and any
 * parked floor identically, which is what lets the 3D view stack a whole multi-storey house.
 */
export const FloorScene: React.FC<FloorSceneProps> = React.memo(
  ({ vertices, walls, rooms, furniture, openings, elevationCm, ceilingTopCm, isActive = false, ceilingHoles = [], floorHoles = [] }) => {
    // Room polygons (plan cm) — for floor slabs and for orienting main gates outward.
    const roomData = useMemo(
      () =>
        Object.values(rooms).map((r) => ({
          id: r.id,
          floorMaterialId: r.floorMaterialId,
          polygon: r.boundaryVertexIds
            .map((id) => vertices[id]?.position ?? { x: 0, y: 0 }),
        })),
      [rooms, vertices]
    );

    const roomPolys = useMemo<Point2D[][]>(
      () => roomData.map((r) => r.polygon).filter((p) => p.length >= 3),
      [roomData]
    );

    // Graph-color the wall adjacency graph so no two walls sharing a vertex get the same
    // polygonOffsetUnits. This eliminates z-fighting seam lines at wall joints without any
    // hash-collision risk. 4 colors suffice for planar graphs; we use a simple greedy pass.
    const wallDepthSlots = useMemo(() => {
      const colorOf: Record<string, number> = {}; // wall id → palette index
      for (const wall of Object.values(walls)) {
        const usedColors = new Set<number>();
        for (const vid of [wall.startVertexId, wall.endVertexId]) {
          const v = vertices[vid];
          if (v) {
            for (const adjId of v.connectedWalls) {
              if (adjId !== wall.id && colorOf[adjId] !== undefined) {
                usedColors.add(colorOf[adjId]);
              }
            }
          }
        }
        let c = 0;
        while (usedColors.has(c)) c++;
        colorOf[wall.id] = c;
      }
      // Map palette index → actual units value
      const slots: Record<string, number> = {};
      for (const [id, c] of Object.entries(colorOf)) {
        slots[id] = DEPTH_SLOT_PALETTE[c % DEPTH_SLOT_PALETTE.length];
      }
      return slots;
    }, [walls, vertices]);

    const wallData = useMemo(
      () =>
        Object.values(walls).map((w) => ({
          id: w.id,
          start: vertices[w.startVertexId]?.position,
          end: vertices[w.endVertexId]?.position,
          thickness: w.thickness,
          height: w.height,
          materialId: w.materialId,
          materialSideA: w.materialSideA,
          materialSideB: w.materialSideB,
          offsets: computeMiterOffsets(w.id, walls, vertices),
          openings: (w.openingIds ?? []).map((oid) => openings[oid]).filter(Boolean) as Opening[],
        })),
      [walls, vertices, openings]
    );

    const furnitureList = useMemo(() => Object.values(furniture), [furniture]);

    // Ceiling slab: sit it on top of the tallest wall and fill up to the floor above.
    const wallTopCm = useMemo(
      () => wallData.reduce((max, w) => Math.max(max, w.height ?? 0), 0),
      [wallData]
    );
    const { baseCm: ceilingBaseCm, thicknessCm: ceilingThicknessCm } =
      ceilingTopCm != null ? ceilingSlabRange(wallTopCm, ceilingTopCm) : { baseCm: 0, thicknessCm: 0 };

    // A stairwell void is cut only into the room slab/finish that fully contains it (every
    // corner inside the polygon). A footprint straddling two rooms or poking outside is
    // skipped — the flight still carries the player up, it just won't punch a torn slab.
    const holesIn = (poly: Point2D[], all: Point2D[][]) =>
      all.filter((h) => h.every((c) => pointInPolygon(c, poly)));

    return (
      <group position={[0, elevationCm * CM_TO_M, 0]}>
        {roomData.map((room) =>
          room.polygon.length >= 3 ? (
            <FloorMesh
              key={room.id}
              polygon={room.polygon}
              materialId={room.floorMaterialId}
              holes={holesIn(room.polygon, floorHoles)}
            />
          ) : null
        )}

        {ceilingThicknessCm > 0 &&
          roomData.map((room) =>
            room.polygon.length >= 3 ? (
              <SlabMesh
                key={`slab-${room.id}`}
                polygon={room.polygon}
                baseCm={ceilingBaseCm}
                thicknessCm={ceilingThicknessCm}
                holes={holesIn(room.polygon, ceilingHoles)}
              />
            ) : null
          )}

        {ceilingTopCm != null &&
          wallData.map((wall) =>
            wall.start && wall.end && ceilingTopCm - (wall.height ?? 0) > 0 ? (
              <WallCapMesh
                key={`cap-${wall.id}`}
                start={wall.start}
                end={wall.end}
                thickness={wall.thickness}
                baseCm={wall.height ?? 0}
                capHeightCm={ceilingTopCm - (wall.height ?? 0)}
                offsets={wall.offsets}
              />
            ) : null
          )}

        {wallData.map((wall) =>
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
              openings={wall.openings}
              roomPolys={roomPolys}
              depthSlot={wallDepthSlots[wall.id]}
            />
          ) : null
        )}

        <FurnitureInstances items={furnitureList} highlightCollisions={isActive} />
      </group>
    );
  }
);

FloorScene.displayName = 'FloorScene';
