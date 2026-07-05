import React from 'react';
import { useAppStore } from '@/store';
import type { ArrayPlacementItem } from '../services/arrayPlacement';
import { computeBuildingBounds, type BuildingGeometry } from '../services/buildingClone';
import { computeComponentBounds, type ComponentCloneGeometry } from '../services/componentClone';

interface ArrayPreviewProps {
  items: ArrayPlacementItem[];
}

export const ArrayPreview: React.FC<ArrayPreviewProps> = React.memo(({ items }) => {
  const config = useAppStore((s) => s.arrayConfig);
  const store = useAppStore.getState();

  if (items.length === 0 || !config.entityType) return null;

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

  // Pillar/furniture mode: draw the picked source's real footprint at every replica
  // position (all items are replicas following the cursor).
  const componentId = config.referenceId;
  if (!componentId) return null;
  const g: ComponentCloneGeometry = {
    vertices: store.vertices, walls: store.walls, openings: store.openings,
    pillars: store.pillars, beams: store.beams, deckSlabs: store.deckSlabs,
    railings: store.railings, furniture: store.furniture, roads: store.roads,
  };
  const bounds = computeComponentBounds(componentId, g);
  if (!bounds) return null;
  const w = bounds.max.x - bounds.min.x;
  const h = bounds.max.y - bounds.min.y;
  return (
    <g className="array-preview" pointerEvents="none">
      {items.length > 1 && (
        <path d={path} fill="none" stroke="#8b5cf6" strokeWidth={1.5} strokeDasharray="10 8" opacity={0.9} />
      )}
      {items.map((item) => (
        <g key={item.index}>
          <rect
            x={item.position.x - w / 2}
            y={-item.position.y - h / 2}
            width={w}
            height={h}
            fill="rgba(139,92,246,0.14)"
            stroke="#8b5cf6"
            strokeWidth={2}
            strokeDasharray="10 6"
          />
          <ArrayNumber x={item.position.x} y={-item.position.y} index={item.index} />
        </g>
      ))}
      {spacingLabels.map((s) => (
        <SpacingLabel key={`comp-${s.key}`} x={s.x} y={-s.y} text={s.text} />
      ))}
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
