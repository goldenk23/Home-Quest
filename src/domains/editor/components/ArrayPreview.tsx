import React from 'react';
import { useAppStore } from '@/store';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import type { ArrayPlacementItem } from '../services/arrayPlacement';
import { computeBuildingBounds, type BuildingGeometry } from '../services/buildingClone';

interface ArrayPreviewProps {
  items: ArrayPlacementItem[];
}

export const ArrayPreview: React.FC<ArrayPreviewProps> = React.memo(({ items }) => {
  const config = useAppStore((s) => s.arrayConfig);
  const store = useAppStore.getState();

  if (items.length === 0 || !config.entityType) return null;

  const furnitureEntry = config.entityType === 'furniture'
    ? getCatalogEntry(config.referenceId ?? store.furnitureCatalogId)
    : null;

  const path = items.map((item, index) => `${index === 0 ? 'M' : 'L'} ${item.position.x} ${-item.position.y}`).join(' ');

  // Spacing/alignment guide: label the gap between consecutive copies + the total span, so
  // the user can see the exact rhythm of the array (and, for buildings, the plot pitch).
  const spacingLabels = items.slice(1).map((item, i) => {
    const prev = items[i];
    const mx = (prev.position.x + item.position.x) / 2;
    const my = (prev.position.y + item.position.y) / 2;
    return { key: item.index, x: mx, y: my, text: `${(config.spacing / 100).toFixed(2)}m` };
  });

  // Building mode: draw the actual footprint bounding box at every copy position, centered
  // on the copy's origin (which is the building's own center), so the preview reads as real
  // duplicated buildings rather than dots.
  if (config.entityType === 'building') {
    const g: BuildingGeometry = {
      vertices: store.vertices, walls: store.walls, rooms: store.rooms, openings: store.openings,
      pillars: store.pillars, beams: store.beams, deckSlabs: store.deckSlabs,
      railings: store.railings, furniture: store.furniture,
    };
    const bounds = computeBuildingBounds(g);
    if (!bounds) return null;
    const w = bounds.max.x - bounds.min.x;
    const h = bounds.max.y - bounds.min.y;
    return (
      <g className="array-preview" pointerEvents="none">
        {items.length > 1 && (
          <path d={path} fill="none" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="10 8" opacity={0.9} />
        )}
        {items.map((item, idx) => (
          <g key={item.index}>
            <rect
              x={item.position.x - w / 2}
              y={-item.position.y - h / 2}
              width={w}
              height={h}
              fill={idx === 0 ? 'rgba(148,163,184,0.10)' : 'rgba(16,185,129,0.14)'}
              stroke={idx === 0 ? '#94a3b8' : '#10b981'}
              strokeWidth={2}
              strokeDasharray={idx === 0 ? '4 6' : '10 6'}
            />
            <ArrayNumber x={item.position.x} y={-item.position.y} index={item.index} />
          </g>
        ))}
        {spacingLabels.map((s) => (
          <SpacingLabel key={s.key} x={s.x} y={-s.y} text={s.text} />
        ))}
      </g>
    );
  }

  return (
    <g className="array-preview" pointerEvents="none">
      {items.length > 1 && (
        <path d={path} fill="none" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="10 8" opacity={0.9} />
      )}
      {spacingLabels.map((s) => (
        <SpacingLabel key={`sp-${s.key}`} x={s.x} y={-s.y} text={s.text} />
      ))}
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

const SpacingLabel: React.FC<{ x: number; y: number; text: string }> = ({ x, y, text }) => (
  <text
    x={x}
    y={y - 8}
    textAnchor="middle"
    fontSize={12}
    fontWeight={600}
    fontFamily="sans-serif"
    fill="#fbbf24"
    stroke="#111827"
    strokeWidth={0.75}
    paintOrder="stroke"
  >
    {text}
  </text>
);

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
