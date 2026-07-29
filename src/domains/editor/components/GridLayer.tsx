// src/domains/editor/components/GridLayer.tsx

import React from 'react';
import { formatLength, CM_PER_UNIT, type DisplayUnit } from '../services/units';

/** Visible world rectangle (cm). Used to cull major grid lines/labels to the viewport. */
export interface WorldBounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

interface GridLayerProps {
  /** Grid cell size in world units (cm) for the fine dotted grid. */
  gridSize: number;
  /** Active display unit for the major labels. */
  unit?: DisplayUnit;
  /** Visible world bounds; when provided, labeled major lines are drawn (culled to view). */
  bounds?: WorldBounds | null;
  /** Current zoom scale (px per cm) so label text keeps a constant on-screen size. */
  scale?: number;
}

/** Major-line spacing (cm) per unit: 1 m for metric, 1 ft for imperial. */
function majorStepCm(unit: DisplayUnit): number {
  return unit === 'ft' || unit === 'in' ? CM_PER_UNIT.ft : CM_PER_UNIT.m;
}

/** ponytail: cap on major lines per axis; a huge zoom-out just stops adding labels. */
const MAX_MAJOR_LINES = 200;

/**
 * Infinite-looking dotted grid via a tiling <pattern>, plus (when `bounds` is given) a set of
 * labeled major grid lines like the Python editor's `draw_grid`. Major lines are culled to the
 * visible world rect and memoized on quantized bounds to avoid re-render thrash while panning.
 * Rendered inside the zoom/pan <g>, so text is scaled by `1/scale` to stay a constant px size.
 */
export const GridLayer: React.FC<GridLayerProps> = React.memo(
  ({ gridSize, unit, bounds, scale = 1 }) => {
    const patternId = 'editor-grid-pattern';

    const major = React.useMemo(() => {
      if (!unit || !bounds) return null;
      const step = majorStepCm(unit);
      const startX = Math.floor(bounds.minX / step) * step;
      const startY = Math.floor(bounds.minY / step) * step;
      if ((bounds.maxX - startX) / step > MAX_MAJOR_LINES) return null;
      if ((bounds.maxY - startY) / step > MAX_MAJOR_LINES) return null;

      const xs: number[] = [];
      for (let x = startX; x <= bounds.maxX; x += step) xs.push(x);
      const ys: number[] = [];
      for (let y = startY; y <= bounds.maxY; y += step) ys.push(y);
      return { xs, ys };
    }, [unit, bounds, scale]);

    const fontSize = 12 / scale;
    const labelPad = 4 / scale;

    return (
      <>
        <defs>
          <pattern id={patternId} width={gridSize} height={gridSize} patternUnits="userSpaceOnUse">
            <circle cx={0} cy={0} r={0.5} fill="rgba(255,255,255,0.15)" />
          </pattern>
        </defs>
        <rect
          x={-50000}
          y={-50000}
          width={100000}
          height={100000}
          fill={`url(#${patternId})`}
          pointerEvents="none"
        />

        {major && bounds && unit && (
          <g className="grid-major" pointerEvents="none">
            {/* Vertical lines at constant worldX (SVG y = -worldY). */}
            {major.xs.map((x) => (
              <line
                key={`vx${x}`}
                x1={x}
                y1={-bounds.minY}
                x2={x}
                y2={-bounds.maxY}
                stroke="rgba(255,255,255,0.08)"
                strokeWidth={1 / scale}
              />
            ))}
            {/* Horizontal lines at constant worldY. */}
            {major.ys.map((y) => (
              <line
                key={`hy${y}`}
                x1={bounds.minX}
                y1={-y}
                x2={bounds.maxX}
                y2={-y}
                stroke="rgba(255,255,255,0.08)"
                strokeWidth={1 / scale}
              />
            ))}
            {/* X-axis labels along the top of the view. */}
            {major.xs.map((x) => (
              <text
                key={`lx${x}`}
                x={x + labelPad}
                y={-bounds.maxY + fontSize + labelPad}
                fill="rgba(255,255,255,0.45)"
                fontSize={fontSize}
                fontFamily="sans-serif"
              >
                {formatLength(x, unit, 0)}
              </text>
            ))}
            {/* Y-axis labels along the left of the view (skip the axis origin to reduce clutter). */}
            {major.ys.map((y) =>
              y === 0 ? null : (
                <text
                  key={`ly${y}`}
                  x={bounds.minX + labelPad}
                  y={-y - labelPad}
                  fill="rgba(255,255,255,0.45)"
                  fontSize={fontSize}
                  fontFamily="sans-serif"
                >
                  {formatLength(y, unit, 0)}
                </text>
              )
            )}
          </g>
        )}
      </>
    );
  }
);

GridLayer.displayName = 'GridLayer';
