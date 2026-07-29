import { describe, it, expect } from 'vitest';
import { endpointFromLength } from '../geometry';

describe('endpointFromLength', () => {
  it('places a point at an exact distance along +X', () => {
    const p = endpointFromLength({ x: 0, y: 0 }, 350, 0);
    expect(p.x).toBeCloseTo(350, 6);
    expect(p.y).toBeCloseTo(0, 6);
    expect(Math.hypot(p.x, p.y)).toBeCloseTo(350, 6);
  });

  it('respects direction (90° = +Y, since world Y is up)', () => {
    const p = endpointFromLength({ x: 100, y: 100 }, 200, Math.PI / 2);
    expect(p.x).toBeCloseTo(100, 6);
    expect(p.y).toBeCloseTo(300, 6);
  });
});
