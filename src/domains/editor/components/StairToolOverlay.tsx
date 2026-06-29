// src/domains/editor/components/StairToolOverlay.tsx
//
// SVG overlay for the Stair tool's in-progress drawing. Shows the confirmed
// path points, the live ghost segment to the cursor, and a preview of the
// stairwell void width perpendicular to the path.
// NOTE: SVG Y-axis is flipped — all plan y coordinates are negated (-p.y).

import React from 'react';
import type { StairToolState } from '../hooks/useStairTool';
import type { Point2D } from '@/types/geometry';
import { pathStrokePolygon } from '../services/stairBuilder';

interface Props {
  toolState: StairToolState;
  stairWidthCm: number;
}

/** Convert an array of plan-cm points to an SVG polygon points string (Y-flipped). */
function polygonPoints(pts: Point2D[]) {
  return pts.map((p) => `${p.x},${-p.y}`).join(' ');
}

/** Build an SVG path string for an ordered list of plan-cm points (Y-flipped). */
function svgPath(pts: Point2D[]) {
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${-p.y}`).join(' ');
}

export const StairToolOverlay: React.FC<Props> = ({ toolState, stairWidthCm }) => {
  const { pathPoints, ghostPoint, error } = toolState;
  if (pathPoints.length === 0 && !ghostPoint) return null;

  // Full preview path (confirmed + ghost).
  const previewPath = ghostPoint ? [...pathPoints, ghostPoint] : pathPoints;

  // Build void preview polygon if we have at least 2 points.
  const voidPolygon = previewPath.length >= 2
    ? pathStrokePolygon(previewPath, stairWidthCm / 2)
    : null;

  // Determine staircase type and instruction text based on confirmed point count.
  const count = pathPoints.length;
  const type =
    count === 0 ? '' :
    count === 1 ? 'Straight staircase' :
    count === 2 ? 'L-shaped staircase' :
    count === 3 ? 'U-shaped staircase' :
    'Multi-turn staircase';

  const instruction =
    count === 0 ? 'Click to place the bottom of the staircase' :
    count === 1 ? 'Click to set direction  •  Double-click or Enter to finish' :
    count === 2 ? 'Click for second turn  •  Double-click or Enter to finish' :
    'Double-click or Enter to finish';

  const first = pathPoints[0];

  return (
    // pointerEvents="none" on the whole overlay so none of the preview geometry (polygon,
    // path, circles) can intercept clicks. Without this, the second click of a double-click
    // can land on the newly-appeared preview polygon instead of the SVG background, and the
    // browser won't fire the dblclick event because the two clicks are on different elements.
    <g pointerEvents="none">
      {/* Stairwell void preview */}
      {voidPolygon && (
        <polygon
          points={polygonPoints(voidPolygon)}
          fill="rgba(99,102,241,0.12)"
          stroke="#6366f1"
          strokeWidth={1.5}
          strokeDasharray="6 3"
        />
      )}

      {/* Centerline (confirmed + ghost dashed) */}
      <path
        d={svgPath(previewPath)}
        fill="none"
        stroke="#6366f1"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={ghostPoint ? '8 4' : undefined}
      />

      {/* Confirmed point markers */}
      {pathPoints.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={-p.y}
          r={5}
          fill={i === 0 ? '#10b981' : '#6366f1'}
          stroke="#fff"
          strokeWidth={1.5}
        />
      ))}

      {/* Ghost point marker */}
      {ghostPoint && (
        <circle
          cx={ghostPoint.x}
          cy={-ghostPoint.y}
          r={4}
          fill="none"
          stroke="#6366f1"
          strokeWidth={1.5}
          opacity={0.7}
        />
      )}

      {/* Length labels on confirmed segments */}
      {pathPoints.length > 1 &&
        pathPoints.slice(0, -1).map((p, i) => {
          const q = pathPoints[i + 1];
          const mx = (p.x + q.x) / 2;
          const my = (p.y + q.y) / 2;
          const len = Math.hypot(q.x - p.x, q.y - p.y).toFixed(0);
          return (
            <text
              key={i}
              x={mx}
              y={-my - 8}
              textAnchor="middle"
              fontSize={11}
              fill="#4f46e5"
              fontWeight={600}
              pointerEvents="none"
            >
              {len} cm
            </text>
          );
        })}

      {/* Instruction overlay — anchored near the first confirmed point */}
      {first && (
        <g>
          <foreignObject
            x={first.x + 24}
            y={-first.y - 110}
            width={480}
            height={110}
            pointerEvents="none"
          >
            <div
              style={{
                background: 'rgba(67, 56, 202, 0.97)',
                color: '#fff',
                padding: '12px 18px',
                borderRadius: '10px',
                fontSize: '15px',
                fontWeight: 600,
                boxShadow: '0 6px 20px rgba(0,0,0,0.25)',
                border: '2px solid rgba(255,255,255,0.35)',
                whiteSpace: 'nowrap',
              }}
            >
              {type && (
                <div style={{ marginBottom: '6px', fontSize: '12px', opacity: 0.85, textTransform: 'uppercase', letterSpacing: '0.7px', fontWeight: 700 }}>
                  {type}
                </div>
              )}
              <div style={{ fontSize: '15px', lineHeight: 1.4 }}>{instruction}</div>
              {error && (
                <div style={{ marginTop: '8px', fontSize: '13px', color: '#fca5a5', fontWeight: 600 }}>
                  ⚠️ {error}
                </div>
              )}
            </div>
          </foreignObject>

          {/* Point counter badge */}
          <circle cx={first.x} cy={-first.y} r={17} fill="#4338ca" stroke="#fff" strokeWidth={2.5} />
          <text
            x={first.x}
            y={-first.y}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={14}
            fill="#fff"
            fontWeight={700}
            pointerEvents="none"
          >
            {pathPoints.length}
          </text>
        </g>
      )}
    </g>
  );
};
