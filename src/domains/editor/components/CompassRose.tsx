// src/domains/editor/components/CompassRose.tsx

import React from 'react';

/**
 * A fixed, screen-anchored compass rose for the 2D editor.
 *
 * Convention used across the app (see zones.ts):
 *   - North = +Y (world), East = +X, angles increase counter-clockwise.
 *   - SVG Y is flipped, so on screen North points UP, East points RIGHT,
 *     South DOWN and West LEFT, exactly like a real map.
 *
 * It is rendered OUTSIDE the pan/zoom <g>, so it always stays in the same
 * corner and at a constant size regardless of how the user pans or zooms.
 */
export const CompassRose: React.FC<{ size?: number; margin?: number }> = ({ size = 88, margin = 16 }) => {
  const r = size / 2;
  const cx = margin + r;
  const cy = margin + r;
  const tip = r - 10; // length of the direction needles

  // Cardinal label positions (screen space: up = North).
  const labels: { dir: string; dx: number; dy: number; color: string }[] = [
    { dir: 'N', dx: 0, dy: -(r - 4), color: '#dc2626' },
    { dir: 'E', dx: r - 4, dy: 0, color: '#334155' },
    { dir: 'S', dx: 0, dy: r - 4, color: '#334155' },
    { dir: 'W', dx: -(r - 4), dy: 0, color: '#334155' },
  ];

  return (
    <g pointerEvents="none" aria-label="Compass: North is up" data-export-exclude="true">
      {/* Dial background */}
      <circle cx={cx} cy={cy} r={r} fill="rgba(15,23,42,0.78)" stroke="#94a3b8" strokeWidth={1.5} />
      <circle cx={cx} cy={cy} r={r - 6} fill="none" stroke="rgba(148,163,184,0.35)" strokeWidth={1} />

      {/* Diagonal ticks (NE, SE, SW, NW) */}
      {[45, 135, 225, 315].map((deg) => {
        const a = (deg * Math.PI) / 180;
        return (
          <line
            key={deg}
            x1={cx + Math.sin(a) * (r - 10)}
            y1={cy - Math.cos(a) * (r - 10)}
            x2={cx + Math.sin(a) * (r - 6)}
            y2={cy - Math.cos(a) * (r - 6)}
            stroke="rgba(226,232,240,0.6)"
            strokeWidth={1}
          />
        );
      })}

      {/* North needle (red) */}
      <polygon
        points={`${cx},${cy - tip} ${cx - 6},${cy} ${cx + 6},${cy}`}
        fill="#dc2626"
      />
      {/* South needle (light) */}
      <polygon
        points={`${cx},${cy + tip} ${cx - 6},${cy} ${cx + 6},${cy}`}
        fill="#e2e8f0"
      />
      <circle cx={cx} cy={cy} r={3} fill="#f8fafc" />

      {/* Cardinal labels */}
      {labels.map((l) => (
        <text
          key={l.dir}
          x={cx + l.dx}
          y={cy + l.dy}
          fill={l.color}
          fontSize={13}
          fontWeight={700}
          fontFamily="sans-serif"
          textAnchor="middle"
          dominantBaseline="central"
        >
          {l.dir}
        </text>
      ))}
    </g>
  );
};
