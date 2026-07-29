// src/domains/editor/components/PolygonPreview.tsx

import React from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';
import { EDITOR_STYLE } from '../constants';
import { shoelaceArea, polygonPerimeter } from '../services/geometry';
import { formatArea, formatLength } from '../services/units';

interface PolygonPreviewProps {
  /** Points placed so far (world cm). */
  points: Point2D[];
}

/**
 * Live preview for the free-form polygon room tool: the in-progress polyline (to the cursor),
 * a close-loop ring on the first point, and a live area/perimeter readout in the active unit.
 */
export const PolygonPreview: React.FC<PolygonPreviewProps> = ({ points }) => {
  const cursor = useAppStore((s) => s.currentMouseWorld);
  const unit = useAppStore((s) => s.displayUnit);
  if (points.length === 0) return null;

  const preview = cursor ? [...points, cursor] : points;
  const d = preview.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${-p.y}`).join(' ');

  // Live measurements once we have enough points to form an area.
  const closed = preview.length >= 3;
  const area = closed ? Math.abs(shoelaceArea(preview)) : 0;
  const perimeter = polygonPerimeter(preview) * (closed ? 1 : 1); // open path length is fine too

  // Centroid for the label.
  const cx = preview.reduce((s, p) => s + p.x, 0) / preview.length;
  const cy = preview.reduce((s, p) => s + p.y, 0) / preview.length;

  const first = points[0];
  const nearFirst =
    cursor && points.length >= 3 && (cursor.x - first.x) ** 2 + (cursor.y - first.y) ** 2 < 30 * 30;

  return (
    <g className="polygon-preview" pointerEvents="none">
      <path
        d={points.length >= 2 ? `${d} Z` : d}
        fill="rgba(52, 211, 153, 0.12)"
        stroke={EDITOR_STYLE.previewStroke}
        strokeWidth={EDITOR_STYLE.previewStrokeWidth}
        strokeDasharray={EDITOR_STYLE.previewDash}
      />
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={-p.y} r={EDITOR_STYLE.vertexRadius} fill={EDITOR_STYLE.previewStroke} />
      ))}
      {nearFirst && (
        <circle cx={first.x} cy={-first.y} r={EDITOR_STYLE.vertexRadius * 2.5} fill="none" stroke="#22d3ee" strokeWidth={2} />
      )}
      {closed && (
        <text
          x={cx}
          y={-cy}
          fill="#fff"
          fontSize={16}
          fontFamily="sans-serif"
          textAnchor="middle"
          stroke="black"
          strokeWidth="0.5px"
          paintOrder="stroke fill"
        >
          {`${formatArea(area, unit)}  |  ${formatLength(perimeter, unit)}`}
        </text>
      )}
    </g>
  );
};
