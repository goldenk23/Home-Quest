import { describe, it, expect } from 'vitest';
import { convertVastuLayout, importVastuLayout } from '../importVastu';
import { useAppStore } from '@/store';
import { validateFloorPlanIntegrity } from '../validation';
import { createWallGeometry } from '@/domains/viewer/services/extrusion';
import type { Opening } from '@/types/editor';

// A minimal NATIVE Python layout (layout_serializer.serialize_layout shape), in pixels.
// grid_spacing 35 px per unit, unit ft (30.48 cm) → 350px = 10ft = 304.8cm.
const nativeFixture = {
  version: '1.0',
  metadata: { unit: 'ft', grid_spacing: 35, canvas_width: 800, canvas_height: 600 },
  rooms: [
    {
      name: 'Kitchen',
      x0: 0, y0: 0, x1: 350, y1: 350,
      fill_mode: 'filled',
      fill_color: '#eeddaa',
      flooring: { has_flooring: true, flooring_type: 'wood' },
    },
  ],
  furniture: [{ image_name: 'double_bed', x: 175, y: 175, scale: 1, angle: 0 }],
  shapes: [],
  text: [{ content: 'Note', x: 100, y: 100, font: 'Arial 12', color: '#ffffff' }],
  compass: { direction: 'E' },
};

const PX = 30.48 / 35; // 1 px → cm at the fixture's grid

describe('convertVastuLayout', () => {
  const { geometry, northDeg, report } = convertVastuLayout(nativeFixture);

  it('produces the expected entity counts', () => {
    expect(report.rooms).toBe(1);
    expect(report.walls).toBe(4);
    expect(report.furniture).toBe(1);
    expect(report.annotations).toBe(1);
    expect(Object.keys(geometry.vertices)).toHaveLength(4);
  });

  it('converts px → cm correctly (350px @ 35/ft → 304.8cm)', () => {
    const xs = Object.values(geometry.vertices).map((v) => v.position.x);
    expect(Math.max(...xs)).toBeCloseTo(304.8, 2);
  });

  it('populates widened fields (fill mode, floor material, room type, north)', () => {
    const room = Object.values(geometry.rooms)[0];
    expect(room.roomType).toBe('kitchen');
    expect(room.floorMaterialId).toBe('floor-wood');
    expect(room.fillMode).toBe('filled');
    expect(room.fillColor).toBe('#eeddaa');
    expect(northDeg).toBe(90); // E
  });

  it('every wall references existing vertices (integrity)', () => {
    for (const w of Object.values(geometry.walls)) {
      expect(geometry.vertices[w.startVertexId]).toBeDefined();
      expect(geometry.vertices[w.endVertexId]).toBeDefined();
    }
  });

  it('3D smoke: each wall extrudes to valid geometry (renders in 3D)', () => {
    for (const w of Object.values(geometry.walls)) {
      const a = geometry.vertices[w.startVertexId].position;
      const b = geometry.vertices[w.endVertexId].position;
      const geo = createWallGeometry(a, b, w.thickness, w.height, undefined, []);
      const pos = geo.getAttribute('position');
      expect(pos).toBeTruthy();
      expect(pos.count).toBeGreaterThan(0);
      for (let i = 0; i < pos.array.length; i++) {
        expect(Number.isNaN(pos.array[i])).toBe(false);
      }
    }
  });
});

describe('doors → openings', () => {
  it('places a singlehand door on the closest wall, centred at its projection', () => {
    const { geometry, report } = convertVastuLayout({
      ...nativeFixture,
      rooms: [{ name: 'Room', x0: 0, y0: 0, x1: 350, y1: 350 }],
      furniture: [{ image_name: 'singlehand_door', x: 175, y: 5 }],
      text: [],
    });
    expect(report.openings).toBe(1);
    const op = Object.values(geometry.openings)[0] as Opening;
    expect(op.type).toBe('door');
    expect(op.kind).toBe('door-standard');
    expect(op.width).toBe(90);
    expect(op.height).toBe(210);
    expect(op.elevation).toBe(0);
    // Door sits 175px along the top wall (start vertex at x=0) → 152.4cm centre offset.
    const wall = geometry.walls[op.wallId];
    expect(wall).toBeDefined();
    expect(op.offsetCm).toBeCloseTo(175 * PX, 1);
    expect(wall.openingIds).toContain(op.id);
  });

  it('maps doublehand doors to the double-door kind', () => {
    const { geometry } = convertVastuLayout({
      ...nativeFixture,
      rooms: [{ name: 'Room', x0: 0, y0: 0, x1: 350, y1: 350 }],
      furniture: [{ image_name: 'doublehand_door', x: 175, y: 5 }],
      text: [],
    });
    const op = Object.values(geometry.openings)[0] as Opening;
    expect(op.kind).toBe('door-double');
    expect(op.width).toBe(150);
  });

  it('reports doors that are not near any wall instead of misplacing them', () => {
    const { report } = convertVastuLayout({
      ...nativeFixture,
      rooms: [{ name: 'Room', x0: 0, y0: 0, x1: 350, y1: 350 }],
      furniture: [{ image_name: 'singlehand_door', x: 5000, y: 5000 }],
      text: [],
    });
    expect(report.openings).toBe(0);
    expect(report.residuals.some((r) => r.includes('door'))).toBe(true);
  });
});

describe('wall_erased_regions → openings', () => {
  it('converts a partial top-side gap into a centred window opening', () => {
    const { geometry, report } = convertVastuLayout({
      ...nativeFixture,
      rooms: [{
        name: 'Room', x0: 0, y0: 0, x1: 350, y1: 350,
        fill_mode: 'walls_only',
        wall_erased_regions: { top: [[100, 200]] },
      }],
      furniture: [],
      text: [],
    });
    expect(report.openings).toBe(1);
    const op = Object.values(geometry.openings)[0] as Opening;
    expect(op.type).toBe('window');
    expect(op.kind).toBe('window-standard');
    expect(op.elevation).toBe(90);
    expect(op.width).toBeCloseTo(100 * PX, 1); // 100px gap
    expect(op.offsetCm).toBeCloseTo(150 * PX, 1); // gap centre, top wall starts at x=0
  });

  it('measures offsets from the wall start vertex even on reversed sides (bottom)', () => {
    const { geometry } = convertVastuLayout({
      ...nativeFixture,
      rooms: [{
        name: 'Room', x0: 0, y0: 0, x1: 350, y1: 350,
        fill_mode: 'walls_only',
        wall_erased_regions: { bottom: [[100, 200]] },
      }],
      furniture: [],
      text: [],
    });
    const op = Object.values(geometry.openings)[0] as Opening;
    // Bottom wall runs from (304.8, −304.8) → (0, −304.8): gap centre at x=130.63cm
    // is 304.8 − 130.63 = 174.17cm from the start vertex.
    expect(op.offsetCm).toBeCloseTo(304.8 - 150 * PX, 1);
    expect(op.width).toBeCloseTo(100 * PX, 1);
  });

  it('treats a side-spanning gap as an erased wall (no wall, no opening)', () => {
    const { report } = convertVastuLayout({
      ...nativeFixture,
      rooms: [{
        name: 'Room', x0: 0, y0: 0, x1: 350, y1: 350,
        fill_mode: 'walls_only',
        // left/right axes are inset by one stroke (0.2ft = 7px) at each end → [7, 343] spans it
        wall_erased_regions: { left: [[7, 343]] },
      }],
      furniture: [],
      text: [],
    });
    expect(report.walls).toBe(3); // left wall skipped
    expect(report.openings).toBe(0);
  });

  it('a door placed on a recut wall claims the gap (one door opening, no window)', () => {
    const { geometry, report } = convertVastuLayout({
      ...nativeFixture,
      rooms: [{
        name: 'Room', x0: 0, y0: 0, x1: 350, y1: 350,
        fill_mode: 'walls_only',
        wall_erased_regions: { top: [[130, 234]] }, // the recut the door made
      }],
      furniture: [{ image_name: 'singlehand_door', x: 182, y: 5 }],
      text: [],
    });
    expect(report.openings).toBe(1);
    const op = Object.values(geometry.openings)[0] as Opening;
    expect(op.type).toBe('door');
    expect(op.kind).toBe('door-standard');
    expect(op.offsetCm).toBeCloseTo(182 * PX, 1); // gap centre at 182px
    expect(op.width).toBeCloseTo(104 * PX, 1); // actual cut width wins over catalog default
  });

  it('REGRESSION: ignores bogus erased regions on filled/transparent rooms', () => {
    // The Python serializer emits wall_erased_regions for EVERY room; for non-walls_only
    // rooms there are no wall-stroke rectangles to diff, so all 4 sides arrive as bogus
    // full-side gaps. Honouring them deletes every wall of the room (the "missing walls"
    // bug). They must be ignored entirely.
    for (const fill_mode of ['filled', 'transparent']) {
      const { report } = convertVastuLayout({
        ...nativeFixture,
        rooms: [{
          name: 'Room', x0: 0, y0: 0, x1: 350, y1: 350,
          fill_mode,
          wall_erased_regions: { top: [[0, 350]], bottom: [[0, 350]], left: [[7, 343]], right: [[7, 343]] },
        }],
        furniture: [],
        text: [],
      });
      expect(report.walls).toBe(4); // all walls survive
      expect(report.openings).toBe(0);
    }
  });
});

describe('wall graph cleanup', () => {
  it('snaps overlapping adjacent rooms to one shared wall (no double walls)', () => {
    const { geometry, report } = convertVastuLayout({
      ...nativeFixture,
      rooms: [
        { name: 'A', x0: 0, y0: 0, x1: 350, y1: 350 },
        { name: 'B', x0: 346, y0: 0, x1: 700, y1: 350 }, // 4px ≈ 3.5cm overlap
      ],
      furniture: [],
      text: [],
    });
    expect(report.rooms).toBe(2);
    // 6 unique corners after snapping; the shared boundary is one wall, not two.
    expect(Object.keys(geometry.vertices)).toHaveLength(6);
    expect(report.walls).toBe(7);
  });

  it('splits walls at T-junctions and dedupes the halves', () => {
    const { geometry, report } = convertVastuLayout({
      ...nativeFixture,
      rooms: [
        { name: 'A', x0: 0, y0: 0, x1: 700, y1: 350 },
        { name: 'B', x0: 0, y0: 350, x1: 350, y1: 700 }, // its top side T-joins A's bottom
      ],
      furniture: [],
      text: [],
    });
    expect(report.rooms).toBe(2);
    expect(Object.keys(geometry.vertices)).toHaveLength(7);
    expect(report.walls).toBe(8); // A.bottom split in two; the shared half is one wall
    // No duplicate walls between the same vertex pair.
    const pairs = new Set<string>();
    for (const w of Object.values(geometry.walls)) {
      const key = [w.startVertexId, w.endVertexId].sort().join('|');
      expect(pairs.has(key)).toBe(false);
      pairs.add(key);
    }
    // Room A's boundary is re-stitched through the T-junction vertex (4 corners + 1 split
    // point) so its vertex set matches what face detection will find — metadata survives.
    const roomA = Object.values(geometry.rooms).find((r) => r.label === 'A')!;
    const roomB = Object.values(geometry.rooms).find((r) => r.label === 'B')!;
    expect(roomA.boundaryVertexIds).toHaveLength(5);
    expect(roomB.boundaryVertexIds).toHaveLength(4);
  });
});

describe('polygon shapes → rooms', () => {
  const polygonLayout = {
    ...nativeFixture,
    rooms: [],
    furniture: [],
    shapes: [
      {
        id: 'shape_1', type: 'polygon',
        points: [[0, 0], [350, 0], [350, 350], [0, 350]],
        tags: ['closed_shape', 'polygon_group_abc', 'polygon_shape'],
        flooring: { has_flooring: true, flooring_type: 'marble' },
      },
      // canvas decorations that must be ignored:
      { id: 'shape_2', type: 'oval', points: [[-2, -2], [2, 2]], tags: ['polygon_group_abc', 'polygon_vertex'] },
      { id: 'shape_3', type: 'text', points: [[175, 175]], tags: ['polygon_group_abc', 'polygon_label'] },
    ],
    text: [
      { content: 'Bedroom\n12×12 ft', x: 175, y: 175, tags: ['polygon_group_abc', 'polygon_label'], font: 'Arial 10', color: 'black' },
    ],
  };

  it('creates a Room with the group label, inferred type and flooring', () => {
    const { geometry, report } = convertVastuLayout(polygonLayout);
    expect(report.rooms).toBe(1);
    expect(report.walls).toBe(4);
    const room = Object.values(geometry.rooms)[0];
    expect(room.label).toBe('Bedroom');
    expect(room.roomType).toBe('bedroom');
    expect(room.floorMaterialId).toBe('floor-marble');
    expect(room.boundaryVertexIds).toHaveLength(4);
  });

  it('does not duplicate the polygon label as a floating annotation', () => {
    const { report } = convertVastuLayout(polygonLayout);
    expect(report.annotations).toBe(0);
  });
});

describe('end-to-end: full-featured native layout', () => {
  // One layout exercising everything at once: adjacent rect rooms with a door (recut gap),
  // a window gap, a fully erased side, a labelled polygon room, mapped + unmapped
  // furniture, a note, and a compass direction.
  const full = {
    version: '1.0',
    metadata: { unit: 'ft', grid_spacing: 35, canvas_width: 1200, canvas_height: 900 },
    rooms: [
      {
        name: 'Kitchen', x0: 0, y0: 0, x1: 350, y1: 350,
        fill_mode: 'walls_only', fill_color: '#eeddaa',
        flooring: { has_flooring: true, flooring_type: 'tile' },
        wall_erased_regions: { right: [[150, 250]] }, // window into the living room
      },
      {
        name: 'Living Room', x0: 346, y0: 0, x1: 1046, y1: 350,
        fill_mode: 'walls_only',
        flooring: { has_flooring: true, flooring_type: 'wood' },
        wall_erased_regions: { bottom: [[600, 700]] }, // door recut
      },
    ],
    shapes: [
      {
        id: 'shape_p', type: 'polygon',
        points: [[0, 350], [350, 350], [350, 700], [0, 700]],
        tags: ['closed_shape', 'polygon_group_bed', 'polygon_shape'],
        flooring: { has_flooring: false },
      },
    ],
    furniture: [
      { image_name: 'singlehand_door', x: 650, y: 345 },
      { image_name: 'double_bed', x: 175, y: 525, angle: 90, scale: 1 },
      { image_name: 'mystery_thing', x: 500, y: 100 },
    ],
    text: [
      { content: 'Master Bedroom', x: 175, y: 525, tags: ['polygon_group_bed', 'polygon_label'], font: 'Arial 10', color: 'black' },
      { content: 'North facing plot', x: 100, y: 50, font: 'Arial 12', color: '#333333' },
    ],
    compass: { direction: 'N' },
  };

  const { geometry, northDeg, report } = convertVastuLayout(full);

  it('converts every feature class', () => {
    expect(report.rooms).toBe(3); // kitchen + living + polygon bedroom
    expect(report.openings).toBe(2); // window gap + claimed door gap
    expect(report.furniture).toBe(1); // bed only; unknown furniture is reported and marked in 2D
    expect(report.annotations).toBe(2); // note + unavailable-asset marker; polygon label became the room label
    expect(northDeg).toBe(0);
    expect(report.unmapped).toEqual(['mystery_thing']);
    expect(Object.values(geometry.annotations)).toContainEqual(expect.objectContaining({
      text: '⚠ ASSET UNAVAILABLE: mystery_thing',
      color: '#ef4444',
      fontSizeCm: 18,
    }));
  });

  it('classifies the two gaps correctly (window vs door)', () => {
    const ops = Object.values(geometry.openings);
    expect(ops.filter((o) => o.type === 'window')).toHaveLength(1);
    expect(ops.filter((o) => o.type === 'door')).toHaveLength(1);
    const door = ops.find((o) => o.type === 'door')!;
    expect(door.kind).toBe('door-standard');
    expect(door.width).toBeCloseTo(100 * PX, 1); // the recut width
  });

  it('labels and types all rooms', () => {
    const labels = Object.values(geometry.rooms).map((r) => `${r.label}:${r.roomType}`).sort();
    expect(labels).toEqual(['Kitchen:kitchen', 'Living Room:living', 'Master Bedroom:bedroom']);
  });

  it('types "Master Bath" as bathroom, not bedroom (keyword order)', () => {
    const { geometry: g } = convertVastuLayout({
      ...nativeFixture,
      rooms: [{ name: 'Master Bath', x0: 0, y0: 0, x1: 350, y1: 350 }],
      furniture: [],
      text: [],
    });
    expect(Object.values(g.rooms)[0].roomType).toBe('bathroom');
  });

  it('passes Home Quest’s own floor-plan integrity validation', () => {
    const result = validateFloorPlanIntegrity(geometry);
    expect(result.errors).toEqual([]);
    expect(result.valid).toBe(true);
  });

  it('extrudes every wall to NaN-free 3D geometry, openings included', () => {
    for (const w of Object.values(geometry.walls)) {
      const a = geometry.vertices[w.startVertexId].position;
      const b = geometry.vertices[w.endVertexId].position;
      const ops = w.openingIds.map((id) => geometry.openings[id]);
      const geo = createWallGeometry(a, b, w.thickness, w.height, undefined, ops);
      const pos = geo.getAttribute('position');
      expect(pos.count).toBeGreaterThan(0);
      for (let i = 0; i < pos.array.length; i++) expect(Number.isNaN(pos.array[i])).toBe(false);
    }
  });
});


const emptyV2Geometry = () => ({
  vertices: [], walls: [], rooms: [], openings: [], furniture: [], shapes: [], text: [],
  pillars: [], beams: [], deck_slabs: [], railings: [],
});

const nativeV2Fixture = () => ({
  version: '2.0',
  metadata: { unit: 'cm', grid_spacing: 1, zoom_level: 1, unit_scale: 1, wall_height_cm: 280 },
  active_floor_id: 'floor-upper',
  floors: [
    {
      id: 'floor-ground', name: 'Ground Floor', elevation_cm: 0,
      geometry: {
        ...emptyV2Geometry(),
        vertices: [
          { id: 'g-v1', position: [100, 100] },
          { id: 'g-v2', position: [200, 100] },
          { id: 'g-v3', position: [200, 200] },
        ],
        walls: [{
          id: 'g-wall', start_vertex_id: 'g-v1', end_vertex_id: 'g-v2',
          thickness_cm: 20, height_cm: 280, material_id: 'paint-white', opening_ids: [],
        }],
        rooms: [{
          id: 'g-room', boundary_vertex_ids: ['g-v1', 'g-v2', 'g-v3'],
          label: 'Ground Room', room_type: 'living', floor_material_id: 'floor-wood',
        }],
        text: [{ id: 'g-text', position: [110, 110], text: 'Ground', font_size_cm: 16, color: '#111111' }],
      },
    },
    {
      id: 'floor-upper', name: 'Upper Floor', elevation_cm: 300,
      geometry: {
        ...emptyV2Geometry(),
        compass: { north_deg_clockwise: 35 },
        vertices: [
          { id: 'u-v1', position: [100, 100] },
          { id: 'u-v2', position: [200, 100] },
          { id: 'u-v3', position: [200, 200] },
        ],
        walls: [{
          id: 'u-wall', start_vertex_id: 'u-v1', end_vertex_id: 'u-v2',
          thickness_cm: 25, height_cm: 290, material_id: 'paint-white',
          material_side_a: 'paint-sage', material_side_b: 'floor-wood', opening_ids: ['u-opening'],
        }],
        rooms: [{
          id: 'u-room', boundary_vertex_ids: ['u-v1', 'u-v2', 'u-v3'],
          label: 'Upper Room', room_type: 'bedroom', floor_material_id: 'paint-white',
        }],
        openings: [{
          id: 'u-opening', wall_id: 'u-wall', type: 'window', kind: 'window-sliding',
          offset_cm: 50, width_cm: 120, height_cm: 100, elevation_cm: 90,
        }],
        furniture: [{ id: 'u-bed', position: [150, 150], catalog_id: 'bed-queen', angle_deg: 90, scale: 1, room_id: 'u-room' }],
        pillars: [{
          id: 'u-pillar', position: [120, 120], width_cm: 30, depth_cm: 35,
          height_cm: 260, elevation_cm: 10, shape: 'rect', material_id: 'floor-marble',
        }],
        beams: [{
          id: 'u-beam', start: [100, 100], end: [200, 100], width_cm: 20,
          depth_cm: 35, elevation_cm: 250, material_id: 'wall-concrete',
        }],
        deck_slabs: [{
          id: 'u-deck', polygon: [[100, 100], [200, 100], [200, 200]],
          thickness_cm: 18, elevation_cm: 5, type: 'balcony', material_id: 'paint-sage',
        }],
        railings: [{
          id: 'u-railing', start: [100, 100], end: [200, 100], height_cm: 105,
          elevation_cm: 18, style: 'open', material_id: 'paint-grey',
        }],
        text: [{ id: 'u-text', position: [110, 110], text: 'Upper', font_size_cm: 16, color: '#222222' }],
      },
    },
  ],
  sun_settings: { time_hours: 15.5, azimuth_deg: 210, direction_override: true },
  cross_floor_references: [{
    id: 'alignment-1', type: 'alignment',
    source_floor_id: 'floor-ground', source_entity_id: 'g-v1',
    target_floor_id: 'floor-upper', target_entity_id: 'u-v1',
  }],
});

describe('native v2 projects', () => {
  it('preserves IDs and applies one shared origin shift to aligned floors', () => {
    const { project } = convertVastuLayout(nativeV2Fixture());
    expect(project).toBeDefined();
    expect(project!.floors).toEqual([
      { id: 'floor-ground', name: 'Ground Floor', elevationCm: 0 },
      { id: 'floor-upper', name: 'Upper Floor', elevationCm: 300 },
    ]);
    expect(project!.activeFloorId).toBe('floor-upper');
    expect(project!.geometryByFloor['floor-ground'].vertices['g-v1'].position)
      .toEqual(project!.geometryByFloor['floor-upper'].vertices['u-v1'].position);
    expect(project!.geometryByFloor['floor-ground'].vertices['g-v2'].position)
      .toEqual(project!.geometryByFloor['floor-upper'].vertices['u-v2'].position);
  });

  it('converts structures, sun, and category-fallback finishes', () => {
    const { project, report } = convertVastuLayout(nativeV2Fixture());
    const upper = project!.geometryByFloor['floor-upper'];
    expect(upper.walls['u-wall']).toEqual(expect.objectContaining({
      id: 'u-wall', thickness: 25, height: 290,
      materialId: 'paint-white', materialSideA: 'paint-sage', materialSideB: 'default-wall',
    }));
    expect(upper.pillars['u-pillar']).toEqual(expect.objectContaining({
      width: 30, depth: 35, height: 260, elevationCm: 10, materialId: 'default-wall',
    }));
    expect(upper.beams['u-beam']).toEqual(expect.objectContaining({ width: 20, depth: 35, elevationCm: 250 }));
    expect(upper.deckSlabs['u-deck']).toEqual(expect.objectContaining({
      thicknessCm: 18, elevationCm: 5, type: 'balcony', materialId: 'default-floor',
    }));
    expect(upper.rooms['u-room'].floorMaterialId).toBe('default-floor');
    expect(project!.sunSettings).toEqual({ timeHours: 15.5, azimuthDeg: 210, directionOverride: true });
    expect(project!.northDeg).toBe(35);
    expect(report.residuals).toEqual(expect.arrayContaining([
      expect.stringContaining('material_side_b'),
      expect.stringContaining('pillars[0].material_id'),
      expect.stringContaining('deck_slabs[0].material_id'),
    ]));
  });

  it('atomically hydrates the active floor, parked floor, structures, north, and sun', () => {
    importVastuLayout(nativeV2Fixture());
    const state = useAppStore.getState();
    expect(state.activeFloorId).toBe('floor-upper');
    expect(state.vertices['u-v1']).toBeDefined();
    expect(state.pillars['u-pillar']).toBeDefined();
    expect(state.beams['u-beam']).toBeDefined();
    expect(state.deckSlabs['u-deck']).toBeDefined();
    expect(state.railings['u-railing']).toBeDefined();
    expect(state.annotations['u-text']).toBeDefined();
    expect(state.floorData['floor-ground'].vertices['g-v1']).toBeDefined();
    expect(state.floorData['floor-upper']).toBeUndefined();
    expect(state.vastuNorthDeg).toBe(35);
    expect([state.sunTimeHours, state.sunAzimuthDeg, state.sunDirectionOverride]).toEqual([15.5, 210, true]);
  });

  it('rejects an invalid second floor without mutating any store state', () => {
    importVastuLayout(nativeV2Fixture());
    const before = useAppStore.getState();
    const snapshot = {
      floors: before.floors,
      activeFloorId: before.activeFloorId,
      floorData: before.floorData,
      vertices: before.vertices,
      sun: [before.sunTimeHours, before.sunAzimuthDeg, before.sunDirectionOverride],
    };
    const invalid = nativeV2Fixture();
    invalid.floors[1].geometry.walls[0].end_vertex_id = 'missing-second-floor-vertex';
    expect(() => importVastuLayout(invalid)).toThrow(/floors\[1\].*end_vertex_id/);
    const after = useAppStore.getState();
    expect({
      floors: after.floors,
      activeFloorId: after.activeFloorId,
      floorData: after.floorData,
      vertices: after.vertices,
      sun: [after.sunTimeHours, after.sunAzimuthDeg, after.sunDirectionOverride],
    }).toEqual(snapshot);
  });
});


describe('native v2 canvas-backed floors', () => {
  const canvas = (label: string) => ({
    version: '1.0',
    metadata: { unit: 'cm', grid_spacing: 1, zoom_level: 1, unit_scale: 1, wall_height_cm: 280 },
    rooms: [{ id: `${label}-source`, name: label, x0: 100, y0: 100, x1: 200, y1: 200 }],
    furniture: [
      { image_name: 'double_bed', x: 150, y: 150, scale: 1, angle: 0 },
      { image_name: 'singlehand_door', x: 150, y: 100 },
    ],
    shapes: [],
    text: [
      { content: `${label} note`, x: 120, y: 120 },
      { content: `${label} canonical`, x: 130, y: 130, tags: ['canonical_v2_mirror'] },
    ],
    compass: { north_deg_clockwise: 25 },
  });

  const geometry = (prefix: string, label: string, withStructure = false) => ({
    ...emptyV2Geometry(),
    canvas: canvas(label),
    vertices: [
      { id: `${prefix}-v1`, position: [100, 100], source_canvas_id: `${label}-source` },
      { id: `${prefix}-v2`, position: [200, 100], source_canvas_id: `${label}-source` },
      { id: `${prefix}-v3`, position: [200, 200], source_canvas_id: `${label}-source` },
      { id: `${prefix}-v4`, position: [100, 200], source_canvas_id: `${label}-source` },
      { id: `${prefix}-explicit-v1`, position: [300, 100] },
      { id: `${prefix}-explicit-v2`, position: [400, 100] },
    ],
    walls: [
      ...[1, 2, 3, 4].map((number, index) => ({
        id: `${prefix}-source-wall-${number}`,
        start_vertex_id: `${prefix}-v${number}`,
        end_vertex_id: `${prefix}-v${number === 4 ? 1 : number + 1}`,
        thickness_cm: 20,
        height_cm: 280,
        material_id: 'paint-sage',
        opening_ids: [],
        source_canvas_id: `${label}-source`,
        source_index: index,
      })),
      {
        id: `${prefix}-explicit-wall`,
        start_vertex_id: `${prefix}-explicit-v1`,
        end_vertex_id: `${prefix}-explicit-v2`,
        thickness_cm: 15,
        height_cm: 260,
        material_id: 'paint-white',
        opening_ids: [],
      },
    ],
    rooms: [{
      id: `${prefix}-source-room`,
      boundary_vertex_ids: [`${prefix}-v1`, `${prefix}-v2`, `${prefix}-v3`, `${prefix}-v4`],
      label,
      room_type: 'bedroom',
      floor_material_id: 'floor-wood',
      source_canvas_id: `${label}-source`,
    }],
    text: [{
      id: `${prefix}-canonical-text`, position: [130, 130], text: `${label} canonical`,
      font_size_cm: 15, color: '#222222',
    }],
    pillars: withStructure ? [{
      id: `${prefix}-pillar`, position: [150, 150], width_cm: 20, depth_cm: 20,
      height_cm: 250, elevation_cm: 0, shape: 'rect', material_id: 'default-wall',
    }] : [],
  });

  const fixture = () => ({
    version: '2.0',
    metadata: { unit: 'cm', grid_spacing: 1, zoom_level: 1, unit_scale: 1, wall_height_cm: 280 },
    active_floor_id: 'floor-upper',
    floors: [
      { id: 'floor-ground', name: 'Ground Floor', elevation_cm: 0, geometry: geometry('g', 'Ground') },
      { id: 'floor-upper', name: 'Upper Floor', elevation_cm: 300, geometry: geometry('u', 'Upper', true) },
    ],
    sun_settings: { time_hours: 12, azimuth_deg: 180, direction_override: false },
    cross_floor_references: [{
      id: 'canvas-alignment', type: 'alignment',
      source_floor_id: 'floor-ground', source_entity_id: 'g-v1',
      target_floor_id: 'floor-upper', target_entity_id: 'u-v1',
    }],
  });

  it('uses canvas geometry once, keeps finish overlays and explicit v2 entities, and shifts all floors together', () => {
    const { project, report } = convertVastuLayout(fixture());
    const ground = project!.geometryByFloor['floor-ground'];
    const upper = project!.geometryByFloor['floor-upper'];

    expect(Object.keys(upper.walls)).toHaveLength(5); // four canvas walls + one explicit wall
    expect(Object.values(upper.walls).filter((wall) => wall.materialId === 'paint-sage')).toHaveLength(4);
    expect(Object.values(upper.rooms)[0].floorMaterialId).toBe('floor-wood');
    expect(upper.walls['u-explicit-wall']).toBeDefined();
    expect(upper.pillars['u-pillar']).toBeDefined();
    expect(Object.keys(upper.openings)).toHaveLength(1);
    expect(Object.keys(upper.furniture)).toHaveLength(1);
    expect(Object.values(upper.annotations).map((item) => item.text).sort()).toEqual(['Upper canonical', 'Upper note']);

    const groundCorner = Object.values(ground.vertices).find((vertex) => vertex.position.x === 0 && vertex.position.y === 100);
    const upperCorner = Object.values(upper.vertices).find((vertex) => vertex.position.x === 0 && vertex.position.y === 100);
    expect(groundCorner?.position).toEqual(upperCorner?.position);
    const alignment = project!.crossFloorReferences[0];
    expect(ground.vertices[alignment.sourceEntityId]).toBeDefined();
    expect(upper.vertices[alignment.targetEntityId]).toBeDefined();
    expect(report.rooms).toBe(2);
    expect(report.walls).toBe(10);
  });

  it('rejects a malformed nested v1 canvas with its floor path', () => {
    const malformed = fixture();
    malformed.floors[1].geometry.canvas.rooms = null as never;
    expect(() => convertVastuLayout(malformed)).toThrow(/floors\[1\]\.geometry\.canvas.*rooms.*array/);
  });
});