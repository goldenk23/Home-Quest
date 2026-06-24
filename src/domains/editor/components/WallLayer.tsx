// src/domains/editor/components/WallLayer.tsx

import React from 'react';
import { useWallSegments } from '@/store/selectors/editorSelectors';
import { useAppStore } from '@/store';
import { computeWallQuad } from '../services/geometry';
import { computeOpeningGeometry } from '../services/openingGeometry';
import { getFinishSwatch } from '@/domains/shared/materials/finishPalette';
import { EDITOR_STYLE } from '../constants';
import type { Point2D } from '@/types/geometry';

/** Build an SVG path string for a quad, applying the world→SVG Y‑flip (-y). */
function quadPath(tl: Point2D, tr: Point2D, br: Point2D, bl: Point2D): string {
  return (
    `M ${tl.x} ${-tl.y} ` +
    `L ${tr.x} ${-tr.y} ` +
    `L ${br.x} ${-br.y} ` +
    `L ${bl.x} ${-bl.y} Z`
  );
}

const DOOR_MASK_ID = 'wall-door-gap-mask';

/**
 * Renders every wall as a filled rectangle (quad) computed from its centerline and
 * thickness. Walls are filled — not stroked lines — so corners and thickness read
 * correctly at any zoom.
 *
 * Doors punch an actual GAP in the wall (architectural convention): we build an SVG mask
 * whose white background shows the whole wall, with a black rectangle over each door
 * footprint that hides the wall there. Because the wall layer sits above the grid/rooms,
 * the gap reveals the floor beneath — the doorway reads as empty, and the door swing
 * (quarter circle) is drawn on top by the OpeningsLayer.
 */
export const WallLayer: React.FC = React.memo(() => {
  const walls = useWallSegments();
  const wallMap = useAppStore((s) => s.walls);
  const vertices = useAppStore((s) => s.vertices);
  const openings = useAppStore((s) => s.openings);

  // Build a black "gap" rectangle for every door so the mask erases the wall there.
  const doorGaps: string[] = [];
  for (const opening of Object.values(openings)) {
    if (opening.type !== 'door') continue;
    const wall = wallMap[opening.wallId];
    if (!wall) continue;
    const start = vertices[wall.startVertexId]?.position;
    const end = vertices[wall.endVertexId]?.position;
    if (!start || !end) continue;
    const geo = computeOpeningGeometry(opening, start, end, wall.thickness);
    if (!geo) continue;

    // Extend a little past the wall faces so no thin slivers of wall remain in the gap.
    const m = geo.halfThick + 2;
    const { j1, j2, n } = geo;
    const c0 = { x: j1.x + n.x * m, y: j1.y + n.y * m };
    const c1 = { x: j2.x + n.x * m, y: j2.y + n.y * m };
    const c2 = { x: j2.x - n.x * m, y: j2.y - n.y * m };
    const c3 = { x: j1.x - n.x * m, y: j1.y - n.y * m };
    doorGaps.push(quadPath(c0, c1, c2, c3));
  }

  const hasGaps = doorGaps.length > 0;

  return (
    <g className="wall-layer">
      {hasGaps && (
        <defs>
          <mask id={DOOR_MASK_ID} maskUnits="userSpaceOnUse" x={-100000} y={-100000} width={200000} height={200000}>
            {/* White = wall visible everywhere by default. */}
            <rect x={-100000} y={-100000} width={200000} height={200000} fill="white" />
            {/* Black = wall hidden (the doorway gap). */}
            {doorGaps.map((d, i) => (
              <path key={i} d={d} fill="black" />
            ))}
          </mask>
        </defs>
      )}
      <g mask={hasGaps ? `url(#${DOOR_MASK_ID})` : undefined}>
        {walls.map((wall) => {
          const quad = computeWallQuad(wall.start, wall.end, wall.thickness, wall.offsets);
          const w = wallMap[wall.id];
          // Room-aware paint: a wall has two faces. Side A is the −normal (bottom) half,
          // side B the +normal (top) half. We split the quad along its centreline and fill
          // each half with that face's finish (falling back to the base material), so paint
          // applied from inside one room only colours the face toward that room.
          const fillBase = getFinishSwatch(w?.materialId, EDITOR_STYLE.wallFill);
          const fillA = getFinishSwatch(w?.materialSideA ?? w?.materialId, EDITOR_STYLE.wallFill);
          const fillB = getFinishSwatch(w?.materialSideB ?? w?.materialId, EDITOR_STYLE.wallFill);

          const { topLeft, topRight, bottomRight, bottomLeft } = quad;
          const startMid = { x: (topLeft.x + bottomLeft.x) / 2, y: (topLeft.y + bottomLeft.y) / 2 };
          const endMid = { x: (topRight.x + bottomRight.x) / 2, y: (topRight.y + bottomRight.y) / 2 };

          // When neither face is painted individually, draw a single quad (unchanged look).
          const split = Boolean(w?.materialSideA || w?.materialSideB);

          if (!split) {
            return (
              <path
                key={wall.id}
                d={quadPath(topLeft, topRight, bottomRight, bottomLeft)}
                fill={fillBase}
                stroke={EDITOR_STYLE.wallStroke}
                strokeWidth={EDITOR_STYLE.wallStrokeWidth}
                data-entity-id={wall.id}
                data-entity-type="wall"
              />
            );
          }

          return (
            <g key={wall.id} data-entity-id={wall.id} data-entity-type="wall">
              {/* Side B (top / +normal half) */}
              <path d={quadPath(topLeft, topRight, endMid, startMid)} fill={fillB} stroke="none" />
              {/* Side A (bottom / −normal half) */}
              <path d={quadPath(startMid, endMid, bottomRight, bottomLeft)} fill={fillA} stroke="none" />
              {/* Outline on top so the wall edge stays crisp. */}
              <path
                d={quadPath(topLeft, topRight, bottomRight, bottomLeft)}
                fill="none"
                stroke={EDITOR_STYLE.wallStroke}
                strokeWidth={EDITOR_STYLE.wallStrokeWidth}
              />
            </g>
          );
        })}
      </g>
    </g>
  );
});

WallLayer.displayName = 'WallLayer';
