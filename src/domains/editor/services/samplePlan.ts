// src/domains/editor/services/samplePlan.ts

import { useAppStore } from '@/store';
import type { RoomType } from '@/types/editor';
import { detectRooms } from './roomDetection';
import { computePlanBoundary } from '@/domains/vastu/services/planBoundary';
import { directionCell } from '@/domains/vastu/services/scoring';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';

/**
 * A detailed, Vastu-compliant single-storey house.
 *
 * The plot is a 12m × 12m square laid out on the classical 3×3 Vastu Purusha Mandala
 * grid (each cell 4m × 4m). North is +Y (up). Rooms are placed in their ideal zones:
 *
 *   NW  bedroom    |  N  living room  |  NE  puja (prayer)
 *   ---------------+------------------+------------------
 *   W   dining     | CENTRE open hall |  E   study
 *   ---------------+------------------+------------------
 *   SW  master bed |  S  bedroom      |  SE  kitchen
 *
 * The centre cell is kept as an open hall/corridor (the Brahmasthan stays unburdened).
 * Room types are assigned automatically from each detected room's grid cell, and a few
 * representative furniture pieces are dropped in so the 3D view and collision are exercised.
 */
export function loadSampleHouse(): void {
  const store = useAppStore.getState();
  const { clearAll, addWall } = store;
  clearAll();

  // 3x3 grid lines at -600, -200, +200, +600 (cm) on both axes → nine 4m cells.
  const G = [-600, -200, 200, 600];

  // Horizontal walls (constant y), one per grid row line, full width.
  for (const y of G) {
    addWall({ x: G[0], y }, { x: G[1], y });
    addWall({ x: G[1], y }, { x: G[2], y });
    addWall({ x: G[2], y }, { x: G[3], y });
  }
  // Vertical walls (constant x), one per grid column line, full height.
  for (const x of G) {
    addWall({ x, y: G[0] }, { x, y: G[1] });
    addWall({ x, y: G[1] }, { x, y: G[2] });
    addWall({ x, y: G[2] }, { x, y: G[3] });
  }

  // After the geometry exists, detect the nine rooms and assign each its ideal type by cell.
  const fresh = useAppStore.getState();
  const detected = detectRooms(fresh.vertices, fresh.walls);
  const boundary = computePlanBoundary(fresh.vertices, fresh.walls);
  const bbox = boundary ? bboxOf(boundary) : null;

  // Ideal room type for each Mandala cell (centre stays an open corridor/hall).
  const CELL_TYPE: Record<string, RoomType> = {
    NE: 'puja',
    N: 'living',
    NW: 'bedroom',
    E: 'study',
    CENTER: 'corridor',
    W: 'dining',
    SE: 'kitchen',
    S: 'bedroom',
    SW: 'bedroom', // master bedroom in the South-West
  };
  const CELL_LABEL: Record<string, string> = {
    NE: 'Puja Room', N: 'Living Room', NW: 'Bedroom 2',
    E: 'Study', CENTER: 'Central Hall', W: 'Dining Room',
    SE: 'Kitchen', S: 'Bedroom 3', SW: 'Master Bedroom',
  };

  const nextRooms: Record<string, typeof detected[number]> = {};
  for (const room of detected) {
    let type: RoomType = 'custom';
    let label = room.label;
    if (bbox) {
      const c = centroidOfIds(room.boundaryVertexIds, fresh.vertices);
      const cell = directionCell(c, bbox);
      type = CELL_TYPE[cell] ?? 'custom';
      label = CELL_LABEL[cell] ?? room.label;
    }
    nextRooms[room.id] = { ...room, roomType: type, label };
  }
  fresh.setRooms(nextRooms);

  // A few furniture pieces in their correct rooms (positions are cell centres, in cm).
  const place = (catalogId: string, x: number, y: number, rotation = 0) => {
    const entry = getCatalogEntry(catalogId);
    fresh.addFurniture({
      position: { x, y },
      rotation,
      scale: 1,
      catalogId,
      roomId: null,
      bounds: { width: entry.bounds.width, depth: entry.bounds.depth },
    });
  };
  place('kitchen-counter', 400, -400);   // SE kitchen
  place('bed-queen', -400, -400);        // SW master bedroom
  place('bed-queen', 0, -400);           // S bedroom
  place('sofa-3seat', 0, 400);           // N living room
  place('dining-table', -400, 0);        // W dining
  place('chair-office', 400, 0);         // E study
  place('toilet', -400, 400);            // NW (bath corner of bedroom 2)
}

// ---- local geometry helpers ----------------------------------------------

import type { EntityId, Vertex } from '@/types/editor';
import type { Point2D } from '@/types/geometry';

function bboxOf(points: Point2D[]) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  return { minX, minY, maxX, maxY };
}

function centroidOfIds(ids: readonly EntityId[], vertices: Record<EntityId, Vertex>): Point2D {
  let x = 0, y = 0, n = 0;
  for (const id of ids) {
    const p = vertices[id]?.position;
    if (p) { x += p.x; y += p.y; n++; }
  }
  return n ? { x: x / n, y: y / n } : { x: 0, y: 0 };
}
