// src/domains/editor/components/WallLayer.tsx

import React from 'react';
import { useWallSegments } from '@/store/selectors/editorSelectors';
import { computeWallQuad } from '../services/geometry';
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

/**
 * Renders every wall as a filled rectangle (quad) computed from its centerline and
 * thickness. Walls are filled — not stroked lines — so corners and thickness read
 * correctly at any zoom.
 */
export const WallLayer: React.FC = React.memo(() => {
  const walls = useWallSegments();

  return (
    <g className="wall-layer">
      {walls.map((wall) => {
        const quad = computeWallQuad(wall.start, wall.end, wall.thickness, wall.offsets);
        return (
          <path
            key={wall.id}
            d={quadPath(quad.topLeft, quad.topRight, quad.bottomRight, quad.bottomLeft)}
            fill={EDITOR_STYLE.wallFill}
            stroke={EDITOR_STYLE.wallStroke}
            strokeWidth={EDITOR_STYLE.wallStrokeWidth}
            // data-id lets selection / hit‑testing identify the wall later.
            data-entity-id={wall.id}
            data-entity-type="wall"
          />
        );
      })}
    </g>
  );
});

WallLayer.displayName = 'WallLayer';
