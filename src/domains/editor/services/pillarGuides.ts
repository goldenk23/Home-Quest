// src/domains/editor/services/pillarGuides.ts
//
// Pure geometry helper that powers pillar-placement alignment guides: while the user is
// about to drop a pillar (cursor position), find existing pillars that the new one would
// line up with — sharing the same X (a "column") or the same Y (a "row") — plus the
// row/column spacing to the nearest neighbour along that axis, so a rectangular grid of
// pillars (e.g. a 4-post deck frame) can be placed exactly parallel/aligned without any
// external measuring. Mirrors the wall `findParallelGuide` pattern: pure, no THREE/React.

import type { Point2D } from '@/types/geometry';

export interface PillarLike {
  id: string;
  position: Point2D;
}

export interface AxisAlignment {
  /** The existing pillar the cursor aligns with along this axis. */
  pillarId: string;
  /** That pillar's position. */
  position: Point2D;
  /** Distance (cm) from the aligned pillar to the cursor along the perpendicular axis. */
  spacing: number;
}

export interface PillarAlignmentGuide {
  /** Existing pillars sharing (approximately) the cursor's X — a vertical "column" line. */
  columnMatch: AxisAlignment | null;
  /** Existing pillars sharing (approximately) the cursor's Y — a horizontal "row" line. */
  rowMatch: AxisAlignment | null;
}

/**
 * Finds the nearest existing pillar aligned with `cursor` on each axis, within
 * `tolerance` cm. Reports the spacing along the OTHER axis so the user can match an
 * existing rectangular grid (e.g. "same row, 300cm to the right").
 */
export function findPillarAlignmentGuide(
  cursor: Point2D,
  pillars: readonly PillarLike[],
  tolerance = 15
): PillarAlignmentGuide {
  let columnMatch: AxisAlignment | null = null;
  let columnBestDist = Infinity;
  let rowMatch: AxisAlignment | null = null;
  let rowBestDist = Infinity;

  for (const p of pillars) {
    const dx = Math.abs(p.position.x - cursor.x);
    const dy = Math.abs(p.position.y - cursor.y);

    // Same X (column): pick the closest one by vertical distance.
    if (dx <= tolerance && dy < columnBestDist) {
      columnBestDist = dy;
      columnMatch = { pillarId: p.id, position: p.position, spacing: dy };
    }

    // Same Y (row): pick the closest one by horizontal distance.
    if (dy <= tolerance && dx < rowBestDist) {
      rowBestDist = dx;
      rowMatch = { pillarId: p.id, position: p.position, spacing: dx };
    }
  }

  return { columnMatch, rowMatch };
}
