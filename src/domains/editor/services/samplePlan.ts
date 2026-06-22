// src/domains/editor/services/samplePlan.ts

import { useAppStore } from '@/store';

/**
 * Loads a two-room starter house so every downstream feature (room detection, areas,
 * 3D walls/floors, Vastu boundary/score, overlays) is immediately visible and testable.
 *
 * Two quads share a central divider wall:
 *   ┌───────┬───────┐
 *   │ left  │ right │
 *   └───────┴───────┘
 * Vertices are deduplicated by the store's addWall, so the shared edge connects cleanly.
 */
export function loadSampleHouse(): void {
  const { clearAll, addWall } = useAppStore.getState();
  clearAll();

  // Left room (4m × 6m)
  addWall({ x: -400, y: -300 }, { x: 0, y: -300 });
  addWall({ x: 0, y: -300 }, { x: 0, y: 300 }); // shared divider
  addWall({ x: 0, y: 300 }, { x: -400, y: 300 });
  addWall({ x: -400, y: 300 }, { x: -400, y: -300 });

  // Right room (divider already exists, so it is reused via vertex dedup)
  addWall({ x: 0, y: -300 }, { x: 400, y: -300 });
  addWall({ x: 400, y: -300 }, { x: 400, y: 300 });
  addWall({ x: 400, y: 300 }, { x: 0, y: 300 });
}
