// src/domains/editor/components/OpeningsLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';

export const OpeningsLayer: React.FC = React.memo(() => {
  const openingsMap = useAppStore(s => s.openings);
  const openings = Object.values(openingsMap);
  const walls = useAppStore(s => s.walls);
  const vertices = useAppStore(s => s.vertices);

  return (
    <g className="openings-layer">
      {openings.map(opening => {
        const wall = walls[opening.wallId];
        if (!wall) return null;
        
        const start = vertices[wall.startVertexId]?.position;
        const end = vertices[wall.endVertexId]?.position;
        if (!start || !end) return null;

        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const length = Math.hypot(dx, dy);
        if (length === 0) return null;

        const vx = dx / length;
        const vy = dy / length;
        const nx = -vy;
        const ny = vx;

        // The center of the opening in 2D plan
        const cx = start.x + vx * opening.offsetCm;
        const cy = start.y + vy * opening.offsetCm;
        const halfW = opening.width / 2;
        const halfThick = wall.thickness / 2;

        const corners = [
          { x: cx - vx * halfW + nx * halfThick, y: cy - vy * halfW + ny * halfThick },
          { x: cx + vx * halfW + nx * halfThick, y: cy + vy * halfW + ny * halfThick },
          { x: cx + vx * halfW - nx * halfThick, y: cy + vy * halfW - ny * halfThick },
          { x: cx - vx * halfW - nx * halfThick, y: cy - vy * halfW - ny * halfThick },
        ];

        const path = `M ${corners[0].x} ${-corners[0].y} ` +
                     `L ${corners[1].x} ${-corners[1].y} ` +
                     `L ${corners[2].x} ${-corners[2].y} ` +
                     `L ${corners[3].x} ${-corners[3].y} Z`;

        let fill = '#fff';
        let stroke = '#000';
        let strokeDasharray = 'none';

        if (opening.type === 'door') {
          fill = '#fde047'; // yellow
          stroke = '#ca8a04';
        } else if (opening.type === 'window') {
          fill = '#93c5fd'; // blue
          stroke = '#2563eb';
        } else if (opening.type === 'vent') {
          fill = '#ccfbf1'; // cyan
          stroke = '#0d9488';
          strokeDasharray = '4 2';
        }

        return (
          <path
            key={opening.id}
            d={path}
            fill={fill}
            stroke={stroke}
            strokeWidth={2}
            strokeDasharray={strokeDasharray}
            onClick={(e) => {
              e.stopPropagation();
              // For simplicity, click to remove for now
              useAppStore.getState().removeOpening(opening.id);
            }}
            style={{ cursor: 'pointer' }}
          />
        );
      })}
    </g>
  );
});

OpeningsLayer.displayName = 'OpeningsLayer';
