// Self-check for the stairwell geometry helpers that connect floors: the footprint must land
// where the flight actually is, containment must gate which room slab/floor gets cut, and a
// hole must survive the shape builder. If any of these break, stairwells stop punching through.
import { describe, it, expect } from 'vitest';
import { stairFootprint, pointInPolygon, shapeWithHoles } from '../transform';

describe('stairFootprint', () => {
  it('axis-aligned (no rotation): spans ±half extents around the centre', () => {
    const fp = stairFootprint(100, 200, 0, 50, 180);
    const xs = fp.map((p) => p.x);
    const ys = fp.map((p) => p.y);
    expect(Math.min(...xs)).toBeCloseTo(50);
    expect(Math.max(...xs)).toBeCloseTo(150);
    expect(Math.min(...ys)).toBeCloseTo(20);
    expect(Math.max(...ys)).toBeCloseTo(380);
  });

  it('quarter turn swaps width/depth onto the other axis', () => {
    const fp = stairFootprint(0, 0, Math.PI / 2, 50, 180);
    const xs = fp.map((p) => p.x);
    const ys = fp.map((p) => p.y);
    // width (50) now runs along Y, depth (180) along X.
    expect(Math.max(...xs) - Math.min(...xs)).toBeCloseTo(360);
    expect(Math.max(...ys) - Math.min(...ys)).toBeCloseTo(100);
  });
});

describe('pointInPolygon', () => {
  const room = [
    { x: 0, y: 0 },
    { x: 400, y: 0 },
    { x: 400, y: 600 },
    { x: 0, y: 600 },
  ];
  it('accepts a footprint fully inside and rejects one poking outside', () => {
    const inside = stairFootprint(200, 300, 0, 55, 180);
    expect(inside.every((c) => pointInPolygon(c, room))).toBe(true);
    const straddling = stairFootprint(380, 300, 0, 55, 180); // hangs past the right wall
    expect(straddling.every((c) => pointInPolygon(c, room))).toBe(false);
  });
});

describe('shapeWithHoles', () => {
  it('subtracts a contained hole from the slab shape', () => {
    const room = [
      { x: 0, y: 0 },
      { x: 400, y: 0 },
      { x: 400, y: 600 },
      { x: 0, y: 600 },
    ];
    const well = stairFootprint(200, 300, 0, 55, 180);
    const shape = shapeWithHoles(room, [well]);
    expect(shape.holes).toHaveLength(1);
    // The hole points should be the well, scaled cm→m (the builder converts units).
    expect(shape.holes[0].getPoints().length).toBeGreaterThanOrEqual(4);
  });
});
