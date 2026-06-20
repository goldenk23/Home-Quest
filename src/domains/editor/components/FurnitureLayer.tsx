import React from 'react';
import { useAppStore } from '@/store';

/**
 * ============================================================================
 * WHAT IS THIS FILE FOR?
 * ============================================================================
 * 
 * This file is responsible for drawing a 2D "footprint" (a top-down view) 
 * for every piece of furniture placed on the floor plan.
 * 
 * THE MENTAL MODEL:
 * 
 * 1. THE DATA: The store tells us exactly where the furniture is (Position X/Y), 
 *    how it's angled (Rotation), and how big it is (Width/Depth).
 * 
 * 2. THE TRANSFORM (<g>): Instead of calculating difficult math to draw a 
 *    tilted rectangle, we use an SVG "group" `<g>` and use a classic trick:
 *     - We move the entire group to the furniture's exact X/Y position (`translate`).
 *     - We then spin the entire group to match the furniture's angle (`rotate`).
 * 
 * 3. THE DRAWING (<rect>): Because the group was moved and spun for us, all 
 *    we have to do is draw a perfectly straight rectangle centered at `(0,0)`.
 *    We also draw a tiny "tick mark" line on one side so the user can easily
 *    tell which way the furniture is facing!
 * 
 * NOTE ON FLIPPING: 
 * Because computer graphics (SVG) flip the Y-axis upside down compared to 
 * standard math, we have to negate both the Y position (`-y`) AND the 
 * rotation (`-degrees`) so the furniture doesn't end up on the wrong side 
 * of the room, facing the wrong way!
 * 
 * DIAGRAM: HOW FURNITURE IS RENDERED
 *
 * To view a visual flowchart of this pipeline, simply Ctrl+Click 
 * the link below to open it in Mermaid Live Editor:
 * 
 * https://mermaid.live/view#base64:eyJjb2RlIjoiZ3JhcGggVERcbiAgICBjbGFzc0RlZiBzdG9yZSBmaWxsOiM0ZjQ2ZTUsc3Ryb2tlOiMzMTJlODEsc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG4gICAgY2xhc3NEZWYgdHJhbnNmb3JtIGZpbGw6IzEwYjk4MSxzdHJva2U6IzA2NGUzYixzdHJva2Utd2lkdGg6MnB4LGNvbG9yOiNmZmZcbiAgICBjbGFzc0RlZiBkcmF3aW5nIGZpbGw6I2Y1OWUwYixzdHJva2U6Izc4MzUwZixzdHJva2Utd2lkdGg6MnB4LGNvbG9yOiNmZmZcblxuICAgIHN1YmdyYXBoIFN0ZXAxIFtcIlN0ZXAgMTogVGhlIFN0b3JlIERhdGFcIl1cbiAgICAgICAgUzFbXCJGdXJuaXR1cmUgRGF0YTxici8+KFBvc2l0aW9uIFgvWSwgUm90YXRpb24sPGJyLz4gV2lkdGgvRGVwdGgpXCJdOjo6c3RvcmVcbiAgICBlbmRcblxuICAgIHN1YmdyYXBoIFN0ZXAyIFtcIlN0ZXAgMjogVGhlIFRyYW5zZm9ybSAoJmx0O2cmZ3Q7KVwiXVxuICAgICAgICBUMVtcIk1vdmUgdG8gUG9zaXRpb248YnIvPnRyYW5zbGF0ZSh4LCAteSlcIl06Ojp0cmFuc2Zvcm1cbiAgICAgICAgVDJbXCJQaXZvdCAvIFJvdGF0ZTxici8+cm90YXRlKC1kZWdyZWVzKVwiXTo6OnRyYW5zZm9ybVxuICAgICAgICBUMSAtLT4gVDJcbiAgICBlbmRcblxuICAgIHN1YmdyYXBoIFN0ZXAzIFtcIlN0ZXAgMzogVGhlIERyYXdpbmcgKCZsdDtyZWN0Jmd0OylcIl1cbiAgICAgICAgRDFbXCJEcmF3IGEgcmVjdGFuZ2xlPGJyLz5jZW50ZXJlZCBhdCAoMCwwKVwiXTo6OmRyYXdpbmdcbiAgICAgICAgRDJbXCJEcmF3IGEgJ3RpY2sgbWFyaycgbGluZTxici8+cG9pbnRpbmcgdG8gdGhlIGZyb250XCJdOjo6ZHJhd2luZ1xuICAgICAgICBEMSAtLT4gRDJcbiAgICBlbmRcblxuICAgIFMxIC0tPiBUMVxuICAgIFQyIC0tPiBEMSIsIm1lcm1haWQiOiJ7XCJ0aGVtZVwiOiBcImRlZmF1bHRcIn0iLCJhdXRvU3luYyI6dHJ1ZSwidXBkYXRlRGlhZ3JhbSI6dHJ1ZX0=
 * ============================================================================
 */
export const FurnitureLayer: React.FC = React.memo(() => {
  const furniture = useAppStore((s) => s.furniture);

  return (
    <g className="furniture-layer">
      {Object.values(furniture).map((item) => {
        const w = item.bounds.width;
        const d = item.bounds.depth;
        const degrees = (-item.rotation * 180) / Math.PI;
        return (
          <g
            key={item.id}
            transform={`translate(${item.position.x} ${-item.position.y}) rotate(${degrees})`}
            data-entity-id={item.id}
            data-entity-type="furniture"
          >
            <rect
              x={-w / 2}
              y={-d / 2}
              width={w}
              height={d}
              rx={3}
              fill="rgba(56, 189, 248, 0.20)"
              stroke="#38bdf8"
              strokeWidth={1.5}
            />
            {/* Small tick marks the "front" of the piece so orientation is visible. */}
            <line x1={0} y1={-d / 2} x2={0} y2={-d / 2 + Math.min(d * 0.25, 15)} stroke="#38bdf8" strokeWidth={2} />
          </g>
        );
      })}
    </g>
  );
});

FurnitureLayer.displayName = 'FurnitureLayer';
