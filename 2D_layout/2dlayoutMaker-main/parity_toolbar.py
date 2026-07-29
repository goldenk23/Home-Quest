"""Dropdown popover for v2 project, finish, and structure controls."""
from __future__ import annotations

import json
import math
import os
import tkinter as tk
import uuid
from tkinter import colorchooser, messagebox, simpledialog, ttk

from Helper.color_scheme import COLORS


class ParityToolbar:
    TARGETS = ("wall both faces", "wall side A", "wall side B", "room floor", "deck")
    TARGET_SURFACE = {
        "wall both faces": "wall", "wall side A": "wall", "wall side B": "wall",
        "room floor": "floor", "deck": "deck",
    }

    def __init__(self, parent, serializer):
        self.serializer = serializer
        self.canvas = serializer.canvas
        self._refreshing = False
        self._floor_by_label = {}
        self._capture = None
        self._capture_points = []
        self._capture_bindings = []
        self._previous_cursor = ""
        self._paint_wall_id = None
        self.finishes = self._load_finishes()
        self._finish_by_label = {item["label"]: item for item in self.finishes}

        owner = parent.winfo_toplevel()
        self.owner = owner
        self.popup = tk.Toplevel(owner)
        self.popup.withdraw()
        self.popup.title("Project Tools")
        self.popup.transient(owner)
        self.popup.resizable(False, False)
        self.popup.protocol("WM_DELETE_WINDOW", self.hide)
        self.popup.bind("<Escape>", lambda _event: self.hide())
        self.popup.configure(bg=COLORS.get("surface_raised", "#FFFFFF"))

        style = ttk.Style(self.popup)
        style.configure(
            "Project.TFrame",
            background=COLORS.get("surface_raised", "#FFFFFF"),
        )
        style.configure(
            "Project.TLabelframe",
            background=COLORS.get("surface_raised", "#FFFFFF"),
            bordercolor=COLORS.get("border_strong", "#CBD5E1"),
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Project.TLabelframe.Label",
            background=COLORS.get("surface_raised", "#FFFFFF"),
            foreground=COLORS.get("text_primary", "#111827"),
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Project.TLabel",
            background=COLORS.get("surface_raised", "#FFFFFF"),
            foreground=COLORS.get("text_secondary", "#64748B"),
            font=("Segoe UI", 9),
        )
        style.configure("Project.TButton", font=("Segoe UI", 9, "bold"), padding=(7, 4))
        style.configure("Project.TCombobox", font=("Segoe UI", 9), padding=(4, 3))

        self.frame = ttk.Frame(self.popup, padding=(10, 8), style="Project.TFrame")
        self.frame.pack(fill="both", expand=True)
        project_row = ttk.LabelFrame(
            self.frame,
            text="Project & Sun",
            padding=(10, 8),
            style="Project.TLabelframe",
        )
        project_row.pack(fill="x")
        author_row = ttk.LabelFrame(
            self.frame,
            text="Finishes & Structure",
            padding=(10, 8),
            style="Project.TLabelframe",
        )
        author_row.pack(fill="x", pady=(8, 0))

        ttk.Label(project_row, text="Floor", style="Project.TLabel").pack(side="left")
        self.floor_var = tk.StringVar()
        self.floor_selector = ttk.Combobox(
            project_row, textvariable=self.floor_var, state="readonly", width=24,
            style="Project.TCombobox",
        )
        self.floor_selector.pack(side="left", padx=(6, 4))
        self.floor_selector.bind("<<ComboboxSelected>>", self._activate)
        for label, command in (
            ("Add", self._add), ("Duplicate", self._duplicate),
            ("Rename", self._rename), ("Elevation", self._elevation),
            ("Delete", self._delete),
        ):
            button = ttk.Button(project_row, text=label, command=command, style="Project.TButton")
            button.pack(side="left", padx=1)
            if label == "Elevation":
                self.elevation_button = button
            elif label == "Delete":
                self.delete_button = button

        ttk.Separator(project_row, orient="vertical").pack(side="left", fill="y", padx=9)
        ttk.Label(project_row, text="Sun", style="Project.TLabel").pack(side="left")
        self.time_var = tk.DoubleVar(value=12)
        self.time_input = ttk.Spinbox(
            project_row, from_=0, to=24, increment=.5, width=5,
            textvariable=self.time_var, command=self._sun_changed,
        )
        self.time_input.pack(side="left", padx=(4, 2))
        ttk.Label(project_row, text="h", style="Project.TLabel").pack(side="left")
        self.manual_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            project_row, text="Manual", variable=self.manual_var, command=self._sun_changed
        ).pack(side="left", padx=(5, 2))
        self.azimuth_var = tk.DoubleVar(value=120)
        self.azimuth_input = ttk.Spinbox(
            project_row, from_=0, to=359, increment=1, width=6,
            textvariable=self.azimuth_var, command=self._sun_changed,
        )
        self.azimuth_input.pack(side="left", padx=2)
        ttk.Label(project_row, text="°", style="Project.TLabel").pack(side="left")
        for widget in (self.time_input, self.azimuth_input):
            widget.bind("<Return>", self._sun_changed)
            widget.bind("<FocusOut>", self._sun_changed)

        ttk.Label(author_row, text="Finish", style="Project.TLabel").pack(side="left")
        self.target_var = tk.StringVar(value=self.TARGETS[0])
        self.target_selector = ttk.Combobox(
            author_row, textvariable=self.target_var, values=self.TARGETS,
            state="readonly", width=12,
        )
        self.target_selector.pack(side="left", padx=(4, 2))
        self.target_selector.bind("<<ComboboxSelected>>", self._target_changed)
        self.finish_var = tk.StringVar()
        self.finish_selector = ttk.Combobox(
            author_row, textvariable=self.finish_var, state="readonly", width=16
        )
        self.finish_selector.pack(side="left", padx=2)
        self.color_button = ttk.Button(author_row, text="Color…", command=self._choose_custom_color)
        self.color_button.pack(side="left", padx=(2, 1))
        self.paint_button = ttk.Button(author_row, text="Paint", command=lambda: self._begin_capture("paint"))
        self.paint_button.pack(side="left", padx=(2, 6))

        self.pillar_button = ttk.Button(author_row, text="Pillar", command=lambda: self._begin_capture("pillar"))
        self.beam_button = ttk.Button(author_row, text="Beam", command=lambda: self._begin_capture("beam"))
        self.deck_button = ttk.Button(author_row, text="Deck", command=lambda: self._begin_capture("deck"))
        for button in (self.pillar_button, self.beam_button, self.deck_button):
            button.pack(side="left", padx=1)
        self.cancel_button = ttk.Button(author_row, text="Cancel", command=self._cancel_capture, state="disabled")
        self.cancel_button.pack(side="left", padx=(5, 1))
        self.frame.bind("<Destroy>", self._destroyed, add="+")
        self._target_changed()
        self.refresh()

    def toggle(self, anchor):
        """Show or hide the controls directly below the top-toolbar button."""
        if self.popup.winfo_viewable():
            self.hide()
            return
        self.refresh()
        self.popup.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height()
        width = self.popup.winfo_reqwidth()
        height = self.popup.winfo_reqheight()
        x = max(0, min(x, self.popup.winfo_screenwidth() - width))
        y = max(0, min(y, self.popup.winfo_screenheight() - height))
        self.popup.geometry(f"+{x}+{y}")
        self.popup.deiconify()
        self.popup.lift()
        self.popup.focus_set()

    def hide(self):
        self.popup.withdraw()

    @property
    def state(self):
        return self.serializer.project_state

    @staticmethod
    def _load_finishes():
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finish_manifest.json")
        with open(path, encoding="utf-8") as stream:
            manifest = json.load(stream)
        if not isinstance(manifest.get("version"), str) or not isinstance(manifest.get("finishes"), list):
            raise ValueError("finish_manifest.json: invalid versioned finish manifest")
        required = {"id", "label", "surfaces", "swatch"}
        finishes = [item for item in manifest["finishes"] if isinstance(item, dict) and required <= set(item)]
        if len(finishes) != len(manifest["finishes"]):
            raise ValueError("finish_manifest.json: every finish needs id, label, surfaces, and swatch")
        return finishes

    def _run(self, operation):
        try:
            result = operation()
        except Exception as exc:
            messagebox.showerror("VastuCraft Pro", str(exc), parent=self.frame.winfo_toplevel())
            self.refresh()
            return None
        self.refresh()
        return result
    def _selected_floor_id(self):
        return self._floor_by_label.get(self.floor_var.get(), self.state.active_floor_id)

    def refresh(self):
        if self._capture:
            self._cancel_capture()
        self._refreshing = True
        try:
            floors = self.state.floors
            self._floor_by_label = {
                f"{floor['name']} ({float(floor['elevation_cm']):g} cm)": floor["id"]
                for floor in floors
            }
            self.floor_selector.configure(values=list(self._floor_by_label))
            active = next(floor for floor in floors if floor["id"] == self.state.active_floor_id)
            label = next(label for label, floor_id in self._floor_by_label.items() if floor_id == active["id"])
            self.floor_var.set(label)
            is_ground = float(active["elevation_cm"]) == 0
            self.elevation_button.configure(state="disabled" if is_ground else "normal")
            self.delete_button.configure(state="disabled" if len(floors) == 1 or is_ground else "normal")
            sun = self.state.sun_settings
            self.time_var.set(float(sun["time_hours"]))
            self.manual_var.set(bool(sun["direction_override"]))
            self.azimuth_var.set(float(sun["azimuth_deg"]))
            self.azimuth_input.configure(state="normal" if self.manual_var.get() else "disabled")
        finally:
            self._refreshing = False

    def _activate(self, _event=None):
        if not self._refreshing:
            self._run(lambda: self.serializer.activate_floor(self._selected_floor_id()))

    def _add(self):
        name = simpledialog.askstring("Add Floor", "Floor name:", parent=self.frame.winfo_toplevel())
        if name is not None:
            self._run(lambda: self.serializer.add_floor(name))

    def _duplicate(self):
        self._run(lambda: self.serializer.duplicate_floor(self._selected_floor_id()))

    def _rename(self):
        floor_id = self._selected_floor_id()
        current = next(floor for floor in self.state.floors if floor["id"] == floor_id)
        name = simpledialog.askstring(
            "Rename Floor", "Floor name:", initialvalue=current["name"],
            parent=self.frame.winfo_toplevel(),
        )
        if name is not None:
            self._run(lambda: self.serializer.rename_floor(floor_id, name))

    def _elevation(self):
        floor_id = self._selected_floor_id()
        current = next(floor for floor in self.state.floors if floor["id"] == floor_id)
        if float(current["elevation_cm"]) == 0:
            return
        value = simpledialog.askfloat(
            "Floor Elevation", "Elevation (cm):", initialvalue=current["elevation_cm"],
            minvalue=0, parent=self.frame.winfo_toplevel(),
        )
        if value is not None:
            self._run(lambda: self.serializer.set_floor_elevation(floor_id, value))

    def _delete(self):
        floor_id = self._selected_floor_id()
        if len(self.state.floors) == 1:
            return
        floor = next(item for item in self.state.floors if item["id"] == floor_id)
        entity_count = sum(len(values) for values in floor["geometry"].values() if isinstance(values, list))
        affected_refs = sum(
            reference.get("source_floor_id") == floor_id or reference.get("target_floor_id") == floor_id
            for reference in self.state.cross_floor_references
        )
        if messagebox.askyesno(
            "Delete Floor",
            f"Delete {floor['name']} with {entity_count} entities and {affected_refs} cross-floor references?",
            parent=self.frame.winfo_toplevel(),
        ):
            self._run(lambda: self.serializer.delete_floor(floor_id))

    def _sun_changed(self, _event=None):
        if self._refreshing:
            return
        self.azimuth_input.configure(state="normal" if self.manual_var.get() else "disabled")
        self._run(lambda: self.serializer.set_sun_settings(
            time_hours=self.time_var.get(), direction_override=self.manual_var.get(),
            azimuth_deg=self.azimuth_var.get(),
        ))
    def _target_changed(self, _event=None):
        surface = self.TARGET_SURFACE.get(self.target_var.get())
        compatible = [item for item in self.finishes if surface in item["surfaces"]]
        current_id = self._finish_by_label.get(self.finish_var.get(), {}).get("id")
        self.finish_selector.configure(values=[item["label"] for item in compatible])
        selected = next((item for item in compatible if item["id"] == current_id), None)
        if selected is None and compatible:
            preferred = "default-wall" if surface == "wall" else "default-floor"
            selected = next((item for item in compatible if item["id"] == preferred), compatible[0])
        self.finish_var.set(selected["label"] if selected else "")

    def _choose_custom_color(self):
        """Reuse Tk's native color picker and encode the exact color as a portable finish ID."""
        current = self._finish_by_label.get(self.finish_var.get(), {})
        chosen = colorchooser.askcolor(
            title="Choose paint color", parent=self.popup,
            initialcolor=current.get("swatch", "#f8fafc"),
        )
        if not chosen or not chosen[1]:
            return
        swatch = str(chosen[1]).lower()
        surface = self.TARGET_SURFACE.get(self.target_var.get(), "wall")
        category = "wall" if surface == "wall" else "floor"
        finish_id = f"custom-{category}-{swatch.lstrip('#')}"
        label = f"Custom {swatch.upper()}"
        surfaces = ["wall", "pillar", "beam", "railing"] if category == "wall" else ["floor", "deck"]
        finish = {
            "id": finish_id, "label": label, "category": category,
            "surfaces": surfaces, "swatch": swatch,
        }
        existing = next((item for item in self.finishes if item["id"] == finish_id), None)
        if existing is None:
            self.finishes.append(finish)
            existing = finish
        self._finish_by_label[label] = existing
        self._target_changed()
        self.finish_var.set(label)

    def _selected_finish(self):
        target = self.target_var.get()
        surface = self.TARGET_SURFACE.get(target)
        finish = self._finish_by_label.get(self.finish_var.get())
        if not finish:
            raise ValueError("Select a finish")
        if surface not in finish["surfaces"]:
            raise ValueError(f"{finish['label']} is not compatible with {target}")
        return finish

    def _bind_capture(self, widget, sequence, callback):
        bind_id = widget.bind(sequence, callback, add="+")
        if bind_id:
            self._capture_bindings.append((widget, sequence, bind_id))

    def _begin_capture(self, kind):
        self._cancel_capture()
        if kind == "paint":
            try:
                self._selected_finish()
            except Exception as exc:
                messagebox.showerror("VastuCraft Pro", str(exc), parent=self.frame.winfo_toplevel())
                return
        try:
            reset = getattr(self.serializer.tools, "reset_modes", None)
            if callable(reset):
                reset()
        except Exception:
            pass
        self._capture = kind
        self._capture_points = []
        try:
            self._previous_cursor = self.canvas.cget("cursor")
            cursors = ("spraycan", "pencil", "crosshair") if kind == "paint" else ("crosshair",)
            for cursor in cursors:
                try:
                    self.canvas.configure(cursor=cursor)
                    break
                except tk.TclError:
                    continue
        except tk.TclError:
            self._previous_cursor = ""
        self.cancel_button.configure(state="normal")
        labels = {
            "paint": "Paint: click", "pillar": "Pillar: click",
            "beam": "Beam: first point", "deck": "Deck: 0 pts",
        }
        getattr(self, f"{kind}_button").configure(text=labels[kind])
        self._bind_capture(self.canvas, "<Button-1>", self._canvas_click)
        self._bind_capture(self.owner, "<Escape>", self._cancel_capture)
        if kind == "paint":
            self._bind_capture(self.canvas, "<Motion>", self._paint_motion)
            self._bind_capture(self.canvas, "<Leave>", self._clear_paint_hover)
        if kind == "deck":
            self._bind_capture(self.canvas, "<Double-Button-1>", self._finish_deck)
            self._bind_capture(self.owner, "<Return>", self._finish_deck)
        self.hide()

    def _cancel_capture(self, _event=None):
        active = self._capture
        for widget, sequence, bind_id in self._capture_bindings:
            try:
                widget.unbind(sequence, bind_id)
            except tk.TclError:
                pass
        self._capture_bindings.clear()
        try:
            self.canvas.delete("parity_capture")
            self.canvas.delete("parity_paint_hover")
            self.canvas.configure(cursor=self._previous_cursor)
        except tk.TclError:
            pass
        self._paint_wall_id = None
        self._capture = None
        self._capture_points = []
        try:
            self.paint_button.configure(text="Paint")
            self.pillar_button.configure(text="Pillar")
            self.beam_button.configure(text="Beam")
            self.deck_button.configure(text="Deck")
            self.cancel_button.configure(state="disabled")
        except tk.TclError:
            pass
        return "break" if active and _event is not None else None

    def _destroyed(self, event):
        if event.widget is self.frame:
            self._cancel_capture()

    def _event_point(self, event):
        return [float(self.canvas.canvasx(event.x)), float(self.canvas.canvasy(event.y))]

    def _canvas_click(self, event):
        point = self._event_point(event)
        kind = self._capture
        if kind == "paint":
            wall_id = self._paint_wall_id
            self._cancel_capture()
            self._run(lambda: self._paint_at(point, wall_id))
        elif kind == "pillar":
            self._cancel_capture()
            self._run(lambda: self._add_pillar(point))
        elif kind == "beam":
            if not self._capture_points:
                self._capture_points.append(point)
                self.beam_button.configure(text="Beam: end point")
                self._preview_points()
            elif math.hypot(point[0] - self._capture_points[0][0], point[1] - self._capture_points[0][1]) <= 1e-6:
                messagebox.showerror("VastuCraft Pro", "Beam endpoints must be distinct", parent=self.frame.winfo_toplevel())
            else:
                start = self._capture_points[0]
                self._cancel_capture()
                self._run(lambda: self._add_beam(start, point))
        elif kind == "deck":
            self._append_capture_point(point)
            self.deck_button.configure(text=f"Deck: {len(self._capture_points)} pts")
            self._preview_points()
        return "break"

    def _append_capture_point(self, point):
        if not self._capture_points or math.hypot(
            point[0] - self._capture_points[-1][0], point[1] - self._capture_points[-1][1]
        ) > 1e-6:
            self._capture_points.append(point)

    def _preview_points(self):
        self.canvas.delete("parity_capture")
        if len(self._capture_points) > 1:
            self.canvas.create_line(
                *(coordinate for point in self._capture_points for coordinate in point),
                fill="#0f766e", width=2, dash=(4, 2), tags=("parity_capture",),
            )
        for x, y in self._capture_points:
            self.canvas.create_oval(
                x - 3, y - 3, x + 3, y + 3, fill="#0f766e", outline="",
                tags=("parity_capture",),
            )
    def _finish_deck(self, event=None):
        if self._capture != "deck":
            return None
        if event is not None and getattr(event, "widget", None) is self.canvas:
            self._append_capture_point(self._event_point(event))
        points = [list(point) for point in self._capture_points]
        if len(points) < 3:
            messagebox.showerror("VastuCraft Pro", "Deck needs at least three points", parent=self.frame.winfo_toplevel())
            return "break"
        self._cancel_capture()
        self._run(lambda: self._add_deck(points))
        return "break"

    def _fresh_id(self, prefix):
        document = self.state.snapshot()
        used = {floor["id"] for floor in document["floors"]}
        used.update(reference["id"] for reference in document["cross_floor_references"])
        for floor in document["floors"]:
            for values in floor["geometry"].values():
                if isinstance(values, list):
                    used.update(item.get("id") for item in values if isinstance(item, dict))
        while True:
            candidate = f"{prefix}-{uuid.uuid4()}"
            if candidate not in used:
                return candidate

    def _add_pillar(self, point):
        record = {
            "id": self._fresh_id("pillar"), "position": point,
            "width_cm": 30.0, "depth_cm": 30.0, "height_cm": 280.0,
            "elevation_cm": 0.0, "shape": "rect", "material_id": "default-wall",
        }
        return self.serializer.commit_active_geometry(
            lambda geometry: geometry.setdefault("pillars", []).append(record) or record,
            redraw_structures=True,
        )

    def _add_beam(self, start, end):
        record = {
            "id": self._fresh_id("beam"), "start": start, "end": end,
            "width_cm": 20.0, "depth_cm": 30.0, "elevation_cm": 250.0,
            "material_id": "default-wall",
        }
        return self.serializer.commit_active_geometry(
            lambda geometry: geometry.setdefault("beams", []).append(record) or record,
            redraw_structures=True,
        )

    def _add_deck(self, points):
        record = {
            "id": self._fresh_id("deck"), "polygon": points,
            "thickness_cm": 15.0, "elevation_cm": 0.0,
            "type": "custom", "material_id": "default-floor",
        }
        return self.serializer.commit_active_geometry(
            lambda geometry: geometry.setdefault("deck_slabs", []).append(record) or record,
            redraw_structures=True,
        )

    @staticmethod
    def _segment_distance(point, start, end):
        px, py = point
        ax, ay = start
        bx, by = end
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        ratio = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + ratio * dx), py - (ay + ratio * dy))

    @classmethod
    def _point_in_polygon(cls, point, polygon):
        if len(polygon) < 3:
            return False
        inside = False
        x, y = point
        previous = polygon[-1]
        for current in polygon:
            if cls._segment_distance(point, previous, current) <= 1e-7:
                return True
            x1, y1 = previous
            x2, y2 = current
            if (y1 > y) != (y2 > y):
                crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                if x < crossing:
                    inside = not inside
            previous = current
        return inside

    @staticmethod
    def _polygon_area(points):
        return abs(sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(points, points[1:] + points[:1])
        )) / 2

    @staticmethod
    def _wall_segment(geometry, wall):
        vertices = {item["id"]: item.get("position") for item in geometry.get("vertices", [])}
        start = vertices.get(wall.get("start_vertex_id"))
        end = vertices.get(wall.get("end_vertex_id"))
        return (start, end) if start and end else (None, None)

    def _nearest_wall_candidate(self, geometry, point):
        candidates = []
        scale = self.serializer._structure_scale()
        for order, wall in enumerate(geometry.get("walls", [])):
            start, end = self._wall_segment(geometry, wall)
            if not start or not end:
                continue
            distance = self._segment_distance(point, start, end)
            tolerance = max(8.0, min(24.0, float(wall.get("thickness_cm", 15)) * scale / 2 + 5))
            if distance <= tolerance:
                candidates.append((distance, order, wall, start, end))
        if not candidates:
            return None
        distance, _order, wall, start, end = min(candidates, key=lambda item: (item[0], item[1]))
        return {"distance": distance, "wall": wall, "start": start, "end": end}

    def _nearest_wall(self, geometry, point):
        candidate = self._nearest_wall_candidate(geometry, point)
        return candidate["wall"] if candidate else None

    @staticmethod
    def _offset_wall_segment(start, end, target, amount=6.0):
        if target == "wall both faces":
            return start, end
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return start, end
        sign = 1 if target == "wall side A" else -1
        ox, oy = sign * -dy / length * amount, sign * dx / length * amount
        return [start[0] + ox, start[1] + oy], [end[0] + ox, end[1] + oy]

    def _draw_wall_indicator(self, wall, start, end, color, target, tag, *, width=4, label=False):
        start, end = self._offset_wall_segment(start, end, target)
        tags = (tag, "parity_capture" if tag == "parity_paint_hover" else "parity_finish_preview")
        self.canvas.create_line(
            *start, *end, fill=color, width=width, arrow="last",
            tags=tags,
        )
        if label:
            side = {
                "wall both faces": "Both faces", "wall side A": "Side A", "wall side B": "Side B",
            }[target]
            midpoint = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2]
            self.canvas.create_text(
                *midpoint, text=f"  {side}  ", fill="#ffffff", font=("Segoe UI", 9, "bold"),
                tags=tags,
            )

    def _clear_paint_hover(self, _event=None):
        self.canvas.delete("parity_paint_hover")
        self._paint_wall_id = None

    def _paint_motion(self, event):
        if self._capture != "paint" or not self.target_var.get().startswith("wall"):
            return
        point = self._event_point(event)
        candidate = self._nearest_wall_candidate(self.state.active_floor["geometry"], point)
        self.canvas.delete("parity_paint_hover")
        self._paint_wall_id = candidate["wall"]["id"] if candidate else None
        if candidate:
            self._draw_wall_indicator(
                candidate["wall"], candidate["start"], candidate["end"],
                "#2563eb", self.target_var.get(), "parity_paint_hover", width=6, label=True,
            )

    def _containing_room(self, geometry, point):
        vertices = {item["id"]: item.get("position") for item in geometry.get("vertices", [])}
        matches = []
        for room in geometry.get("rooms", []):
            polygon = [vertices.get(vertex_id) for vertex_id in room.get("boundary_vertex_ids", [])]
            if polygon and all(polygon) and self._point_in_polygon(point, polygon):
                matches.append((self._polygon_area(polygon), room))
        return min(matches, key=lambda match: match[0])[1] if matches else None

    def _containing_deck(self, geometry, point):
        matches = [
            (self._polygon_area(deck.get("polygon", [])), deck)
            for deck in geometry.get("deck_slabs", [])
            if self._point_in_polygon(point, deck.get("polygon", []))
        ]
        return min(matches, key=lambda match: match[0])[1] if matches else None
    def _paint_at(self, point, wall_id=None):
        target = self.target_var.get()
        finish = self._selected_finish()

        def mutation(geometry):
            if target.startswith("wall"):
                entity = next(
                    (wall for wall in geometry.get("walls", []) if wall.get("id") == wall_id),
                    None,
                ) if wall_id else None
                if entity is None:
                    entity = self._nearest_wall(geometry, point)
                field = {
                    "wall both faces": "material_id",
                    "wall side A": "material_side_a",
                    "wall side B": "material_side_b",
                }[target]
            elif target == "room floor":
                entity = self._containing_room(geometry, point)
                field = "floor_material_id"
            else:
                entity = self._containing_deck(geometry, point)
                field = "material_id"
            if entity is None:
                raise ValueError(f"No {target} target at that point")
            entity[field] = finish["id"]
            return entity

        entity = self.serializer.commit_active_geometry(
            mutation, redraw_structures=target == "deck"
        )
        self._tint_entity(entity, target, finish["swatch"])
        return entity

    def _tint_entity(self, entity, target, swatch):
        """Show the exact canonical target; persisted material fields remain authoritative."""
        if target.startswith("wall"):
            geometry = self.state.active_floor["geometry"]
            wall = next(
                (item for item in geometry.get("walls", []) if item.get("id") == entity.get("id")),
                entity,
            )
            start, end = self._wall_segment(geometry, wall)
            if start and end:
                tag = f"parity_finish:{entity.get('id')}:{target.replace(' ', '_')}"
                self.canvas.delete(tag)
                self._draw_wall_indicator(wall, start, end, swatch, target, tag, width=5)
            return

        candidates = set(self.canvas.find_withtag(f"entity:{entity.get('id')}"))
        source = str(entity.get("source_canvas_id", ""))
        if source.startswith("room_room_group_"):
            candidates.update(self.canvas.find_withtag(source[len("room_"):]))
        elif source.startswith("shape_"):
            candidates.update(self.canvas.find_withtag(f"source_shape:{source}"))
            try:
                candidates.add(int(source.split("_", 1)[1]))
            except ValueError:
                pass
        for item in candidates:
            try:
                item_type = self.canvas.type(item)
                if target == "room floor" and item_type in ("rectangle", "polygon", "oval"):
                    self.canvas.itemconfigure(item, fill=swatch)
                elif target == "deck" and item_type == "polygon":
                    self.canvas.itemconfigure(item, fill=swatch)
            except tk.TclError:
                continue
