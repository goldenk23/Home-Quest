"""Regression checks for dragging a detected (closed line loop) room.

Reproduces the reported failure: the colored floor detaching from its wall
boundary on drag. Runs the real detection + overlay code against a live Tk
canvas, with no dialogs and no mainloop.

Two wall representations are covered because they tag differently:
  * fresh Line-tool walls -> ("line", "committed_line", "line_<uuid>")
  * rehydrated walls      -> ("line", "line_<id>", "source_shape:<id>")
"""
import tkinter as tk
import unittest
from types import SimpleNamespace

from layout_schema import new_project
from layout_serializer import LayoutSerializer
from project_state import ProjectState

EDGES = [
    (200, 100, 600, 100),
    (600, 100, 600, 400),
    (600, 400, 200, 400),
    (200, 400, 200, 100),
]
FILL = "#d0f0c0"


class DetectedRoomDragTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:  # pragma: no cover - headless CI
            self.skipTest(f"Tk unavailable: {error}")
        self.root.withdraw()
        self.canvas = tk.Canvas(self.root, width=900, height=700)
        self.canvas.pack()
        self.canvas.update_idletasks()
        self.addCleanup(self.root.destroy)

        serializer = LayoutSerializer.__new__(LayoutSerializer)
        serializer.canvas = self.canvas
        serializer.model = SimpleNamespace(
            unit="feet", unit_scale={"feet": 1.0}, grid_spacing=20, zoom_level=1.0,
        )
        serializer.view = SimpleNamespace(
            grid_visible=True, pixel_to_real=lambda px, py: (float(px), float(py)),
        )
        serializer.tools = SimpleNamespace(
            image_furniture_items=[], windows=[], room_entities_by_group_tag={},
            room_flooring_images={}, line_metadata={}, current_compass_direction=None,
        )
        serializer.project_state = ProjectState(new_project())
        serializer._detected_room_overrides = {}
        self.serializer = serializer

    def _draw_loop(self, mode):
        for index, edge in enumerate(EDGES):
            if mode == "fresh":
                tags = ("line", "committed_line", f"line_{index}")
            else:
                tags = ("line", f"line_wall-{index}", f"source_shape:wall-{index}")
            self.canvas.create_line(*edge, fill="white", width=2, tags=tags)

    def _overlay(self):
        items = self.canvas.find_withtag("parity_detected_room")
        polygons = [i for i in items if self.canvas.type(i) == "polygon"]
        labels = [i for i in items if self.canvas.type(i) == "text"]
        return polygons, labels

    def _style_as_room(self, polygon, label):
        entity_id = next(
            t.split(":", 1)[1]
            for t in self.canvas.gettags(polygon)
            if t.startswith("entity:")
        )
        self.canvas.itemconfig(polygon, fill=FILL, outline="black", width=2)
        self.canvas.itemconfig(label, text="Room")
        self.serializer._detected_room_overrides[entity_id] = {
            "label": "Room", "fill_mode": "filled", "fill_color": FILL,
        }
        self.serializer.refresh_detected_room_overlay()

    def _corners(self, polygon):
        coords = self.canvas.coords(polygon)
        return {
            (round(coords[i], 3), round(coords[i + 1], 3))
            for i in range(0, len(coords) - 1, 2)
        }

    def _wall_corners(self):
        corners = set()
        for item in self.canvas.find_all():
            if self.canvas.type(item) != "line":
                continue
            c = self.canvas.coords(item)
            corners.add((round(c[0], 3), round(c[1], 3)))
            corners.add((round(c[2], 3), round(c[3], 3)))
        return corners

    def _run_drag(self, mode):
        self._draw_loop(mode)
        self.serializer.refresh_detected_room_overlay()
        polygons, labels = self._overlay()
        self.assertEqual(1, len(polygons), f"{mode}: expected one detected room polygon")
        self.assertEqual(1, len(labels), f"{mode}: expected one detected room label")

        self._style_as_room(polygons[0], labels[0])
        polygons, labels = self._overlay()
        drag_tag = next(
            (t for t in self.canvas.gettags(polygons[0]) if t.startswith("parity_room_drag:")),
            None,
        )
        self.assertIsNotNone(drag_tag, f"{mode}: styled room has no drag group")

        grouped = self.canvas.find_withtag(drag_tag)
        walls = [i for i in grouped if self.canvas.type(i) == "line"]
        self.assertEqual(
            len(EDGES), len(walls),
            f"{mode}: {len(walls)} of {len(EDGES)} boundary walls joined the drag group",
        )

        before = {i: self.canvas.coords(i) for i in self.canvas.find_all()}
        dx, dy = -140, 120
        self.canvas.move(drag_tag, dx, dy)
        for item, old in before.items():
            if self.canvas.type(item) != "line":
                continue
            new = self.canvas.coords(item)
            self.assertEqual(
                (dx, dy), (round(new[0] - old[0], 6), round(new[1] - old[1], 6)),
                f"{mode}: wall {item} did not move with the room",
            )
        return mode

    def test_fresh_line_tool_room_moves_as_one_unit(self):
        self._run_drag("fresh")

    def _divide(self, dividers, *, with_closing_polygon):
        """Draw the loop (optionally with the Line tool's closing polygon) plus dividers."""
        self._draw_loop("fresh")
        if with_closing_polygon:
            corners = [(200, 100), (600, 100), (600, 400), (200, 400)]
            self.canvas.create_polygon(
                [c for point in corners for c in point],
                outline="white", fill="", width=2, tags=("closed_shape",),
            )
        for index, divider in enumerate(dividers):
            self.canvas.create_line(
                *divider, tags=("line", "committed_line", f"line_div{index}"),
            )
        self.serializer.refresh_detected_room_overlay()
        return self._overlay()

    def test_divider_lines_split_the_room_into_separate_rooms(self):
        """Dividing a drawn room must yield one nameable room per enclosure.

        Without T-junction/crossing splitting the face walk cannot turn where a divider
        meets the middle of a wall, so only one room was ever detected.
        """
        cases = [
            ([], 1),
            ([(400, 100, 400, 400)], 2),
            ([(200, 250, 600, 250)], 2),
            ([(400, 100, 400, 400), (200, 250, 600, 250)], 4),
            ([(400, 100, 400, 250), (200, 250, 600, 250)], 3),
        ]
        for dividers, expected in cases:
            for with_closing_polygon in (False, True):
                with self.subTest(dividers=len(dividers), closing=with_closing_polygon):
                    self.canvas.delete("all")
                    self.serializer._detected_room_overrides = {}
                    polygons, labels = self._divide(
                        dividers, with_closing_polygon=with_closing_polygon,
                    )
                    self.assertEqual(expected, len(polygons))
                    # create_room_from_closed_lines only prompts for rooms that have
                    # both a polygon and a label, so both counts must match.
                    self.assertEqual(expected, len(labels))

    def test_unnamed_room_overlay_stays_visually_silent(self):
        """An unnamed room must not announce itself.

        The overlay label is required by "Lines -> Room" to offer the room for naming,
        but until the user names it the overlay carries no fill and the label keeps the
        original dark colour, so nothing appears on the canvas.
        """
        self._draw_loop("fresh")
        self.serializer.refresh_detected_room_overlay()
        polygons, labels = self._overlay()
        self.assertEqual("", self.canvas.itemcget(polygons[0], "fill"))
        self.assertEqual("#0f172a", self.canvas.itemcget(labels[0], "fill"))

    def _rect_loop(self, x0, y0, x1, y1, prefix):
        edges = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
        for index, edge in enumerate(edges):
            self.canvas.create_line(
                *edge, tags=("line", "committed_line", f"line_{prefix}{index}"),
            )

    def _controller(self):
        from controller import CanvasController

        controller = CanvasController.__new__(CanvasController)
        controller.canvas = self.canvas
        controller.tools = self.serializer.tools
        # on_drag touches these before reaching the group-drag path.
        self.serializer.tools.canvas_frozen = False
        self.serializer.tools._cancel_line_input = lambda: None
        return controller

    def _drag_controller(self, group, from_xy):
        controller = self._controller()
        controller.model = SimpleNamespace(get=lambda _key: False)
        controller.dragging_item = None
        controller.dragging_group = group
        controller.drag_start_pos = from_xy
        controller.drag_origin_pos = from_xy
        controller._last_motion_time = 0
        controller._motion_throttle_ms = 0
        controller._drag_anchor = None
        return controller

    def _drag_via_controller(self, group, from_xy, to_xy):
        """Drive the real on_drag path, not the snap helper directly."""
        controller = self._drag_controller(group, from_xy)
        controller.on_drag(SimpleNamespace(x=to_xy[0], y=to_xy[1]))
        return controller

    def _room_group_at(self, left_edge):
        for polygon in self._overlay()[0]:
            coords = self.canvas.coords(polygon)
            if abs(min(coords[0::2]) - left_edge) < 0.001:
                return next(
                    t for t in self.canvas.gettags(polygon)
                    if str(t).startswith("parity_room_drag:")
                ), polygon
        raise AssertionError(f"no detected room with left edge {left_edge}")

    def test_release_without_a_prior_drag_does_not_crash(self):
        """A click that never starts a group drag must survive release.

        Live crash (crash.log): on_release reads self.dragging_group directly, but
        __init__ never initialised it, so the first click on empty canvas / a protected
        label raised AttributeError on release and the app died silently. Build a REAL
        controller through its real __init__ so the attribute-init fix is what's tested.
        """
        from model import CanvasModel
        from action import ActionManager
        from view import CanvasView
        from tools import CanvasTools
        from controller import CanvasController

        container = tk.Frame(self.root)
        container.pack()
        model = CanvasModel()
        actions = ActionManager()
        view = CanvasView(container, model)
        tools = CanvasTools(self.root, model, view, actions)
        actions.tools = tools
        view.tools = tools
        controller = CanvasController(self.root, model, view, tools, actions)

        self.assertIsNone(controller.dragging_group, "dragging_group must init to None")
        # No AttributeError even though no drag ever set dragging_group.
        controller.on_release(SimpleNamespace(x=10, y=10))
        container.destroy()

    def _real_controller(self):
        """A CanvasController built through its real __init__ on a real object graph.

        Returns a serializer bound to the SAME canvas as the controller. (Using the setUp
        serializer here would refresh a different canvas, so no parity tags would land on
        the controller's walls and detected-room tests would silently pass for the wrong
        reason — a mistake this helper deliberately prevents.)
        """
        from model import CanvasModel
        from action import ActionManager
        from view import CanvasView
        from tools import CanvasTools
        from controller import CanvasController
        from layout_serializer import LayoutSerializer

        container = tk.Frame(self.root)
        container.pack()
        model = CanvasModel()
        actions = ActionManager()
        view = CanvasView(container, model)
        tools = CanvasTools(self.root, model, view, actions)
        actions.tools = tools
        view.tools = tools
        controller = CanvasController(self.root, model, view, tools, actions)
        model.tools = tools
        serializer = LayoutSerializer(model, view, tools, actions)
        return controller, view.canvas, serializer

    def test_bare_wall_drag_moves_the_whole_connected_shape(self):
        """Grabbing one wall of a hand-drawn loop must move the whole shape, not tear it.

        The reported "everything falls apart": a loop the detector never turned into a room
        has no parity_room_drag group, so select_item handed back a single line_<uuid> and
        only that wall moved. select_item now upgrades a bare-wall grab to its connected
        component. A separate loop far away must stay a separate component.
        """
        controller, canvas, _serializer = self._real_controller()

        def loop(x0, y0, x1, y1, p):
            edges = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
            return [
                canvas.create_line(*e, tags=("line", "committed_line", f"line_{p}{i}"))
                for i, e in enumerate(edges)
            ]

        shape = loop(200, 100, 500, 400, "a")
        divider = canvas.create_line(350, 100, 350, 400, tags=("line", "committed_line", "line_div"))
        far = loop(700, 100, 900, 400, "b")  # separate component, must not move

        tag = controller._wall_component_drag_tag(shape[0])
        self.assertIsNotNone(tag, "a connected loop must produce a component tag")
        grouped = set(canvas.find_withtag(tag))
        # All four loop walls plus the T-junction divider are one shape.
        for item in shape + [divider]:
            self.assertIn(item, grouped, "connected wall missing from the drag group")
        for item in far:
            self.assertNotIn(item, grouped, "a separate loop must not join the drag group")

        before = {i: canvas.coords(i) for i in shape + [divider] + far}
        canvas.move(tag, -40, 25)
        for item in shape + [divider]:
            new, old = canvas.coords(item), before[item]
            self.assertEqual((-40.0, 25.0), (round(new[0] - old[0], 3), round(new[1] - old[1], 3)),
                             "connected wall did not move with the shape")
        for item in far:
            self.assertEqual(before[item], canvas.coords(item), "separate loop should not move")

    def _full_gesture(self, controller, canvas, cx, cy, dx, dy):
        """Real click -> drag -> release through select_item/on_drag/on_release."""
        controller._motion_throttle_ms = 0  # let every synthetic motion event through
        controller.select_item(SimpleNamespace(x=cx, y=cy, widget=canvas))
        controller.drag_start_pos = (cx, cy)
        controller.drag_origin_pos = (cx, cy)
        steps = max(abs(dx), abs(dy), 1)
        for i in range(1, steps + 1):
            controller.on_drag(SimpleNamespace(x=cx + dx * i // steps, y=cy + dy * i // steps))
        controller.on_release(SimpleNamespace(x=cx + dx, y=cy + dy))

    def test_room_colour_survives_a_split(self):
        """The reported "name/colour vanished": a room's id is rebuilt from its geometry, so
        splitting a styled room (drawing a divider — the user's exact flow) changes the id and
        the id-keyed style override was dropped on the next detection pass, blanking the fill.
        The override is now recovered by the room's stable boundary WALL items (line_<uuid>),
        so the styling carries onto the halves instead of vanishing.
        """
        controller, canvas, serializer = self._real_controller()

        def loop(x0, y0, x1, y1, p):
            edges = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
            return [canvas.create_line(*e, tags=("line", "committed_line", f"line_{p}{i}"))
                    for i, e in enumerate(edges)]

        loop(200, 100, 600, 400, "a")
        serializer.refresh_detected_room_overlay()
        poly = next(i for i in canvas.find_withtag("parity_detected_room")
                    if canvas.type(i) == "polygon")
        eid = next(t.split(":", 1)[1] for t in canvas.gettags(poly) if t.startswith("entity:"))
        serializer._detected_room_overrides[eid] = {
            "label": "Kitchen", "fill_mode": "filled", "fill_color": FILL}
        serializer.refresh_detected_room_overlay()
        self.assertEqual([FILL], [canvas.itemcget(p, "fill")
                                  for p in canvas.find_withtag("parity_detected_room")
                                  if canvas.type(p) == "polygon"])

        # Split: a divider turns the one styled room into two; ids change.
        canvas.create_line(400, 100, 400, 400, tags=("line", "committed_line", "line_div"))
        serializer.refresh_detected_room_overlay()

        fills = [canvas.itemcget(p, "fill") for p in canvas.find_withtag("parity_detected_room")
                 if canvas.type(p) == "polygon"]
        self.assertEqual(2, len(fills), "split should yield two rooms")
        self.assertTrue(all(f == FILL for f in fills),
                        f"styling vanished on split instead of following the walls: {fills}")

    def test_two_separate_detected_rooms_still_drag_independently(self):
        """Counter-check to the split-room fix: two rooms that do not touch must stay separate
        components, so one can be dragged to snap against the other."""
        controller, canvas, serializer = self._real_controller()

        def loop(x0, y0, x1, y1, p):
            edges = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
            return [canvas.create_line(*e, tags=("line", "committed_line", f"line_{p}{i}"))
                    for i, e in enumerate(edges)]

        a = loop(200, 100, 500, 400, "a")
        b = loop(600, 100, 900, 400, "b")  # 100 px gap
        serializer.refresh_detected_room_overlay()

        before = {w: canvas.coords(w) for w in a + b}
        self._full_gesture(controller, canvas, 350, 100, -30, 0)  # grab room A
        for w in a:
            old, new = before[w], canvas.coords(w)
            self.assertEqual((-30.0, 0.0), (round(new[0] - old[0], 1), round(new[1] - old[1], 1)))
        for w in b:
            self.assertEqual(before[w], canvas.coords(w), f"room B wall {w} moved but should not")

    def test_show_message_is_importable_at_tools_module_scope(self):
        """create_room_from_closed_lines calls show_message() bare; the module-level
        import must exist or naming a room crashes (NameError, crash.log)."""
        import tools as tools_module
        self.assertTrue(callable(tools_module.show_message))

    def test_drag_snaps_a_drawn_room_flush_to_its_neighbour(self):
        """Draw-tool rooms patch together like Room-tool rooms, via on_drag."""
        self._rect_loop(200, 100, 500, 400, "a")
        self._rect_loop(520, 100, 800, 400, "b")  # 20 px gap
        self.serializer.refresh_detected_room_overlay()
        self.assertEqual(2, len(self._overlay()[0]), "expected one room per drawn loop")

        group, polygon = self._room_group_at(520)
        self._drag_via_controller(group, (600, 200), (585, 200))  # 15 px left of a 20 px gap
        self.assertAlmostEqual(
            500.0, min(self.canvas.coords(polygon)[0::2]), places=3,
            msg="room should snap flush to its neighbour",
        )

        self.serializer.refresh_detected_room_overlay()
        polygons, _ = self._overlay()
        self.assertEqual(2, len(polygons), "patched rooms stay two rooms")
        shared = [self._corners(p) for p in polygons]
        self.assertEqual(
            {(500.0, 100.0), (500.0, 400.0)}, shared[0] & shared[1],
            "patched rooms should share the touching wall's corners",
        )

    def test_drag_snaps_to_walls_that_never_became_a_room(self):
        """The neighbour need not be a detected room.

        Snapping only to detected rooms silently did nothing whenever the neighbour was
        an open shape or a lone wall, which is the common real case.
        """
        for edge in ((200, 100, 500, 100), (500, 100, 500, 400), (500, 400, 200, 400)):
            self.canvas.create_line(*edge, tags=("line", "committed_line", f"line_open{edge[0]}"))
        self._rect_loop(520, 100, 800, 400, "b")
        self.serializer.refresh_detected_room_overlay()
        self.assertEqual(1, len(self._overlay()[0]), "the open shape must not be a room")

        group, polygon = self._room_group_at(520)
        self._drag_via_controller(group, (600, 200), (585, 200))
        self.assertAlmostEqual(
            500.0, min(self.canvas.coords(polygon)[0::2]), places=3,
            msg="room should snap to the open shape's wall",
        )

    def test_a_room_already_flush_can_still_be_dragged(self):
        """A patched room must not be glued in place.

        Live logs showed the failure: two rooms sharing a wall at x=437.5 meant the
        neighbour's wall was a candidate at the dragged room's own edge, so every drag
        was cancelled back to `(0.0, 0.0)` and the room could not move at all.
        """
        self._rect_loop(200, 100, 440, 400, "a")
        self._rect_loop(440, 100, 700, 400, "b")  # already flush
        self.serializer.refresh_detected_room_overlay()

        group, polygon = self._room_group_at(440)
        self._drag_via_controller(group, (500, 200), (530, 200))  # 30 px right
        self.assertAlmostEqual(
            470.0, min(self.canvas.coords(polygon)[0::2]), places=3,
            msg="a flush room must move by the full mouse delta, not snap back",
        )

    def test_snap_holds_across_many_small_motion_events(self):
        """The test that matters: a real drag is dozens of 1-3 px motion events.

        `on_drag` resets `drag_start_pos` every event, so snapping the per-event delta has
        no memory of the drag start and the room bounced 500 -> 499 -> 500 forever, which
        is what "snapping does not work" looked like on screen. Single-event tests all
        passed against that bug, so this walks the pointer one pixel at a time.
        """
        self._rect_loop(200, 100, 500, 400, "a")
        self._rect_loop(520, 100, 800, 400, "b")  # 20 px gap
        self.serializer.refresh_detected_room_overlay()
        group, polygon = self._room_group_at(520)

        def left():
            return round(min(self.canvas.coords(polygon)[0::2]), 3)

        controller = self._drag_controller(group, (600, 200))
        seen = []
        for x in range(599, 580, -1):
            controller.on_drag(SimpleNamespace(x=x, y=200))
            seen.append(left())

        self.assertIn(500.0, seen, f"room never snapped flush: {seen}")
        held = seen[seen.index(500.0):]
        self.assertEqual(
            [500.0] * len(held), held,
            f"room did not hold the flush position (oscillation): {seen}",
        )

        # Keep pulling: a deliberate larger drag has to break away cleanly.
        for x in range(580, 540, -1):
            controller.on_drag(SimpleNamespace(x=x, y=200))
        self.assertLess(left(), 490.0, "a larger drag must break away from the snap")

    def test_dragging_a_single_wall_snaps_to_nearby_geometry(self):
        """A wall dragged on its own must snap too, not only a detected room.

        What the user actually does with the Draw tool is drag walls: an un-detected loop
        has no `parity_room_drag:` group, so clicking it drags one `line_<uuid>` group and
        the shape comes apart wall by wall. Snapping only detected rooms left that whole
        path unassisted, which is why the editor still felt like it had no snapping.
        """
        self._rect_loop(200, 100, 500, 400, "a")
        self.serializer.refresh_detected_room_overlay()
        # A lone wall 20 px below the rectangle; x deliberately 30 px clear of both
        # vertical edges so only the y axis can snap.
        wall = self.canvas.create_line(
            230, 420, 530, 420, tags=("line", "committed_line", "line_lone"),
        )

        controller = self._drag_controller("line_lone", (380, 420))
        seen = []
        for step in range(1, 20):
            controller.on_drag(SimpleNamespace(x=380, y=420 - step))
            seen.append(round(self.canvas.coords(wall)[1], 3))

        self.assertIn(400.0, seen, f"lone wall never snapped to the room edge: {seen}")
        held = seen[seen.index(400.0):]
        self.assertEqual([400.0] * len(held), held, f"lone wall did not hold the snap: {seen}")

        for step in range(20, 60):
            controller.on_drag(SimpleNamespace(x=380, y=420 - step))
        self.assertLess(
            self.canvas.coords(wall)[1], 390.0, "a larger drag must break the wall away",
        )

    def test_a_large_drag_is_not_snapped(self):
        """Snapping must not fight the user when nothing is close."""
        self._rect_loop(200, 100, 500, 400, "a")
        self._rect_loop(520, 100, 800, 400, "b")
        self.serializer.refresh_detected_room_overlay()
        group, polygon = self._room_group_at(520)
        before = min(self.canvas.coords(polygon)[0::2])
        self._drag_via_controller(group, (600, 200), (400, 200))  # 200 px left
        self.assertAlmostEqual(
            before - 200, min(self.canvas.coords(polygon)[0::2]), places=3,
            msg="a far drag should move by exactly the mouse delta",
        )

    def test_room_tool_room_gets_no_overlay_and_stays_draggable(self):
        """A Room-tool room is a real entity that draws and drags itself.

        The live log showed an overlay generated from the room rectangle sitting on
        top of it, stealing the click and dragging only the overlay + its label
        (`members=[617, 618]`), so the room itself never moved.
        """
        from entities import RoomEntity

        room = RoomEntity(self.canvas, self.serializer.model, "kitchen", 10, 12, 0)
        self.serializer.tools.room_entities_by_group_tag[room.group_tag] = room
        self.serializer.refresh_detected_room_overlay()

        polygons, labels = self._overlay()
        self.assertEqual([], polygons, "a real room must not get a detected-room overlay")
        self.assertEqual([], labels, "a real room must not get a detected-room label")

        # Nothing may shadow the room, and its own group must still move as one unit.
        for item in self.canvas.find_all():
            self.assertNotIn(
                "parity_detected_room", self.canvas.gettags(item),
                "overlay item drawn over a real room",
            )
        before = {i: self.canvas.coords(i) for i in self.canvas.find_withtag(room.group_tag)}
        self.assertGreaterEqual(len(before), 2, "room rectangle and label should be grouped")
        self.canvas.move(room.group_tag, 40, -25)
        for item, old in before.items():
            new = self.canvas.coords(item)
            self.assertEqual(
                (40, -25), (round(new[0] - old[0], 6), round(new[1] - old[1], 6)),
                f"room item {item} did not move with its group",
            )

    def test_closing_polygon_does_not_create_a_second_room(self):
        """The Line tool adds a `closed_shape` polygon when a loop closes.

        Its corners coincide with the wall endpoints, so detection must still see
        exactly one room (the live log showed detected=2 and a duplicate label).
        """
        self._draw_loop("fresh")
        corners = [(200, 100), (600, 100), (600, 400), (200, 400)]
        self.canvas.create_polygon(
            [c for point in corners for c in point],
            outline="white", fill="", width=2, tags=("closed_shape",),
        )
        self.serializer.refresh_detected_room_overlay()
        polygons, labels = self._overlay()
        self.assertEqual(1, len(polygons), "closing polygon produced a duplicate room")
        self.assertEqual(1, len(labels), "closing polygon produced a duplicate room label")

    def test_closing_polygon_moves_with_the_room(self):
        """The closing polygon is drawn in the line colour over the walls, so if it
        stays put the boundary appears detached from the moved floor."""
        self._draw_loop("fresh")
        corners = [(200, 100), (600, 100), (600, 400), (200, 400)]
        shape = self.canvas.create_polygon(
            [c for point in corners for c in point],
            outline="white", fill="", width=2, tags=("closed_shape",),
        )
        self.serializer.refresh_detected_room_overlay()
        polygons, labels = self._overlay()
        self._style_as_room(polygons[0], labels[0])
        polygons, _ = self._overlay()
        drag_tag = next(
            t for t in self.canvas.gettags(polygons[0]) if t.startswith("parity_room_drag:")
        )
        self.assertIn(
            shape, self.canvas.find_withtag(drag_tag),
            "closing polygon is not part of the room drag group",
        )
        before = self.canvas.coords(shape)
        self.canvas.move(drag_tag, -140, 120)
        after = self.canvas.coords(shape)
        self.assertEqual(
            [(-140, 120)] * (len(before) // 2),
            [
                (round(after[i] - before[i], 6), round(after[i + 1] - before[i + 1], 6))
                for i in range(0, len(before) - 1, 2)
            ],
            "closing polygon did not move with the room",
        )

    def test_rehydrated_room_moves_as_one_unit(self):
        self._run_drag("reloaded")

    def test_post_drag_refresh_keeps_one_aligned_styled_overlay(self):
        for mode in ("fresh", "reloaded"):
            with self.subTest(mode=mode):
                self.canvas.delete("all")
                self.serializer._detected_room_overrides = {}
                self._run_drag(mode)

                # The post-drag re-detection must not leave a second stale overlay
                # behind, and the fill must stay on the moved boundary.
                self.serializer.refresh_detected_room_overlay()
                polygons, labels = self._overlay()
                self.assertEqual(1, len(polygons), f"{mode}: duplicate room overlay after drag")
                self.assertEqual(1, len(labels), f"{mode}: duplicate room label after drag")
                self.assertEqual(FILL, self.canvas.itemcget(polygons[0], "fill"))
                self.assertEqual(
                    self._wall_corners(), self._corners(polygons[0]),
                    f"{mode}: floor fill is not aligned with the wall boundary",
                )


if __name__ == "__main__":
    unittest.main()
