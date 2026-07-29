import tkinter as tk

from drawing_helpers import get_distance_label


class LineEditManager:
    """Manage line edit handles and dragging behavior."""

    def __init__(self, canvas: tk.Canvas, model, actions, tools) -> None:
        self.canvas = canvas
        self.model = model
        self.actions = actions
        self.tools = tools
        self.active_line_id = None
        self.active_line_tag = None
        self.handle_ids = {}
        self.dragging_handle = None
        self._drag_bindings = {}

    def start_edit(self, line_id: int, line_tag: str, line_metadata: dict) -> None:
        if not line_metadata:
            return
        self.clear()
        self.active_line_id = line_id
        self.active_line_tag = line_tag
        coords = self.canvas.coords(line_id)
        if len(coords) < 4:
            return
        x0, y0, x1, y1 = coords[:4]
        self._create_handle("start", x0, y0)
        self._create_handle("end", x1, y1)
        for handle_id in self.handle_ids.values():
            self.canvas.tag_raise(handle_id)
        self.canvas.itemconfig(line_id, tags=tuple(set(self.canvas.gettags(line_id)) | {"editable_line"}))

    def clear(self) -> None:
        for handle_id in list(self.handle_ids.values()):
            try:
                self.canvas.delete(handle_id)
            except Exception:
                pass
        self.handle_ids = {}
        self.dragging_handle = None
        self.active_line_id = None
        self.active_line_tag = None

    def _create_handle(self, kind: str, x: float, y: float) -> None:
        radius = 5
        handle_id = self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#00a3ff",
            outline="#005b8f",
            tags=("line_edit_handle", f"line_edit_handle_{kind}"),
        )
        self.handle_ids[kind] = handle_id
        self.canvas.tag_bind(handle_id, "<ButtonPress-1>", lambda e, k=kind: self._start_drag(e, k))
        self.canvas.tag_bind(handle_id, "<B1-Motion>", self._drag)
        self.canvas.tag_bind(handle_id, "<ButtonRelease-1>", self._end_drag)

    def _start_drag(self, event, kind: str) -> None:
        self.dragging_handle = kind

    def _drag(self, event) -> None:
        if not self.active_line_id or not self.dragging_handle:
            return
        coords = self.canvas.coords(self.active_line_id)
        if len(coords) < 4:
            return
        x0, y0, x1, y1 = coords[:4]
        if self.dragging_handle == "start":
            x0, y0 = event.x, event.y
        else:
            x1, y1 = event.x, event.y
        self.canvas.coords(self.active_line_id, x0, y0, x1, y1)
        self._update_handle_position("start", x0, y0)
        self._update_handle_position("end", x1, y1)
        self._update_line_decorations(x0, y0, x1, y1)

    def _end_drag(self, _event) -> None:
        self.dragging_handle = None

    def _update_handle_position(self, kind: str, x: float, y: float) -> None:
        handle_id = self.handle_ids.get(kind)
        if not handle_id:
            return
        radius = 5
        try:
            self.canvas.coords(handle_id, x - radius, y - radius, x + radius, y + radius)
        except Exception:
            pass

    def _update_line_decorations(self, x0: float, y0: float, x1: float, y1: float) -> None:
        if not self.active_line_tag or not hasattr(self.tools, "line_metadata"):
            return
        metadata = self.tools.line_metadata.get(self.active_line_tag)
        if not metadata:
            return
        metadata.update({"x0": x0, "y0": y0, "x1": x1, "y1": y1})
        label_id = metadata.get("label")
        if label_id:
            try:
                label_text, mid_x, mid_y = get_distance_label(
                    x0, y0, x1, y1, self.model.unit, self.model.zoom_level
                )
                self.canvas.coords(label_id, mid_x, mid_y - 10)
                self.canvas.itemconfig(label_id, text=label_text)
            except Exception:
                pass
        point_id = metadata.get("point")
        if point_id:
            try:
                self.canvas.coords(point_id, x1 - 0.5, y1 - 0.5, x1 + 0.5, y1 + 0.5)
            except Exception:
                pass
