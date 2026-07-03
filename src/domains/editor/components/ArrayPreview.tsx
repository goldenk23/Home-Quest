import React from 'react';
import { useAppStore } from '@/store';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import type { ArrayPlacementItem } from '../services/arrayPlacement';

interface ArrayPreviewProps {
  items: ArrayPlacementItem[];
}

export const ArrayPreview: React.FC<ArrayPreviewProps> = React.memo(({ items }) => {
  const config = useAppStore((s) => s.arrayConfig);

  if (items.length === 0 || !config.entityType) return null;

  const furnitureEntry = config.entityType === 'furniture'
    ? getCatalogEntry(config.referenceId ?? useAppStore.getState().furnitureCatalogId)
    : null;

  const path = items.map((item, index) => `${index === 0 ? 'M' : 'L'} ${item.position.x} ${-item.position.y}`).join(' ');

  return (
    <g className="array-preview" pointerEvents="none">
      {items.length > 1 && (
        <path d={path} fill="none" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="10 8" opacity={0.9} />
      )}
      {items.map((item) => {
        if (config.entityType === 'pillar') {
          return (
            <g key={item.index}>
              <rect
                x={item.position.x - 17.5}
                y={-item.position.y - 17.5}
                width={35}
                height={35}
                fill="rgba(248,250,252,0.22)"
                stroke="#fbbf24"
                strokeWidth={2}
                strokeDasharray="6 4"
              />
              <ArrayNumber x={item.position.x} y={-item.position.y} index={item.index} />
            </g>
          );
        }

        const width = furnitureEntry?.bounds.width ?? 80;
        const depth = furnitureEntry?.bounds.depth ?? 80;
        const degrees = (-(Number.isFinite(config.angle) ? config.angle : 0) * 180) / Math.PI;
        return (
          <g key={item.index} transform={`translate(${item.position.x} ${-item.position.y}) rotate(${degrees})`}>
            <rect
              x={-width / 2}
              y={-depth / 2}
              width={width}
              height={depth}
              rx={3}
              fill="rgba(56,189,248,0.18)"
              stroke="#fbbf24"
              strokeWidth={2}
              strokeDasharray="6 4"
            />
            <line x1={0} y1={-depth / 2} x2={0} y2={-depth / 2 + Math.min(depth * 0.25, 15)} stroke="#fbbf24" strokeWidth={2} />
            <ArrayNumber x={0} y={0} index={item.index} />
          </g>
        );
      })}
    </g>
  );
});

ArrayPreview.displayName = 'ArrayPreview';

const ArrayNumber: React.FC<{ x: number; y: number; index: number }> = ({ x, y, index }) => (
  <text
    x={x}
    y={y}
    textAnchor="middle"
    dominantBaseline="middle"
    fontSize={13}
    fontWeight={700}
    fontFamily="sans-serif"
    fill="#fff7ed"
    stroke="#111827"
    strokeWidth={0.75}
    paintOrder="stroke"
  >
    {index + 1}
  </text>
);
