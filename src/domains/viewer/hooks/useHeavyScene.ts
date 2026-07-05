// src/domains/viewer/hooks/useHeavyScene.ts

import { useAppStore } from '@/store';

/**
 * Above this many renderable entities (all storeys combined) the scene is treated as
 * "heavy" and expensive rendering features are degraded automatically. A normal house is
 * well under 200 entities; the Hall-1 campus is several thousand.
 */
const HEAVY_ENTITY_THRESHOLD = 600;

type EntityRecords = {
  walls?: Record<string, unknown>;
  openings?: Record<string, unknown>;
  pillars?: Record<string, unknown>;
  beams?: Record<string, unknown>;
  deckSlabs?: Record<string, unknown>;
  railings?: Record<string, unknown>;
  furniture?: Record<string, unknown>;
};

function countEntities(g: EntityRecords): number {
  return (
    Object.keys(g.walls ?? {}).length +
    Object.keys(g.openings ?? {}).length +
    Object.keys(g.pillars ?? {}).length +
    Object.keys(g.beams ?? {}).length +
    Object.keys(g.deckSlabs ?? {}).length +
    Object.keys(g.railings ?? {}).length +
    Object.keys(g.furniture ?? {}).length
  );
}

/**
 * True when the plan (active floor + all parked floors) is large enough that real-time
 * shadows and full-resolution rendering would tank the framerate. Consumers use this to
 * auto-degrade: shadows off, pixel ratio capped. Selector returns a primitive, so
 * subscribers only re-render when the boolean actually flips.
 */
export function useHeavyScene(): boolean {
  return useAppStore((s) => {
    let n = countEntities(s);
    for (const floorId in s.floorData) {
      n += countEntities(s.floorData[floorId] as EntityRecords);
      if (n > HEAVY_ENTITY_THRESHOLD) return true;
    }
    return n > HEAVY_ENTITY_THRESHOLD;
  });
}
