import { describe, it, expect } from 'vitest';
import { stairRampHeightAt } from '../transform';

// Stair centred at origin, axis-aligned (rotation 0), 1m half-width, 2m half-depth (4m run),
// rising 3m (one storey) from base 0. Ascends along +Z.
const S = { cx: 0, cz: 0, rot: 0, halfW: 1, halfD: 2, base: 0, rise: 3 };
const ramp = (x: number, z: number, rot = S.rot) =>
  stairRampHeightAt(x, z, S.cx, S.cz, rot, S.halfW, S.halfD, S.base, S.rise);

describe('stairRampHeightAt', () => {
  it('maps bottom→top of the run to base→base+rise', () => {
    expect(ramp(0, -2)).toBeCloseTo(0); // bottom step (-Z)
    expect(ramp(0, 0)).toBeCloseTo(1.5); // midpoint
    expect(ramp(0, 2)).toBeCloseTo(3); // top tread lands on the floor above
  });

  it('returns null outside the footprint', () => {
    expect(ramp(2, 0)).toBeNull(); // past the width
    expect(ramp(0, 3)).toBeNull(); // past the run
  });

  it('honours rotation: a 90° turn puts the ascent along world +X', () => {
    // rotation +90°: local +Z maps to world +X, so progress now follows x, not z.
    const h = stairRampHeightAt(2, 0, 0, 0, Math.PI / 2, S.halfW, S.halfD, 0, 3);
    expect(h).toBeCloseTo(3); // x=+2 is the top after the turn
    // ...and the across-axis (now z) is bounded by halfW.
    expect(stairRampHeightAt(0, 2, 0, 0, Math.PI / 2, S.halfW, S.halfD, 0, 3)).toBeNull();
  });
});
