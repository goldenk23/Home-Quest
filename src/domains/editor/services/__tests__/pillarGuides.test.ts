import { describe, it, expect } from 'vitest';
import { findPillarAlignmentGuide } from '../pillarGuides';

describe('findPillarAlignmentGuide', () => {
  const pillars = [
    { id: 'a', position: { x: 0, y: 0 } },
    { id: 'b', position: { x: 400, y: 0 } },
  ];

  it('detects a row match and reports spacing to the NEAREST aligned pillar', () => {
    const guide = findPillarAlignmentGuide({ x: 700, y: 3 }, pillars);
    expect(guide.rowMatch?.pillarId).toBe('b'); // b (x=400) is nearer than a (x=0)
    expect(guide.rowMatch?.spacing).toBe(300);
  });

  it('detects a column match (same X as pillar a) and reports vertical spacing', () => {
    const guide = findPillarAlignmentGuide({ x: 3, y: 300 }, pillars);
    expect(guide.columnMatch?.pillarId).toBe('a');
    expect(guide.columnMatch?.spacing).toBe(300);
  });

  it('returns nulls when nothing aligns within tolerance', () => {
    const guide = findPillarAlignmentGuide({ x: 200, y: 200 }, pillars);
    expect(guide.rowMatch).toBeNull();
    expect(guide.columnMatch).toBeNull();
  });
});
