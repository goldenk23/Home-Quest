import { describe, it, expect } from 'vitest';
import { snapDeckCornerOutward, extendBeamEndsToPillars } from '../structuralJoints';

describe('snapDeckCornerOutward', () => {
  const rect = { shape: 'rect' as const, width: 40, depth: 40 };

  it('pushes a rect-post corner out to the post outer corner (top-right quadrant)', () => {
    // centroid at origin, corner up-right of it → push +x/+y by half footprint.
    const out = snapDeckCornerOutward({ x: 100, y: 100 }, { x: 0, y: 0 }, rect);
    expect(out).toEqual({ x: 120, y: 120 });
  });

  it('pushes toward the correct quadrant when the corner is down-left of centroid', () => {
    const out = snapDeckCornerOutward({ x: -100, y: -100 }, { x: 0, y: 0 }, rect);
    expect(out).toEqual({ x: -120, y: -120 });
  });

  it('round post reaches its radius along the outward direction', () => {
    const round = { shape: 'round' as const, width: 60, depth: 60 };
    const out = snapDeckCornerOutward({ x: 100, y: 0 }, { x: 0, y: 0 }, round);
    expect(out.x).toBeCloseTo(130); // 100 + radius 30
    expect(out.y).toBeCloseTo(0);
  });
});

describe('extendBeamEndsToPillars', () => {
  const rect = { shape: 'rect' as const, width: 30, depth: 30 };

  it('extends both ends outward along the beam axis by the pillar half-extent', () => {
    // Horizontal beam from (0,0) to (400,0); both ends on 30cm posts.
    const [s, e] = extendBeamEndsToPillars({ x: 0, y: 0 }, { x: 400, y: 0 }, rect, rect);
    expect(s).toEqual({ x: -15, y: 0 }); // start pushed back by 15
    expect(e).toEqual({ x: 415, y: 0 }); // end pushed forward by 15
  });

  it('leaves an end unchanged when it has no pillar', () => {
    const [s, e] = extendBeamEndsToPillars({ x: 0, y: 0 }, { x: 400, y: 0 }, null, rect);
    expect(s).toEqual({ x: 0, y: 0 });
    expect(e).toEqual({ x: 415, y: 0 });
  });

  it('degenerate zero-length beam is returned as-is', () => {
    const [s, e] = extendBeamEndsToPillars({ x: 5, y: 5 }, { x: 5, y: 5 }, rect, rect);
    expect(s).toEqual({ x: 5, y: 5 });
    expect(e).toEqual({ x: 5, y: 5 });
  });
});
