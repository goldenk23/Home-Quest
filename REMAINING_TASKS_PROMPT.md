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

## Important Follow-Up / Improvement Suggestion

### Railing Tool Stability Regression Guard

A blank-screen crash was reported when clicking the **Railing** tool/section. The likely cause was conditional hook usage inside the Railing controls in `src/app/SandboxView.tsx`. This has been fixed by moving all railing-related `useAppStore(...)` calls to the top level of the `SandboxView` component.

Recommended follow-up improvement:
- Add a small regression test or manual QA checklist item for switching between toolbar tools, especially `select → railing → select`, to ensure React hook-order errors do not return.
- Consider adding an error boundary around the top toolbar controls, similar to the existing editor/viewer `ErrorBoundary`, so a toolbar rendering error does not blank the whole app.

Known test-environment note:
- Vitest currently logs existing `indexedDB is not defined` persistence warnings, but tests pass. These warnings are not related to the railing work.

---

## Task 1: Repeat / Array Placement Workflow (NOT STARTED)

### Overview
Implement a workflow that lets users place repeated items in an array or sequence pattern.

### Requirements

#### 1. Target Entities
Support array placement for:
- Furniture (most common use case)
- Pillars
- Optional later extension: Beams, Deck Slabs, Railings

#### 2. UI State

**Update `src/store/slices/uiSlice.ts`:**
```typescript
export interface UISlice {
  // ... existing fields ...

  /** Array/repeat tool configuration */
  arrayConfig: {
    /** Entity type to repeat */
    entityType: 'furniture' | 'pillar' | null;
    /** Reference to the entity to repeat (catalog ID for furniture, entity ID for others) */
    referenceId: string | null;
    /** Number of repetitions */
    count: number;
    /** Spacing between items in cm */
    spacing: number;
    /** Direction angle in radians */
    angle: number;
    /** Whether in preview mode */
    isPreviewing: boolean;
  };

  setArrayConfig: (config: Partial<UISlice['arrayConfig']>) => void;
  resetArrayConfig: () => void;
}
```

Add default `arrayConfig` in initial state:
```typescript
arrayConfig: {
  entityType: null,
  referenceId: null,
  count: 3,
  spacing: 100,
  angle: 0,
  isPreviewing: false,
},
```

#### 3. Editor Integration

**Create `src/domains/editor/hooks/useArrayTool.ts`:**
- Implement array preview logic
- Handle click-to-place workflow
- Support commit and cancel operations
- Ensure undo/redo treats the entire array placement as one history action

**Create `src/domains/editor/components/ArrayPreview.tsx`:**
- Visual preview of array placement
- Show numbered positions
- Different styles for furniture vs pillars

**Update `src/domains/editor/components/EditorCanvas.tsx`:**
- Import `useArrayTool` and `ArrayPreview`
- Add array tool handling in `handleSvgClick`
- Add `<ArrayPreview />` in render
- Add Escape key handler to cancel array tool

#### 4. UI Controls

**Update `src/app/SandboxView.tsx`:**
- Add Array tool button in toolbar
- Add array configuration controls when tool is active:
  - Entity type selector (Furniture/Pillar)
  - Count slider (2-20)
  - Spacing slider (50-500 cm)
  - Angle slider (0-360°) or direction buttons
  - Preview/Commit buttons

**Update `src/store/slices/uiSlice.ts`:**
- Add `'array'` to `Tool` type union

#### 5. Testing
- Test array placement with different configurations
- Test undo/redo of array placement (should undo entire array as one action)
- Test canceling array preview with Escape key
- Test with different entity types
- Test edge cases (count = 1, very large spacing, invalid reference IDs)

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

---

## Success Criteria

### Repeat/Array Placement
- [ ] Array tool UI state defined
- [ ] Array preview working in editor
- [ ] Click-to-place workflow functional
- [ ] Furniture and pillar arrays supported
- [ ] Configuration controls in UI
- [ ] Undo/redo works as a single action
- [ ] Escape key cancels preview
- [ ] Tests added and passing
- [ ] Build passes

### Final Verification
- [ ] `npm run build` succeeds
- [ ] `npm run test:run` all tests pass
- [ ] `npm run lint` no new errors, or pre-existing lint issues documented
- [ ] Application runs: `npm run dev`
- [ ] Manual testing confirms feature works end-to-end
- [ ] Manual testing confirms switching toolbar tools does not blank the app

---

## Notes
- Deck slabs, beams, and railings are now implemented and can serve as references for future structural features.
- The project uses snapshot-based undo/redo; array placement should integrate with this so one array placement becomes one undo step.
- Multi-floor support is critical; ensure new features work across floor switching.
- Follow existing hit testing, selection, and dragging patterns in `EditorCanvas.tsx`.
