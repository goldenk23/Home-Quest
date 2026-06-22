// src/domains/editor/components/RoomLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { ROOM_FILL_COLORS } from '../constants';
import { computeSignedArea } from '../services/roomDetection';
import type { Point2D } from '@/types/geometry';

/** Convert an ordered list of world points into a closed SVG polygon path (Y‑flipped). */
function polygonPath(points: Point2D[]): string {
  if (points.length === 0) return '';
  const [first, ...rest] = points;
  const move = `M ${first.x} ${-first.y}`;
  const lines = rest.map((p) => `L ${p.x} ${-p.y}`).join(' ');
  return `${move} ${lines} Z`;
}

/**
 * Renders each detected room as a tinted polygon with a centered label.
 * Rooms sit just above the grid and below the walls so wall edges stay sharp.
 */
export const RoomLayer: React.FC = React.memo(() => {
  const rooms = useAppStore((s) => s.rooms);
  const vertices = useAppStore((s) => s.vertices);

  return (
    <g className="room-layer">
      {Object.values(rooms).map((room) => {
        // Resolve boundary vertex IDs → positions; skip any room with missing vertices.
        const points = room.boundaryVertexIds
          .map((id) => vertices[id]?.position)
          .filter((p): p is Point2D => Boolean(p));
        if (points.length < 3) return null;

        // Label position = polygon centroid (simple average is fine for convex-ish rooms).
        const cx = points.reduce((sum, p) => sum + p.x, 0) / points.length;
        const cy = points.reduce((sum, p) => sum + p.y, 0) / points.length;

        // Area in m² (positions are in cm, so divide by 10,000).
        const areaM2 = Math.abs(computeSignedArea(points)) / 10000;

        return (
          <g key={room.id}>
            <path
              d={polygonPath(points)}
              fill={ROOM_FILL_COLORS[room.roomType]}
              stroke="rgba(255,255,255,0.08)"
              strokeWidth={1}
              data-entity-id={room.id}
              data-entity-type="room"
            />
            <text
              x={cx}
              y={-cy - 9}
              fontSize={16}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="rgba(255,255,255,0.8)"
              pointerEvents="none"
            >
              {room.label}
            </text>
            <text
              x={cx}
              y={-cy + 11}
              fontSize={12}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="rgba(255,255,255,0.55)"
              pointerEvents="none"
            >
              {areaM2.toFixed(2)} m²
            </text>
          </g>
        );
      })}
    </g>
  );
});

RoomLayer.displayName = 'RoomLayer';
