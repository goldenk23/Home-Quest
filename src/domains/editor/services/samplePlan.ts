// src/domains/editor/services/samplePlan.ts

import { useAppStore } from '@/store';
import type { RoomType, EntityId, Vertex } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { detectRooms } from './roomDetection';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';

/**
 * Loads the sample apartment, recreated from the reference 2D floor plan
 * (balcony + kitchen + living across the top; two bedrooms and a corridor in the middle;
 * bathroom, walk-in closet, entrance and master bedroom across the bottom).
 *
 * Coordinate system: centimeters, x→right, y→down (matching the plan image). Walls are
 * pre-segmented at every junction so neighbouring rooms share exact vertices, which is
 * what the planar-graph room detector needs.
 *
 *   x grid:  0   190  220        420  520            950
 *   y grid:  0 ───────────────── top band (balcony/kitchen/living)
 *           400 ──────────────── middle band (bed1 / corridor / bed2)
 *           620 ──────────────── bottom band (bath/closet / entrance / master)
 *           800 ── (bath|closet split)
 *           920 ── bottom edge
 */
export function loadSampleHouse(): void {
  const store = useAppStore.getState();
  const { clearAll, addWall, addOpening } = store;
  clearAll();

  // Spaciousness factor: every plan COORDINATE (wall endpoints, opening offsets, furniture
  // positions) is multiplied by this, while real-world sizes (furniture footprints, door /
  // window widths, wall height) stay fixed — so the rooms grow roomier around their
  // contents. Bump this up for an even more open feel.
  const S = 1.45;

  const W = (x1: number, y1: number, x2: number, y2: number) =>
    addWall({ x: x1 * S, y: y1 * S }, { x: x2 * S, y: y2 * S });

  // --- Horizontal walls ---
  const hBalconyTop = W(0, 0, 190, 0);
  const hKitchenTop = W(190, 0, 420, 0);
  const hLivingTop = W(420, 0, 950, 0);

  W(0, 400, 190, 400);
  W(190, 400, 420, 400);
  const hLivingCorridor = W(420, 400, 520, 400);
  W(520, 400, 950, 400);

  W(0, 620, 220, 620);
  W(220, 620, 420, 620);
  const hCorridorEntrance = W(420, 620, 520, 620);
  W(520, 620, 950, 620);

  W(0, 800, 220, 800);

  W(0, 920, 220, 920);
  const hEntranceFront = W(220, 920, 520, 920);
  const hMasterBottom = W(520, 920, 950, 920);

  // --- Vertical walls ---
  const vBalconyLeft = W(0, 0, 0, 400);
  const vBed1Left = W(0, 400, 0, 620);
  const vBathLeft = W(0, 620, 0, 800);
  W(0, 800, 0, 920);

  const vBalconyKitchen = W(190, 0, 190, 400);

  const vEntranceBath = W(220, 620, 220, 800);
  const vEntranceCloset = W(220, 800, 220, 920);

  const vKitchenLiving = W(420, 0, 420, 400);
  const vCorridorBed1 = W(420, 400, 420, 620);

  const vCorridorBed2 = W(520, 400, 520, 620);
  const vEntranceMaster = W(520, 620, 520, 920);

  const vLivingRight = W(950, 0, 950, 400);
  const vBed2Right = W(950, 400, 950, 620);
  const vMasterRight = W(950, 620, 950, 920);

  // --- Doors (offset measured from each wall's first endpoint) ---
  const addD = (wallId: EntityId, offsetCm: number, width = 90) =>
    addOpening({ wallId, type: 'door', offsetCm: offsetCm * S, width, height: 210, elevation: 0 });

  addD(hEntranceFront, 150, 100);  // main entrance
  addD(vEntranceMaster, 90, 90);   // entrance → master bedroom
  addD(vEntranceBath, 90, 75);     // entrance → bathroom
  addD(vEntranceCloset, 60, 70);   // entrance → walk-in closet
  addD(hCorridorEntrance, 50, 80); // entrance → corridor
  addD(hLivingCorridor, 50, 80);   // corridor → living
  addD(vCorridorBed1, 110, 85);    // corridor → bedroom 1
  addD(vCorridorBed2, 110, 85);    // corridor → bedroom 2
  addD(vKitchenLiving, 280, 150);  // kitchen ↔ living (wide opening)
  addD(vBalconyKitchen, 300, 100); // kitchen → balcony

  // --- Windows ---
  const addW = (wallId: EntityId, offsetCm: number, width = 120, height = 120, elevation = 90) =>
    addOpening({ wallId, type: 'window', offsetCm: offsetCm * S, width, height, elevation });

  addW(hLivingTop, 250, 320, 150, 80); // large living-room window
  addW(vLivingRight, 200, 180);
  addW(hKitchenTop, 115, 130);
  addW(vBed1Left, 110, 140);
  addW(vBed2Right, 110, 140);
  addW(vMasterRight, 90, 120);
  addW(vMasterRight, 220, 120);
  addW(hMasterBottom, 220, 160);

  // Balcony: floor-to-low railing openings to read as an open balcony.
  addW(vBalconyLeft, 200, 320, 120, 0);
  addW(hBalconyTop, 95, 150, 120, 0);

  // Bathroom ventilation slot (high, narrow).
  addOpening({ wallId: vBathLeft, type: 'vent', offsetCm: 90 * S, width: 60, height: 50, elevation: 150 });

  // --- Detect rooms, then label/type them by nearest centroid ---
  const fresh = useAppStore.getState();
  const detected = detectRooms(fresh.vertices, fresh.walls);

  const roomMappings: { cx: number; cy: number; label: string; type: RoomType; floor: string }[] = [
    { cx: 95, cy: 200, label: 'Balcony', type: 'balcony', floor: 'concrete' },
    { cx: 305, cy: 200, label: 'Kitchen', type: 'kitchen', floor: 'tile' },
    { cx: 685, cy: 200, label: 'Living Room', type: 'living', floor: 'wood' },
    { cx: 210, cy: 510, label: 'Bedroom', type: 'bedroom', floor: 'wood' },
    { cx: 470, cy: 510, label: 'Corridor', type: 'corridor', floor: 'wood' },
    { cx: 735, cy: 510, label: 'Bedroom 2', type: 'bedroom', floor: 'wood' },
    { cx: 110, cy: 710, label: 'Bathroom', type: 'bathroom', floor: 'tile' },
    { cx: 110, cy: 860, label: 'Walk-in Closet', type: 'storage', floor: 'wood' },
    { cx: 370, cy: 770, label: 'Entrance', type: 'entrance', floor: 'tile' },
    { cx: 735, cy: 770, label: 'Master Bedroom', type: 'bedroom', floor: 'wood' },
  ];

  const nextRooms: Record<string, typeof detected[number]> = {};
  for (const room of detected) {
    const c = centroidOfIds(room.boundaryVertexIds, fresh.vertices);
    let best = roomMappings[0];
    let minD = Infinity;
    for (const m of roomMappings) {
      const dist = Math.hypot(c.x - m.cx * S, c.y - m.cy * S);
      if (dist < minD) { minD = dist; best = m; }
    }
    nextRooms[room.id] = { ...room, roomType: best.type, label: best.label, floorMaterialId: best.floor };
  }
  fresh.setRooms(nextRooms);

  // --- Furniture (modern) ---
  const place = (catalogId: string, x: number, y: number, rotation = 0) => {
    try {
      const entry = getCatalogEntry(catalogId);
      fresh.addFurniture({
        position: { x: x * S, y: y * S },
        rotation,
        scale: 1,
        catalogId,
        roomId: null,
        bounds: { width: entry.bounds.width, depth: entry.bounds.depth },
      });
    } catch { /* unknown catalog id — skip */ }
  };

  const HALF = Math.PI / 2;

  // Balcony
  place('plant', 60, 80);
  place('plant', 135, 330);

  // Kitchen
  place('kitchen-counter', 235, 200, HALF);
  place('fridge', 380, 60);

  // Living room
  place('tv-unit', 640, 35, Math.PI);
  place('rug', 640, 300);
  place('sofa-3seat', 640, 330);
  place('coffee-table', 640, 235);
  place('armchair', 490, 250, HALF);
  place('dining-table', 855, 130);
  place('plant', 910, 360);

  // Bedroom 1
  place('bed-queen', 150, 512);
  place('wardrobe', 370, 470, HALF);
  place('nightstand', 270, 430);

  // Bedroom 2
  place('bed-queen', 650, 512);
  place('wardrobe', 900, 470, HALF);
  place('nightstand', 540, 425);

  // Bathroom
  place('shower', 165, 680);
  place('vanity', 60, 655, Math.PI);
  place('toilet', 55, 765);
  place('washer', 170, 765);

  // Walk-in closet
  place('wardrobe', 110, 860);

  // Entrance
  place('sideboard', 350, 650, Math.PI);
  place('plant', 470, 870);

  // Master bedroom
  place('bed-queen', 730, 745);
  place('wardrobe', 900, 800, HALF);
  place('nightstand', 600, 670);
  place('nightstand', 840, 670);

  // Loading the sample is a fresh baseline — drop any prior undo history so the first
  // undo doesn't try to revert to an unrelated earlier plan.
  useAppStore.getState().clearHistory();
}

function centroidOfIds(ids: readonly EntityId[], vertices: Record<EntityId, Vertex>): Point2D {
  let x = 0, y = 0, n = 0;
  for (const id of ids) {
    const p = vertices[id]?.position;
    if (p) { x += p.x; y += p.y; n++; }
  }
  return n ? { x: x / n, y: y / n } : { x: 0, y: 0 };
}
