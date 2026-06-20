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
