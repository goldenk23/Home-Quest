# Home Quest — Implementation Guide (Restructured: Part 5 Onwards)

> **How to read this document.** Parts 1–4 of the original `IMPLEMENTATION_GUIDE.md`
> (System Architecture, Coordinate Systems, the Floor‑Plan Data Model, and the Zustand
> Store) are treated as **already built and working**. Every file and export they
> established — `src/types/geometry.ts`, `src/types/editor.ts`, `src/domains/editor/services/geometry.ts`
> (`computeWallQuad`, `screenToWorld`, `worldToScreen`), `src/domains/editor/hooks/useSnapping.ts`
> (`applySnapping`), the store in `src/store/index.ts`, all four slices, and the selectors
> in `src/store/selectors/editorSelectors.ts` (`useWallSegments`, `useEndpoints`,
> `useGeometryForViewer`) — is assumed to exist exactly as written there.
>
> This document **replaces everything from Part 5 onwards**. It has been re‑ordered so
> that **a file is always created before anything imports it**, and every file that the
> original guide referenced but never actually defined has been written out and slotted
> into the correct step. Each step explains *why* the code exists in plain language
> before showing the code, and the code itself stays production‑grade.

---

## What was broken (and how this rewrite fixes it)

The original guide from Part 5 onwards had three classes of problems. They are called
out here once so you understand the kinds of fixes you will see throughout:

1. **Imports with no source file.** Part 5's `EditorCanvas.tsx` imported `WallLayer`,
   `RoomLayer`, `FurnitureLayer`, `SelectionLayer`, and `DrawingPreview` — none of which
   were ever defined anywhere in the guide. These are now written out as real files,
   each in its own step.
2. **Using things before they exist.** `EditorCanvas` (Part 5) used the `usePanZoom`
   hook that was only defined *later* in the same part, and it wired up wall‑drawing
   that only appeared in Part 6. Steps are now ordered bottom‑up: leaf utilities and
   layers first, the canvas that composes them last.
3. **Dangling / contradictory references.** Part 6's `useWallDrawing` called
   `findIntersectionsPure(...)` and `splitWallAtPoint(...)`, but `wallOps.ts` only
   exported `findIntersections` (with a different signature) and a
   `splitWallAtPoint_DEPRECATED` flagged as racy. These are reconciled into a single
   correct, atomic implementation, and the room‑detection code (which nothing ever
   called) is now wired in through a hook.

---

## Corrected file tree (Part 5 onwards)

Files marked **(new)** did not exist in the original guide's steps and are created here
to remove the "orphaned import" problem. Files marked **(modify)** already appeared but
are rewritten for correct ordering or to fix bugs. Installment 1 (this document so far)
covers the **2D Editor pipeline** — the rest follow in the same linear style.

```
src/
├── app/
│   ├── App.tsx                         # (modify) Part 21 — lazy domains + error boundaries
│   ├── ErrorBoundary.tsx               # (new)    Part 21
│   ├── monitoring.ts                   # (new)    Part 19
│   ├── hooks/
│   │   └── useKeyboardShortcuts.ts     # (new)    Part 22
│   └── fallbacks/
│       ├── EditorFallback.tsx          # (new)    Part 21
│       ├── ViewerFallback.tsx          # (new)    Part 21
│       └── VastuFallback.tsx           # (new)    Part 21
├── domains/
│   ├── editor/
│   │   ├── constants.ts                # (new)    Part 5  — layer styling, room colors
│   │   ├── components/
│   │   │   ├── GridLayer.tsx           # (modify) Part 5
│   │   │   ├── WallLayer.tsx           # (new)    Part 5
│   │   │   ├── RoomLayer.tsx           # (new)    Part 5
│   │   │   ├── FurnitureLayer.tsx      # (new)    Part 5
│   │   │   ├── SelectionLayer.tsx      # (new)    Part 5
│   │   │   ├── DrawingPreview.tsx      # (new)    Part 6
│   │   │   └── EditorCanvas.tsx        # (modify) Part 5 shell → Part 6 wiring
│   │   ├── hooks/
│   │   │   ├── usePan.ts               # (modify) Part 5
│   │   │   ├── useWallDrawing.ts       # (modify) Part 6 (was useDrawing.ts)
│   │   │   ├── useRoomDetection.ts     # (new)    Part 7 — runs detection, writes store
│   │   │   └── useKeyboardEditor.ts    # (new)    Part 24
│   │   └── services/
│   │       ├── wallOps.ts              # (modify) Part 6 — single atomic implementation
│   │       ├── roomDetection.ts        # (modify) Part 7
│   │       ├── collision.ts            # (new)    Part 12 / Part 27
│   │       ├── safeGeometry.ts         # (new)    Part 21
│   │       └── index.ts                # (new)    Part 16 — public API barrel
│   ├── viewer/
│   │   ├── components/
│   │   │   ├── ViewerCanvas.tsx        # (new)    Part 8
│   │   │   ├── SceneEnvironment.tsx    # (new)    Part 8
│   │   │   ├── SceneContent.tsx        # (new)    Part 8
│   │   │   ├── WallMesh.tsx            # (new)    Part 10
│   │   │   ├── FloorMesh.tsx           # (new)    Part 10
│   │   │   ├── FurnitureModel.tsx      # (new)    Part 11
│   │   │   ├── CameraController.tsx    # (new)    Part 13
│   │   │   └── VastuOverlay3D.tsx      # (new)    Part 15
│   │   ├── hooks/
│   │   │   ├── useAssetLoader.ts       # (new)    Part 11
│   │   │   ├── useSafeAssetLoader.ts   # (new)    Part 21
│   │   │   ├── useOrbitCamera.ts       # (new)    Part 13
│   │   │   └── useFirstPerson.ts       # (new)    Part 13
│   │   └── services/
│   │       ├── transform.ts            # (exists) Part 9 — confirm planTo3D
│   │       ├── extrusion.ts            # (new)    Part 10
│   │       └── materials.ts            # (new)    Part 10
│   ├── vastu/
│   │   ├── components/
│   │   │   ├── VastuOverlay2D.tsx      # (new)    Part 15
│   │   │   └── VastuPanel.tsx          # (new)    Part 24
│   │   └── services/
│   │       ├── vectors.ts              # (new)    Part 14
│   │       ├── brahmasthan.ts          # (new)    Part 14
│   │       ├── zones.ts                # (new)    Part 14
│   │       ├── scoring.ts              # (new)    Part 14
│   │       └── index.ts                # (new)    Part 16 — public API barrel
│   └── shared/
│       └── components/
│           ├── Toolbar.tsx             # (new)    Part 24
│           └── ScreenReaderAnnouncer.tsx # (new)  Part 24
├── store/
│   ├── index.ts                        # (modify) Part 23 — add persist middleware
│   ├── history/
│   │   ├── commands.ts                 # (new)    Part 22
│   │   ├── historyManager.ts           # (new)    Part 22
│   │   └── ... slices/historySlice.ts  # (new)    Part 22
│   └── persistence/
│       ├── persistConfig.ts            # (new)    Part 23
│       ├── migrations.ts               # (new)    Part 23
│       ├── fileIO.ts                   # (new)    Part 23
│       └── validation.ts              # (new)    Part 23
└── utils/
    ├── math.ts                         # (new)    Part 16
    ├── errors.ts                       # (new)    Part 21
    ├── env.ts                          # (new)    Part 19
    └── eventBus.ts                     # (new)    Part 16
```

> Tests (`__tests__/…`, `tests/visual/…`) introduced from Part 18, 29–31 are folded in
> beside the code they exercise. They are listed in their own installments rather than
> duplicated here.

---

## PART 5: 2D Editor Rendering

### Why SVG (the one decision that shapes this whole part)

A residential floor plan has maybe 50–200 walls, 10–30 rooms, and a couple hundred
furniture items. At that scale, **SVG** wins over an imperative `<canvas>`: every wall is
a real DOM element, so click/hover handling and React's declarative model come for free,
and it stays crisp at any zoom. Canvas only pulls ahead past ~5,000 interactive elements,
which a house plan never reaches.

The editor is built as a stack of SVG **layers** drawn in z‑order. Each layer reads only
the slice of state it needs, so a furniture hover never re‑renders the walls.

```
GridLayer        (bottom)  → infinite dotted grid
RoomLayer                  → filled room polygons
WallLayer                  → thick wall quads
FurnitureLayer             → furniture icons
SelectionLayer   (top)     → highlight outlines for selected entities
DrawingPreview   (top)     → rubber‑band line while drawing (added in Part 6)
```

We build these **leaves first**, then assemble them in `EditorCanvas` at the end of the
part. That ordering is the whole point of this rewrite: nothing is imported before it
exists.

> **One coordinate rule to remember.** World space has **Y pointing up** (architectural
> convention), but SVG has **Y pointing down**. Pan/zoom is applied with a single
> `<g transform="translate(...) scale(...)">` that does *not* flip Y. So every layer plots
> a world point `p` at SVG‑local `(p.x, -p.y)`. You will see `-p.y` in every layer below —
> that minus sign is the Y‑flip, nothing more.

---

### Part 5, Step 1: Editor constants — **`src/domains/editor/constants.ts`** (new)

Before any layer renders, we need shared, named values for colors, stroke widths, and
room fills. Putting them in one file keeps styling consistent and makes theming a
one‑file change later. This file has **no imports from our own code**, so it is safe to
create first.

```typescript
// src/domains/editor/constants.ts

import type { RoomType } from '@/types/editor';

/**
 * Visual styling for the 2D editor layers.
 * All sizes are in WORLD units (centimeters) unless noted, because layers render
 * inside the zoom/pan <g> transform where 1 unit = 1 cm.
 */
export const EDITOR_STYLE = {
  /** Wall fill color (walls are filled quads, not stroked lines). */
  wallFill: '#e5e7eb',
  wallStroke: '#9ca3af',
  wallStrokeWidth: 1, // cm

  /** Vertex dots drawn at wall junctions. */
  vertexRadius: 4, // cm
  vertexFill: '#60a5fa',

  /** Selection highlight. */
  selectionStroke: '#f59e0b',
  selectionStrokeWidth: 3, // cm
  selectionGlow: 'rgba(245, 158, 11, 0.25)',

  /** Live drawing preview line (Part 6). */
  previewStroke: '#34d399',
  previewStrokeWidth: 2, // cm
  previewDash: '12 8', // dash pattern in cm
} as const;

/**
 * Fill color per room type. Used by RoomLayer to tint room polygons so a glance
 * communicates layout. Colors are intentionally low‑saturation so walls/furniture
 * stay legible on top.
 */
export const ROOM_FILL_COLORS: Record<RoomType, string> = {
  living: 'rgba(96, 165, 250, 0.18)',
  bedroom: 'rgba(167, 139, 250, 0.18)',
  kitchen: 'rgba(251, 146, 60, 0.18)',
  bathroom: 'rgba(45, 212, 191, 0.18)',
  puja: 'rgba(250, 204, 21, 0.20)',
  study: 'rgba(129, 140, 248, 0.18)',
  dining: 'rgba(248, 113, 113, 0.16)',
  storage: 'rgba(148, 163, 184, 0.18)',
  garage: 'rgba(100, 116, 139, 0.18)',
  balcony: 'rgba(74, 222, 128, 0.16)',
  entrance: 'rgba(244, 114, 182, 0.16)',
  corridor: 'rgba(203, 213, 225, 0.14)',
  custom: 'rgba(148, 163, 184, 0.14)',
};
```

---

### Part 5, Step 2: Pan & zoom — **`src/domains/editor/hooks/usePan.ts`** (modify)

The canvas must let users pan (drag) and zoom (wheel). We isolate that math in
`usePanZoom` so `EditorCanvas` stays focused on composition. It exposes the current
`ViewTransform` (from Part 2's `geometry.ts` types) plus ready‑made event handlers.

We define this hook **before** `EditorCanvas` because the canvas imports it. (In the
original guide it appeared *after* the canvas — that was the ordering bug.)

```typescript
// src/domains/editor/hooks/usePan.ts

import { useState, useCallback, useRef, RefObject } from 'react';
import type { ViewTransform } from '@/types/geometry';

const MIN_SCALE = 0.1;
const MAX_SCALE = 10;
const ZOOM_FACTOR = 1.1; // each wheel notch zooms by 10%

/**
 * Owns pan/zoom state for the editor SVG.
 *
 * @param svgRef - ref to the <svg> element, needed to map the cursor position into
 *                 element‑local coordinates so we can zoom toward the pointer.
 */
export function usePanZoom(svgRef: RefObject<SVGSVGElement>) {
  const [viewTransform, setViewTransform] = useState<ViewTransform>({
    scale: 1,
    offsetX: 0,
    offsetY: 0,
  });

  // Refs hold "in‑flight" gesture data without causing re‑renders on every mouse move.
  const isPanning = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      // Scroll up = zoom in, scroll down = zoom out.
      const factor = e.deltaY > 0 ? 1 / ZOOM_FACTOR : ZOOM_FACTOR;

      setViewTransform((prev) => {
        const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.scale * factor));
        if (!svgRef.current) return { ...prev, scale: newScale };

        // Keep the point under the cursor fixed while zooming ("zoom to cursor").
        const rect = svgRef.current.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const ratio = newScale / prev.scale;

        return {
          scale: newScale,
          offsetX: mx - (mx - prev.offsetX) * ratio,
          offsetY: my - (my - prev.offsetY) * ratio,
        };
      });
    },
    [svgRef]
  );

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    // Pan with middle mouse, or Alt + left click (keeps left click free for drawing).
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanning.current = true;
      lastMouse.current = { x: e.clientX, y: e.clientY };
      e.preventDefault();
    }
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastMouse.current.x;
    const dy = e.clientY - lastMouse.current.y;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    setViewTransform((prev) => ({
      ...prev,
      offsetX: prev.offsetX + dx,
      offsetY: prev.offsetY + dy,
    }));
  }, []);

  const handleMouseUp = useCallback(() => {
    isPanning.current = false;
  }, []);

  return {
    viewTransform,
    handlers: {
      onWheel: handleWheel,
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
    },
  };
}
```

---

### Part 5, Step 3: Grid — **`src/domains/editor/components/GridLayer.tsx`** (modify)

The grid is one SVG `<pattern>` that tiles itself, so no matter how far the user zooms
or pans there are still only three DOM nodes. It takes the grid size from the store's
snap config so the visual grid always matches where points actually snap.

```typescript
// src/domains/editor/components/GridLayer.tsx

import React from 'react';

interface GridLayerProps {
  /** Grid cell size in world units (cm). */
  gridSize: number;
}

/**
 * Infinite‑looking dotted grid via a tiling <pattern>.
 * The big background <rect> is intentionally huge so the pattern fills the viewport
 * at any pan/zoom. pointerEvents="none" lets clicks pass through to the canvas.
 */
export const GridLayer: React.FC<GridLayerProps> = React.memo(({ gridSize }) => {
  const patternId = 'editor-grid-pattern';
  return (
    <>
      <defs>
        <pattern id={patternId} width={gridSize} height={gridSize} patternUnits="userSpaceOnUse">
          <circle cx={0} cy={0} r={0.5} fill="rgba(255,255,255,0.15)" />
        </pattern>
      </defs>
      <rect
        x={-50000}
        y={-50000}
        width={100000}
        height={100000}
        fill={`url(#${patternId})`}
        pointerEvents="none"
      />
    </>
  );
});

GridLayer.displayName = 'GridLayer';
```

---

### Part 5, Step 4: Walls — **`src/domains/editor/components/WallLayer.tsx`** (new — was missing)

This file was imported by `EditorCanvas` but never written. A wall is stored as a thin
centerline plus a `thickness`; to draw it we turn that into a 4‑corner quad with
`computeWallQuad` (built in Part 3). We read walls through the `useWallSegments` selector
(built in Part 4) so this layer only re‑renders when wall geometry actually changes.

```typescript
// src/domains/editor/components/WallLayer.tsx

import React from 'react';
import { useWallSegments } from '@/store/selectors/editorSelectors';
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
 * Renders every wall as a filled rectangle (quad) computed from its centerline and
 * thickness. Walls are filled — not stroked lines — so corners and thickness read
 * correctly at any zoom.
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
```

---

### Part 5, Step 5: Rooms — **`src/domains/editor/components/RoomLayer.tsx`** (new — was missing)

Rooms are closed polygons referenced by their boundary vertex IDs. We resolve those IDs
to positions, build a polygon path (with the Y‑flip), and tint it by room type using the
color map from Step 1. We read `rooms` and `vertices` straight from the store here — a
room only needs its own vertices, and this keeps us from adding a new selector to the
Part 4 file.

```typescript
// src/domains/editor/components/RoomLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { ROOM_FILL_COLORS } from '../constants';
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
              y={-cy}
              fontSize={16}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="rgba(255,255,255,0.7)"
              pointerEvents="none"
              // Counter the parent zoom a touch so labels stay readable; optional.
            >
              {room.label}
            </text>
          </g>
        );
      })}
    </g>
  );
});

RoomLayer.displayName = 'RoomLayer';
```

---

### Part 5, Step 6: Furniture — **`src/domains/editor/components/FurnitureLayer.tsx`** (new — was missing)

Each furniture item has a world position, a rotation (radians, around the vertical axis),
and a bounding box in centimeters. For the 2D editor we draw a simple labeled rectangle
sized to those bounds and rotated into place — the real GLTF model is a 3D concern (Part 11).

```typescript
// src/domains/editor/components/FurnitureLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';

/**
 * Draws a 2D footprint icon for every furniture item.
 * The SVG transform does three things in order: move to the item's position
 * (Y‑flipped), rotate, then we draw the rect centered on the origin.
 * Rotation is negated because screen Y is flipped relative to world Y, so a
 * counter‑clockwise world rotation is clockwise on screen.
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
```

---

### Part 5, Step 7: Selection — **`src/domains/editor/components/SelectionLayer.tsx`** (new — was missing)

The top layer highlights whatever is selected. It reads `selectedIds` from the store and
draws an amber outline over selected walls and furniture. Because it only subscribes to
the selection list (plus the entities it needs to outline), hovering or selecting does not
disturb the heavier layers below.

```typescript
// src/domains/editor/components/SelectionLayer.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { computeWallQuad } from '../services/geometry';
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
```

---

### Part 5, Step 8: The canvas shell — **`src/domains/editor/components/EditorCanvas.tsx`** (modify)

Now that every layer exists, we compose them. This version handles **rendering, pan/zoom,
and live mouse tracking** (it writes the snapped cursor position into the store so other
parts can read it). Wall‑drawing click handling is intentionally **not** here yet — it
arrives in Part 6, where we extend this same component. This keeps the import graph honest:
`EditorCanvas` only imports things that already exist at this point.

```typescript
// src/domains/editor/components/EditorCanvas.tsx  (Part 5 version — rendering shell)

import React, { useRef, useCallback } from 'react';
import { useAppStore } from '@/store';
import { useEndpoints } from '@/store/selectors/editorSelectors';
import { screenToWorld } from '../services/geometry';
import { applySnapping } from '../hooks/useSnapping';
import { usePanZoom } from '../hooks/usePan';
import { GridLayer } from './GridLayer';
import { RoomLayer } from './RoomLayer';
import { WallLayer } from './WallLayer';
import { FurnitureLayer } from './FurnitureLayer';
import { SelectionLayer } from './SelectionLayer';

/**
 * Composes the SVG layers in z‑order inside a single pan/zoom <g> transform.
 * On mouse move it converts the cursor to world space, snaps it, and stores it as
 * `currentMouseWorld` — the shared "where is the cursor in the model" value used by
 * snapping feedback and (in Part 6) the drawing preview.
 */
export const EditorCanvas: React.FC = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const { viewTransform, handlers } = usePanZoom(svgRef);
  const endpoints = useEndpoints();
  const snapConfig = useAppStore((s) => s.snapConfig);

  // Keep the latest transform in a ref so handleMouseMove doesn't need to be
  // recreated on every pan/zoom frame (avoids re‑binding the SVG listener constantly).
  const viewTransformRef = useRef(viewTransform);
  viewTransformRef.current = viewTransform;

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current) return;
      // Let the pan handler run first (it no‑ops unless a pan gesture is active).
      handlers.onMouseMove(e);

      const rect = svgRef.current.getBoundingClientRect();
      const raw = screenToWorld({ px: e.clientX, py: e.clientY }, rect, viewTransformRef.current);
      const snapped = applySnapping(raw, endpoints, snapConfig);
      // Transient, high‑frequency value: set it directly without an action.
      useAppStore.setState({ currentMouseWorld: snapped });
    },
    [endpoints, snapConfig, handlers]
  );

  return (
    <svg
      ref={svgRef}
      className="w-full h-full bg-neutral-900 cursor-crosshair"
      onMouseMove={handleMouseMove}
      onWheel={handlers.onWheel}
      onMouseDown={handlers.onMouseDown}
      onMouseUp={handlers.onMouseUp}
    >
      <g transform={`translate(${viewTransform.offsetX}, ${viewTransform.offsetY}) scale(${viewTransform.scale})`}>
        <GridLayer gridSize={snapConfig.gridSize} />
        <RoomLayer />
        <WallLayer />
        <FurnitureLayer />
        <SelectionLayer />
      </g>
    </svg>
  );
};
```

**Common mistakes this ordering prevents**

1. Importing a layer component that doesn't exist yet (the original crash).
2. Calling `usePanZoom` before it's defined.
3. Forgetting the Y‑flip in one layer, which silently mirrors only that layer.

---

## PART 6: Wall Drawing System

### How drawing works

Drawing a wall is a tiny state machine: **click once** to set the start point, **click
again** to finish the wall. Optionally, *chain mode* makes the end of one wall the start
of the next so you can draw a connected outline without re‑clicking. While the user moves
the mouse between clicks, a dashed "rubber‑band" preview follows the cursor.

```
 IDLE ──click──▶ DRAWING ──click──▶ commit wall
   ▲                │                   │
   │             Escape          chain? ─┴─▶ start = end (stay DRAWING)
   └────────────────┴───────────────────────▶ back to IDLE
```

There is one subtlety that the original guide got tangled in: when a new wall crosses an
existing wall, the existing wall must be **split** at the crossing so the two share a
vertex (room detection in Part 7 depends on shared vertices). We build that splitting
logic first, as a clean service, then the hook that uses it.

---

### Part 6, Step 1: Wall operations — **`src/domains/editor/services/wallOps.ts`** (modify)

This single file replaces the original's contradictory pair (`findIntersections` with the
wrong signature **and** a `splitWallAtPoint_DEPRECATED` that had a race condition). Here:

- `findWallIntersections` takes the store's `Record<…>` collections directly (matching how
  the hook calls it) and returns crossings sorted along the new wall.
- `splitWallAtPoint` performs the **entire** split inside one `setState` call, so the
  store is never observed in a half‑updated state (this is the atomic fix the original
  deferred to "Part 25").

```typescript
// src/domains/editor/services/wallOps.ts

import type { Point2D, EntityId, Wall, Vertex } from '@/types';
import { useAppStore } from '@/store';
import { generateId } from '@/utils/id';

export interface WallIntersection {
  wallId: EntityId;
  point: Point2D;
  /** Parameter along the NEW wall (0..1), used to order splits start→end. */
  t: number;
}

/**
 * Finds where a proposed segment (newStart → newEnd) crosses existing wall centerlines.
 *
 * Uses the standard parametric segment‑intersection test. For segments A(P1→P2) and
 * B(P3→P4): solve for t (along A) and u (along B). A real crossing exists only when both
 * t and u are strictly inside (0,1) — we exclude the exact endpoints so shared corners
 * aren't mistaken for crossings.
 */
export function findWallIntersections(
  newStart: Point2D,
  newEnd: Point2D,
  walls: Record<EntityId, Wall>,
  vertices: Record<EntityId, Vertex>
): WallIntersection[] {
  const results: WallIntersection[] = [];

  const d1x = newEnd.x - newStart.x;
  const d1y = newEnd.y - newStart.y;

  for (const wall of Object.values(walls)) {
    const sv = vertices[wall.startVertexId];
    const ev = vertices[wall.endVertexId];
    if (!sv || !ev) continue;

    const p3 = sv.position;
    const p4 = ev.position;
    const d2x = p4.x - p3.x;
    const d2y = p4.y - p3.y;

    // 2D cross product of the two directions. ~0 ⇒ parallel ⇒ no single crossing.
    const cross = d1x * d2y - d1y * d2x;
    if (Math.abs(cross) < 1e-10) continue;

    const dx = p3.x - newStart.x;
    const dy = p3.y - newStart.y;
    const t = (dx * d2y - dy * d2x) / cross; // along the new wall
    const u = (dx * d1y - dy * d1x) / cross; // along the existing wall

    const EPS = 1e-6;
    if (t > EPS && t < 1 - EPS && u > EPS && u < 1 - EPS) {
      results.push({
        wallId: wall.id,
        point: { x: newStart.x + t * d1x, y: newStart.y + t * d1y },
        t,
      });
    }
  }

  // Process splits in order along the new wall so topology stays consistent.
  return results.sort((a, b) => a.t - b.t);
}

/**
 * Splits an existing wall at `point`, atomically.
 *
 * Topology change: one wall A→B becomes A→V and V→B, where V is a brand‑new vertex at
 * `point`. The shared vertex V is what lets a later wall connect cleanly, which is the
 * prerequisite for room detection.
 *
 * Everything happens inside a SINGLE setState() so no subscriber ever sees a wall that
 * points at a vertex that doesn't exist yet.
 *
 * @returns the new vertex id, or '' if the wall was not found.
 */
export function splitWallAtPoint(wallId: EntityId, point: Point2D): EntityId {
  const newVertexId = generateId('vertex');
  let ok = false;

  useAppStore.setState((draft) => {
    const original = draft.walls[wallId];
    if (!original) return; // nothing to split

    const originalEndVertexId = original.endVertexId;

    // 1. Create the junction vertex.
    draft.vertices[newVertexId] = {
      id: newVertexId,
      position: point,
      connectedWalls: [],
    };

    // 2. Shorten the original wall so it now ends at the junction.
    original.endVertexId = newVertexId;

    // 3. Create the second half, inheriting thickness/height/material from the original.
    const newWallId = generateId('wall');
    draft.walls[newWallId] = {
      ...original,
      id: newWallId,
      startVertexId: newVertexId,
      endVertexId: originalEndVertexId,
    };

    // 4. Fix up connectivity so the graph stays correct.
    draft.vertices[newVertexId].connectedWalls = [wallId, newWallId];
    const endVertex = draft.vertices[originalEndVertexId];
    if (endVertex) {
      const idx = endVertex.connectedWalls.indexOf(wallId);
      if (idx !== -1) endVertex.connectedWalls[idx] = newWallId;
    }

    ok = true;
  });

  return ok ? newVertexId : '';
}

/**
 * Returns the angles (radians) of every wall meeting at a vertex, sorted ascending.
 * Used later for mitered corner rendering. Pure — safe to call anywhere.
 */
export function computeCornerAngles(
  vertexId: EntityId,
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): number[] {
  const vertex = vertices[vertexId];
  if (!vertex || vertex.connectedWalls.length < 2) return [];

  return vertex.connectedWalls
    .map((wallId) => {
      const wall = walls[wallId];
      const otherId = wall.startVertexId === vertexId ? wall.endVertexId : wall.startVertexId;
      const other = vertices[otherId];
      if (!other) return 0;
      return Math.atan2(other.position.y - vertex.position.y, other.position.x - vertex.position.x);
    })
    .sort((a, b) => a - b);
}
```

---

### Part 6, Step 2: The drawing hook — **`src/domains/editor/hooks/useWallDrawing.ts`** (modify)

This replaces the original `useDrawing.ts`. It keeps the start point in React state (so the
preview can react to it) and, on the second click, splits any crossed walls **before**
adding the new wall. Note the consistent naming — it calls `findWallIntersections` and
`splitWallAtPoint`, the exact functions we just defined (the original called names that
didn't exist).

```typescript
// src/domains/editor/hooks/useWallDrawing.ts

import { useState, useCallback } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types';
import { findWallIntersections, splitWallAtPoint } from '../services/wallOps';

const MIN_WALL_LENGTH_SQ = 1; // reject sub‑1cm walls (squared, so 1 = 1cm²)

export function useWallDrawing() {
  // The pending start point. null ⇒ we're idle (no wall in progress).
  const [drawStart, setDrawStart] = useState<Point2D | null>(null);
  const [chainMode, setChainMode] = useState(false);

  /** Call this with a SNAPPED world point on each editor click. */
  const handleClick = useCallback(
    (worldPos: Point2D) => {
      // First click: remember where the wall starts.
      if (!drawStart) {
        setDrawStart(worldPos);
        return;
      }

      // Second click: finish the wall.
      const start = drawStart;
      const end = worldPos;
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      if (dx * dx + dy * dy < MIN_WALL_LENGTH_SQ) return; // ignore accidental tiny walls

      // Read FRESH state (not a stale closure) for accurate intersection tests.
      const { walls, vertices, addWall } = useAppStore.getState();

      // Split every existing wall this new wall crosses, in order along the new wall.
      const crossings = findWallIntersections(start, end, walls, vertices);
      for (const c of crossings) {
        splitWallAtPoint(c.wallId, c.point);
      }

      // Add the new wall (the store action finds/creates shared vertices for us).
      addWall(start, end);

      // Chain mode keeps drawing from the point we just placed; otherwise go idle.
      setDrawStart(chainMode ? end : null);
    },
    [drawStart, chainMode]
  );

  /** Cancel the in‑progress wall (e.g. on Escape). */
  const cancel = useCallback(() => setDrawStart(null), []);

  return { drawStart, chainMode, setChainMode, handleClick, cancel };
}
```

---

### Part 6, Step 3: Rubber‑band preview — **`src/domains/editor/components/DrawingPreview.tsx`** (new — was missing)

`EditorCanvas` imported a `DrawingPreview` that never existed. Here it is. It draws a dashed
line from the pending start point to the live (snapped) cursor, plus a dot at each end so
the user sees exactly where the wall will land. It reads the cursor from the store's
`currentMouseWorld` and receives the start point as a prop from the hook.

```typescript
// src/domains/editor/components/DrawingPreview.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { EDITOR_STYLE } from '../constants';
import type { Point2D } from '@/types/geometry';

interface DrawingPreviewProps {
  /** The pending wall start point, or null when no wall is in progress. */
  start: Point2D | null;
}

/**
 * The live "what you're about to draw" line. Renders nothing until a start point exists
 * and the cursor is inside the canvas. Remember the Y‑flip: world Y up → SVG draws at -y.
 */
export const DrawingPreview: React.FC<DrawingPreviewProps> = ({ start }) => {
  const cursor = useAppStore((s) => s.currentMouseWorld);
  if (!start || !cursor) return null;

  return (
    <g className="drawing-preview" pointerEvents="none">
      <line
        x1={start.x}
        y1={-start.y}
        x2={cursor.x}
        y2={-cursor.y}
        stroke={EDITOR_STYLE.previewStroke}
        strokeWidth={EDITOR_STYLE.previewStrokeWidth}
        strokeDasharray={EDITOR_STYLE.previewDash}
      />
      <circle cx={start.x} cy={-start.y} r={EDITOR_STYLE.vertexRadius} fill={EDITOR_STYLE.previewStroke} />
      <circle cx={cursor.x} cy={-cursor.y} r={EDITOR_STYLE.vertexRadius} fill={EDITOR_STYLE.previewStroke} />
    </g>
  );
};
```

---

### Part 6, Step 4: Wire drawing into the canvas — **`src/domains/editor/components/EditorCanvas.tsx`** (modify)

Finally we extend the Part 5 canvas. Two additions: (1) use `useWallDrawing` and call its
`handleClick` with the already‑snapped cursor on click, and (2) render `DrawingPreview`
(passing the hook's `drawStart`) when the wall tool is active. `activeTool` comes from the
UI slice built in Part 4. We keep an `onClick` separate from the pan handlers so panning
(Alt/middle‑drag) never places a wall.

```typescript
// src/domains/editor/components/EditorCanvas.tsx  (Part 6 version — adds drawing)

import React, { useRef, useCallback, useEffect } from 'react';
import { useAppStore } from '@/store';
import { useEndpoints } from '@/store/selectors/editorSelectors';
import { screenToWorld } from '../services/geometry';
import { applySnapping } from '../hooks/useSnapping';
import { usePanZoom } from '../hooks/usePan';
import { useWallDrawing } from '../hooks/useWallDrawing';
import { GridLayer } from './GridLayer';
import { RoomLayer } from './RoomLayer';
import { WallLayer } from './WallLayer';
import { FurnitureLayer } from './FurnitureLayer';
import { SelectionLayer } from './SelectionLayer';
import { DrawingPreview } from './DrawingPreview';

export const EditorCanvas: React.FC = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const { viewTransform, handlers } = usePanZoom(svgRef);
  const endpoints = useEndpoints();
  const snapConfig = useAppStore((s) => s.snapConfig);
  const activeTool = useAppStore((s) => s.activeTool); // from the UI slice (Part 4)

  const { drawStart, handleClick, cancel } = useWallDrawing();

  const viewTransformRef = useRef(viewTransform);
  viewTransformRef.current = viewTransform;

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current) return;
      handlers.onMouseMove(e);
      const rect = svgRef.current.getBoundingClientRect();
      const raw = screenToWorld({ px: e.clientX, py: e.clientY }, rect, viewTransformRef.current);
      const snapped = applySnapping(raw, endpoints, snapConfig);
      useAppStore.setState({ currentMouseWorld: snapped });
    },
    [endpoints, snapConfig, handlers]
  );

  // A plain left click while the wall tool is active places a point. We reuse the
  // already‑snapped cursor that handleMouseMove stored, so click and preview agree.
  const handleSvgClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (activeTool !== 'wall') return;
      if (e.button !== 0 || e.altKey) return; // ignore pan gestures
      const cursor = useAppStore.getState().currentMouseWorld;
      if (cursor) handleClick(cursor);
    },
    [activeTool, handleClick]
  );

  // Escape cancels the in‑progress wall.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [cancel]);

  return (
    <svg
      ref={svgRef}
      className="w-full h-full bg-neutral-900 cursor-crosshair"
      onMouseMove={handleMouseMove}
      onWheel={handlers.onWheel}
      onMouseDown={handlers.onMouseDown}
      onMouseUp={handlers.onMouseUp}
      onClick={handleSvgClick}
    >
      <g transform={`translate(${viewTransform.offsetX}, ${viewTransform.offsetY}) scale(${viewTransform.scale})`}>
        <GridLayer gridSize={snapConfig.gridSize} />
        <RoomLayer />
        <WallLayer />
        <FurnitureLayer />
        <SelectionLayer />
        {activeTool === 'wall' && <DrawingPreview start={drawStart} />}
      </g>
    </svg>
  );
};
```

**Common mistakes this ordering prevents**

1. Calling `findIntersectionsPure` / `splitWallAtPoint` before they exist or under the
   wrong name (the original's dangling references).
2. Splitting walls in a non‑atomic way, letting a subscriber render a wall whose vertex
   isn't in the store yet.
3. Letting a pan gesture also drop a wall (guarded by the `altKey` / button checks).

---

## PART 7: Room Detection

### The idea in plain terms

Walls and their shared vertices form a graph. A "room" is the smallest loop of walls that
encloses an area. Finding those loops is a classic computational‑geometry task: at every
junction, always take the **sharpest left turn**, and you will trace exactly one enclosed
face. Do that from every edge, skip loops you've already traced, and throw away the single
loop that wraps the *outside* of the building (it winds the opposite way, which we detect
with a signed‑area test).

This part has two pieces: the pure `roomDetection.ts` algorithm (no React, easy to test),
and a small `useRoomDetection` hook that **runs** it whenever the walls change and writes
the result into the store. That hook is the missing link — in the original guide
`detectRooms` was written but **nothing ever called it**, so rooms never appeared.

---

### Part 7, Step 1: Detection algorithm — **`src/domains/editor/services/roomDetection.ts`** (modify)

A pure module: give it the `vertices` and `walls` records, get back an array of `Room`s.
Keeping it pure means Part 18's tests can call it with plain objects and assert on the
output — no store, no rendering.

```typescript
// src/domains/editor/services/roomDetection.ts

import type { EntityId, Vertex, Wall, Room, Point2D } from '@/types';
import { generateId } from '@/utils/id';

interface DirectedEdge {
  wallId: EntityId;
  fromVertexId: EntityId;
  toVertexId: EntityId;
}

/**
 * Finds all rooms (minimal enclosed loops) in the wall graph.
 *
 * Every wall becomes two directed edges (one per direction). Starting from each unused
 * directed edge we trace a loop using the "smallest counter‑clockwise turn" rule, which
 * is the standard way to extract faces from a planar graph. Interior loops come out
 * wound counter‑clockwise (positive signed area); the lone exterior loop is clockwise
 * (negative) and is discarded.
 */
export function detectRooms(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): Room[] {
  const rooms: Room[] = [];
  const visitedEdges = new Set<string>();

  // Build both directed edges for every wall.
  const directedEdges: DirectedEdge[] = [];
  for (const wall of Object.values(walls)) {
    directedEdges.push({ wallId: wall.id, fromVertexId: wall.startVertexId, toVertexId: wall.endVertexId });
    directedEdges.push({ wallId: wall.id, fromVertexId: wall.endVertexId, toVertexId: wall.startVertexId });
  }

  for (const startEdge of directedEdges) {
    const key = `${startEdge.fromVertexId}->${startEdge.toVertexId}`;
    if (visitedEdges.has(key)) continue;

    const cycle = traceCycle(startEdge, vertices, directedEdges);
    if (!cycle) continue;

    // Mark every directed edge of this loop as used so we don't trace it again.
    for (let i = 0; i < cycle.length; i++) {
      const from = cycle[i];
      const to = cycle[(i + 1) % cycle.length];
      visitedEdges.add(`${from}->${to}`);
    }

    // Positive area ⇒ interior face ⇒ a real room. Negative ⇒ exterior boundary ⇒ skip.
    const polygon = cycle.map((vid) => vertices[vid].position);
    if (computeSignedArea(polygon) > 0) {
      rooms.push({
        id: generateId('room'),
        boundaryVertexIds: cycle,
        roomType: 'custom',
        label: `Room ${rooms.length + 1}`,
        floorMaterialId: 'default-floor',
      });
    }
  }

  return rooms;
}

/**
 * Traces one loop by always taking the smallest CCW turn at each vertex.
 * Returns the ordered vertex IDs of the loop, or null if it dead‑ends or runs too long
 * (the length cap guards against infinite loops on malformed graphs).
 */
function traceCycle(
  startEdge: DirectedEdge,
  vertices: Record<EntityId, Vertex>,
  allEdges: DirectedEdge[]
): EntityId[] | null {
  const MAX_CYCLE_LENGTH = 100;
  const cycle: EntityId[] = [startEdge.fromVertexId];

  let currentFrom = startEdge.fromVertexId;
  let currentTo = startEdge.toVertexId;

  for (let step = 0; step < MAX_CYCLE_LENGTH; step++) {
    // Closed the loop back to the start?
    if (currentTo === startEdge.fromVertexId) {
      return cycle.length >= 3 ? cycle : null;
    }
    cycle.push(currentTo);

    // Direction we arrived from, measured at the current vertex.
    const incomingAngle = Math.atan2(
      vertices[currentFrom].position.y - vertices[currentTo].position.y,
      vertices[currentFrom].position.x - vertices[currentTo].position.x
    );

    // All ways out of currentTo except straight back where we came from.
    const outgoing = allEdges.filter((e) => e.fromVertexId === currentTo && e.toVertexId !== currentFrom);
    if (outgoing.length === 0) return null; // dead end

    // Pick the outgoing edge with the smallest counter‑clockwise turn.
    let bestEdge: DirectedEdge | null = null;
    let bestAngle = Infinity;
    for (const edge of outgoing) {
      const outAngle = Math.atan2(
        vertices[edge.toVertexId].position.y - vertices[currentTo].position.y,
        vertices[edge.toVertexId].position.x - vertices[currentTo].position.x
      );
      let rel = outAngle - incomingAngle;
      while (rel <= 0) rel += Math.PI * 2; // normalize into (0, 2π]
      while (rel > Math.PI * 2) rel -= Math.PI * 2;
      if (rel < bestAngle) {
        bestAngle = rel;
        bestEdge = edge;
      }
    }
    if (!bestEdge) return null;

    currentFrom = currentTo;
    currentTo = bestEdge.toVertexId;
  }

  return null; // exceeded the safety cap
}

/**
 * Signed polygon area via the shoelace formula.
 * Positive ⇒ counter‑clockwise winding, negative ⇒ clockwise.
 */
export function computeSignedArea(polygon: Point2D[]): number {
  let area = 0;
  const n = polygon.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += polygon[i].x * polygon[j].y - polygon[j].x * polygon[i].y;
  }
  return area / 2;
}

/** Validates a candidate room polygon: ≥3 vertices, non‑degenerate, non‑self‑intersecting. */
export function validateRoomPolygon(vertexIds: EntityId[], vertices: Record<EntityId, Vertex>): boolean {
  if (vertexIds.length < 3) return false;
  const polygon = vertexIds.map((id) => vertices[id]?.position).filter((p): p is Point2D => Boolean(p));
  if (polygon.length < 3) return false;
  if (Math.abs(computeSignedArea(polygon)) < 1) return false; // < 1 cm² is degenerate
  return !hasSelfIntersection(polygon);
}

function hasSelfIntersection(polygon: Point2D[]): boolean {
  const n = polygon.length;
  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue; // adjacent edges legitimately share a vertex
      if (segmentsIntersect(polygon[i], polygon[(i + 1) % n], polygon[j], polygon[(j + 1) % n])) {
        return true;
      }
    }
  }
  return false;
}

function segmentsIntersect(a1: Point2D, a2: Point2D, b1: Point2D, b2: Point2D): boolean {
  const d1x = a2.x - a1.x, d1y = a2.y - a1.y;
  const d2x = b2.x - b1.x, d2y = b2.y - b1.y;
  const cross = d1x * d2y - d1y * d2x;
  if (Math.abs(cross) < 1e-10) return false;
  const dx = b1.x - a1.x, dy = b1.y - a1.y;
  const t = (dx * d2y - dy * d2x) / cross;
  const u = (dx * d1y - dy * d1x) / cross;
  const EPS = 1e-6;
  return t > EPS && t < 1 - EPS && u > EPS && u < 1 - EPS;
}
```

---

### Part 7, Step 2: Run detection automatically — **`src/domains/editor/hooks/useRoomDetection.ts`** (new — closes the orphan)

The algorithm above does nothing until something calls it. This hook watches the walls and
vertices in the store and, whenever they change, recomputes rooms and writes them back via
the `setRooms` action (built in Part 4). It **preserves** the `roomType`, `label`, and
floor material a user previously assigned by matching the new loops to the old ones by
their set of boundary vertices — so re‑running detection after an edit doesn't wipe the
user's "this is the kitchen" choice.

```typescript
// src/domains/editor/hooks/useRoomDetection.ts

import { useEffect } from 'react';
import { useAppStore } from '@/store';
import type { EntityId, Room } from '@/types';
import { detectRooms } from '../services/roomDetection';

/** A stable key for a loop, independent of which vertex it starts at or its direction. */
function boundaryKey(vertexIds: readonly EntityId[]): string {
  return [...vertexIds].sort().join('|');
}

/**
 * Recomputes rooms whenever wall geometry changes and merges in any user‑set metadata
 * from rooms that occupy the same boundary. Mount this once, high in the editor tree
 * (e.g. inside the editor screen). It renders nothing.
 */
export function useRoomDetection(): void {
  const walls = useAppStore((s) => s.walls);
  const vertices = useAppStore((s) => s.vertices);

  useEffect(() => {
    const detected = detectRooms(vertices, walls);

    // Index existing rooms by boundary so we can carry over user choices.
    const previous = useAppStore.getState().rooms;
    const previousByBoundary = new Map<string, Room>();
    for (const room of Object.values(previous)) {
      previousByBoundary.set(boundaryKey(room.boundaryVertexIds), room);
    }

    const next: Record<EntityId, Room> = {};
    for (const room of detected) {
      const prior = previousByBoundary.get(boundaryKey(room.boundaryVertexIds));
      const merged = prior
        ? { ...room, id: prior.id, roomType: prior.roomType, label: prior.label, floorMaterialId: prior.floorMaterialId }
        : room;
      next[merged.id] = merged;
    }

    useAppStore.getState().setRooms(next);
    // Re‑run only when the geometry references change. Zustand gives us stable refs
    // unless walls/vertices actually changed, so this won't loop.
  }, [walls, vertices]);
}
```

> **Where to mount it.** Add `useRoomDetection();` at the top of whatever component hosts
> the editor (for example a `EditorScreen` that renders `<EditorCanvas />`). It has no UI,
> so it just needs to be alive while the editor is on screen. The detected rooms then flow
> automatically into `RoomLayer` (Part 5) and, later, the 3D floors and Vastu analysis.

**Common mistakes this ordering prevents**

1. Writing `detectRooms` but never calling it (rooms silently never appear).
2. Overwriting user‑assigned room types every time a wall moves.
3. An effect that depends on freshly‑built objects each render and loops forever — here we
   depend on the store's stable `walls`/`vertices` references instead.

---

## End of Installment 1 (Parts 5–7: the complete 2D editor pipeline)

At this point the 2D editor is fully wired and internally consistent: constants → pan/zoom
→ five render layers → canvas shell → drawing service → drawing hook → preview → canvas
wiring → room detection → the hook that runs it. Every import resolves to a file that was
created in an earlier step, and the two original dangling references
(`findIntersectionsPure`, `splitWallAtPoint_DEPRECATED`) are gone.

**Next installments will continue in this exact format:**

- **Installment 2 — 3D foundation (Parts 8–11):** `ViewerCanvas` → `SceneEnvironment` →
  `transform.ts` (confirm `planTo3D`) → `extrusion.ts` → `materials.ts` → `WallMesh` →
  `FloorMesh` → `useAssetLoader` → `FurnitureModel` → `SceneContent` (assembled last).
- **Installment 3 — Interaction & analysis (Parts 12–15):** collision, camera rigs, the
  Vastu math chain (`vectors` → `brahmasthan` → `zones` → `scoring`), then the 2D/3D
  overlays.
- **Installment 4 — Hardening & delivery (Parts 16–31):** barrels/event bus, performance,
  error boundaries, undo/redo, persistence, accessibility, validation, loading states,
  touch input, and the test suites — each with its missing files created and ordered.

## Installment 2 — 3D Foundation (Parts 8–11)

The original 3D chapters were ordered top‑down: `ViewerCanvas` and `SceneContent` came
first and reached "down" for components that didn't exist yet (`FloorMesh`, a `useMaterial`
hook), imported things from the wrong path (`FurnitureInstances`), and pulled in
`CameraController` (Part 13) and `VastuOverlay3D` (Part 15) before those parts. We flip the
order: build every leaf mesh and its helpers first, then assemble `SceneContent`, then the
`ViewerCanvas` last. The camera rig and Vastu overlay are deliberately left as a temporary
`OrbitControls` and an absent overlay until their own installments slot in.

---

## PART 8: React Three Fiber — Lighting (the one leaf with no dependencies)

### Why this comes first

`react-three-fiber` (R3F) lets us describe a Three.js scene with JSX. The scene needs
light before anything is visible, and the lighting component imports nothing from our own
code — so it is the safe first brick. The `ViewerCanvas` and `SceneContent` that the
original guide led with are built at the **end** of this installment, once their children
exist.

### Part 8, Step 1: Scene lighting — **`src/domains/viewer/components/SceneEnvironment.tsx`** (new)

```typescript
// src/domains/viewer/components/SceneEnvironment.tsx

import React from 'react';
import { Environment, ContactShadows } from '@react-three/drei';

/**
 * All the lighting for the 3D view, in one place.
 *
 * - Environment (HDRI) gives soft, realistic ambient reflections.
 * - A single directional light acts as the sun and casts shadows. It is placed in the
 *   east/high position (positive X, high Y) — the Vastu‑ideal morning‑sun direction.
 * - Hemisphere + ambient lights lift the shadows so they never go pure black.
 * - ContactShadows draws soft contact darkening under objects so they feel grounded.
 */
export const SceneEnvironment: React.FC = () => {
  return (
    <>
      <Environment preset="apartment" background={false} />

      <directionalLight
        position={[15, 20, 10]}
        intensity={1.5}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-far={50}
        shadow-camera-left={-20}
        shadow-camera-right={20}
        shadow-camera-top={20}
        shadow-camera-bottom={-20}
        shadow-bias={-0.0001}
      />

      <hemisphereLight args={['#b1e1ff', '#b97a20', 0.3]} />
      <ambientLight intensity={0.2} />

      <ContactShadows position={[0, 0.01, 0]} opacity={0.4} scale={40} blur={2} far={4} />
    </>
  );
};
```

---

## PART 9: 2D → 3D Coordinate Transformation — **`src/domains/viewer/services/transform.ts`** (exists — confirm)

### Why this is just a confirmation

This file already exists from the foundation (it is the canonical home of `planTo3D`,
which Part 2's editor `geometry.ts` re‑exports as `world2DTo3D`). Every 3D mesh below
depends on it, so it must be in place before Part 10. Confirm it matches the contract
below; if your repo's copy differs, align it to this.

```typescript
// src/domains/viewer/services/transform.ts

import type { Point2D, Point3D } from '@/types/geometry';
import * as THREE from 'three';

const CM_TO_M = 0.01;

/**
 * The core mapping: a 2D plan point (centimeters, Y‑up/north) → a 3D world point
 * (meters). 2D‑Y becomes 3D‑(−Z) so "north on the plan" stays "north in 3D" while
 * keeping Three.js's right‑handed system. `elevationCm` lifts the point onto the Y axis
 * (floors at 0, wall tops at the wall height, etc.).
 */
export function planTo3D(point: Point2D, elevationCm = 0): Point3D {
  return { x: point.x * CM_TO_M, y: elevationCm * CM_TO_M, z: -point.y * CM_TO_M };
}

/** Inverse of planTo3D (drops the vertical/elevation component). */
export function threeDToPlan(point: Point3D): Point2D {
  const M_TO_CM = 1 / CM_TO_M;
  return { x: point.x * M_TO_CM, y: -point.z * M_TO_CM };
}

/** Convenience: a Three.js Vector3 straight from a plan point. */
export function planToVec3(point: Point2D, elevationCm = 0): THREE.Vector3 {
  return new THREE.Vector3(point.x * CM_TO_M, elevationCm * CM_TO_M, -point.y * CM_TO_M);
}

/**
 * Builds a THREE.Shape from a room polygon, in meters.
 *
 * The shape is created in its own 2D space using (x, y). When the resulting mesh is laid
 * flat with rotation [-π/2, 0, 0], a shape point (x, y) lands at world (x, 0, −y) — which
 * is exactly what planTo3D produces. So floors built this way line up perfectly with walls.
 */
export function polygonToShape(vertices: Point2D[]): THREE.Shape {
  const shape = new THREE.Shape();
  if (vertices.length === 0) return shape;
  shape.moveTo(vertices[0].x * CM_TO_M, vertices[0].y * CM_TO_M);
  for (let i = 1; i < vertices.length; i++) {
    shape.lineTo(vertices[i].x * CM_TO_M, vertices[i].y * CM_TO_M);
  }
  shape.closePath();
  return shape;
}
```

> **Centering tip.** Floating‑point precision degrades far from the origin, so keep the
> plan centered near (0,0). The store's editor model is already centered, so no extra work
> is needed here — just don't translate the whole plan thousands of meters away.

---

## PART 10: Wall & Floor Meshes

We build the geometry generator, the shared‑material system, the tiny `useMaterial` hook
(which the original `WallMesh` imported but no one ever wrote), then the two mesh
components. Order: `extrusion.ts` → `materials.ts` → `useMaterial.ts` → `WallMesh.tsx` →
`FloorMesh.tsx`.

### Part 10, Step 1: Wall geometry — **`src/domains/viewer/services/extrusion.ts`** (new)

A wall is a centerline plus a thickness and height. We hand‑build a box from 8 corners
(rather than using `BoxGeometry` + rotation, which causes Z‑fighting where angled walls
meet) so corners line up exactly with their neighbors.

```typescript
// src/domains/viewer/services/extrusion.ts

import * as THREE from 'three';
import type { Point2D } from '@/types/geometry';

const CM_TO_M = 0.01;

/**
 * Builds a BufferGeometry for one wall: a rectangular prism standing on the ground,
 * long axis along the wall, with correct per‑face normals and UVs for texturing.
 */
export function createWallGeometry(
  start: Point2D,
  end: Point2D,
  thicknessCm: number,
  heightCm: number
): THREE.BufferGeometry {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  if (length < 0.01) return new THREE.BufferGeometry(); // skip degenerate walls

  // 2D perpendicular unit vector — offsets the centerline to the two wall faces.
  const nx = -dy / length;
  const ny = dx / length;
  const halfThick = thicknessCm / 2;
  const h = heightCm;

  const corners2D = {
    startLeft: { x: start.x + nx * halfThick, y: start.y + ny * halfThick },
    startRight: { x: start.x - nx * halfThick, y: start.y - ny * halfThick },
    endLeft: { x: end.x + nx * halfThick, y: end.y + ny * halfThick },
    endRight: { x: end.x - nx * halfThick, y: end.y - ny * halfThick },
  };

  // Convert each corner to 3D (meters). Bottom at y=0, top at y=height. 2D‑Y → 3D‑(−Z).
  const v = {
    bsl: [corners2D.startLeft.x * CM_TO_M, 0, -corners2D.startLeft.y * CM_TO_M],
    bsr: [corners2D.startRight.x * CM_TO_M, 0, -corners2D.startRight.y * CM_TO_M],
    bel: [corners2D.endLeft.x * CM_TO_M, 0, -corners2D.endLeft.y * CM_TO_M],
    ber: [corners2D.endRight.x * CM_TO_M, 0, -corners2D.endRight.y * CM_TO_M],
    tsl: [corners2D.startLeft.x * CM_TO_M, h * CM_TO_M, -corners2D.startLeft.y * CM_TO_M],
    tsr: [corners2D.startRight.x * CM_TO_M, h * CM_TO_M, -corners2D.startRight.y * CM_TO_M],
    tel: [corners2D.endLeft.x * CM_TO_M, h * CM_TO_M, -corners2D.endLeft.y * CM_TO_M],
    ter: [corners2D.endRight.x * CM_TO_M, h * CM_TO_M, -corners2D.endRight.y * CM_TO_M],
  };

  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  let vertexOffset = 0;

  // Adds one quad (4 verts, 2 triangles) with a flat normal and simple UVs.
  function addFace(p0: number[], p1: number[], p2: number[], p3: number[], normal: number[], uW: number, uH: number) {
    positions.push(...p0, ...p1, ...p2, ...p3);
    normals.push(...normal, ...normal, ...normal, ...normal);
    uvs.push(0, 0, uW, 0, uW, uH, 0, uH);
    indices.push(vertexOffset, vertexOffset + 1, vertexOffset + 2, vertexOffset, vertexOffset + 2, vertexOffset + 3);
    vertexOffset += 4;
  }

  const lenM = length * CM_TO_M;
  const hM = h * CM_TO_M;
  const thickM = thicknessCm * CM_TO_M;

  addFace(v.bsl, v.bel, v.tel, v.tsl, [nx, 0, -ny], lenM, hM);            // left face
  addFace(v.ber, v.bsr, v.tsr, v.ter, [-nx, 0, ny], lenM, hM);           // right face
  addFace(v.bsr, v.bsl, v.tsl, v.tsr, [-dx / length, 0, dy / length], thickM, hM); // start cap
  addFace(v.bel, v.ber, v.ter, v.tel, [dx / length, 0, -dy / length], thickM, hM); // end cap
  addFace(v.tsl, v.tel, v.ter, v.tsr, [0, 1, 0], lenM, thickM);          // top
  addFace(v.bsr, v.ber, v.bel, v.bsl, [0, -1, 0], lenM, thickM);         // bottom

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  return geometry;
}
```

### Part 10, Step 2: Shared materials — **`src/domains/viewer/services/materials.ts`** (new)

Materials are expensive to upload to the GPU, so we create each one **once** and hand back
the same instance every time. This cache is what keeps 200 walls from creating 200
identical materials.

```typescript
// src/domains/viewer/services/materials.ts

import * as THREE from 'three';

const materialCache = new Map<string, THREE.Material>();

/** Factory per material id. Add new surfaces here. */
export const MATERIAL_DEFINITIONS: Record<string, () => THREE.Material> = {
  'default-wall': () => new THREE.MeshStandardMaterial({ color: '#f5f0e8', roughness: 0.9, metalness: 0 }),
  'brick-wall': () => new THREE.MeshStandardMaterial({ color: '#c4593a', roughness: 0.85, metalness: 0 }),
  'default-floor': () => new THREE.MeshStandardMaterial({ color: '#d4c5a9', roughness: 0.7, metalness: 0 }),
  'tile-floor': () => new THREE.MeshStandardMaterial({ color: '#e8e0d0', roughness: 0.4, metalness: 0.1 }),
};

/** Returns the one shared material instance for an id (falls back to default‑wall). */
export function getMaterial(materialId: string): THREE.Material {
  const cached = materialCache.get(materialId);
  if (cached) return cached;
  const factory = MATERIAL_DEFINITIONS[materialId] ?? MATERIAL_DEFINITIONS['default-wall'];
  const material = factory();
  materialCache.set(materialId, material);
  return material;
}
```

### Part 10, Step 3: Material hook — **`src/domains/viewer/hooks/useMaterial.ts`** (new — was missing)

`WallMesh` in the original guide imported `useMaterial` from `../hooks/useMaterial`, but
that file never existed (only the `getMaterial` function did). Here is the missing hook —
a thin, memoized wrapper so components can grab a shared material by id.

```typescript
// src/domains/viewer/hooks/useMaterial.ts

import { useMemo } from 'react';
import type * as THREE from 'three';
import { getMaterial } from '../services/materials';

/** Returns the cached material for an id, stable across re‑renders. */
export function useMaterial(materialId: string): THREE.Material {
  return useMemo(() => getMaterial(materialId), [materialId]);
}
```

### Part 10, Step 4: Wall mesh — **`src/domains/viewer/components/WallMesh.tsx`** (new)

Now `WallMesh` has everything it imports. Geometry is memoized so it only rebuilds when a
wall's dimensions change; the material is shared via the hook.

```typescript
// src/domains/viewer/components/WallMesh.tsx

import React, { useMemo } from 'react';
import { createWallGeometry } from '../services/extrusion';
import { useMaterial } from '../hooks/useMaterial';
import type { Point2D } from '@/types/geometry';

interface WallMeshProps {
  start: Point2D;
  end: Point2D;
  thickness: number;
  height: number;
  materialId: string;
}

export const WallMesh: React.FC<WallMeshProps> = React.memo(
  ({ start, end, thickness, height, materialId }) => {
    const geometry = useMemo(
      () => createWallGeometry(start, end, thickness, height),
      [start.x, start.y, end.x, end.y, thickness, height]
    );
    const material = useMaterial(materialId);
    return <mesh geometry={geometry} material={material} castShadow receiveShadow />;
  }
);

WallMesh.displayName = 'WallMesh';
```

### Part 10, Step 5: Floor mesh — **`src/domains/viewer/components/FloorMesh.tsx`** (new — was missing)

`SceneContent` imported a `FloorMesh` that was never written. A floor is just a room
polygon turned into a flat shape (via `polygonToShape`) and laid down with the
`[-π/2, 0, 0]` rotation that we proved aligns shapes with `planTo3D`.

```typescript
// src/domains/viewer/components/FloorMesh.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { polygonToShape } from '../services/transform';
import { useMaterial } from '../hooks/useMaterial';
import type { Point2D } from '@/types/geometry';

interface FloorMeshProps {
  /** Room boundary in 2D plan coordinates (cm). */
  polygon: Point2D[];
  materialId: string;
}

export const FloorMesh: React.FC<FloorMeshProps> = React.memo(({ polygon, materialId }) => {
  // Rebuild only when the polygon actually changes. We key the memo on a compact string
  // of the coordinates so a new array with identical points doesn't force a rebuild.
  const geometry = useMemo(() => {
    if (polygon.length < 3) return new THREE.BufferGeometry();
    return new THREE.ShapeGeometry(polygonToShape(polygon));
  }, [polygon.map((p) => `${p.x},${p.y}`).join(';')]); // eslint-disable-line react-hooks/exhaustive-deps

  const material = useMaterial(materialId);
  if (polygon.length < 3) return null;

  // Rotate the XY shape flat onto the ground; sit a hair above 0 to avoid z‑fighting
  // with the ground plane.
  return (
    <mesh geometry={geometry} material={material} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, 0]} receiveShadow />
  );
});

FloorMesh.displayName = 'FloorMesh';
```

---

## PART 11: Furniture

We load GLTF models and render one per placed item. Order: the loader/catalog hook first,
then the renderer that uses it.

### Part 11, Step 1: Asset loader & catalog — **`src/domains/viewer/hooks/useAssetLoader.ts`** (new)

```typescript
// src/domains/viewer/hooks/useAssetLoader.ts

import { useGLTF } from '@react-three/drei';
import { useMemo } from 'react';
import * as THREE from 'three';

/** Maps a catalog id to its model file, base scale, and vertical offset. */
export const FURNITURE_CATALOG: Record<string, { path: string; scale: number; yOffset: number }> = {
  'sofa-3seat': { path: '/models/sofa-3seat.glb', scale: 0.01, yOffset: 0 },
  'dining-table': { path: '/models/dining-table.glb', scale: 0.01, yOffset: 0 },
  'bed-queen': { path: '/models/bed-queen.glb', scale: 0.01, yOffset: 0 },
  'chair-office': { path: '/models/chair-office.glb', scale: 0.01, yOffset: 0 },
  'toilet': { path: '/models/toilet.glb', scale: 0.01, yOffset: 0 },
  'kitchen-counter': { path: '/models/kitchen-counter.glb', scale: 0.01, yOffset: 0 },
};

/** Warm the cache for commonly used models so first placement isn't laggy. */
export function preloadCommonModels(): void {
  for (const id of ['sofa-3seat', 'dining-table', 'bed-queen']) {
    const entry = FURNITURE_CATALOG[id];
    if (entry) useGLTF.preload(entry.path);
  }
}

/**
 * Loads a model and returns an independent CLONE per furniture instance.
 * A Three.js Object3D can only have one parent, so two pieces sharing the same model must
 * each get their own clone — otherwise the second one "steals" the mesh from the first.
 */
export function useFurnitureModel(catalogId: string, instanceId: string): THREE.Object3D {
  const entry = FURNITURE_CATALOG[catalogId];
  const { scene } = useGLTF(entry?.path ?? '/models/placeholder.glb');

  return useMemo(() => {
    const clone = scene.clone(true);
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });
    return clone;
  }, [scene, instanceId]); // instanceId keeps clones unique per piece
}
```

> **Asset note.** Provide a `/public/models/placeholder.glb` so a missing/unknown
> `catalogId` degrades gracefully instead of throwing. Compress real models with Draco and
> KTX2 textures; the `manualChunks` split for `three`/`@react-three/*` already lives in your
> `vite.config.ts` from the foundation.

### Part 11, Step 2: Furniture renderer — **`src/domains/viewer/components/FurnitureModel.tsx`** (new)

Exports `FurnitureInstances`, which `SceneContent` will import. Each piece is positioned via
`planTo3D` and rotated around the vertical axis.

```typescript
// src/domains/viewer/components/FurnitureModel.tsx

import React, { useMemo } from 'react';
import { shallow } from 'zustand/shallow';
import { useAppStore } from '@/store';
import { planTo3D } from '../services/transform';
import { useFurnitureModel, FURNITURE_CATALOG } from '../hooks/useAssetLoader';
import type { FurnitureItem } from '@/types';

/** Renders every placed furniture item. */
export const FurnitureInstances: React.FC = () => {
  const furniture = useAppStore((s) => Object.values(s.furniture), shallow);
  return (
    <group>
      {furniture.map((item) => (
        <FurniturePiece key={item.id} item={item} />
      ))}
    </group>
  );
};

const FurniturePiece: React.FC<{ item: FurnitureItem }> = React.memo(({ item }) => {
  const model = useFurnitureModel(item.catalogId, item.id);
  const catalog = FURNITURE_CATALOG[item.catalogId];
  const scale = (catalog?.scale ?? 0.01) * item.scale;
  const yOffset = catalog?.yOffset ?? 0;

  const position = useMemo(() => {
    const p = planTo3D(item.position, 0);
    return [p.x, p.y + yOffset, p.z] as [number, number, number];
  }, [item.position, yOffset]);

  return <primitive object={model} position={position} rotation={[0, item.rotation, 0]} scale={[scale, scale, scale]} />;
});

FurniturePiece.displayName = 'FurniturePiece';
```

---

## PART 8 (assembled): Scene & Canvas — built last, now that children exist

### Part 8, Step 2: Scene content — **`src/domains/viewer/components/SceneContent.tsx`** (new)

This is the bridge from store data to 3D meshes. It uses the `useGeometryForViewer`
selector (Part 4) and renders the ground, floors, walls, and furniture. The original
version also referenced `CameraController` (Part 13) and `VastuOverlay3D` (Part 15); those
are intentionally **omitted here** and added in their own installments so nothing imports a
file that doesn't exist yet. (`FurnitureInstances` is imported from `./FurnitureModel`, not
the bogus `./FurnitureInstances` path the original used.)

```typescript
// src/domains/viewer/components/SceneContent.tsx

import React from 'react';
import { useGeometryForViewer } from '@/store/selectors/editorSelectors';
import { WallMesh } from './WallMesh';
import { FloorMesh } from './FloorMesh';
import { FurnitureInstances } from './FurnitureModel';

/**
 * Pure orchestrator: maps store geometry to meshes. Each child builds its own geometry,
 * so this component just lists what's in the scene.
 */
export const SceneContent: React.FC = () => {
  const { walls, rooms } = useGeometryForViewer();

  return (
    <group>
      {/* Infinite‑ish ground plane to catch shadows. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} receiveShadow>
        <planeGeometry args={[100, 100]} />
        <meshStandardMaterial color="#1a1a2e" />
      </mesh>

      {rooms.map((room) => (
        <FloorMesh key={room.id} polygon={room.polygon} materialId={room.floorMaterialId} />
      ))}

      {walls.map((wall) =>
        wall.start && wall.end ? (
          <WallMesh
            key={wall.id}
            start={wall.start}
            end={wall.end}
            thickness={wall.thickness}
            height={wall.height}
            materialId={wall.materialId}
          />
        ) : null
      )}

      <FurnitureInstances />
      {/* CameraController arrives in Part 13; VastuOverlay3D in Part 15. */}
    </group>
  );
};
```

### Part 8, Step 3: The canvas — **`src/domains/viewer/components/ViewerCanvas.tsx`** (new)

The R3F entry point, assembled last. It imports `SceneEnvironment` (the original forgot to)
and uses drei's `OrbitControls` as a **temporary** camera so the viewer is usable right
now; Part 13 replaces it with the real `CameraController`. Note `import.meta.env.DEV`
(Vite) instead of the original's `process.env.NODE_ENV`.

```typescript
// src/domains/viewer/components/ViewerCanvas.tsx

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Preload, Stats } from '@react-three/drei';
import { SceneEnvironment } from './SceneEnvironment';
import { SceneContent } from './SceneContent';

/**
 * The 3D viewport.
 * - shadows + PCF soft shadow maps for grounded lighting
 * - dpr capped at 2 so 4K displays don't tank the framerate
 * - a Suspense boundary so async GLTF loads don't crash the tree
 * - OrbitControls is a placeholder camera until Part 13's CameraController
 */
export const ViewerCanvas: React.FC = () => {
  return (
    <div className="w-full h-full">
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', stencil: false }}
        camera={{ fov: 60, near: 0.1, far: 1000, position: [10, 10, 10] }}
      >
        <Suspense fallback={null}>
          <SceneEnvironment />
          <SceneContent />
          <OrbitControls makeDefault />
          <Preload all />
        </Suspense>
        {import.meta.env.DEV && <Stats />}
      </Canvas>
    </div>
  );
};
```

**Common mistakes this ordering prevents**

1. `SceneContent` importing `FloorMesh` / `FurnitureInstances` that don't exist (or live at
   another path).
2. `WallMesh` importing a `useMaterial` hook that was never written.
3. Pulling `CameraController` (Part 13) and `VastuOverlay3D` (Part 15) into the scene before
   those parts exist — now deferred to their installments.

---

## End of Installment 2 (Parts 8–11: the 3D foundation)

The 3D view now stands on its own: lighting → transform → wall/floor geometry → shared
materials → meshes → furniture → scene → canvas, each created before it's used. It renders
with a temporary orbit camera and no Vastu overlay yet — both are filled in next.

**Installment 3 — Interaction & analysis (Parts 12–15)** continues: `collision.ts`, the
camera rigs (`useOrbitCamera` → `useFirstPerson` → `CameraController`, which then replaces
the placeholder `OrbitControls`), the Vastu math chain (`vectors` → `brahmasthan` → `zones`
→ `scoring`), and finally the `VastuOverlay2D` / `VastuOverlay3D` components (the latter
plugging back into `SceneContent`).

## Installment 3 — Interaction & Analysis (Parts 12–15)

This installment adds furniture collision, the real camera rigs (which finally replace the
placeholder `OrbitControls` from Installment 2), the Vastu math chain, and the 2D/3D
overlays. Two orphans from the original are closed here: nothing ever computed the plan
boundary or the Vastu score, so a `useVastuAnalysis` hook is added to do both. As agreed,
**no test scripts are included** — validate visually in the 3D view.

---

## PART 12: Collision Detection

### Why and how

Furniture shouldn't overlap other furniture. We do this in two phases: a cheap **broad
phase** (axis‑aligned boxes + a spatial hash grid) throws out pairs that obviously can't
touch, then a precise **narrow phase** (Separating Axis Theorem on oriented boxes) confirms
the survivors. Order of creation: type additions first, then the service.

### Part 12, Step 1: Bounding‑box types — **`src/types/geometry.ts`** (additions)

Append these two interfaces to the existing geometry types from Part 2.

```typescript
// src/types/geometry.ts  (append)

/** Axis‑Aligned Bounding Box — a box whose sides line up with the world axes. */
export interface AABB {
  readonly min: Point2D;
  readonly max: Point2D;
}

/** Oriented Bounding Box — a box that can be rotated (furniture footprint). */
export interface OBB {
  readonly center: Point2D;
  readonly halfExtents: Point2D; // half‑width, half‑depth
  readonly rotation: number; // radians
}
```

### Part 12, Step 2: Collision service — **`src/domains/editor/services/collision.ts`** (new)

A pure module (no React, no store). The original imported `computeWallQuad` but never used
it — that import is removed here.

```typescript
// src/domains/editor/services/collision.ts

import type { Point2D, AABB, OBB } from '@/types/geometry';
import type { FurnitureItem, Wall, Vertex } from '@/types/editor';

/** Broad‑phase test: two AABBs overlap only if they overlap on BOTH axes. O(1). */
export function aabbOverlaps(a: AABB, b: AABB): boolean {
  return a.min.x <= b.max.x && a.max.x >= b.min.x && a.min.y <= b.max.y && a.max.y >= b.min.y;
}

/** Tightest axis‑aligned box around a (possibly rotated) furniture item. */
export function furnitureToAABB(item: FurnitureItem): AABB {
  const hw = item.bounds.width / 2;
  const hd = item.bounds.depth / 2;
  const cos = Math.abs(Math.cos(item.rotation));
  const sin = Math.abs(Math.sin(item.rotation));
  const ex = hw * cos + hd * sin; // rotated extent on X
  const ey = hw * sin + hd * cos; // rotated extent on Y
  return {
    min: { x: item.position.x - ex, y: item.position.y - ey },
    max: { x: item.position.x + ex, y: item.position.y + ey },
  };
}

/**
 * Narrow‑phase test: do two oriented boxes overlap?
 * Separating Axis Theorem — if we can find ANY axis where the boxes' shadows don't
 * overlap, they're apart. For two OBBs there are 4 candidate axes (2 per box).
 */
export function obbIntersects(a: OBB, b: OBB): boolean {
  const cornersA = getOBBCorners(a);
  const cornersB = getOBBCorners(b);
  const axes = [...getOBBAxes(a), ...getOBBAxes(b)];
  for (const axis of axes) {
    const projA = projectOntoAxis(cornersA, axis);
    const projB = projectOntoAxis(cornersB, axis);
    if (projA.max < projB.min || projB.max < projA.min) return false; // gap found ⇒ apart
  }
  return true;
}

function getOBBCorners(obb: OBB): Point2D[] {
  const cos = Math.cos(obb.rotation);
  const sin = Math.sin(obb.rotation);
  const local = [
    { x: -obb.halfExtents.x, y: -obb.halfExtents.y },
    { x: obb.halfExtents.x, y: -obb.halfExtents.y },
    { x: obb.halfExtents.x, y: obb.halfExtents.y },
    { x: -obb.halfExtents.x, y: obb.halfExtents.y },
  ];
  return local.map((lc) => ({
    x: obb.center.x + lc.x * cos - lc.y * sin,
    y: obb.center.y + lc.x * sin + lc.y * cos,
  }));
}

function getOBBAxes(obb: OBB): Point2D[] {
  const cos = Math.cos(obb.rotation);
  const sin = Math.sin(obb.rotation);
  return [
    { x: cos, y: sin },
    { x: -sin, y: cos },
  ];
}

function projectOntoAxis(points: Point2D[], axis: Point2D): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const p of points) {
    const proj = p.x * axis.x + p.y * axis.y;
    if (proj < min) min = proj;
    if (proj > max) max = proj;
  }
  return { min, max };
}

/**
 * Spatial hash grid for the broad phase. The world is chopped into square cells; only
 * items sharing a cell are ever narrow‑phase tested. Keep cellSize ≥ the largest item so
 * overlapping items always share a cell.
 */
export class SpatialHashGrid {
  private cells = new Map<string, Set<string>>();
  private entityCells = new Map<string, string[]>();

  constructor(private cellSize = 100) {} // 100cm = 1m cells

  insert(entityId: string, aabb: AABB): void {
    const keys: string[] = [];
    const minCx = Math.floor(aabb.min.x / this.cellSize);
    const maxCx = Math.floor(aabb.max.x / this.cellSize);
    const minCy = Math.floor(aabb.min.y / this.cellSize);
    const maxCy = Math.floor(aabb.max.y / this.cellSize);
    for (let cx = minCx; cx <= maxCx; cx++) {
      for (let cy = minCy; cy <= maxCy; cy++) {
        const key = `${cx},${cy}`;
        keys.push(key);
        if (!this.cells.has(key)) this.cells.set(key, new Set());
        this.cells.get(key)!.add(entityId);
      }
    }
    this.entityCells.set(entityId, keys);
  }

  remove(entityId: string): void {
    const keys = this.entityCells.get(entityId);
    if (!keys) return;
    for (const key of keys) this.cells.get(key)?.delete(entityId);
    this.entityCells.delete(entityId);
  }

  query(aabb: AABB): Set<string> {
    const result = new Set<string>();
    const minCx = Math.floor(aabb.min.x / this.cellSize);
    const maxCx = Math.floor(aabb.max.x / this.cellSize);
    const minCy = Math.floor(aabb.min.y / this.cellSize);
    const maxCy = Math.floor(aabb.max.y / this.cellSize);
    for (let cx = minCx; cx <= maxCx; cx++) {
      for (let cy = minCy; cy <= maxCy; cy++) {
        const cell = this.cells.get(`${cx},${cy}`);
        if (cell) for (const id of cell) result.add(id);
      }
    }
    return result;
  }

  clear(): void {
    this.cells.clear();
    this.entityCells.clear();
  }
}

/**
 * Returns the ids of furniture that the given item overlaps.
 * (`walls`/`vertices` are part of the signature for the wall‑aware extension in Part 27;
 * furniture‑vs‑furniture is handled here.)
 */
export function checkFurnitureCollisions(
  item: FurnitureItem,
  allFurniture: Record<string, FurnitureItem>,
  walls: Wall[],
  vertices: Record<string, Vertex>,
  spatialGrid: SpatialHashGrid
): string[] {
  const collisions: string[] = [];
  const itemAABB = furnitureToAABB(item);
  const itemOBB: OBB = {
    center: item.position,
    halfExtents: { x: item.bounds.width / 2, y: item.bounds.depth / 2 },
    rotation: item.rotation,
  };

  for (const candidateId of spatialGrid.query(itemAABB)) {
    if (candidateId === item.id) continue;
    const other = allFurniture[candidateId];
    if (!other) continue;
    const otherOBB: OBB = {
      center: other.position,
      halfExtents: { x: other.bounds.width / 2, y: other.bounds.depth / 2 },
      rotation: other.rotation,
    };
    if (obbIntersects(itemOBB, otherOBB)) collisions.push(candidateId);
  }
  return collisions;
}
```

---

## PART 13: Camera Systems

Two rigs: an **orbit** camera for design review and a **first‑person** walkthrough. We
build both, wrap them in a `CameraController` switch, then update `ViewerCanvas` to use it
instead of the placeholder.

### Part 13, Step 1: Orbit rig — **`src/domains/viewer/hooks/useOrbitCamera.ts`** (new)

Reads the cached `planCentroid3D` (viewer slice, Part 4) so rotation stays centered on the
model. Unused imports from the original (`useThree`, `THREE`) are dropped.

```typescript
// src/domains/viewer/hooks/useOrbitCamera.ts

import React, { useRef, useEffect } from 'react';
import { OrbitControls } from '@react-three/drei';
import { useAppStore } from '@/store';

/**
 * Bird's‑eye orbit camera. Clamps distance and polar angle so you can't fly underground
 * or zoom inside a wall, and re‑targets the plan centroid whenever it changes.
 */
export const OrbitCameraController: React.FC = () => {
  const controlsRef = useRef<any>(null);
  const planCentroid = useAppStore((s) => s.planCentroid3D);

  useEffect(() => {
    if (controlsRef.current && planCentroid) {
      controlsRef.current.target.set(planCentroid.x, 0, planCentroid.z);
      controlsRef.current.update();
    }
  }, [planCentroid]);

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      minDistance={2}
      maxDistance={50}
      maxPolarAngle={Math.PI / 2 - 0.05} // stay above ground
      minPolarAngle={0.1}
      enableDamping
      dampingFactor={0.05}
      rotateSpeed={0.5}
      panSpeed={0.8}
      zoomSpeed={1.2}
    />
  );
};
```

### Part 13, Step 2: First‑person rig — **`src/domains/viewer/hooks/useFirstPerson.ts`** (new)

WASD movement + pointer‑lock mouse look, kept at eye height. Movement is multiplied by
`delta` so speed is identical at 30 or 144 fps.

```typescript
// src/domains/viewer/hooks/useFirstPerson.ts

import { useRef, useEffect, useCallback } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

interface FirstPersonConfig {
  moveSpeed: number; // meters / second
  lookSpeed: number; // radians / pixel
  eyeHeight: number; // meters
  collisionRadius: number; // meters
}

const DEFAULT_CONFIG: FirstPersonConfig = {
  moveSpeed: 3.0,
  lookSpeed: 0.002,
  eyeHeight: 1.6,
  collisionRadius: 0.3,
};

export function useFirstPersonControls(config = DEFAULT_CONFIG) {
  const { camera, gl } = useThree();
  const euler = useRef(new THREE.Euler(0, 0, 0, 'YXZ')); // yaw then pitch ⇒ no gimbal lock
  const keys = useRef(new Set<string>());
  const isLocked = useRef(false);

  const requestLock = useCallback(() => {
    gl.domElement.requestPointerLock();
  }, [gl]);

  useEffect(() => {
    const onLockChange = () => {
      isLocked.current = document.pointerLockElement === gl.domElement;
    };
    const onMouseMove = (e: MouseEvent) => {
      if (!isLocked.current) return;
      euler.current.y -= e.movementX * config.lookSpeed;
      euler.current.x -= e.movementY * config.lookSpeed;
      // Clamp pitch so you can't flip over backwards.
      euler.current.x = Math.max(-Math.PI / 2 + 0.01, Math.min(Math.PI / 2 - 0.01, euler.current.x));
      camera.quaternion.setFromEuler(euler.current);
    };
    const onKeyDown = (e: KeyboardEvent) => keys.current.add(e.code);
    const onKeyUp = (e: KeyboardEvent) => keys.current.delete(e.code);

    document.addEventListener('pointerlockchange', onLockChange);
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('keyup', onKeyUp);
    return () => {
      document.removeEventListener('pointerlockchange', onLockChange);
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('keyup', onKeyUp);
    };
  }, [camera, gl, config.lookSpeed]);

  useFrame((_, delta) => {
    if (!isLocked.current) return;
    const direction = new THREE.Vector3();
    if (keys.current.has('KeyW')) direction.z -= 1;
    if (keys.current.has('KeyS')) direction.z += 1;
    if (keys.current.has('KeyA')) direction.x -= 1;
    if (keys.current.has('KeyD')) direction.x += 1;
    direction.normalize();

    // Move relative to where you're facing, but ignore pitch so you don't fly.
    const moveQuat = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, euler.current.y, 0));
    direction.applyQuaternion(moveQuat);

    const speed = config.moveSpeed * delta;
    camera.position.x += direction.x * speed;
    camera.position.z += direction.z * speed;
    camera.position.y = config.eyeHeight; // pinned to standing height
  });

  return { requestLock, isLocked };
}
```

### Part 13, Step 3: The switch — **`src/domains/viewer/components/CameraController.tsx`** (new)

```typescript
// src/domains/viewer/components/CameraController.tsx

import React from 'react';
import { OrbitCameraController } from '../hooks/useOrbitCamera';
import { useFirstPersonControls } from '../hooks/useFirstPerson';

interface CameraControllerProps {
  mode: 'orbit' | 'firstPerson';
}

export const CameraController: React.FC<CameraControllerProps> = ({ mode }) => {
  return mode === 'orbit' ? <OrbitCameraController /> : <FirstPersonCamera />;
};

/** An invisible click‑catcher that enters pointer‑lock when clicked. */
const FirstPersonCamera: React.FC = () => {
  const { requestLock } = useFirstPersonControls();
  return (
    <mesh visible={false} onClick={requestLock}>
      <planeGeometry args={[1000, 1000]} />
    </mesh>
  );
};
```

### Part 13, Step 4: Use the real camera — **`src/domains/viewer/components/ViewerCanvas.tsx`** (modify)

Now that `CameraController` exists, swap out the temporary `OrbitControls` from Installment
2 and drive the mode from the store's `cameraMode`.

```typescript
// src/domains/viewer/components/ViewerCanvas.tsx  (updated)

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Preload, Stats } from '@react-three/drei';
import { useAppStore } from '@/store';
import { SceneEnvironment } from './SceneEnvironment';
import { SceneContent } from './SceneContent';
import { CameraController } from './CameraController';

export const ViewerCanvas: React.FC = () => {
  const cameraMode = useAppStore((s) => s.cameraMode);

  return (
    <div className="w-full h-full">
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', stencil: false }}
        camera={{ fov: 60, near: 0.1, far: 1000, position: [10, 10, 10] }}
      >
        <Suspense fallback={null}>
          <SceneEnvironment />
          <CameraController mode={cameraMode} />
          <SceneContent />
          <Preload all />
        </Suspense>
        {import.meta.env.DEV && <Stats />}
      </Canvas>
    </div>
  );
};
```

---

## PART 14: Vastu Mathematics

Vastu analysis needs four pure modules, built in dependency order: **`vectors.ts`**
(independent) → **`brahmasthan.ts`** (centroid; uses `computeSignedArea` from Part 7) →
**`zones.ts`** (the 8 directional sectors) → **`scoring.ts`** (uses both `zones` and
`brahmasthan`). The store's Vastu slice (Part 4) already imports `VastuScore` from
`scoring.ts` and `VastuDirection` from `zones.ts`, so these files complete that contract.

### Part 14, Step 1: Direction vectors — **`src/domains/vastu/services/vectors.ts`** (new)

```typescript
// src/domains/vastu/services/vectors.ts

import type { Point2D } from '@/types/geometry';

/**
 * Unit vectors for the 16‑direction model (each 22.5° apart). North = +Y, East = +X.
 * Used for fine‑grained zone work and as a lookup when drawing direction markers.
 */
export const DIRECTION_VECTORS_16: Record<string, Point2D> = {
  E: { x: 1.0, y: 0.0 },
  ENE: { x: 0.924, y: 0.383 },
  NE: { x: 0.707, y: 0.707 },
  NNE: { x: 0.383, y: 0.924 },
  N: { x: 0.0, y: 1.0 },
  NNW: { x: -0.383, y: 0.924 },
  NW: { x: -0.707, y: 0.707 },
  WNW: { x: -0.924, y: 0.383 },
  W: { x: -1.0, y: 0.0 },
  WSW: { x: -0.924, y: -0.383 },
  SW: { x: -0.707, y: -0.707 },
  SSW: { x: -0.383, y: -0.924 },
  S: { x: 0.0, y: -1.0 },
  SSE: { x: 0.383, y: -0.924 },
  SE: { x: 0.707, y: -0.707 },
  ESE: { x: 0.924, y: -0.383 },
};

/** Angular midpoint between two direction vectors (handles the 0°/360° wrap). */
export function angularMidpoint(a: Point2D, b: Point2D): Point2D {
  const ax = Math.atan2(a.y, a.x);
  const bx = Math.atan2(b.y, b.x);
  let diff = bx - ax;
  if (diff > Math.PI) diff -= 2 * Math.PI;
  if (diff < -Math.PI) diff += 2 * Math.PI;
  const mid = ax + diff / 2;
  return { x: Math.cos(mid), y: Math.sin(mid) };
}

/**
 * Tests whether an angle falls inside a sector, correctly handling sectors that straddle
 * 0°/360° (e.g. the East sector running 337.5°→22.5°).
 */
export function isAngleInSector(angle: number, sectorStart: number, sectorSpan: number): boolean {
  const TWO_PI = Math.PI * 2;
  const normAngle = ((angle % TWO_PI) + TWO_PI) % TWO_PI;
  const normStart = ((sectorStart % TWO_PI) + TWO_PI) % TWO_PI;
  const end = normStart + sectorSpan;
  return end <= TWO_PI ? normAngle >= normStart && normAngle < end : normAngle >= normStart || normAngle < end - TWO_PI;
}
```

### Part 14, Step 2: Plan center — **`src/domains/vastu/services/brahmasthan.ts`** (new)

The **Brahmasthan** is the plan's geometric center. We use the true *area* centroid (not a
vertex average), so an L‑shaped plan's center correctly shifts toward the larger wing.

```typescript
// src/domains/vastu/services/brahmasthan.ts

import type { Point2D } from '@/types/geometry';
import { computeSignedArea } from '@/domains/editor/services/roomDetection';

/** Average of points — used only as a fallback for degenerate inputs. */
function vertexAverage(points: Point2D[]): Point2D {
  const sum = points.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 });
  return { x: sum.x / points.length, y: sum.y / points.length };
}

/**
 * Area centroid of a polygon (the Brahmasthan). Falls back to a vertex average for
 * polygons with <3 points or (near‑)zero area.
 */
export function calculateBrahmasthan(boundary: Point2D[]): Point2D {
  if (boundary.length < 3) return vertexAverage(boundary);

  const area = computeSignedArea(boundary);
  if (Math.abs(area) < 1e-10) return vertexAverage(boundary);

  let cx = 0;
  let cy = 0;
  const n = boundary.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const cross = boundary[i].x * boundary[j].y - boundary[j].x * boundary[i].y;
    cx += (boundary[i].x + boundary[j].x) * cross;
    cy += (boundary[i].y + boundary[j].y) * cross;
  }
  const factor = 1 / (6 * area);
  return { x: cx * factor, y: cy * factor };
}

/**
 * The central Brahmasthan zone (kept open in Vastu). Returns a center + radius, where the
 * radius is one‑third of the distance to the nearest boundary edge.
 */
export function calculateBrahmasthanZone(boundary: Point2D[], center: Point2D): { center: Point2D; radius: number } {
  let minDist = Infinity;
  const n = boundary.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    minDist = Math.min(minDist, pointToSegmentDistance(center, boundary[i], boundary[j]));
  }
  return { center, radius: minDist / 3 };
}

function pointToSegmentDistance(p: Point2D, a: Point2D, b: Point2D): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y);
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}
```

### Part 14, Step 3: Directional zones — **`src/domains/vastu/services/zones.ts`** (new)

```typescript
// src/domains/vastu/services/zones.ts

import type { Point2D } from '@/types/geometry';

export type VastuDirection = 'N' | 'NE' | 'E' | 'SE' | 'S' | 'SW' | 'W' | 'NW';

export interface VastuZone {
  readonly direction: VastuDirection;
  readonly startAngle: number; // radians from +X (East), CCW
  readonly spanAngle: number;
  readonly element: 'fire' | 'water' | 'earth' | 'air' | 'space';
  readonly recommendedRooms: string[];
  readonly color: string;
}

/**
 * The eight 45° sectors. North = +Y (90°), East = +X (0°), angles increase CCW.
 * Each sector is centered on its compass direction (e.g. East spans 337.5°→22.5°).
 */
export const VASTU_ZONES_8: VastuZone[] = [
  { direction: 'E', startAngle: (15 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'air', recommendedRooms: ['living', 'study', 'entrance'], color: '#4CAF50' },
  { direction: 'NE', startAngle: Math.PI / 8, spanAngle: Math.PI / 4, element: 'water', recommendedRooms: ['puja', 'study', 'living'], color: '#2196F3' },
  { direction: 'N', startAngle: (3 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'water', recommendedRooms: ['living', 'entrance', 'study'], color: '#03A9F4' },
  { direction: 'NW', startAngle: (5 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'air', recommendedRooms: ['bedroom', 'storage', 'garage'], color: '#9C27B0' },
  { direction: 'W', startAngle: (7 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'space', recommendedRooms: ['dining', 'bedroom', 'study'], color: '#673AB7' },
  { direction: 'SW', startAngle: (9 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'earth', recommendedRooms: ['bedroom', 'storage'], color: '#795548' },
  { direction: 'S', startAngle: (11 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'fire', recommendedRooms: ['kitchen', 'dining'], color: '#F44336' },
  { direction: 'SE', startAngle: (13 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'fire', recommendedRooms: ['kitchen', 'bathroom'], color: '#FF5722' },
];

/** Maps an angle (degrees, 0=E, CCW) to one of the 8 directions. */
function degreesToDirection(degrees: number): VastuDirection {
  const d = ((degrees % 360) + 360) % 360;
  if (d >= 337.5 || d < 22.5) return 'E';
  if (d < 67.5) return 'NE';
  if (d < 112.5) return 'N';
  if (d < 157.5) return 'NW';
  if (d < 202.5) return 'W';
  if (d < 247.5) return 'SW';
  if (d < 292.5) return 'S';
  return 'SE';
}

/** The primary direction of a room, measured from the Brahmasthan to the room's centroid. */
export function getRoomDirection(roomPolygon: Point2D[], brahmasthan: Point2D): VastuDirection {
  const n = roomPolygon.length;
  const centroid = roomPolygon.reduce((acc, p) => ({ x: acc.x + p.x / n, y: acc.y + p.y / n }), { x: 0, y: 0 });
  const angle = Math.atan2(centroid.y - brahmasthan.y, centroid.x - brahmasthan.x);
  return degreesToDirection((angle * 180) / Math.PI);
}
```

### Part 14, Step 4: Scoring — **`src/domains/vastu/services/scoring.ts`** (new)

```typescript
// src/domains/vastu/services/scoring.ts

import type { Room, RoomType } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { type VastuDirection, getRoomDirection } from './zones';
import { calculateBrahmasthan } from './brahmasthan';

export interface VastuScore {
  readonly overall: number; // 0‑100
  readonly roomScores: Record<string, RoomVastuScore>;
  readonly recommendations: VastuRecommendation[];
}

export interface RoomVastuScore {
  readonly roomId: string;
  readonly roomType: RoomType;
  readonly direction: VastuDirection;
  readonly score: number;
  readonly isIdeal: boolean;
  readonly idealDirections: VastuDirection[];
  readonly reason: string;
}

export interface VastuRecommendation {
  readonly severity: 'critical' | 'warning' | 'suggestion';
  readonly roomId: string;
  readonly message: string;
}

/** Ideal / acceptable / adverse placements per room type (traditional Vastu). */
const VASTU_RULES: Record<RoomType, { ideal: VastuDirection[]; acceptable: VastuDirection[]; adverse: VastuDirection[] }> = {
  living: { ideal: ['N', 'NE', 'E'], acceptable: ['NW', 'SE'], adverse: ['SW', 'S'] },
  bedroom: { ideal: ['SW', 'S', 'W'], acceptable: ['NW'], adverse: ['NE', 'SE'] },
  kitchen: { ideal: ['SE'], acceptable: ['S', 'E', 'NW'], adverse: ['NE', 'SW'] },
  bathroom: { ideal: ['NW', 'W'], acceptable: ['SE'], adverse: ['NE', 'SW', 'E'] },
  puja: { ideal: ['NE'], acceptable: ['N', 'E'], adverse: ['S', 'SW', 'SE'] },
  study: { ideal: ['NE', 'N', 'E'], acceptable: ['W', 'NW'], adverse: ['SW', 'S', 'SE'] },
  dining: { ideal: ['W', 'E'], acceptable: ['N', 'S'], adverse: ['NE', 'SW'] },
  storage: { ideal: ['SW', 'S', 'W'], acceptable: ['NW'], adverse: ['NE', 'N'] },
  garage: { ideal: ['NW', 'SE'], acceptable: ['W', 'S'], adverse: ['NE'] },
  balcony: { ideal: ['N', 'E', 'NE'], acceptable: ['NW', 'SE'], adverse: ['SW', 'W'] },
  entrance: { ideal: ['N', 'E', 'NE'], acceptable: ['NW'], adverse: ['S', 'SW', 'SE'] },
  corridor: { ideal: ['N', 'E'], acceptable: ['W', 'S'], adverse: [] },
  custom: { ideal: [], acceptable: [], adverse: [] },
};

/**
 * Full Vastu analysis for a plan. `roomPolygons` maps room id → its boundary points (cm);
 * `planBoundary` is the outer outline used to find the Brahmasthan.
 */
export function computeVastuScore(
  rooms: Room[],
  roomPolygons: Record<string, Point2D[]>,
  planBoundary: Point2D[]
): VastuScore {
  const brahmasthan = calculateBrahmasthan(planBoundary);
  const roomScores: Record<string, RoomVastuScore> = {};
  const recommendations: VastuRecommendation[] = [];

  for (const room of rooms) {
    const polygon = roomPolygons[room.id];
    if (!polygon || polygon.length < 3) continue;

    const direction = getRoomDirection(polygon, brahmasthan);
    const rules = VASTU_RULES[room.roomType];

    let score: number;
    let isIdeal = false;
    let reason: string;

    if (rules.ideal.includes(direction)) {
      score = 100;
      isIdeal = true;
      reason = `${room.label} is perfectly placed in the ${direction}.`;
    } else if (rules.acceptable.includes(direction)) {
      score = 70;
      reason = `${room.label} is acceptably placed in the ${direction}. Ideal: ${rules.ideal.join(', ')}.`;
    } else if (rules.adverse.includes(direction)) {
      score = 20;
      reason = `${room.label} in the ${direction} is adverse. Prefer: ${rules.ideal.join(', ')}.`;
      recommendations.push({ severity: 'critical', roomId: room.id, message: reason });
    } else {
      score = 50;
      reason = `${room.label} is neutral in the ${direction}. Ideal: ${rules.ideal.join(', ')}.`;
      recommendations.push({ severity: 'suggestion', roomId: room.id, message: reason });
    }

    roomScores[room.id] = {
      roomId: room.id,
      roomType: room.roomType,
      direction,
      score,
      isIdeal,
      idealDirections: rules.ideal,
      reason,
    };
  }

  const entries = Object.values(roomScores);
  const overall = entries.length ? entries.reduce((s, r) => s + r.score, 0) / entries.length : 0;
  return { overall, roomScores, recommendations };
}
```

---

## PART 15: Vastu Overlay Rendering

The overlays only *read* `planBoundary` and `vastuScore` from the store — but in the
original guide **nothing ever wrote them**, so the overlays would always render nothing.
We fix that first by adding (1) a function that derives the plan's outer boundary from the
walls, and (2) a hook that runs the whole analysis and pushes results into the store. Then
the two overlay components, then we plug them back into the editor and the 3D scene.

### Part 15, Step 1: Outer boundary — **`src/domains/vastu/services/planBoundary.ts`** (new — was missing)

The plan boundary is the single outermost loop of walls. We trace every face of the wall
graph (same idea as room detection) and return the one with the largest area magnitude —
that loop, by definition, encloses the whole plan.

```typescript
// src/domains/vastu/services/planBoundary.ts

import type { EntityId, Vertex, Wall, Point2D } from '@/types';
import { computeSignedArea } from '@/domains/editor/services/roomDetection';

interface DirectedEdge {
  fromVertexId: EntityId;
  toVertexId: EntityId;
}

/**
 * Derives the plan's outer boundary polygon (cm) from the wall graph, or null if there
 * isn't a closed loop yet. Returns the loop with the greatest enclosed area — the outline
 * that wraps every room.
 */
export function computePlanBoundary(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): Point2D[] | null {
  const edges: DirectedEdge[] = [];
  for (const wall of Object.values(walls)) {
    edges.push({ fromVertexId: wall.startVertexId, toVertexId: wall.endVertexId });
    edges.push({ fromVertexId: wall.endVertexId, toVertexId: wall.startVertexId });
  }

  const visited = new Set<string>();
  let best: Point2D[] | null = null;
  let bestArea = 0;

  for (const start of edges) {
    if (visited.has(`${start.fromVertexId}->${start.toVertexId}`)) continue;
    const cycle = traceCycle(start, vertices, edges);
    if (!cycle) continue;

    for (let i = 0; i < cycle.length; i++) {
      visited.add(`${cycle[i]}->${cycle[(i + 1) % cycle.length]}`);
    }

    const polygon = cycle.map((id) => vertices[id].position);
    const area = Math.abs(computeSignedArea(polygon));
    if (area > bestArea) {
      bestArea = area;
      best = polygon;
    }
  }

  return best;
}

/** Smallest‑left‑turn face tracer (identical rule to room detection). */
function traceCycle(
  startEdge: DirectedEdge,
  vertices: Record<EntityId, Vertex>,
  allEdges: DirectedEdge[]
): EntityId[] | null {
  const MAX = 200;
  const cycle: EntityId[] = [startEdge.fromVertexId];
  let from = startEdge.fromVertexId;
  let to = startEdge.toVertexId;

  for (let step = 0; step < MAX; step++) {
    if (to === startEdge.fromVertexId) return cycle.length >= 3 ? cycle : null;
    cycle.push(to);

    const incoming = Math.atan2(
      vertices[from].position.y - vertices[to].position.y,
      vertices[from].position.x - vertices[to].position.x
    );
    const outgoing = allEdges.filter((e) => e.fromVertexId === to && e.toVertexId !== from);
    if (outgoing.length === 0) return null;

    let bestEdge: DirectedEdge | null = null;
    let bestAngle = Infinity;
    for (const e of outgoing) {
      const out = Math.atan2(
        vertices[e.toVertexId].position.y - vertices[to].position.y,
        vertices[e.toVertexId].position.x - vertices[to].position.x
      );
      let rel = out - incoming;
      while (rel <= 0) rel += Math.PI * 2;
      while (rel > Math.PI * 2) rel -= Math.PI * 2;
      if (rel < bestAngle) {
        bestAngle = rel;
        bestEdge = e;
      }
    }
    if (!bestEdge) return null;
    from = to;
    to = bestEdge.toVertexId;
  }
  return null;
}
```

### Part 15, Step 2: Run the analysis — **`src/domains/vastu/hooks/useVastuAnalysis.ts`** (new — closes the orphan)

This hook is the missing wiring. It watches walls/vertices/rooms, computes the boundary and
the score, and writes both into the store (`setPlanBoundary`, `setVastuScore`) so the
panels and overlays have something to show. Mount it once alongside `useRoomDetection`.

```typescript
// src/domains/vastu/hooks/useVastuAnalysis.ts

import { useEffect } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types/geometry';
import { computePlanBoundary } from '../services/planBoundary';
import { computeVastuScore } from '../services/scoring';

/**
 * Recomputes the plan boundary and Vastu score whenever the geometry changes, then stores
 * them. Renders nothing — mount once where the editor/viewer lives.
 */
export function useVastuAnalysis(): void {
  const walls = useAppStore((s) => s.walls);
  const vertices = useAppStore((s) => s.vertices);
  const rooms = useAppStore((s) => s.rooms);

  useEffect(() => {
    const boundary = computePlanBoundary(vertices, walls);
    useAppStore.getState().setPlanBoundary(boundary);

    if (!boundary) {
      useAppStore.getState().setVastuScore(null);
      return;
    }

    // Resolve each room's boundary vertex ids → positions for the scorer.
    const roomList = Object.values(rooms);
    const roomPolygons: Record<string, Point2D[]> = {};
    for (const room of roomList) {
      roomPolygons[room.id] = room.boundaryVertexIds
        .map((id) => vertices[id]?.position)
        .filter((p): p is Point2D => Boolean(p));
    }

    useAppStore.getState().setVastuScore(computeVastuScore(roomList, roomPolygons, boundary));
  }, [walls, vertices, rooms]);
}
```

### Part 15, Step 3: 2D overlay — **`src/domains/vastu/components/VastuOverlay2D.tsx`** (new)

Pie‑slice sectors drawn from the Brahmasthan, inside the editor SVG (so it obeys the same
`-y` flip).

```typescript
// src/domains/vastu/components/VastuOverlay2D.tsx

import React, { useMemo } from 'react';
import { useAppStore } from '@/store';
import { VASTU_ZONES_8, type VastuZone } from '../services/zones';
import { calculateBrahmasthan } from '../services/brahmasthan';
import type { Point2D } from '@/types/geometry';

export const VastuOverlay2D: React.FC = () => {
  const planBoundary = useAppStore((s) => s.planBoundary);
  const showVastu = useAppStore((s) => s.showVastuOverlay2D);

  const brahmasthan = useMemo(
    () => (planBoundary ? calculateBrahmasthan(planBoundary) : null),
    [planBoundary]
  );

  if (!showVastu || !brahmasthan || !planBoundary) return null;

  // Sectors reach a bit past the furthest boundary vertex.
  const maxDist = planBoundary.reduce(
    (max, p) => Math.max(max, Math.hypot(p.x - brahmasthan.x, p.y - brahmasthan.y)),
    0
  );

  return (
    <g opacity={0.3} pointerEvents="none">
      {VASTU_ZONES_8.map((zone) => (
        <ZoneSector key={zone.direction} zone={zone} center={brahmasthan} radius={maxDist * 1.1} />
      ))}
      <circle cx={brahmasthan.x} cy={-brahmasthan.y} r={maxDist / 6} fill="gold" opacity={0.4} stroke="goldenrod" strokeWidth={1} />
    </g>
  );
};

const ZoneSector: React.FC<{ zone: VastuZone; center: Point2D; radius: number }> = ({ zone, center, radius }) => {
  const path = useMemo(() => {
    // World angles are CCW; SVG Y is flipped, so we negate the y component of each point.
    const startAngle = zone.startAngle;
    const endAngle = zone.startAngle + zone.spanAngle;
    const x1 = center.x + radius * Math.cos(startAngle);
    const y1 = -center.y - radius * Math.sin(startAngle);
    const x2 = center.x + radius * Math.cos(endAngle);
    const y2 = -center.y - radius * Math.sin(endAngle);
    const largeArc = zone.spanAngle > Math.PI ? 1 : 0;
    // sweep‑flag 0 because the Y‑flip turns world‑CCW into SVG‑CW.
    return `M ${center.x} ${-center.y} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 0 ${x2} ${y2} Z`;
  }, [zone, center, radius]);

  return <path d={path} fill={zone.color} />;
};
```

> **Wire it in (small edit to `EditorCanvas.tsx`).** Add the import
> `import { VastuOverlay2D } from '@/domains/vastu/components/VastuOverlay2D';` and place
> `<VastuOverlay2D />` just **below** `<SelectionLayer />` inside the pan/zoom `<g>` so the
> sectors sit above the plan. It self‑hides unless `showVastuOverlay2D` is on.

### Part 15, Step 4: 3D overlay — **`src/domains/viewer/components/VastuOverlay3D.tsx`** (new)

The same sectors as flat, transparent triangle fans floating just above the floor.

```typescript
// src/domains/viewer/components/VastuOverlay3D.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { useAppStore } from '@/store';
import { VASTU_ZONES_8 } from '@/domains/vastu/services/zones';
import { calculateBrahmasthan } from '@/domains/vastu/services/brahmasthan';

const CM_TO_M = 0.01;
const OVERLAY_HEIGHT = 0.05; // 5cm above floor
const SEGMENTS_PER_ZONE = 16;

export const VastuOverlay3D: React.FC = () => {
  const planBoundary = useAppStore((s) => s.planBoundary);

  const { brahmasthan, radius } = useMemo(() => {
    if (!planBoundary || planBoundary.length < 3) return { brahmasthan: null, radius: 0 };
    const center = calculateBrahmasthan(planBoundary);
    const maxDist = planBoundary.reduce((max, p) => Math.max(max, Math.hypot(p.x - center.x, p.y - center.y)), 0);
    return { brahmasthan: center, radius: maxDist * CM_TO_M };
  }, [planBoundary]);

  if (!brahmasthan) return null;
  const centerX = brahmasthan.x * CM_TO_M;
  const centerZ = -brahmasthan.y * CM_TO_M;

  return (
    <group position={[0, OVERLAY_HEIGHT, 0]}>
      {VASTU_ZONES_8.map((zone) => (
        <ZoneMesh3D
          key={zone.direction}
          centerX={centerX}
          centerZ={centerZ}
          radius={radius}
          startAngle={zone.startAngle}
          spanAngle={zone.spanAngle}
          color={zone.color}
        />
      ))}
    </group>
  );
};

const ZoneMesh3D: React.FC<{
  centerX: number;
  centerZ: number;
  radius: number;
  startAngle: number;
  spanAngle: number;
  color: string;
}> = React.memo(({ centerX, centerZ, radius, startAngle, spanAngle, color }) => {
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const vertices: number[] = [];
    for (let i = 0; i < SEGMENTS_PER_ZONE; i++) {
      const a1 = startAngle + (i / SEGMENTS_PER_ZONE) * spanAngle;
      const a2 = startAngle + ((i + 1) / SEGMENTS_PER_ZONE) * spanAngle;
      vertices.push(centerX, 0, centerZ); // fan center
      vertices.push(centerX + radius * Math.cos(a1), 0, centerZ - radius * Math.sin(a1)); // 2D‑Y → 3D‑(−Z)
      vertices.push(centerX + radius * Math.cos(a2), 0, centerZ - radius * Math.sin(a2));
    }
    geo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geo.computeVertexNormals();
    return geo;
  }, [centerX, centerZ, radius, startAngle, spanAngle]);

  return (
    <mesh geometry={geometry}>
      {/* depthWrite off so overlapping zones blend predictably; DoubleSide so it's visible from below */}
      <meshBasicMaterial color={color} transparent opacity={0.25} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  );
});

ZoneMesh3D.displayName = 'ZoneMesh3D';
```

> **Wire it in (small edit to `SceneContent.tsx`).** Add
> `import { VastuOverlay3D } from './VastuOverlay3D';` and the store read
> `const showVastu = useAppStore((s) => s.showVastuOverlay3D);` (import `useAppStore`), then
> render `{showVastu && <VastuOverlay3D />}` as the last child of the `<group>`. This is the
> overlay the Part 8 `SceneContent` referenced but couldn't yet include.

---

## End of Installment 3 (Parts 12–15)

Collision, both camera rigs, the full Vastu math chain, and both overlays are now in place
and wired. The previously‑orphaned Vastu analysis runs through `useVastuAnalysis` (mount it
next to `useRoomDetection`), the plan boundary is derived from the walls, and the 3D scene
finally includes its overlay.

**Installment 4 — Hardening & delivery (Parts 16–31)** is next: barrels & event bus,
performance & scaling, error boundaries, undo/redo, persistence, accessibility, input
validation, loading/empty states, the complete OBB wall collision, and touch/responsive
input — **with all `*.test.*` files and the test‑only parts (18, 29, 30, 31) omitted**, per
your request to validate via 3D rendering.

## Installment 4 — Hardening & Delivery (Parts 16–31)

> **Test scripts omitted by request.** You're validating through 3D rendering, so the
> test‑only parts (**18, 29, 30, 31**) and every `*.test.ts(x)` file from Parts 21–23 are
> intentionally left out. All the production code from those parts is kept. Where the
> original referenced a renamed function, the references below are corrected
> (`findIntersections` → `findWallIntersections`, etc.).

---

## PART 16: Performance Optimization

These are patterns, not new files — apply them to the components you already built. Each is
self‑contained and safe to adopt incrementally.

### Surgical store selectors (the single biggest win)

Subscribe to the *smallest* slice a component needs, so unrelated state changes don't
re‑render it.

```typescript
import { shallow } from 'zustand/shallow';
import { useAppStore } from '@/store';

// ❌ Re‑renders on ANY state change.
const bad = useAppStore();

// ✅ Re‑renders only when the count changes.
const wallCount = useAppStore((s) => Object.keys(s.walls).length);

// ✅ A list of ids with shallow equality; children subscribe to their own item.
const wallIds = useAppStore((s) => Object.keys(s.walls), shallow);
```

### Instanced meshes for repeated furniture

When the same model appears many times, render them in one draw call.

```typescript
import { InstancedMesh, Matrix4, Vector3, Quaternion } from 'three';
import type { Point2D } from '@/types/geometry';

/** Builds one InstancedMesh from N transforms — O(1) draw calls instead of O(n). */
export function createFurnitureInstances(
  geometry: THREE.BufferGeometry,
  material: THREE.Material,
  transforms: Array<{ position: Vector3; rotation: number; scale: number }>
): InstancedMesh {
  const mesh = new InstancedMesh(geometry, material, transforms.length);
  const matrix = new Matrix4();
  const position = new Vector3();
  const quaternion = new Quaternion();
  const scale = new Vector3();
  transforms.forEach((t, i) => {
    position.copy(t.position);
    quaternion.setFromAxisAngle(new Vector3(0, 1, 0), t.rotation);
    scale.setScalar(t.scale);
    matrix.compose(position, quaternion, scale);
    mesh.setMatrixAt(i, matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  return mesh;
}
```

### Batch static walls into one geometry

```typescript
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { createWallGeometry } from '@/domains/viewer/services/extrusion';
import type { Point2D } from '@/types/geometry';

/** Merge "locked" (non‑editing) walls into a single buffer to cut draw calls. */
export function batchWallGeometries(
  walls: Array<{ start: Point2D; end: Point2D; thickness: number; height: number }>
): THREE.BufferGeometry | null {
  const geometries = walls
    .map((w) => createWallGeometry(w.start, w.end, w.thickness, w.height))
    .filter((g) => g.attributes.position && g.attributes.position.count > 0);
  return geometries.length ? mergeGeometries(geometries, false) : null;
}
```

> Note: in current Three.js the helper is `mergeGeometries` (older docs say
> `mergeBufferGeometries`). After building any **custom** geometry, call
> `geometry.computeBoundingSphere()` so R3F's frustum culling works correctly.

### Quick reference

| Layer | Memoize | Why |
|-------|---------|-----|
| Store selectors | derived arrays/objects (`shallow`) | avoid reference‑inequality re‑renders |
| Geometry | `useMemo` on BufferGeometry | don't rebuild GPU buffers each frame |
| Materials | global cache (`getMaterial`) | one GPU upload per material |
| Components | `React.memo` on leaves | skip render when props are equal |

---

## PART 17: Scaling — Barrels & Event Bus

### The domain rule

`src/domains/[domain]/` keeps `components/`, `hooks/`, `services/`, `constants.ts`, and a
public `index.ts`. **Domains talk only through the store or through these public barrels —
never by importing another domain's component directly.**

### Part 17, Step 1: Editor public API — **`src/domains/editor/services/index.ts`** (new)

Exports use the **corrected** names from Installment 1 (`findWallIntersections`,
`splitWallAtPoint`).

```typescript
// src/domains/editor/services/index.ts — public API

export { computeWallQuad } from './geometry';
export { detectRooms, computeSignedArea, validateRoomPolygon } from './roomDetection';
export { findWallIntersections, splitWallAtPoint, computeCornerAngles } from './wallOps';
export { applySnapping, snapToGrid, snapToEndpoint } from '../hooks/useSnapping';
export { aabbOverlaps, obbIntersects, furnitureToAABB, SpatialHashGrid } from './collision';
```

### Part 17, Step 2: Vastu public API — **`src/domains/vastu/services/index.ts`** (new)

`getZoneForPoint` from the original is **not** re‑exported (it was consolidated into
`getRoomDirection`); `computePlanBoundary` is added.

```typescript
// src/domains/vastu/services/index.ts — public API

export { calculateBrahmasthan, calculateBrahmasthanZone } from './brahmasthan';
export { VASTU_ZONES_8, getRoomDirection, type VastuDirection, type VastuZone } from './zones';
export { computeVastuScore, type VastuScore } from './scoring';
export { computePlanBoundary } from './planBoundary';
export { DIRECTION_VECTORS_16, angularMidpoint, isAngleInSector } from './vectors';
```

### Part 17, Step 3: Event bus — **`src/utils/eventBus.ts`** (new)

A tiny pub/sub for cross‑domain notifications that don't belong in the store (e.g. "a wall
was added, rebuild its geometry").

```typescript
// src/utils/eventBus.ts

type EventHandler<T = unknown> = (payload: T) => void;

class EventBus {
  private handlers = new Map<string, Set<EventHandler>>();

  /** Subscribe; returns an unsubscribe function. */
  on<T>(event: string, handler: EventHandler<T>): () => void {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(handler as EventHandler);
    return () => this.handlers.get(event)?.delete(handler as EventHandler);
  }

  emit<T>(event: string, payload: T): void {
    this.handlers.get(event)?.forEach((handler) => handler(payload));
  }
}

export const eventBus = new EventBus();
// Editor:  eventBus.emit('wall:added', { wallId });
// Viewer:  eventBus.on<{ wallId: string }>('wall:added', ({ wallId }) => rebuild(wallId));
```

> Other scaling levers (use as needed): lazy‑load the viewer bundle with
> `React.lazy(() => import('./domains/viewer/...'))`, move `detectRooms`/`computeVastuScore`
> into a Web Worker if plans get very large, and rely on the persistence middleware from
> Part 23 for autosave.

---

## PART 18: Testing Strategy — omitted

Skipped per your request (you're validating through 3D rendering). If you later want a test
suite, it would live in `__tests__/` folders beside each service and run under Vitest; ask
and I'll generate it as a separate document.

---

## PART 19: Production Deployment

### Part 19, Step 1: Environment config — **`src/utils/env.ts`** (new)

Centralizes all `import.meta.env` reads so the rest of the app never touches `import.meta`
directly.

```typescript
// src/utils/env.ts

export const config = {
  apiUrl: import.meta.env.VITE_API_URL ?? '',
  assetsCdn: import.meta.env.VITE_ASSETS_CDN ?? '',
  sentryDsn: import.meta.env.VITE_SENTRY_DSN ?? '',
  analyticsId: import.meta.env.VITE_ANALYTICS_ID ?? '',
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
} as const;
```

```bash
# .env.production
VITE_API_URL=https://api.homequest.app
VITE_ASSETS_CDN=https://assets.homequest.app
VITE_SENTRY_DSN=https://xxx@sentry.io/xxx
VITE_ANALYTICS_ID=G-XXXXXXXXXX
```

### Part 19, Step 2: Error monitoring — **`src/app/monitoring.ts`** (new)

Requires `@sentry/react`. No‑ops outside production or when no DSN is set, so it's safe to
call unconditionally from `main.tsx`.

```typescript
// src/app/monitoring.ts

import * as Sentry from '@sentry/react';
import { config } from '@/utils/env';

export function initMonitoring(): void {
  if (!config.isProd || !config.sentryDsn) return;
  Sentry.init({
    dsn: config.sentryDsn,
    integrations: [Sentry.browserTracingIntegration(), Sentry.replayIntegration()],
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0.01,
    replaysOnErrorSampleRate: 1.0,
  });
}

/** Lightweight performance marks for critical flows (visible in Sentry Performance). */
export function markFlowStart(name: string): void {
  performance.mark(`${name}-start`);
}
export function markFlowEnd(name: string): void {
  performance.mark(`${name}-end`);
  performance.measure(name, `${name}-start`, `${name}-end`);
}
```

### Part 19, Step 3: Hosting & build config

**`vercel.json`** (new) — long‑cache static assets, SPA rewrite:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "headers": [
    { "source": "/models/(.*)", "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }] },
    { "source": "/textures/(.*)", "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }] }
  ],
  "rewrites": [{ "source": "/((?!api|models|textures).*)", "destination": "/index.html" }]
}
```

**`vite.config.ts`** (modify) — production chunking and terser. Merge the `build` block into
your existing config (which already has the `@` alias and `assetsInclude` from the
foundation):

```typescript
build: {
  target: 'esnext',
  minify: 'terser',
  terserOptions: { compress: { drop_console: true, drop_debugger: true } },
  rollupOptions: {
    output: {
      manualChunks: {
        'vendor-react': ['react', 'react-dom'],
        'vendor-three': ['three'],
        'vendor-r3f': ['@react-three/fiber', '@react-three/drei'],
        'vendor-state': ['zustand', 'immer'],
      },
    },
  },
  chunkSizeWarningLimit: 1000,
  assetsInlineLimit: 4096,
},
```

---

## PART 20: Final Architecture (test folders removed)

This is the end‑state tree reflecting the **renamed/added** files from this rewrite and
**omitting all `__tests__/` folders** (you're testing via rendering). Differences from the
original final tree: `useDrawing.ts` → `useWallDrawing.ts`, added `useRoomDetection.ts`,
`useMaterial.ts`, `useVastuAnalysis.ts`, `planBoundary.ts`, and the service barrels.

```
src/
├── app/
│   ├── App.tsx                 # error boundaries + lazy domains (Part 21)
│   ├── main.tsx
│   ├── monitoring.ts           # Part 19
│   ├── ErrorBoundary.tsx       # Part 21
│   ├── hooks/useKeyboardShortcuts.ts  # Part 22
│   └── fallbacks/{Editor,Viewer,Vastu}Fallback.tsx  # Part 21
├── domains/
│   ├── editor/
│   │   ├── components/ {EditorCanvas,GridLayer,WallLayer,RoomLayer,FurnitureLayer,SelectionLayer,DrawingPreview}.tsx
│   │   ├── hooks/ {useSnapping,usePan,useWallDrawing,useRoomDetection,useKeyboardEditor}.ts
│   │   ├── services/ {geometry,roomDetection,wallOps,collision,safeGeometry,index}.ts
│   │   └── constants.ts
│   ├── viewer/
│   │   ├── components/ {ViewerCanvas,SceneEnvironment,SceneContent,WallMesh,FloorMesh,FurnitureModel,CameraController,VastuOverlay3D}.tsx
│   │   ├── hooks/ {useOrbitCamera,useFirstPerson,useAssetLoader,useSafeAssetLoader,useMaterial}.ts
│   │   └── services/ {extrusion,transform,materials}.ts
│   ├── vastu/
│   │   ├── components/ {VastuPanel,VastuOverlay2D}.tsx
│   │   ├── hooks/ useVastuAnalysis.ts
│   │   └── services/ {brahmasthan,zones,scoring,vectors,planBoundary,index}.ts
│   └── shared/
│       └── components/ {Toolbar,ScreenReaderAnnouncer}.tsx
├── store/
│   ├── index.ts
│   ├── slices/ {editorSlice,viewerSlice,vastuSlice,uiSlice,historySlice}.ts
│   ├── selectors/ editorSelectors.ts
│   ├── history/ {commands,historyManager}.ts
│   └── persistence/ {persistConfig,migrations,fileIO,validation}.ts
├── types/ {geometry,editor}.ts
└── utils/ {math,id,env,eventBus,errors}.ts
```

---

## PART 21: Error Boundaries & Error Handling

Layered safety: typed error classes → a reusable `ErrorBoundary` → per‑domain fallback UIs
→ safe geometry/asset wrappers → the `App` root that ties them together. We build leaves
first; the `App` (which composes everything) comes last. `@sentry/react` is required (the
same dep Part 19 uses).

### Part 21, Step 1: Typed errors — **`src/utils/errors.ts`** (new)

```typescript
// src/utils/errors.ts

/** Base for all app errors — carries a code, structured context, and a recoverable flag. */
export class AppError extends Error {
  readonly code: string;
  readonly context: Record<string, unknown>;
  readonly recoverable: boolean;

  constructor(message: string, code: string, context: Record<string, unknown> = {}, recoverable = true) {
    super(message);
    this.name = 'AppError';
    this.code = code;
    this.context = context;
    this.recoverable = recoverable;
  }
}

export class GeometryError extends AppError {
  constructor(message: string, context: Record<string, unknown> = {}) {
    super(message, 'GEOMETRY_ERROR', context, true);
    this.name = 'GeometryError';
  }
}

export class AssetLoadError extends AppError {
  constructor(assetPath: string, cause?: Error) {
    super(`Failed to load asset: ${assetPath}`, 'ASSET_LOAD_ERROR', { assetPath, originalError: cause?.message }, true);
    this.name = 'AssetLoadError';
  }
}

export class StoreCorruptionError extends AppError {
  constructor(sliceName: string, details: string) {
    super(`Store corruption in ${sliceName}: ${details}`, 'STORE_CORRUPTION', { sliceName, details }, false);
    this.name = 'StoreCorruptionError';
  }
}

export class VastuCalculationError extends AppError {
  constructor(message: string, context: Record<string, unknown> = {}) {
    super(message, 'VASTU_CALC_ERROR', context, true);
    this.name = 'VastuCalculationError';
  }
}
```

### Part 21, Step 2: Loading spinner — **`src/domains/shared/components/LoadingSpinner.tsx`** (new — was missing)

`App` imported this but it was never written. A minimal accessible spinner used as a
Suspense fallback.

```typescript
// src/domains/shared/components/LoadingSpinner.tsx

import React from 'react';

interface LoadingSpinnerProps {
  label?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ label = 'Loading…' }) => (
  <div className="flex flex-col items-center justify-center h-full w-full bg-neutral-900 text-neutral-300 gap-3" role="status" aria-live="polite">
    <span className="inline-block w-8 h-8 border-2 border-neutral-600 border-t-blue-500 rounded-full animate-spin" aria-hidden="true" />
    <span className="text-sm">{label}</span>
  </div>
);
```

### Part 21, Step 3: Error boundary — **`src/app/ErrorBoundary.tsx`** (new)

```typescript
// src/app/ErrorBoundary.tsx

import React, { Component, ErrorInfo, ReactNode } from 'react';
import * as Sentry from '@sentry/react';
import { AppError } from '@/utils/errors';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback: ReactNode | ((error: Error, reset: () => void) => ReactNode);
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  level: 'global' | 'domain' | 'component';
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    Sentry.withScope((scope) => {
      scope.setLevel(this.props.level === 'global' ? 'fatal' : 'error');
      scope.setTag('boundary_level', this.props.level);
      if (error instanceof AppError) {
        scope.setTag('error_code', error.code);
        scope.setExtra('error_context', error.context);
        scope.setExtra('recoverable', error.recoverable);
      }
      scope.setExtra('componentStack', errorInfo.componentStack);
      Sentry.captureException(error);
    });
    this.props.onError?.(error, errorInfo);
  }

  reset = (): void => this.setState({ hasError: false, error: null });

  render(): ReactNode {
    if (this.state.hasError) {
      const { fallback } = this.props;
      return typeof fallback === 'function' ? fallback(this.state.error!, this.reset) : fallback;
    }
    return this.props.children;
  }
}
```

### Part 21, Step 4: Fallback UIs — **`src/app/fallbacks/*.tsx`** (new)

```typescript
// src/app/fallbacks/EditorFallback.tsx

import React from 'react';

export const EditorFallback: React.FC<{ error: Error; reset: () => void }> = ({ error, reset }) => (
  <div className="flex flex-col items-center justify-center h-full bg-neutral-900 text-white p-8" role="alert" aria-live="assertive">
    <h2 className="text-xl font-semibold mb-2">Editor encountered an error</h2>
    <p className="text-neutral-400 mb-4 text-center max-w-md">
      {error.message || 'An unexpected error occurred in the floor plan editor.'}
    </p>
    <div className="flex gap-3">
      <button onClick={reset} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md" aria-label="Retry loading the editor">Try Again</button>
      <button onClick={() => window.location.reload()} className="px-4 py-2 bg-neutral-700 hover:bg-neutral-600 rounded-md" aria-label="Reload the page">Reload Page</button>
    </div>
  </div>
);
```

```typescript
// src/app/fallbacks/ViewerFallback.tsx

import React from 'react';

export const ViewerFallback: React.FC<{ error: Error; reset: () => void }> = ({ error, reset }) => (
  <div className="flex flex-col items-center justify-center h-full bg-black text-white p-8" role="alert" aria-live="assertive">
    <h2 className="text-xl font-semibold mb-2">3D Viewer Error</h2>
    <p className="text-neutral-400 mb-4 text-center max-w-md">
      The 3D viewer failed to render — likely a WebGL or model‑loading issue.
    </p>
    <p className="text-neutral-500 text-sm mb-4 font-mono">{error.message}</p>
    <button onClick={reset} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md">Retry</button>
  </div>
);
```

```typescript
// src/app/fallbacks/VastuFallback.tsx

import React from 'react';

export const VastuFallback: React.FC<{ error: Error; reset: () => void }> = ({ error, reset }) => (
  <div className="p-4 bg-yellow-900/20 border border-yellow-700 rounded-md" role="alert">
    <p className="text-yellow-300 text-sm">Vastu analysis temporarily unavailable.</p>
    <button onClick={reset} className="text-yellow-400 underline text-xs mt-1">Retry</button>
  </div>
);
```

### Part 21, Step 5: Safe geometry — **`src/domains/editor/services/safeGeometry.ts`** (new)

Guards against `NaN`/`Infinity` and out‑of‑bounds coordinates poisoning the math.

```typescript
// src/domains/editor/services/safeGeometry.ts

import type { Point2D } from '@/types/geometry';
import { GeometryError } from '@/utils/errors';

const MAX_COORD = 1_000_000; // 10km in cm

/** Throws if a point is non‑finite or absurdly far from origin; otherwise returns it. */
export function validatePoint(point: Point2D, label = 'point'): Point2D {
  if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) {
    throw new GeometryError(`Invalid ${label}: non-finite value`, { point, label });
  }
  if (Math.abs(point.x) > MAX_COORD || Math.abs(point.y) > MAX_COORD) {
    throw new GeometryError(`${label} exceeds max coordinate bounds`, { point, maxAllowed: MAX_COORD });
  }
  return point;
}

/** Division that returns a fallback instead of Infinity/NaN. */
export function safeDivide(numerator: number, denominator: number, fallback = 0): number {
  if (Math.abs(denominator) < Number.EPSILON) return fallback;
  const result = numerator / denominator;
  return Number.isFinite(result) ? result : fallback;
}

/** Validates vertex count and that every vertex is finite/in‑bounds. */
export function validatePolygon(vertices: Point2D[], minVertices = 3, label = 'polygon'): void {
  if (vertices.length < minVertices) {
    throw new GeometryError(`${label} needs ≥${minVertices} vertices, got ${vertices.length}`, { vertexCount: vertices.length, minVertices });
  }
  vertices.forEach((v, i) => validatePoint(v, `${label}[${i}]`));
}

/** Runs a geometry op, returning null (and warning) on GeometryError; re‑throws others. */
export function safeGeometryOp<T>(operation: () => T, context: string): T | null {
  try {
    return operation();
  } catch (error) {
    if (error instanceof GeometryError) {
      console.warn(`[Geometry] ${context}:`, error.message, error.context);
      return null;
    }
    throw error;
  }
}
```

### Part 21, Step 6: Safe asset loader — **`src/domains/viewer/hooks/useSafeAssetLoader.ts`** (new)

Adds the missing `import React` (the original used `React.FC`/JSX without it) and reports
load failures to Sentry while returning a visible placeholder.

```typescript
// src/domains/viewer/hooks/useSafeAssetLoader.ts

import React, { useState, useMemo } from 'react';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import * as Sentry from '@sentry/react';
import { AssetLoadError } from '@/utils/errors';

interface AssetLoadState {
  model: THREE.Group | null;
  isLoading: boolean;
  error: AssetLoadError | null;
  retry: () => void;
}

/** Safe wrapper around useGLTF: returns an error state + retry instead of crashing. */
export function useSafeAssetLoader(path: string): AssetLoadState {
  const [retryCount, setRetryCount] = useState(0);
  const retry = () => setRetryCount((c) => c + 1);

  try {
    const { scene } = useGLTF(path);
    const model = useMemo(() => {
      const clone = scene.clone(true);
      clone.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.castShadow = true;
          child.receiveShadow = true;
        }
      });
      return clone as THREE.Group;
    }, [scene, retryCount]);
    return { model, isLoading: false, error: null, retry };
  } catch (e) {
    const assetError = new AssetLoadError(path, e instanceof Error ? e : undefined);
    Sentry.captureException(assetError);
    return { model: null, isLoading: false, error: assetError, retry };
  }
}

/** Semi‑transparent wireframe box shown when a model fails to load. */
export const AssetPlaceholder: React.FC<{ width: number; depth: number; height?: number }> = ({ width, depth, height = 80 }) => {
  const CM_TO_M = 0.01;
  return (
    <mesh>
      <boxGeometry args={[width * CM_TO_M, height * CM_TO_M, depth * CM_TO_M]} />
      <meshStandardMaterial color="#ff6b6b" transparent opacity={0.4} wireframe />
    </mesh>
  );
};
```

### Part 21, Step 7: App root — **`src/app/App.tsx`** (modify)

Composes the boundaries and lazy‑loads each domain. **Fix vs the original:** the components
are *named* exports, so `lazy()` must map them to `default` (otherwise React throws "does
not export default"). `LoadingSpinner` now exists (Step 2). `VastuPanel`/`Toolbar` are built
in Part 24 — lazy loading means the import only resolves at runtime, so build those before
running the app.

```typescript
// src/app/App.tsx

import React, { Suspense, lazy } from 'react';
import { ErrorBoundary } from './ErrorBoundary';
import { EditorFallback } from './fallbacks/EditorFallback';
import { ViewerFallback } from './fallbacks/ViewerFallback';
import { VastuFallback } from './fallbacks/VastuFallback';
import { LoadingSpinner } from '@/domains/shared/components/LoadingSpinner';

// Named exports → map to { default } so React.lazy accepts them.
const EditorCanvas = lazy(() =>
  import('@/domains/editor/components/EditorCanvas').then((m) => ({ default: m.EditorCanvas }))
);
const ViewerCanvas = lazy(() =>
  import('@/domains/viewer/components/ViewerCanvas').then((m) => ({ default: m.ViewerCanvas }))
);
const VastuPanel = lazy(() =>
  import('@/domains/vastu/components/VastuPanel').then((m) => ({ default: m.VastuPanel }))
);

export const App: React.FC = () => (
  <ErrorBoundary
    level="global"
    fallback={(error, reset) => (
      <div className="flex items-center justify-center h-screen bg-neutral-950 text-white">
        <div className="text-center">
          <h1 className="text-2xl mb-4">Something went wrong</h1>
          <p className="text-neutral-400 mb-4">{error.message}</p>
          <button onClick={reset} className="px-4 py-2 bg-blue-600 rounded">Restart Application</button>
        </div>
      </div>
    )}
  >
    <div className="h-screen flex flex-col">
      <header className="h-12 bg-neutral-800 border-b border-neutral-700" role="banner" />
      <main className="flex-1 flex" role="main">
        <section className="flex-1" aria-label="2D Floor Plan Editor">
          <ErrorBoundary level="domain" fallback={(e, r) => <EditorFallback error={e} reset={r} />}>
            <Suspense fallback={<LoadingSpinner label="Loading editor…" />}>
              <EditorCanvas />
            </Suspense>
          </ErrorBoundary>
        </section>
        <section className="flex-1" aria-label="3D Visualization">
          <ErrorBoundary level="domain" fallback={(e, r) => <ViewerFallback error={e} reset={r} />}>
            <Suspense fallback={<LoadingSpinner label="Loading 3D viewer…" />}>
              <ViewerCanvas />
            </Suspense>
          </ErrorBoundary>
        </section>
        <aside className="w-80" aria-label="Vastu Analysis">
          <ErrorBoundary level="domain" fallback={(e, r) => <VastuFallback error={e} reset={r} />}>
            <Suspense fallback={<LoadingSpinner label="Loading analysis…" />}>
              <VastuPanel />
            </Suspense>
          </ErrorBoundary>
        </aside>
      </main>
    </div>
  </ErrorBoundary>
);
```

---

## PART 22: Undo/Redo System

A command stack: each mutation is a reversible `Command` with `execute()`/`undo()`. Build
the command types → the manager → the Zustand slice → the keyboard shortcuts.

### Part 22, Step 1: Command types — **`src/store/history/commands.ts`** (new)

```typescript
// src/store/history/commands.ts

import type { Point2D, EntityId } from '@/types';
import type { Wall, Vertex, FurnitureItem, Room } from '@/types/editor';

/** A reversible operation. Carries enough data to go both directions. */
export interface Command {
  readonly type: string;
  readonly label: string; // shown in the UI ("Undo Add Wall")
  readonly timestamp: number;
  execute(): void;
  undo(): void;
}

export interface AddWallCommand extends Command {
  type: 'ADD_WALL';
  wallId: EntityId;
  startVertexId: EntityId;
  endVertexId: EntityId;
  wall: Wall;
  startVertex: Vertex;
  endVertex: Vertex;
  createdVertexIds: EntityId[];
}

export interface RemoveWallCommand extends Command {
  type: 'REMOVE_WALL';
  wall: Wall;
  startVertex: Vertex;
  endVertex: Vertex;
  affectedRooms: Room[];
}

export interface MoveVertexCommand extends Command {
  type: 'MOVE_VERTEX';
  vertexId: EntityId;
  oldPosition: Point2D;
  newPosition: Point2D;
}

export interface AddFurnitureCommand extends Command {
  type: 'ADD_FURNITURE';
  item: FurnitureItem;
}

export interface RemoveFurnitureCommand extends Command {
  type: 'REMOVE_FURNITURE';
  item: FurnitureItem;
}

export interface MoveFurnitureCommand extends Command {
  type: 'MOVE_FURNITURE';
  itemId: EntityId;
  oldPosition: Point2D;
  newPosition: Point2D;
}

export interface RotateFurnitureCommand extends Command {
  type: 'ROTATE_FURNITURE';
  itemId: EntityId;
  oldRotation: number;
  newRotation: number;
}

export interface SetRoomTypeCommand extends Command {
  type: 'SET_ROOM_TYPE';
  roomId: EntityId;
  oldType: string;
  newType: string;
}

export interface BatchCommand extends Command {
  type: 'BATCH';
  commands: Command[];
}
```

### Part 22, Step 2: History manager — **`src/store/history/historyManager.ts`** (new)

```typescript
// src/store/history/historyManager.ts

import type { Command } from './commands';

const MAX_HISTORY_SIZE = 100;

/**
 * Past/future command stacks. Commands (not full snapshots) are stored, so memory stays
 * small. Batches group related ops (e.g. a wall split = create vertex + 2 walls) into one
 * undo unit. Starting a new action clears the redo (future) stack.
 */
export class HistoryManager {
  private past: Command[] = [];
  private future: Command[] = [];
  private batchQueue: Command[] | null = null;

  constructor(private maxSize = MAX_HISTORY_SIZE) {}

  execute(command: Command): void {
    command.execute();
    if (this.batchQueue) {
      this.batchQueue.push(command);
      return;
    }
    this.past.push(command);
    this.future = [];
    if (this.past.length > this.maxSize) this.past.shift();
  }

  undo(): boolean {
    const command = this.past.pop();
    if (!command) return false;
    command.undo();
    this.future.push(command);
    return true;
  }

  redo(): boolean {
    const command = this.future.pop();
    if (!command) return false;
    command.execute();
    this.past.push(command);
    return true;
  }

  beginBatch(_label: string): void {
    this.batchQueue = [];
  }

  endBatch(label: string): void {
    if (!this.batchQueue || this.batchQueue.length === 0) {
      this.batchQueue = null;
      return;
    }
    const commands = [...this.batchQueue];
    this.batchQueue = null;
    const batch: Command = {
      type: 'BATCH',
      label,
      timestamp: Date.now(),
      execute: () => commands.forEach((c) => c.execute()),
      undo: () => [...commands].reverse().forEach((c) => c.undo()),
    };
    this.past.push(batch);
    this.future = [];
    if (this.past.length > this.maxSize) this.past.shift();
  }

  cancelBatch(): void {
    if (!this.batchQueue) return;
    [...this.batchQueue].reverse().forEach((c) => c.undo());
    this.batchQueue = null;
  }

  get canUndo(): boolean { return this.past.length > 0; }
  get canRedo(): boolean { return this.future.length > 0; }
  get undoLabel(): string | null { return this.past.at(-1)?.label ?? null; }
  get redoLabel(): string | null { return this.future.at(-1)?.label ?? null; }
  get historySize(): number { return this.past.length; }

  clear(): void {
    this.past = [];
    this.future = [];
    this.batchQueue = null;
  }
}
```

### Part 22, Step 3: History slice — **`src/store/slices/historySlice.ts`** (new)

The store composition in Part 4 already includes `createHistorySlice`; this is its
implementation. It mirrors the manager's flags into reactive state so the toolbar can
enable/disable the undo/redo buttons.

```typescript
// src/store/slices/historySlice.ts

import type { StateCreator } from 'zustand';
import type { AppStore } from '..';
import { HistoryManager } from '../history/historyManager';
import type { Command } from '../history/commands';

const historyManager = new HistoryManager(100);

export interface HistorySlice {
  canUndo: boolean;
  canRedo: boolean;
  undoLabel: string | null;
  redoLabel: string | null;
  executeCommand: (command: Command) => void;
  undo: () => void;
  redo: () => void;
  beginBatch: (label: string) => void;
  endBatch: (label: string) => void;
  cancelBatch: () => void;
  clearHistory: () => void;
}

export const createHistorySlice: StateCreator<
  AppStore,
  [['zustand/immer', never], ['zustand/devtools', never]],
  [],
  HistorySlice
> = (set) => {
  const syncFlags = (state: HistorySlice) => {
    state.canUndo = historyManager.canUndo;
    state.canRedo = historyManager.canRedo;
    state.undoLabel = historyManager.undoLabel;
    state.redoLabel = historyManager.redoLabel;
  };

  return {
    canUndo: false,
    canRedo: false,
    undoLabel: null,
    redoLabel: null,

    executeCommand: (command) => {
      historyManager.execute(command);
      set(syncFlags);
    },
    undo: () => {
      historyManager.undo();
      set(syncFlags);
    },
    redo: () => {
      historyManager.redo();
      set(syncFlags);
    },
    beginBatch: (label) => historyManager.beginBatch(label),
    endBatch: (label) => {
      historyManager.endBatch(label);
      set(syncFlags);
    },
    cancelBatch: () => historyManager.cancelBatch(),
    clearHistory: () => {
      historyManager.clear();
      set((state) => {
        state.canUndo = false;
        state.canRedo = false;
        state.undoLabel = null;
        state.redoLabel = null;
      });
    },
  };
};
```

### Part 22, Step 4: Keyboard shortcuts — **`src/app/hooks/useKeyboardShortcuts.ts`** (new)

```typescript
// src/app/hooks/useKeyboardShortcuts.ts

import { useEffect } from 'react';
import { useAppStore } from '@/store';

/** Ctrl/Cmd+Z to undo, Ctrl+Y or Ctrl/Cmd+Shift+Z to redo. Mount once near the root. */
export function useKeyboardShortcuts(): void {
  const undo = useAppStore((s) => s.undo);
  const redo = useAppStore((s) => s.redo);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isMeta = e.ctrlKey || e.metaKey;
      if (isMeta && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if ((isMeta && e.key === 'y') || (isMeta && e.shiftKey && e.key === 'z')) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [undo, redo]);
}
```

---

## PART 23: Persistence Layer

Auto‑save to IndexedDB plus manual JSON export/import, with schema migrations and import
validation. Requires `idb-keyval`. Order: storage adapter → migrations → store update →
validation → file I/O (file I/O imports validation, so validation comes first).

### Part 23, Step 1: IndexedDB adapter — **`src/store/persistence/persistConfig.ts`** (new)

```typescript
// src/store/persistence/persistConfig.ts

import type { StateStorage } from 'zustand/middleware';
import { get, set, del } from 'idb-keyval';

/**
 * IndexedDB-backed storage for Zustand's persist middleware. Chosen over localStorage:
 * no ~5MB cap, async (won't block the main thread), and works in workers.
 */
export const indexedDBStorage: StateStorage = {
  getItem: async (name) => {
    try {
      return (await get(name)) ?? null;
    } catch (error) {
      console.error('[Persistence] read failed:', error);
      return null;
    }
  },
  setItem: async (name, value) => {
    try {
      await set(name, value);
    } catch (error) {
      console.error('[Persistence] write failed:', error);
    }
  },
  removeItem: async (name) => {
    try {
      await del(name);
    } catch (error) {
      console.error('[Persistence] delete failed:', error);
    }
  },
};
```

### Part 23, Step 2: Schema migrations — **`src/store/persistence/migrations.ts`** (new)

```typescript
// src/store/persistence/migrations.ts

import type { EntityId, Vertex, Wall, Room, FurnitureItem } from '@/types';

/** Bump this whenever the persisted shape changes. */
export const CURRENT_SCHEMA_VERSION = 3;

export interface PersistedStateV1 {
  version: 1;
  vertices: Record<EntityId, Vertex>;
  walls: Record<EntityId, Wall>;
  rooms: Record<EntityId, Room>;
}
export interface PersistedStateV2 extends Omit<PersistedStateV1, 'version'> {
  version: 2;
  furniture: Record<EntityId, FurnitureItem>;
}
export interface PersistedStateV3 extends Omit<PersistedStateV2, 'version'> {
  version: 3;
  metadata: { name: string; createdAt: string; lastModifiedAt: string; authorId: string | null };
  settings: { gridSize: number; wallThickness: number; wallHeight: number; measurementUnit: 'cm' | 'ft' | 'in' };
}
export type PersistedState = PersistedStateV3;

/** Upgrades any older persisted blob to the current shape. Each step is idempotent. */
export function migrateState(state: any): PersistedState {
  let current = state;
  if (!current.version || current.version < 2) current = migrateV1ToV2(current);
  if (current.version < 3) current = migrateV2ToV3(current);
  return current as PersistedState;
}

function migrateV1ToV2(state: PersistedStateV1): PersistedStateV2 {
  return { ...state, version: 2, furniture: {} };
}

function migrateV2ToV3(state: PersistedStateV2): PersistedStateV3 {
  return {
    ...state,
    version: 3,
    metadata: { name: 'Untitled Floor Plan', createdAt: new Date().toISOString(), lastModifiedAt: new Date().toISOString(), authorId: null },
    settings: { gridSize: 10, wallThickness: 20, wallHeight: 280, measurementUnit: 'cm' },
  };
}
```

### Part 23, Step 3: Add persistence to the store — **`src/store/index.ts`** (modify)

Wrap the existing slice composition in the `persist` middleware. `partialize` saves only
the floor‑plan data (never transient UI/history state).

```typescript
// src/store/index.ts  (updated)

import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { devtools, persist, createJSONStorage } from 'zustand/middleware';
import { type EditorSlice, createEditorSlice } from './slices/editorSlice';
import { type ViewerSlice, createViewerSlice } from './slices/viewerSlice';
import { type VastuSlice, createVastuSlice } from './slices/vastuSlice';
import { type UISlice, createUISlice } from './slices/uiSlice';
import { type HistorySlice, createHistorySlice } from './slices/historySlice';
import { indexedDBStorage } from './persistence/persistConfig';
import { migrateState, CURRENT_SCHEMA_VERSION } from './persistence/migrations';

export type AppStore = EditorSlice & ViewerSlice & VastuSlice & UISlice & HistorySlice;

export const useAppStore = create<AppStore>()(
  devtools(
    persist(
      immer((...args) => ({
        ...createEditorSlice(...args),
        ...createViewerSlice(...args),
        ...createVastuSlice(...args),
        ...createUISlice(...args),
        ...createHistorySlice(...args),
      })),
      {
        name: 'homequest-store',
        version: CURRENT_SCHEMA_VERSION,
        storage: createJSONStorage(() => indexedDBStorage),
        migrate: migrateState,
        // Persist floor‑plan data only — UI/history are transient.
        partialize: (state) => ({
          vertices: state.vertices,
          walls: state.walls,
          rooms: state.rooms,
          furniture: state.furniture,
        }),
        skipHydration: false,
      }
    ),
    { name: 'HomeQuest' }
  )
);
```

### Part 23, Step 4: Import validation — **`src/store/persistence/validation.ts`** (new)

Checks referential integrity (walls/rooms point at real vertices, finite coordinates,
etc.) before importing, so a bad file can't corrupt the store.

```typescript
// src/store/persistence/validation.ts

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/** Validates a parsed floor‑plan object. Errors block import; warnings don't. */
export function validateFloorPlanIntegrity(data: any): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!data.vertices || typeof data.vertices !== 'object') errors.push('Missing or invalid vertices field');
  if (!data.walls || typeof data.walls !== 'object') errors.push('Missing or invalid walls field');
  if (!data.rooms || typeof data.rooms !== 'object') errors.push('Missing or invalid rooms field');
  if (!data.furniture || typeof data.furniture !== 'object') errors.push('Missing or invalid furniture field');
  if (errors.length > 0) return { valid: false, errors, warnings };

  for (const [id, vertex] of Object.entries(data.vertices as Record<string, any>)) {
    const pos = vertex.position;
    if (!pos || typeof pos.x !== 'number' || typeof pos.y !== 'number') errors.push(`Vertex ${id}: invalid position`);
    else if (!Number.isFinite(pos.x) || !Number.isFinite(pos.y)) errors.push(`Vertex ${id}: non-finite coordinates`);
  }

  for (const [id, wall] of Object.entries(data.walls as Record<string, any>)) {
    if (!data.vertices[wall.startVertexId]) errors.push(`Wall ${id}: references non-existent start vertex ${wall.startVertexId}`);
    if (!data.vertices[wall.endVertexId]) errors.push(`Wall ${id}: references non-existent end vertex ${wall.endVertexId}`);
    if (wall.thickness <= 0 || wall.thickness > 200) warnings.push(`Wall ${id}: unusual thickness ${wall.thickness}cm`);
    if (wall.height <= 0 || wall.height > 2000) warnings.push(`Wall ${id}: unusual height ${wall.height}cm`);
  }

  for (const [id, room] of Object.entries(data.rooms as Record<string, any>)) {
    if (!Array.isArray(room.boundaryVertexIds)) {
      errors.push(`Room ${id}: boundaryVertexIds is not an array`);
      continue;
    }
    for (const vid of room.boundaryVertexIds) {
      if (!data.vertices[vid]) errors.push(`Room ${id}: references non-existent vertex ${vid}`);
    }
    if (room.boundaryVertexIds.length < 3) errors.push(`Room ${id}: fewer than 3 boundary vertices`);
  }

  for (const [id, item] of Object.entries(data.furniture as Record<string, any>)) {
    if (!item.position || typeof item.position.x !== 'number') errors.push(`Furniture ${id}: invalid position`);
    if (item.roomId && !data.rooms[item.roomId]) warnings.push(`Furniture ${id}: references non-existent room ${item.roomId}`);
  }

  for (const [id, vertex] of Object.entries(data.vertices as Record<string, any>)) {
    const connected = (vertex.connectedWalls || []).filter((wid: string) => data.walls[wid]);
    if (connected.length === 0) warnings.push(`Vertex ${id}: orphan (connected to no valid walls)`);
  }

  return { valid: errors.length === 0, errors, warnings };
}
```

### Part 23, Step 5: Export / import — **`src/store/persistence/fileIO.ts`** (new)

```typescript
// src/store/persistence/fileIO.ts

import { useAppStore } from '@/store';
import { type PersistedState, CURRENT_SCHEMA_VERSION, migrateState } from './migrations';
import { validateFloorPlanIntegrity } from './validation';

/** Downloads the current plan as a JSON file. */
export function exportFloorPlan(filename = 'floorplan.hq.json'): void {
  const state = useAppStore.getState();
  const exportData: PersistedState = {
    version: CURRENT_SCHEMA_VERSION,
    vertices: state.vertices,
    walls: state.walls,
    rooms: state.rooms,
    furniture: state.furniture,
    metadata: { name: filename.replace('.hq.json', ''), createdAt: new Date().toISOString(), lastModifiedAt: new Date().toISOString(), authorId: null },
    settings: { gridSize: 10, wallThickness: 20, wallHeight: 280, measurementUnit: 'cm' },
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** Reads, migrates, validates, then applies a plan file. Returns success + any error. */
export async function importFloorPlan(file: File): Promise<{ success: boolean; error?: string }> {
  try {
    const raw = JSON.parse(await file.text());
    const migrated = migrateState(raw);

    const validation = validateFloorPlanIntegrity(migrated);
    if (!validation.valid) return { success: false, error: validation.errors.join('; ') };

    useAppStore.setState({
      vertices: migrated.vertices,
      walls: migrated.walls,
      rooms: migrated.rooms,
      furniture: migrated.furniture,
    });
    useAppStore.getState().clearHistory(); // imported plan is a fresh baseline

    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof SyntaxError ? 'Invalid JSON file' : (error as Error).message,
    };
  }
}
```

---

## PART 24: Accessibility (WCAG 2.1 AA)

Make every spatial, mouse‑driven action reachable by keyboard and legible to screen
readers. Order: the screen‑reader announcer first (others call into it), then keyboard
editing, the toolbar, the Vastu panel, skip links, and a preferences hook.

> **WCAG note:** these patterns cover the common AA criteria (keyboard access, names/roles,
> non‑color cues, live regions). Full AA conformance still requires manual testing with real
> assistive tech and an expert review — code alone can't guarantee it.

### Part 24, Step 1: Live‑region announcer — **`src/domains/shared/components/ScreenReaderAnnouncer.tsx`** (new)

```typescript
// src/domains/shared/components/ScreenReaderAnnouncer.tsx

import React from 'react';

/** Two hidden live regions (polite + assertive). Mount once at the app root. */
export const ScreenReaderAnnouncer: React.FC = () => (
  <>
    <div id="sr-announcer" role="status" aria-live="polite" aria-atomic="true" className="sr-only" />
    <div id="sr-announcer-assertive" role="alert" aria-live="assertive" aria-atomic="true" className="sr-only" />
  </>
);

/** Imperatively announce a message to screen readers. */
export function announce(message: string, priority: 'polite' | 'assertive' = 'polite'): void {
  const id = priority === 'assertive' ? 'sr-announcer-assertive' : 'sr-announcer';
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = ''; // clear so the same message re‑announces
  requestAnimationFrame(() => {
    el.textContent = message;
  });
}
```

### Part 24, Step 2: Keyboard editing — **`src/domains/editor/hooks/useKeyboardEditor.ts`** (new)

Arrow keys nudge the selection (Shift = fine 1cm), Delete removes it; each move is announced.

```typescript
// src/domains/editor/hooks/useKeyboardEditor.ts

import { useEffect, useCallback } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types';

const NUDGE_AMOUNT = 10; // cm
const FINE_NUDGE = 1; // cm with Shift

export function useKeyboardEditor(): void {
  const selectedIds = useAppStore((s) => s.selectedIds);
  const moveVertex = useAppStore((s) => s.moveVertex);
  const moveFurniture = useAppStore((s) => s.moveFurniture);
  const removeWall = useAppStore((s) => s.removeWall);
  const removeFurniture = useAppStore((s) => s.removeFurniture);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Ignore when typing in a field.
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const nudge = e.shiftKey ? FINE_NUDGE : NUDGE_AMOUNT;

      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault();
          nudgeSelection(selectedIds, { x: 0, y: nudge }, moveVertex, moveFurniture);
          announcePosition('up', nudge);
          break;
        case 'ArrowDown':
          e.preventDefault();
          nudgeSelection(selectedIds, { x: 0, y: -nudge }, moveVertex, moveFurniture);
          announcePosition('down', nudge);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          nudgeSelection(selectedIds, { x: -nudge, y: 0 }, moveVertex, moveFurniture);
          announcePosition('left', nudge);
          break;
        case 'ArrowRight':
          e.preventDefault();
          nudgeSelection(selectedIds, { x: nudge, y: 0 }, moveVertex, moveFurniture);
          announcePosition('right', nudge);
          break;
        case 'Delete':
        case 'Backspace':
          e.preventDefault();
          deleteSelection(selectedIds, removeWall, removeFurniture);
          break;
      }
    },
    [selectedIds, moveVertex, moveFurniture, removeWall, removeFurniture]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

function nudgeSelection(
  ids: string[],
  delta: Point2D,
  moveVertex: (id: string, pos: Point2D) => void,
  moveFurniture: (id: string, pos: Point2D) => void
): void {
  const state = useAppStore.getState();
  for (const id of ids) {
    if (state.vertices[id]) {
      const p = state.vertices[id].position;
      moveVertex(id, { x: p.x + delta.x, y: p.y + delta.y });
    } else if (state.furniture[id]) {
      const p = state.furniture[id].position;
      moveFurniture(id, { x: p.x + delta.x, y: p.y + delta.y });
    }
  }
}

function deleteSelection(
  ids: string[],
  removeWall: (id: string) => void,
  removeFurniture: (id: string) => void
): void {
  const state = useAppStore.getState();
  for (const id of ids) {
    if (state.walls[id]) removeWall(id);
    else if (state.furniture[id]) removeFurniture(id);
  }
  useAppStore.getState().clearSelection();
}

function announcePosition(direction: string, amount: number): void {
  const el = document.getElementById('sr-announcer');
  if (el) el.textContent = `Moved ${direction} by ${amount} centimeters`;
}
```

### Part 24, Step 3: Accessible toolbar — **`src/domains/shared/components/Toolbar.tsx`** (new)

Icon buttons with `aria-label`, `aria-pressed`, and descriptions. Reads/sets `activeTool`
on the UI slice (ensure its `Tool` union includes `select | wall | furniture | pan | measure`).

```typescript
// src/domains/shared/components/Toolbar.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { announce } from './ScreenReaderAnnouncer';

type Tool = 'select' | 'wall' | 'furniture' | 'pan' | 'measure';

interface ToolConfig {
  id: Tool;
  label: string;
  shortcut: string;
  icon: string;
  description: string;
}

const TOOLS: ToolConfig[] = [
  { id: 'select', label: 'Select', shortcut: 'S', icon: '⊡', description: 'Select and move entities' },
  { id: 'wall', label: 'Draw Wall', shortcut: 'W', icon: '━', description: 'Click to place wall endpoints' },
  { id: 'furniture', label: 'Place Furniture', shortcut: 'F', icon: '▣', description: 'Choose and place furniture items' },
  { id: 'pan', label: 'Pan View', shortcut: 'H', icon: '✋', description: 'Click and drag to pan the canvas' },
  { id: 'measure', label: 'Measure', shortcut: 'M', icon: '↔', description: 'Measure distances between points' },
];

export const Toolbar: React.FC = () => {
  const activeTool = useAppStore((s) => s.activeTool);
  const setActiveTool = useAppStore((s) => s.setActiveTool);

  const handleToolChange = (tool: Tool) => {
    setActiveTool(tool);
    announce(`${TOOLS.find((t) => t.id === tool)?.label} tool activated`);
  };

  return (
    <nav aria-label="Drawing Tools" role="toolbar" className="flex gap-1 px-2">
      {TOOLS.map((tool) => (
        <button
          key={tool.id}
          onClick={() => handleToolChange(tool.id)}
          aria-label={`${tool.label} (${tool.shortcut})`}
          aria-pressed={activeTool === tool.id}
          aria-describedby={`tool-desc-${tool.id}`}
          title={`${tool.label} (${tool.shortcut})`}
          className={`w-10 h-10 flex items-center justify-center rounded-md text-lg transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 ${
            activeTool === tool.id ? 'bg-blue-600 text-white' : 'bg-neutral-700 text-neutral-300 hover:bg-neutral-600'
          }`}
        >
          {tool.icon}
          <span id={`tool-desc-${tool.id}`} className="sr-only">{tool.description}</span>
        </button>
      ))}
    </nav>
  );
};
```

### Part 24, Step 4: Accessible Vastu panel — **`src/domains/vastu/components/VastuPanel.tsx`** (new)

Reads the cached `vastuScore` (set by `useVastuAnalysis` from Installment 3). Score is shown
with text + icon, never color alone. The unused `computeVastuScore` import from the original
is dropped.

```typescript
// src/domains/vastu/components/VastuPanel.tsx

import React from 'react';
import { useAppStore } from '@/store';
import type { RoomVastuScore } from '../services/scoring';

export const VastuPanel: React.FC = () => {
  const vastuScore = useAppStore((s) => s.vastuScore);

  if (!vastuScore) {
    return (
      <div className="p-4 text-neutral-400" role="status">
        <p>Draw walls and create rooms to see Vastu analysis.</p>
      </div>
    );
  }

  return (
    <section aria-labelledby="vastu-heading" className="p-4 overflow-y-auto h-full">
      <h2 id="vastu-heading" className="text-lg font-semibold text-white mb-4">Vastu Analysis</h2>

      <div className="mb-6 p-4 rounded-lg bg-neutral-800" role="status" aria-live="polite"
        aria-label={`Overall Vastu score: ${Math.round(vastuScore.overall)} out of 100`}>
        <div className="flex items-center justify-between">
          <span className="text-neutral-300">Overall Score</span>
          <ScoreIndicator score={vastuScore.overall} />
        </div>
        <div className="mt-2 h-2 bg-neutral-700 rounded-full overflow-hidden" role="progressbar"
          aria-valuenow={Math.round(vastuScore.overall)} aria-valuemin={0} aria-valuemax={100} aria-label="Vastu compliance score">
          <div className="h-full rounded-full transition-all" style={{ width: `${vastuScore.overall}%`, backgroundColor: getScoreColor(vastuScore.overall) }} />
        </div>
      </div>

      <h3 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-3">Room Analysis</h3>
      <ul className="space-y-2" aria-label="Individual room Vastu scores">
        {Object.values(vastuScore.roomScores).map((rs) => (
          <RoomScoreCard key={rs.roomId} roomScore={rs} />
        ))}
      </ul>

      {vastuScore.recommendations.length > 0 && (
        <>
          <h3 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mt-6 mb-3">Recommendations</h3>
          <ul className="space-y-2" aria-label="Vastu recommendations">
            {vastuScore.recommendations.map((rec, i) => (
              <li key={i} className={`p-3 rounded-md text-sm ${getSeverityClasses(rec.severity)}`}>
                <span className="sr-only">{rec.severity} recommendation:</span>
                <span aria-hidden="true">{getSeverityIcon(rec.severity)}</span> {rec.message}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
};

const ScoreIndicator: React.FC<{ score: number }> = ({ score }) => {
  const rounded = Math.round(score);
  const label = score >= 80 ? 'Excellent' : score >= 60 ? 'Good' : score >= 40 ? 'Fair' : 'Poor';
  return (
    <span className="text-2xl font-bold" style={{ color: getScoreColor(score) }} aria-label={`${rounded} percent, rated ${label}`}>
      {rounded}<span className="text-sm font-normal text-neutral-400 ml-1" aria-hidden="true">/100</span>
    </span>
  );
};

const RoomScoreCard: React.FC<{ roomScore: RoomVastuScore }> = ({ roomScore }) => (
  <li className="p-3 bg-neutral-800 rounded-md"
    aria-label={`${roomScore.roomType} room: score ${roomScore.score}, direction ${roomScore.direction}`}>
    <div className="flex justify-between items-center">
      <span className="text-white capitalize">{roomScore.roomType}</span>
      <span className="flex items-center gap-2">
        <span className="text-xs text-neutral-400">{roomScore.direction}</span>
        <ScoreBadge score={roomScore.score} isIdeal={roomScore.isIdeal} />
      </span>
    </div>
    <p className="text-xs text-neutral-400 mt-1">{roomScore.reason}</p>
  </li>
);

const ScoreBadge: React.FC<{ score: number; isIdeal: boolean }> = ({ score, isIdeal }) => (
  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
    isIdeal ? 'bg-green-900 text-green-300' : score >= 70 ? 'bg-yellow-900 text-yellow-300' : 'bg-red-900 text-red-300'
  }`} aria-label={isIdeal ? 'Ideal placement' : `Score: ${score}`}>
    {isIdeal ? '✓ Ideal' : score}
  </span>
);

function getScoreColor(score: number): string {
  if (score >= 80) return '#4ade80';
  if (score >= 60) return '#facc15';
  if (score >= 40) return '#fb923c';
  return '#f87171';
}
function getSeverityClasses(severity: string): string {
  if (severity === 'critical') return 'bg-red-900/30 border border-red-700 text-red-300';
  if (severity === 'warning') return 'bg-yellow-900/30 border border-yellow-700 text-yellow-300';
  return 'bg-blue-900/30 border border-blue-700 text-blue-300';
}
function getSeverityIcon(severity: string): string {
  if (severity === 'critical') return '🔴';
  if (severity === 'warning') return '🟡';
  return '💡';
}
```

### Part 24, Step 5: Skip links & preferences (new)

```typescript
// src/domains/shared/components/SkipLinks.tsx

import React from 'react';

/** Keyboard "skip to…" links, hidden until focused. */
export const SkipLinks: React.FC = () => (
  <nav aria-label="Skip links" className="sr-only focus-within:not-sr-only focus-within:fixed focus-within:z-50 focus-within:top-0 focus-within:left-0">
    <ul className="flex gap-2 p-2 bg-blue-600">
      <li><a href="#editor-canvas" className="px-3 py-1 bg-white text-blue-600 rounded font-medium">Skip to Editor</a></li>
      <li><a href="#viewer-canvas" className="px-3 py-1 bg-white text-blue-600 rounded font-medium">Skip to 3D Viewer</a></li>
      <li><a href="#vastu-panel" className="px-3 py-1 bg-white text-blue-600 rounded font-medium">Skip to Vastu Analysis</a></li>
    </ul>
  </nav>
);
```

```typescript
// src/app/hooks/useAccessibilityPreferences.ts

import { useEffect, useState } from 'react';

export interface A11yPreferences {
  prefersReducedMotion: boolean;
  prefersHighContrast: boolean;
  prefersColorScheme: 'light' | 'dark';
}

/** Reflects OS/browser a11y settings so components can dial down motion, bump contrast, etc. */
export function useAccessibilityPreferences(): A11yPreferences {
  const [prefs, setPrefs] = useState<A11yPreferences>({
    prefersReducedMotion: false,
    prefersHighContrast: false,
    prefersColorScheme: 'dark',
  });

  useEffect(() => {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const contrast = window.matchMedia('(prefers-contrast: more)');
    const scheme = window.matchMedia('(prefers-color-scheme: light)');
    const update = () =>
      setPrefs({
        prefersReducedMotion: motion.matches,
        prefersHighContrast: contrast.matches,
        prefersColorScheme: scheme.matches ? 'light' : 'dark',
      });
    update();
    motion.addEventListener('change', update);
    contrast.addEventListener('change', update);
    scheme.addEventListener('change', update);
    return () => {
      motion.removeEventListener('change', update);
      contrast.removeEventListener('change', update);
      scheme.removeEventListener('change', update);
    };
  }, []);

  return prefs;
}
```

---

## PART 25: Input Validation & State Integrity Guards

> **Already done in Installment 1:** the original's headline fix here — making
> `splitWallAtPoint` atomic (one `setState`) — is already how it's written in Part 6. The
> original's `findIntersectionsPure` is the same function we shipped as
> `findWallIntersections`. So this part adds only the **new** guard utilities and the
> validated `addWall`.

### Part 25, Step 1: Store guards — **`src/store/guards/storeGuards.ts`** (new)

```typescript
// src/store/guards/storeGuards.ts

import type { Point2D, EntityId } from '@/types';
import type { Wall, Vertex } from '@/types/editor';

/** Pre‑flight check for addWall: rejects non‑finite, zero‑length, or absurd walls. */
export function validateAddWall(
  start: Point2D,
  end: Point2D,
  thickness: number,
  height: number
): { valid: boolean; error?: string } {
  if (!Number.isFinite(start.x) || !Number.isFinite(start.y)) return { valid: false, error: 'Start point has non-finite coordinates' };
  if (!Number.isFinite(end.x) || !Number.isFinite(end.y)) return { valid: false, error: 'End point has non-finite coordinates' };
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (dx * dx + dy * dy < 0.01) return { valid: false, error: 'Wall has zero length' };
  if (thickness <= 0 || thickness > 200) return { valid: false, error: `Invalid wall thickness: ${thickness}` };
  if (height <= 0 || height > 2000) return { valid: false, error: `Invalid wall height: ${height}` };
  return { valid: true };
}

/** Checks referential + bidirectional integrity of the wall graph. */
export function validateGraphIntegrity(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): { valid: boolean; issues: string[] } {
  const issues: string[] = [];

  for (const [wallId, wall] of Object.entries(walls)) {
    if (!vertices[wall.startVertexId]) issues.push(`Wall ${wallId}: dangling start vertex ref ${wall.startVertexId}`);
    if (!vertices[wall.endVertexId]) issues.push(`Wall ${wallId}: dangling end vertex ref ${wall.endVertexId}`);
  }
  for (const [vertexId, vertex] of Object.entries(vertices)) {
    for (const wallId of vertex.connectedWalls) {
      if (!walls[wallId]) issues.push(`Vertex ${vertexId}: dangling wall ref ${wallId}`);
    }
  }
  for (const [wallId, wall] of Object.entries(walls)) {
    const sv = vertices[wall.startVertexId];
    if (sv && !sv.connectedWalls.includes(wallId)) issues.push(`Wall ${wallId}: start vertex doesn't reference this wall`);
    const ev = vertices[wall.endVertexId];
    if (ev && !ev.connectedWalls.includes(wallId)) issues.push(`Wall ${wallId}: end vertex doesn't reference this wall`);
  }

  return { valid: issues.length === 0, issues };
}

/** Best‑effort recovery: drops dangling walls, prunes bad refs, removes orphan vertices. */
export function repairGraphIntegrity(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): { verticesRemoved: number; wallsRemoved: number; refsFixed: number } {
  let verticesRemoved = 0;
  let wallsRemoved = 0;
  let refsFixed = 0;

  for (const [wallId, wall] of Object.entries(walls)) {
    if (!vertices[wall.startVertexId] || !vertices[wall.endVertexId]) {
      delete walls[wallId];
      wallsRemoved++;
    }
  }
  for (const vertex of Object.values(vertices)) {
    const valid = vertex.connectedWalls.filter((wid) => walls[wid]);
    if (valid.length !== vertex.connectedWalls.length) {
      refsFixed += vertex.connectedWalls.length - valid.length;
      vertex.connectedWalls = valid;
    }
  }
  for (const [vertexId, vertex] of Object.entries(vertices)) {
    if (vertex.connectedWalls.length === 0) {
      delete vertices[vertexId];
      verticesRemoved++;
    }
  }

  return { verticesRemoved, wallsRemoved, refsFixed };
}
```

### Part 25, Step 2: Validated `addWall` — **`src/store/slices/editorSlice.ts`** (modify)

Front the existing `addWall` action with the guard and add duplicate/self‑reference checks.
This replaces the body of `addWall` from Part 4.

```typescript
// inside createEditorSlice — addWall (validated)
import { validateAddWall } from '@/store/guards/storeGuards';

addWall: (start, end, thickness = 20, height = 280) => {
  const validation = validateAddWall(start, end, thickness, height);
  if (!validation.valid) {
    console.warn(`[Store] addWall rejected: ${validation.error}`);
    return '';
  }

  const wallId = generateId('wall');
  let wallCreated = false;

  set((state) => {
    const startVertexId = findOrCreateVertex(state, start);
    const endVertexId = findOrCreateVertex(state, end);
    if (startVertexId === endVertexId) return; // no self‑loops

    // No duplicate wall between the same two vertices (either direction).
    const dup = Object.values(state.walls).find(
      (w) =>
        (w.startVertexId === startVertexId && w.endVertexId === endVertexId) ||
        (w.startVertexId === endVertexId && w.endVertexId === startVertexId)
    );
    if (dup) return;

    state.walls[wallId] = { id: wallId, startVertexId, endVertexId, thickness, height, materialId: 'default-wall', isLoadBearing: false };
    state.vertices[startVertexId].connectedWalls.push(wallId);
    state.vertices[endVertexId].connectedWalls.push(wallId);
    wallCreated = true;
  });

  return wallCreated ? wallId : '';
},
```

---

## PART 26: Loading & Empty States

No blank screens. Build the small feedback components, then make `ViewerCanvas` use them.

> **One canonical `LoadingSpinner`.** Part 21 created a minimal stub so `App` could import
> it. This step is the **enhanced** version (adds a `size` prop) at the **same path** —
> replace the stub with this. `App`'s `label`‑only usage stays compatible.

### Part 26, Step 1: Loading spinner — **`src/domains/shared/components/LoadingSpinner.tsx`** (modify)

```typescript
// src/domains/shared/components/LoadingSpinner.tsx

import React from 'react';

interface LoadingSpinnerProps {
  label: string;
  size?: 'sm' | 'md' | 'lg';
}

/** Accessible spinner; the label is both shown and exposed to screen readers. */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ label, size = 'md' }) => {
  const sizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' };
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3" role="status" aria-label={label}>
      <svg className={`${sizes[size]} animate-spin text-blue-500`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <p className="text-neutral-400 text-sm">{label}</p>
    </div>
  );
};
```

### Part 26, Step 2: Asset progress — **`src/domains/shared/components/ModelLoadingProgress.tsx`** (new)

```typescript
// src/domains/shared/components/ModelLoadingProgress.tsx

import React from 'react';
import { useProgress } from '@react-three/drei';

/** Overlay showing GLTF/texture load progress, driven by R3F's useProgress. */
export const ModelLoadingProgress: React.FC = () => {
  const { active, progress, item } = useProgress();
  if (!active) return null;
  const filename = item?.split('/').pop() ?? 'assets';

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 z-10" role="progressbar"
      aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100} aria-label={`Loading 3D assets: ${Math.round(progress)}%`}>
      <div className="w-64">
        <div className="flex justify-between text-sm text-neutral-400 mb-2">
          <span>Loading {filename}</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="h-2 bg-neutral-800 rounded-full overflow-hidden">
          <div className="h-full bg-blue-500 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
      </div>
    </div>
  );
};
```

### Part 26, Step 3: Empty state — **`src/domains/shared/components/EmptyState.tsx`** (new)

```typescript
// src/domains/shared/components/EmptyState.tsx

import React from 'react';

interface EmptyStateProps {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, action, icon }) => (
  <div className="flex flex-col items-center justify-center h-full p-8 text-center">
    {icon && <div className="text-4xl mb-4 text-neutral-500" aria-hidden="true">{icon}</div>}
    <h3 className="text-lg font-medium text-neutral-300 mb-2">{title}</h3>
    <p className="text-neutral-500 text-sm max-w-xs mb-4">{description}</p>
    {action && (
      <button onClick={action.onClick} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm transition-colors">
        {action.label}
      </button>
    )}
  </div>
);
```

### Part 26, Step 4: Final `ViewerCanvas` — **`src/domains/viewer/components/ViewerCanvas.tsx`** (modify)

The definitive version: shows an empty state until walls exist, an asset‑loading overlay,
and keeps `SceneEnvironment` + `CameraController` from earlier installments.

```typescript
// src/domains/viewer/components/ViewerCanvas.tsx  (final)

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Preload, Stats } from '@react-three/drei';
import { useAppStore } from '@/store';
import { SceneEnvironment } from './SceneEnvironment';
import { SceneContent } from './SceneContent';
import { CameraController } from './CameraController';
import { ModelLoadingProgress } from '@/domains/shared/components/ModelLoadingProgress';
import { EmptyState } from '@/domains/shared/components/EmptyState';

export const ViewerCanvas: React.FC = () => {
  const cameraMode = useAppStore((s) => s.cameraMode);
  const hasWalls = useAppStore((s) => Object.keys(s.walls).length > 0);

  if (!hasWalls) {
    return (
      <EmptyState
        title="No floor plan yet"
        description="Draw walls in the 2D editor to see your design come to life in 3D."
        icon="🏗️"
      />
    );
  }

  return (
    <div className="w-full h-full relative">
      <ModelLoadingProgress />
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', stencil: false }}
        camera={{ fov: 60, near: 0.1, far: 1000, position: [10, 10, 10] }}
      >
        <Suspense fallback={null}>
          <SceneEnvironment />
          <CameraController mode={cameraMode} />
          <SceneContent />
          <Preload all />
        </Suspense>
        {import.meta.env.DEV && <Stats />}
      </Canvas>
    </div>
  );
};
```

---

## PART 27: Complete OBB Collision (Wall‑aware)

> **Already done in Installment 3:** the full `obbIntersects` (Separating Axis Theorem) and
> its helpers `getOBBCorners` / `getOBBAxes` / `projectOntoAxis` are written in Part 12. The
> only genuinely new piece is **furniture‑vs‑wall** collision, added below to the same file.

### Part 27, Step 1: Wall collision — append to **`src/domains/editor/services/collision.ts`** (modify)

A wall is a rotated rectangle, so we model it as an OBB and reuse `obbIntersects`. This lets
`checkFurnitureCollisions` flag furniture overlapping a wall, not just other furniture.

```typescript
// src/domains/editor/services/collision.ts  (append)

import type { Point2D, OBB } from '@/types/geometry';
import type { Wall, Vertex, EntityId } from '@/types/editor';
// obbIntersects is defined earlier in this same file (Part 12).

/** Builds an OBB for a wall from its two endpoints and thickness. */
export function wallToOBB(wall: Wall, vertices: Record<EntityId, Vertex>): OBB | null {
  const a = vertices[wall.startVertexId]?.position;
  const b = vertices[wall.endVertexId]?.position;
  if (!a || !b) return null;

  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  if (length < 0.01) return null;

  return {
    center: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 },
    halfExtents: { x: length / 2, y: wall.thickness / 2 },
    rotation: Math.atan2(dy, dx), // wall's angle = its local long axis
  };
}

/** True if a furniture OBB overlaps any wall. */
export function furnitureIntersectsAnyWall(
  itemOBB: OBB,
  walls: Record<EntityId, Wall>,
  vertices: Record<EntityId, Vertex>
): boolean {
  for (const wall of Object.values(walls)) {
    const wallOBB = wallToOBB(wall, vertices);
    if (wallOBB && obbIntersects(itemOBB, wallOBB)) return true;
  }
  return false;
}
```

> To use it, build the item's OBB (as `checkFurnitureCollisions` already does) and call
> `furnitureIntersectsAnyWall(itemOBB, walls, vertices)` before committing a placement —
> reject or highlight the placement if it returns `true`.

---

## PART 28: Touch Input & Responsive Design

For on‑site tablet use: a gesture recognizer for the 2D canvas, a layout hook, and a
responsive shell. Order: touch hook → layout hook → responsive shell.

### Part 28, Step 1: Touch gestures — **`src/domains/editor/hooks/useTouch.ts`** (new)

Classifies 1‑finger tap/drag/long‑press and 2‑finger pinch/pan, converting touches into
world coordinates (note the same `-y` flip as mouse input).

```typescript
// src/domains/editor/hooks/useTouch.ts

import { useRef, useCallback, RefObject } from 'react';
import type { Point2D, ViewTransform } from '@/types/geometry';

interface TouchState {
  touches: Map<number, Point2D>;
  initialDistance: number;
  initialScale: number;
  initialCenter: Point2D;
  gesture: 'none' | 'pan' | 'pinch' | 'drag' | 'longpress';
  longPressTimer: ReturnType<typeof setTimeout> | null;
}

const LONG_PRESS_DURATION = 500; // ms
const MIN_PINCH_DISTANCE = 10; // px

export function useTouchGestures(
  svgRef: RefObject<SVGSVGElement>,
  viewTransform: ViewTransform,
  setViewTransform: (vt: ViewTransform) => void,
  onTap: (worldPos: Point2D) => void,
  onLongPress: (worldPos: Point2D) => void,
  onDrag: (worldPos: Point2D) => void,
  onDragEnd: () => void
) {
  const state = useRef<TouchState>({
    touches: new Map(),
    initialDistance: 0,
    initialScale: 1,
    initialCenter: { x: 0, y: 0 },
    gesture: 'none',
    longPressTimer: null,
  });

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      e.preventDefault();
      const s = state.current;
      for (const touch of Array.from(e.changedTouches)) {
        s.touches.set(touch.identifier, { x: touch.clientX, y: touch.clientY });
      }

      if (s.touches.size === 1) {
        const pos = Array.from(s.touches.values())[0];
        s.longPressTimer = setTimeout(() => {
          s.gesture = 'longpress';
          onLongPress(screenToWorldTouch(pos, svgRef.current!, viewTransform));
        }, LONG_PRESS_DURATION);
      } else if (s.touches.size === 2) {
        cancelLongPress(s);
        const pts = Array.from(s.touches.values());
        s.initialDistance = distance(pts[0], pts[1]);
        s.initialScale = viewTransform.scale;
        s.initialCenter = midpoint(pts[0], pts[1]);
        s.gesture = 'pinch';
      } else if (s.touches.size === 3) {
        cancelLongPress(s);
        s.gesture = 'none';
      }
    },
    [viewTransform, onLongPress, svgRef]
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      e.preventDefault();
      const s = state.current;
      for (const touch of Array.from(e.changedTouches)) {
        s.touches.set(touch.identifier, { x: touch.clientX, y: touch.clientY });
      }

      if (s.touches.size === 1 && s.gesture !== 'longpress') {
        cancelLongPress(s);
        s.gesture = 'drag';
        const pos = Array.from(s.touches.values())[0];
        onDrag(screenToWorldTouch(pos, svgRef.current!, viewTransform));
      } else if (s.touches.size === 2) {
        const pts = Array.from(s.touches.values());
        const currentDist = distance(pts[0], pts[1]);
        const currentCenter = midpoint(pts[0], pts[1]);

        if (Math.abs(currentDist - s.initialDistance) > MIN_PINCH_DISTANCE) {
          const scaleFactor = currentDist / s.initialDistance;
          const newScale = Math.min(10, Math.max(0.1, s.initialScale * scaleFactor));
          setViewTransform({
            scale: newScale,
            offsetX: viewTransform.offsetX + (currentCenter.x - s.initialCenter.x),
            offsetY: viewTransform.offsetY + (currentCenter.y - s.initialCenter.y),
          });
        } else {
          setViewTransform({
            ...viewTransform,
            offsetX: viewTransform.offsetX + (currentCenter.x - s.initialCenter.x),
            offsetY: viewTransform.offsetY + (currentCenter.y - s.initialCenter.y),
          });
          s.initialCenter = currentCenter;
        }
      }
    },
    [viewTransform, setViewTransform, onDrag, svgRef]
  );

  const handleTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      const s = state.current;
      for (const touch of Array.from(e.changedTouches)) s.touches.delete(touch.identifier);

      if (s.touches.size === 0) {
        if (s.gesture === 'none') {
          const last = e.changedTouches[0];
          if (last) onTap(screenToWorldTouch({ x: last.clientX, y: last.clientY }, svgRef.current!, viewTransform));
        }
        if (s.gesture === 'drag') onDragEnd();
        cancelLongPress(s);
        s.gesture = 'none';
      }
    },
    [viewTransform, onTap, onDragEnd, svgRef]
  );

  return { onTouchStart: handleTouchStart, onTouchMove: handleTouchMove, onTouchEnd: handleTouchEnd };
}

function cancelLongPress(state: TouchState): void {
  if (state.longPressTimer) {
    clearTimeout(state.longPressTimer);
    state.longPressTimer = null;
  }
}
function distance(a: Point2D, b: Point2D): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}
function midpoint(a: Point2D, b: Point2D): Point2D {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}
function screenToWorldTouch(screen: Point2D, svg: SVGSVGElement, view: ViewTransform): Point2D {
  const rect = svg.getBoundingClientRect();
  return {
    x: (screen.x - rect.left - view.offsetX) / view.scale,
    y: -(screen.y - rect.top - view.offsetY) / view.scale, // Y‑flip, as with the mouse
  };
}
```

### Part 28, Step 2: Layout hook — **`src/app/hooks/useResponsiveLayout.ts`** (new)

```typescript
// src/app/hooks/useResponsiveLayout.ts

import { useState, useEffect } from 'react';

export type LayoutMode = 'desktop' | 'tablet-landscape' | 'tablet-portrait' | 'mobile';

interface LayoutConfig {
  mode: LayoutMode;
  showSidebar: boolean;
  showViewer: boolean;
  editorFullWidth: boolean;
  panelPosition: 'right' | 'bottom' | 'overlay';
}

const BREAKPOINTS = { mobile: 640, tabletPortrait: 768, tabletLandscape: 1024, desktop: 1280 };

function getLayoutConfig(): LayoutConfig {
  const width = window.innerWidth;
  if (width >= BREAKPOINTS.desktop) return { mode: 'desktop', showSidebar: true, showViewer: true, editorFullWidth: false, panelPosition: 'right' };
  if (width >= BREAKPOINTS.tabletLandscape) return { mode: 'tablet-landscape', showSidebar: false, showViewer: true, editorFullWidth: false, panelPosition: 'overlay' };
  if (width >= BREAKPOINTS.tabletPortrait) return { mode: 'tablet-portrait', showSidebar: false, showViewer: false, editorFullWidth: true, panelPosition: 'bottom' };
  return { mode: 'mobile', showSidebar: false, showViewer: false, editorFullWidth: true, panelPosition: 'bottom' };
}

/** Recomputes the layout config on resize. */
export function useResponsiveLayout(): LayoutConfig {
  const [config, setConfig] = useState<LayoutConfig>(getLayoutConfig());
  useEffect(() => {
    const onResize = () => setConfig(getLayoutConfig());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return config;
}
```

### Part 28, Step 3: Responsive shell — **`src/app/ResponsiveLayout.tsx`** (new)

Side‑by‑side on desktop, tabbed editor/viewer + bottom panel on smaller screens. **Fix vs
the original:** the same named‑export → `{ default }` mapping for `lazy()` as in `App`.

```typescript
// src/app/ResponsiveLayout.tsx

import React, { Suspense, lazy, useState } from 'react';
import { useResponsiveLayout } from './hooks/useResponsiveLayout';
import { LoadingSpinner } from '@/domains/shared/components/LoadingSpinner';
import { ErrorBoundary } from './ErrorBoundary';
import { EditorFallback } from './fallbacks/EditorFallback';
import { ViewerFallback } from './fallbacks/ViewerFallback';

const EditorCanvas = lazy(() => import('@/domains/editor/components/EditorCanvas').then((m) => ({ default: m.EditorCanvas })));
const ViewerCanvas = lazy(() => import('@/domains/viewer/components/ViewerCanvas').then((m) => ({ default: m.ViewerCanvas })));
const VastuPanel = lazy(() => import('@/domains/vastu/components/VastuPanel').then((m) => ({ default: m.VastuPanel })));

export const ResponsiveLayout: React.FC = () => {
  const layout = useResponsiveLayout();
  const [activeTab, setActiveTab] = useState<'editor' | 'viewer'>('editor');

  if (layout.mode === 'desktop') {
    return (
      <div className="flex-1 flex">
        <section className="flex-1" aria-label="2D Floor Plan Editor">
          <ErrorBoundary level="domain" fallback={(e, r) => <EditorFallback error={e} reset={r} />}>
            <Suspense fallback={<LoadingSpinner label="Loading editor…" />}><EditorCanvas /></Suspense>
          </ErrorBoundary>
        </section>
        <section className="flex-1" aria-label="3D Visualization">
          <ErrorBoundary level="domain" fallback={(e, r) => <ViewerFallback error={e} reset={r} />}>
            <Suspense fallback={<LoadingSpinner label="Loading viewer…" />}><ViewerCanvas /></Suspense>
          </ErrorBoundary>
        </section>
        <aside className="w-80 border-l border-neutral-700" aria-label="Vastu Analysis">
          <Suspense fallback={<LoadingSpinner label="Loading analysis…" />}><VastuPanel /></Suspense>
        </aside>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      <div className="flex border-b border-neutral-700" role="tablist" aria-label="View selector">
        <button role="tab" aria-selected={activeTab === 'editor'} aria-controls="editor-panel" onClick={() => setActiveTab('editor')}
          className={`flex-1 py-2 text-sm font-medium ${activeTab === 'editor' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-neutral-400'}`}>2D Editor</button>
        <button role="tab" aria-selected={activeTab === 'viewer'} aria-controls="viewer-panel" onClick={() => setActiveTab('viewer')}
          className={`flex-1 py-2 text-sm font-medium ${activeTab === 'viewer' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-neutral-400'}`}>3D View</button>
      </div>

      <div id="editor-panel" role="tabpanel" className={`flex-1 ${activeTab !== 'editor' ? 'hidden' : ''}`}>
        <Suspense fallback={<LoadingSpinner label="Loading editor…" />}><EditorCanvas /></Suspense>
      </div>
      <div id="viewer-panel" role="tabpanel" className={`flex-1 ${activeTab !== 'viewer' ? 'hidden' : ''}`}>
        <Suspense fallback={<LoadingSpinner label="Loading viewer…" />}><ViewerCanvas /></Suspense>
      </div>

      {layout.panelPosition === 'bottom' && (
        <aside className="h-48 border-t border-neutral-700 overflow-y-auto" aria-label="Vastu Analysis">
          <Suspense fallback={<LoadingSpinner label="Loading analysis…" />}><VastuPanel /></Suspense>
        </aside>
      )}
    </div>
  );
};
```

---

## PARTS 29–31: Test Suites — omitted

These parts are entirely test scripts (`__tests__/**`, the E2E suite, and the coverage
config). They are omitted per your request to validate through 3D rendering. If you want
them later as a standalone document, just ask.

---

## Wiring & dependencies checklist

A few one‑time steps tie the new pieces together:

1. **Install new dependencies:**
   ```bash
   npm install @sentry/react idb-keyval
   ```
   (`@react-three/fiber`, `@react-three/drei`, `three`, `zustand`, and `immer` are already in
   the foundation.)

2. **Mount the "engine" hooks once** in the component that hosts the editor (they render
   nothing but keep the model live):
   ```typescript
   useRoomDetection();   // Part 7 — keeps rooms in sync with walls
   useVastuAnalysis();   // Part 15 — keeps plan boundary + Vastu score in sync
   useKeyboardEditor();  // Part 24 — arrow‑key nudging / delete
   useKeyboardShortcuts(); // Part 22 — undo/redo
   ```

3. **Add the overlays** you wired in Installment 3: `<VastuOverlay2D />` in the
   `EditorCanvas` layer stack, and `{showVastu && <VastuOverlay3D />}` in `SceneContent`.

4. **Place `<ScreenReaderAnnouncer />` and `<SkipLinks />`** at the app root, and use
   `<ResponsiveLayout />` (Part 28) as the body if you want the tablet/mobile layout instead
   of the fixed three‑pane `App`.

---

## Done — full rewrite complete (Parts 5–28, tests omitted)

The restructured guide now covers the entire application linearly: **2D editor (5–7) → 3D
foundation (8–11) → interaction & analysis (12–15) → hardening & delivery (16–28)**. Every
file is created before it's imported, every orphaned reference from the original has a real
file (or is wired in through a hook), the renamed functions are consistent across barrels
and callers, and the lazy‑loading / `useMaterial` / `FloorMesh` / `LoadingSpinner` /
plan‑boundary gaps are all closed. Test scripts (Parts 18, 29–31, and the `__tests__`
blocks) are intentionally left out for your render‑based testing workflow.
