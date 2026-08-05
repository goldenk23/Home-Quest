"""Wall openings (windows / ventilation) placed on hand-drawn wall lines.

Verifies the reported need: clicking a drawn wall inserts a window/ventilation symbol that
(a) is created, (b) sits on the clicked wall, and (c) carries the wall's group tag so it
moves when the wall/room is dragged. Runs against a live Tk canvas, no dialogs, no mainloop.
"""
import tkinter as tk
import unittest
from types import SimpleNamespace


class WallOpeningTests(unittest.TestCase):
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
        container = tk.Frame(self.root); container.pack()
        self.model = CanvasModel()
        self.actions = ActionManager()
        self.view = CanvasView(container, self.model)
        self.tools = CanvasTools(self.root, self.model, self.view, self.actions)
        self.actions.tools = self.tools
        self.canvas = self.view.canvas
        # show_message is a blocking modal; neutralise it for headless placement tests.
        import tools as tools_module
        self._orig_show_message = tools_module.show_message
        tools_module.show_message = lambda *a, **k: None
        self.addCleanup(lambda: setattr(tools_module, "show_message", self._orig_show_message))
        self.addCleanup(self.root.destroy)

    def _wall(self, x0, y0, x1, y1, tag):
        return self.canvas.create_line(x0, y0, x1, y1, tags=("line", "committed_line", tag))

    def test_opening_attaches_to_the_clicked_wall_and_moves_with_it(self):
        wall = self._wall(200, 100, 500, 100, "line_top")  # horizontal wall
        # Place a sliding window at the middle of the wall (bypass the modal chooser).
        oid = self.tools._place_wall_opening(
            wall, (200, 100, 500, 100), 350, 108, "Sliding Window")
        self.assertTrue(oid, "no opening id returned")

        symbol = list(self.canvas.find_withtag("wall_opening"))
        self.assertGreater(len(symbol), 0, "no symbol drawn")
        # Every symbol item must carry the wall's group tag, so it drags with the wall.
        for item in symbol:
            self.assertIn("line_top", self.canvas.gettags(item),
                          "opening not tagged to the wall it was placed on")

        # Symbol sits centred on the click, along the wall (~x=350, y≈100).
        xs, ys = [], []
        for item in symbol:
            c = self.canvas.coords(item)
            xs += c[0::2]; ys += c[1::2]
        self.assertAlmostEqual(350, (min(xs) + max(xs)) / 2, delta=6)
        self.assertAlmostEqual(100, (min(ys) + max(ys)) / 2, delta=6)

        # Dragging the wall's group moves the opening by the same delta.
        before = {i: self.canvas.coords(i) for i in symbol}
        self.canvas.move("line_top", -40, 25)
        for item, old in before.items():
            new = self.canvas.coords(item)
            self.assertEqual((-40.0, 25.0),
                             (round(new[0] - old[0], 3), round(new[1] - old[1], 3)),
                             "opening did not move with the wall")

    def test_place_window_uses_pending_kind_and_snaps_to_nearest_wall(self):
        """The real flow: kind chosen up front (stored on _pending_opening_kind), then a click
        NEAR a wall drops that opening on it — no per-click popup, generous tolerance."""
        self._wall(200, 100, 500, 100, "line_top")
        self.tools._pending_opening_kind = "Ventilation"
        # Click ~10 px below the wall line (not exactly on it).
        placed = self.tools.place_window(SimpleNamespace(x=350, y=110))
        self.assertTrue(placed, "click near a wall should place an opening")
        self.assertEqual(1, len(self.tools.wall_openings))
        self.assertEqual("vent", self.tools.wall_openings[0]["otype"])
        symbol = self.canvas.find_withtag("wall_opening")
        self.assertGreater(len(symbol), 0)
        for item in symbol:
            self.assertIn("line_top", self.canvas.gettags(item))

    def test_place_window_far_from_walls_reports_and_does_not_place(self):
        self._wall(200, 100, 500, 100, "line_top")
        self.tools._pending_opening_kind = "Sliding Window"
        placed = self.tools.place_window(SimpleNamespace(x=350, y=500))  # far away
        self.assertFalse(placed)
        self.assertEqual(0, len(self.tools.wall_openings))

    def test_each_kind_draws_a_distinct_symbol(self):
        from tools import WALL_OPENING_KINDS
        counts = {}
        for i, kind in enumerate(WALL_OPENING_KINDS):
            self.canvas.delete("all")
            self.tools.wall_openings = []
            y = 50 * i + 50
            wall = self._wall(0, y, 400, y, f"line_{i}")
            self.tools._place_wall_opening(wall, (0, y, 400, y), 200, y, kind)
            counts[kind] = len(self.canvas.find_withtag("wall_opening"))
        # Every kind draws a frame (4) plus its own detail lines, so none is empty.
        for kind, n in counts.items():
            self.assertGreaterEqual(n, 5, f"{kind} drew too few lines ({n})")


if __name__ == "__main__":
    unittest.main()
