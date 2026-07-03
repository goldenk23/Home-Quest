# Remaining Structural Feature Tasks - Implementation Prompt

## Project Context

You are working on **Home Quest**, a React + TypeScript floor plan editor with 2D editing and 3D visualization. The project uses:
- **React 19** + **TypeScript**
- **Zustand** for state management (with Immer middleware)
- **Three.js** + **@react-three/fiber** for 3D rendering
- **Vite** as build tool
- **Vitest** for testing

The codebase follows a domain-driven structure with clear separation between editor (2D), viewer (3D), and shared domains.

## Current State

### ✅ Completed Structural Features

1. **Deck Slab Support** - FULLY IMPLEMENTED
   - Type definition in `src/types/editor.ts` (`DeckSlab` interface)
   - Store actions in `src/store/slices/editorSlice.ts`
   - 2D rendering in `src/domains/editor/components/DeckLayer.tsx`
   - 3D rendering in `src/domains/viewer/components/DeckSlabMesh.tsx`
   - Selection, history/undo, persistence, and multi-floor support
   - Integrated in `FloorScene`, `SceneContent`, and editor UI

2. **Smart Pillar Snapping for Beams and Deck Slabs** - FULLY IMPLEMENTED
   - Beam endpoints snap to nearby pillar centers
   - Deck slab polygon points snap to nearby pillar centers
   - Visual feedback via `PillarSnapIndicator.tsx`
   - Files: `src/domains/editor/components/EditorCanvas.tsx`, `src/domains/editor/components/PillarSnapIndicator.tsx`

3. **Railings / Parapets Feature** - COMPLETED AND VERIFIED
   - Railing data model/type support is available through `src/types/editor-railings.d.ts` module augmentation because `src/types/editor.ts` was locked and direct edits did not persist reliably.
   - Store actions implemented: add, update, remove, move
   - Persistence, migration, validation, file import/export, history snapshots, and floor switching integrated
   - 2D rendering: `src/domains/editor/components/RailingLayer.tsx`
   - 3D rendering: `src/domains/viewer/components/RailingMesh.tsx`
   - Selection, hit testing, deletion, and dragging integrated in `EditorCanvas.tsx` and `SelectionLayer.tsx`
   - Scene integration completed in `FloorScene.tsx` and `SceneContent.tsx`
   - UI integration completed in `SandboxView.tsx`:
     - Railing tool button
     - Height control
     - Elevation control
     - Open/Solid style control
   - New railing placement uses configured height, elevation, and style from `uiSlice.ts`
   - Verified:
     - ✅ `npm run build` succeeds
     - ✅ `npm run test:run` succeeds: 7 files / 39 tests passing

4. **Repeat / Array Placement Workflow** - COMPLETED AND VERIFIED
   - Type definition in `src/store/slices/uiSlice.ts` (`ArrayToolConfig` interface, `arrayConfig` state)
   - Store actions: `setArrayConfig`, `resetArrayConfig`, `'array'` tool type registered
   - Position generation: `src/domains/editor/services/arrayPlacement.ts` (`generateArrayPositions`)
   - Hook: `src/domains/editor/hooks/useArrayTool.ts` (preview, commit, cancel)
   - 2D preview: `src/domains/editor/components/ArrayPreview.tsx` (numbered positions)
   - Editor integration in `EditorCanvas.tsx`:
     - Click handler commits array placement
     - Escape key cancels array preview
     - `<ArrayPreview>` rendered when array tool is active
     - Undo/redo treats entire array as one history action via `recordHistory('Place Array', ...)`
   - UI integration in `SandboxView.tsx`:
     - Array tool button in toolbar
     - Entity type selector (Furniture/Pillar)
     - Furniture catalog picker (when furniture type selected)
     - Count slider (2-20)
     - Spacing slider (50-500 cm)
     - Angle slider (0-360°) with 0°/90° preset buttons
     - Show Preview / Cancel buttons
   - Verified:
     - ✅ `npm run build` succeeds
     - ✅ `npm run test:run` succeeds: 7 files / 39 tests passing

## No Remaining Tasks

All structural feature tasks from the original prompt have been implemented. The project is up to date.

## Important Follow-Up / Improvement Suggestion

### Railing Tool Stability Regression Guard

A blank-screen crash was reported when clicking the **Railing** tool/section. The likely cause was conditional hook usage inside the Railing controls in `src/app/SandboxView.tsx`. This has been fixed by moving all railing-related `useAppStore(...)` calls to the top level of the `SandboxView` component.

Recommended follow-up improvement:
- Add a small regression test or manual QA checklist item for switching between toolbar tools, especially `select → railing → select`, to ensure React hook-order errors do not return.
- Consider adding an error boundary around the top toolbar controls, similar to the existing editor/viewer `ErrorBoundary`, so a toolbar rendering error does not blank the whole app.

Known test-environment note:
- Vitest currently logs existing `indexedDB is not defined` persistence warnings, but tests pass. These warnings are not related to the railing or array work.

---

## Implementation Guidelines

### Code Style
- Follow existing patterns in the codebase
- Use Immer for immutable state updates
- Use TypeScript strictly (no `any` types)
- Keep components pure and memoized where appropriate
- Use `generateId()` for entity IDs with appropriate prefixes

### Testing Strategy
1. Add unit tests for pure functions (geometry/array position generation)
2. Add integration tests for store actions
3. Test undo/redo behavior
4. Test cancellation and edge cases
5. Manual testing in the running application

### Verification Commands
After implementing features, run:
```bash
npm run build      # Should pass
npm run lint       # Fix new errors; pre-existing warnings can be documented
npm run test:run   # All tests should pass
```

### Key Files Reference
- Types: `src/types/editor.ts`, `src/types/index.ts`, `src/types/editor-railings.d.ts`
- Store: `src/store/slices/editorSlice.ts`, `src/store/slices/floorsSlice.ts`, `src/store/slices/uiSlice.ts`
- History: `src/store/history/snapshot.ts`
- Persistence: `src/store/persistence/migrations.ts`, `src/store/persistence/fileIO.ts`, `src/store/persistence/validation.ts`
- Editor (2D): `src/domains/editor/components/*`, `src/domains/editor/hooks/*`
- Viewer (3D): `src/domains/viewer/components/*`
- UI: `src/app/SandboxView.tsx`

### Important Patterns
- Entity IDs: Use `generateId('entity-type')` (e.g., `'railing'`, `'furniture'`)
- Measurements: All distances in centimeters, angles in radians internally
- Coordinates: 2D world space, Y-up in 3D (Three.js convention)
- Materials: Reuse existing material system from walls/furniture
- Selection: Follow beam/deck slab/railing selection patterns
- Persistence: Update schema version and add migration when adding persisted fields