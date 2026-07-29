// src/domains/editor/components/FurnitureLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { useCollidingFurnitureIds } from '../hooks/useCollisions';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import { SYMBOL2D_PATH } from '@/domains/shared/assets/pythonAssetMap';

/**
 * Draws a 2D footprint icon for every furniture item.
 * The SVG transform does three things in order: move to the item's position
 * (Y‑flipped), rotate, then we draw the rect centered on the origin.
 * Rotation is negated because screen Y is flipped relative to world Y, so a
 * counter‑clockwise world rotation is clockwise on screen.
 *
 * Items involved in a collision are drawn red so the collision engine is visible.
 */
export const FurnitureLayer: React.FC = React.memo(() => {
  const furniture = useAppStore((s) => s.furniture);
  const colliding = useCollidingFurnitureIds();

  return (
    <g className="furniture-layer">
      {Object.values(furniture).map((item) => {
        const w = item.bounds.width;
        const d = item.bounds.depth;
        const degrees = (-item.rotation * 180) / Math.PI;
        const isColliding = colliding.has(item.id);
        const stroke = isColliding ? '#ef4444' : '#38bdf8';
        const fill = isColliding ? 'rgba(239, 68, 68, 0.22)' : 'rgba(56, 189, 248, 0.20)';
        const label = getCatalogEntry(item.catalogId).label;
        const symbol = SYMBOL2D_PATH[item.catalogId];
        return (
          <g
            key={item.id}
            transform={`translate(${item.position.x} ${-item.position.y}) rotate(${degrees})`}
            data-entity-id={item.id}
            data-entity-type="furniture"
          >
            {symbol ? (
              <>
                {/* Real architectural top-view symbol, stretched to the footprint. */}
                <image
                  href={symbol}
                  x={-w / 2}
                  y={-d / 2}
                  width={w}
                  height={d}
                  preserveAspectRatio="none"
                  opacity={isColliding ? 0.5 : 1}
                />
                {/* Faint bounds so selection/collision stays visible over the symbol. */}
                <rect
                  x={-w / 2}
                  y={-d / 2}
                  width={w}
                  height={d}
                  rx={3}
                  fill={isColliding ? 'rgba(239, 68, 68, 0.22)' : 'none'}
                  stroke={stroke}
                  strokeWidth={isColliding ? 1.5 : 0.75}
                  strokeOpacity={isColliding ? 1 : 0.5}
                />
              </>
            ) : (
              <>
                <rect
                  x={-w / 2}
                  y={-d / 2}
                  width={w}
                  height={d}
                  rx={3}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={1.5}
                />
                {/* Small tick marks the "front" of the piece so orientation is visible. */}
                <line x1={0} y1={-d / 2} x2={0} y2={-d / 2 + Math.min(d * 0.25, 15)} stroke={stroke} strokeWidth={2} />
                <text
                  x={0}
                  y={0}
                  fontSize={Math.max(10, Math.min(w, d) * 0.18)}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={isColliding ? '#fecaca' : '#e0f2fe'}
                  pointerEvents="none"
                  transform={`rotate(${-degrees})`}
                >
                  {label}
                </text>
              </>
            )}
          </g>
        );
      })}
    </g>
  );
});

FurnitureLayer.displayName = 'FurnitureLayer';
