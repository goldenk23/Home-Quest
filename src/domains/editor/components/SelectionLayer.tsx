// src/domains/editor/components/SelectionLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { computeWallQuad } from '../services/geometry';
import { computeOpeningGeometry } from '../services/openingGeometry';
import { EDITOR_STYLE } from '../constants';
import type { Point2D } from '@/types/geometry';

function quadPath(tl: Point2D, tr: Point2D, br: Point2D, bl: Point2D): string {
  return `M ${tl.x} ${-tl.y} L ${tr.x} ${-tr.y} L ${br.x} ${-br.y} L ${bl.x} ${-bl.y} Z`;
}

/**
 * Draws highlight outlines for the current selection. Supports walls and furniture;
 * other entity types are simply ignored (no crash if an unknown id is selected).
 */
export const SelectionLayer: React.FC = React.memo(() => {
  const selectedIds = useAppStore((s) => s.selectedIds);
  const walls = useAppStore((s) => s.walls);
  const vertices = useAppStore((s) => s.vertices);
  const furniture = useAppStore((s) => s.furniture);
  const openings = useAppStore((s) => s.openings);

  if (selectedIds.length === 0) return null;

  return (
    <g className="selection-layer" pointerEvents="none">
      {selectedIds.map((id) => {
        const wall = walls[id];
        if (wall) {
          const start = vertices[wall.startVertexId]?.position;
          const end = vertices[wall.endVertexId]?.position;
          if (!start || !end) return null;
          const q = computeWallQuad(start, end, wall.thickness + EDITOR_STYLE.selectionStrokeWidth * 2);
          return (
            <path
              key={id}
              d={quadPath(q.topLeft, q.topRight, q.bottomRight, q.bottomLeft)}
              fill={EDITOR_STYLE.selectionGlow}
              stroke={EDITOR_STYLE.selectionStroke}
              strokeWidth={EDITOR_STYLE.selectionStrokeWidth}
            />
          );
        }

        const item = furniture[id];
        if (item) {
          const w = item.bounds.width * item.scale + EDITOR_STYLE.selectionStrokeWidth * 2;
          const d = item.bounds.depth * item.scale + EDITOR_STYLE.selectionStrokeWidth * 2;
          const degrees = (-item.rotation * 180) / Math.PI;
          return (
            <g key={id} transform={`translate(${item.position.x} ${-item.position.y}) rotate(${degrees})`}>
              <rect
                x={-w / 2}
                y={-d / 2}
                width={w}
                height={d}
                rx={3}
                fill={EDITOR_STYLE.selectionGlow}
                stroke={EDITOR_STYLE.selectionStroke}
                strokeWidth={EDITOR_STYLE.selectionStrokeWidth}
              />
              {/* Scale Handles (Corners) */}
              <circle cx={-w/2} cy={-d/2} r={4} fill="#fff" stroke={EDITOR_STYLE.selectionStroke} strokeWidth={2} />
              <circle cx={w/2} cy={-d/2} r={4} fill="#fff" stroke={EDITOR_STYLE.selectionStroke} strokeWidth={2} />
              <circle cx={-w/2} cy={d/2} r={4} fill="#fff" stroke={EDITOR_STYLE.selectionStroke} strokeWidth={2} />
              <circle cx={w/2} cy={d/2} r={4} fill="#fff" stroke={EDITOR_STYLE.selectionStroke} strokeWidth={2} />
              {/* Rotation Handle */}
              <line x1={0} y1={-d/2} x2={0} y2={-d/2 - 20} stroke={EDITOR_STYLE.selectionStroke} strokeWidth={2} />
              <circle cx={0} cy={-d/2 - 20} r={5} fill="#fff" stroke={EDITOR_STYLE.selectionStroke} strokeWidth={2} />
            </g>
          );
        }

        // Openings (doors / gates / windows / vents): outline the opening footprint on the wall.
        const opening = openings[id];
        if (opening) {
          const ow = walls[opening.wallId];
          if (!ow) return null;
          const s = vertices[ow.startVertexId]?.position;
          const en = vertices[ow.endVertexId]?.position;
          if (!s || !en) return null;
          const geo = computeOpeningGeometry(opening, s, en, ow.thickness);
          if (!geo) return null;
          const { center, v, n, halfW, halfThick } = geo;
          const pad = EDITOR_STYLE.selectionStrokeWidth;
          const hw = halfW + pad;
          const ht = halfThick + pad;
          const c1 = { x: center.x - v.x * hw + n.x * ht, y: center.y - v.y * hw + n.y * ht };
          const c2 = { x: center.x + v.x * hw + n.x * ht, y: center.y + v.y * hw + n.y * ht };
          const c3 = { x: center.x + v.x * hw - n.x * ht, y: center.y + v.y * hw - n.y * ht };
          const c4 = { x: center.x - v.x * hw - n.x * ht, y: center.y - v.y * hw - n.y * ht };
          return (
            <path
              key={id}
              d={quadPath(c1, c2, c3, c4)}
              fill={EDITOR_STYLE.selectionGlow}
              stroke={EDITOR_STYLE.selectionStroke}
              strokeWidth={EDITOR_STYLE.selectionStrokeWidth}
            />
          );
        }

        return null;
      })}
    </g>
  );
});

SelectionLayer.displayName = 'SelectionLayer';
