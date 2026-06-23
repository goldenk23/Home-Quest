// src/domains/editor/components/DrawingPreview.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { EDITOR_STYLE } from '../constants';
import type { Point2D } from '@/types/geometry';
import { findParallelGuide, toWallSegments } from '../services/wallGuides';

interface DrawingPreviewProps {
  /** The pending wall start point, or null when no wall is in progress. */
  start: Point2D | null;
  /** The first point of the current chain (for close-loop detection). */
  chainOrigin?: Point2D | null;
}

/**
 * The live "what you're about to draw" line. Renders nothing until a start point exists
 * and the cursor is inside the canvas. Remember the Y‑flip: world Y up → SVG draws at -y.
 */
export const DrawingPreview: React.FC<DrawingPreviewProps> = ({ start, chainOrigin }) => {
  const cursor = useAppStore((s) => s.currentMouseWorld);
  const walls = useAppStore((s) => s.walls);
  const vertices = useAppStore((s) => s.vertices);
  if (!start || !cursor) return null;

  const dx = cursor.x - start.x;
  const dy = cursor.y - start.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  
  let angleDeg = Math.atan2(dy, dx) * (180 / Math.PI);
  if (angleDeg < 0) angleDeg += 360;

  // Place text halfway along the line, offset slightly.
  const midX = (start.x + cursor.x) / 2;
  const midY = (start.y + cursor.y) / 2;

  // Compare the segment being drawn against the nearest PARALLEL existing wall, so the
  // user can match opposite sides of a rectangle/room exactly.
  const segments = toWallSegments(walls, vertices);
  const guide = findParallelGuide(start, cursor, segments);

  // Are we about to close the loop back onto the chain origin?
  const closing =
    chainOrigin != null &&
    (cursor.x - chainOrigin.x) ** 2 + (cursor.y - chainOrigin.y) ** 2 < 1 &&
    length > 1;

  return (
    <g className="drawing-preview" pointerEvents="none">
      {/* Equal-length guide: highlight the parallel wall and show its length + the delta. */}
      {guide && (
        <>
          <line
            x1={guide.start.x}
            y1={-guide.start.y}
            x2={guide.end.x}
            y2={-guide.end.y}
            stroke={guide.isEqual ? '#22d3ee' : '#a855f7'}
            strokeWidth={guide.isEqual ? 4 : 2}
            strokeDasharray="6 6"
            opacity={0.9}
          />
          <text
            x={(guide.start.x + guide.end.x) / 2}
            y={-(guide.start.y + guide.end.y) / 2 + 22}
            fill={guide.isEqual ? '#22d3ee' : '#d8b4fe'}
            fontSize="14"
            fontFamily="sans-serif"
            textAnchor="middle"
            stroke="black"
            strokeWidth="0.5px"
            paintOrder="stroke fill"
          >
            {`parallel: ${(guide.length / 100).toFixed(2)}m`}
          </text>
        </>
      )}

      {/* Close-loop indicator: a ring on the origin when the cursor will close the room. */}
      {closing && chainOrigin && (
        <circle
          cx={chainOrigin.x}
          cy={-chainOrigin.y}
          r={EDITOR_STYLE.vertexRadius * 2.5}
          fill="none"
          stroke="#22d3ee"
          strokeWidth={2}
        />
      )}

      <line
        x1={start.x}
        y1={-start.y}
        x2={cursor.x}
        y2={-cursor.y}
        stroke={EDITOR_STYLE.previewStroke}
        strokeWidth={EDITOR_STYLE.previewStrokeWidth}
        strokeDasharray={EDITOR_STYLE.previewDash}
      />
      <circle cx={start.x} cy={-start.y} r={EDITOR_STYLE.vertexRadius} fill={EDITOR_STYLE.previewStroke} />
      <circle cx={cursor.x} cy={-cursor.y} r={EDITOR_STYLE.vertexRadius} fill={EDITOR_STYLE.previewStroke} />
      
      {length > 0 && (
        <text 
          x={midX} 
          y={-midY - 15} 
          fill="white" 
          fontSize="16" 
          fontFamily="sans-serif"
          textAnchor="middle"
          stroke="black"
          strokeWidth="0.5px"
          paintOrder="stroke fill"
        >
          {`${(length / 100).toFixed(2)}m  |  ${Math.round(angleDeg)}°`}
          {guide ? (guide.isEqual ? '  ✓ equal' : `  Δ ${(guide.delta / 100).toFixed(2)}m`) : ''}
        </text>
      )}
    </g>
  );
};
