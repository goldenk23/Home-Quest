import React from 'react';
import { useAppStore } from '@/store';

export const RailingLayer: React.FC = React.memo(() => {
  const railings = useAppStore((s) => s.railings);
  const list = Object.values(railings);
  if (list.length === 0) return null;

  return (
    <g className="railing-layer">
      {list.map((railing) => (
        <line
          key={railing.id}
          x1={railing.start.x}
          y1={-railing.start.y}
          x2={railing.end.x}
          y2={-railing.end.y}
          stroke={railing.style === 'solid' ? '#78716c' : '#a8a29e'}
          strokeWidth={railing.style === 'solid' ? 4 : 2}
          strokeDasharray={railing.style === 'open' ? '5 5' : undefined}
          data-entity-id={railing.id}
          data-entity-type="railing"
        />
      ))}
    </g>
  );
});

RailingLayer.displayName = 'RailingLayer';
