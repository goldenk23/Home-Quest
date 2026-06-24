// src/domains/editor/components/RoadLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';
import type { Point2D } from '@/types/geometry';

/** Build an SVG path string for a quad, applying the world→SVG Y-flip (-y). */
function quadPath(tl: Point2D, tr: Point2D, br: Point2D, bl: Point2D): string {
  return `M ${tl.x} ${-tl.y} L ${tr.x} ${-tr.y} L ${br.x} ${-br.y} L ${bl.x} ${-bl.y} Z`;
}

/**
 * Renders every road as a filled grey paving strip computed from its centerline and width,
 * with a dashed centre line so it reads as a road/driveway. Roads sit BELOW walls and rooms
 * in the editor stack (they're exterior ground paving), so they're drawn first by the canvas.
 */
export const RoadLayer: React.FC = React.memo(() => {
  const roads = useAppStore(useShallow((s) => Object.values(s.roads)));
  if (roads.length === 0) return null;

  return (
    <g className="road-layer">
      {roads.map((road) => {
        const dx = road.end.x - road.start.x;
        const dy = road.end.y - road.start.y;
        const len = Math.hypot(dx, dy) || 1;
        // Unit normal to the centerline, scaled to half width.
        const nx = (-dy / len) * (road.width / 2);
        const ny = (dx / len) * (road.width / 2);
        const tl = { x: road.start.x + nx, y: road.start.y + ny };
        const tr = { x: road.end.x + nx, y: road.end.y + ny };
        const br = { x: road.end.x - nx, y: road.end.y - ny };
        const bl = { x: road.start.x - nx, y: road.start.y - ny };
        return (
          <g key={road.id} data-entity-id={road.id} data-entity-type="road">
            <path d={quadPath(tl, tr, br, bl)} fill="#6b7280" stroke="#4b5563" strokeWidth={2} />
            {/* dashed centre line */}
            <line
              x1={road.start.x}
              y1={-road.start.y}
              x2={road.end.x}
              y2={-road.end.y}
              stroke="#fbbf24"
              strokeWidth={Math.max(4, road.width * 0.04)}
              strokeDasharray={`${road.width * 0.25} ${road.width * 0.22}`}
              opacity={0.8}
            />
          </g>
        );
      })}
    </g>
  );
});

RoadLayer.displayName = 'RoadLayer';
