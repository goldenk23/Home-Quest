// src/domains/editor/components/DimensionLayer.tsx

import React from 'react';
import { useWallSegments } from '@/store/selectors/editorSelectors';

/**
 * Dimension annotations: draws each wall's real-world length as a label aligned with the
 * wall (like a CAD dimension), sitting just off the wall centerline. Lengths ≥ 1 m are
 * shown in metres, shorter ones in centimetres. Rendered inside the pan/zoom group, so it
 * tracks the geometry; pointerEvents are off so labels never block editing.
 */
export const DimensionLayer: React.FC = React.memo(() => {
  const walls = useWallSegments();

  return (
    <g className="dimension-layer" pointerEvents="none">
      {walls.map((w) => {
        const dx = w.end.x - w.start.x;
        const dy = w.end.y - w.start.y;
        const len = Math.hypot(dx, dy);
        if (len < 1) return null;

        // Midpoint in SVG space (world Y is flipped to -y on screen).
        const mx = (w.start.x + w.end.x) / 2;
        const my = -(w.start.y + w.end.y) / 2;

        // Angle of the wall on screen; keep text upright (never upside-down).
        let deg = (Math.atan2(-dy, dx) * 180) / Math.PI;
        if (deg > 90) deg -= 180;
        if (deg < -90) deg += 180;

        const label = len >= 100 ? `${(len / 100).toFixed(2)} m` : `${Math.round(len)} cm`;
        const offset = w.thickness / 2 + 8; // lift the label just clear of the wall fill

        return (
          <g key={w.id} transform={`translate(${mx} ${my}) rotate(${deg})`}>
            <text
              x={0}
              y={-offset}
              fill="#fde68a"
              stroke="#1c1917"
              strokeWidth={0.7}
              paintOrder="stroke"
              fontSize={14}
              fontWeight={600}
              fontFamily="sans-serif"
              textAnchor="middle"
            >
              {label}
            </text>
          </g>
        );
      })}
    </g>
  );
});

DimensionLayer.displayName = 'DimensionLayer';
