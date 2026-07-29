// src/domains/editor/components/RoomLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { ROOM_FILL_COLORS } from '../constants';
import { computeSignedArea } from '../services/roomDetection';
import { getFinishSwatch, isDefaultFinish, getFinishById } from '@/domains/shared/materials/finishPalette';
import type { Point2D } from '@/types/geometry';

/** cm size of one flooring-texture tile in the 2D plan. ponytail: fixed tile, not per-finish. */
const FLOOR_TILE_CM = 150;

/**
 * Fill for a room in the 2D editor. A painted room (one whose `floorMaterialId` is a
 * registered finish) shows its finish swatch at ~0.55 alpha so the chosen tile reads at a
 * glance while labels/walls stay legible. Unpainted rooms keep their room-type tint.
 * The hex is converted to an rgba string via the hexToRgba helper below.
 */
function roomFill(floorMaterialId: string, roomType: keyof typeof ROOM_FILL_COLORS): string {
  if (isDefaultFinish(floorMaterialId)) {
    return ROOM_FILL_COLORS[roomType];
  }
  // Real flooring image (wood/marble/tile/grass) → fill via a tiling <pattern>.
  if (getFinishById(floorMaterialId)?.imageTexture) {
    return `url(#floor-tex-${floorMaterialId})`;
  }
  const hex = getFinishSwatch(floorMaterialId, '#d4c5a9');
  return hexToRgba(hex, 0.55);
}

/** #rrggbb → rgba(r,g,b,a). Falls back to the input on anything it can't parse. */
function hexToRgba(hex: string, alpha: number): string {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

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
  const selectedIds = useAppStore((s) => s.selectedIds);

  // Distinct flooring-image materials in use → one <pattern> each (defined once).
  const texturedMaterials = React.useMemo(() => {
    const ids = new Set<string>();
    for (const room of Object.values(rooms)) {
      if (getFinishById(room.floorMaterialId)?.imageTexture) ids.add(room.floorMaterialId);
    }
    return [...ids];
  }, [rooms]);

  return (
    <g className="room-layer">
      <defs>
        {texturedMaterials.map((id) => {
          const src = getFinishById(id)?.imageTexture;
          if (!src) return null;
          return (
            <pattern
              key={id}
              id={`floor-tex-${id}`}
              width={FLOOR_TILE_CM}
              height={FLOOR_TILE_CM}
              patternUnits="userSpaceOnUse"
            >
              <image href={src} x={0} y={0} width={FLOOR_TILE_CM} height={FLOOR_TILE_CM} preserveAspectRatio="xMidYMid slice" />
              {/* Slight dark wash so labels/walls stay legible over busy textures. */}
              <rect x={0} y={0} width={FLOOR_TILE_CM} height={FLOOR_TILE_CM} fill="rgba(0,0,0,0.12)" />
            </pattern>
          );
        })}
      </defs>
      {Object.values(rooms).map((room) => {
        // Resolve boundary vertex IDs → positions; skip any room with missing vertices.
        const points = room.boundaryVertexIds
          .map((id) => vertices[id]?.position)
          .filter((p): p is Point2D => Boolean(p));
        if (points.length < 3) return null;

        const isSelected = selectedIds.includes(room.id);
        const mode = room.fillMode ?? 'filled';
        // 'transparent' and 'walls-only' draw no polygon fill; otherwise use the explicit
        // color, then the texture/tint resolver.
        const fill =
          mode === 'filled'
            ? room.fillColor ?? roomFill(room.floorMaterialId, room.roomType)
            : 'none';

        // Label position = polygon centroid (simple average is fine for convex-ish rooms).
        const cx = points.reduce((sum, p) => sum + p.x, 0) / points.length;
        const cy = points.reduce((sum, p) => sum + p.y, 0) / points.length;

        // Area in m² (positions are in cm, so divide by 10,000).
        const areaM2 = Math.abs(computeSignedArea(points)) / 10000;

        return (
          <g key={room.id}>
            <path
              d={polygonPath(points)}
              fill={fill}
              stroke={isSelected ? '#f59e0b' : mode === 'transparent' ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.08)'}
              strokeWidth={isSelected ? 4 : 1}
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
