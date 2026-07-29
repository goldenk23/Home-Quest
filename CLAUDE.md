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

Single Zustand store with Immer + devtools + persist middleware. Seven slices:

| Slice | Owns |
|-------|------|
| `editorSlice` | core geometry: vertices, walls, rooms, furniture, openings, roads, stairs, pillars, beams, deckSlabs, railings; selection; snap config |
| `floorsSlice` | multi-storey support (see below) |
| `uiSlice` | active tool, panel visibility, chain mode |
| `viewerSlice` | 3D camera mode, render quality |
| `vastuSlice` | overlay toggles, computed scores |
| `settingsSlice` | feature flags, dev mode, `activeView` |
| `historySlice` | undo/redo snapshot stacks |

**Multi-storey (`floorsSlice`):** The live store always holds exactly the *active* floor's geometry, so every 2D editor component, snapping, room detection, and undo/redo keep operating on one floor unchanged. Other floors are "parked" as serialized geometry in `floorData`. Switching floors swaps the working set with a parked one. The 3D viewer reads the active floor live and parked floors from `floorData`, stacking them by each floor's `elevationCm`.

State is normalized hash maps (`Record<EntityId, T>`) for O(1) lookup. Persistence via `idb-keyval` (IndexedDB); UI state and history are transient.

Selectors in `src/store/selectors/` are memoized views over the raw store. Prefer selectors over reading store slices directly in components.

### Three Domains (`src/domains/`)

Each domain has `components/`, `hooks/`, and `services/` subdirectories with a `services/index.ts` barrel exporting the public API. `src/domains/shared/` holds cross-domain UI (`Toolbar`, `EmptyState`, `DevToolsPanel`, a11y helpers), the material `finishPalette`, the `openingCatalog`, and GLB discovery (`useGlbWallDiscovery`).

**Editor** (`src/domains/editor/`) — 2D drawing of every structural element, room detection, snapping, collision detection. Beyond walls it edits roads, stairs, pillars, beams, decks, railings, openings (doors/windows), furniture, and array/clone placement, across multiple floors.
- `EditorCanvas.tsx` — main canvas; pan/zoom; hit testing. The scene is composed of `*Layer.tsx` components (`WallLayer`, `RoomLayer`, `StairLayer`, `PillarLayer`, `BeamLayer`, `DeckLayer`, `RailingLayer`, `RoadLayer`, `OpeningsLayer`, `FurnitureLayer`, `DimensionLayer`, `GridLayer`, `SelectionLayer`, `GhostFloorLayer`, `CompassRose`).
- `useWallDrawing.ts` — wall placement with automatic splitting at crossings
- `useSnapping.ts` — priority pipeline: endpoint → wall-edge → angle → grid (15 cm, 10 cm thresholds)
- `useRoomDetection.ts` — re-runs face extraction when wall graph changes; preserves existing room labels
- other tool hooks: `useStairTool`, `useArrayTool`, `useRoadDrawing`, `useCollisions`, `usePan`, `useTouch`, `useKeyboardEditor`
- `services/roomDetection.ts` — planar-graph face extraction (directed edges, sharpest-turn cycle tracing, Shoelace signed area)
- `services/wallOps.ts` — wall splitting, intersection math, miter offsets
- `services/geometry.ts` — screen ↔ world coordinate transforms
- other services: `stairBuilder`, `arrayPlacement`, `buildingClone`/`componentClone`, `collision`, `openingGeometry`, `pillarGuides`, `structuralJoints`, `wallGuides`, `safeGeometry`

**Viewer** (`src/domains/viewer/`) — React Three Fiber 3D scene.
- `ViewerCanvas.tsx` → `SceneContent.tsx` / `FloorScene.tsx` — R3F scene root; stacks floors by elevation
- `WallMesh.tsx` — extrudes 2D walls to 3D; punches door/window holes via `THREE.ExtrudeGeometry`
- mesh components per element type: `FloorMesh`, `StairMesh`, `PillarMesh`, `BeamMesh`, `RailingMesh`, `RoadMesh`, `DeckSlabMesh`, `SlabMesh`, `WallCapMesh`, `GroundPlane`
- `FurnitureModel.tsx` — renders placed furniture: a catalog entry with a `model` loads the real glTF asset (`useGLTF` + `<Clone>`, scaled to its footprint, optional topper); entries without a model fall back to a procedural prefab (`furniture/ProceduralPrefabs`)
- `useFirstPerson.ts` — WASD + mouse look (YXZ Euler to avoid gimbal lock), wall sliding collision; `useOrbitCamera` for orbit mode
- asset loading: `useAssetLoader` (FURNITURE_CATALOG), `useSafeAssetLoader`, `services/modelPrep.ts` (grounds/normalizes loaded models)
- `services/extrusion.ts` — 2D → 3D wall geometry; miter shearing; hole cutting
- `services/transform.ts` — plan cm ↔ 3D meters (`3D.x = plan.x × 0.01`, `3D.z = -plan.y × 0.01`)
- `services/materials.ts` / `furnitureMaterials.ts` — PBR material library; `services/sun.ts` + `SceneEnvironment`/`Effects` for lighting and post-processing

**Vastu** (`src/domains/vastu/`) — Compass-direction scoring of room placements.
- `useVastuAnalysis.ts` — recomputes on room or boundary change
- `services/scoring.ts` — maps each room's area-weighted centroid to a 3×3 Vastu grid direction, scores 0–100 per rule, weighted average overall
- `services/planBoundary.ts` — largest-loop outer outline detection
- `services/zones.ts`, `vectors.ts`, `brahmasthan.ts` — 3×3 grid zone math, direction vectors, and the central `brahmasthan` zone check

### Types (`src/types/`)

- `geometry.ts` — `Point2D`, `Point3D`, `AABB`, `OBB`, `ViewTransform`
- `editor.ts` — `Vertex`, `Wall`, `Room`, `FurnitureItem`, `Opening`, `RoomType`, plus the newer element types (`Road`, `Pillar`, `Beam`, `DeckSlab`, `Railing`) and multi-floor types (`Floor`, `FloorGeometry`)
- `stair.ts` — stair entity types; `editor-railings.d.ts` — railing type augmentation; `index.ts` — barrel re-export

## Known Rough Edges

1. **Two `App.tsx` files:** `src/App.tsx` is the current root; it renders `SandboxView` (dev harness) when `activeView === 'sandbox'` (the default), otherwise a placeholder heading — it does **not** yet mount `src/app/App.tsx`, the production 3-pane shell. Controlled by the `activeView` setting in `settingsSlice`.

2. **Two undo systems:** Snapshot-based (`store/slices/historySlice.ts` + `history/snapshot.ts`) is live. Command-pattern (`history/historyManager.ts`, `history/commands.ts`) is unused dead code (referenced only within the `history/` folder).

3. **GLB assets are wired up:** Real glTF models ship under `public/models/` and `public/walls/`. `FurnitureModel` loads catalog models via `useGLTF`, falling back to procedural prefabs when a catalog entry has no `model`. A `wallsManifestPlugin` in `vite.config.ts` scans `public/walls/` (top-level files and one level of subfolders) on dev-start/build and writes `public/walls/manifest.json`, so dropped `.glb`/`.gltf` files are discovered without a fixed filename (`useGlbWallDiscovery`).

4. **Test config:** The `vite.config.ts` has no `test` block. `vitest.config.ts` is the sole source of truth for test configuration.

## Testing

- Unit tests live in `src/**/__tests__/*.test.ts(x)` or alongside files as `*.test.ts`.
- `src/test/setup.ts` mocks `ResizeObserver`, `IntersectionObserver`, and pointer lock APIs.
- Coverage threshold is 80% (statements, lines, functions, branches).
- Visual regression baselines are in `tests/visual/__screenshots__/`; update with `npm run test:visual:update` after intentional visual changes.
