import { describe, it, expect } from 'vitest';
import {
  WALL_FINISHES,
  FLOOR_FINISHES,
  getFinishById,
  categoryOf,
  getFinishSwatch,
  isDefaultFinish,
} from '../finishPalette';

describe('finish palette', () => {
  it('every finish has a unique id within its category', () => {
    const wallIds = new Set(WALL_FINISHES.map((f) => f.id));
    const floorIds = new Set(FLOOR_FINISHES.map((f) => f.id));
    expect(wallIds.size).toBe(WALL_FINISHES.length);
    expect(floorIds.size).toBe(FLOOR_FINISHES.length);
    // No id is shared across categories either.
    for (const id of wallIds) expect(floorIds.has(id)).toBe(false);
  });

  it('wall finishes are all category "wall", floor finishes all "floor"', () => {
    expect(WALL_FINISHES.every((f) => f.category === 'wall')).toBe(true);
    expect(FLOOR_FINISHES.every((f) => f.category === 'floor')).toBe(true);
  });

  it('getFinishById resolves registered ids and returns null for unknown', () => {
    expect(getFinishById('paint-white')?.name).toBe('White');
    expect(getFinishById('floor-wood')?.category).toBe('floor');
    expect(getFinishById('does-not-exist')).toBeNull();
  });

  it('categoryOf reports the category or null', () => {
    expect(categoryOf('paint-sage')).toBe('wall');
    expect(categoryOf('floor-marble')).toBe('floor');
    expect(categoryOf('unknown')).toBeNull();
  });

  it('getFinishSwatch returns the swatch, falling back for unknown ids', () => {
    expect(getFinishSwatch('paint-navy', '#fff')).toBe('#1e3a5f');
    // Unknown id → fallback (so a layer never goes transparent on a legacy id).
    expect(getFinishSwatch('legacy-id', '#abc')).toBe('#abc');
    expect(getFinishSwatch(undefined, '#def')).toBe('#def');
  });

  it('isDefaultFinish flags legacy/default ids', () => {
    expect(isDefaultFinish('default-wall')).toBe(true);
    expect(isDefaultFinish('default-floor')).toBe(true);
    expect(isDefaultFinish(undefined)).toBe(true);
    expect(isDefaultFinish('')).toBe(true);
    expect(isDefaultFinish('paint-white')).toBe(false);
    expect(isDefaultFinish('floor-wood')).toBe(false);
  });

  it('floor finishes with a texture declare a positive physical tile size', () => {
    for (const f of FLOOR_FINISHES) {
      if (f.texture) {
        expect(f.repeatMeters, `${f.id} should set repeatMeters`).toBeGreaterThan(0);
      }
    }
  });
});
