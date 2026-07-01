import React from 'react';
import { useAppStore } from '@/store';

export const PillarLayer: React.FC = React.memo(() => {
  const pillars = useAppStore((s) => s.pillars);
  const list = Object.values(pillars);
  if (list.length === 0) return null;

  return (
    <g className="pillar-layer">
      {list.map((p) => {
        const fill = '#f8fafc';
        const stroke = '#64748b';
        if (p.shape === 'round') {
          return (
            <circle
              key={p.id}
              cx={p.position.x}
              cy={-p.position.y}
              r={Math.max(p.width, p.depth) / 2}
              fill={fill}
              stroke={stroke}
              strokeWidth={2}
              data-entity-id={p.id}
              data-entity-type="pillar"
            />
          );
        }
        return (
          <rect
            key={p.id}
            x={p.position.x - p.width / 2}
            y={-p.position.y - p.depth / 2}
            width={p.width}
            height={p.depth}
            fill={fill}
            stroke={stroke}
            strokeWidth={2}
            data-entity-id={p.id}
            data-entity-type="pillar"
          />
        );
      })}
    </g>
  );
});

PillarLayer.displayName = 'PillarLayer';