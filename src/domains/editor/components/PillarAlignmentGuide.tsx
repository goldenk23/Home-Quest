// src/domains/editor/components/PillarAlignmentGuide.tsx

import React from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';
import { findPillarAlignmentGuide } from '../services/pillarGuides';

interface Props {
  /** Where the next pillar will be placed (usually the live cursor position). */
  cursor: Point2D | null;
}

/**
 * While the Pillar tool is active, draws dashed row/column guide lines from the cursor to
 * any existing pillar it lines up with, plus the spacing (cm) to that pillar. This is the
 * only feedback the user had for lining up a rectangular grid of pillars — without it, a
 * second/third/fourth pillar had to be placed by eye against the first.
 */
export const PillarAlignmentGuide: React.FC<Props> = ({ cursor }) => {
  const pillars = useAppStore((s) => s.pillars);
  if (!cursor) return null;

  const list = Object.values(pillars);
  if (list.length === 0) return null;

  const guide = findPillarAlignmentGuide(cursor, list);
  if (!guide.columnMatch && !guide.rowMatch) return null;

  return (
    <g className="pillar-alignment-guide" pointerEvents="none">
      {/* Column guide: vertical dashed line — the new pillar shares this one's X. */}
      {guide.columnMatch && (
        <>
          <line
            x1={guide.columnMatch.position.x}
            y1={-guide.columnMatch.position.y}
            x2={cursor.x}
            y2={-cursor.y}
            stroke="#22d3ee"
            strokeWidth={2}
            strokeDasharray="6 6"
            opacity={0.9}
          />
          <text
            x={cursor.x + 12}
            y={-(cursor.y + guide.columnMatch.position.y) / 2}
            fill="#22d3ee"
            fontSize="14"
            fontFamily="sans-serif"
            stroke="black"
            strokeWidth="0.5px"
            paintOrder="stroke fill"
          >
            {`↕ aligned · ${(guide.columnMatch.spacing / 100).toFixed(2)}m`}
          </text>
        </>
      )}

      {/* Row guide: horizontal dashed line — the new pillar shares this one's Y. */}
      {guide.rowMatch && (
        <>
          <line
            x1={guide.rowMatch.position.x}
            y1={-guide.rowMatch.position.y}
            x2={cursor.x}
            y2={-cursor.y}
            stroke="#a855f7"
            strokeWidth={2}
            strokeDasharray="6 6"
            opacity={0.9}
          />
          <text
            x={(cursor.x + guide.rowMatch.position.x) / 2}
            y={-cursor.y - 12}
            fill="#a855f7"
            fontSize="14"
            fontFamily="sans-serif"
            textAnchor="middle"
            stroke="black"
            strokeWidth="0.5px"
            paintOrder="stroke fill"
          >
            {`↔ aligned · ${(guide.rowMatch.spacing / 100).toFixed(2)}m`}
          </text>
        </>
      )}
    </g>
  );
};
