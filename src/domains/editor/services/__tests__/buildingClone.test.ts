import { describe, it, expect } from 'vitest';
import { cloneGeometry, computeBuildingBounds, type BuildingGeometry } from '../buildingClone';

function emptyGeom(): BuildingGeometry {
  return { vertices: {}, walls: {}, rooms: {}, openings: {}, pillars: {}, beams: {}, deckSlabs: {}, railings: {}, furniture: {} };
}

function sampleGeom(): BuildingGeometry {
  const g = emptyGeom();
  g.vertices = {
    v1: { id: 'v1', position: { x: 0, y: 0 }, connectedWalls: ['w1'] },
    v2: { id: 'v2', position: { x: 100, y: 0 }, connectedWalls: ['w1'] },
  };
  g.walls = {
    w1: { id: 'w1', startVertexId: 'v1', endVertexId: 'v2', thickness: 10, height: 300, materialId: 'default-wall', isLoadBearing: true, openingIds: ['o1'] },
  };
  g.openings = {
    o1: { id: 'o1', wallId: 'w1', type: 'door', offsetCm: 50, width: 90, height: 210, elevation: 0 },
  };
  g.rooms = {
    r1: { id: 'r1', boundaryVertexIds: ['v1', 'v2'], roomType: 'living', label: 'Hall', floorMaterialId: 'default-floor' },
  };
  g.pillars = { p1: { id: 'p1', position: { x: 10, y: 10 }, width: 35, depth: 35, height: 300, elevationCm: 0, shape: 'rect', materialId: 'paint-white' } };
  return g;
}

describe('computeBuildingBounds', () => {
  it('returns null for an empty plan', () => {
    expect(computeBuildingBounds(emptyGeom())).toBeNull();
  });

  it('spans all vertices/pillars and centers correctly', () => {
    const b = computeBuildingBounds(sampleGeom())!;
    expect(b.min).toEqual({ x: 0, y: 0 });
    expect(b.max).toEqual({ x: 100, y: 10 });
    expect(b.center).toEqual({ x: 50, y: 5 });
  });
});

describe('cloneGeometry', () => {
  it('offsets positions and gives every entity a fresh id', () => {
    let n = 0;
    const gen = (p: string) => `${p}-clone-${n++}`;
    const clone = cloneGeometry(sampleGeom(), { x: 500, y: 0 }, gen);

    const v = Object.values(clone.vertices);
    expect(v).toHaveLength(2);
    expect(v.map((x) => x.position.x).sort((a, b) => a - b)).toEqual([500, 600]);
    // No original ids survive.
    expect(Object.keys(clone.vertices).every((id) => id.startsWith('vertex-clone'))).toBe(true);
  });

  it('remaps every cross-reference onto the new ids (self-consistent copy)', () => {
    let n = 0;
    const gen = (p: string) => `${p}-${n++}`;
    const clone = cloneGeometry(sampleGeom(), { x: 0, y: 0 }, gen);

    const wall = Object.values(clone.walls)[0];
    const vertexIds = new Set(Object.keys(clone.vertices));
    const openingIds = new Set(Object.keys(clone.openings));

    expect(vertexIds.has(wall.startVertexId)).toBe(true);
    expect(vertexIds.has(wall.endVertexId)).toBe(true);
    expect(wall.openingIds.every((o) => openingIds.has(o))).toBe(true);

    // The cloned opening points back at the cloned wall.
    const opening = Object.values(clone.openings)[0];
    expect(opening.wallId).toBe(wall.id);

    // The cloned room's boundary vertices are all cloned vertices.
    const room = Object.values(clone.rooms)[0];
    expect(room.boundaryVertexIds.every((id) => vertexIds.has(id))).toBe(true);
  });
});
