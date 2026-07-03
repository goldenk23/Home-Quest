// src/domains/editor/components/PillarSnapIndicator.tsx

import React from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';

interface Props {
  activeTool: 'beam' | 'deck';
  currentPoint: Point2D | null;
  snapRadius?: number;
}

export const PillarSnapIndicator: React.FC<Props> = ({ 
  currentPoint, 
  snapRadius = 50 
}) => {
  const pillars = useAppStore((s) => s.pillars);
  
  if (!currentPoint) return null;
  
  const snapCandidates = Object.values(pillars).filter((pillar) => {
    const dx = currentPoint.x - pillar.position.x;
    const dy = currentPoint.y - pillar.position.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const pillarSnapRadius = Math.max(pillar.width, pillar.depth) / 2 + snapRadius;
    return distance <= pillarSnapRadius;
  });
  
  if (snapCandidates.length === 0) return null;
  
  return (
    <g className="pillar-snap-indicator" pointerEvents="none">
      {snapCandidates.map((pillar) => (
        <g key={pillar.id}>
          {/* Highlight snap candidate pillar */}
          <circle
            cx={pillar.position.x}
            cy={-pillar.position.y}
            r={Math.max(pillar.width, pillar.depth) / 2}
            fill="none"
            stroke="#22c55e"
            strokeWidth={3}
            opacity={0.6}
          />
          {/* Snap connection indicator */}
          <line
            x1={currentPoint.x}
            y1={-currentPoint.y}
            x2={pillar.position.x}
            y2={-pillar.position.y}
            stroke="#22c55e"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            opacity={0.5}
          />
        </g>
      ))}
    </g>
  );
};
