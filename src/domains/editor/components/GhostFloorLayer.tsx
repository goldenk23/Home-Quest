// src/domains/editor/components/GhostFloorLayer.tsx

import React from 'react';
import { useFloorBelowGeometry } from '@/store/selectors/editorSelectors';
import type { Point2D } from '@/types/geometry';

/**
 * Draws the storey directly below the active one as a faint, non-interactive "ghost" tracing
 * (room areas + wall footprints). This gives a reference to build the new floor on top of, so
 * walls can be lined up with the floor beneath. Rendered behind the live floor's layers and
 * with `pointerEvents: none` so it never interferes with editing. Nothing shows on the ground
 * floor (no storey below).
 */
export const GhostFloorLayer: React.FC = React.memo(() => {
  const geo = useFloorBelowGeometry();
  if (!geo) return null;

  const rooms = Object.values(geo.rooms);
  const walls = Object.values(geo.walls);

  return (
    <g className="ghost-floor-layer" style={{ pointerEvents: 'none' }} aria-hidden>
      {/* Faint room fills so the rooms below read as shaded areas. */}
      {rooms.map((room) => {
        const poly = room.boundaryVertexIds
          .map((id) => geo.vertices[id]?.position)
          .filter((p): p is Point2D => Boolean(p));
        if (poly.length < 3) return null;
        const d = poly.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${-p.y}`).join(' ') + ' Z';
        return <path key={room.id} d={d} fill="#0ea5e9" fillOpacity={0.06} stroke="none" />;
      })}

      {/* Wall footprints below, drawn as dashed cyan lines at their real thickness. */}
      {walls.map((w) => {
        const s = geo.vertices[w.startVertexId]?.position;
        const e = geo.vertices[w.endVertexId]?.position;
        if (!s || !e) return null;
        return (
          <line
            key={w.id}
            x1={s.x}
            y1={-s.y}
            x2={e.x}
            y2={-e.y}
            stroke="#38bdf8"
            strokeWidth={Math.max(w.thickness, 6)}
            strokeOpacity={0.18}
            strokeLinecap="round"
          />
        );
      })}
      {/* Crisp centerlines on top of the footprints so corners are easy to trace/align to. */}
      {walls.map((w) => {
        const s = geo.vertices[w.startVertexId]?.position;
        const e = geo.vertices[w.endVertexId]?.position;
        if (!s || !e) return null;
        return (
          <line
            key={`c-${w.id}`}
            x1={s.x}
            y1={-s.y}
            x2={e.x}
            y2={-e.y}
            stroke="#0ea5e9"
            strokeWidth={1.5}
            strokeOpacity={0.5}
            strokeDasharray="10 8"
          />
        );
      })}
    </g>
  );
});

GhostFloorLayer.displayName = 'GhostFloorLayer';
