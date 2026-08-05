"""Dropdown popover for v2 project, finish, and structure controls."""
from __future__ import annotations

import json
import math
import os
import tkinter as tk
import uuid
from tkinter import colorchooser, messagebox, simpledialog, ttk

from Helper.color_scheme import COLORS
import structural_joints


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
        self._capture_entity_ids = []
        self._capture_bindings = []
        self._selected_structure = None
        self._beam_capture_elevation = 0.0
        self._deck_capture_elevation = 0.0
        self._stair_width_cm = 110.0
        self._previous_cursor = ""
        self._paint_wall_id = None
        # The Furniture tab owns the launcher; this toolbar owns the existing additive
        # multi-point capture so normal controller modes never race staircase clicks.
        self.serializer.tools.begin_stair_capture = self.begin_stair_capture
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

        structure_dims_row = ttk.LabelFrame(
            self.frame,
            text="Structure Dimensions (cm)",
            padding=(10, 8),
            style="Project.TLabelframe",
        )
        structure_dims_row.pack(fill="x", pady=(8, 0))
        self.pillar_width_var = tk.DoubleVar(value=30.0)
        self.pillar_depth_var = tk.DoubleVar(value=30.0)
        self.pillar_height_var = tk.DoubleVar(value=280.0)
        self.pillar_shape_var = tk.StringVar(value="rect")
        self.beam_width_var = tk.DoubleVar(value=20.0)
        self.beam_depth_var = tk.DoubleVar(value=30.0)
        self.beam_elevation_var = tk.DoubleVar(value=0.0)
        self.deck_thickness_var = tk.DoubleVar(value=15.0)
        self.deck_elevation_var = tk.DoubleVar(value=0.0)
        self.deck_type_var = tk.StringVar(value="custom")
        self.structure_status_var = tk.StringVar(value="No structure selected")
        for label_text, var, lo, hi, inc in (
            ("Pillar W", self.pillar_width_var, 1, 1000, 1),
            ("Pillar D", self.pillar_depth_var, 1, 1000, 1),
            ("Pillar H", self.pillar_height_var, 1, 5000, 5),
        ):
            ttk.Label(structure_dims_row, text=label_text, style="Project.TLabel").pack(side="left", padx=(2, 0))
            ttk.Spinbox(
                structure_dims_row, from_=lo, to=hi, increment=inc, width=6,
                textvariable=var,
            ).pack(side="left", padx=(0, 6))
        ttk.Label(structure_dims_row, text="Shape", style="Project.TLabel").pack(side="left", padx=(2, 0))
        ttk.Combobox(
            structure_dims_row, textvariable=self.pillar_shape_var,
            values=("rect", "round"), state="readonly", width=6,
        ).pack(side="left", padx=(0, 6))
        for label_text, var, lo, hi, inc in (
            ("Beam W", self.beam_width_var, 1, 500, 1),
            ("Beam D", self.beam_depth_var, 1, 500, 1),
            ("Beam Elev", self.beam_elevation_var, 0, 5000, 5),
        ):
            ttk.Label(structure_dims_row, text=label_text, style="Project.TLabel").pack(side="left", padx=(2, 0))
            ttk.Spinbox(
                structure_dims_row, from_=lo, to=hi, increment=inc, width=6,
                textvariable=var,
            ).pack(side="left", padx=(0, 6))
        for label_text, var, lo, hi, inc in (
            ("Deck T", self.deck_thickness_var, 1, 500, 1),
            ("Deck Elev", self.deck_elevation_var, 0, 5000, 5),
        ):
            ttk.Label(structure_dims_row, text=label_text, style="Project.TLabel").pack(side="left", padx=(2, 0))
            ttk.Spinbox(
                structure_dims_row, from_=lo, to=hi, increment=inc, width=6,
                textvariable=var,
            ).pack(side="left", padx=(0, 6))
        ttk.Label(structure_dims_row, text="Deck Type", style="Project.TLabel").pack(side="left", padx=(2, 0))
        ttk.Combobox(
            structure_dims_row, textvariable=self.deck_type_var,
            values=("custom", "roof"), state="readonly", width=7,
        ).pack(side="left", padx=(0, 6))

        structure_edit_row = ttk.Frame(self.frame, style="Project.TFrame")
        structure_edit_row.pack(fill="x", pady=(5, 0))
        ttk.Label(
            structure_edit_row, textvariable=self.structure_status_var,
            style="Project.TLabel",
        ).pack(side="left", padx=(2, 8))
        self.select_structure_button = ttk.Button(
            structure_edit_row, text="Select/Edit",
            command=lambda: self._begin_capture("select_structure"),
            style="Project.TButton",
        )
        self.select_structure_button.pack(side="left", padx=1)
        ttk.Button(
            structure_edit_row, text="Apply Values",
            command=self._apply_selected_structure, style="Project.TButton",
        ).pack(side="left", padx=1)
        ttk.Label(
            structure_edit_row,
            text="Beam Elev/Deck Elev = 0 uses supporting pillar tops",
            style="Project.TLabel",
        ).pack(side="left", padx=(8, 0))

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

    def _run(self, operation, *, refresh=True):
        try:
            result = operation()
        except Exception as exc:
            messagebox.showerror("VastuCraft Pro", str(exc), parent=self.frame.winfo_toplevel())
            if refresh:
                self.refresh()
            return None
        if refresh:
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
            if self._selected_structure:
                kind, entity_id = self._selected_structure
                collection = {"pillar": "pillars", "beam": "beams", "deck": "deck_slabs"}[kind]
                if not any(item.get("id") == entity_id for item in active["geometry"].get(collection, [])):
                    self._selected_structure = None
                    self.structure_status_var.set("No structure selected")
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

    def begin_stair_capture(self, width_cm=110):
        """Start the Furniture-tab staircase path tool using Home Quest's width limits."""
        try:
            width = float(width_cm)
        except (TypeError, ValueError):
            messagebox.showerror(
                "Staircase", "Stair width must be a number from 60 to 500 cm.",
                parent=self.frame.winfo_toplevel(),
            )
            return
        if not 60 <= width <= 500:
            messagebox.showerror(
                "Staircase", "Stair width must be 60–500 cm.",
                parent=self.frame.winfo_toplevel(),
            )
            return
        self._stair_width_cm = float(round(width / 10) * 10)
        self._begin_capture("stair")

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
        self.serializer.tools._parity_capture_active = True
        self._capture_points = []
        self._capture_entity_ids = []
        selected_kind = self._selected_structure[0] if self._selected_structure else None
        if kind == "beam":
            self._beam_capture_elevation = float(self.beam_elevation_var.get())
        elif kind == "deck":
            self._deck_capture_elevation = 0.0 if selected_kind == "deck" else float(self.deck_elevation_var.get())
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
            "paint": "Paint: click", "pillar": "Pillar: place posts",
            "beam": "Beam: select first pillar", "deck": "Deck: select pillars",
            "select_structure": "Select structure on canvas",
        }
        button = (
            self.select_structure_button if kind == "select_structure"
            else getattr(self, f"{kind}_button", None)
        )
        if button is not None:
            button.configure(text=labels[kind])
        self._bind_capture(self.canvas, "<Button-1>", self._canvas_click)
        self._bind_capture(self.owner, "<Escape>", self._cancel_capture)
        if kind == "paint":
            self._bind_capture(self.canvas, "<Motion>", self._paint_motion)
            self._bind_capture(self.canvas, "<Leave>", self._clear_paint_hover)
        elif kind in ("pillar", "beam", "deck", "stair"):
            self._bind_capture(self.canvas, "<Motion>", self._structure_motion)
        if kind == "deck":
            self._bind_capture(self.canvas, "<Double-Button-1>", self._finish_deck)
            self._bind_capture(self.owner, "<Return>", self._finish_deck)
        elif kind == "stair":
            self._bind_capture(self.canvas, "<Double-Button-1>", self._finish_stair)
            self._bind_capture(self.owner, "<Return>", self._finish_stair)

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
        self.serializer.tools._parity_capture_active = False
        self._capture_points = []
        self._capture_entity_ids = []
        try:
            self.paint_button.configure(text="Paint")
            self.pillar_button.configure(text="Pillar")
            self.beam_button.configure(text="Beam")
            self.deck_button.configure(text="Deck")
            self.select_structure_button.configure(text="Select/Edit")
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
        elif kind == "select_structure":
            selected = self._structure_at_point(point)
            self._cancel_capture()
            if selected is None:
                messagebox.showinfo(
                    "VastuCraft Pro", "Click directly on a pillar, beam, or deck.",
                    parent=self.frame.winfo_toplevel(),
                )
            else:
                self._select_structure(*selected)
        elif kind == "pillar":
            aligned, _guide = self._aligned_pillar_point(point)
            record = self._run(lambda: self._add_pillar(aligned), refresh=False)
            if record:
                self._select_structure("pillar", record)
                self.canvas.tag_raise("parity_capture")
                self.pillar_button.configure(text="Pillar: place another (Esc to finish)")
        elif kind == "beam":
            snapped, pillar = self._snap_to_pillar(point)
            if pillar is None:
                messagebox.showinfo(
                    "Beam", "Click directly on a pillar to select it.",
                    parent=self.frame.winfo_toplevel(),
                )
                return "break"
            pillar_id = pillar["id"]
            if not self._capture_entity_ids:
                self._capture_points.append(snapped)
                self._capture_entity_ids.append(pillar_id)
                self.beam_button.configure(text="Beam: select second pillar")
                self.structure_status_var.set(f"Beam start: {pillar_id[:18]}")
                self._preview_points()
            elif pillar_id == self._capture_entity_ids[0]:
                messagebox.showerror(
                    "Beam", "Select a different second pillar.",
                    parent=self.frame.winfo_toplevel(),
                )
            else:
                start_pillar_id = self._capture_entity_ids[0]
                self._cancel_capture()
                record = self._run(lambda: self._add_beam(start_pillar_id, pillar_id))
                if record:
                    self._select_structure("beam", record)
        elif kind == "deck":
            snapped, pillar = self._snap_to_pillar(point)
            close_tolerance = self._pillar_snap_tolerance()
            if len(self._capture_points) >= 3 and math.hypot(
                snapped[0] - self._capture_points[0][0], snapped[1] - self._capture_points[0][1]
            ) <= close_tolerance:
                return self._finish_deck()
            pillar_id = pillar.get("id") if pillar else None
            if pillar_id and pillar_id in self._capture_entity_ids:
                if self._capture_entity_ids and pillar_id == self._capture_entity_ids[-1]:
                    return "break"
                messagebox.showerror("VastuCraft Pro", "Each deck corner must use a different pillar", parent=self.frame.winfo_toplevel())
                return "break"
            self._append_capture_point(snapped)
            self._capture_entity_ids.append(pillar_id)
            self.deck_button.configure(text=f"Deck: {len(self._capture_points)} pillars (click first to close)")
            self._preview_points()
        elif kind == "stair":
            snapped = self._native_snap(point, self._capture_points)
            if self._append_stair_point(snapped):
                self._preview_points()
        return "break"

    def _append_capture_point(self, point):
        if not self._capture_points or math.hypot(
            point[0] - self._capture_points[-1][0], point[1] - self._capture_points[-1][1]
        ) > 1e-6:
            self._capture_points.append(point)

    def _append_stair_point(self, point):
        """Append one stair point unless it is within React's 1 cm minimum segment."""
        if self._capture_points:
            distance_px = math.hypot(
                point[0] - self._capture_points[-1][0],
                point[1] - self._capture_points[-1][1],
            )
            if distance_px < self.serializer._structure_scale():
                return False
        self._capture_points.append([float(point[0]), float(point[1])])
        return True

    def _preview_points(self):
        self.canvas.delete("parity_capture_fixed")
        tags = ("parity_capture", "parity_capture_fixed")
        if len(self._capture_points) > 1:
            self.canvas.create_line(
                *(coordinate for point in self._capture_points for coordinate in point),
                fill="#22d3ee", width=2, dash=(6, 4), tags=tags,
            )
        for index, (x, y) in enumerate(self._capture_points, start=1):
            self.canvas.create_oval(
                x - 7, y - 7, x + 7, y + 7, fill="", outline="#22d3ee",
                width=3, tags=tags,
            )
            self.canvas.create_text(
                x + 11, y - 11, text=str(index), fill="#e0f2fe",
                font=("Segoe UI", 10, "bold"), tags=tags,
            )

    def _format_structure_length(self, pixels):
        cm = abs(float(pixels)) / max(self.serializer._structure_scale(), 1e-9)
        total_inches = cm / 2.54
        feet = int(total_inches // 12)
        inches = total_inches - feet * 12
        return f"{feet}' {inches:.1f}\"" if feet else f"{inches:.1f} in"

    def _pillar_guide_tolerance(self):
        return max(3.0, 15.0 * self.serializer._structure_scale())

    def _native_snap(self, point, previous=()):
        """Reuse the editor's endpoint/grid/orthogonal snap engine before structure snapping."""
        try:
            helper = self.serializer.tools.guideline_helper
            x, y, _info = helper.get_snap_point(
                float(point[0]), float(point[1]), list(previous), snap_to_existing=True,
            )
            return [float(x), float(y)]
        except Exception:
            return [float(point[0]), float(point[1])]

    def _snap_to_pillar(self, point):
        pillars = self.state.active_floor["geometry"].get("pillars", [])
        tolerance = self._pillar_snap_tolerance()
        pillar = structural_joints.nearest_pillar(pillars, point, tolerance)
        if pillar is None:
            point = self._native_snap(point, self._capture_points)
            pillar = structural_joints.nearest_pillar(pillars, point, tolerance)
        if pillar is None:
            return list(point), None
        position = pillar.get("position", point)
        return [float(position[0]), float(position[1])], pillar

    def _aligned_pillar_point(self, point):
        point = self._native_snap(point)
        pillars = self.state.active_floor["geometry"].get("pillars", [])
        guide = structural_joints.pillar_alignment_guide(
            pillars, point, self._pillar_guide_tolerance(),
        )
        aligned = [float(point[0]), float(point[1])]
        if guide["column"]:
            aligned[0] = guide["column"]["position"][0]
        if guide["row"]:
            aligned[1] = guide["row"]["position"][1]
        return aligned, guide

    def _structure_motion(self, event):
        if self._capture not in ("pillar", "beam", "deck", "stair"):
            return
        self.canvas.delete("parity_capture_hover")
        tags = ("parity_capture", "parity_capture_hover")
        raw = self._event_point(event)
        if self._capture == "stair":
            point = self._native_snap(raw, self._capture_points)
            if self._capture_points:
                start = self._capture_points[-1]
                width_px = max(2, self._stair_width_cm * self.serializer._structure_scale())
                self.canvas.create_line(
                    *start, *point, fill="#c7d2fe", width=width_px,
                    capstyle="projecting", tags=tags,
                )
                self.canvas.create_line(
                    *start, *point, fill="#6366f1", width=2, dash=(6, 4), tags=tags,
                )
                midpoint = ((start[0] + point[0]) / 2, (start[1] + point[1]) / 2)
                self.canvas.create_text(
                    midpoint[0], midpoint[1] - 12,
                    text=f"{self._stair_width_cm:g} cm",
                    fill="#4f46e5", font=("Segoe UI", 10, "bold"), tags=tags,
                )
            return
        if self._capture == "pillar":
            point, guide = self._aligned_pillar_point(raw)
            for axis, color, angle in (("column", "#22d3ee", 90), ("row", "#a855f7", 0)):
                match = guide[axis]
                if not match:
                    continue
                other = match["position"]
                self.canvas.create_line(*other, *point, fill=color, width=2, dash=(6, 6), tags=tags)
                midpoint = ((other[0] + point[0]) / 2, (other[1] + point[1]) / 2)
                self.canvas.create_text(
                    midpoint[0] + 10, midpoint[1] - 10,
                    text=f"{self._format_structure_length(match['spacing'])} · {angle}°",
                    fill=color, font=("Segoe UI", 10, "bold"), tags=tags,
                )
            scale = self.serializer._structure_scale()
            half_w = max(4, float(self.pillar_width_var.get()) * scale / 2)
            half_d = max(4, float(self.pillar_depth_var.get()) * scale / 2)
            creator = self.canvas.create_oval if self.pillar_shape_var.get() == "round" else self.canvas.create_rectangle
            creator(
                point[0] - half_w, point[1] - half_d, point[0] + half_w, point[1] + half_d,
                fill="", outline="#22d3ee", width=2, dash=(4, 3), tags=tags,
            )
            return

        point, pillar = self._snap_to_pillar(raw)
        if pillar:
            radius = max(9.0, max(
                float(pillar.get("width_cm", 30)), float(pillar.get("depth_cm", 30)),
            ) * self.serializer._structure_scale() / 2 + 4)
            self.canvas.create_oval(
                point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius,
                fill="", outline="#22d3ee", width=3, tags=tags,
            )
        if self._capture_points:
            start = self._capture_points[-1]
            self.canvas.create_line(*start, *point, fill="#22d3ee", width=3, dash=(6, 4), tags=tags)
            dx, dy = point[0] - start[0], point[1] - start[1]
            angle = math.degrees(math.atan2(dy, dx)) % 180
            self.canvas.create_text(
                (start[0] + point[0]) / 2, (start[1] + point[1]) / 2 - 12,
                text=f"{self._format_structure_length(math.hypot(dx, dy))} · {angle:.1f}°",
                fill="#22d3ee", font=("Segoe UI", 10, "bold"), tags=tags,
            )

    def _structure_at_point(self, point):
        geometry = self.state.active_floor["geometry"]
        collections = {"pillar": "pillars", "beam": "beams", "deck": "deck_slabs"}
        items = self.canvas.find_overlapping(point[0] - 7, point[1] - 7, point[0] + 7, point[1] + 7)
        for item in reversed(items):
            tags = set(self.canvas.gettags(item))
            if "parity_floor_underlay" in tags:
                continue
            kind = next((name for name in collections if f"parity_{name}" in tags), None)
            entity_id = next((tag.split(":", 1)[1] for tag in tags if tag.startswith("entity:")), None)
            if kind and entity_id:
                entity = next(
                    (value for value in geometry.get(collections[kind], []) if value.get("id") == entity_id),
                    None,
                )
                if entity:
                    return kind, entity
        return None

    def _select_structure(self, kind, entity):
        self._selected_structure = (kind, entity["id"])
        if kind == "pillar":
            self.pillar_width_var.set(float(entity.get("width_cm", 30)))
            self.pillar_depth_var.set(float(entity.get("depth_cm", 30)))
            self.pillar_height_var.set(float(entity.get("height_cm", 280)))
            self.pillar_shape_var.set(str(entity.get("shape", "rect")))
        elif kind == "beam":
            self.beam_width_var.set(float(entity.get("width_cm", 20)))
            self.beam_depth_var.set(float(entity.get("depth_cm", 30)))
            self.beam_elevation_var.set(float(entity.get("elevation_cm", 0)))
        else:
            self.deck_thickness_var.set(float(entity.get("thickness_cm", 15)))
            self.deck_elevation_var.set(float(entity.get("elevation_cm", 0)))
            self.deck_type_var.set(str(entity.get("type", "custom")))
        detail = f" · elevation {float(entity.get('elevation_cm', 0)):g} cm" if kind == "beam" else ""
        self.structure_status_var.set(f"Selected {kind}: {entity['id'][:18]}{detail}")

    def _apply_selected_structure(self):
        if not self._selected_structure:
            messagebox.showinfo("VastuCraft Pro", "Select a structure first", parent=self.frame.winfo_toplevel())
            return
        kind, entity_id = self._selected_structure
        collection = {"pillar": "pillars", "beam": "beams", "deck": "deck_slabs"}[kind]

        def mutation(geometry):
            entity = next((item for item in geometry.get(collection, []) if item.get("id") == entity_id), None)
            if entity is None:
                raise ValueError("The selected structure is no longer on this floor")
            if kind == "pillar":
                entity.update({
                    "width_cm": max(1.0, float(self.pillar_width_var.get())),
                    "depth_cm": max(1.0, float(self.pillar_depth_var.get())),
                    "height_cm": max(1.0, float(self.pillar_height_var.get())),
                    "shape": str(self.pillar_shape_var.get() or "rect"),
                })
            elif kind == "beam":
                post_ids = set(entity.get("post_ids", []))
                supports = [
                    pillar for pillar in geometry.get("pillars", [])
                    if pillar.get("id") in post_ids
                ]
                entity.update({
                    "width_cm": max(1.0, float(self.beam_width_var.get())),
                    "depth_cm": max(1.0, float(self.beam_depth_var.get())),
                    "elevation_cm": self._resolved_beam_elevation(
                        self.beam_elevation_var.get(), supports,
                    ),
                })
            else:
                entity.update({
                    "thickness_cm": max(1.0, float(self.deck_thickness_var.get())),
                    "elevation_cm": max(0.0, float(self.deck_elevation_var.get())),
                    "type": str(self.deck_type_var.get() or "custom"),
                })
            return entity

        entity = self._run(lambda: self.serializer.commit_active_geometry(mutation, redraw_structures=True))
        if entity:
            self._select_structure(kind, entity)

    def _finish_deck(self, event=None):
        if self._capture != "deck":
            return None
        points = [list(point) for point in self._capture_points]
        if len(points) < 3:
            messagebox.showerror("VastuCraft Pro", "Deck needs at least three pillar corners", parent=self.frame.winfo_toplevel())
            return "break"
        self._cancel_capture()
        record = self._run(lambda: self._add_deck(points))
        if record:
            self._select_structure("deck", record)
        return "break"

    def _finish_stair(self, event=None):
        if self._capture != "stair":
            return None
        points = [list(point) for point in self._capture_points]
        if len(points) < 2:
            messagebox.showerror(
                "Staircase", "Draw at least two points before finishing the staircase.",
                parent=self.frame.winfo_toplevel(),
            )
            return "break"
        active = self.state.active_floor
        upper = min(
            (
                floor for floor in self.state.floors
                if float(floor["elevation_cm"]) > float(active["elevation_cm"])
            ),
            key=lambda floor: float(floor["elevation_cm"]),
            default=None,
        )
        if upper is None:
            self._cancel_capture()
            messagebox.showerror(
                "Staircase", "Add a second floor first — a staircase needs two floors to connect.",
                parent=self.frame.winfo_toplevel(),
            )
            return "break"
        width_cm = self._stair_width_cm
        self._cancel_capture()
        self._run(lambda: self._add_stair(points, width_cm, active["id"], upper["id"]))
        return "break"

    def _add_stair(self, points, width_cm, lower_floor_id, upper_floor_id):
        record = {
            "id": self._fresh_id("stair"),
            "lower_floor_id": str(lower_floor_id),
            "upper_floor_id": str(upper_floor_id),
            "path_points": [[float(point[0]), float(point[1])] for point in points],
            "width_cm": float(width_cm),
        }
        return self.serializer.commit_active_geometry(
            lambda geometry: geometry.setdefault("stairs", []).append(record) or record,
            redraw_structures=True,
        )

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
            "width_cm": max(1.0, float(self.pillar_width_var.get())),
            "depth_cm": max(1.0, float(self.pillar_depth_var.get())),
            "height_cm": max(1.0, float(self.pillar_height_var.get())),
            "elevation_cm": 0.0,
            "shape": str(self.pillar_shape_var.get() or "rect"),
            "material_id": "default-wall",
        }
        return self.serializer.commit_active_geometry(
            lambda geometry: geometry.setdefault("pillars", []).append(record) or record,
            redraw_structures=True,
        )

    @staticmethod
    def _resolved_beam_elevation(requested, pillars):
        requested = max(0.0, float(requested))
        if requested > 0:
            return requested
        support_top = max(
            (
                float(pillar.get("height_cm", 0)) + float(pillar.get("elevation_cm", 0))
                for pillar in pillars
            ),
            default=280.0,
        )
        return max(280.0, support_top)

    def _add_beam(self, start_pillar_id, end_pillar_id):
        pillars = self.state.active_floor["geometry"].get("pillars", [])
        pillars_by_id = {pillar.get("id"): pillar for pillar in pillars}
        start_pillar = pillars_by_id.get(start_pillar_id)
        end_pillar = pillars_by_id.get(end_pillar_id)
        if start_pillar is None or end_pillar is None:
            raise ValueError("A selected pillar is no longer on this floor")
        start = start_pillar.get("position")
        end = end_pillar.get("position")
        if not isinstance(start, (list, tuple)) or len(start) != 2 or not isinstance(end, (list, tuple)) or len(end) != 2:
            raise ValueError("Selected pillars need valid positions")
        start = [float(start[0]), float(start[1])]
        end = [float(end[0]), float(end[1])]

        scale = self.serializer._structure_scale()
        start_fp = structural_joints.footprint_of(start_pillar)
        end_fp = structural_joints.footprint_of(end_pillar)
        for footprint in (start_fp, end_fp):
            footprint.width *= scale
            footprint.depth *= scale
        adj_start, adj_end = structural_joints.extend_beam_ends_to_pillars(
            start, end, start_fp, end_fp,
        )
        requested_elevation = getattr(self, "_beam_capture_elevation", self.beam_elevation_var.get())
        record = {
            "id": self._fresh_id("beam"),
            "start": list(adj_start), "end": list(adj_end),
            "width_cm": max(1.0, float(self.beam_width_var.get())),
            "depth_cm": max(1.0, float(self.beam_depth_var.get())),
            "elevation_cm": self._resolved_beam_elevation(
                requested_elevation, (start_pillar, end_pillar),
            ),
            "material_id": "default-wall",
            "post_ids": [start_pillar_id, end_pillar_id],
        }
        beam_id = record["id"]

        def mutation(geometry):
            geometry.setdefault("beams", []).append(record)
            for pillar_id in (start_pillar_id, end_pillar_id):
                linked = next(
                    (pillar for pillar in geometry.get("pillars", []) if pillar.get("id") == pillar_id),
                    None,
                )
                if linked is not None:
                    beam_ids = linked.setdefault("beam_ids", [])
                    if beam_id not in beam_ids:
                        beam_ids.append(beam_id)
            return record

        return self.serializer.commit_active_geometry(mutation, redraw_structures=True)

    def _add_deck(self, points):
        """Create a deck/roof from ordered pillar picks, seated on their outer faces."""
        pillars = self.state.active_floor["geometry"].get("pillars", [])
        tolerance = self._pillar_snap_tolerance()
        snapped, supports = [], []
        for point in points:
            pillar = structural_joints.nearest_pillar(pillars, point, tolerance)
            if pillar is not None:
                position = pillar.get("position")
                snapped.append([float(position[0]), float(position[1])])
                supports.append(pillar)
            else:
                snapped.append(list(point))
                supports.append(None)

        scale = self.serializer._structure_scale()
        footprints = []
        for pillar in supports:
            if pillar is None:
                footprints.append(None)
                continue
            footprint = structural_joints.footprint_of(pillar)
            footprint.width *= scale
            footprint.depth *= scale
            footprints.append(footprint)
        adjusted = [
            list(point) for point in structural_joints.expand_deck_to_pillars(
                [tuple(point) for point in snapped], footprints,
            )
        ]

        requested_elevation = float(getattr(self, "_deck_capture_elevation", self.deck_elevation_var.get()))
        support_top = max(
            (
                float(pillar.get("height_cm", 0)) + float(pillar.get("elevation_cm", 0))
                for pillar in supports if pillar is not None
            ),
            default=0.0,
        )
        post_ids = list(dict.fromkeys(
            pillar["id"] for pillar in supports if pillar is not None
        ))
        record = {
            "id": self._fresh_id("deck"), "polygon": adjusted,
            "thickness_cm": max(1.0, float(self.deck_thickness_var.get())),
            "elevation_cm": requested_elevation if requested_elevation > 0 else support_top,
            "type": str(self.deck_type_var.get() or "custom"),
            "material_id": "default-floor", "post_ids": post_ids,
        }
        return self.serializer.commit_active_geometry(
            lambda geometry: geometry.setdefault("deck_slabs", []).append(record) or record,
            redraw_structures=True,
        )

    def _pillar_snap_tolerance(self) -> float:
        """Pixels-of-tolerance to snap a click to a pillar center.

        Defaults to a generous radius (so the user does not have to click the
        exact center) but grows with the pillar footprint so larger posts are
        easier to snap to. Mirrors the React Home Quest placement tolerance.
        """
        try:
            scale = self.serializer._structure_scale()
        except Exception:
            scale = 1.0
        pillar_px = max(
            float(self.pillar_width_var.get()),
            float(self.pillar_depth_var.get()),
        ) * scale
        return max(24.0, pillar_px / 2 + 24.0)

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
