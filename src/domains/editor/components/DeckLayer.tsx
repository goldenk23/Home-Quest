import React from 'react';
import { useAppStore } from '@/store';

function polygonPath(points: { x: number; y: number }[]): string {
  if (points.length === 0) return '';
  const [first, ...rest] = points;
  return [`M ${first.x} ${-first.y}`, ...rest.map((p) => `L ${p.x} ${-p.y}`), 'Z'].join(' ');
}

export const DeckLayer: React.FC = React.memo(() => {
  const deckSlabs = useAppStore((s) => s.deckSlabs);
  const list = Object.values(deckSlabs);
  if (list.length === 0) return null;

  return (
    <g className="deck-layer">
      {list.map((slab) => (
        <path
          key={slab.id}
          d={polygonPath(slab.polygon)}
          fill="rgba(14,165,233,0.22)"
          stroke="#0284c7"
          strokeWidth={2}
          strokeDasharray={slab.type === 'roof' ? '10 6' : undefined}
          data-entity-id={slab.id}
          data-entity-type="deck-slab"
        />
      ))}
    </g>
  );
});

DeckLayer.displayName = 'DeckLayer';