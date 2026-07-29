import { describe, it, expect } from 'vitest';
import { computeZoneGrid } from '../zoneGrid';
import type { Point2D } from '@/types/geometry';

// A 400x400 square centered on the origin.
const square: Point2D[] = [
  { x: -200, y: -200 },
  { x: 200, y: -200 },
  { x: 200, y: 200 },
  { x: -200, y: 200 },
];
const center: Point2D = { x: 0, y: 0 };

describe('computeZoneGrid', () => {
  it('produces one division line and one label per sector for each count', () => {
    for (const count of [8, 16, 32] as const) {
      const g = computeZoneGrid(square, center, count, 0, 'modern');
      expect(g.divisions).toHaveLength(count);
      expect(g.labels).toHaveLength(count);
    }
  });

  it('division endpoints land on the boundary (within the square extent)', () => {
    const g = computeZoneGrid(square, center, 8, 0, 'modern');
    for (const d of g.divisions) {
      expect(Math.abs(d.b.x)).toBeLessThanOrEqual(200.001);
      expect(Math.abs(d.b.y)).toBeLessThanOrEqual(200.001);
      expect(Math.hypot(d.b.x, d.b.y)).toBeGreaterThan(1); // not collapsed to center
    }
  });

  it('uses Vedic labels for 8 zones in vedic mode, compass otherwise', () => {
    const vedic = computeZoneGrid(square, center, 8, 0, 'vedic');
    expect(vedic.labels[0].text).toBe('Kubera'); // North
    const modern = computeZoneGrid(square, center, 8, 0, 'modern');
    expect(modern.labels[0].text).toBe('N');
  });
});
