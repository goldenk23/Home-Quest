# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Home Quest is a browser app where you draw a 2D floor plan, watch it become a navigable 3D house in real time, and get an automatic **Vastu** (traditional Indian architectural alignment) score per room. Single-screen sandbox: 2D editor + live 3D viewer + Vastu panel.

Stack: React 19, TypeScript, Zustand 5 (+ Immer middleware), Three.js via React Three Fiber (`@react-three/fiber`, `@react-three/drei`), Vite 8, Tailwind 4. Persistence via IndexedDB (`idb-keyval`). No backend.

`ARCHITECTURE.md` is a long, accurate deep-dive written from the source — read it for any non-trivial feature work. `features.md` is the user-facing capability list.

## Commands

```bash
npm run dev              # Vite dev server at http://localhost:5173
npm run build            # tsc -b && vite build (type-checks the whole project)
npm run lint             # ESLint
npm test                 # Vitest watch mode
npm run test:run         # Vitest single run (CI)
npm run storybook        # Storybook at :6006
npm run test:visual      # Playwright visual-regression (auto-starts dev server)
npm run test:visual:update   # Update screenshot baselines after intentional UI changes
```

Run a single unit test: `npx vitest run src/path/to/file.test.ts` (or `npx vitest run -t "test name"`).

Unit tests live next to source as `*.test.ts(x)` or under `__tests__/`. Vitest uses jsdom + `src/test/setup.ts`. Coverage is enforced (80% statements/functions/lines, 75% branches) but scoped to `services/`, `hooks/`, `store/`, and `utils/` only — UI components are excluded.

## Architecture

**Everything flows through one central Zustand store.** Domains never talk to each other directly — the 2D editor never imports 3D code and vice-versa. UI calls store actions → actions mutate state via Immer drafts → engine hooks react to changes and write results back → all views read from the store. Data flows one way (down).

### The store (`src/store/`)

`useAppStore` (`store/index.ts`) is composed from slices, each owning one topic of state + its actions:

- `editorSlice` — floor-plan geometry + mutations (addWall, moveFurniture, paint, split, etc.)
- `floorsSlice` — multi-storey support (see below)
- `uiSlice` — active tool/panel (transient)
- `viewerSlice` — 3D camera mode, render quality
- `vastuSlice` — overlay toggles + computed score
- `settingsSlice` — feature flags, `activeView`
- `historySlice` — undo/redo

Only floor-plan data is persisted to IndexedDB (`partialize` in `store/index.ts`); UI and history are transient. Schema changes go through `store/persistence/migrations.ts` (bump `CURRENT_SCHEMA_VERSION`); incoming plans are validated/repaired in `persistence/validation.ts` and `store/guards/`.

### Data model (`src/types/editor.ts`)

The floor plan is a **graph**, stored as flat `Record<id, T>` maps (not nested):
- `Vertex` — a point; tracks `connectedWalls`.
- `Wall` — connects two vertex IDs; has thickness/height (cm), a base `materialId`, and optional per-face paint (`materialSideA`/`materialSideB`).
- `Room` — a closed polygon (ordered `boundaryVertexIds`) **detected automatically**, plus a `roomType` that drives Vastu.
- `FurnitureItem` — position/rotation/scale + catalog ref + collision `bounds`.
- `Opening` — door/window/vent/ac on a wall, positioned by `offsetCm` along the wall.
- `Road` — standalone exterior segment, NOT part of the vertex graph.

### Domains (`src/domains/{editor,viewer,vastu,shared}/`)

Each domain has `components/`, `hooks/`, `services/`. **Services are pure logic (the math); they expose a public API through `services/index.ts` — import from that barrel, not deep paths.** Key engine hooks that recompute derived state on store changes: `useRoomDetection` (editor), `useVastuAnalysis` (vastu). Key services: `roomDetection`, `wallOps`, `wallGuides`, `collision` (editor); `extrusion`, `transform`, `sun` (viewer); `scoring`, `brahmasthan`, `zones` (vastu).

### Coordinate systems — important

- **2D editor world units are centimeters.** Layers render inside a zoom/pan `<g>` where 1 unit = 1 cm. `Point2D` = cm.
- **3D world units are meters.** `Point3D` = meters. The viewer's `transform` service maps 2D→3D: a 2D `(x, y)` becomes 3D `(x, 0, z)` — the 2D y-axis becomes the 3D **z**-axis, and 3D y is vertical height.
- Path alias `@/` → `src/` (in `vite.config.ts`, `vitest.config.ts`, `tsconfig`).

## Gotchas (verify against current code before relying on these)

- **Two `App.tsx` files.** `main.tsx` renders `src/App.tsx`, which shows the **SandboxView** dev harness (`activeView` defaults to `'sandbox'`). The polished three-pane production shell at `src/app/App.tsx` is **not wired as root**.
- **Two undo systems.** The live one is snapshot-based (`store/slices/historySlice.ts` + `history/snapshot.ts`). A separate command-pattern implementation (`history/historyManager.ts`, `history/commands.ts`) exists but is **unused** — don't confuse them.
- **Furniture renders as procedural boxes**, not `.glb` models — sized in real centimeters from the catalog. No GLTF assets are shipped.
- **Collision today is furniture-vs-furniture only** (spatial-hash broad phase + SAT for oriented boxes). Furniture-vs-wall is not implemented.
- **`.kiro/specs/`** holds feature spec docs (e.g. stair-builder requirements) — check there for in-progress feature intent.
