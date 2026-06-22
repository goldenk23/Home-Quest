// src/domains/editor/components/DrawingPreview.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { EDITOR_STYLE } from '../constants';
import type { Point2D } from '@/types/geometry';

interface DrawingPreviewProps {
  /** The pending wall start point, or null when no wall is in progress. */
  start: Point2D | null;
}

/**
 * The live "what you're about to draw" line. Renders nothing until a start point exists
 * and the cursor is inside the canvas. Remember the Y‑flip: world Y up → SVG draws at -y.
 */
export const DrawingPreview: React.FC<DrawingPreviewProps> = ({ start }) => {
  const cursor = useAppStore((s) => s.currentMouseWorld);
  if (!start || !cursor) return null;

  const dx = cursor.x - start.x;
  const dy = cursor.y - start.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  
  let angleDeg = Math.atan2(dy, dx) * (180 / Math.PI);
  if (angleDeg < 0) angleDeg += 360;

  // Place text halfway along the line, offset slightly.
  const midX = (start.x + cursor.x) / 2;
  const midY = (start.y + cursor.y) / 2;

  return (
    <g className="drawing-preview" pointerEvents="none">
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
        </text>
      )}
    </g>
  );
};
