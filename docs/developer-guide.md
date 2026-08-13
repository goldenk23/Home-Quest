# Developer guide

This page is for people who want to **change the code**. It tells you where each behavior lives and which rules you must not break. Read [Architecture](architecture.md) first — it explains the parts; this page explains how to work on them.

## The mental model in one paragraph

The canvas (what you see) and `ProjectState` (the official record) are two different representations of the same plan. `LayoutSerializer` translates between them. A normal edit: changes the canvas, records **one** undoable action, rings the "something changed" bell, and — when needed — lets autosave and 3D fetch a fresh official copy through the serializer. If you keep that picture in your head, most design decisions in the codebase make sense.

## Code map — where things live

| File / folder | What it does, in plain words |
|---|---|
| `app.pyw` | The starting point. Builds every part and connects them. **Start reading here.** |
| `model.py`, `view.py`, `controller.py` | The canvas: what is shown, where the camera is, and how mouse/keyboard events are routed. |
| `tools.py` | The editing behaviors (draw, select, move, snap…). **Big and central — search all callers before changing anything here.** |
| `toolbar.py`, `*_toolbar_tab.py` | The sidebar and toolbar tabs. |
| `entities.py`, `Furniture.py`, `FurnitureHelper/` | How rooms and furniture objects live on the canvas. |
| `Helper/cad_snapping.py`, `Helper/guideline_helper.py` | Snapping math and the on-screen alignment guides. |
| `room_detection.py` | Finds closed wall loops and turns them into rooms. |
| `Helper/door_cut_registry.py` | Keeps track of which walls have door/window cut-outs. |
| `action.py` | Undo/redo, plus the single "something changed" notification path. |
| `layout_schema.py` | The strict project format and its validation rules. The contract everything obeys. |
| `project_state.py` | The keeper of the official project copy; all changes go through checked transactions here. |
| `layout_serializer.py` | Canvas ⇄ official format translation, save/load, and rollback when a load fails. **Also big — treat like `tools.py`.** |
| `local_autosave.py` | The background autosave and rolling backups. |
| `parity_toolbar.py`, `structural_joints.py` | Multi-floor tools and structural elements (pillars, beams, slabs…). |
| `vastu_polygon/geometry.py` | The current Vastu geometry code. (`vastu_geometry.py` is just an old-name forwarding file.) |
| `generate_layout/` | The whole AI pipeline: talk to Google, plan, repair, validate, apply. |
| `embedded_viewer.py` | The built-in 3D window. Its frontend source is **not** in this repository. |

## Rules you must not break

These are the invariants — the load-bearing assumptions. Breaking one usually causes data loss or corrupt projects.

1. **Check before you show.** Never put data from a file, the network, or the AI onto the canvas before it passes validation.
2. **All official changes go through `ProjectState`/`FloorManager`.** Never edit `ProjectState._document` directly. Callers always receive copies, so mutating what you were given does nothing (by design).
3. **Exactly one `LayoutSerializer`** exists, attached to the `ActionManager`. Don't create a second one.
4. **One user action = one history entry = one "changed" notification.** Don't log five undo steps for one drag.
5. **Keep both formats.** The official v2 collections *and* the embedded v1 canvas data must both survive until a real migration replaces them.
6. **IDs are globally unique and every reference must resolve.** A door points at a wall that exists; a stair points at a floor that exists.
7. **Only the UI thread touches widgets.** AI workers send results through the tab's queue; stale answers are dropped via generation IDs.
8. **Treat `viewer_dist/` as sealed.** The hashed files inside it and the `assets/` folder structure must not change — 3D models reference each other by relative paths.
9. **Writes must be atomic** (temp file, then swap). And never overwrite the real `.env`.

## How to make common changes

**Add a new editing command** (e.g., a new tool action):
Find the nearest existing pattern in `CanvasTools` or a toolbar tab, reuse its action-logging and notification calls, then verify: undo/redo, save → reload, autosave, and 3D refresh.

**Add a new kind of geometry** (e.g., a new structural element):
Update `GEOMETRY_COLLECTIONS` plus validation in `layout_schema.py`; teach the serializer to derive and rebuild it; make floor duplication handle it; if 3D should show it, the viewer contract changes too (see rule 8 — that is currently hard).

**Add a floor operation** (e.g., "merge floors"):
Implement it as validate-first-then-commit logic in `FloorManager`, expose it through `LayoutSerializer._commit_project_change`, and use project snapshots so undo and rollback work.

**Change AI behavior:**
Keep the AI's output declarative (a wish list, never final coordinates). Validate and normalize it, let the built-in planners draw the geometry, run repair and strict validation, and apply the result through the serializer on the UI thread.

**Change anything in 3D:**
The Python side and the compiled viewer must agree on message names and shapes. Because the viewer's source is missing, **do not change the protocol** until a reproducible viewer build exists — see [Embedded 3D viewer](embedded-3d-viewer.md).

## Style expectations

- Prefer the existing helper or the Python standard library over new dependencies.
- Make the smallest change that fixes the root cause — no drive-by refactors.
- Keep error messages shown to users actionable ("what do I do now?").
- If you deliberately take a bounded shortcut, mark it with a `ponytail:` comment so the next person knows it's intentional.
- Run the targeted tests, then the full offline checklist in [Testing](testing.md). Anything touching packaging or 3D also needs the manual release checklist.
