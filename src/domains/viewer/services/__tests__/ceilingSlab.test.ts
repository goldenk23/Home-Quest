import { describe, it, expect } from 'vitest';
import { ceilingSlabRange } from '../transform';

describe('ceilingSlabRange', () => {
  it('fills the inter-storey gap flush: default 280cm walls, 300cm storey', () => {
    const { baseCm, thicknessCm } = ceilingSlabRange(280, 300);
    expect(baseCm).toBe(280);
    expect(thicknessCm).toBe(20);
    // The slab top must land exactly on the floor above — this is the bug being fixed.
    expect(baseCm + thicknessCm).toBe(300);
  });

  it('keeps the top flush no matter the wall height', () => {
    for (const wallTop of [0, 150, 280, 295, 320]) {
      const { baseCm, thicknessCm } = ceilingSlabRange(wallTop, 300);
      expect(baseCm + thicknessCm).toBeCloseTo(300);
      expect(thicknessCm).toBeGreaterThanOrEqual(8); // never degenerate
    }
  });
});
