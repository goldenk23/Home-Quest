import React from 'react';
import { useWallSegments } from '@/store/selectors/editorSelector';
import { computeWallQuad } from '../services/geometry';
import { EDITOR_STYLE } from '../constants';
import type { Point2D } from '@/types/geometry';

/** Build an SVG path string for a quad, applying the world→SVG Y‑flip (-y). */
function quadPath(tl: Point2D, tr: Point2D, br: Point2D, bl: Point2D): string {
  return (
    `M ${tl.x} ${-tl.y} ` +
    `L ${tr.x} ${-tr.y} ` +
    `L ${br.x} ${-br.y} ` +
    `L ${bl.x} ${-bl.y} Z`
  );
}

/**
 * ============================================================================
 * WHAT IS THIS FILE FOR?
 * ============================================================================
 * 
 * This file is responsible for drawing all the physical walls onto the screen.
 * 
 * THE MENTAL MODEL:
 * 
 * 1. THE DATA (1D): Inside our global store, a wall isn't a complex shape. 
 *    It is simply a 1D mathematical line (a Start Point and an End Point) 
 *    plus a thickness value (e.g., "this wall is 20cm thick").
 * 
 * 2. THE MATH (2D): When it's time to draw the wall, the `computeWallQuad` 
 *    function uses trigonometry to expand that thin 1D line outward into a 
 *    2D rectangle (a "quad"). It gives us the exact coordinates for the 4 
 *    corners of the physical wall: Top-Left, Top-Right, Bottom-Right, Bottom-Left.
 * 
 * 3. THE DRAWING (SVG): Finally, the `quadPath` function below connects 
 *    those 4 corners using a literal "connect-the-dots" instruction string 
 *    (e.g., M = Move to corner 1, L = Line to corner 2...). 
 * 
 * NOTE ON Y-FLIPPING:
 * In standard math (which our store uses), moving UP increases the Y value. 
 * But in web browsers (SVG), moving DOWN increases the Y value. Therefore, 
 * `quadPath` mathematically flips all the Y coordinates (`-tl.y`) so the 
 * walls don't accidentally draw upside down!
 * 
 * DIAGRAM: HOW WALLS ARE RENDERED
 *
 * To view a visual flowchart of this pipeline, simply Ctrl+Click 
 * the link below to open it in Mermaid Live Editor:
 * 
 * https://mermaid.live/view#base64:eyJjb2RlIjoiZ3JhcGggVERcbiAgICBjbGFzc0RlZiBzdGF0ZSBmaWxsOiM0ZjQ2ZTUsc3Ryb2tlOiMzMTJlODEsc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG4gICAgY2xhc3NEZWYgbWF0aCBmaWxsOiMxMGI5ODEsc3Ryb2tlOiMwNjRlM2Isc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG4gICAgY2xhc3NEZWYgc3ZnIGZpbGw6I2Y1OWUwYixzdHJva2U6Izc4MzUwZixzdHJva2Utd2lkdGg6MnB4LGNvbG9yOiNmZmZcblxuICAgIHN1YmdyYXBoIFN0ZXAxIFtcIlN0ZXAgMTogVGhlIFN0b3JlIERhdGEgKDFEKVwiXVxuICAgICAgICBTMVtcIldhbGwgQ2VudGVybGluZTxici8+KFN0YXJ0IFBvaW50IOKUgOKUgOKUgCBFbmQgUG9pbnQpXCJdOjo6c3RhdGVcbiAgICAgICAgUzJbXCJXYWxsIFRoaWNrbmVzczxici8+KGUuZy4sIDIwY20pXCJdOjo6c3RhdGVcbiAgICBlbmRcblxuICAgIHN1YmdyYXBoIFN0ZXAyIFtcIlN0ZXAgMjogVGhlIE1hdGggKDJEIFF1YWQpXCJdXG4gICAgICAgIE0xW1wiY29tcHV0ZVdhbGxRdWFkKClcIl06OjptYXRoXG4gICAgICAgIE0yW1wiQ2FsY3VsYXRlcyA0IGNvcm5lcnM6PGJyLz5Ub3AtTGVmdCwgVG9wLVJpZ2h0LDxici8+Qm90dG9tLVJpZ2h0LCBCb3R0b20tTGVmdFwiXTo6Om1hdGhcbiAgICAgICAgTTEgLS0+IE0yXG4gICAgZW5kXG5cbiAgICBzdWJncmFwaCBTdGVwMyBbXCJTdGVwIDM6IFRoZSBTVkcgUGF0aFwiXVxuICAgICAgICBWMVtcInF1YWRQYXRoKClcIl06OjpzdmdcbiAgICAgICAgVjJbXCJGbGlwcyB0aGUgWS1heGlzICgteSk8YnIvPk1hdGggWSBnb2VzIFVQLCBTVkcgWSBnb2VzIERPV05cIl06OjpzdmdcbiAgICAgICAgVjNbXCJEcmF3cyBhIGZpbGxlZCBzaGFwZTo8YnIvPjxwYXRoIGQ9J00geCB5IEwgeCB5IC4uLicgLz5cIl06OjpzdmdcbiAgICAgICAgVjEgLS0+IFYyXG4gICAgICAgIFYyIC0tPiBWM1xuICAgIGVuZFxuXG4gICAgUzEgLS0+IE0xXG4gICAgUzIgLS0+IE0xXG4gICAgTTIgLS0+IFYxIiwibWVybWFpZCI6IntcInRoZW1lXCI6IFwiZGVmYXVsdFwifSIsImF1dG9TeW5jIjp0cnVlLCJ1cGRhdGVEaWFncmFtIjp0cnVlfQ==
 * ============================================================================
 */
export const WallLayer: React.FC = React.memo(() => {
  const walls = useWallSegments();

  return (
    <g className="wall-layer">
      {walls.map((wall) => {
        const quad = computeWallQuad(wall.start, wall.end, wall.thickness);
        return (
          <path
            key={wall.id}
            d={quadPath(quad.topLeft, quad.topRight, quad.bottomRight, quad.bottomLeft)}
            fill={EDITOR_STYLE.wallFill}
            stroke={EDITOR_STYLE.wallStroke}
            strokeWidth={EDITOR_STYLE.wallStrokeWidth}
            // data-id lets selection / hit‑testing identify the wall later.
            data-entity-id={wall.id}
            data-entity-type="wall"
          />
        );
      })}
    </g>
  );
});

WallLayer.displayName = 'WallLayer';