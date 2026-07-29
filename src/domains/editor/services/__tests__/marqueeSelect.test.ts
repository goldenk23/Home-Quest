import { describe, it, expect } from 'vitest';
import { normalizeRect, pointInRect, collectEntitiesInRect, type MarqueeGeometry } from '../marqueeSelect';

describe('normalizeRect / pointInRect', () => {
  it('normalizes corners regardless of order', () => {
    const r = normalizeRect({ x: 300, y: 50 }, { x: 100, y: 200 });
    expect(r).toEqual({ minX: 100, maxX: 300, minY: 50, maxY: 200 });
    expect(pointInRect({ x: 150, y: 100 }, r)).toBe(true);
    expect(pointInRect({ x: 400, y: 100 }, r)).toBe(false);
  });
});

describe('collectEntitiesInRect', () => {
  const g: MarqueeGeometry = {
    vertices: {
      v1: { id: 'v1', position: { x: 0, y: 0 }, connectedWalls: [] } as any,
      v2: { id: 'v2', position: { x: 100, y: 0 }, connectedWalls: [] } as any,
      v4: { id: 'v4', position: { x: 800, y: 800 }, connectedWalls: [] } as any,
      v5: { id: 'v5', position: { x: 900, y: 900 }, connectedWalls: [] } as any,
    },
    walls: {
      w1: { id: 'w1', startVertexId: 'v1', endVertexId: 'v2' } as any, // both endpoints inside
      w2: { id: 'w2', startVertexId: 'v4', endVertexId: 'v5' } as any, // fully outside
    },
    furniture: {
      f1: { id: 'f1', position: { x: 50, y: 50 } } as any, // inside
      f2: { id: 'f2', position: { x: 800, y: 800 } } as any, // outside
    },
    pillars: {},
    beams: {},
    roads: {},
    deckSlabs: {},
    railings: {},
  };

  it('collects only entities inside the rect', () => {
    const ids = collectEntitiesInRect(g, { minX: -10, minY: -10, maxX: 200, maxY: 200 });
    expect(ids.sort()).toEqual(['f1', 'w1']);
  });
});
