# Structural Feature Implementation Plan

## Current State Analysis

### ✅ Already Implemented (Deck Slabs)
- DeckSlab type defined in types/editor.ts with polygon, thickness, elevation, materialId, and type fields
- Store support: addDeckSlab, updateDeckSlab, removeDeckSlab, moveDeckSlab in editorSlice
- Persistence: included in FloorGeometry, migrations (v7), validation, fileIO
- History: included in snapshot system
- Editor: DeckLayer renders 2D polygons with proper styling
- Viewer: DeckSlabMesh renders 3D extruded geometry
- Selection: SelectionLayer highlights selected deck slabs
- EditorCanvas: deck tool workflow with polygon click-to-close, hit testing, dragging, deletion
- FloorScene & SceneContent: deck slabs render for active and parked floors
- UI: 'deck' tool in uiSlice and SandboxView with instructions

### ❌ Missing Features

#### 1. Railings/Parapets
- **Not implemented at all** - no types, store, rendering, or UI

#### 2. Repeat/Array Placement Workflow
- **Not implemented at all** - no array tool, no repeat logic

#### 3. Deck Slab Improvements Needed
- Property panel for editing deck slab attributes (thickness, elevation, material, type)
- Better visual distinction for different deck types (corridor vs balcony vs roof)
- Deck slab stairs field integration if needed

## Implementation Strategy

### Phase 1: Add Railing Support (if needed for project scope)
**Decision Point:** Railings are architectural elements typically associated with:
- Deck/balcony edges
- Stair edges
- Roof parapets

**Implementation approach:**
1. Define Railing type with edge-based geometry (start/end points or attached to deck edges)
2. Add store actions
3. Add rendering in 2D and 3D
4. Add selection/manipulation
5. Add to persistence/history

### Phase 2: Repeat/Array Placement Tool
**Target entities:** Furniture, Pillars, Beams, Deck Slabs (user choice)
**Implementation:**
1. Add array tool to UI
2. Implement array placement logic with preview
3. Add commit workflow
4. Ensure undo/redo works as single action

### Phase 3: Testing & Verification
1. Add unit tests for new logic
2. Update existing tests
3. Run build, lint, test commands
4. Manual verification in SandboxView

## Scope Clarification Needed

Based on the codebase review, I need to clarify scope:

1. **Railings:** Should railings be:
   - Auto-generated along deck edges?
   - Manually placeable entities?
   - Omitted from this implementation?

2. **Array Tool:** Should it support:
   - Linear arrays (1D)?
   - Grid arrays (2D)?
   - Which entity types?

Without explicit scope in the requirements, I will implement:
- **Skip railings** (can be added later as a separate feature)
- **Focus on array placement** for furniture and structural elements
- **Complete deck slab workflow** with property editing
