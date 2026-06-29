// src/domains/editor/components/StairLayer.tsx
//
// SVG layer that draws all placed stair entities on the 2D editor canvas.
// Reads stairs from the store and renders the path outline, stairwell void,
// and step-count annotation for each staircase.
// NOTE: SVG Y-axis is flipped — all plan y coordinates are negated (-p.y).

import React from 'react';
import { useAppStore } from '@/store';
import type { StairEntity } from '@/types/stair';

function svgPt(p: { x: number; y: number }) {
  return `${p.x},${-p.y}`;
}

function polygonPoints(pts: { x: number; y: number }[]) {
  return pts.map(svgPt).join(' ');
}

function pathD(pts: { x: number; y: number }[]) {
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${-p.y}`).join(' ');
}

const StairEntitySVG: React.FC<{ stair: StairEntity; selected: boolean }> = ({ stair, selected }) => {
  const mid = stair.pathPoints.reduce(
    (acc, p) => ({ x: acc.x + p.x / stair.pathPoints.length, y: acc.y + p.y / stair.pathPoints.length }),
    { x: 0, y: 0 }
  );

  const totalSteps = stair.flights.reduce((n, f) => n + f.stepCount, 0);

  return (
    <g>
      {/* Stairwell void outline */}
      <polygon
        points={polygonPoints(stair.stairwellVoid)}
        fill={selected ? 'rgba(234,179,8,0.18)' : 'rgba(120,120,200,0.13)'}
        stroke={selected ? '#ca8a04' : '#6366f1'}
        strokeWidth={selected ? 2.5 : 1.5}
        strokeDasharray="6 3"
      />

      {/* Path centerline */}
      <path
        d={pathD(stair.pathPoints)}
        fill="none"
        stroke={selected ? '#ca8a04' : '#6366f1'}
        strokeWidth={selected ? 2 : 1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Step ticks on each flight */}
      {stair.flights.map((flight) => {
        const dx = flight.endPoint.x - flight.startPoint.x;
        const dy = flight.endPoint.y - flight.startPoint.y;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len;
        const uy = dy / len;
        const nx = -uy;
        const ny = ux;
        const halfW = stair.widthCm / 2;
        const ticks = Array.from({ length: flight.stepCount - 1 }, (_, k) => {
          const t = (k + 1) / flight.stepCount;
          const cx = flight.startPoint.x + t * dx;
          const cy = flight.startPoint.y + t * dy;
          return (
            <line
              key={k}
              x1={cx - nx * halfW}
              y1={-(cy - ny * halfW)}
              x2={cx + nx * halfW}
              y2={-(cy + ny * halfW)}
              stroke={selected ? '#ca8a04' : '#6366f1'}
              strokeWidth={0.8}
              opacity={0.6}
            />
          );
        });
        return <g key={flight.id}>{ticks}</g>;
      })}

      {/* Label */}
      <text
        x={mid.x}
        y={-mid.y}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={14}
        fill={selected ? '#ca8a04' : '#4f46e5'}
        fontWeight={600}
        pointerEvents="none"
        style={{ userSelect: 'none' }}
      >
        {totalSteps}↑ {stair.widthCm}cm
      </text>
    </g>
  );
};

/** Renders placed stair entities. Mount inside the zoom/pan `<g>` in EditorCanvas. */
export const StairLayer: React.FC = () => {
  const stairs = useAppStore((s) => s.stairs);
  const selectedIds = useAppStore((s) => s.selectedIds);

  return (
    <g>
      {Object.values(stairs).map((stair) => (
        <StairEntitySVG
          key={stair.id}
          stair={stair}
          selected={selectedIds.includes(stair.id)}
        />
      ))}
    </g>
  );
};
