// src/domains/editor/services/samplePlan.ts

import { useAppStore } from '@/store';
import type { RoomType, EntityId, Vertex } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { detectRooms } from './roomDetection';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import { getOpeningKind } from '@/domains/shared/openings/openingCatalog';

/**
 * Loads the sample house, recreated as closely as possible from the reference 3D dollhouse
 * render: a larger single-storey home with a protruding bay-window nook at the front-left, a
 * big living room with a dark bookshelf wall, fireplace, sofa, coffee table and floral rug;
 * a kitchen, a foyer with stairs, a study, a home office, two more bedrooms and two
 * bathrooms (one ensuite) arranged across three bands.
 *
 * Coordinate system: centimeters, x→right, y→down (matching the plan image). Walls are
 * pre-segmented at every junction so neighbouring rooms share exact vertices, which is
 * what the planar-graph room detector needs.
 *
 *   x grid:  0   340      620   820      1080      1340
 *   y grid:  0 ───────────────── back band  (Bedroom / Kitchen / Foyer+Stairs / Study)
 *           300 ──────────────── middle band (Office / Bath / Corridor / Bedroom / Master Bath)
 *           560 ──────────────── front band  (Bay Nook / Living Room)
 *           900 ── front edge   (+ bay window bump-out to y=1000 under the nook)
 */
export function loadSampleHouse(): void {
  const store = useAppStore.getState();
  const { clearAll, addWall, addOpening } = store;
  store.resetFloors(); // sample house is a fresh single-storey baseline
  clearAll();

  // Spaciousness factor: every plan COORDINATE is multiplied by this while real-world sizes
  // (furniture footprints, door/window widths, wall height) stay fixed. The plan below is
  // authored at full real-world scale already, so S stays at 1.
  const S = 1;

  const W = (x1: number, y1: number, x2: number, y2: number) =>
    addWall({ x: x1 * S, y: y1 * S }, { x: x2 * S, y: y2 * S });

  // --- Horizontal walls (split at every vertical-wall junction) ---
  // y = 0  (back exterior)
  const hBed1Top = W(0, 0, 340, 0);
  const hKitchenTop = W(340, 0, 620, 0);
  W(620, 0, 820, 0);                       // foyer top
  const hStudyTop = W(820, 0, 1340, 0);

  // y = 300  (back | middle divider)
  const hBed1Office = W(0, 300, 340, 300);
  W(340, 300, 620, 300);                   // kitchen | bath
  const hFoyerCorridor = W(620, 300, 820, 300);
  W(820, 300, 1080, 300);                  // study | bedroom
  W(1080, 300, 1340, 300);                 // study | master bath

  // y = 560  (middle | front divider)
  const hOfficeNook = W(0, 560, 340, 560);
  W(340, 560, 620, 560);                   // bath | living
  const hCorridorLiving = W(620, 560, 820, 560);
  W(820, 560, 1080, 560);                  // bedroom | living
  W(1080, 560, 1340, 560);                 // master bath | living

  // y = 900  (front exterior) — living front + bay-window bump under the nook
  W(0, 900, 60, 900);
  const hBumpLeft = W(60, 900, 60, 1000);
  const hBumpFront = W(60, 1000, 280, 1000);
  const hBumpRight = W(280, 1000, 280, 900);
  W(280, 900, 340, 900);
  const hLivingFront = W(340, 900, 1340, 900);

  // --- Vertical walls (split at every horizontal-wall junction) ---
  // x = 0 (left exterior)
  const vBed1Left = W(0, 0, 0, 300);
  const vOfficeLeft = W(0, 300, 0, 560);
  const vNookLeft = W(0, 560, 0, 900);

  // x = 340
  W(340, 0, 340, 300);                     // bed1 | kitchen
  W(340, 300, 340, 560);                   // office | bath
  const vNookLiving = W(340, 560, 340, 900);

  // x = 620
  const vKitchenFoyer = W(620, 0, 620, 300);
  const vBathCorridor = W(620, 300, 620, 560);

  // x = 820
  const vFoyerStudy = W(820, 0, 820, 300);
  const vCorridorBed = W(820, 300, 820, 560);

  // x = 1080
  const vBedMaster = W(1080, 300, 1080, 560);

  // x = 1340 (right exterior)
  const vStudyRight = W(1340, 0, 1340, 300);
  const vMasterRight = W(1340, 300, 1340, 560);
  const vLivingRight = W(1340, 560, 1340, 900);

  // --- Doors (offset measured from each wall's first endpoint) ---
  const addD = (wallId: EntityId, offsetCm: number, width = 85) =>
    addOpening({ wallId, type: 'door', offsetCm: offsetCm * S, width, height: 210, elevation: 0 });

  // Main gate: the front entrance, rendered as a proper villa gate that faces outward in 3D.
  const mainGate = getOpeningKind('door-main-gate');
  addOpening({
    wallId: hLivingFront,
    type: 'door',
    kind: 'door-main-gate',
    offsetCm: 500 * S,
    width: mainGate?.width ?? 160,
    height: mainGate?.height ?? 240,
    elevation: 0,
  });

  addD(vNookLiving, 140, 90);     // living ↔ bay nook
  addD(hOfficeNook, 170, 80);     // office ↔ nook
  addD(hCorridorLiving, 100, 95); // corridor ↔ living
  addD(hFoyerCorridor, 100, 90);  // foyer ↔ corridor
  addD(vBathCorridor, 130, 80);   // corridor ↔ bathroom
  addD(vCorridorBed, 130, 85);    // corridor ↔ bedroom
  addD(vBedMaster, 130, 75);      // bedroom ↔ master bath (ensuite)
  addD(vKitchenFoyer, 150, 90);   // foyer ↔ kitchen
  addD(vFoyerStudy, 150, 90);     // foyer ↔ study
  addD(hBed1Office, 170, 80);     // bedroom ↔ office

  // --- Windows ---
  const addW = (wallId: EntityId, offsetCm: number, width = 120, height = 120, elevation = 90) =>
    addOpening({ wallId, type: 'window', offsetCm: offsetCm * S, width, height, elevation });

  addW(hBed1Top, 170, 120);
  addW(vBed1Left, 150, 120);
  addW(hKitchenTop, 140, 120);
  addW(hStudyTop, 360, 160, 140, 90);
  addW(vStudyRight, 150, 120);
  addW(vOfficeLeft, 130, 120);
  addW(vMasterRight, 130, 100);
  addW(vLivingRight, 170, 150, 150, 80);
  addW(hLivingFront, 200, 160, 150, 80);  // large living window left of door
  addW(hLivingFront, 760, 160, 150, 80);  // large living window right of door
  addW(vNookLeft, 170, 120);

  // Bay window: the three faces of the front bump-out, floor-to-near-ceiling glass.
  addW(hBumpFront, 110, 140, 160, 30);
  addW(hBumpLeft, 50, 70, 160, 30);
  addW(hBumpRight, 50, 70, 160, 30);

  // Bathroom ventilation slot (high, narrow).
  addOpening({ wallId: vBathCorridor, type: 'vent', offsetCm: 220 * S, width: 50, height: 45, elevation: 170 });

  // --- Detect rooms, then label/type them by nearest centroid ---
  const fresh = useAppStore.getState();
  const detected = detectRooms(fresh.vertices, fresh.walls);

  const roomMappings: { cx: number; cy: number; label: string; type: RoomType; floor: string; wall: string }[] = [
    { cx: 170, cy: 150, label: 'Bedroom', type: 'bedroom', floor: 'floor-wood', wall: 'paint-powder' },
    { cx: 480, cy: 150, label: 'Kitchen', type: 'kitchen', floor: 'floor-checker', wall: 'paint-mustard' },
    { cx: 720, cy: 150, label: 'Foyer & Stairs', type: 'entrance', floor: 'floor-marble', wall: 'paint-cream' },
    { cx: 1080, cy: 150, label: 'Study', type: 'study', floor: 'floor-wood-dark', wall: 'paint-navy' },
    { cx: 170, cy: 430, label: 'Home Office', type: 'study', floor: 'floor-wood', wall: 'paint-ochre' },
    { cx: 480, cy: 430, label: 'Bathroom', type: 'bathroom', floor: 'floor-ceramic', wall: 'paint-mint' },
    { cx: 720, cy: 430, label: 'Corridor', type: 'corridor', floor: 'floor-wood', wall: 'paint-linen' },
    { cx: 950, cy: 430, label: 'Bedroom 2', type: 'bedroom', floor: 'floor-wood', wall: 'paint-grey' },
    { cx: 1210, cy: 430, label: 'Master Bath', type: 'bathroom', floor: 'floor-slate', wall: 'paint-powder' },
    { cx: 170, cy: 790, label: 'Bay Window Nook', type: 'living', floor: 'floor-wood-light', wall: 'paint-cream' },
    { cx: 840, cy: 730, label: 'Living Room', type: 'living', floor: 'floor-wood', wall: 'paint-sage' },
  ];

  const nextRooms: Record<string, typeof detected[number]> = {};
  const roomWallColors: { boundaryVertexIds: readonly EntityId[]; wall: string }[] = [];
  for (const room of detected) {
    const c = centroidOfIds(room.boundaryVertexIds, fresh.vertices);
    let best = roomMappings[0];
    let minD = Infinity;
    for (const m of roomMappings) {
      const dist = Math.hypot(c.x - m.cx * S, c.y - m.cy * S);
      if (dist < minD) { minD = dist; best = m; }
    }
    nextRooms[room.id] = { ...room, roomType: best.type, label: best.label, floorMaterialId: best.floor };
    roomWallColors.push({ boundaryVertexIds: room.boundaryVertexIds, wall: best.wall });
  }
  fresh.setRooms(nextRooms);

  // --- Paint the walls -------------------------------------------------------
  // Base finish (the fallback for any face we don't paint) reads as a clean villa exterior;
  // then each room paints the INTERIOR face of its bounding walls with its own colour, so a
  // shared partition can carry a different colour on each side (e.g. mint bath ↔ navy study).
  const painted = useAppStore.getState();
  for (const wallId of Object.keys(painted.walls)) {
    painted.updateWall(wallId, { materialId: 'wall-plaster' });
  }

  // Map an unordered vertex-id pair → the wall joining them, so room boundary edges resolve
  // back to their wall.
  const edgeKey = (a: EntityId, b: EntityId) => (a < b ? `${a}|${b}` : `${b}|${a}`);
  const edgeToWall = new Map<string, EntityId>();
  for (const w of Object.values(painted.walls)) {
    edgeToWall.set(edgeKey(w.startVertexId, w.endVertexId), w.id);
  }

  for (const { boundaryVertexIds, wall: color } of roomWallColors) {
    const poly = boundaryVertexIds
      .map((id) => painted.vertices[id]?.position)
      .filter((p): p is Point2D => Boolean(p));
    if (poly.length < 3) continue;
    for (let i = 0; i < boundaryVertexIds.length; i++) {
      const a = boundaryVertexIds[i];
      const b = boundaryVertexIds[(i + 1) % boundaryVertexIds.length];
      const wallId = edgeToWall.get(edgeKey(a, b));
      if (!wallId) continue;
      const w = painted.walls[wallId];
      const s = painted.vertices[w.startVertexId]?.position;
      const e = painted.vertices[w.endVertexId]?.position;
      if (!s || !e) continue;
      // Wall's +normal (side A) is plan direction (dy, -dx); side B is the opposite face.
      const dx = e.x - s.x, dy = e.y - s.y;
      const len = Math.hypot(dx, dy) || 1;
      const nx = dy / len, ny = -dx / len;
      const mx = (s.x + e.x) / 2, my = (s.y + e.y) / 2;
      const probe = w.thickness / 2 + 5;
      const onSideA = pointInPoly({ x: mx + nx * probe, y: my + ny * probe }, poly);
      painted.updateWall(wallId, onSideA ? { materialSideA: color } : { materialSideB: color });
    }
  }

  // --- Furniture ---
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

  // Bedroom (back-left)
  place('bed-queen', 180, 150);
  place('nightstand', 60, 50);
  place('wardrobe', 300, 150, HALF);

  // Kitchen (back, yellow-tiled)
  place('kitchen-counter-end', 365, 45);
  place('kitchen-counter', 460, 45);
  place('stove', 555, 45);
  place('fridge', 585, 255, Math.PI);
  place('kitchen-counter', 365, 255, Math.PI);

  // Foyer & stairs
  place('sideboard', 720, 270, Math.PI);
  place('plant', 660, 60);
  place('plant', 785, 70);

  // Study (back-right, navy)
  place('desk', 1010, 55);
  place('chair-office', 1010, 120);
  place('bookshelf', 860, 150, HALF);
  place('sideboard', 1250, 55);
  place('plant-leafy', 1300, 255);

  // Home office (middle-left, orange)
  place('desk', 170, 335);
  place('chair-office', 170, 405);
  place('bookshelf', 55, 440, HALF);
  place('plant', 305, 520);

  // Bathroom (middle-centre)
  place('vanity', 360, 360, HALF);
  place('toilet', 600, 350, -HALF);
  place('bathtub', 480, 500);

  // Corridor
  place('plant', 780, 520);

  // Bedroom 2 (middle, striped bed)
  place('bed-queen', 950, 430, Math.PI);
  place('nightstand', 845, 320);
  place('nightstand', 1055, 320);

  // Master bath (middle-right, spa / stone)
  place('bathtub', 1285, 440, HALF);
  place('vanity', 1110, 330);
  place('shower', 1285, 340);
  place('plant', 1115, 520);

  // Living room (front, the showpiece)
  place('bookshelf', 380, 630, HALF);
  place('bookshelf', 380, 760, HALF);
  place('fireplace', 362, 700, HALF);
  place('sofa-3seat', 640, 605);
  place('coffee-table', 660, 720);
  place('rug', 700, 745);
  place('dining-chair', 540, 745, HALF);
  place('dining-chair', 800, 745, -HALF);
  place('armchair', 940, 640, Math.PI);
  place('armchair', 860, 850);
  place('sideboard', 1120, 585, Math.PI);
  place('plant-leafy', 1290, 860);

  // Bay window nook (front-left)
  place('armchair', 170, 740);
  place('ottoman', 170, 830);
  place('plant', 70, 610);
  place('plant', 280, 610);

  // Loading the sample is a fresh baseline — drop any prior undo history so the first
  // undo doesn't try to revert to an unrelated earlier plan.
  useAppStore.getState().clearHistory();
  // Center the freshly loaded house in the 2D editor.
  useAppStore.getState().requestFitView();
}

function centroidOfIds(ids: readonly EntityId[], vertices: Record<EntityId, Vertex>): Point2D {
  let x = 0, y = 0, n = 0;
  for (const id of ids) {
    const p = vertices[id]?.position;
    if (p) { x += p.x; y += p.y; n++; }
  }
  return n ? { x: x / n, y: y / n } : { x: 0, y: 0 };
}

/** Ray-casting point-in-polygon test (polygon points in world cm). */
function pointInPoly(p: Point2D, polygon: readonly Point2D[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y;
    const xj = polygon[j].x, yj = polygon[j].y;
    const intersect = yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}
