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

- **Current focus:** Stabilize the Phase 0-6 Tk multi-planner and migrate the active AI configuration to Gemini 3.1 Pro Preview without changing native v1, `LayoutSerializer.load_document(confirm=True)`, rollback, the web importer, or the existing 2D/3D renderer.
- **Active model configuration:** Both the shared web provider (`AI_MODEL`) and Tk layout generator (`AI_LAYOUT_MODEL`/default) now use `gemini-3.1-pro-preview` through the required `global` location. Runtime `.env`, `.env.example`, and the layout defaults agree. Gemini 3 requests use `ThinkingLevel.HIGH`; explicitly configured Gemini 2.5 rollback models retain the existing numeric thinking budget.
- **Root cause fixed:** `multi` no longer asks Gemini for the comb-only `rows.top`/`rows.bottom` program and no longer requires a valid comb shell before flexible planning. It uses a stage-specific canonical `DesignSpec`, feasibility, hard requirement gates, multiple seeds, scoring, and semantic geometry de-duplication. `comb` keeps the previous program/engine behavior as rollback.
- **Explicit-brief enforcement:** Direct prompt facts override model inventions. The exact 40x60 north-facing three-bedroom Vastu prompt is aligned to zero setbacks when omitted, exactly three bedrooms, one assumed living room/bathroom, requested kitchen and puja, hard SE/NE zones, and a hard living-kitchen open-plan relationship. Unrequested dining, foyer, corridor, and extra-bathroom spaces are removed and disclosed.
- **Phase 0-3 state:** Planner flag/seed fail closed; generation IDs scope progress and terminal events. Direct specs carry stable IDs, dimensions, accessibility, strategy preferences, assumptions, and traceability; invalid output is rejected. Relationship endpoints resolve exact IDs plus safe aliases while ambiguity and self-links fail explicitly. Multi refinement uses the accepted spec plus only the latest request. Feasibility applies practical minima/aspect/setbacks/one-floor scope.
- **Phase 4-6 state:** Bounded deterministic subdivision and fixed topology strategies share `PlacedRoom`, the native builder, hard topology gates, existing validators, transparent scoring, deterministic tie-breaking, and geometry de-duplication. Multi tries multiple seeds and never hides comb among its candidates. The open-living-core topology provides a no-hallway layout for the exact prompt, and native entrance placement avoids an existing exterior window interval.
- **Furniture/deferred state:** Multi furniture has a separate contract plus supported catalog names; failed furnishing cannot silently return an empty shell unless unfurnished output was explicit. Still deferred: Phase 7 pre-apply candidate selection, Phase 9 semantic open boundaries, and the full Phase 10 deterministic furniture placer. Historical pre-change Phase 0 captures cannot be reconstructed.
- **Reliability boundary:** Manual file loading still uses `LayoutSerializer.load_document(..., confirm=True)`. The AI apply path deliberately avoids the blocking modal: it atomically writes `before_ai_apply_<timestamp>.json`, aborts without replacing anything if that backup fails, then calls `load_document(..., confirm=False)`; serializer validation, transactional rollback, autosave, and the existing 3D refresh remain intact.
- **Stopped deleting explicitly-listed rooms (bathroom-trim fix):** `align_with_brief` defaulted bathrooms/living/singular types to a max of 1 when the brief stated no number, which silently dropped an explicitly-named room — a 10-room brief listing both a master and a common bathroom (but never "2 bathrooms") lost the common bathroom (`ignored ... Common Bathroom`). New rule: an explicit number is enforced exactly; living/bathroom the user never mentioned stay capped at 1 (assumed-space guard); a type the user mentioned without a number keeps the model's count. `design_spec` guards assert two explicitly-named bathrooms both survive, while "2 bathrooms" still trims a 3-bathroom spec to 2, and the 40x60 exact prompt still caps its invented second bathroom to one. Audit note for the live 10-room render: it showed 8 rooms because the common bathroom was dropped here (now fixed) and the puja/zone placement needs the BACKEND ACTIVITY to confirm; room sizes running 2-3x requested is the oversized-plot fill, now bounded by the solver's 2x-share cap.
- **CP-SAT `constraint_solver` planner (hard-brief coverage):** Added `generate_layout/planners/constraint_solver.py`, a Google OR-Tools CP-SAT strategy registered behind the existing registry (imported in `planners/__init__.py`); `ortools==9.11.4210` added to `requirements.txt` and installed in the editor `.venv`. It models the plan as integer rectangles on a 1-ft grid and solves for an exact-cover tiling of the buildable envelope satisfying the same hard requirements `validate_topology` enforces: per-room min size, max aspect, area bounds, hard Vastu zone quadrants (N=top/W=left vs footprint midpoint), hard exterior-window rooms on the perimeter, the entrance room on the facing edge, and hard adjacency (direct_door/adjacent/open_plan/attached_to) as a >=3 ft shared wall (plus hard `near`). Exact cover guarantees a gap-free, connected partition so reachability holds without a corridor. Bounded so it yields to subdivision/templates/comb on timeout — a pure add, no pipeline/serializer/renderer change. **Balance fix:** exact cover forced the surplus of an over-sized plot into one degenerate giant room (observed live as a kitchen filling most of a 52x76 plan). Each room's area is now capped at 2x its proportional share of the plot (`target/sum(targets)*plot_area`), which structurally forbids a giant room; the objective pulls toward those shares. This makes the packing harder to solve, so the budget was raised to `max_deterministic_time=60` with a `max_time_in_seconds=30` wall safety cap. On the hard 9-room brief the largest room is now ~28% of the plot (was ~50%+). **Two-phase solve + deterministic-only budget (reliability fix):** `constraint_solver` runs `_solve` twice — Attempt 1 BALANCED (2x fair-share area cap so no room dominates), then, if that finds nothing in its budget, Attempt 2 UNCAPPED which always returns a valid tiling. Stopping is by `max_deterministic_time` only (no wall-clock cap): a wall cap was cutting the search off before it found a feasible tiling, turning solvable briefs into spurious no-solutions. Determinism is asserted on the selected winner, not the solver's bits. **Known limitation (root cause of the "large kitchen"):** the plot is often much larger than the rooms need (52x76 = 3952 ft² for ~10 rooms that need ~2000), and exact cover must fill it, so the surplus becomes a large room. The balanced attempt spreads this (9-room self-check: biggest room 29%), but for ~10 rooms it exceeds the deterministic budget and falls back to the uncapped solve, which lets one room (e.g. the kitchen) absorb the surplus. Per-room hard area caps were tried and rejected: they make CP-SAT's exact-cover search too slow (timeouts → failures). The durable fix is a warm-start hint or a right-sized plot; noted as the next task rather than more time-budget tuning. Solver adds ~30-60s per generation; validation: 9-room self-check valid at 29%, full `_multi_pipeline_check` passes (~125s). Verified end to end: on the hard 9-room east-facing brief (4 zoned bedrooms, attached master bath, open kitchen, puja) every heuristic strategy fails with degenerate aspect/zone errors and subdivision returns nothing, while `constraint_solver` produces a validator-clean, natively-built, scored (0.876), deterministic, selected candidate. It also coexists with `google-genai` (protobuf 5.26). On over-sized plots it may emit a large room, which the validator/scoring reject or rank low, so it never wins spuriously.
- **`strategy_preferences` string coercion + lower Gemini 3 thinking:** Two live failures fixed. (1) The model returned `building.strategy_preferences` as a bare string (`"open_living_core"`); `from_dict` iterated it character by character, so validation reported `unknown strategy preferences: ['_','c','e','g',...]`. New `_as_str_list` wraps a bare string before filtering (same tolerant-shape principle as `furniture_requirements`), with a `design_spec` guard asserting a string preference becomes `["open_living_core"]` and validates clean. (2) `504 DEADLINE_EXCEEDED` is Gemini 3.1 Pro HIGH-thinking latency on large briefs (an infra timeout, not a logic bug). Per project decision the model stays `gemini-3.1-pro-preview` at `ThinkingLevel.HIGH` (default); `AI_LAYOUT_THINKING_LEVEL` can lower it only if the user chooses to trade depth for latency. The model was never changed to Gemini 2.5 — the 2.5 path is inactive rollback only. Gemini 2.5 rollback still uses the numeric budget.
- **Plot-dimension extraction hardened against room-size collisions:** A brief lists many `NxM ft` pairs (plot plus every room), and `align_with_brief` used the *first* regex match, so the plot could latch onto a room size — observed live as "Interpreted 10 spaces on 6x7 ft" (the puja room size) when the model wrongly set the plot and the brief was history-polluted. New `_extract_plot_dimensions(text)` collects all pairs and prefers one whose surrounding text names the plot (`plot`/`lot`/`site`/`parcel`/`land`), else the largest-area pair (a plot always exceeds any room). `design_spec` guards assert `52 ft x 76 ft ... 6x7 ft puja` resolves to `(52,76)`, an unlabelled largest-pair case, and that a model spec mistakenly set to a room's `6x7` is corrected to the brief's `52x76`. Note: the AI tab accumulates the whole conversation, so on an initial generation the brief joins all prior prompts — a stale process or a chat with accumulated history can still mis-seed dimensions; a full restart plus "New Design" (clears the conversation) is the clean-test path.
- **Eliminated brief re-parsing in the multi validation gate (second copy of the same root cause):** `ai_validator.validate_design` also re-reads the raw brief with substring matching (`if phrase in brief: require room`) and emitted "design brief requires a foyer/dining/utility" when the brief's "Do not add" exclusion list contained those words — blocking generation before the geometry solver ever ran. Multi mode now passes an **empty brief** to `validate_design` at every call site (`_run_multi_planner` structure phase, the furnish `full_validator`, and the final validation) via `validation_brief = "" if planner_mode == "multi" else design_brief`, keeping its brief-agnostic geometry/overlap/reachability checks while dropping the fragile requirement logic. Requirements in multi mode are enforced structurally by the DesignSpec + `validate_topology`. Comb mode is unchanged (it has no structured spec). Verified: the hard 9-room spec **with the multi-line exclusion list** now returns feasible and selects `constraint_solver` (0.876) with no "requires a …" error; a `_multi_pipeline_check` regression locks this. Side effect: `constraint_solver` now also validates on the family spec (0.779), since the brief re-parse had been rejecting it.
- **Removed the fragile keyword "requested room" check (earlier root-cause fix, same class):** `align_with_brief` no longer re-derives which non-bedroom rooms the brief wanted via substring matching, and no longer emits "brief requests a <room> but the spec has none". That check repeatedly manufactured false failures because it could not distinguish a request from an exclusion ("do not add an office" contains "office"), and it broke on both inline and multi-line "do not add" lists. The model already interprets the prose; the deterministic layer now enforces only reliably-extractable facts — plot size, facing, floors, zero-setback default, and the bedroom **count** (extra bedrooms pruned to the requested number, too few reported) — plus structural validation (zones, feasibility, geometry, connectivity). Over-generation is bounded by the spec instruction, best-effort invented-room pruning, and feasibility rather than by keyword matching. `_positive_clauses` remains only for best-effort pruning of clearly-excluded room types. `design_spec` guards assert a multi-line exclusion list produces no false errors while the bedroom-count contract still holds.
- **Robustness fixes (general, not prompt-specific):** (1) Advisory metadata in `design_spec.from_dict` (`assumptions`, `locked_constraints`, `traceability`, `furniture_requirements`) is now normalized and clamped, never validated strictly, so the model's formatting choices for hints cannot sink a valid structural spec. `furniture_requirements` specifically accepts an array of `{room_id, items}` or an object keyed by room (`{"room_x": ["bed"]}`, coerced to that list) and ignores scalar/garbage (empty); rooms, plot, and relationships stay strict. This resolved both "furniture_requirements must contain at most 200 items" and "furniture_requirements must be an array". (2) Output-token limits raised because Gemini 3 HIGH thinking shares the output budget: `AI_LAYOUT_MAX_TOKENS` default 32000 with a 65536 cap, per-attempt cap 65536, `.env.example` bumped to 32000. (3) `native_builder.build_native` emits a consistent north-up compass (`direction="N"`, `north_deg_clockwise=0`) instead of `direction=facing`; the plan is always drawn north-up and facing is expressed by the entrance edge, matching the comb engine and the loader's angle-priority draw.
- **Latest validation (offline, no Vertex call; run with the editor `.venv`):** IDE diagnostics clean for `ai_client.py`, `constraint_solver.py`, `planners/__init__.py`, `design_spec.py`, and `_multi_pipeline_check.py`. Resolved Gemini 3 thinking level is `MEDIUM`, Gemini 2.5 budget still 6144. `design_spec` self-check guards string-shaped `strategy_preferences` and plot/room dimension collisions; the `constraint_solver` self-check now asserts a balanced tiling (no room > 40% of plot, ~28% on the hard 9-room brief). Full `_multi_pipeline_check` passes in ~184s (slower because the solver runs several times under the raised budget); a live generation adds ~30s for the solver. `constraint_solver` self-check tiles the hard 9-room brief validator-clean and deterministically; `design_spec`, `feasibility`, `subdivision`, and `_multi_pipeline_check` all pass, including a new exclusion-list regression. Exact 40x60 prompt still selects `open_living_core` at 0.817. End-to-end `_run_multi_planner` on the hard 9-room brief **with the "Do not add" exclusion list** is feasible, selects `constraint_solver` (0.876), and raises no "requires a …" error. `git diff --check` clean except the pre-existing `tab.py` LF-to-CRLF warning.
- **Prior validation (offline, no Vertex call):** `py_compile` and IDE diagnostics are clean for `design_spec.py`, `ai_client.py`, `native_builder.py`, and `server/vertex_provider.py`. Resolved layout config is `gemini-3.1-pro-preview`, `global`, `HIGH`; the Gemini 2.5 path still resolves a 6144-token budget; `max_tokens` default is now 32000. `design_spec` self-check passes including guards that an over-long, object-keyed, or scalar `furniture_requirements` value is normalized (not rejected). `native_builder` and `_multi_pipeline_check` pass; the exact prompt still selects validator-clean `open_living_core` at score `0.817`. `git diff --check` reports only the pre-existing `tab.py` LF-to-CRLF warning.
- **Conversational chat mode implemented (additive; planner/spec/serializer untouched):** Added a chat router to `generate_layout` (`ai_client.py`) that runs **only on a multi-mode refinement turn** (`previous_layout is not None`). One cheap Gemini call (`_INTENT_ROUTER_SYSTEM`, temp 0, its own `_ROUTER_CALL_BUDGET=1` added on top of `_INITIAL_CALL_BUDGET` so it never starves the structural pipeline) classifies the latest message into **structural** / **surgical** / **answer** and returns `change_kind` on every result path. structural falls straight through to the existing spec→planner→furnish pipeline unchanged. **surgical** ("paint a wall", "change flooring", "move a door/window") edits the accepted native JSON in place via `_run_pass` with a new `_SURGICAL_EDIT_SYSTEM` prompt reusing the existing `_REPAIR_SYSTEM` repair loop (`_SURGICAL_CALL_BUDGET=2`), so nothing the user didn't mention moves. **answer** replies in chat with `layout=None`, touching nothing. LangGraph was rejected (would own hand-built control flow and violate the architecture invariant). `tab.py` ok-handler now branches on `change_kind`/`layout is None`: an answer turn appends the reply and leaves canvas, stored layout, and `_ai_spec` untouched; surgical/answer preserve the previous `DesignSpec` for conversation continuity.
- **Chat-mode reliability guards:** Router fails closed to `structural` on any classifier error/garbage (a full re-plan always yields a valid plan). Surgical edits are double-gated — existing `validate_layout` + `validate_design` (empty brief) PLUS a new `_surgical_diff_errors`/`_room_footprints` guard that rejects any secret room add/remove/move/resize by comparing rounded `(x0,y0,x1,y1)` footprints before/after; violations feed the repair loop, and a still-failing edit raises `AIValidationError` → `tab.py` rolls back the turn and restores the prompt (canvas intact). Cancel/timeout flow through both new passes via the existing `claim_call`/`check_abort`.
- **Latest validation (offline, no Vertex call; router/surgical live paths still unexercised):** `py_compile` and IDE diagnostics clean for `ai_client.py` and `tab.py`. New `python -m generate_layout.ai_client` self-check passes (recolor allowed; move/drop/add rejected; missing coords degrade to `None` without crashing). Full `_multi_pipeline_check` passes unchanged (`selected recursive_subdivision`, exact prompt `open_living_core 0.817`), confirming the structural pipeline/planner/scoring/comb paths are untouched.
- **Multi-storey Scope A implemented (additive; single-floor path unchanged):** Independent stacked floors now generate end to end. NEW `generate_layout/native_v2.py` `build_multi_floor_document(floors)` wraps ground-first per-floor native v1 layouts into a v2.0 document — each floor `{id: floor_N, name (deduped), elevation_cm (index×wall_height, ground=0, unique), geometry:{canvas:<v1 layout>}}`, plus valid `metadata` (copied from the ground canvas), `active_floor_id="floor_0"`, valid `sun_settings`, empty `cross_floor_references`. Confirmed the web `convertV2Layout` runs `convertV1Layout` on each floor's embedded `canvas` and regenerates entity ids, so **no cross-floor id namespacing is needed** and the 3D/store side needs zero change. In `ai_client.py`: `_detect_floor_count` (handles "two-storey", "3 floors", "G+2"→3, duplex/triplex, "multi-storey"; capped at `_MAX_FLOORS=4`; returns 1 otherwise), `_allocate_floors` (one cheap Gemini call splitting rooms per floor via `_FLOOR_ALLOCATION_SYSTEM`), and `generate_multi_floor_layout` which generates **each floor with the existing single-floor pipeline verbatim** (`previous_layout=None`, single-floor sub-brief that can't re-trigger detection) and locks every floor to the ground floor's footprint. A guard at the top of `generate_layout` delegates ONLY when `planner_mode=="multi" and previous_layout is None and _detect_floor_count>1`; single-floor, comb, and refinement turns are byte-for-byte unchanged.
- **Multi-storey plot-extraction fix (live bug):** First live run failed with "Interpreted 5 spaces on 14x15 ft" then "buildable area 210 ft² is below … / hard zone SE needs 56 ft² but its quadrant has 52.5 ft²" — every floor resolved its plot as a room size (14×15) instead of 30×36. Cause: the orchestrator built each floor preamble from `design_spec._extract_plot_dimensions(design_brief)`, but the prompt wrote the plot as "30 ft (East-West, road frontage) x 36 ft (…)" whose parentheticals break the `NxM` adjacency the regex needs, so it grabbed the largest room pair. Fix: `_FLOOR_ALLOCATION_SYSTEM` now also returns `plot {width_ft, depth_ft, facing}` (Gemini reads the prose reliably); `_allocate_floors` returns `(plot, facing, floors)`; `generate_multi_floor_layout` resolves the shared plot once up front (allocation → regex fallback → clear error if neither), and each floor preamble is now `"Rectangular plot: W ft x D ft, <facing>-facing. This is a single floor…"` so the downstream `_extract_plot_dimensions` locks the plot over any per-room size. Regression locked in the `ai_client` self-check (the new preamble containing both `30 ft x 36 ft` and a `14x15 ft` room resolves to `(30,36)`). `py_compile` + diagnostics clean.
- **Multi-storey now fully in-Tkinter (web app dropped):** User is discarding the web app; everything must live in the Tk editor. Discovery: the Python app is ALREADY natively multi-floor — `LayoutSerializer.load_document` accepts a native **v2 document with a `floors` list** (`layout_schema.validate_document`/`validate_v2`), `ProjectState`/`FloorManager` hold every floor, `activate_floor(floor_id)` switches the drawn floor, and `_canvas_from_geometry` renders a floor's embedded `geometry.canvas` verbatim (the earlier "single-plane, use the web app" framing was wrong). New delivery: `generate_multi_floor_layout` returns the native v2 doc in `version_2`; `tab.py` atomically backs up the current project and applies the **v2 doc itself** via `load_document(version_2, confirm=False)` (loads all floors, draws ground) instead of the old ground-v1-plus-file approach — the `ai_multifloor_*.json` file write was REMOVED. Added an in-AI-tab **Floor switcher** (`_show_floor_switcher`/`_on_switch_floor`/`_highlight_active_floor`): one button per `project_state.floors` entry that calls `serializer.activate_floor(id)` and highlights the active floor; hidden for single-floor, cleared on New Design. `native_v2.build_multi_floor_document` output confirmed valid against the real `layout_schema.validate_v2`. Note: `ParityToolbar` (an existing full Floors/finishes/sun popover) exists but is NOT mounted in the running app, which is why the AI-tab switcher was added. Scope A limits unchanged (`ponytail:` in `native_v2.py`): stairs not vertically aligned, no `cross_floor_references`, floors generate sequentially (minutes for 3–4, cancellable), post-gen chat refinement targets the ground floor.
- **Latest validation (multi-storey in-Tk):** `py_compile` + IDE diagnostics clean for `ai_client.py`, `tab.py`, `native_v2.py`. `native_v2` self-check now also validates the built doc against the app's own `layout_schema.validate_v2` (passes: 2 floors, ground active). `ai_client` self-check (chat-mode + floor-count + plot-preamble) passes. Full `_multi_pipeline_check` identical to pre-change — single-floor pipeline untouched.
- **Latest validation (offline, no Vertex call; multi-floor allocation/per-floor live calls still unexercised):** `py_compile` + IDE diagnostics clean for `ai_client.py`, `tab.py`, `native_v2.py`. `python -m generate_layout.native_v2` self-check passes (one ground floor, unique ids/names/elevations, v1 canvas per floor, non-v1 rejected). `python -m generate_layout.ai_client` self-check passes including floor-count detection (single-floor briefs and generated per-floor sub-briefs both resolve to 1). Full `_multi_pipeline_check` output is identical to pre-change (`selected recursive_subdivision`, exact prompt `open_living_core 0.817`), confirming the single-floor pipeline is untouched.
- **Multi-storey confirmed working live (G+1):** After the plot-extraction fix, the G+1 test prompt (30x36 ft; ground = living/kitchen(SE)/dining/puja(NE)/common bath/stair, first = master(SW)+attached bath/bed2(NW)/bed3(W)/common bath/stair) generated end to end — backend feed showed per-floor generation and the ground floor applied to the Tk canvas. The v2.0 stack was written to `2D_layout/2dlayoutMaker-main/ai_multifloor_20260730_041941.json`. The feasibility-checked prompt was provided in chat only (NOT saved to `docs/prompt.txt`; do not write test prompts there without explicit permission).
- **Latest live evidence:** A fresh restarted run logs `Planning 2 floors`, completes both Ground and First generation, then reports `Stacked 2 floors` and `Loaded 2 floors`, while each 3D screenshot still contains one storey. This proves generation, v2 construction, and AI-side apply succeed; the failure is a split live project state before viewer serialization. The prior interpretation of the vertically combined screenshots as detached floors in one scene was incorrect.
- **Definitive root cause fixed — duplicate serializers/project states:** `MiniAutoCADApp` creates the authoritative `self.serializer`, and the embedded viewer calls `self.serializer.serialize_layout()`. Later, `EditToolbarTab` created a second `LayoutSerializer(...)`, whose constructor overwrote `actions.serializer`; the AI tab therefore loaded two floors into serializer B while 3D serialized serializer A's stale one-floor project. `edit_toolbar_tab.py` now reuses `self.actions.serializer`, so AI, Edit save/load, autosave, floor controls, and 3D share one `ProjectState` owner. **Regression prevention:** `LayoutSerializer.__init__` now fails immediately if `actions.serializer` already references another instance, making a future duplicate impossible to introduce silently anywhere in the runtime.
- **Cross-floor alignment hardening remains:** `convertV2Layout` normalizes each nested Python canvas's non-model pan/viewport offset after canonical overlays are merged, then applies the shared project origin. Once the shared serializer delivers both floors, Ground and First share one X/Z footprint while `FloorScene` applies the first-floor elevation.
- **Generation/apply fixes remain:** Explicit G+1 requests in the latest turn always enter the multi-floor route regardless of previous AI layout. `tab.py` atomically backs up the current project and applies v2 with `confirm=False`; backup failure aborts replacement, while manual imports retain confirmation.
- **Latest validation (offline, no Vertex call):** Python compilation passed for `app.pyw`, `edit_toolbar_tab.py`, `layout_serializer.py`, and `generate_layout/tab.py`; IDE diagnostics are clean for both serializer files; serializer/project tests pass 19/19 after the single-owner guard. Repository search confirms the active Edit toolbar no longer constructs a serializer; the dormant legacy constructor cannot silently replace the owner because the new guard would raise. Earlier web validation remains green: importer tests 29/29 and production build succeeds.
- **Next useful action / blocker (multi-storey):** To avoid another paid generation, before closing the currently running **old-code** app use the Edit sidebar's **Save as JSON** action—the duplicate Edit/AI serializer in that process holds the generated two-floor v2 project. Then fully close/reopen Home Quest, load that JSON, and open **3D View**. The only remaining blocker is this restarted live visual check with the single shared serializer. If the old process has already closed without saving and autosave contains only serializer A's one-floor state, one regeneration may unfortunately be required. Future Scope B remains vertically aligned stair geometry plus `cross_floor_references`.
- **Next useful action (chat mode):** Restart the editor + New Design, then live-test the three intents: a structural follow-up ("add a store room"), a surgical edit ("paint the living room walls blue" / "change kitchen flooring to marble" / "move the front door to center"), and a question ("why is the puja in the NE?"). Confirm surgical edits leave every other room's footprint identical and answer turns don't alter the canvas. Separately verify the R3F 3D renderer honors `fill_color`/`material_id` so paint/flooring shows in 3D (the Python `layout_serializer` already recreates them on the Tk canvas).
- **Next useful action (multi-planner):** Fully close and relaunch the Home Quest launcher (the editor loads Python once; `.env`/code changes need a restart) AND click "New Design" to clear the accumulated AI conversation before testing, so an earlier prompt's dimensions cannot bleed into the joined brief. Then rerun the hard prompt and confirm BACKEND ACTIVITY shows the correct plot (e.g. `52x76 ft`) and `selected_strategy=constraint_solver`. If a plan applies but the compass is not visible, capture a screenshot of the successful canvas: the compass is emitted, migrated, and drawn at fixed canvas coords `(60,60)`, so any remaining invisibility is a canvas viewport/z-order matter, not missing data.
- **Current blocker/risk:** Live Gemini 3.1 Pro (public preview) behavior is still unmeasured here; the offline pipeline is proven, but only a restarted live call confirms the full model→spec→solver→native→apply path on a real request. `constraint_solver` uses a deterministic time budget (~seconds) that adds to each multi-mode generation; acceptable versus the minute-scale model calls but worth watching on very large briefs.
- **Remaining boundary:** Do not create another renderer, bypass `LayoutSerializer`, or route Python-native files through `.hq.json`.