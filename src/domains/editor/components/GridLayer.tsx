// src/domains/editor/components/GridLayer.tsx

import React from 'react';

interface GridLayerProps {
  /** Grid cell size in world units (cm). */
  gridSize: number;
}

/**
 * Infinite‑looking dotted grid via a tiling <pattern>.
 * The big background <rect> is intentionally huge so the pattern fills the viewport
 * at any pan/zoom. pointerEvents="none" lets clicks pass through to the canvas.
 */
export const GridLayer: React.FC<GridLayerProps> = React.memo(({ gridSize }) => {
  const patternId = 'editor-grid-pattern';
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
    </>
  );
});

GridLayer.displayName = 'GridLayer';
