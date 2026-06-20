import React from 'react';
import { useAppStore } from '@/store';
import { computeWallQuad } from '../services/geometry';
import { EDITOR_STYLE } from '../constants';
import type { Point2D } from '@/types/geometry';

function quadPath(tl: Point2D, tr: Point2D, br: Point2D, bl: Point2D): string {
  return `M ${tl.x} ${-tl.y} L ${tr.x} ${-tr.y} L ${br.x} ${-br.y} L ${bl.x} ${-bl.y} Z`;
}

/**
 * ============================================================================
 * WHAT IS THIS FILE FOR?
 * ============================================================================
 * 
 * This file is responsible for drawing a glowing outline around whatever the 
 * user is currently clicking on (like a Wall or a piece of Furniture).
 * 
 * THE MENTAL MODEL:
 * 
 * This layer works by using a very simple visual trick: it just draws the 
 * exact same item again, but slightly bigger and colored bright blue!
 * 
 * 1. CHECK SELECTION: It looks at the store to see what IDs are currently 
 *    selected by the user.
 * 
 * 2. IF IT'S A WALL: It uses the exact same `computeWallQuad` math as the 
 *    WallLayer, but it intentionally makes the thickness slightly WIDER. Because 
 *    this layer sits behind the actual wall, the wider edges peek out from 
 *    behind the wall, creating a glowing outline!
 * 
 * 3. IF IT'S FURNITURE: It uses the exact same `translate` and `rotate` math 
 *    as the FurnitureLayer, but it makes the rectangle slightly WIDER and DEEPER. 
 *    Again, this causes the bright blue box to peek out from behind the real 
 *    furniture.
 * 
 * If it doesn't recognize the ID, it simply ignores it so the app never crashes.
 * 
 * DIAGRAM: HOW SELECTIONS ARE RENDERED
 *
 * To view a visual flowchart of this pipeline, simply Ctrl+Click 
 * the link below to open it in Mermaid Live Editor:
 * 
 * https://mermaid.live/view#base64:eyJjb2RlIjoiZ3JhcGggVERcbiAgICBjbGFzc0RlZiBsb2dpYyBmaWxsOiM0ZjQ2ZTUsc3Ryb2tlOiMzMTJlODEsc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG4gICAgY2xhc3NEZWYgd2FsbCBmaWxsOiMxMGI5ODEsc3Ryb2tlOiMwNjRlM2Isc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG4gICAgY2xhc3NEZWYgZnVybiBmaWxsOiNmNTllMGIsc3Ryb2tlOiM3ODM1MGYsc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG5cbiAgICBzdWJncmFwaCBTdGVwMSBbXCJTdGVwIDE6IENoZWNrIFNlbGVjdGlvblwiXVxuICAgICAgICBMMVtcIkdldCBzZWxlY3RlZElkczxici8+ZnJvbSBTdG9yZVwiXTo6OmxvZ2ljXG4gICAgICAgIEwye1wiV2hhdCBpcyB0aGlzIElEP1wifTo6OmxvZ2ljXG4gICAgICAgIEwxIC0tPiBMMlxuICAgIGVuZFxuXG4gICAgc3ViZ3JhcGggU3RlcDIgW1wiU3RlcCAyOiBEcmF3IFdhbGwgR2xvd1wiXVxuICAgICAgICBXMVtcIkl0J3MgYSBXYWxsIVwiXTo6OndhbGxcbiAgICAgICAgVzJbXCJVc2UgY29tcHV0ZVdhbGxRdWFkKCk8YnIvPk1ha2UgdGhpY2tuZXNzIHNsaWdodGx5IFdJREVSPGJyLz50aGFuIHRoZSByZWFsIHdhbGxcIl06Ojp3YWxsXG4gICAgICAgIFczW1wiRHJhdyBnbG93aW5nIHNoYXBlPGJyLz51bmRlcm5lYXRoIHRoZSByZWFsIHdhbGxcIl06Ojp3YWxsXG4gICAgICAgIFcxIC0tPiBXMiAtLT4gVzNcbiAgICBlbmRcblxuICAgIHN1YmdyYXBoIFN0ZXAzIFtcIlN0ZXAgMzogRHJhdyBGdXJuaXR1cmUgR2xvd1wiXVxuICAgICAgICBGMVtcIkl0J3MgRnVybml0dXJlIVwiXTo6OmZ1cm5cbiAgICAgICAgRjJbXCJVc2UgdHJhbnNsYXRlL3JvdGF0ZTxici8+TWFrZSByZWN0YW5nbGUgc2xpZ2h0bHkgV0lERVI8YnIvPnRoYW4gdGhlIHJlYWwgZnVybml0dXJlXCJdOjo6ZnVyblxuICAgICAgICBGM1tcIkRyYXcgZ2xvd2luZyBib3g8YnIvPnVuZGVybmVhdGggcmVhbCBmdXJuaXR1cmVcIl06OjpmdXJuXG4gICAgICAgIEYxIC0tPiBGMiAtLT4gRjNcbiAgICBlbmRcblxuICAgIEwyIC0tPnxXYWxsIElEfCBXMVxuICAgIEwyIC0tPnxGdXJuaXR1cmUgSUR8IEYxXG4gICAgTDIgLS0+fFVua25vd24gSUR8IElnbm9yZVtJZ25vcmVdIiwibWVybWFpZCI6IntcInRoZW1lXCI6IFwiZGVmYXVsdFwifSIsImF1dG9TeW5jIjp0cnVlLCJ1cGRhdGVEaWFncmFtIjp0cnVlfQ==
 * ============================================================================
 */
export const SelectionLayer: React.FC = React.memo(() => {
  const selectedIds = useAppStore((s) => s.selectedIds);
  const walls = useAppStore((s) => s.walls);
  const vertices = useAppStore((s) => s.vertices);
  const furniture = useAppStore((s) => s.furniture);

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
          const w = item.bounds.width + EDITOR_STYLE.selectionStrokeWidth * 2;
          const d = item.bounds.depth + EDITOR_STYLE.selectionStrokeWidth * 2;
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
            </g>
          );
        }

        return null;
      })}
    </g>
  );
});

SelectionLayer.displayName = 'SelectionLayer';