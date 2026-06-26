// src/domains/editor/components/OpeningsLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { computeOpeningGeometry } from '../services/openingGeometry';
import { resolveKind } from '@/domains/shared/openings/openingCatalog';
import type { Point2D } from '@/types/geometry';

/** Ray-casting point-in-polygon test (polygon points in world cm). */
function pointInPolygon(p: Point2D, polygon: Point2D[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y;
    const xj = polygon[j].x, yj = polygon[j].y;
    const intersect = yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export const OpeningsLayer: React.FC = React.memo(() => {
  const openingsMap = useAppStore(s => s.openings);
  const openings = Object.values(openingsMap);
  const walls = useAppStore(s => s.walls);
  const vertices = useAppStore(s => s.vertices);
  const rooms = useAppStore(s => s.rooms);

  /**
   * Picks which side of the wall a door swings into. We probe a point just off each face
   * at the door centre and prefer the side that lies inside a room (so doors open into
   * the room, like a real plan). +1 = along +normal, −1 = along −normal.
   */
  const chooseSwingSide = (center: Point2D, n: Point2D, probe: number): 1 | -1 => {
    const pPlus = { x: center.x + n.x * probe, y: center.y + n.y * probe };
    const pMinus = { x: center.x - n.x * probe, y: center.y - n.y * probe };
    let plusInside = false;
    let minusInside = false;
    for (const room of Object.values(rooms)) {
      const poly = room.boundaryVertexIds
        .map((id) => vertices[id]?.position)
        .filter((pt): pt is Point2D => Boolean(pt));
      if (poly.length < 3) continue;
      if (!plusInside && pointInPolygon(pPlus, poly)) plusInside = true;
      if (!minusInside && pointInPolygon(pMinus, poly)) minusInside = true;
    }
    if (plusInside && !minusInside) return 1;
    if (minusInside && !plusInside) return -1;
    return 1; // ambiguous (both/neither) → consistent default
  };

  return (
    <g className="openings-layer">
      {openings.map(opening => {
        const wall = walls[opening.wallId];
        if (!wall) return null;

        const start = vertices[wall.startVertexId]?.position;
        const end = vertices[wall.endVertexId]?.position;
        if (!start || !end) return null;

        const geo = computeOpeningGeometry(opening, start, end, wall.thickness);
        if (!geo) return null;

        const { center, v, n, halfW, halfThick, j1, j2 } = geo;

        // ---- DOOR: empty gap (cut by WallLayer) + quarter-circle swing symbol --------
        if (opening.type === 'door') {
          const width = halfW * 2;
          const side = chooseSwingSide(center, n, halfThick + 20);

          // Hinge at j1; closed leaf lies along the wall to j2; open leaf is perpendicular.
          const hinge = j1;
          const closedEnd = j2;
          const openEnd = { x: hinge.x + n.x * side * width, y: hinge.y + n.y * side * width };

          // Quarter-circle swing arc, sampled as a polyline (avoids SVG arc-flag pitfalls).
          const angClosed = Math.atan2(v.y, v.x);          // hinge → closedEnd direction
          const angOpen = Math.atan2(n.y * side, n.x * side); // hinge → openEnd direction
          let delta = angOpen - angClosed;
          while (delta > Math.PI) delta -= 2 * Math.PI;
          while (delta < -Math.PI) delta += 2 * Math.PI;

          const SEGMENTS = 18;
          let arc = '';
          for (let i = 0; i <= SEGMENTS; i++) {
            const ang = angClosed + (delta * i) / SEGMENTS;
            const px = hinge.x + width * Math.cos(ang);
            const py = hinge.y + width * Math.sin(ang);
            arc += `${i === 0 ? 'M' : 'L'} ${px} ${-py} `;
          }

          const stroke = '#ca8a04'; // amber-600 — keeps door identity
          return (
            <g
              key={opening.id}
              onClick={(e) => {
                e.stopPropagation();
                useAppStore.getState().select([opening.id]);
              }}
              style={{ cursor: 'pointer' }}
            >
              {/* Jamb stops: short lines across the wall thickness mark the opening edges. */}
              <line
                x1={j1.x + n.x * halfThick} y1={-(j1.y + n.y * halfThick)}
                x2={j1.x - n.x * halfThick} y2={-(j1.y - n.y * halfThick)}
                stroke="#6b7280" strokeWidth={2}
              />
              <line
                x1={j2.x + n.x * halfThick} y1={-(j2.y + n.y * halfThick)}
                x2={j2.x - n.x * halfThick} y2={-(j2.y - n.y * halfThick)}
                stroke="#6b7280" strokeWidth={2}
              />
              {/* Swing arc (the area the door sweeps). */}
              <path d={arc} fill="none" stroke={stroke} strokeWidth={2} />
              {/* Door leaf (the open panel). */}
              <line
                x1={hinge.x} y1={-hinge.y}
                x2={openEnd.x} y2={-openEnd.y}
                stroke={stroke} strokeWidth={3}
              />
              {/* Invisible thick hit area along the closed opening for easier clicking. */}
              <line
                x1={hinge.x} y1={-hinge.y}
                x2={closedEnd.x} y2={-closedEnd.y}
                stroke="transparent" strokeWidth={Math.max(halfThick, 8)}
              />
            </g>
          );
        }

        // ---- WINDOW / VENT: keep the framed rectangle representation -------------------
        const corners = [
          { x: center.x - v.x * halfW + n.x * halfThick, y: center.y - v.y * halfW + n.y * halfThick },
          { x: center.x + v.x * halfW + n.x * halfThick, y: center.y + v.y * halfW + n.y * halfThick },
          { x: center.x + v.x * halfW - n.x * halfThick, y: center.y + v.y * halfW - n.y * halfThick },
          { x: center.x - v.x * halfW - n.x * halfThick, y: center.y - v.y * halfW - n.y * halfThick },
        ];
        const path =
          `M ${corners[0].x} ${-corners[0].y} ` +
          `L ${corners[1].x} ${-corners[1].y} ` +
          `L ${corners[2].x} ${-corners[2].y} ` +
          `L ${corners[3].x} ${-corners[3].y} Z`;

        let fill = '#93c5fd'; // window blue
        let stroke = '#2563eb';
        let strokeDasharray = 'none';
        const kind = resolveKind(opening.kind, opening.type);
        if (opening.type === 'vent') {
          fill = kind.color;
          stroke = '#0d9488';
          strokeDasharray = '4 2';
        } else if (opening.type === 'ac') {
          fill = '#e2e8f0';
          stroke = '#475569';
        } else {
          // windows: use the kind colour, kept blue-ish
          fill = kind.color;
          stroke = '#2563eb';
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
              useAppStore.getState().select([opening.id]);
            }}
            style={{ cursor: 'pointer' }}
          />
        );
      })}
    </g>
  );
});

OpeningsLayer.displayName = 'OpeningsLayer';
