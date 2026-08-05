# Handoff: room snapping in the Python/Tkinter 2D editor

**Purpose:** everything another engineer/AI needs to fix "dragging rooms together does not snap"
in the Tk editor. Written after several failed attempts; the failures are documented because they
narrow the search.

> **Status: FIXED.** The §8 oscillation was reproduced by the multi-event test, then fixed with the
> §8 "Recommended fix" (anchored absolute-position snapping with break-away hysteresis) in
> `CanvasController._snap_room_delta` / `_snap_axis`. The `> 0.5` "already sits on it" filter of §4
> is gone — with an anchor it is no longer needed, and it was what caused the bouncing.
> `_drag_anchor` is reset in `select_item` (new press) and `on_release`. Nothing outside the
> controller drag path changed. Regression test:
> `tests.test_room_drag_group.test_snap_holds_across_many_small_motion_events` (32 tests pass).
> Sections 4-8 below are kept as the historical record of why it broke.

---

## 1. The requirement (user's words, paraphrased)

- With the **Room tool**, two rooms can be brought together and "patched" (edges align flush) to
  assemble a house. That already works.
- With the **Draw tool** (Line tool loops that become rooms), the same must work: bring two
  separately drawn rooms close and they should snap flush. Switching tools should feel identical.
- Current state: **it does not snap.**

---

## 2. Environment

| Item | Value |
|---|---|
| App root | `c:\Users\golde\Desktop\Projects\Home Quest\2D_layout\2dlayoutMaker-main` |
| Entry point | `app.pyw` — **no console window, so every `print` is discarded** |
| Python | `.\.venv\Scripts\python.exe` (run from the app root) |
| Launch | `Set-Location "C:\Users\golde\Desktop\Projects\Home Quest"; powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\run-home-quest.ps1"` |
| Kill stale editors | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\2D_layout\kill-python-editor.ps1"` |
| Tests | `.\.venv\Scripts\python.exe -m unittest tests.test_parity_foundation tests.test_room_drag_group` (31 tests, all passing) |
| Syntax check | `.\.venv\Scripts\python.exe -m py_compile controller.py` |

**Tkinter loads Python once** — source edits require a full app restart. Verify the running
process actually postdates your edit (`Get-CimInstance Win32_Process`), because a stale
interpreter has already wasted debugging time in this project once.

**Diagnosing GUI behaviour:** because there is no console, add a temporary module that appends to
a log file next to the app, then read the file. Prints are useless here.

---

## 3. How rooms exist on the canvas (essential background)

There are **two completely different kinds of room**:

### A. Room-tool room — a real entity
`entities.py::RoomEntity` creates a `rectangle` plus a `text` label, both tagged
`("room", "room_group_<n>")`. It is registered in `CanvasTools.room_entities_by_group_tag`.
Dragging it is handled by an existing branch in `CanvasController.on_drag` that snaps via
`Helper/guideline_helper.py::get_room_alignment_snap`. **This path works. Do not modify it.**

### B. Draw-tool room — a derived overlay
1. The Line tool creates wall lines tagged `("line", "committed_line", "line_<uuid>")`, each with a
   measurement label and an endpoint marker sharing the `line_<uuid>` tag.
2. When a loop closes, `tools.py::start_line` also creates a **`closed_shape` polygon** over the
   walls (outline in the line colour, no fill). It is easy to mistake this for the walls.
3. `layout_serializer.py::refresh_detected_room_overlay()` runs planar-graph face extraction
   (`room_detection.py`) over the wall graph and, for each detected face, creates:
   - a `polygon` tagged `parity_detected_room`, `entity:<room-id>`, `floor:<id>`
   - a `text` label tagged `parity_detected_room`, `detected_room_label:<room-id>`
4. `_tag_detected_room_drag_group()` then adds a synthetic tag
   **`parity_room_drag:<room-id>`** to the overlay polygon, its label, every boundary wall's
   `line_<uuid>` group, and any coincident `closed_shape` polygon — so the whole room drags as one
   unit.
5. `CanvasController.select_item` gives `parity_room_drag:*` **precedence** over the individual
   `line_*` tag, so clicking a wall drags the whole room.

Room ids are derived from boundary vertex ids, so **a room's id changes when geometry merges**
(see §7 known issue).

Unnamed rooms are intentionally invisible: overlay polygon `fill=""`, label `fill="#0f172a"`
(near-black on the dark canvas). The label item must keep existing because
`tools.py::create_room_from_closed_lines` only offers a room for naming when it has *both* a
polygon and a label. Do not "fix" the label colour — making it visible looks like unwanted
automatic room naming, which the user rejected.

---

## 4. Current snapping implementation (the thing to fix)

`controller.py`, called from `on_drag` at **line ~324**:

```python
# Draw-tool rooms (closed line loops) snap flush to neighbouring rooms
if self.dragging_group.startswith("parity_room_drag:"):
    dx, dy = self._snap_room_delta(self.dragging_group, dx, dy)

# Normal group dragging using tag-based move
self.canvas.move(self.dragging_group, dx, dy)
```

Supporting methods, `controller.py` lines ~557-676:

- `_room_bounds(item)` → `(x0, y0, x1, y1)` from an item's own coordinates (not `bbox()`, which
  would include text extents).
- `_dragged_group_bounds(group)` → bounds of the dragged room's overlay polygon, falling back to
  the union of its wall items.
- `_snap_candidates(exclude_group)` → sets of candidate `x` and `y` edge coordinates gathered from
  every non-grid `line` item, every other `parity_detected_room` polygon, and every
  `room_entities_by_group_tag` rectangle, excluding items in the dragged group.
- `_snap_room_delta(group, dx, dy, tolerance=8.0)` → adds the nearest within-tolerance shift to
  `dx`/`dy`. Includes this filter, added to stop rooms freezing (see §6, attempt 4):

```python
edge_xs = {v for v in edge_xs
           if abs(v - bounds[0]) > 0.5 and abs(v - bounds[2]) > 0.5}
edge_ys = {v for v in edge_ys
           if abs(v - bounds[1]) > 0.5 and abs(v - bounds[3]) > 0.5}
```

This design only ever adjusts the drag delta. It does not touch room detection or the overlay
pipeline.

---

## 5. Critical mechanic: `drag_start_pos` resets every event

At the end of the group-drag path, `on_drag` does `self.drag_start_pos = (event.x, event.y)`.
So `dx`/`dy` are **per-event increments of 1-3 px**, not the total drag distance. Any snapping
built on those increments has no memory of where the drag started.

There is also a motion throttle at the top of `on_drag`
(`self._motion_throttle_ms`), which coalesces events.

---

## 6. What was already tried, and exactly what each attempt proved

1. **Snap only to detected rooms.** Failed live. Cause: if the neighbour is an open loop or a lone
   wall (never a detected room), the candidate list was empty and snapping silently did nothing.
   Fixed by broadening `_snap_candidates` to all wall lines.
2. **Reused `guideline_helper.get_room_alignment_snap` for drawn rooms.** Reverted. It unpacks
   exactly four coordinates, so polygon-based rooms were skipped; adapting it meant editing a
   working component.
3. **Changed `room_detection.dedupe_walls` to keep coincident walls** (to give each room its own
   shared wall). **This broke room detection** and was reverted. Reason: the `closed_shape`
   polygon duplicates every wall, and `detect_rooms` marks visited edges by direction, so
   duplicates swallow faces. **Do not touch `dedupe_walls` or `detect_rooms`.**
4. **Per-event delta snapping (current code).** File logging on the user's real canvas produced the
   decisive evidence:

```
snap: bounds=(437.5, 140.0, 665.0, 420.0)
snap: candidates x=2 y=2 nearest_x=[437.5, 210.0] nearest_y=[420.0, 140.0]
snap: moved_edges=(438.5, 140.0, 666.0, 420.0) in=(1,0) out=(0.0,0.0) snapped=True
```

The rooms were **already flush at x=437.5**; the neighbour's shared wall is a separate canvas line
at that coordinate, so it was a snap target on the dragged room's *own* edge. Every increment was
cancelled to `(0.0, 0.0)` — the room was frozen. The `> 0.5` filter in §4 was added to fix that,
and it does (verified), but see §8.

---

## 7. Known related issue (currently unfixed, out of scope but relevant)

A room's id is rebuilt from its boundary vertex ids. When two rooms are patched, their corner
vertices merge, the surviving vertex id changes, the room id changes, and any user-assigned name
and colour (stored in `LayoutSerializer._detected_room_overrides`, keyed by room id) is dropped —
measured as fill going `#d0f0c0` → `""`. A durable fix needs an identity that survives corner
merging **without** modifying wall dedupe or `detect_rooms`. An attempt that stamped identity onto
boundary lines worked in tests but was reverted along with the `dedupe_walls` regression.

---

## 8. Root cause — REPRODUCED AND CONFIRMED

Per-event delta snapping cannot hold an alignment, and the anti-freeze filter of §4 guarantees it
oscillates:

- Event N: gap is 5 px → snap applies → the room lands flush, so `bounds` now equals the candidate.
- Event N+1: that candidate is filtered out (the room "already sits on" it), so the room moves by
  the raw delta and immediately leaves the flush position.
- Event N+2: it is 1 px away again → snaps back. And so on.

**Measured** with the multi-event harness in §10 (dragging left one pixel per event, from a 20 px
gap, neighbour edge at x=500). Values are the dragged room's left edge:

```
519, 518, 517, 516, 515, 514, 513, 512, 511, 510, 509, 500, 499, 500, 499, 500, 499, 500, 499
```

It reaches 500, then bounces 500 → 499 → 500 → 499 indefinitely. The room never holds the flush
position, which is precisely why the user reports "snapping is not working" even though a
single-event test shows `500.0`.

**This is the bug to fix.** Every existing single-event test passes against this broken behaviour,
which is why it survived several rounds of "verified" fixes.

### Recommended fix

Standard CAD-style drag snapping: **anchor the drag, snap the absolute position, add hysteresis.**
Note this also removes the need for the `> 0.5` filter, because the desired position is derived from
the pointer rather than from the room's current position, so a flush room can no longer freeze
itself.

1. On drag start (`select_item`, where `dragging_group` is set), record
   `self._drag_anchor = (pointer_x, pointer_y, *room_bounds)`.
2. On each motion event compute the *desired* absolute position from the anchor:
   `desired_x0 = anchor_x0 + (event.x - anchor_pointer_x)` (same for y). Do **not** accumulate
   per-event deltas.
3. Snap `desired` to the nearest candidate edge within tolerance (say 10 px), *including* edges the
   room currently sits on — with an anchor there is no freeze risk, because the desired position
   comes from the pointer, not from the room's current position.
4. Add break-away hysteresis: once snapped to an edge, keep it until the desired position is more
   than, say, 15 px from that edge. This is what makes snapping feel magnetic.
5. Move by `snapped_desired - current_bounds`, then set `drag_start_pos = (event.x, event.y)` as the
   existing code does (or leave `drag_start_pos` alone and drive everything from the anchor).
6. Clear `self._drag_anchor` in `on_release`.

Optional: also snap to grid intersections (`model.grid_spacing * model.zoom_level`) so a lone room
aligns to the grid; and draw alignment guides via
`Helper/guideline_helper.py::draw_room_alignment_guides` for feedback.

---

## 9. Hard constraints

- **Do not modify** `room_detection.py` (`dedupe_walls`, `detect_rooms`), the overlay creation in
  `refresh_detected_room_overlay`, or `Helper/guideline_helper.py`. Each has broken something once.
- **Do not make unnamed room labels visible.** See §3.
- Keep `planarize()` / `split_walls_at_vertices()` in `room_detection.py` — they make divider lines
  split a room into multiple detected rooms and are confirmed working.
- The change should stay inside `CanvasController` (drag path) so it can be reverted by deleting one
  method group and its call site.
- The worktree contains substantial uncommitted user work. Do not revert unrelated files.

---

## 10. Reproduction harness (headless, no GUI, verified to work)

Run from the app root with `.\.venv\Scripts\python.exe -`:

```python
import tkinter as tk
from types import SimpleNamespace
from layout_schema import new_project
from layout_serializer import LayoutSerializer
from project_state import ProjectState
from controller import CanvasController

def setup():
    root = tk.Tk(); root.withdraw()
    canvas = tk.Canvas(root, width=1200, height=800); canvas.pack(); canvas.update_idletasks()
    s = LayoutSerializer.__new__(LayoutSerializer)
    s.canvas = canvas
    s.model = SimpleNamespace(unit="feet", unit_scale={"feet": 1.0}, grid_spacing=20, zoom_level=1.0)
    s.view = SimpleNamespace(grid_visible=True, pixel_to_real=lambda x, y: (float(x), float(y)))
    tools = SimpleNamespace(image_furniture_items=[], windows=[], room_entities_by_group_tag={},
                            room_flooring_images={}, line_metadata={}, current_compass_direction=None,
                            canvas_frozen=False, _cancel_line_input=lambda: None)
    s.tools = tools
    s.project_state = ProjectState(new_project())
    s._detected_room_overrides = {}
    c = CanvasController.__new__(CanvasController)
    c.canvas = canvas; c.tools = tools; c.model = SimpleNamespace(get=lambda k: False)
    c.dragging_item = None; c._last_motion_time = 0; c._motion_throttle_ms = 0
    return root, canvas, s, c

def loop(canvas, x0, y0, x1, y1, p):
    for i, e in enumerate([(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]):
        canvas.create_line(*e, tags=("line", "committed_line", f"line_{p}{i}"))

root, canvas, s, c = setup()
loop(canvas, 200, 100, 500, 400, "a")
loop(canvas, 520, 100, 800, 400, "b")          # 20 px gap
s.refresh_detected_room_overlay()

poly = [i for i in canvas.find_withtag("parity_detected_room")
        if canvas.type(i) == "polygon" and min(canvas.coords(i)[0::2]) == 520.0][0]
group = [t for t in canvas.gettags(poly) if str(t).startswith("parity_room_drag:")][0]

c.dragging_group = group
c.drag_start_pos = (600, 200)
# IMPORTANT: simulate a real drag as MANY small events, like the mouse produces.
for x in range(599, 580, -1):
    c.on_drag(SimpleNamespace(x=x, y=200))
    c.drag_start_pos = (x, 200)
print("left edge:", min(canvas.coords(poly)[0::2]), "- expect 500.0 and to STAY there")
root.destroy()
```

**This multi-event loop is the test that matters.** It reproduces the live bug today, printing
`519, 518, ... 509, 500, 499, 500, 499, ...` and a final value of `499.0`. Earlier single-event
tests passed while the real app failed. Assert the room *holds* the flush position across continued
small movements, and that a deliberate large drag still breaks away.

Add it to `tests/test_room_drag_group.py` as a failing test first, then fix.

---

## 11. Acceptance criteria

1. Two drawn rooms brought within ~10 px snap flush and **hold** while the mouse keeps moving
   slightly (magnetic feel), across many small motion events.
2. A deliberate larger drag breaks away cleanly; no room is ever frozen in place.
3. A drawn room snaps to a Room-tool room and vice versa.
4. A drawn room snaps to a lone wall or an open (non-room) shape.
5. Room-tool → Room-tool snapping is unchanged.
6. Detection counts unchanged: plain loop 1 room; one divider 2; two crossing dividers 4; two
   separate loops 2 (each verified with the `closed_shape` closing polygon present).
7. No automatic room names appear on a freshly drawn loop.
8. `tests.test_parity_foundation` + `tests.test_room_drag_group` still pass (31 tests today).
9. Verified in the **running app** after a full restart, not only headlessly.

---

## 12. Key files

| File | Relevance |
|---|---|
| `controller.py` | `select_item` (group precedence, ~line 785), `on_drag` (~244, snap call ~324), `on_release` (~402), snap helpers (~557-676) |
| `layout_serializer.py` | `refresh_detected_room_overlay`, `_boundary_line_items`, `_tag_detected_room_drag_group`, `_derive_canvas_geometry`, `_detected_room_overrides` |
| `room_detection.py` | `detect_rooms`, `dedupe_walls`, `merge_vertices_by_position`, `planarize`, `split_walls_at_vertices` — **do not modify** |
| `tools.py` | `start_line` (wall + `closed_shape` creation), `create_room_from_closed_lines` (naming/colour), `_trigger_room_detection` (150 ms debounce) |
| `entities.py` | `RoomEntity` (Room-tool rooms) |
| `Helper/guideline_helper.py` | Room-tool snapping and alignment guides — **do not modify** |
| `tests/test_room_drag_group.py` | Existing regression tests for room drag/snap/detection |
