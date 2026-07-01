# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run dev              # Vite dev server (http://localhost:5173)
npm run build            # TypeScript check + production build
npm run preview          # Serve production build locally
npm run lint             # ESLint

npm run test             # Vitest in watch mode
npm run test:run         # Vitest single run (CI)
npm run test:visual      # Playwright visual regression
npm run test:visual:update  # Update Playwright baselines

npm run storybook        # Component sandbox (http://localhost:6006)
```

Run a single test file: `npx vitest run src/domains/editor/services/__tests__/roomDetection.test.ts`

## Architecture

Home Quest is a 2D floor-plan editor with live 3D visualization and Vastu compliance scoring.

**One-way data flow:** UI → Zustand store action → Immer mutation → derived hooks (room detection, Vastu scoring) → pure math services → results written back to store → components re-render → IndexedDB auto-save.

### Central Store (`src/store/`)

Single Zustand store with Immer + devtools + persist middleware. Six slices:

| Slice | Owns |
|-------|------|
| `editorSlice` | vertices, walls, rooms, furniture, openings (core geometry) |
| `uiSlice` | active tool, panel visibility, chain mode |
| `viewerSlice` | 3D camera mode, render quality |
| `vastuSlice` | overlay toggles, computed scores |
| `settingsSlice` | feature flags, dev mode, `activeView` |
| `historySlice` | undo/redo snapshot stacks |

State is normalized hash maps (`Record<EntityId, T>`) for O(1) lookup. Persistence via `idb-keyval` (IndexedDB); UI state and history are transient.

Selectors in `src/store/selectors/` are memoized views over the raw store. Prefer selectors over reading store slices directly in components.

### Three Domains (`src/domains/`)

Each domain has `components/`, `hooks/`, and `services/` subdirectories with a `services/index.ts` barrel exporting the public API.

**Editor** (`src/domains/editor/`) — 2D drawing, room detection, snapping, collision detection.
- `EditorCanvas.tsx` — main canvas; pan/zoom; hit testing
- `useWallDrawing.ts` — wall placement with automatic splitting at crossings
- `useSnapping.ts` — priority pipeline: endpoint → wall-edge → angle → grid (15 cm, 10 cm thresholds)
- `useRoomDetection.ts` — re-runs face extraction when wall graph changes; preserves existing room labels
- `services/roomDetection.ts` — planar-graph face extraction (directed edges, sharpest-turn cycle tracing, Shoelace signed area)
- `services/wallOps.ts` — wall splitting, intersection math, miter offsets
- `services/geometry.ts` — screen ↔ world coordinate transforms

**Viewer** (`src/domains/viewer/`) — React Three Fiber 3D scene.
- `ViewerCanvas.tsx` — R3F scene root
- `WallMesh.tsx` — extrudes 2D walls to 3D; punches door/window holes via `THREE.ExtrudeGeometry`
- `useFirstPerson.tsx` — WASD + mouse look (YXZ Euler to avoid gimbal lock), wall sliding collision
- `services/extrusion.ts` — 2D → 3D wall geometry; miter shearing; hole cutting
- `services/transform.ts` — plan cm ↔ 3D meters (`3D.x = plan.x × 0.01`, `3D.z = -plan.y × 0.01`)
- `services/materials.ts` — PBR material library

**Vastu** (`src/domains/vastu/`) — Compass-direction scoring of room placements.
- `useVastuAnalysis.ts` — recomputes on room or boundary change
- `services/scoring.ts` — maps each room's area-weighted centroid to a 3×3 Vastu grid direction, scores 0–100 per rule, weighted average overall
- `services/planBoundary.ts` — largest-loop outer outline detection

### Types (`src/types/`)

- `geometry.ts` — `Point2D`, `Point3D`, `AABB`, `OBB`, `ViewTransform`
- `editor.ts` — `Vertex`, `Wall`, `Room`, `FurnitureItem`, `Opening`, `RoomType`

## Known Rough Edges

1. **Two `App.tsx` files:** `src/App.tsx` is the current root and renders `SandboxView` (dev harness). `src/app/App.tsx` is the production 3-pane layout, not yet wired as default. Controlled by `activeView` setting (defaults to `'sandbox'`).

2. **Two undo systems:** Snapshot-based (`store/slices/historySlice.ts` + `history/snapshot.ts`) is live. Command-pattern (`history/historyManager.ts`, `history/commands.ts`) is unused dead code.

3. **Furniture is procedural boxes:** No `.glb` assets shipped. `FurnitureModel` component renders placeholder geometry only.

4. **Test config:** The `vite.config.ts` has no `test` block. `vitest.config.ts` is the sole source of truth for test configuration.

## Testing

- Unit tests live in `src/**/__tests__/*.test.ts(x)` or alongside files as `*.test.ts`.
- `src/test/setup.ts` mocks `ResizeObserver`, `IntersectionObserver`, and pointer lock APIs.
- Coverage threshold is 80% (statements, lines, functions, branches).
- Visual regression baselines are in `tests/visual/__screenshots__/`; update with `npm run test:visual:update` after intentional visual changes.
