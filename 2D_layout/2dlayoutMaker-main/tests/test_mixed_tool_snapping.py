"""Room tool and Draw tool must coexist in ONE layout: both create real RoomEntity
objects, both snap to each other, and neither tool's mode blocks the other.

Root cause this locks down: `controller.on_click` checks `drawing_enabled` BEFORE
`select_item`, so while line mode is armed every click draws a line and NO room can be
selected/dragged/snapped. The Draw tool therefore must drop drawing mode once a closed
loop becomes a room.
"""
import tkinter as tk
import unittest
from types import SimpleNamespace


class MixedToolSnappingTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:  # pragma: no cover - headless CI
            self.skipTest(f"Tk unavailable: {error}")
        self.root.withdraw()
        from model import CanvasModel
        from action import ActionManager
        from view import CanvasView
        from tools import CanvasTools
        from controller import CanvasController

        container = tk.Frame(self.root)
        container.pack()
        self.model = CanvasModel()
        self.actions = ActionManager()
        self.view = CanvasView(container, self.model)
        self.tools = CanvasTools(self.root, self.model, self.view, self.actions)
        self.actions.tools = self.tools
        self.view.tools = self.tools
        self.controller = CanvasController(self.root, self.model, self.view, self.tools, self.actions)
        self.controller._motion_throttle_ms = 0
        self.model.tools = self.tools
        self.canvas = self.view.canvas
        self.addCleanup(self.root.destroy)

    def _make_room(self, name, width_real, height_real, at_x, at_y):
        """Create a room exactly the way BOTH tools now do it."""
        from entities import RoomEntity
        group_id = getattr(self.model, "room_counter", 0)
        setattr(self.model, "room_counter", group_id + 1)
        room = RoomEntity(self.canvas, self.model, name, width_real, height_real, group_id)
        self.canvas.move(room.group_tag, at_x - room.x0, at_y - room.y0)
        room.x0, room.y0 = at_x, at_y
        room.x1, room.y1 = at_x + room.width_px, at_y + room.height_px
        self.tools.room_entities_by_group_tag[room.group_tag] = room
        return room

    def _drag(self, room, dx, dy):
        """Drag a room through the real click→drag path."""
        c = self.canvas.coords(room.rect_id)
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        self.controller.select_item(SimpleNamespace(x=cx, y=cy, widget=self.canvas))
        self.controller.drag_start_pos = (cx, cy)
        self.controller.drag_origin_pos = (cx, cy)
        steps = max(abs(dx), abs(dy), 1)
        for i in range(1, steps + 1):
            self.controller.on_drag(SimpleNamespace(
                x=cx + dx * i // steps, y=cy + dy * i // steps))
        self.controller.on_release(SimpleNamespace(x=cx + dx, y=cy + dy))

    def test_unique_group_tags_across_both_tools(self):
        """Both tools draw group ids from model.room_counter, so tags never collide
        (a collision would make canvas.move drag two rooms at once)."""
        a = self._make_room("A", 10, 8, 100, 100)
        b = self._make_room("B", 8, 6, 600, 100)
        c = self._make_room("C", 6, 6, 100, 500)
        tags = [a.group_tag, b.group_tag, c.group_tag]
        self.assertEqual(len(tags), len(set(tags)), f"duplicate room group tags: {tags}")
        self.assertEqual(3, len(self.tools.room_entities_by_group_tag))

    def test_drawing_mode_blocks_room_selection(self):
        """The root cause: with line mode armed, `on_click` routes to start_line and the
        room is never selected — so nothing can be dragged or snapped. This is why snapping
        appeared to break for BOTH tools after using the Draw tool."""
        room = self._make_room("A", 10, 8, 200, 200)
        c = self.canvas.coords(room.rect_id)
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2

        self.model.set("drawing_enabled", True)
        self.controller.dragging_group = None
        self.controller.on_click(SimpleNamespace(x=cx, y=cy, widget=self.canvas))
        self.assertIsNone(
            self.controller.dragging_group,
            "drawing mode must swallow the click (documents why the mode has to be released)",
        )

    def test_room_is_selectable_when_drawing_mode_is_off(self):
        """With drawing mode off — the state the Draw tool now leaves after closing a loop —
        a click selects the room, which is what makes drag + snap reachable."""
        room = self._make_room("A", 10, 8, 200, 200)
        c = self.canvas.coords(room.rect_id)
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2

        self.assertFalse(self.model.get("drawing_enabled"))
        self.controller.dragging_group = None
        self.controller.on_click(SimpleNamespace(x=cx, y=cy, widget=self.canvas))
        self.assertEqual(
            room.group_tag, self.controller.dragging_group,
            "with drawing mode off the room must be selectable so it can snap",
        )

    def test_draw_room_snaps_to_room_tool_room(self):
        """A hand-drawn room dragged toward a Room-tool room snaps flush."""
        room_tool = self._make_room("RoomTool", 12, 8, 100, 100)
        right_edge = self.canvas.coords(room_tool.rect_id)[2]
        drawn = self._make_room("Drawn", 8, 8, right_edge + 40, 100)

        self._drag(drawn, -40, 0)

        self.assertAlmostEqual(
            right_edge, self.canvas.coords(drawn.rect_id)[0], delta=2,
            msg="drawn room did not snap flush to the Room-tool room",
        )

    def test_room_tool_room_snaps_to_draw_room(self):
        """And the reverse direction: a Room-tool room snaps onto a hand-drawn room."""
        drawn = self._make_room("Drawn", 12, 8, 100, 100)
        right_edge = self.canvas.coords(drawn.rect_id)[2]
        room_tool = self._make_room("RoomTool", 8, 8, right_edge + 40, 100)

        self._drag(room_tool, -40, 0)

        self.assertAlmostEqual(
            right_edge, self.canvas.coords(room_tool.rect_id)[0], delta=2,
            msg="Room-tool room did not snap flush to the drawn room",
        )

    def test_red_dashed_alignment_guides_appear_while_snapping(self):
        """The red dashed guides must show up when a drag comes into alignment. They only
        draw when snap_info flags are set, which needs a workable tolerance — at 5 px they
        flickered."""
        a = self._make_room("A", 12, 8, 100, 100)
        a_right = self.canvas.coords(a.rect_id)[2]
        b = self._make_room("B", 8, 8, a_right + 30, 100)

        c = self.canvas.coords(b.rect_id)
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        self.controller.select_item(SimpleNamespace(x=cx, y=cy, widget=self.canvas))
        self.controller.drag_start_pos = (cx, cy)
        self.controller.drag_origin_pos = (cx, cy)

        seen_guides = False
        for i in range(1, 31):
            self.controller.on_drag(SimpleNamespace(x=cx - i, y=cy))
            if self.canvas.find_withtag("guideline_room"):
                seen_guides = True
                break
        self.assertTrue(seen_guides, "no red dashed alignment guide appeared during the drag")

    # --- guides must be consistent across tools -------------------------------------
    def _visible_guides(self):
        """Guide items that are actually on screen.

        `find_withtag` also returns pooled items that `clear_guides` merely hid, so state
        has to be checked or the assertion proves nothing.
        """
        return [
            item for item in self.canvas.find_withtag("guideline_room")
            if self.canvas.itemcget(item, "state") != "hidden"
        ]

    def _wall_loop(self, x0, y0, x1, y1, prefix):
        """A Draw-tool room: four committed wall lines, no RoomEntity."""
        edges = ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0))
        for i, edge in enumerate(edges):
            self.canvas.create_line(*edge, tags=("line", "committed_line", f"line_{prefix}{i}"))

    def _drag_guides_appear(self, press_x, press_y, steps):
        """Drag from a press point and report whether a dashed guide ever showed."""
        self.controller.select_item(SimpleNamespace(x=press_x, y=press_y, widget=self.canvas))
        self.controller.drag_start_pos = (press_x, press_y)
        self.controller.drag_origin_pos = (press_x, press_y)
        for x, y in steps:
            self.controller.on_drag(SimpleNamespace(x=x, y=y))
            if self._visible_guides():
                return True
        return False

    def test_guides_appear_for_draw_tool_wall_loops(self):
        """The Draw tool drew no guides at all: only the Room-tool drag path called
        draw_room_alignment_guides. Dragging a hand-drawn loop flush must show the same
        dashed guide."""
        self._wall_loop(200, 100, 500, 400, "a")
        self._wall_loop(520, 100, 800, 400, "b")   # 20 px gap
        self.assertTrue(
            self._drag_guides_appear(660, 100, [(660 - i, 100) for i in range(1, 26)]),
            "no dashed guide appeared while snapping two drawn rooms together",
        )

    def test_guides_appear_when_room_tool_meets_drawn_walls(self):
        """A Room-tool room snapping onto draw-tool walls: its snap_info only knows about
        other RoomEntity objects, so the guide used to be missing for this pairing."""
        self._wall_loop(200, 100, 500, 400, "a")
        room = self._make_room("R", 6, 6, 540, 100)
        c = self.canvas.coords(room.rect_id)
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        self.assertTrue(
            self._drag_guides_appear(cx, cy, [(cx - i, cy) for i in range(1, 61)]),
            "no dashed guide appeared while a Room-tool room snapped onto drawn walls",
        )

    def test_guides_still_appear_after_the_canvas_is_wiped(self):
        """GuidelineHelper pools its canvas items forever. A full wipe deletes them while
        the pool keeps the dead ids, and Tk ignores writes to dead ids — so guides silently
        stopped appearing for the rest of the session."""
        a = self._make_room("A", 12, 8, 100, 100)
        a_right = self.canvas.coords(a.rect_id)[2]
        b = self._make_room("B", 8, 8, a_right + 30, 100)
        c = self.canvas.coords(b.rect_id)
        self._drag_guides_appear(
            (c[0] + c[2]) / 2, (c[1] + c[3]) / 2,
            [((c[0] + c[2]) / 2 - i, (c[1] + c[3]) / 2) for i in range(1, 31)],
        )
        self.assertTrue(self.tools.guideline_helper.line_pool, "expected pooled guide items")

        self.canvas.delete("all")                  # New / Clear layout
        self.tools.room_entities_by_group_tag.clear()
        self.controller.dragging_group = None

        self._wall_loop(200, 100, 500, 400, "a")
        self._wall_loop(520, 100, 800, 400, "b")
        self.assertTrue(
            self._drag_guides_appear(660, 100, [(660 - i, 100) for i in range(1, 26)]),
            "guides never came back after the canvas was wiped",
        )

    def test_snapped_room_releases_when_the_pointer_moves_away(self):
        """A snapped room must not stay glued to its neighbour.

        `on_drag` resets `drag_start_pos` every event, so dx/dy are 1-3 px increments. The
        old code snapped `current_coords + dx`, which re-snapped a flush room onto the same
        edge on every event: the room only moved if the mouse jerked past the 12 px
        tolerance in ONE event, which is the "sticks a bit while snapping/dragging" report.
        Anchoring to the pointer makes small moves accumulate, so the room releases once the
        pointer has genuinely travelled past the tolerance.
        """
        a = self._make_room("A", 12, 8, 100, 100)
        a_right = self.canvas.coords(a.rect_id)[2]
        b = self._make_room("B", 8, 8, a_right + 20, 100)

        c = self.canvas.coords(b.rect_id)
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        self.controller.select_item(SimpleNamespace(x=cx, y=cy, widget=self.canvas))
        self.controller.drag_start_pos = (cx, cy)
        self.controller.drag_origin_pos = (cx, cy)

        # Pull it flush (20 px left, one pixel per event).
        for i in range(1, 21):
            self.controller.on_drag(SimpleNamespace(x=cx - i, y=cy))
        self.assertAlmostEqual(
            a_right, self.canvas.coords(b.rect_id)[0], delta=2,
            msg="room did not snap flush, so the release behaviour cannot be judged",
        )

        # Now drag steadily back to the right, again one pixel per event. Well past the
        # 12 px tolerance the room must have followed the pointer.
        for i in range(1, 26):
            self.controller.on_drag(SimpleNamespace(x=cx - 20 + i, y=cy))
        self.assertGreater(
            self.canvas.coords(b.rect_id)[0], a_right + 5,
            "room stayed stuck to its neighbour while the pointer moved 25 px away",
        )

    def test_loop_walls_are_retired_before_the_name_prompt(self):
        """No duplicate room-name label while the Draw tool's naming dialog is open.

        `askstring` runs a nested Tk event loop, so the 150 ms detection debounce scheduled
        by the closing wall fires *inside* it. With the loop's walls still on the canvas
        that pass found this very loop and drew an overlay label on top of the RoomEntity's
        own — the duplicate name that flashed and then vanished on the next refresh. The
        walls must be gone, and the pending pass cancelled, before prompting.
        """
        from tkinter import simpledialog
        seen = {}

        def fake_askstring(*_args, **_kwargs):
            seen["walls"] = [
                item for item in self.canvas.find_withtag("committed_line")
                if self.canvas.type(item) == "line"
            ]
            seen["pending"] = getattr(self.tools, "_room_detection_after_id", None)
            return "Kitchen"

        original = simpledialog.askstring
        simpledialog.askstring = fake_askstring
        self.addCleanup(lambda: setattr(simpledialog, "askstring", original))

        self.model.set("drawing_enabled", True)
        for x, y in ((200, 100), (400, 100), (400, 300), (200, 300), (200, 100)):
            self.tools.start_line(SimpleNamespace(x=x, y=y, widget=self.canvas))

        self.assertIn("walls", seen, "the loop never closed, so no name was requested")
        self.assertEqual([], seen["walls"], "loop walls were still on the canvas at prompt time")
        self.assertIsNone(seen["pending"], "a detection pass was still pending at prompt time")
        self.assertEqual(
            ["Kitchen"],
            [room.name for room in self.tools.room_entities_by_group_tag.values()],
            "the closed loop should have produced exactly one named room",
        )

    def test_rooms_cannot_penetrate_each_other(self):
        """Dragging a small room deep inside a big one must not overlap it.

        Positions are chosen so NO edge and NO centre line aligns within the snap
        tolerance — otherwise snapping alone would incidentally separate them and this
        test would prove nothing about the overlap guard.
        """
        a = self._make_room("A", 12, 8, 200, 200)          # 200,200 → 620,480
        ax0, ay0, ax1, ay1 = self.canvas.coords(a.rect_id)[:4]
        b = self._make_room("B", 6, 4, 700, 250)           # small, y deliberately offset

        # FAST drag: a few big jumps, like a quick mouse move. Small 1-px steps would land
        # inside the snap tolerance and be stopped by snapping alone; a fast drag skips past
        # that window, which is exactly when a room used to slide inside another.
        c = self.canvas.coords(b.rect_id)
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        self.controller.select_item(SimpleNamespace(x=cx, y=cy, widget=self.canvas))
        self.controller.drag_start_pos = (cx, cy)
        self.controller.drag_origin_pos = (cx, cy)
        for step in (-150, -300, -450):
            self.controller.on_drag(SimpleNamespace(x=cx + step, y=cy))
        self.controller.on_release(SimpleNamespace(x=cx - 450, y=cy))

        bx0, by0, bx1, by1 = self.canvas.coords(b.rect_id)[:4]
        overlap_x = min(bx1, ax1) - max(bx0, ax0)
        overlap_y = min(by1, ay1) - max(by0, ay0)
        penetrating = overlap_x > 1 and overlap_y > 1
        self.assertFalse(
            penetrating,
            f"room B penetrated room A (overlap {overlap_x:.1f}x{overlap_y:.1f}); "
            f"A={ax0, ay0, ax1, ay1} B={bx0, by0, bx1, by1}",
        )

    def test_three_rooms_from_both_tools_all_snap_in_one_layout(self):
        """Full mixed layout: rooms keep snapping regardless of creation order."""
        a = self._make_room("A", 10, 8, 100, 100)          # room tool
        a_right = self.canvas.coords(a.rect_id)[2]
        b = self._make_room("B", 10, 8, a_right + 45, 100)  # draw tool
        self._drag(b, -45, 0)
        self.assertAlmostEqual(a_right, self.canvas.coords(b.rect_id)[0], delta=2)

        b_right = self.canvas.coords(b.rect_id)[2]
        c = self._make_room("C", 8, 8, b_right + 45, 100)   # room tool again
        self._drag(c, -45, 0)
        self.assertAlmostEqual(
            b_right, self.canvas.coords(c.rect_id)[0], delta=2,
            msg="third room (other tool) failed to snap onto the chain",
        )
        # All three still independent entities.
        self.assertEqual(3, len(self.tools.room_entities_by_group_tag))


if __name__ == "__main__":
    unittest.main()
