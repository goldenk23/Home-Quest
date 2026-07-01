import React from 'react';
import { useAppStore } from '@/store';
import { computeWallQuad } from '../services/geometry';

function quadPath(q: ReturnType<typeof computeWallQuad>): string {
  return `M ${q.topLeft.x} ${-q.topLeft.y} L ${q.topRight.x} ${-q.topRight.y} L ${q.bottomRight.x} ${-q.bottomRight.y} L ${q.bottomLeft.x} ${-q.bottomLeft.y} Z`;
}

export const BeamLayer: React.FC = React.memo(() => {
  const beams = useAppStore((s) => s.beams);
  const list = Object.values(beams);
  if (list.length === 0) return null;
  return (
    <g className="beam-layer">
      {list.map((b) => (
        <path key={b.id} d={quadPath(computeWallQuad(b.start, b.end, b.width))} fill="rgba(148,163,184,0.55)" stroke="#475569" strokeWidth={2} />
      ))}
    </g>
  );
});

BeamLayer.displayName = 'BeamLayer';