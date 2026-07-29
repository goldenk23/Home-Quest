import { describe, it, expect } from 'vitest';
import { shoelaceArea, polygonPerimeter } from '../geometry';

describe('shoelaceArea', () => {
  it('computes the area of a 200x300 rectangle (cm²)', () => {
    const rect = [
      { x: 0, y: 0 },
      { x: 200, y: 0 },
      { x: 200, y: 300 },
      { x: 0, y: 300 },
    ];
    expect(Math.abs(shoelaceArea(rect))).toBeCloseTo(60000, 6);
  });

  it('returns 0 for fewer than 3 points', () => {
    expect(shoelaceArea([{ x: 0, y: 0 }, { x: 1, y: 1 }])).toBe(0);
  });
});

describe('polygonPerimeter', () => {
  it('computes the perimeter of a 200x300 rectangle', () => {
    const rect = [
      { x: 0, y: 0 },
      { x: 200, y: 0 },
      { x: 200, y: 300 },
      { x: 0, y: 300 },
    ];
    expect(polygonPerimeter(rect)).toBeCloseTo(1000, 6);
  });
});
