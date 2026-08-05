# 2D-to-3D integration handoff

**Updated:** 2026-07-23  
**Workspace:** `c:\Users\golde\Desktop\Projects\Home Quest`

## Goal

Create detailed house plans in the separate Python/Tkinter 2D Layout Maker, save its native JSON, import that file into Home Quest, and visualize the same geometry and assets through Home Quest's existing 3D renderer.

## Current architecture

`layout_serializer.py` → native Python JSON v1.0 → `SandboxView.handleImportPython` → `assertVastuLayout` / `convertVastuLayout` / `importVastuLayout` → Zustand active-floor maps → `SceneContent` → `FloorScene` → existing floors, walls, openings, furniture, and structural meshes.

The integration intentionally has no second 3D renderer and no native→`.hq.json` conversion stage.

## Integration work completed

- Added the native Python importer at `src/store/persistence/importVastu.ts`.
- Added **Import Python Layout** UI in `src/app/SandboxView.tsx`.
- Added Python furniture/flooring mappings in `src/domains/shared/assets/pythonAssetMap.ts`.
- Converted rectangle and polygon rooms, standalone wall lines, furniture, flooring, annotations, and compass orientation.
- Converted door furniture to wall openings and erased wall segments to windows.
- Added corner snapping, duplicate-wall removal, T-junction splitting, room-boundary rebuilding, and duplicate-opening suppression.
- Fixed readonly TypeScript mutations that previously broke production builds.
- Added strict untrusted-JSON validation, finite-number checks, schema/version checks, entity limits, and a 5 MB file limit.
- Invalid files are rejected before confirmation, backup, or store mutation.
- Existing plans require replacement confirmation and receive a backup first.
- Corrected zoom, unit-scale, `yard`/`yards` aliases, Y reflection, and canvas-offset normalization.
- Python metadata now exports `unit_scale` and `wall_height_cm`; real room wall thickness is preserved.
- Compass serialization now preserves generated and manually configured north as clockwise degrees.
- Grid/generated labels are filtered on both sides.
- Unknown furniture is skipped and reported instead of becoming a sofa.
- Unsupported shape types and all lossy conversions are shown as import warnings.
- Removed the unused competing `GenerateLayoutService.build_save_payload()` format.
- Removed the obsolete converted sample `temp/layout1.hq.json`; native Python JSON is the source format.

## Coordinate contract

For native v1 files, a Python pixel length is converted with:

`cm = pixels × unit_scale ÷ (grid_spacing × zoom_level) × centimeters_per_unit`

Python screen Y is negated. After conversion, all imported content is translated to a stable local origin so Tk canvas pan/zoom offsets do not affect camera framing.

## Key implementation files

- `2D_layout/2dlayoutMaker-main/layout_serializer.py`
- `2D_layout/2dlayoutMaker-main/generate_layout/service.py`
- `src/store/persistence/importVastu.ts`
- `src/store/persistence/__tests__/importVastu.test.ts`
- `src/store/persistence/__tests__/reference-house.smoke.test.ts`
- `src/domains/shared/assets/pythonAssetMap.ts`
- `src/app/SandboxView.tsx`
- `src/domains/viewer/components/SceneContent.tsx`
- `src/domains/viewer/components/FloorScene.tsx`
## Detailed reference house

Native sample:

`2D_layout/2dlayoutMaker-main/single_storey_vastu_reference.json`

It is a 64 ft × 40 ft single-storey interpretation of the supplied image, with 11 spaces: master bedroom, master bathroom, dressing hall, second bedroom, open living/dining/kitchen, central hall, family lounge, main entrance, powder room, laundry, and mudroom/storage.

The file contains 54 furniture records: 14 doors converted to openings and 40 mapped 3D furniture/fixture items. It also exercises exterior windows, wall gaps, shared walls, wood/marble/tile flooring, two standalone wall lines, five annotations, and north orientation. All referenced Python image assets exist.

Permanent sample regression check:

`src/store/persistence/__tests__/reference-house.smoke.test.ts`

It imports the real JSON fixture, requires no unmapped/residual data, validates graph integrity, and extrudes every wall/opening to finite 3D geometry.

## Reference image

The supplied image is an oblique cutaway of a realistic single-storey home: two furnished bedrooms on the left, bathroom/service rooms between them, a large open living/dining/kitchen on the upper-right, a family/lounge area near the lower center, a recessed main entrance, and compact powder/laundry/mudroom spaces on the lower-right. It has light wood floors, pale walls, dark window/door frames, broad glazed openings, kitchen island/counters, dining seating, and landscaped grass outside.

The original chat image binary is not stored in the repository. Save it manually as `docs/reference-house.png` (or attach it again in a future chat) if pixel-level visual comparison is needed. The native JSON above is the durable geometric interpretation.

## Current manual artifacts

- `temp/floorplan.hq.json` is a Home Quest export with schema version 8. It is not a native Python layout and must not be selected in **Import Python Layout**.
- `temp/layout1.json` is a native Python sample used for smoke validation.
- `2D_layout/01_run.txt` contains the Python editor launch commands.

Python editor launch:

```bat
cd "c:\Users\golde\Desktop\Projects\Home Quest\2D_layout\2dlayoutMaker-main"
.\.venv\Scripts\python.exe app.pyw
```

## Recommended end-to-end manual test

1. Launch the Python editor using `2D_layout/01_run.txt`.
2. Load `single_storey_vastu_reference.json`.
3. Inspect rooms, wall cuts, doors, windows, furniture, flooring, labels, and north.
4. Save the plan again from Python to exercise serializer round-tripping.
5. In Home Quest, choose **Import Python Layout** and select that newly saved native JSON.
6. Inspect both 2D and 3D views; do not use an `.hq.json` file for this button.

## Last validation results

- Importer/asset/reference tests: 3 files, 27 tests passed.
- Production build: passed (`npm run build`).
- Targeted ESLint for integration files: passed.
- Python serializer/generator compilation: passed.
- Real reference JSON parse, asset-resolution, graph-integrity, and 3D-extrusion smoke checks: passed.
- Vite reports an existing large-bundle warning; it does not fail the build.
- Repository-wide lint still has unrelated pre-existing errors outside this integration; changed integration files pass targeted lint.

## Known scope boundaries

- The Python bridge currently imports one floor. Home Quest itself supports multiple floors.
- Python v1 explicitly supports rooms, wall lines, inferred door/window openings, mapped furniture, flooring, text, and compass data. Structures unavailable in the Python source model (stairs, pillars, beams, roads, deck slabs, and railings) are not fabricated.
- Door/window semantics in native v1 come from door furniture and erased wall regions. A future semantic v2 format is only justified if the Python editor gains explicit wall/opening entities.
- Imported unknown furniture is intentionally skipped and reported.

## Worktree warning

The repository has substantial modified, deleted, and untracked user work beyond this integration. No commit was created. Future work must inspect `git status`/`#Git Diff`, modify only relevant files, and never reset or discard unrelated changes.

## Prompt for the next chat

Use this message:

> Read #File docs/2d-3d-integration-handoff.md, follow the workspace steering, and inspect the current #Git Diff without reverting unrelated work. Continue the conversational AI floor-plan feature from the live session state. The implementation is wired from `src/app/Thinker.tsx` through `POST /api/floor-plans/generate`, Vertex AI Gemini 2.5 Pro via `server/vertex_provider.py`, native Vastu v1 validation, and the existing 2D/3D importer. ADC, the Python bridge, real initial generation, and real refinement have been verified. Next run `npm run dev:api` and `npm run dev` for browser-level generate → render → refinement QA. Treat #File 2D_layout/2dlayoutMaker-main/single_storey_vastu_reference.json and the existing importer as format authority. Do not create another renderer or `.hq.json` conversion path. The production build has unrelated missing `src/types/*` blockers documented below.

## Tutorial: how AI floor-plan generation actually works here (for learning)

This section is a learning walkthrough of the AI pipeline in `generate_layout/`. Read it top to bottom; it assumes you know basic Python but not floor-plan generation.

### 1. The core problem: what LLMs are good and bad at

An LLM like Gemini is excellent at *understanding intent* ("put the kitchen in the south-east, four bedrooms, a puja room in the north-east"). It is **bad at exact coordinate arithmetic**: keeping dozens of rectangle corners, mirrored wall openings, and door positions all numerically consistent at the same time. A floor plan needs both. If you ask the model to emit the final pixel coordinates for a 19-room house in one shot, it will get the *design* mostly right but make a handful of *arithmetic* mistakes — a wall opening cut on one room but not its neighbour, a door 15 px off the gap, two pieces of furniture overlapping by a few pixels.

Analogy: it is like a brilliant architect sketching by hand. The rooms and flow are great, but the lines do not meet perfectly. You do not fire the architect; you hand the sketch to a draftsman who cleans up the lines.

### 2. The architecture: LLM designs, deterministic code cleans up, validator judges, loop repeats

This is the same pattern coding agents (Codex, Kiro) use: the model proposes, a **deterministic oracle** checks it, precise errors go back, the model revises. Our oracle is `ai_validator.py`. The "draftsman" is the new `geometry_autofix.py`. The flow in `ai_client.py::generate_layout` is:

```
LLM generates JSON layout
      │
      ▼
geometry_autofix.autofix_layout()   ← cleans up mechanical mistakes (the draftsman)
      │
      ▼
validate_layout()  +  validate_design()   ← strict oracle: schema + brief compliance
      │
      ├── all clear ──▶ return the layout, draw it on the canvas
      │
      └── errors ──▶ send the model its layout + the exact errors, ask for a fix
                     (repeat up to _MAX_ATTEMPTS times)
```

Key idea: the auto-fix only touches *coordinates*, never *design decisions*. It will move a door onto its gap; it will never decide where a room goes. That keeps the output the model's design, not the engine's.

### 3. What `geometry_autofix.py` repairs, and why each pass exists

Each pass targets one class of mistake we actually observed the model make on the 60×80 brief. All tolerances (1 px wall-match, 20 px minimum shared opening, 4 px furniture inset) are copied from `ai_validator.py` so a repaired layout passes *by construction*.

1. **`_repair_degenerate_rooms`** — sometimes the model writes `x1 == x0` (a zero-width room) but states the real size in the room's `width`/`width_real` fields. We rebuild the missing corner from that stated intent and resync the derived fields.
2. **`_normalize_erased_intervals`** — a wall opening (`wall_erased_regions`) must sit within the wall and be sorted/non-overlapping. The model sometimes lets an opening run past a corner. We clamp every interval to its wall, drop empties, sort, and merge.
3. **`_nudge_corner_openings`** — a door in the corner of a room has no swing clearance. We slide any opening back so it keeps at least 1 ft (20 px) from each corner (only if the wall is long enough to hold one).
4. **`_mirror_openings`** — the biggest fix. A doorway between two rooms must be cut on *both* their shared walls at the same spot. The model routinely cuts only one side. For every interior opening, we find the adjoining room and add the matching interval, so the pair is consistent. This alone removed the dominant failure class.
5. **`_snap_doors`** — each door must sit on a real *partial* wall gap. We snap every door to the centre of the nearest partial gap (distance becomes 0). Note we deliberately ignore *full-wall* openings (open-plan gaps) because the validator only treats partial gaps as doorways — matching that rule exactly was a real bug fix.
6. **`_clamp_furniture`** — a bed must be fully inside its room. We compute each item's real footprint (from `FurnitureHelper/furniture_sizes.py`, respecting scale and rotation) and clamp its centre so the whole box fits inside the room with the validator's 4 px inset.
7. **`_separate_furniture`** — two items in the same room must not overlap. This is standard *collision separation*: for each overlapping pair we push them apart along the axis of least penetration by the minimum amount, over a few passes. Minimal movement preserves the model's chosen positions instead of re-arranging the room.

Every one of these is written to *never raise* — a bug in the draftsman must never break generation (`autofix_layout` wraps everything in a guard and returns the layout regardless). And each is *idempotent*: running it twice changes nothing the second time. Both properties have assert-based self-checks in the module's `__main__`.

### 4. Two more reliability levers in `ai_client.py`

- **`_extract_json` tolerates trailing junk.** Models sometimes append stray text after the JSON envelope. Instead of failing, we decode the *first* complete JSON object with `raw_decode` and ignore the rest.
- **`thinking_budget` raised to 8192.** Gemini 2.5 Pro reasons better on spatial packing with more thinking room; 2048 was starving it. `_MAX_ATTEMPTS` is 5 so the repair loop has room for genuine design fixes after the mechanics are auto-cleaned.

### 5. What the validator checks that the auto-fix cannot fix

`validate_design` enforces the *brief*: the four distinct bedrooms exist, rooms sit in their requested Vastu zones, the dining room has a real door to the kitchen and lounge, every wet room has an exterior ventilation window, circulation reaches every room without passing through a bedroom/bath/kitchen, furniture inventory per room, and so on. These are **design decisions**, not arithmetic, so the auto-fix leaves them to the model via the repair loop. This is the current frontier (see live state below): the mechanical layer is solved deterministically; the hardest briefs still need the model to nail every design requirement, which points to per-subtask decomposition as the next step.

### 6. How to run and learn from it

- Auto-fix self-check (offline, free): `.\.venv\Scripts\python.exe generate_layout\geometry_autofix.py`
- Validator self-check (offline, free): `.\.venv\Scripts\python.exe generate_layout\ai_validator.py`
- Real end-to-end generation (calls Vertex): `.\.venv\Scripts\python.exe _ai_smoke_tmp.py` — watch the `details` list shrink across attempts; that list *is* the agent's feedback loop in action.

## Live session state (automatically maintained)

- **Current focus — Staircase guidance added; upper-floor guard remains unresolved:** Stair authoring is available from the Tk Furniture tab with the established 60–500 cm width bounds and 2+ ordered-point workflow. Clicking **Staircase** now opens a native informational popup before placement; the newly supplied live 3D image still shows malformed overlapping/tall terminal guard geometry, so the renderer issue is not closed.
- **Tk popup and capture flow:** `create_furniture_tab` in `2D_layout/2dlayoutMaker-main/toolbar.py` now routes the Staircase button through a small `start_stair_capture` callback. It calls `messagebox.showinfo` with the required two-floor prerequisite, default 110 cm width, straight/L/U point counts, additional-flight behavior, Enter/double-click completion, Escape cancellation, and bottom-to-nearest-upper-floor direction; after dismissal it calls the unchanged `tools.begin_stair_capture(stair_width_var.get())`. `ParityToolbar.begin_stair_capture`, `_canvas_click`, `_structure_motion`, and `_finish_stair` remain the canonical placement path.
- **Stair data/source of truth:** One canonical lower-floor record stores only `id`, `lower_floor_id`, `upper_floor_id`, `path_points`, and `width_cm` through `LayoutSerializer.commit_active_geometry`. `layout_schema` validates stair dimensions and cross-floor ownership; `importVastu` converts Tk pixels/Y-down into shared plan centimeters/Y-up and calls the same pure `buildStair` used by web-authored and sample stairs. No geometry, persistence, undo/redo, floor ownership, source-path offset, or format workaround was changed for the popup.
- **Pending 3D renderer correction:** `src/domains/viewer/components/StairMesh.tsx` currently treats the upper-floor slab as the final flight's terminal landing by passing `hasTopLanding` to every `FlightMesh`, reusing the half-stair-width trim for stringers and rails. Live imagery nevertheless still shows overlapping/tall guard geometry at the upper exit. First-person constraints were not modified: they release axis locking and width clamping in a 0.6 m end apron, and handrail meshes are not direct movement colliders.
- **Files changed for the stair work:** Stair-port work spans `2D_layout/2dlayoutMaker-main/toolbar.py`, `parity_toolbar.py`, `layout_schema.py`, `layout_serializer.py`, `generate_layout/native_v2.py`, `tests/test_parity_foundation.py`, `src/store/persistence/importVastu.ts`, `src/store/persistence/__tests__/importVastu.test.ts`, and `src/domains/viewer/components/StairMesh.tsx`. The latest turn changed only `toolbar.py` to add the instructional popup. Preserve unrelated worktree changes.
- **Validation:** Latest popup change passes targeted IDE diagnostics, `python -m py_compile toolbar.py`, and scoped `git diff --check`. Prior results remain: Python/Tk regression suites **58/58**, targeted importer tests **36/36**, full web suite **114/114** across 20 files, targeted `StairMesh.tsx` ESLint/diagnostics, production build, and Tk materialization smoke all pass; the build retains only its existing large-chunk warning. The popup itself still requires restarted live-Tk confirmation.
- **Next action / blockers:** Fully restart the Tk application and confirm that clicking **Staircase** displays the complete instructions and begins capture after OK. Separately diagnose the clearly visible terminal guard overlap/orientation in `StairMesh` and verify straight/L/U stairs in first person, especially forward and lateral dismount at the upper endpoint. If movement remains blocked, inspect the upper-floor wall at the endpoint separately because current collision code does not collide with the rail mesh. Do not claim the guard issue closed until live rendering and crossing pass.
- **Boundaries/worktree warning:** No stair data, floor openings, room/snapping/furniture placement behavior, collision constants, dependency, or unrelated feature was changed by the popup work. No commit was created. Inspect the current diff before future edits and never reset substantial modified or untracked user work.
