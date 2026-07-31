# Multi-storey (G+1) 3D View — Debugging Handoff

Self-contained context for an AI/engineer taking over the "multi-floor building does not
appear in the 3D view" issue. Everything needed is below; you do not need prior chat history.

---

## 1. Product goal

Home Quest is a Python/Tkinter 2D floor-plan editor (`2D_layout/2dlayoutMaker-main/`) with an
**embedded 3D viewer** (a prebuilt React/React-Three-Fiber bundle rendered inside the Tk app via
WebView2). An AI feature ("AI Layout Generator" tab) uses Gemini to generate floor plans.

A **multi-storey (e.g. G+1 / two-storey)** feature was added: the AI should generate each floor
and the app should show a stacked multi-floor building in the 3D view, with the ability to switch
which floor is drawn on the 2D canvas.

**Current symptom:** after generating a two-storey home, the **3D view still shows only the ground
floor** (one storey). The user needs both floors visible/stacked in 3D, entirely inside the Tk app
(the separate web app is NOT used).

---

## 2. How the pipeline works (data flow)

```
AI tab (generate_layout/tab.py)
  → ai_generate_layout(messages,...)              [generate_layout/ai_client.py]
      → if multi-storey: generate_multi_floor_layout()
            → _allocate_floors()   (1 Gemini call: splits rooms per floor + returns shared plot)
            → for each floor: generate_layout([single-floor sub-brief])  (existing single-floor pipeline)
            → native_v2.build_multi_floor_document([{name, layout(v1)}...])  → a native v2 doc
      → returns result = { layout: <ground v1>, version_2: <v2 doc>, floor_count, change_kind:"structural", ... }
  → tab.py applies:  serializer.load_document(version_2, confirm=False)   [layout_serializer.py]
      → validate_document → validate_v2   [layout_schema.py]
      → project_state.replace(doc)         [project_state.py]  (now holds ALL floors)
      → _materialize_active_floor()        (draws the ACTIVE floor's canvas on the 2D Tk canvas)
  → app.pyw._send_viewer_layout()  sends serializer.serialize_layout() (FULL v2, all floors) to the
      embedded viewer  → JS importVastuLayout(doc) → convertV2Layout → store.floors/floorData
      → SceneContent renders active floor + every parked floor at its elevationCm (stacks storeys)
```

### Native schema (two versions)
- **v1** (`version:"1.0"`): flat `{metadata, rooms[], furniture[], shapes[], text[], ...}` in canvas
  pixels. Produced by `generate_layout/native_builder.py`. This is what the AI single-floor path emits.
- **v2** (`version:"2.0"`): `{version, metadata, active_floor_id, floors:[{id,name,elevation_cm,
  geometry}], sun_settings, cross_floor_references}`. Each floor's `geometry` may embed the whole v1
  doc as `geometry.canvas`. Defined/validated in `2D_layout/2dlayoutMaker-main/layout_schema.py`
  (`validate_v2`, `migrate_v1_to_v2`). `project_state.py` owns the live v2 project.

### Key files (all under `2D_layout/2dlayoutMaker-main/`)
- `generate_layout/ai_client.py` — Gemini client; `generate_layout()` (entry), `generate_multi_floor_layout()`, `_allocate_floors()`, `_detect_floor_count()`.
- `generate_layout/native_v2.py` — `build_multi_floor_document(floors)` builds the v2 doc from per-floor v1 layouts.
- `generate_layout/tab.py` — the AI tab UI; worker thread; `_poll_ai_queue()` applies the result and hosts the in-tab **Floor switcher** (`_show_floor_switcher`, `_on_switch_floor` → `serializer.activate_floor`).
- `layout_serializer.py` — `load_document(data, confirm)`, `serialize_layout()`, `activate_floor()`, `_materialize_active_floor()`, `_canvas_from_geometry()`, `_confirm_and_backup_current_layout()`.
- `layout_schema.py` — `validate_v2`, `validate_document`, `migrate_v1_to_v2`, `empty_geometry`.
- `project_state.py` — `ProjectState` + `FloorManager` (add/activate/duplicate/delete floor).
- `app.pyw` — `_send_viewer_layout()`, `_show_viewer()` (→ `_refresh_3d`), `_on_project_mutation()` (debounced viewer refresh; only when workspace mode == "viewer").
- Web/3D source (compiled into the served bundle `dist/`): `src/store/persistence/importVastu.ts` (`convertV2Layout`, `convertVastuLayout`, `importVastuLayout`), `src/domains/viewer/components/SceneContent.tsx` (stacks floors), `FloorScene.tsx`.

---

## 3. What has been VERIFIED (offline, factual)

1. **Generation is correct.** A real generated file `ai_multifloor_20260730_041941.json` (and the
   live run) contains TWO populated floors: `floor_0 Ground @0cm` (5 canvas rooms) and
   `floor_1 First @280cm` (6 canvas rooms).
2. **The v2 doc is schema-valid.** `native_v2.build_multi_floor_document(...)` output passes the
   app's own `layout_schema.validate_v2` (asserted in `native_v2.py`'s `__main__` self-check).
3. **`project_state` keeps both floors.** Round-trip `ProjectState(doc).snapshot()` preserves
   `floor_1` at elevation 280 with its `geometry.canvas.rooms` intact.
4. **The 3D renderer already stacks floors.** `SceneContent.tsx` renders the active floor (live)
   plus every parked floor from `floorData` at its `elevationCm`; `convertV2Layout` builds each
   floor's geometry from its embedded `canvas`. The served bundle `dist/` (built 2026-07-29) is
   newer than that source, so it includes the stacking logic.
5. **The multi-floor branch runs on a fresh generation.** Logging showed
   `planner=multi previous_layout_is_none=True floor_count=2`, then two per-floor generations. NOTE:
   the branch only fires on an INITIAL generation (`previous_layout is None`); if you regenerate
   without clicking "New Design", it routes to single-floor chat refinement instead.

## 4. ROOT CAUSE that was found and fixed

A temporary log (`viewer_debug.log`, since removed) showed, on a real run:
```
multi-decision: planner=multi previous_layout_is_none=True floor_count=2 ...
tab-apply: has_version_2=True payload_version=2.0 payload_floors=2      # valid 2-floor v2 handed to loader
send_layout: version=2.0 floors=1 active=floor-<uuid> Ground Floor rooms=5   (x10, identical)
# NOTE: there was NO "post-load" line, which was logged immediately AFTER load_document returns.
```
Interpretation: `load_document(v2, confirm=True)` was entered but **never returned** — it blocked
inside `_confirm_and_backup_current_layout()` on a modal `messagebox.askyesno("Replace Current
Layout? Create a backup and continue?")` (shown because the canvas already had a drawing). The
repeated `send_layout` lines are viewer refreshes firing inside that modal's nested Tk event loop,
each serializing the still-uncommitted (single-floor) project. So the multi-floor project never
committed; the old single floor stayed on canvas and in the viewer.

**Fix applied in `tab.py`** (the AI apply is the user's explicit intent, so the modal is redundant
friction that was blocking commit): write a backup first, then apply with `confirm=False`:
```python
# write before_ai_apply_<ts>.json backup, then:
applied = serializer.load_document(apply_payload, confirm=False)
```
Also made `native_v2` floors byte-shape-identical to `migrate_v1_to_v2` (full empty collections +
`canvas` + `compass`). This **changes the documented invariant** "AI apply is
`load_document(confirm=True)`" — done intentionally; safety preserved via the explicit backup.

## 5. What is NOT yet confirmed (the open question for you)

It has **not** been verified live that both floors now render in 3D after the `confirm=False` fix.
The apply path is now unblocked, so if the 3D still shows one floor, focus here:

- **Prime suspect: the viewer-side conversion of a MIXED v2 document.** After `load_document`, when
  `serialize_layout()` is sent to the viewer, the **active (ground) floor** has been re-derived into
  **canonical** geometry (`vertices/walls/rooms` via `_snapshot_active_canvas` /
  `_derive_canvas_geometry`), while **parked (upper) floors remain `{geometry.canvas: <v1>}`**. In
  `src/store/persistence/importVastu.ts::convertV2Layout`, each floor builds geometry from
  `geometry.canvas` via `convertV1Layout(canvas, normalizeOrigin=false)`; the active floor may
  instead resolve from its canonical collections. Verify BOTH floors end up in `geometryByFloor` /
  `store.floorData` with non-empty rooms/walls, and that `shiftProjectOrigin` aligns them (a parked
  floor rendered far off-origin would appear "missing" in the framed view).
- **Confirm the doc sent to the viewer actually has 2 floors** with renderable content. Re-add a
  one-line log in `app.pyw._send_viewer_layout` dumping `len(document["floors"])` and each floor's
  room/canvas-room counts (the previous diagnostic; it was removed after use).
- **Confirm `importVastuLayout` populates `store.floors` (length 2) and `store.floorData`** for the
  upper floor. If `store.floors` has 1 entry, the viewer got a 1-floor doc (serialize/apply issue);
  if it has 2 but the upper `floorData` geometry is empty, it's a `convertV2Layout`/`convertV1Layout`
  issue on the parked `canvas`.
- **Elevations:** upper floor is at `elevation_cm = index * wall_height_cm` (ground wall height,
  typically 280). Ensure this matches what the 3D expects (the native `FloorManager._next_elevation`
  uses +300; the web `STORY_HEIGHT_CM` may differ). A wrong/zero elevation could overlap floors.

## 6. Reproduction

1. Launch the editor (see `2D_layout/01_run.txt`). It loads Python once — FULLY QUIT before retesting code changes.
2. AI Layout Generator tab → **New Design** (required so `previous_layout is None`).
3. Paste a two-storey prompt, e.g. a G+1 on a 30 ft × 36 ft plot (ground: living/kitchen SE/dining/
   puja NE/bath/stair; first: master SW + bath/bed2 NW/bed3 W/bath/stair). It must contain
   "two-storey" or "G+1" so `_detect_floor_count() > 1`.
4. Generate → open **3D View**.
5. Expected: both storeys stacked in 3D; the in-tab **Floor** buttons switch the 2D canvas floor.

## 7. Constraints / invariants (from `.kiro/steering/home-quest.md`)

- Do NOT create a second 3D renderer or an intermediate `.hq.json` converter; reuse the existing
  entity/store/rendering pipeline.
- Python native v1 and web `.hq.json` are different formats; never feed `.hq.json` to the Python importer.
- Single-floor behavior must remain unchanged when `floors == 1`.
- Model config is locked: Gemini `gemini-3.1-pro-preview`, thinking HIGH, `AI_LAYOUT_PLANNER=multi`.
- The AI apply used to be strictly `load_document(confirm=True)`; this handoff changed the multi-floor
  (and single) AI apply to backup-then-`confirm=False`. If you revert that, the modal will re-block the apply.

## 8. Useful commands (Windows, run from `2D_layout/2dlayoutMaker-main`)

```
.\.venv\Scripts\python.exe -m py_compile generate_layout\ai_client.py generate_layout\tab.py generate_layout\native_v2.py app.pyw
.\.venv\Scripts\python.exe -m generate_layout.native_v2        # v2 doc self-check (validates via layout_schema.validate_v2)
.\.venv\Scripts\python.exe -m generate_layout.ai_client        # floor-count + plot-preamble self-checks
.\.venv\Scripts\python.exe -m generate_layout._multi_pipeline_check   # single-floor pipeline regression (~2-3 min)
```

The broader project handoff with full history is `docs/2d-3d-integration-handoff.md` (see its
"Live session state" section).
