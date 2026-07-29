import { describe, it, expect } from 'vitest';
import { computeAlignment } from '../alignmentGuides';

describe('computeAlignment', () => {
  const anchors = [
    { x: 100, y: 200 },
    { x: 500, y: 50 },
  ];

  it('snaps X and Y to the nearest anchor within tolerance', () => {
    const r = computeAlignment({ x: 104, y: 47 }, anchors, 8);
    expect(r.snapX).toBe(100); // within 8 of x=100
    expect(r.snapY).toBe(50); // within 8 of y=50
  });

  it('returns nothing when no anchor is within tolerance', () => {
    const r = computeAlignment({ x: 300, y: 300 }, anchors, 8);
    expect(r.snapX).toBeUndefined();
    expect(r.snapY).toBeUndefined();
  });
});
