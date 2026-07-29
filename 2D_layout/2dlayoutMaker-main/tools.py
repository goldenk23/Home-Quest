import tkinter as tk
from tkinter import simpledialog, colorchooser, filedialog, messagebox
import math
import os
import shutil
import sys
import tempfile
import platform
import subprocess
import importlib.util
import uuid

# Ensure this module's directory is first on sys.path so local `Helper/*` resolves
# to MiniAutoCAD's bundled helper folder, not the main app's `Helper/` package.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    if _THIS_DIR and _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageGrab
from Furniture import Furniture, find_image_path
from drawing_helpers import get_distance_label
from geometry import calculate_polygon_area, calculate_polygon_perimeter
from polygon_label_placer import PolygonLabelPlacer


def _import_local_dimension_drawer():
    """
    VastuApp already imports the main app's top-level `Helper` package.
    That means `import Helper.*` becomes "sticky" via sys.modules and can
    resolve to the wrong Helper folder.

    To make MiniAutoCAD stable when launched from VastuApp, we:
    - try importing `Helper.dimensioning` only if it resolves to this module's folder
    - otherwise, load `Helper/dimensioning.py` directly via file path
    """

    def _norm(p: str) -> str:
        try:
            return os.path.normcase(os.path.abspath(p or ""))
        except Exception:
            return p or ""

    # 1) Best case: it's importable AND it's our local Helper/dimensioning.py
    try:
        import Helper.dimensioning as _dim_mod  # type: ignore

        dd = getattr(_dim_mod, "DimensionDrawer", None)
        mod_file = getattr(_dim_mod, "__file__", "") or ""
        expected_dir = os.path.join(_THIS_DIR, "Helper")
        if dd is not None and _norm(mod_file).startswith(_norm(expected_dir)):
            return dd
    except Exception:
        pass

    # 2) Fallback: load from explicit file path (avoids `Helper` name collisions)
    dim_path = os.path.join(_THIS_DIR, "Helper", "dimensioning.py")
    spec = importlib.util.spec_from_file_location("_mini_autocad_dimensioning", dim_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Unable to load dimensioning module from '{dim_path}'")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so decorators (e.g., dataclass) can resolve __module__.
    # Without this, dataclasses may crash with:
    # AttributeError: 'NoneType' object has no attribute '__dict__'
    try:
        sys.modules[spec.name] = module
    except Exception:
        pass
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
    except Exception:
        # Avoid leaving a broken partially-loaded module behind.
        try:
            if sys.modules.get(spec.name) is module:
                del sys.modules[spec.name]
        except Exception:
            pass
        raise
    return getattr(module, "DimensionDrawer")


DimensionDrawer = _import_local_dimension_drawer()


def _import_local_set_window_icon():
    """
    VastuApp may already have imported a different top-level `Helper` package.
    Load MiniAutoCAD's `Helper/set_window_icon.py` via file path to avoid collisions.
    """

    def _norm(p: str) -> str:
        try:
            return os.path.normcase(os.path.abspath(p or ""))
        except Exception:
            return p or ""

    # 1) Best case: importable AND it's our local Helper/set_window_icon.py
    try:
        import Helper.set_window_icon as _swi_mod  # type: ignore

        fn = getattr(_swi_mod, "set_window_icon", None)
        mod_file = getattr(_swi_mod, "__file__", "") or ""
        expected_dir = os.path.join(_THIS_DIR, "Helper")
        if fn is not None and _norm(mod_file).startswith(_norm(expected_dir)):
            return fn
    except Exception:
        pass

    # 2) Fallback: load from explicit file path
    swi_path = os.path.join(_THIS_DIR, "Helper", "set_window_icon.py")
    spec = importlib.util.spec_from_file_location("_mini_autocad_set_window_icon", swi_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Unable to load set_window_icon module from '{swi_path}'")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
    except Exception:
        pass
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
    except Exception:
        try:
            if sys.modules.get(spec.name) is module:
                del sys.modules[spec.name]
        except Exception:
            pass
        raise
    return getattr(module, "set_window_icon")


set_window_icon = _import_local_set_window_icon()


def _import_local_door_cut_registry():
    """
    VastuApp may already have imported a different top-level `Helper` package.
    We must ensure we load MiniAutoCAD's `Helper/door_cut_registry.py`.
    """

    def _norm(p: str) -> str:
        try:
            return os.path.normcase(os.path.abspath(p or ""))
        except Exception:
            return p or ""

    # 1) Best case: importable AND it's our local Helper/door_cut_registry.py
    try:
        import Helper.door_cut_registry as _dcr_mod  # type: ignore

        cls = getattr(_dcr_mod, "DoorCutRegistry", None)
        mod_file = getattr(_dcr_mod, "__file__", "") or ""
        expected_dir = os.path.join(_THIS_DIR, "Helper")
        if cls is not None and _norm(mod_file).startswith(_norm(expected_dir)):
            return cls
    except Exception:
        pass

    # 2) Fallback: load from explicit file path (avoids `Helper` namespace collisions)
    dcr_path = os.path.join(_THIS_DIR, "Helper", "door_cut_registry.py")
    spec = importlib.util.spec_from_file_location("_mini_autocad_door_cut_registry", dcr_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Unable to load door cut registry module from '{dcr_path}'")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
    except Exception:
        pass
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
    except Exception:
        try:
            if sys.modules.get(spec.name) is module:
                del sys.modules[spec.name]
        except Exception:
            pass
        raise
    return getattr(module, "DoorCutRegistry")


DoorCutRegistry = _import_local_door_cut_registry()
import json
from constraint import Problem
from functools import partial
from furniture_suggestor import FurnitureSuggester  
from vastu_geometry import VastuPolygonGenerator

VASTU_DIRECTIONS = {
    "N":   (337.5, 22.5),
    "NNE": (22.5, 45),
    "NE":  (45, 67.5),
    "ENE": (67.5, 90),
    "E":   (90, 112.5),
    "ESE": (112.5, 135),
    "SE":  (135, 157.5),
    "SSE": (157.5, 180),
    "S":   (180, 202.5),
    "SSW": (202.5, 225),
    "SW":  (225, 247.5),
    "WSW": (247.5, 270),
    "W":   (270, 292.5),
    "WNW": (292.5, 315),
    "NW":  (315, 337.5)
}

def angle_from_center(cx, cy, x, y):
    import math
    dx = x - cx
    dy = cy - y
    angle = math.degrees(math.atan2(dx, dy)) % 360
    return angle

def get_vastu_direction(angle):
    for direction, (start, end) in VASTU_DIRECTIONS.items():
        if start < end:
            if start <= angle < end:
                return direction
        else:
            if angle >= start or angle < end:
                return direction
    return "Unknown"


from Helper.guideline_helper import GuidelineHelper


    


class CanvasTools:
    def __init__(self, root, model, view, actions):
        self.root = root
        self.model = model
        self.view = view
        self.canvas = view.canvas
        self.actions = actions
        self.first_point = None
        self.current_line_label = None
        self.current_preview = None
        self.polygon_points = []
        self.current_preview = None
        self.polygon_preview_line = None  # Temporary line from last point to mouse cursor
        self._active_polygon_group_tag = None
        self.vastu_preview_polygon = None
        self.vastu_preview_line = None
        self.fill_color = "#cccccc"
        self.temp_entry = None
        self.temp_direction = None
        self.temp_origin = None
        self.unit_scale = model.unit_scale
        self.freeform_points = []
        self.image_furniture_items = []
        self.selected_furniture_obj = None
        self.layout_move_mode = False
        self._entire_layout_tag = None
        self._entire_layout_outline_id = None
        self._entire_layout_state_scope = None
        self.line_metadata = {}  # Store line metadata for edit/duplicate
        self.flooring_enabled = False
        self.flooring_image_path = ""
        self.flooring_type_var = tk.StringVar(value="wood")
        # If True, clicking a room/polygon will REMOVE flooring instead of applying it.
        self.flooring_remove_mode = False
        self.room_flooring_images = {}
        self._flooring_rescale_id = None
        self.window_mode = False
        self.windows = []
        self.selected_window = None
        self.paste_ready = False
        self.group_id_counter = 1
        self.coord_label = None
        self.canvas_frozen = False
        self.copied_item_data = None
        self.group_id_counter = 1000  # for generating new room group tags
        self.furniture_objects = []  # Define once here
        self.room_entities_by_group_tag = {} # New: To store RoomEntity instances
        self.polygon_rooms_map = {}  # Map polygon_group_tag -> list of room group_tags
        self.selection_rectangle_id = None
        # Multi‑wall erase (selection rectangle)
        self._multi_erase_start = None
        self._multi_erase_rect_id = None
        # Region screenshot helpers
        self._screenshot_start = None
        self._screenshot_rect_id = None
        self._screenshot_bind_ids = {}
        # Wall erase helpers (two‑point erase)
        self._wall_erase_first_point = None
        self._wall_erase_preview_id = None
        # In CanvasTools __init__
        self.measure_points = []
        self.temp_measure_items = []
        # Door wall-cut recompute (dynamic cutting when doors move)
        self._door_recut_after_id = None
        self._recomputing_door_cuts = False
        # Room outline multi-cut registry (supports 2+ doors on same wall)
        self._door_cut_registry = DoorCutRegistry()
        # polygon_group_tag -> baseline polygon coords (pre-door-cut), as flat list [x0,y0,x1,y1,...]
        self._polygon_baseline_coords_by_group = {}
        # Vastu: user-defined North direction in ANTI-CLOCKWISE degrees.
        # North direction (canvas: anti-clockwise from up). 270° = right = North per app convention.
        self.vastu_north_deg = 270.0
        # Guidelines helper for polygon creation
        self.guideline_helper = GuidelineHelper(self.canvas, self.model)

        # Auto-dimension helper (engineering-style arrow dimensions)
        self.dimension_drawer = DimensionDrawer(self.canvas, self.model)
        self.polygon_label_placer = PolygonLabelPlacer(self.canvas)
        self._polygon_label_serial = 0

        # Vastu slice baseline (for reset after user drags individual zones)
        self._vastu_zone_baseline_by_item = {}

        self._overlay_tooltip = None

        # Room editing state
        self.currently_editing_room_tag = None
        self.room_widgets = {}

        # Trace Image Manager
        try:
            from Helper.trace_manager import TraceImageManager
            self.trace_manager = TraceImageManager(self)
        except Exception as e:
            print(f"[TraceImageManager] Import failed: {e}")
            self.trace_manager = None

    def on_zoom_changed(self, scale_factor: float) -> None:
        """
        Keep in-memory geometry state consistent with `canvas.scale("all", 0, 0, ...)`.

        Tk canvas items are scaled by `CanvasView.apply_zoom()`, but our stored point lists
        (`polygon_points`, `first_point`, `line_metadata` endpoints, etc.) are just Python
        data and must be scaled too; otherwise distance/snap calculations will mix old
        and new coordinate spaces after the next zoom/pan/auto-pan step.
        """
        try:
            sf = float(scale_factor)
        except Exception:
            return

        if abs(sf - 1.0) < 1e-12:
            return

        def _scale_point(p):
            try:
                return (float(p[0]) * sf, float(p[1]) * sf)
            except Exception:
                return p

        # Active drawing state
        if hasattr(self, "polygon_points") and isinstance(self.polygon_points, list):
            self.polygon_points = [_scale_point(p) for p in self.polygon_points]
        if hasattr(self, "vastu_polygon_points") and isinstance(self.vastu_polygon_points, list):
            self.vastu_polygon_points = [_scale_point(p) for p in self.vastu_polygon_points]
        if hasattr(self, "freeform_points") and isinstance(self.freeform_points, list):
            self.freeform_points = [_scale_point(p) for p in self.freeform_points]

        if getattr(self, "first_point", None):
            self.first_point = _scale_point(self.first_point)
        if getattr(self, "temp_origin", None):
            self.temp_origin = _scale_point(self.temp_origin)

        # Two-point wall eraser preview anchor
        if getattr(self, "_wall_erase_first_point", None):
            self._wall_erase_first_point = _scale_point(self._wall_erase_first_point)

        # Multi-erase start anchor
        if getattr(self, "_multi_erase_start", None):
            self._multi_erase_start = _scale_point(self._multi_erase_start)

        # Line editing endpoints stored for later recomputation
        if hasattr(self, "line_metadata") and isinstance(self.line_metadata, dict):
            for meta in self.line_metadata.values():
                try:
                    if "x0" in meta:
                        meta["x0"] = float(meta["x0"]) * sf
                    if "y0" in meta:
                        meta["y0"] = float(meta["y0"]) * sf
                    if "x1" in meta:
                        meta["x1"] = float(meta["x1"]) * sf
                    if "y1" in meta:
                        meta["y1"] = float(meta["y1"]) * sf
                except Exception:
                    continue

        # Baseline coordinates used for door recuts (best-effort)
        if hasattr(self, "_polygon_baseline_coords_by_group") and isinstance(
            self._polygon_baseline_coords_by_group, dict
        ):
            try:
                for k, flat in list(self._polygon_baseline_coords_by_group.items()):
                    if isinstance(flat, list):
                        self._polygon_baseline_coords_by_group[k] = [float(v) * sf for v in flat]
            except Exception:
                pass

        # Snap-direction hysteresis can become stale across zoom jumps.
        try:
            if hasattr(self, "guideline_helper") and hasattr(self.guideline_helper, "_grid_snap_last_coord"):
                self.guideline_helper._grid_snap_last_coord = {"x": None, "y": None}
        except Exception:
            pass

        # Scale snapping tolerances (world-unit stable snapping).
        try:
            if hasattr(self, "guideline_helper") and hasattr(self.guideline_helper, "on_zoom_changed"):
                self.guideline_helper.on_zoom_changed(sf)
        except Exception:
            pass

    def _event_to_canvas_coords(self, event: tk.Event) -> tuple[float, float]:
        """
        Convert a Tk event's widget pixel coordinates to canvas/world coordinates.

        It is critical that drawing tools store endpoints in *canvas coordinates*
        (via `canvas.canvasx/canvasy`) so they remain stable while scrolling or
        when auto-pan extends the scrollregion.
        """
        try:
            return float(self.canvas.canvasx(event.x)), float(self.canvas.canvasy(event.y))
        except Exception:
            # Best-effort fallback if conversion fails for some reason.
            return float(getattr(event, "x", 0.0)), float(getattr(event, "y", 0.0))

    def _record_manual_wall_erase(self, room_entity, wall_side: str, start: float, end: float) -> None:
        """
        Track user-initiated wall erasures for walls_only rooms so they persist across door recuts.
        """
        try:
            if getattr(room_entity, "fill_mode", "") != "walls_only":
                return
            try:
                regions = getattr(room_entity, "_manual_wall_erased_regions", None)
            except Exception:
                regions = None
            if regions is None:
                regions = {}
                try:
                    setattr(room_entity, "_manual_wall_erased_regions", regions)
                except Exception:
                    return
            zoom = self.model.zoom_level
            a, b = float(start) / zoom, float(end) / zoom
            if a > b:
                a, b = b, a
            side_list = list(regions.get(wall_side) or [])
            side_list.append([a, b])
            # Merge overlapping / adjacent intervals with small tolerance
            eps = 1.0
            side_list = sorted(side_list, key=lambda iv: iv[0])
            merged: list[list[float]] = []
            for s, e in side_list:
                if not merged:
                    merged.append([s, e])
                else:
                    last = merged[-1]
                    if s <= last[1] + eps:
                        last[1] = max(last[1], e)
                    else:
                        merged.append([s, e])
            regions[wall_side] = merged
        except Exception:
            pass
    def has_walls_only_room(self) -> bool:
        """
        Return True if there is at least one room with fill_mode == 'walls_only'.
        Used by toolbar to enable/disable wall eraser buttons.
        """
        try:
            rooms = getattr(self, "room_entities_by_group_tag", {}) or {}
        except Exception:
            rooms = {}
        try:
            for room in rooms.values():
                try:
                    if getattr(room, "fill_mode", "") == "walls_only":
                        return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    # ---------------- Flooring helpers ----------------
    def _get_item_floor_style(self, item_id: int) -> dict:
        """Capture minimal style we need to restore after flooring removal."""
        style: dict = {"fill": "", "stipple": ""}
        try:
            style["fill"] = self.canvas.itemcget(item_id, "fill") or ""
        except Exception:
            style["fill"] = ""
        try:
            # Tk canvas supports 'stipple' for simulated transparency patterns
            style["stipple"] = self.canvas.itemcget(item_id, "stipple") or ""
        except Exception:
            style["stipple"] = ""
        return style

    def _apply_item_floor_style(self, item_id: int, style: dict | None) -> None:
        if not style:
            return
        try:
            self.canvas.itemconfig(
                item_id,
                fill=style.get("fill", ""),
                stipple=style.get("stipple", ""),
            )
        except Exception:
            # Some platforms / item types may not support stipple; fall back to fill-only.
            try:
                self.canvas.itemconfig(item_id, fill=style.get("fill", ""))
            except Exception:
                pass

    def _remove_flooring_for_owner(self, owner_id: int, *, group_tag: str | None = None) -> dict | None:
        """
        Remove flooring image/border for a room-rect or polygon.
        Returns an 'old_payload' compatible with ActionManager flooring_apply.
        """
        old_data = self.room_flooring_images.get(owner_id) or {}
        image_id = old_data.get("image_id")
        border_id = old_data.get("border_id")

        # Delete known items first
        try:
            if image_id:
                self.canvas.delete(image_id)
        except Exception:
            pass
        try:
            if border_id:
                self.canvas.delete(border_id)
        except Exception:
            pass

        # Best-effort fallback: delete tagged flooring items for this group
        if not image_id and group_tag:
            try:
                for it in list(self.canvas.find_withtag("flooring")):
                    tags = self.canvas.gettags(it)
                    if group_tag in tags:
                        try:
                            self.canvas.delete(it)
                        except Exception:
                            pass
            except Exception:
                pass
        if not border_id and group_tag:
            try:
                for it in list(self.canvas.find_withtag("flooring_border")):
                    tags = self.canvas.gettags(it)
                    if group_tag in tags:
                        try:
                            self.canvas.delete(it)
                        except Exception:
                            pass
            except Exception:
                pass

        # Remove registry entry
        try:
            self.room_flooring_images.pop(owner_id, None)
        except Exception:
            pass

        # Build undo payload (if we had anything)
        if old_data.get("image_path"):
            payload = {
                "kind": old_data.get("kind") or "polygon",
                "image_id": image_id,
                "border_id": border_id,
                "image_path": old_data.get("image_path"),
                "group_tag": old_data.get("group_tag") or group_tag,
            }
            # Keep any saved original style (used when removing flooring)
            if "owner_original_style" in old_data:
                payload["owner_original_style"] = old_data.get("owner_original_style")
            # Best-effort coords for undo recreation
            try:
                if payload["kind"] == "room":
                    payload["room_bbox"] = old_data.get("room_bbox")
                else:
                    payload["polygon_coords"] = old_data.get("polygon_coords")
            except Exception:
                pass
            return payload

        return None

    def create_tooltip(self, widget, text):
        if not hasattr(self, "_overlay_tooltip"):
            self._overlay_tooltip = None

        try:
            from Helper.ctk_global import ctk
        except Exception:
            ctk = None

        def enter(event):
            try:
                if not ctk:
                    return
                if self._overlay_tooltip is None or not self._overlay_tooltip.winfo_exists():
                    self._overlay_tooltip = ctk.CTkLabel(
                        self.root,
                        text=text,
                        fg_color="#333",
                        text_color="white",
                    )
                else:
                    self._overlay_tooltip.configure(text=text)

                self._overlay_tooltip.update_idletasks()

                scale = 1.0
                try:
                    scale = float(self.root.tk.call("tk", "scaling"))
                    if scale <= 0:
                        scale = 1.0
                except Exception:
                    scale = 1.0

                root_abs_y = self.root.winfo_rooty()
                root_height = self.root.winfo_height()
                tip_height = self._overlay_tooltip.winfo_height()

                abs_x = widget.winfo_rootx() - 40
                abs_y = widget.winfo_rooty() + widget.winfo_height() + 2

                if abs_y + tip_height > root_abs_y + root_height:
                    abs_y = widget.winfo_rooty() - tip_height - 4

                rel_x = abs_x - self.root.winfo_rootx()
                rel_y = abs_y - root_abs_y

                # Convert screen-pixel delta to Tk logical coordinates when scaling is active.
                rel_x = rel_x / scale
                rel_y = rel_y / scale

                if rel_x < 0:
                    rel_x = 0
                if rel_y < 0:
                    rel_y = 0

                self._overlay_tooltip.place(x=int(rel_x), y=int(rel_y))
            except Exception:
                pass

        def leave(event):
            try:
                if self._overlay_tooltip is not None and self._overlay_tooltip.winfo_exists():
                    self._overlay_tooltip.place_forget()
            except Exception:
                pass

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def _ask_vastu_north_deg(self, default_deg: float = 0.0) -> float:
        """
        Ask user where North is, in ANTI-CLOCKWISE degrees:
        0 = up, 90 = left, 180 = down, 270 = right.
        """
        # Preferred: custom Toplevel dialog so we can apply app icon.
        # IMPORTANT: Load via file path to avoid `Helper` namespace collisions with the
        # main app (there is also a top-level `Helper/` folder).
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            dlg_path = os.path.join(base_dir, "Helper", "vastu_north_dialog.py")
            if os.path.isfile(dlg_path):
                spec = importlib.util.spec_from_file_location("_mini_autocad_vastu_north_dialog", dlg_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    # IMPORTANT: register before exec_module so dataclasses/typing can resolve
                    # module globals via sys.modules[__name__].__dict__ during class creation.
                    try:
                        sys.modules[spec.name] = module
                    except Exception:
                        pass
                    spec.loader.exec_module(module)  # type: ignore[attr-defined]
                    VastuNorthAngleDialog = getattr(module, "VastuNorthAngleDialog", None)
                    if VastuNorthAngleDialog:
                        dlg = VastuNorthAngleDialog(self.root, initial_angle=float(default_deg) % 360.0)
                        res = dlg.show()
                        if res is None:
                            return float(default_deg) % 360.0
                        return float(res.angle_deg_anticlockwise) % 360.0
        except Exception as e:
            # Fallback to simpledialog if something goes wrong
            try:
                print(f"[MiniAutoCAD][Vastu] Falling back to simple dialog (north angle): {e}")
            except Exception:
                pass

        try:
            val = simpledialog.askfloat(
                "Vastu: North Direction",
                "Enter North direction angle (degrees):\n\n"
                "N(↑)"
                "0 = Up, 90 = Left, 180 = Down, 270 = Right",
                parent=self.root,
                initialvalue=float(default_deg) % 360.0,
                minvalue=0.0,
                maxvalue=359.999,
            )
        except Exception:
            val = None
        if val is None:
            return float(default_deg) % 360.0
        return float(val) % 360.0

    def _draw_vastu_north_marker(self, center_x: float, center_y: float, north_deg: float) -> None:
        """Draw a small arrow showing chosen North direction inside polygon."""
        try:
            self.canvas.delete("vastu_north_marker")
        except Exception:
            pass

        # User gives anti-clockwise degrees; geometry expects compass degrees (clockwise).
        north_compass = (-float(north_deg)) % 360.0
        vx, vy = VastuPolygonGenerator.angle_to_unit_vector(north_compass)
        length = 70.0
        x2 = center_x + vx * length
        y2 = center_y + vy * length

        try:
            self.canvas.create_line(
                center_x,
                center_y,
                x2,
                y2,
                arrow=tk.LAST,
                width=2,
                fill="red",
                tags=("vastu_north_marker", "vastu_group"),
            )
            self.canvas.create_text(
                x2,
                y2,
                text="N",
                font=("Arial", 10, "bold"),
                fill="red",
                anchor="sw",
                tags=("vastu_north_marker", "vastu_group"),
            )
        except Exception:
            pass

    def _new_polygon_group_tag(self) -> str:
        return f"polygon_group_{uuid.uuid4().hex[:10]}"

    def _merge_item_tags(self, item_id: int, extra_tags: tuple[str, ...]) -> None:
        existing = set(self.canvas.gettags(item_id))
        existing.update(extra_tags)
        self.canvas.itemconfig(item_id, tags=tuple(existing))

    def _remove_group_tags(self, item_id: int) -> None:
        """Remove room_group_* and polygon_group_* tags from a canvas item."""
        try:
            tags = set(self.canvas.gettags(item_id))
        except Exception:
            return
        new_tags = tuple(t for t in tags if not (t.startswith("room_group_") or t.startswith("polygon_group_")))
        try:
            self.canvas.itemconfig(item_id, tags=new_tags)
        except Exception:
            pass

    def enter_furniture_edit_mode(self, furniture_obj) -> bool:
        """
        Detach a committed furniture from its polygon/room group so user can edit/resize it.
        Triggered via right-click on the furniture.
        """
        if not furniture_obj or not hasattr(furniture_obj, "image_id"):
            return False

        # Remove group tags from image and any existing handles
        self._remove_group_tags(furniture_obj.image_id)
        for hid in list(getattr(furniture_obj, "handles", []) or []):
            self._remove_group_tags(hid)

        # Mark editable
        try:
            furniture_obj.committed = False
            furniture_obj.editing = True
        except Exception:
            pass

        # Show handles for editing
        try:
            furniture_obj.draw_handles()
            furniture_obj.draw_highlight()
        except Exception:
            pass

        try:
            print("✏️ Furniture edit mode enabled (right-click). Press Enter to commit again.")
        except Exception:
            pass
        return True

    def duplicate_furniture(self, furniture_obj) -> bool:
        """Duplicate a furniture item near its current position (starts in edit mode, not committed)."""
        if not furniture_obj or not hasattr(furniture_obj, "image_id"):
            return False
        try:
            x, y = furniture_obj.get_position()
        except Exception:
            return False
        try:
            new_x, new_y = float(x) + 30.0, float(y) + 30.0
        except Exception:
            new_x, new_y = x, y

        try:
            # Copy all properties from original furniture
            original_scale = getattr(furniture_obj, "scale", 1.0)
            original_angle = getattr(furniture_obj, "angle", 0)
            original_target_size = getattr(furniture_obj, "target_size", None)
            original_real_size_ft = getattr(furniture_obj, "real_size_ft", None)
            original_model_ref = getattr(furniture_obj, "model_ref", None)
            original_image = getattr(furniture_obj, "original_image", None)
            
            new_obj = Furniture(
                canvas=self.canvas,
                image_path=furniture_obj.image_path,
                x=new_x,
                y=new_y,
                select_callback=self.select_image_item,
                scale=original_scale,
                angle=original_angle,
                get_freeze_state=self.get_canvas_freeze_state,
                edit_callback=self.enter_furniture_edit_mode,
                duplicate_callback=self.duplicate_furniture,
                delete_callback=self.delete_furniture_item,
                target_size=original_target_size,
            )

            try:
                if original_image is not None:
                    new_obj.original_image = original_image.copy()
                    new_obj.update_image()
                    self.canvas.itemconfig(new_obj.image_id, image=new_obj.tk_image)
            except Exception as e:
                print(f"[DEBUG] Warning: Could not copy original_image for duplicate: {e}")
            
            # Ensure it's editable by default
            try:
                new_obj.committed = False
                new_obj.editing = True
            except Exception:
                pass
            
            new_obj.real_size_ft = original_real_size_ft
            new_obj.model_ref = original_model_ref or self.model
            self.image_furniture_items.append(new_obj)
            self.select_image_item(new_obj)
            self.actions.log({
                "type": "create_furniture",
                "image_id": new_obj.image_id,
                "image_path": new_obj.image_path,
                "x": new_x,
                "y": new_y,
                "scale": new_obj.scale,
                "angle": new_obj.angle,
                "initial_angle": new_obj.initial_angle,
                "real_size_ft": new_obj.real_size_ft,
                "target_size": new_obj.target_size,
            })
            
            # If it's a door, cut wall for the duplicate
            if getattr(furniture_obj, "is_door", False) and original_real_size_ft:
                try:
                    real_w_ft, real_h_ft = original_real_size_ft
                    self._cut_wall_for_door(new_obj, real_w_ft, real_h_ft)
                    # Ensure furniture (door) stays on top after wall cutting
                    try:
                        self.canvas.tag_raise(new_obj.image_id)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"[DEBUG] Error cutting wall for duplicated door: {e}")
            
            return True
        except Exception:
            return False

    def delete_furniture_item(self, furniture_obj) -> bool:
        """Delete furniture item from canvas and internal registries."""
        if not furniture_obj:
            return False
        was_door = False
        try:
            was_door = self._is_door_furniture(furniture_obj)
        except Exception:
            was_door = False
        try:
            x, y = furniture_obj.get_position()
            self.actions.log({
                "type": "delete_furniture",
                "image_id": furniture_obj.image_id,
                "image_path": furniture_obj.image_path,
                "x": x,
                "y": y,
                "scale": getattr(furniture_obj, "scale", 1.0),
                "angle": getattr(furniture_obj, "angle", 0),
                "initial_angle": getattr(furniture_obj, "initial_angle", getattr(furniture_obj, "angle", 0)),
                "real_size_ft": getattr(furniture_obj, "real_size_ft", None),
                "target_size": getattr(furniture_obj, "target_size", None),
            })
        except Exception:
            pass
        try:
            furniture_obj.delete_handles()
        except Exception:
            pass
        try:
            furniture_obj.delete()
        except Exception:
            # Fallback: delete just the image_id if delete() fails
            try:
                if hasattr(furniture_obj, "image_id"):
                    self.canvas.delete(furniture_obj.image_id)
            except Exception:
                pass
        try:
            if furniture_obj in self.image_furniture_items:
                self.image_furniture_items.remove(furniture_obj)
        except Exception:
            pass
        if getattr(self, "selected_furniture_obj", None) == furniture_obj:
            self.selected_furniture_obj = None
        # If a door was deleted, restore walls by recomputing all door cuts.
        if was_door:
            try:
                self.schedule_recompute_door_cuts(delay_ms=30)
            except Exception:
                pass
        return True

    def auto_commit_uncommitted_furniture(self) -> None:
        """
        Auto-commit any uncommitted furniture items before placing a new one.
        This ensures only one furniture item is in edit mode at a time.
        """
        for furniture_item in self.image_furniture_items:
            if furniture_item and not getattr(furniture_item, "committed", False):
                # Try to commit to underlying group if possible
                try:
                    self.commit_furniture_to_underlying_group(furniture_item)
                except Exception:
                    # If commit fails (no underlying group), just mark as committed anyway
                    # so it doesn't interfere with new placement
                    try:
                        furniture_item.committed = True
                        furniture_item.editing = False
                        furniture_item.delete_handles()
                    except Exception:
                        pass

    def commit_furniture_to_underlying_group(self, furniture_obj) -> bool:
        """
        Commit a furniture item to the underlying polygon/room group by adding the same group tag
        to the furniture image + its resize handles.

        After commit: dragging the polygon/room moves furniture with it (group drag).
        """
        if not furniture_obj or not hasattr(furniture_obj, "image_id"):
            return False

        try:
            x, y = furniture_obj.get_position()
        except Exception:
            return False

        # Find any group under the furniture center.
        # Collect both polygon and room groups so furniture can follow either.
        items = self.canvas.find_overlapping(x - 3, y - 3, x + 3, y + 3)
        if not items:
            return False

        polygon_group_tag = None
        room_group_tag = None

        for item in reversed(items):
            try:
                tags = self.canvas.gettags(item)
            except Exception:
                continue

            if polygon_group_tag is None and any(t.startswith("polygon_group_") for t in tags):
                polygon_group_tag = next((t for t in tags if t.startswith("polygon_group_")), None)

            if room_group_tag is None and any(t.startswith("room_group_") for t in tags):
                room_group_tag = next((t for t in tags if t.startswith("room_group_")), None)

            if polygon_group_tag and room_group_tag:
                break

        # If we have no explicit polygon_group_* yet, but there is a legacy polygon,
        # retro-tag it so future drags work consistently.
        if polygon_group_tag is None:
            for item in reversed(items):
                try:
                    tags = self.canvas.gettags(item)
                except Exception:
                    continue
                if self.canvas.type(item) == "polygon" and "closed_shape" in tags:
                    try:
                        polygon_group_tag = self.ensure_polygon_grouping(item)
                    except Exception:
                        polygon_group_tag = None
                    break

        # Primary group for committed furniture:
        # - If a room is present, prefer the room group so moving the room moves furniture.
        # - Otherwise, fall back to polygon group (plot-only layouts).
        primary_group_tag = room_group_tag or polygon_group_tag
        if not primary_group_tag:
            return False

        # Merge group tag onto furniture image (handles are removed in committed/locked mode)
        try:
            extra_tags = tuple(
                t for t in (room_group_tag, polygon_group_tag, "furniture_committed") if t
            )
            self._merge_item_tags(furniture_obj.image_id, extra_tags)
        except Exception:
            try:
                existing = set(self.canvas.gettags(furniture_obj.image_id))
                to_add = {t for t in (room_group_tag, polygon_group_tag, "furniture_committed") if t}
                self.canvas.itemconfig(furniture_obj.image_id, tags=tuple(existing | to_add))
            except Exception:
                return False

        # Lock after commit: hide handles so resize can't accidentally drag the polygon group
        try:
            furniture_obj.committed = True
            furniture_obj.editing = False
            furniture_obj.committed_group_tag = primary_group_tag
        except Exception:
            pass
        try:
            furniture_obj.delete_handles()
            if furniture_obj == getattr(self, "selected_furniture_obj", None):
                furniture_obj.draw_highlight()
        except Exception:
            pass

        try:
            print(f"✅ Furniture committed to group: {primary_group_tag or polygon_group_tag}")
        except Exception:
            pass
        return True

    def ensure_polygon_grouping(self, polygon_id: int) -> str:
        """
        Ensure a polygon (and any nearby vertex markers / label) share a polygon_group_* tag.
        This is primarily to support polygons created before grouping was implemented.
        """
        tags = self.canvas.gettags(polygon_id)
        existing_group = next((t for t in tags if t.startswith("polygon_group_")), None)
        if existing_group:
            return existing_group

        group_tag = self._new_polygon_group_tag()
        self._merge_item_tags(polygon_id, (group_tag, "polygon_shape"))

        coords = self.canvas.coords(polygon_id)
        vertices = list(zip(coords[0::2], coords[1::2]))

        # Tag small green ovals near each vertex as vertex markers
        for vx, vy in vertices:
            near = self.canvas.find_overlapping(vx - 4, vy - 4, vx + 4, vy + 4)
            for item in near:
                if item == polygon_id:
                    continue
                if self.canvas.type(item) != "oval":
                    continue
                try:
                    fill = self.canvas.itemcget(item, "fill")
                except Exception:
                    continue
                if fill != "green":
                    continue
                bbox = self.canvas.bbox(item)
                if not bbox:
                    continue
                x0, y0, x1, y1 = bbox
                if (x1 - x0) > 12 or (y1 - y0) > 12:
                    continue
                self._merge_item_tags(item, (group_tag, "polygon_vertex"))

        # Tag nearby area/perimeter label (if present). If multiple labels overlap,
        # pick the closest matching label to the polygon centroid.
        if vertices:
            cx = sum(x for x, _ in vertices) / len(vertices)
            cy = sum(y for _, y in vertices) / len(vertices)

            xs = [x for x, _ in vertices]
            ys = [y for _, y in vertices]
            pad = 80
            near = self.canvas.find_overlapping(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

            best_item = None
            best_dist2 = None
            for item in near:
                if self.canvas.type(item) != "text":
                    continue
                txt = self.canvas.itemcget(item, "text")
                if not (isinstance(txt, str) and txt.strip().startswith("Area")):
                    continue
                bbox = self.canvas.bbox(item)
                if not bbox or len(bbox) != 4:
                    continue
                ix = (float(bbox[0]) + float(bbox[2])) / 2.0
                iy = (float(bbox[1]) + float(bbox[3])) / 2.0
                d2 = (ix - float(cx)) ** 2 + (iy - float(cy)) ** 2
                if best_dist2 is None or d2 < best_dist2:
                    best_dist2 = d2
                    best_item = item

            if best_item is not None:
                self._merge_item_tags(best_item, (group_tag, "polygon_label"))

        return group_tag

    # === Line Drawing ===
    def start_line(self, event):
        # Safety check: if drawing is not enabled, don't process
        if not self.model.get("drawing_enabled"):
            # Clean up any stray temp_entry
            if self.temp_entry:
                try:
                    self.temp_entry.destroy()
                except:
                    pass
                self.temp_entry = None
            return
        
        # Store and measure using canvas coordinates (not widget coords), then use the
        # same endpoint/midpoint/perpendicular/grid snap engine as polygon tools.
        x, y = self._event_to_canvas_coords(event)
        try:
            points = [self.first_point] if self.first_point else []
            x, y, _ = self.guideline_helper.get_snap_point(x, y, points, snap_to_existing=True)
        except Exception:
            pass

        # IMPORTANT: Clean up any existing temp_entry before starting new line
        if self.temp_entry:
            try:
                self.temp_entry.destroy()
            except:
                pass
            self.temp_entry = None

        if not self.first_point:
            self.first_point = (x, y)

            # Create small black point
            point_id = self.canvas.create_oval(x - 0.5, y - 0.5, x + 0.5, y + 0.5, fill="black")
            self.actions.log({"type": "create", "items": [point_id]})
        else:
            x0, y0 = self.first_point
            x1, y1 = x, y
            dx = x1 - x0
            dy = y1 - y0
            mouse_length = math.hypot(dx, dy)

            if mouse_length > 0:
                # Calculate distance in real-world units from the two clicked points
                # Convert pixel distance to real-world units (same formula as get_distance_label)
                adjusted_pixel_length = mouse_length / self.model.zoom_level
                unit_scale = self.model.unit_scale.get(self.model.unit, 1.0)
                real_length = (adjusted_pixel_length / self.model.grid_spacing) * unit_scale
                calculated_distance = real_length

                # Create line directly without input field - use calculated distance
                self._create_line_from_distance(x0, y0, x1, y1, calculated_distance)

                # Freeform closed-shape support
                self.freeform_points.append((x0, y0))
                self.freeform_points.append((x1, y1))

                if (
                    len(self.freeform_points) >= 3 and
                    math.dist(self.freeform_points[0], self.freeform_points[-1]) < 10
                ):
                    # Build closed polygon
                    polygon_points = [self.freeform_points[0]]
                    for pt in self.freeform_points[1:]:
                        if math.dist(pt, polygon_points[-1]) > 1:
                            polygon_points.append(pt)

                    flat = [coord for pt in polygon_points for coord in pt]

                    # Apply current line style (solid / bold / dashed) to closed shape outline
                    style = getattr(self.model, "line_style", "solid")
                    poly_width = 4 if style == "bold" else 2
                    poly_dash = (4, 2) if style == "dashed" else None

                    polygon_id = self.canvas.create_polygon(
                        flat,
                        outline=self.model.line_color,
                        fill=self.model.fill_color,
                        width=poly_width,
                        dash=poly_dash,
                        tags=("closed_shape",),
                    )
                    self.actions.log({"type": "create", "items": [polygon_id]})
                    self.freeform_points.clear()
                    self.model.fill_color = ""

             # Line is already created by _create_line_from_distance, so just clean up preview
            if self.current_preview:
                self.canvas.delete(self.current_preview)
                self.current_preview = None

            if self.current_line_label:
                self.canvas.delete(self.current_line_label)
                self.current_line_label = None

    def update_line_preview(self, event) -> None:
        """
        Live preview for the line tool: from first click to current mouse
        position, with real‑time distance label and current line_style.
        """
        if not self.first_point:
            return

        x0, y0 = self.first_point
        x1, y1 = self._event_to_canvas_coords(event)
        try:
            x1, y1, _ = self.guideline_helper.get_snap_point(
                x1, y1, [self.first_point], snap_to_existing=True
            )
        except Exception:
            pass

        # Style based on model.line_style
        style = getattr(self.model, "line_style", "solid")
        width = 4 if style == "bold" else 2
        dash = (4, 2) if style == "dashed" else None
        arrow = getattr(self.model, "line_arrow", "none")

        # Preview line
        try:
            if self.current_preview and self.canvas.type(self.current_preview) == "line":
                self.canvas.coords(self.current_preview, x0, y0, x1, y1)
                self.canvas.itemconfig(
                    self.current_preview,
                    fill=self.model.line_color,
                    width=width,
                    dash=dash,
                    arrow=arrow,
                )
            else:
                if self.current_preview:
                    try:
                        self.canvas.delete(self.current_preview)
                    except Exception:
                        pass
                    self.current_preview = None
                self.current_preview = self.canvas.create_line(
                    x0,
                    y0,
                    x1,
                    y1,
                    fill=self.model.line_color,
                    width=width,
                    dash=dash,
                    arrow=arrow,
                    tags=("active_preview",),
                )
        except Exception:
            pass

        # Distance label near the middle of the preview line
        try:
            label_text, mx, my = get_distance_label(
                x0, y0, x1, y1, self.model.unit, self.model.zoom_level
            )
            if self.current_line_label:
                self.canvas.coords(self.current_line_label, mx, my - 10)
                self.canvas.itemconfig(
                    self.current_line_label,
                    text=label_text,
                    fill="red",
                    font=("Arial", 9, "bold"),
                )
            else:
                self.current_line_label = self.canvas.create_text(
                    mx,
                    my - 10,
                    text=label_text,
                    font=("Arial", 9, "bold"),
                    fill="red",
                    tags=("active_preview",),
                )
        except Exception:
            pass

    def _cancel_line_input(self, event=None):
        """Cancel line input and clean up all preview states to prevent traces."""
        if self.temp_entry:
            try:
                self.temp_entry.destroy()
            except Exception:
                pass
            self.temp_entry = None
        self.first_point = None
        self.temp_direction = None
        self.temp_origin = None
        if self.current_preview:
            try:
                self.canvas.delete(self.current_preview)
            except Exception:
                pass
            self.current_preview = None
        if self.current_line_label:
            try:
                self.canvas.delete(self.current_line_label)
            except Exception:
                pass
            self.current_line_label = None
        # Clear polygon preview line
        if getattr(self, "polygon_preview_line", None):
            try:
                self.canvas.delete(self.polygon_preview_line)
            except Exception:
                pass
            self.polygon_preview_line = None
        # Clear vastu preview line/polygon
        if getattr(self, "vastu_preview_line", None):
            try:
                self.canvas.delete(self.vastu_preview_line)
            except Exception:
                pass
            self.vastu_preview_line = None
        if getattr(self, "vastu_preview_polygon", None):
            try:
                self.canvas.delete(self.vastu_preview_polygon)
            except Exception:
                pass
            self.vastu_preview_polygon = None
        # Clear guideline overlays
        try:
            if hasattr(self, "guideline_helper"):
                self.guideline_helper.clear_guides()
        except Exception:
            pass
        # Delete any orphaned preview items by tag (fallback if refs were lost)
        for tag in ("polygon_preview_line", "vastu_preview_line", "vastu_polygon_temp"):
            try:
                self.canvas.delete(tag)
            except Exception:
                pass

    def _create_line_from_distance(self, x0, y0, x1, y1, distance):
        """Create a line directly from two points and a distance value (no input field needed)."""
        # Calculate direction vector
        dx = x1 - x0
        dy = y1 - y0
        mouse_length = math.hypot(dx, dy)
        
        if mouse_length > 0:
            direction = (dx / mouse_length, dy / mouse_length)
            unit_scale = self.model.unit_scale.get(self.model.unit, 1.0)
            pixel_length = (distance / unit_scale) * self.model.grid_spacing * self.model.zoom_level
            final_x1 = x0 + direction[0] * pixel_length
            final_y1 = y0 + direction[1] * pixel_length
        else:
            final_x1, final_y1 = x1, y1

        width = 4 if self.model.line_style == "bold" else 2
        dash = (4, 2) if self.model.line_style == "dashed" else None
        arrow = getattr(self.model, "line_arrow", "none")

        # Create line with tags for right-click editing
        import uuid
        line_tag = f"line_{uuid.uuid4().hex[:8]}"

        # If both endpoints lie inside the same polygon_group_* (or room_group_*) region,
        # attach that group tag so the line moves together with the polygon/room when dragged.
        extra_group_tags: tuple[str, ...] = ()
        try:
            hit_items_start = self.canvas.find_overlapping(x0 - 2, y0 - 2, x0 + 2, y0 + 2)
            hit_items_end = self.canvas.find_overlapping(final_x1 - 2, final_y1 - 2, final_x1 + 2, final_y1 + 2)
            common_groups = set()
            for item in hit_items_start:
                try:
                    tags = self.canvas.gettags(item)
                except Exception:
                    continue
                for t in tags:
                    if isinstance(t, str) and (t.startswith("polygon_group_") or t.startswith("room_group_")):
                        common_groups.add(t)
            if common_groups:
                end_groups = set()
                for item in hit_items_end:
                    try:
                        tags = self.canvas.gettags(item)
                    except Exception:
                        continue
                    for t in tags:
                        if isinstance(t, str) and (t.startswith("polygon_group_") or t.startswith("room_group_")):
                            end_groups.add(t)
                shared = common_groups & end_groups
                if shared:
                    # Use one stable group tag; polygons typically only have a single polygon_group_*
                    g = next(iter(shared))
                    extra_group_tags = (g,)
        except Exception:
            extra_group_tags = ()

        base_line_tags = ("line", "committed_line", line_tag)
        line_tags = base_line_tags + extra_group_tags

        line = self.canvas.create_line(
            x0,
            y0,
            final_x1,
            final_y1,
            fill=self.model.line_color,
            width=width,
            dash=dash,
            arrow=arrow,
            tags=line_tags,
        )
        # Label and point
        label_text, mid_x, mid_y = get_distance_label(
            x0, y0, final_x1, final_y1, self.model.unit, self.model.zoom_level
        )
        label_tags = ("line_label", line_tag) + extra_group_tags
        label = self.canvas.create_text(
            mid_x,
            mid_y - 10,
            text=label_text,
            font=("Arial", 8),
            fill="black",
            tags=label_tags,
        )
        point_tags = ("line_point", line_tag) + extra_group_tags
        point = self.canvas.create_oval(
            final_x1 - 0.5,
            final_y1 - 0.5,
            final_x1 + 0.5,
            final_y1 + 0.5,
            fill="black",
            tags=point_tags,
        )

        # Store line metadata for editing/duplication
        if not hasattr(self, 'line_metadata'):
            self.line_metadata = {}
        self.line_metadata[line_tag] = {
            'x0': x0, 'y0': y0, 'x1': final_x1, 'y1': final_y1,
            'width': width, 'dash': dash, 'color': self.model.line_color,
            'label': label, 'point': point
        }

        self.actions.log({
            "type": "create",
            "items": [line, label, point]
        })

        # Keep Line mode active and chain the next segment from this endpoint.
        self.first_point = (final_x1, final_y1)
        if self.current_preview:
            self.canvas.delete(self.current_preview)
            self.current_preview = None
        if self.current_line_label:
            self.canvas.delete(self.current_line_label)
            self.current_line_label = None
        if self.temp_entry:
            try:
                self.temp_entry.destroy()
            except Exception:
                pass
            self.temp_entry = None

    def finish_line_with_distance(self, event):
        try:
            dist = float(self.temp_entry.get())
        except:
            self._cancel_line_input()
            return

        dx, dy = self.temp_direction
        x0, y0 = self.temp_origin

        unit_scale = self.model.unit_scale[self.model.unit]
        pixel_length = (dist / unit_scale) * self.model.grid_spacing * self.model.zoom_level
        x1 = x0 + dx * pixel_length
        y1 = y0 + dy * pixel_length

        width = 4 if self.model.line_style == "bold" else 2
        dash = (4, 2) if self.model.line_style == "dashed" else None

        # Create line with tags for right-click editing
        import uuid
        line_tag = f"line_{uuid.uuid4().hex[:8]}"

        # If both endpoints lie inside the same polygon_group_* (or room_group_*) region,
        # attach that group tag so the line moves together with the polygon/room when dragged.
        extra_group_tags: tuple[str, ...] = ()
        try:
            hit_items_start = self.canvas.find_overlapping(x0 - 2, y0 - 2, x0 + 2, y0 + 2)
            hit_items_end = self.canvas.find_overlapping(x1 - 2, y1 - 2, x1 + 2, y1 + 2)
            common_groups = set()
            for item in hit_items_start:
                try:
                    tags = self.canvas.gettags(item)
                except Exception:
                    continue
                for t in tags:
                    if isinstance(t, str) and (t.startswith("polygon_group_") or t.startswith("room_group_")):
                        common_groups.add(t)
            if common_groups:
                end_groups = set()
                for item in hit_items_end:
                    try:
                        tags = self.canvas.gettags(item)
                    except Exception:
                        continue
                    for t in tags:
                        if isinstance(t, str) and (t.startswith("polygon_group_") or t.startswith("room_group_")):
                            end_groups.add(t)
                shared = common_groups & end_groups
                if shared:
                    g = next(iter(shared))
                    extra_group_tags = (g,)
        except Exception:
            extra_group_tags = ()

        base_line_tags = ("line", "committed_line", line_tag)
        line_tags = base_line_tags + extra_group_tags

        line = self.canvas.create_line(
            x0,
            y0,
            x1,
            y1,
            fill=self.model.line_color,
            width=width,
            dash=dash,
            tags=line_tags,
        )
        # Label and point
        label_text, mid_x, mid_y = get_distance_label(
            x0, y0, x1, y1, self.model.unit, self.model.zoom_level
        )
        label_tags = ("line_label", line_tag) + extra_group_tags
        label = self.canvas.create_text(
            mid_x,
            mid_y - 10,
            text=label_text,
            font=("Arial", 8),
            fill="black",
            tags=label_tags,
        )
        point_tags = ("line_point", line_tag) + extra_group_tags
        point = self.canvas.create_oval(
            x1 - 0.5,
            y1 - 0.5,
            x1 + 0.5,
            y1 + 0.5,
            fill="black",
            tags=point_tags,
        )

        # Store line metadata for editing/duplication
        if not hasattr(self, 'line_metadata'):
            self.line_metadata = {}
        self.line_metadata[line_tag] = {
            'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
            'width': width, 'dash': dash, 'color': self.model.line_color,
            'label': label, 'point': point
        }

        self.actions.log({
            "type": "create",
            "items": [line, label, point]
        })

        # Keep Line mode active and chain the next segment from this endpoint.
        self.first_point = (x1, y1)
        if self.current_preview:
            self.canvas.delete(self.current_preview)
            self.current_preview = None
        if self.current_line_label:
            self.canvas.delete(self.current_line_label)
            self.current_line_label = None

        if self.temp_entry:
            try:
                self.temp_entry.destroy()
            except Exception:
                pass
            self.temp_entry = None
        self.temp_direction = None
        self.temp_origin = None

    # === Polygon Drawing ===
    def _is_shift_pressed(self, event) -> bool:
        """Return True when user holds Shift (used for ortho locking)."""
        try:
            shift_mask = int(getattr(tk, "SHIFT", 0x0001))
            return bool(int(getattr(event, "state", 0)) & shift_mask)
        except Exception:
            return False

    def _apply_shift_ortho_lock(
        self,
        event,
        *,
        mouse_cx: float,
        mouse_cy: float,
        snapped_x: float,
        snapped_y: float,
        snap_info: dict,
        last_x: float,
        last_y: float,
    ) -> tuple[float, float, dict]:
        """
        AutoCAD-like behavior:
        - Hold Shift to constrain the next polygon edge to horizontal/vertical.
        - The constraint axis is chosen based on which direction the mouse is closer to.
        """
        if not self._is_shift_pressed(event):
            return snapped_x, snapped_y, snap_info

        dx = float(mouse_cx) - float(last_x)
        dy = float(mouse_cy) - float(last_y)

        # If movement is more horizontal -> lock Y (horizontal line).
        # If movement is more vertical -> lock X (vertical line).
        if abs(dx) >= abs(dy):
            snapped_y = float(last_y)
            snap_info["snap_type"] = "ortho_h"
            snap_info["has_h_align"] = True
            snap_info["has_v_align"] = False
            snap_info["has_grid_h"] = False  # y changed to exactly last_y
        else:
            snapped_x = float(last_x)
            snap_info["snap_type"] = "ortho_v"
            snap_info["has_h_align"] = False
            snap_info["has_v_align"] = True
            snap_info["has_grid_v"] = False  # x changed to exactly last_x

        return snapped_x, snapped_y, snap_info

    def add_polygon_point(self, event):
        # Work in canvas coordinates so drawing stays correct while panning/zooming.
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        # Use guidelines to snap the point (canvas coords)
        snapped_x, snapped_y, snap_info = self.guideline_helper.get_snap_point(
            cx, cy, self.polygon_points
        )
        # Optional ortho locking: Shift constrains the next edge to horizontal/vertical
        # relative to the last vertex.
        if self.polygon_points:
            last_x, last_y = self.polygon_points[-1]
            snapped_x, snapped_y, snap_info = self._apply_shift_ortho_lock(
                event,
                mouse_cx=cx,
                mouse_cy=cy,
                snapped_x=snapped_x,
                snapped_y=snapped_y,
                snap_info=snap_info,
                last_x=last_x,
                last_y=last_y,
            )
        x, y = snapped_x, snapped_y
        
        # Clear guides after placing point
        self.guideline_helper.clear_guides()

        # First point
        if not self.polygon_points:
            self._active_polygon_group_tag = self._new_polygon_group_tag()
            self.polygon_points.append((x, y))
            # Create initial polygon (empty)
            self.current_preview = self.canvas.create_polygon(
                x, y,
                outline="green",
                fill="",
                width=2,
                tags=(self._active_polygon_group_tag, "polygon_shape_preview"),
            )
            # First vertex marker
            point = self.canvas.create_oval(
                x - 2,
                y - 2,
                x + 2,
                y + 2,
                fill="green",
                outline="",
                tags=(self._active_polygon_group_tag, "polygon_vertex"),
            )
            self.canvas.tag_raise(point)
            self.actions.log({"type": "create", "items": [point]})
            return

        # Check if clicked near first point → close polygon
        if self._close_to_first(event) and len(self.polygon_points) >= 3:
            # Tracing Image Calibration Hook: If a background image is loaded and auto-calibrate is on,
            # prompt the user for the real-world distance of this closing segment (last point to first point) to scale image.
            if getattr(self, "trace_manager", None) and self.trace_manager.original_image and getattr(self.trace_manager, "auto_calibrate", True):
                try:
                    from Helper.trace_calibration import calibrate_trace_image
                    pt1 = self.polygon_points[-1]
                    pt2 = self.polygon_points[0]
                    calibrate_trace_image(self, pt1, pt2)
                except Exception as e:
                    print(f"[Trace Calibration] Closing segment calibration hook failed: {e}")
            self.finish_polygon()
            return

        # Add new point
        self.polygon_points.append((x, y))

        # Tracing Image Calibration Hook: If a background image is loaded and auto-calibrate is on,
        # prompt the user for the real-world distance of this new segment to scale the image.
        if getattr(self, "trace_manager", None) and self.trace_manager.original_image and getattr(self.trace_manager, "auto_calibrate", True):
            try:
                from Helper.trace_calibration import calibrate_trace_image
                pt1 = self.polygon_points[-2]
                pt2 = self.polygon_points[-1]
                calibrate_trace_image(self, pt1, pt2)
                # Update local x, y variables to match the scaled coordinates of the newly added point
                x, y = self.polygon_points[-1]
            except Exception as e:
                print(f"[Trace Calibration] Calibration hook failed: {e}")

        # Remove preview line since we've added a new point
        if self.polygon_preview_line:
            try:
                self.canvas.delete(self.polygon_preview_line)
                self.polygon_preview_line = None
            except Exception:
                pass

        # Update polygon preview
        flat = [coord for pt in self.polygon_points for coord in pt]
        self.canvas.coords(self.current_preview, *flat)

        # Vertex marker
        group_tag = self._active_polygon_group_tag or "polygon_group_unknown"
        point = self.canvas.create_oval(
            x - 2,
            y - 2,
            x + 2,
            y + 2,
            fill="green",
            outline="",
            tags=(group_tag, "polygon_vertex"),
        )
        self.canvas.tag_raise(point)
        self.actions.log({"type": "create", "items": [point]})

    def undo_last_polygon_point(self) -> bool:
        if not getattr(self, "polygon_points", []):
            return False

        # Pop the last point coordinate
        self.polygon_points.pop()

        # Undo the last logged create action (which is the vertex dot)
        try:
            self.actions.undo(self.canvas)
        except Exception as e:
            print(f"[Undo Polygon Point] Error performing actions.undo: {e}")

        # Clean up temporary preview drawings
        if getattr(self, "polygon_preview_line", None):
            try:
                self.canvas.delete(self.polygon_preview_line)
            except Exception:
                pass
            self.polygon_preview_line = None

        if getattr(self, "current_line_label", None):
            try:
                self.canvas.delete(self.current_line_label)
            except Exception:
                pass
            self.current_line_label = None

        try:
            self.guideline_helper.clear_guides()
        except Exception:
            pass

        # Update or delete the preview polygon coordinates
        if not self.polygon_points:
            if getattr(self, "current_preview", None):
                try:
                    self.canvas.delete(self.current_preview)
                except Exception:
                    pass
                self.current_preview = None
            self._active_polygon_group_tag = None
            print("🟢 Polygon points cleared.")
        else:
            if getattr(self, "current_preview", None):
                flat = [coord for pt in self.polygon_points for coord in pt]
                if len(self.polygon_points) == 1:
                    flat.extend(self.polygon_points[0])
                try:
                    self.canvas.coords(self.current_preview, *flat)
                except Exception:
                    pass
            print(f"🟢 Last point undone. Remaining points: {len(self.polygon_points)}")

        # Force a preview update based on current mouse position for instant visual feedback
        try:
            class DummyEvent:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y
                    self.state = 0
            
            px = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            py = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            ev = DummyEvent(px, py)
            self.update_polygon_preview(ev)
        except Exception:
            pass

        return True

    def undo_last_vastu_polygon_point(self) -> bool:
        if not getattr(self, "vastu_polygon_points", []):
            return False

        # Pop the last point coordinate
        self.vastu_polygon_points.pop()

        # If it was the first point, undo 1 action (the first dot).
        # Otherwise, undo 2 actions (the dot, then the line).
        try:
            if not self.vastu_polygon_points:
                self.actions.undo(self.canvas)  # Dot
            else:
                self.actions.undo(self.canvas)  # Dot
                self.actions.undo(self.canvas)  # Connection line
        except Exception as e:
            print(f"[Undo Vastu Polygon Point] Error performing actions.undo: {e}")

        # Clean up temporary preview drawings
        if getattr(self, "vastu_preview_line", None):
            try:
                self.canvas.delete(self.vastu_preview_line)
            except Exception:
                pass
            self.vastu_preview_line = None

        if getattr(self, "current_line_label", None):
            try:
                self.canvas.delete(self.current_line_label)
            except Exception:
                pass
            self.current_line_label = None

        try:
            self.guideline_helper.clear_guides()
        except Exception:
            pass

        # Update or delete the preview polygon coordinates
        if not self.vastu_polygon_points:
            if getattr(self, "vastu_preview_polygon", None):
                try:
                    self.canvas.delete(self.vastu_preview_polygon)
                except Exception:
                    pass
                self.vastu_preview_polygon = None
            print("🧭 Vastu polygon points cleared.")
        else:
            if getattr(self, "vastu_preview_polygon", None):
                flat = [coord for pt in self.vastu_polygon_points for coord in pt]
                if len(self.vastu_polygon_points) == 1:
                    flat.extend(self.vastu_polygon_points[0])
                try:
                    self.canvas.coords(self.vastu_preview_polygon, *flat)
                except Exception:
                    pass
            print(f"🧭 Last Vastu point undone. Remaining points: {len(self.vastu_polygon_points)}")

        # Force a preview update based on current mouse position for instant visual feedback
        try:
            class DummyEvent:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y
                    self.state = 0
            
            px = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            py = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            ev = DummyEvent(px, py)
            self.update_vastu_polygon_preview(ev)
        except Exception:
            pass

        return True

    def _close_to_first(self, event):
        """Check if click is close to first vertex."""
        if not self.polygon_points:
            return False
        x0, y0 = self.polygon_points[0]
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        return math.dist((cx, cy), (x0, y0)) < 10

    def update_polygon_preview(self, event):
        """Update live preview of polygon while mouse moves."""
        if not self.model.get("polygon_mode"):
            self.guideline_helper.clear_guides()
            return
        
        # If no points yet, nothing to preview
        if not self.polygon_points:
            self.guideline_helper.clear_guides()
            return

        # Current mouse position in canvas coords
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        # Get snapped position using guidelines (canvas coords)
        snapped_x, snapped_y, snap_info = self.guideline_helper.get_snap_point(
            cx, cy, self.polygon_points
        )
        # Optional ortho locking: Shift constrains preview edge relative to last vertex.
        if self.polygon_points:
            last_x, last_y = self.polygon_points[-1]
            snapped_x, snapped_y, snap_info = self._apply_shift_ortho_lock(
                event,
                mouse_cx=cx,
                mouse_cy=cy,
                snapped_x=snapped_x,
                snapped_y=snapped_y,
                snap_info=snap_info,
                last_x=last_x,
                last_y=last_y,
            )
        x, y = snapped_x, snapped_y
        
        # Draw guidelines (mouse position in canvas coords)
        self.guideline_helper.draw_guides(
            cx, cy, self.polygon_points, x, y, snap_info
        )
        
        group_tag = self._active_polygon_group_tag or "polygon_group_unknown"
        
        # Update polygon shape preview with current points + mouse position
        if self.current_preview:
            # Build coordinates: all clicked points + current mouse position
            preview_coords = []
            for pt in self.polygon_points:
                preview_coords.extend(pt)
            preview_coords.extend([x, y])
            
            # Update the polygon preview
            try:
                self.canvas.coords(self.current_preview, *preview_coords)
            except Exception:
                pass
        
        # Update or create preview line from last point to mouse cursor
        if len(self.polygon_points) > 0:
            last_x, last_y = self.polygon_points[-1]
            
            # Check if close to first point - show closing preview
            if len(self.polygon_points) >= 3:
                first_x, first_y = self.polygon_points[0]
                dist_to_first = math.dist((x, y), (first_x, first_y))
                
                if dist_to_first < 10:
                    # Show preview closing to first point
                    if self.polygon_preview_line:
                        try:
                            self.canvas.delete(self.polygon_preview_line)
                        except Exception:
                            pass
                    
                    # Create line from last point to first point (closing preview)
                    self.polygon_preview_line = self.canvas.create_line(
                        last_x, last_y, first_x, first_y,
                        fill="green",
                        width=2,
                        dash=(4, 2),
                        tags=(group_tag, "polygon_preview_line")
                    )
                    return
            
            # Normal preview: line from last point to current mouse position
            if self.polygon_preview_line:
                try:
                    self.canvas.coords(self.polygon_preview_line, last_x, last_y, x, y)
                except Exception:
                    # If update fails, recreate the line
                    try:
                        self.canvas.delete(self.polygon_preview_line)
                    except Exception:
                        pass
                    self.polygon_preview_line = self.canvas.create_line(
                        last_x, last_y, x, y,
                        fill="green",
                        width=2,
                        dash=(4, 2),
                        tags=(group_tag, "polygon_preview_line")
                    )
            else:
                self.polygon_preview_line = self.canvas.create_line(
                    last_x, last_y, x, y,
                    fill="green",
                    width=2,
                    dash=(4, 2),
                    tags=(group_tag, "polygon_preview_line")
                )

            # Segment distance label in red color
            try:
                pixel_dist = math.dist((last_x, last_y), (x, y))
                zoom = float(getattr(self.model, "zoom_level", 1.0) or 1.0)
                grid_spacing = float(getattr(self.model, "grid_spacing", 20.0) or 20.0)
                unit = getattr(self.model, "unit", "ft")
                unit_scale_map = getattr(self.model, "unit_scale", {}) or {}
                unit_factor = float(unit_scale_map.get(unit, 1.0) or 1.0)

                denom = max(1e-6, grid_spacing * zoom)
                real_dist = (pixel_dist / denom) * unit_factor
                label_text = f"{real_dist:.2f} {unit}"

                mx = (last_x + x) / 2.0
                my = (last_y + y) / 2.0

                if self.current_line_label:
                    self.canvas.coords(self.current_line_label, mx, my - 10)
                    self.canvas.itemconfig(self.current_line_label, text=label_text, fill="red", font=("Arial", 9, "bold"))
                else:
                    self.current_line_label = self.canvas.create_text(
                        mx, my - 10,
                        text=label_text,
                        font=("Arial", 9, "bold"),
                        fill="red",
                        tags=(group_tag, "polygon_preview_label")
                    )
            except Exception:
                pass
    def finish_polygon(self):
        """Finalize polygon: lock shape, compute area/perimeter, add label."""
        if len(self.polygon_points) < 3:
            return  # Not a valid polygon

        group_tag = self._active_polygon_group_tag or self._new_polygon_group_tag()
        self._active_polygon_group_tag = group_tag

        # Finalize polygon (ensure closed)
        flat = [float(coord) for pt in self.polygon_points for coord in pt]
        self.canvas.coords(self.current_preview, *flat)
        
        # Store baseline coordinates for undo/redo and dynamic recompute support
        if hasattr(self, "_polygon_baseline_coords_by_group"):
            self._polygon_baseline_coords_by_group[group_tag] = list(flat)

        # Apply current line style to finalized polygon outline
        style = getattr(self.model, "line_style", "solid")
        poly_width = 4 if style == "bold" else 2
        poly_dash = (4, 2) if style == "dashed" else None

        # Use green for outline unless transparent mode is ON
        poly_outline = "" if self.model.get("polygon_transparent") else "green"
        
        self.canvas.itemconfig(
            self.current_preview,
            tags=("closed_shape", group_tag, "polygon_shape"),
            outline=poly_outline,
            width=poly_width,
            dash=poly_dash,
        )

        # Area + perimeter
        zoom_level = float(getattr(self.model, "zoom_level", 1.0))
        area = calculate_polygon_area(self.polygon_points, self.model.unit, zoom_level)
        perimeter = calculate_polygon_perimeter(self.polygon_points, self.model.unit, zoom_level)

        self._polygon_label_serial = int(getattr(self, "_polygon_label_serial", 0) or 0) + 1
        serial = self._polygon_label_serial
        label_text = (
            f"Area {serial}: {area:.2f} {self.model.unit}²\n"
            f"Perimeter {serial}: {perimeter:.2f} {self.model.unit}"
        )
        label_id = self.polygon_label_placer.create_polygon_label(
            self.polygon_points,
            label_text,
            tags=(group_tag, "polygon_label"),
            fill="black",
            font=("Arial", 9),
        )
        self.canvas.tag_raise(label_id)

        # Engineering-style dimensions for each polygon edge (extension lines + arrowed dimension line)
        dim_items = []
        try:
            if getattr(self.model, "auto_polygon_dimensions", True) and hasattr(self, "dimension_drawer"):
                dim_items = self.dimension_drawer.draw_polygon_edge_dimensions(
                    self.polygon_points,
                    group_tag=group_tag,
                    dim_tag=f"{group_tag}__dims",
                )
        except Exception:
            dim_items = []

        # Log for undo
        self.actions.log(
            {
                "type": "create",
                "items": [self.current_preview, label_id, *dim_items],
                "dimension_recompute": {
                    "group_tag": group_tag,
                    "dim_tag": f"{group_tag}__dims",
                },
            }
        )

        # Clear guidelines
        self.guideline_helper.clear_guides()
        
        # Reset
        self.polygon_points = []
        self.current_preview = None
        if self.polygon_preview_line:
            try:
                self.canvas.delete(self.polygon_preview_line)
            except Exception:
                pass
            self.polygon_preview_line = None
        if self.current_line_label:
            try:
                self.canvas.delete(self.current_line_label)
            except Exception:
                pass
            self.current_line_label = None
        self._active_polygon_group_tag = None

        try:
            self.model.set("polygon_mode", False)
        except Exception:
            try:
                setattr(self.model, "polygon_mode", False)
            except Exception:
                pass
        try:
            self.view.canvas.config(cursor="arrow")
        except Exception:
            pass

    def toggle_polygon_transparency(self):
        """Toggle transparency of all polygons and their vertex markers."""
        current = self.model.get("polygon_transparent")
        new_state = not current
        self.model.set("polygon_transparent", new_state)
        
        outline_color = "" if new_state else "green"
        vertex_color = "" if new_state else "green"
        
        # Target polygon shapes
        for item_id in self.canvas.find_withtag("polygon_shape"):
            try:
                self.canvas.itemconfig(item_id, outline=outline_color)
            except Exception:
                pass
            
        # Target polygon vertices
        for item_id in self.canvas.find_withtag("polygon_vertex"):
            try:
                self.canvas.itemconfig(item_id, fill=vertex_color)
            except Exception:
                pass

        # Target preview line if drawing
        if hasattr(self, "polygon_preview_line") and self.polygon_preview_line:
             try:
                 self.canvas.itemconfig(self.polygon_preview_line, fill=outline_color)
             except Exception:
                 pass

    def _preview_polygon(self):
        if self.current_preview:
            self.canvas.delete(self.current_preview)
        if len(self.polygon_points) >= 2:
            coords = [coord for pt in self.polygon_points for coord in pt]
            self.current_preview = self.canvas.create_line(coords, fill="gray", dash=(4, 2))
                  
#eraser mode
    def enable_eraser_mode(self):
        """
        Enable eraser mode.
        New behavior:
        - First click: mark starting point for wall erase (no deletion yet).
        - Second click: create a gap in the wall between the two points (only erases the part between points).
        """
        self.reset_modes()
        self.model.set("eraser_mode", True)
        self.view.canvas.config(cursor="dotbox")
        # Clear any previous wall‑erase state
        self._wall_erase_first_point = None
        if self._wall_erase_preview_id:
            try:
                self.canvas.delete(self._wall_erase_preview_id)
            except Exception:
                pass
            self._wall_erase_preview_id = None

        # Clear multi‑erase selection state if coming from that mode
        self._multi_erase_start = None
        if self._multi_erase_rect_id:
            try:
                self.canvas.delete(self._multi_erase_rect_id)
            except Exception:
                pass
            self._multi_erase_rect_id = None


    def enable_multi_eraser_mode(self):
        """
        Enable multi‑wall eraser mode with precise selection.

        Usage:
        - Click the "Erase Multiple (Precise)" button.
        - Right‑click and drag to draw a selection rectangle.
        - Only walls whose centers are well within the selection area will be selected.
        - A confirmation dialog will show exactly how many walls are selected before deleting.
        """
        self.reset_modes()
        self.model.set("multi_eraser_mode", True)
        self.view.canvas.config(cursor="crosshair")

        # Reset internal selection rectangle state
        self._multi_erase_start = None
        if self._multi_erase_rect_id:
            try:
                self.canvas.delete(self._multi_erase_rect_id)
            except Exception:
                pass
            self._multi_erase_rect_id = None


    def handle_eraser_click(self, event):
        """
        Two‑point wall eraser:
        - First click: choose starting point.
        - Second click: create a gap in the wall between the two points (partial erase).
        """
        x, y = event.x, event.y

        # First point: store and draw a small preview marker
        if self._wall_erase_first_point is None:
            self._wall_erase_first_point = (x, y)

            # Remove old preview if any
            if self._wall_erase_preview_id:
                try:
                    self.canvas.delete(self._wall_erase_preview_id)
                except Exception:
                    pass
                self._wall_erase_preview_id = None

            size = 4
            try:
                self._wall_erase_preview_id = self.canvas.create_oval(
                    x - size,
                    y - size,
                    x + size,
                    y + size,
                    outline="red",
                    width=2,
                    tags=("wall_erase_preview",),
                )
                self.canvas.tag_raise(self._wall_erase_preview_id)
            except Exception:
                self._wall_erase_preview_id = None
            return

        # Second point: define corridor and erase part of wall between the two points
        x0, y0 = self._wall_erase_first_point
        x1, y1 = x, y

        # Clear preview + reset state
        if self._wall_erase_preview_id:
            try:
                self.canvas.delete(self._wall_erase_preview_id)
            except Exception:
                pass
        self._wall_erase_preview_id = None
        self._wall_erase_first_point = None

        # Ignore tiny distances (accidental double click)
        if abs(x1 - x0) < 3 and abs(y1 - y0) < 3:
            return

        # Define a corridor rectangle around the segment between the two points
        margin = 10  # pixels on each side
        xmin, xmax = sorted((x0, x1))
        ymin, ymax = sorted((y0, y1))
        xmin -= margin
        xmax += margin
        ymin -= margin
        ymax += margin

        candidates = self.canvas.find_overlapping(xmin, ymin, xmax, ymax)
        if not candidates:
            return

        # We will pick a single "best" wall segment to erase part of
        best_item_id: int | None = None
        best_distance: float = float("inf")

        # Mid‑point of the erase segment – used to choose the nearest wall
        mid_x = (x0 + x1) / 2.0
        mid_y = (y0 + y1) / 2.0

        def _is_wall_like(item_id: int) -> bool:
            """
            Heuristic to treat an item as a wall:
            - Skip grid / helpers / measurement / selection / screenshot overlays.
            - Prefer thin, long rectangles or any line.
            """
            try:
                tags = self.canvas.gettags(item_id)
                # Skip helper/overlay items
                if "grid" in tags:
                    return False
                if "measure_temp" in tags or "measure_dot" in tags:
                    return False
                if "selection_highlight" in tags or "screenshot_region" in tags:
                    return False
                if "balcony" in tags:
                    return False
                if "flooring" in tags or "flooring_border" in tags:
                    return False
                item_type = self.canvas.type(item_id)
            except Exception:
                return False

            if item_type == "line":
                return True

            if item_type == "rectangle":
                try:
                    coords = self.canvas.coords(item_id)
                    if len(coords) >= 4:
                        xA, yA, xB, yB = coords[0], coords[1], coords[2], coords[3]
                        width = abs(xB - xA)
                        height = abs(yB - yA)
                        # Wall rectangles are usually long and thin
                        thin_threshold = 15.0
                        long_threshold = 25.0
                        long_enough = max(width, height) >= long_threshold
                        thin_enough = min(width, height) <= thin_threshold
                        return long_enough and thin_enough
                except Exception:
                    return False

            # Skip plot polygons (polygon_shape/closed_shape) - never erase layout boundaries
            if item_type == "polygon":
                try:
                    tags = self.canvas.gettags(item_id)
                    if "polygon_shape" in tags or "closed_shape" in tags:
                        return False
                except Exception:
                    pass

            return False

        def _distance_to_item_center(item_id: int) -> float:
            try:
                coords = self.canvas.coords(item_id)
                if len(coords) >= 4:
                    xA, yA, xB, yB = coords[0], coords[1], coords[2], coords[3]
                    cx = (xA + xB) / 2.0
                    cy = (yA + yB) / 2.0
                elif len(coords) == 2:
                    cx, cy = coords[0], coords[1]
                else:
                    return float("inf")
                dx = cx - mid_x
                dy = cy - mid_y
                return (dx * dx + dy * dy) ** 0.5
            except Exception:
                return float("inf")

        for item_id in candidates:
            if not _is_wall_like(item_id):
                continue
            dist = _distance_to_item_center(item_id)
            if dist < best_distance:
                best_distance = dist
                best_item_id = item_id

        if best_item_id is not None and best_distance < float("inf"):
            def _snapshot_item(item_id: int):
                try:
                    snap = self.actions._snapshot_canvas_items(self.canvas, [item_id])
                    if snap:
                        return snap[0]
                except Exception:
                    pass
                # Fallback schema (best-effort)
                try:
                    item_type = self.canvas.type(item_id)
                except Exception:
                    item_type = ""
                try:
                    coords = self.canvas.coords(item_id)
                except Exception:
                    coords = []
                try:
                    tags = self.canvas.gettags(item_id)
                except Exception:
                    tags = ()
                return {"type": item_type, "coords": coords, "options": {}, "tags": tags}

            # Check if this is the last wall - prevent deletion if so
            def count_walls_on_canvas():
                """Count all wall-like items on the canvas, excluding the current item being processed."""
                wall_count = 0
                all_items = self.canvas.find_all()
                
                for item_id in all_items:
                    # Skip the item we're about to delete
                    if item_id == best_item_id:
                        continue
                        
                    try:
                        tags = self.canvas.gettags(item_id)
                        # Skip helper/overlay items
                        if "grid" in tags:
                            continue
                        if "measure_temp" in tags or "measure_dot" in tags:
                            continue
                        if "selection_highlight" in tags or "screenshot_region" in tags:
                            continue
                        if "balcony" in tags:
                            continue
                        if "flooring" in tags or "flooring_border" in tags:
                            continue
                        if "wall_erase_preview" in tags:
                            continue
                        if "multi_erase_highlight" in tags:
                            continue
                            
                        item_type = self.canvas.type(item_id)
                    except Exception:
                        continue

                    if item_type == "line":
                        wall_count += 1
                    elif item_type == "rectangle":
                        try:
                            coords = self.canvas.coords(item_id)
                            if len(coords) >= 4:
                                xA, yA, xB, yB = coords[0], coords[1], coords[2], coords[3]
                                width = abs(xB - xA)
                                height = abs(yB - yA)
                                # Wall rectangles are usually long and thin
                                thin_threshold = 15.0
                                long_threshold = 25.0
                                long_enough = max(width, height) >= long_threshold
                                thin_enough = min(width, height) <= thin_threshold
                                if long_enough and thin_enough:
                                    wall_count += 1
                        except Exception:
                            continue
                    elif item_type == "polygon":
                        try:
                            tags = self.canvas.gettags(item_id)
                            if "closed_shape" in tags or "room" in tags:
                                wall_count += 1
                        except Exception:
                            continue
                
                return wall_count
            
            remaining_walls = count_walls_on_canvas()
            
            # If this would be the last wall, show error and don't allow any modification
            if remaining_walls <= 0:
                try:
                    messagebox.showerror(
                        "Cannot Erase Wall",
                        "This wall cannot be deleted.\n\nAt least one wall must remain on the canvas.",
                        icon="error"
                    )
                except Exception:
                    print("❌ This wall cannot be deleted. At least one wall must remain on the canvas.")
                
                # Exit eraser mode and return to normal behavior
                try:
                    self.model.set("eraser_mode", False)
                except Exception:
                    pass
                try:
                    self.canvas.config(cursor="arrow")
                except Exception:
                    pass
                return
            
            try:
                item_type = self.canvas.type(best_item_id)

                if item_type == "rectangle":
                    # For rectangle walls, create a gap by splitting the wall
                    coords = self.canvas.coords(best_item_id)
                    if len(coords) >= 4:
                        wall_x0, wall_y0, wall_x1, wall_y1 = coords[0], coords[1], coords[2], coords[3]
                        wall_width = abs(wall_x1 - wall_x0)
                        wall_height = abs(wall_y1 - wall_y0)
                        
                        # Determine wall orientation and which coordinates to use for cutting
                        if wall_width > wall_height:
                            # Horizontal wall - cut based on X coordinates
                            cut_start = min(x0, x1)
                            cut_end = max(x0, x1)
                            wall_side = "top"  # Treat as top wall for cutting logic
                            
                            # Check if cut would span entire wall (with some margin)
                            margin = 10  # pixels
                            if cut_start <= (wall_x0 + margin) and cut_end >= (wall_x1 - margin):
                                # Cut would remove entire wall - check if it's the last one
                                if remaining_walls <= 0:
                                    try:
                                        messagebox.showerror(
                                            "Cannot Erase Wall",
                                            "This operation would completely remove the last wall.\n\nAt least one wall must remain on the canvas.",
                                            icon="error"
                                        )
                                    except Exception:
                                        print("❌ Cannot completely remove the last wall. At least one wall must remain.")
                                    
                                    # Exit eraser mode
                                    try:
                                        self.model.set("eraser_mode", False)
                                        self.canvas.config(cursor="arrow")
                                    except Exception:
                                        pass
                                    return
                        else:
                            # Vertical wall - cut based on Y coordinates  
                            cut_start = min(y0, y1)
                            cut_end = max(y0, y1)
                            wall_side = "left"  # Treat as left wall for cutting logic
                            
                            # Check if cut would span entire wall (with some margin)
                            margin = 10  # pixels
                            if cut_start <= (wall_y0 + margin) and cut_end >= (wall_y1 - margin):
                                # Cut would remove entire wall - check if it's the last one
                                if remaining_walls <= 0:
                                    try:
                                        messagebox.showerror(
                                            "Cannot Erase Wall",
                                            "This operation would completely remove the last wall.\n\nAt least one wall must remain on the canvas.",
                                            icon="error"
                                        )
                                    except Exception:
                                        print("❌ Cannot completely remove the last wall. At least one wall must remain.")
                                    
                                    # Exit eraser mode
                                    try:
                                        self.model.set("eraser_mode", False)
                                        self.canvas.config(cursor="arrow")
                                    except Exception:
                                        pass
                                    return

                        # Determine owning walls_only room (if any) BEFORE we cut the wall
                        room_entity_for_manual = None
                        try:
                            tags = self.canvas.gettags(best_item_id)
                            group_tag = None
                            for t in tags:
                                if isinstance(t, str) and t.startswith("room_group_"):
                                    group_tag = t
                                    break
                            if group_tag:
                                room_entity_for_manual = getattr(self, "room_entities_by_group_tag", {}).get(group_tag)
                        except Exception:
                            room_entity_for_manual = None
                        
                        # Slightly shrink the cut region so the visual gap is not
                        # larger than intended (avoid ~1-grid overshoot).
                        try:
                            shrink = 2.0
                            if cut_end - cut_start > 2 * shrink:
                                cut_start += shrink
                                cut_end -= shrink
                        except Exception:
                            pass

                        # Use existing wall cutting function to create gap
                        self._cut_wall_segment(best_item_id, cut_start, cut_end, 0, wall_side, 0)

                        # Record this as a manual wall erase for walls_only rooms (so it persists across door recuts)
                        if room_entity_for_manual is not None:
                            self._record_manual_wall_erase(room_entity_for_manual, wall_side, cut_start, cut_end)

                        print("✅ Gap created in wall between selected points.")
                        
                elif item_type == "line":
                    # For line walls, we need to split the line into segments
                    coords = self.canvas.coords(best_item_id)
                    if len(coords) >= 4:
                        line_x0, line_y0, line_x1, line_y1 = coords[0], coords[1], coords[2], coords[3]
                        
                        # Get line properties
                        fill_color = self.canvas.itemcget(best_item_id, "fill")
                        width = self.canvas.itemcget(best_item_id, "width")
                        tags = self.canvas.gettags(best_item_id)
                        
                        # Calculate intersection points with the erase segment
                        # For simplicity, project the erase points onto the line
                        line_length = ((line_x1 - line_x0)**2 + (line_y1 - line_y0)**2)**0.5
                        if line_length > 0:
                            old_items_snapshot = [_snapshot_item(best_item_id)]
                            new_items_snapshot = []
                            # Project first point onto line
                            t0 = max(0, min(1, ((x0 - line_x0) * (line_x1 - line_x0) + (y0 - line_y0) * (line_y1 - line_y0)) / (line_length**2)))
                            # Project second point onto line  
                            t1 = max(0, min(1, ((x1 - line_x0) * (line_x1 - line_x0) + (y1 - line_y0) * (line_y1 - line_y0)) / (line_length**2)))
                            
                            # Ensure t0 < t1
                            if t0 > t1:
                                t0, t1 = t1, t0
                            
                            # Check if cut would span entire line (with small margin)
                            margin = 0.05  # 5% of line length
                            if t0 <= margin and t1 >= (1 - margin):
                                # Cut would remove entire line - check if it's the last wall
                                if remaining_walls <= 0:
                                    try:
                                        messagebox.showerror(
                                            "Cannot Erase Wall",
                                            "This operation would completely remove the last wall.\n\nAt least one wall must remain on the canvas.",
                                            icon="error"
                                        )
                                    except Exception:
                                        print("❌ Cannot completely remove the last wall. At least one wall must remain.")
                                    
                                    # Exit eraser mode
                                    try:
                                        self.model.set("eraser_mode", False)
                                        self.canvas.config(cursor="arrow")
                                    except Exception:
                                        pass
                                    return
                            
                            # Create line segments before and after the gap
                            if t0 > 0:
                                # Line segment before gap
                                seg1_x1 = line_x0 + t0 * (line_x1 - line_x0)
                                seg1_y1 = line_y0 + t0 * (line_y1 - line_y0)
                                seg1_id = self.canvas.create_line(
                                    line_x0, line_y0, seg1_x1, seg1_y1,
                                    fill=fill_color, width=width, tags=tags
                                )
                                new_items_snapshot.append(_snapshot_item(seg1_id))
                            
                            if t1 < 1:
                                # Line segment after gap
                                seg2_x0 = line_x0 + t1 * (line_x1 - line_x0)
                                seg2_y0 = line_y0 + t1 * (line_y1 - line_y0)
                                seg2_id = self.canvas.create_line(
                                    seg2_x0, seg2_y0, line_x1, line_y1,
                                    fill=fill_color, width=width, tags=tags
                                )
                                new_items_snapshot.append(_snapshot_item(seg2_id))
                            
                            # Delete original line
                            self.canvas.delete(best_item_id)

                            if new_items_snapshot:
                                try:
                                    self.actions.log(
                                        {
                                            "type": "replace_group",
                                            "old_items": old_items_snapshot,
                                            "new_items": new_items_snapshot,
                                        }
                                    )
                                except Exception:
                                    pass
                            print("✅ Gap created in line between selected points.")
                        
                else:
                    # For other types (polygons, etc.), this would be full deletion
                    # Check if it's the last wall before allowing deletion
                    if remaining_walls <= 0:
                        try:
                            messagebox.showerror(
                                "Cannot Erase Wall",
                                "This wall cannot be deleted.\n\nAt least one wall must remain on the canvas.",
                                icon="error"
                            )
                        except Exception:
                            print("❌ This wall cannot be deleted. At least one wall must remain on the canvas.")
                        
                        # Exit eraser mode
                        try:
                            self.model.set("eraser_mode", False)
                            self.canvas.config(cursor="arrow")
                        except Exception:
                            pass
                        return
                    
                    # Log for undo functionality
                    try:
                        snap = self.actions._snapshot_canvas_items(self.canvas, [best_item_id])
                        item = snap[0] if snap else None
                    except Exception:
                        item = None

                    if item:
                        payload = {
                            "type": "delete",
                            "item_type": item.get("type"),
                            "coords": item.get("coords"),
                            "options": item.get("options"),
                            "tags": item.get("tags"),
                            "new_id": None,  # set during undo recreate
                        }
                    else:
                        # Fallback (keeps previous behavior but may lose some style metadata)
                        try:
                            coords = self.canvas.coords(best_item_id)
                        except Exception:
                            coords = []
                        try:
                            tags = self.canvas.gettags(best_item_id)
                        except Exception:
                            tags = ()
                        options = {}
                        if item_type == "text":
                            try:
                                options["text"] = self.canvas.itemcget(best_item_id, "text")
                                options["fill"] = self.canvas.itemcget(best_item_id, "fill")
                            except Exception:
                                pass
                        elif item_type == "line":
                            try:
                                options["fill"] = self.canvas.itemcget(best_item_id, "fill")
                                options["width"] = self.canvas.itemcget(best_item_id, "width")
                            except Exception:
                                pass
                        elif item_type in ("oval", "rectangle", "polygon"):
                            try:
                                options["fill"] = self.canvas.itemcget(best_item_id, "fill")
                                options["outline"] = self.canvas.itemcget(best_item_id, "outline")
                                options["width"] = self.canvas.itemcget(best_item_id, "width")
                            except Exception:
                                pass
                        payload = {
                            "type": "delete",
                            "item_type": item_type,
                            "coords": coords,
                            "options": options,
                            "tags": tags,
                            "new_id": None,
                        }

                    try:
                        self.actions.log(payload)
                    except Exception:
                        pass
                    
                    self.canvas.delete(best_item_id)
                    print("✅ Wall cleared between selected points.")
                    
            except Exception as e:
                print(f"Error creating gap in wall: {e}")
                return

            # ✅ After one successful erase, exit eraser mode and return to normal behavior.
            # (User can re-enable eraser explicitly from the toolbar.)
            try:
                self.model.set("eraser_mode", False)
            except Exception:
                pass
            try:
                self.canvas.config(cursor="arrow")
            except Exception:
                pass

    # === Multi‑wall Eraser (selection rectangle) ===
    def start_multi_erase_selection(self, event):
        """Begin a multi-wall erase selection rectangle (right-click press)."""
        if not self.model.get("multi_eraser_mode"):
            return

        self._multi_erase_start = (event.x, event.y)

        # Remove previous selection rect if any
        if self._multi_erase_rect_id:
            try:
                self.canvas.delete(self._multi_erase_rect_id)
            except Exception:
                pass
            self._multi_erase_rect_id = None

        try:
            self._multi_erase_rect_id = self.canvas.create_rectangle(
                event.x,
                event.y,
                event.x,
                event.y,
                outline="red",
                fill="red",
                stipple="gray25",  # Semi-transparent pattern
                width=2,
                dash=(4, 2),
                tags=("multi_erase_rect",),
            )
            self.canvas.tag_raise(self._multi_erase_rect_id)
        except Exception:
            self._multi_erase_rect_id = None

    def update_multi_erase_selection(self, event):
        """Update selection rectangle while user drags right button."""
        if not self.model.get("multi_eraser_mode"):
            return
        if not self._multi_erase_start or not self._multi_erase_rect_id:
            return

        x0, y0 = self._multi_erase_start
        x1, y1 = event.x, event.y

        try:
            self.canvas.coords(self._multi_erase_rect_id, x0, y0, x1, y1)
            self.canvas.tag_raise(self._multi_erase_rect_id)
        except Exception:
            pass

    def finish_multi_erase_selection(self, event):
        """Finish selection and optionally delete all wall-like items inside."""
        if not self.model.get("multi_eraser_mode"):
            return
        if not self._multi_erase_start:
            return

        x0, y0 = self._multi_erase_start
        x1, y1 = event.x, event.y

        # Clear selection rectangle visual
        if self._multi_erase_rect_id:
            try:
                self.canvas.delete(self._multi_erase_rect_id)
            except Exception:
                pass
            self._multi_erase_rect_id = None

        self._multi_erase_start = None

        # Ignore tiny selections
        if abs(x1 - x0) < 3 and abs(y1 - y0) < 3:
            return

        xmin, xmax = sorted((x0, x1))
        ymin, ymax = sorted((y0, y1))

        # Add tolerance to make selection more precise (walls must be more centered in selection)
        selection_tolerance = 10  # pixels - walls must be this far from selection edges
        
        candidates = self.canvas.find_overlapping(xmin, ymin, xmax, ymax)
        if not candidates:
            return

        wall_items = []
        for item_id in candidates:
            try:
                tags = self.canvas.gettags(item_id)
                if "grid" in tags:
                    continue
                if "measure_temp" in tags or "measure_dot" in tags:
                    continue
                if "selection_highlight" in tags or "screenshot_region" in tags:
                    continue
                if "balcony" in tags:
                    continue
                if "flooring" in tags or "flooring_border" in tags:
                    continue
                if "multi_erase_rect" in tags:  # Skip the selection rectangle itself
                    continue
                if "wall_erase_preview" in tags:
                    continue
                if "multi_erase_highlight" in tags:
                    continue
                    
                item_type = self.canvas.type(item_id)
            except Exception:
                continue

            # More precise wall detection
            is_wall = False
            
            if item_type == "line":
                # Check if line is substantially within selection area
                try:
                    coords = self.canvas.coords(item_id)
                    if len(coords) >= 4:
                        line_x0, line_y0, line_x1, line_y1 = coords[0], coords[1], coords[2], coords[3]
                        # Check if a significant portion of the line is within selection
                        line_center_x = (line_x0 + line_x1) / 2
                        line_center_y = (line_y0 + line_y1) / 2
                        
                        # Line center must be within selection area with tolerance
                        if (xmin + selection_tolerance) <= line_center_x <= (xmax - selection_tolerance) and \
                           (ymin + selection_tolerance) <= line_center_y <= (ymax - selection_tolerance):
                            is_wall = True
                except Exception:
                    continue
                    
            elif item_type == "rectangle":
                try:
                    coords = self.canvas.coords(item_id)
                    if len(coords) >= 4:
                        rect_x0, rect_y0, rect_x1, rect_y1 = coords[0], coords[1], coords[2], coords[3]
                        width = abs(rect_x1 - rect_x0)
                        height = abs(rect_y1 - rect_y0)
                        
                        # Check if it looks like a wall (long and thin)
                        thin_threshold = 15.0
                        long_threshold = 25.0
                        long_enough = max(width, height) >= long_threshold
                        thin_enough = min(width, height) <= thin_threshold
                        
                        if long_enough and thin_enough:
                            # Check if rectangle center is within selection area
                            rect_center_x = (rect_x0 + rect_x1) / 2
                            rect_center_y = (rect_y0 + rect_y1) / 2
                            
                            # Rectangle center must be within selection area with tolerance
                            if (xmin + selection_tolerance) <= rect_center_x <= (xmax - selection_tolerance) and \
                               (ymin + selection_tolerance) <= rect_center_y <= (ymax - selection_tolerance):
                                is_wall = True
                except Exception:
                    continue
                    
            elif item_type == "polygon":
                # Plot polygons (polygon_shape) must never be erased - they are layout boundaries.
                # Only room wall rectangles should be erasable via multi-erase.
                try:
                    tags = self.canvas.gettags(item_id)
                    if "polygon_shape" in tags or "closed_shape" in tags:
                        # Skip plot/closed polygons - user erases room walls, not the plot boundary
                        continue
                    if "room" in tags:
                        bbox = self.canvas.bbox(item_id)
                        if bbox:
                            poly_center_x = (bbox[0] + bbox[2]) / 2
                            poly_center_y = (bbox[1] + bbox[3]) / 2
                            if (xmin + selection_tolerance) <= poly_center_x <= (xmax - selection_tolerance) and \
                               (ymin + selection_tolerance) <= poly_center_y <= (ymax - selection_tolerance):
                                is_wall = True
                except Exception:
                    continue
            
            if is_wall:
                wall_items.append(item_id)

        if not wall_items:
            return

        # Debug: Print selection info
        print(f"[DEBUG] Multi-eraser selection area: ({xmin:.1f}, {ymin:.1f}) to ({xmax:.1f}, {ymax:.1f})")
        print(f"[DEBUG] Found {len(wall_items)} wall items to select:")
        for i, item_id in enumerate(wall_items):
            try:
                item_type = self.canvas.type(item_id)
                coords = self.canvas.coords(item_id)
                if item_type == "line" and len(coords) >= 4:
                    print(f"[DEBUG]   {i+1}. Line {item_id}: ({coords[0]:.1f}, {coords[1]:.1f}) to ({coords[2]:.1f}, {coords[3]:.1f})")
                elif item_type == "rectangle" and len(coords) >= 4:
                    width = abs(coords[2] - coords[0])
                    height = abs(coords[3] - coords[1])
                    print(f"[DEBUG]   {i+1}. Rectangle {item_id}: ({coords[0]:.1f}, {coords[1]:.1f}) to ({coords[2]:.1f}, {coords[3]:.1f}) - {width:.1f}x{height:.1f}")
                elif item_type == "polygon":
                    bbox = self.canvas.bbox(item_id)
                    print(f"[DEBUG]   {i+1}. Polygon {item_id}: bbox {bbox}")
                else:
                    print(f"[DEBUG]   {i+1}. {item_type} {item_id}: {coords}")
            except Exception as e:
                print(f"[DEBUG]   {i+1}. Item {item_id}: Error getting info - {e}")

        # Count total walls on canvas to prevent deleting all walls
        def count_all_walls():
            """Count all wall-like items on the canvas."""
            wall_count = 0
            all_items = self.canvas.find_all()
            
            for item_id in all_items:
                try:
                    tags = self.canvas.gettags(item_id)
                    if "grid" in tags:
                        continue
                    if "measure_temp" in tags or "measure_dot" in tags:
                        continue
                    if "selection_highlight" in tags or "screenshot_region" in tags:
                        continue
                    if "balcony" in tags:
                        continue
                    if "flooring" in tags or "flooring_border" in tags:
                        continue
                    item_type = self.canvas.type(item_id)
                except Exception:
                    continue

                if item_type == "line":
                    wall_count += 1
                elif item_type == "rectangle":
                    try:
                        coords = self.canvas.coords(item_id)
                        if len(coords) >= 4:
                            xA, yA, xB, yB = coords[0], coords[1], coords[2], coords[3]
                            width = abs(xB - xA)
                            height = abs(yB - yA)
                            # Wall rectangles are usually long and thin
                            thin_threshold = 15.0
                            long_threshold = 25.0
                            long_enough = max(width, height) >= long_threshold
                            thin_enough = min(width, height) <= thin_threshold
                            if long_enough and thin_enough:
                                wall_count += 1
                    except Exception:
                        continue
                elif item_type == "polygon":
                    try:
                        tags = self.canvas.gettags(item_id)
                        if "closed_shape" in tags or "room" in tags:
                            wall_count += 1
                    except Exception:
                        continue
            
            return wall_count
        
        total_walls = count_all_walls()
        
        # Check if deleting selected walls would leave no walls
        if len(wall_items) >= total_walls:
            try:
                messagebox.showerror(
                    "Cannot Erase Walls",
                    "Cannot delete all walls.\n\nAt least one wall must remain on the canvas.",
                    icon="error"
                )
            except Exception:
                print("❌ Cannot delete all walls. At least one wall must remain on the canvas.")
            return

        # Highlight selected walls before confirmation
        highlight_ids: list[int] = []
        for item_id in wall_items:
            try:
                bbox = self.canvas.bbox(item_id)
                if not bbox:
                    continue
                hx0, hy0, hx1, hy1 = bbox
                # Add padding to make highlight more visible
                padding = 3
                hid = self.canvas.create_rectangle(
                    hx0 - padding,
                    hy0 - padding,
                    hx1 + padding,
                    hy1 + padding,
                    outline="red",
                    fill="red",
                    stipple="gray25",  # Semi-transparent
                    width=3,
                    dash=(6, 3),
                    tags=("multi_erase_highlight",),
                )
                highlight_ids.append(hid)
                self.canvas.tag_raise(hid)
            except Exception:
                continue

        # Ask user for confirmation with count information
        try:
            ok = messagebox.askokcancel(
                "Erase Walls",
                f"Selected {len(wall_items)} wall(s) will be deleted.\n\nProceed?",
                icon="warning",
            )
        except Exception:
            ok = True

        if not ok:
            # Clear only highlights and keep walls as-is
            for hid in highlight_ids:
                try:
                    self.canvas.delete(hid)
                except Exception:
                    continue
            return

        expanded_items = []
        for item_id in wall_items:
            if item_id not in expanded_items:
                expanded_items.append(item_id)
            try:
                tags = self.canvas.gettags(item_id)
            except Exception:
                continue
            line_tag = next((t for t in tags if t.startswith("line_")), None)
            if line_tag:
                try:
                    for related_id in self.canvas.find_withtag(line_tag):
                        if related_id not in expanded_items:
                            expanded_items.append(related_id)
                except Exception:
                    pass

        wall_items = expanded_items

        # Before deleting, record manual wall erasures for walls_only rooms so they persist across door recuts.
        try:
            for item_id in wall_items:
                try:
                    if self.canvas.type(item_id) != "rectangle":
                        continue
                    tags = self.canvas.gettags(item_id)
                    group_tag = None
                    for t in tags:
                        if isinstance(t, str) and t.startswith("room_group_"):
                            group_tag = t
                            break
                    if not group_tag:
                        continue
                    room_entity = getattr(self, "room_entities_by_group_tag", {}).get(group_tag)
                    if not room_entity or getattr(room_entity, "fill_mode", "") != "walls_only":
                        continue
                    rect_id = getattr(room_entity, "rect_id", None)
                    if not rect_id or not self._item_exists(rect_id):
                        continue
                    room_coords = self.canvas.coords(rect_id)
                    if not room_coords or len(room_coords) < 4:
                        continue
                    rx0, ry0, rx1, ry1 = float(room_coords[0]), float(room_coords[1]), float(room_coords[2]), float(room_coords[3])
                    coords = self.canvas.coords(item_id)
                    if not coords or len(coords) < 4:
                        continue
                    x0, y0, x1, y1 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])
                    w, h = abs(x1 - x0), abs(y1 - y0)
                    # Determine which side this wall rectangle belongs to
                    side = None
                    if w >= h:
                        # Horizontal-ish wall
                        if abs(y0 - ry0) < abs(y1 - ry1):
                            side = "top"
                        else:
                            side = "bottom"
                        start = min(x0, x1)
                        end = max(x0, x1)
                    else:
                        # Vertical-ish wall
                        if abs(x0 - rx0) < abs(x1 - rx1):
                            side = "left"
                        else:
                            side = "right"
                        start = min(y0, y1)
                        end = max(y0, y1)
                    if side is not None:
                        self._record_manual_wall_erase(room_entity, side, start, end)
                except Exception:
                    continue
        except Exception:
            pass

        # Build payload for undo/redo as a delete_group
        items_payload = []
        for item_id in wall_items:
            try:
                item_type = self.canvas.type(item_id)
                coords = self.canvas.coords(item_id)
                tags = self.canvas.gettags(item_id)

                options = {}
                if item_type == "text":
                    options["text"] = self.canvas.itemcget(item_id, "text")
                    options["fill"] = self.canvas.itemcget(item_id, "fill")
                elif item_type == "line":
                    options["fill"] = self.canvas.itemcget(item_id, "fill")
                    options["width"] = self.canvas.itemcget(item_id, "width")
                elif item_type in ("oval", "rectangle", "polygon"):
                    options["fill"] = self.canvas.itemcget(item_id, "fill")
                    options["outline"] = self.canvas.itemcget(item_id, "outline")
                    options["width"] = self.canvas.itemcget(item_id, "width")

                items_payload.append(
                    {
                        "type": item_type,
                        "coords": coords,
                        "options": options,
                        "tags": tags,
                    }
                )
            except Exception:
                continue

        # Delete items from canvas (and then clear highlights)
        for item_id in wall_items:
            try:
                self.canvas.delete(item_id)
            except Exception:
                continue

        for hid in highlight_ids:
            try:
                self.canvas.delete(hid)
            except Exception:
                continue

        # Log grouped deletion for undo/redo
        if items_payload:
            try:
                self.actions.log(
                    {
                        "type": "delete_group",
                        "items": items_payload,
                    }
                )
            except Exception:
                pass
    # === Fill Tool ===
    def fill_shape(self, event):
        overlapping = self.canvas.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)
        for item_id in reversed(overlapping):
            item_type = self.canvas.type(item_id)
            if item_type in ["polygon", "rectangle", "oval"]:
                try:
                    old_color = self.canvas.itemcget(item_id, "fill")
                except Exception:
                    old_color = ""
                self.canvas.itemconfig(item_id, fill=self.fill_color)
                self.actions.log({
                    "type": "fill",
                    "item": item_id,
                    "color": self.fill_color,
                    "old_color": old_color,
                })
                # One‑click behavior: turn off fill mode and restore cursor,
                # but do not reset other tools/modes (walls, room styles, etc.).
                try:
                    self.model.set("fill_mode_enabled", False)
                except Exception:
                    pass
                try:
                    self.canvas.config(cursor="arrow")
                except Exception:
                    pass
                break

    # === Text Insertion ===
    def insert_text(self, event):
        """Show modern text insertion dialog using platform-specific UI text classes."""
        # Detect platform and use appropriate UI text class
        system = platform.system()
        try:
            self.model.set("text_insertion_mode", False)
            self.canvas.config(cursor="arrow")
        except Exception:
            pass
        
        # Create app wrapper compatible with UI text classes
        class AppWrapper:
            def __init__(self, root, canvas, model):
                self.root = root
                self.canvas = canvas
                # Create a dummy image matching canvas size for 1:1 coordinate mapping
                from PIL import Image as PILImage
                try:
                    canvas_width = max(canvas.winfo_width() or 1200, 1200)
                    canvas_height = max(canvas.winfo_height() or 800, 800)
                except:
                    canvas_width, canvas_height = 1200, 800
                self.image = PILImage.new("RGB", (canvas_width, canvas_height), "white")
                self.brush_color = getattr(model, "line_color", "#000000")
                self.zoom_factor = 1.0
                # Dummy zoom_flip_tools for coordinate conversion
                class DummyZoomFlip:
                    pan_offset = [0, 0]
                self.zoom_flip_tools = DummyZoomFlip()
                self.layout_rect = None
        
        app_wrapper = AppWrapper(self.root, self.canvas, self.model)
        
        # Store click position (canvas coordinates) in app_wrapper for dialog to access
        click_x, click_y = event.x, event.y
        app_wrapper.click_position = (click_x, click_y)
        
        def _import_local_text_tool_class(os_name: str):
            """
            Load MiniAutoCAD's UI text tool via file path to avoid `Helper` collisions in VastuApp.
            """

            def _norm(p: str) -> str:
                try:
                    return os.path.normcase(os.path.abspath(p or ""))
                except Exception:
                    return p or ""

            if os_name == "Darwin":
                rel = os.path.join("Helper", "ui_text", "mac", "ctk_text_mac.py")
                mod_name = "Helper.ui_text.mac.ctk_text_mac"
                expected_dir = os.path.join(_THIS_DIR, "Helper", "ui_text", "mac")
            else:
                # Windows + Linux fallback: ttk-based dialog
                rel = os.path.join("Helper", "ui_text", "windows", "ttkb_text_window.py")
                mod_name = "Helper.ui_text.windows.ttkb_text_window"
                expected_dir = os.path.join(_THIS_DIR, "Helper", "ui_text", "windows")

            # 1) Best case: importable and points to our local file
            try:
                module = __import__(mod_name, fromlist=["CTKTextTool"])
                cls = getattr(module, "CTKTextTool", None)
                mod_file = getattr(module, "__file__", "") or ""
                if cls is not None and _norm(mod_file).startswith(_norm(expected_dir)):
                    return cls
            except Exception:
                pass

            # 2) Fallback: file path import
            path = os.path.join(_THIS_DIR, rel)
            spec = importlib.util.spec_from_file_location("_mini_autocad_ui_text_tool", path)
            if spec is None or spec.loader is None:
                raise ModuleNotFoundError(f"Unable to load UI text tool from '{path}'")
            m = importlib.util.module_from_spec(spec)
            try:
                sys.modules[spec.name] = m
            except Exception:
                pass
            spec.loader.exec_module(m)  # type: ignore[attr-defined]
            return getattr(m, "CTKTextTool")

        try:
            CTKTextTool = _import_local_text_tool_class(system)
            text_tool = CTKTextTool(app_wrapper)

            # IMPORTANT integration fix:
            # The UI text tools were designed for a standalone canvas and they call
            # `canvas.bind(...)` + later `canvas.unbind(...)` which can wipe MiniAutoCAD's
            # controller bindings (dragging, selection, etc.).
            # We commit immediately into a real canvas text item, so we do NOT need
            # their overlay drag bindings at all.
            try:
                if hasattr(text_tool, "_set_active_text"):
                    text_tool._set_active_text = lambda *args, **kwargs: None  # type: ignore[assignment]
            except Exception:
                pass
            try:
                def _clear_overlay_without_unbind():
                    # Delete overlay items/handles but keep global canvas bindings intact.
                    for cid in list(getattr(text_tool, "active_canvas_items", []) or []):
                        try:
                            self.canvas.delete(cid)
                        except Exception:
                            pass
                    try:
                        text_tool.active_canvas_items = []
                    except Exception:
                        pass
                    for cid in list(getattr(text_tool, "active_handles", []) or []):
                        try:
                            self.canvas.delete(cid)
                        except Exception:
                            pass
                    try:
                        text_tool.active_handles = []
                    except Exception:
                        pass
                text_tool._clear_active_overlay = _clear_overlay_without_unbind  # type: ignore[assignment]
            except Exception:
                pass
                
            # Override coordinate conversion to be 1:1 (canvas = image)
            def canvas_to_image_1to1(x, y):
                return (x, y)

            def image_to_canvas_1to1(x, y):
                return (x, y)

            text_tool.canvas_to_image = canvas_to_image_1to1
            text_tool.image_to_canvas = image_to_canvas_1to1

            # Store click position in text_tool
            text_tool._click_position = app_wrapper.click_position

            # Override _create_text_overlay to use click position when position is None
            original_create_overlay = text_tool._create_text_overlay

            def adapted_create_overlay(content, bold, italic, size, color, icon="", text_box=False, position=None):
                if position is None and hasattr(text_tool, "_click_position") and text_tool._click_position:
                    click_pos = text_tool._click_position
                    img_x, img_y = text_tool.canvas_to_image(click_pos[0], click_pos[1])
                    position = (img_x, img_y)
                original_create_overlay(content, bold, italic, size, color, icon, text_box, position)
                # MiniAutoCAD behavior: commit immediately so Undo removes the text.
                try:
                    text_tool.commit_active_text()
                except Exception:
                    pass

            text_tool._create_text_overlay = adapted_create_overlay

            # Override commit to insert text on our canvas
            def adapted_commit(event=None):
                if text_tool.active_text:
                    content = text_tool.active_text.get("content", "")
                    if content.strip():
                        size = text_tool.active_text.get("size", 24)
                        color = text_tool.active_text.get("color", "#000000")
                        bold = text_tool.active_text.get("bold", False)
                        italic = text_tool.active_text.get("italic", False)

                        img_x = text_tool.active_text.get("x", click_x)
                        img_y = text_tool.active_text.get("y", click_y)
                        final_x, final_y = text_tool.image_to_canvas(img_x, img_y)

                        font_style = []
                        if bold:
                            font_style.append("bold")
                        if italic:
                            font_style.append("italic")
                        font_tuple = ("Arial", size, " ".join(font_style) if font_style else "normal")

                        text_id = self.canvas.create_text(
                            final_x,
                            final_y,
                            text=content,
                            anchor="nw",
                            fill=color,
                            font=font_tuple,
                            tags=("user_text", "user_text_editing"),
                        )
                        # Center text at click position (same as edit resize behavior)
                        try:
                            bbox = self.canvas.bbox(text_id)
                            if bbox and len(bbox) == 4:
                                w = bbox[2] - bbox[0]
                                h = bbox[3] - bbox[1]
                                self.canvas.move(text_id, -w / 2, -h / 2)
                        except Exception:
                            pass
                        self.actions.log({"type": "create", "items": [text_id]})

                    text_tool._clear_active_overlay()
                    text_tool.active_text = None

            text_tool.commit_active_text = adapted_commit
            text_tool.open_text_dialog()
                
        except Exception as e:
            print(f"Error loading UI text class: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to simple dialog
            self._insert_text_simple(event)
    
    def _insert_text_simple(self, event):
        """Simple text insertion dialog as fallback."""
        from tkinter import ttk
        
        # Helper function for placeholder text
        def add_placeholder(entry, placeholder_text, placeholder_color='gray'):
            """Add placeholder text functionality to ttk.Entry"""
            def on_focus_in(event):
                if entry.get() == placeholder_text:
                    entry.delete(0, tk.END)
                    entry.config(foreground='black')
            
            def on_focus_out(event):
                if entry.get() == '':
                    entry.insert(0, placeholder_text)
                    entry.config(foreground=placeholder_color)
            
            entry.insert(0, placeholder_text)
            entry.config(foreground=placeholder_color)
            entry.bind('<FocusIn>', on_focus_in)
            entry.bind('<FocusOut>', on_focus_out)
            
            def get_value():
                val = entry.get()
                return '' if val == placeholder_text else val
            return get_value
        
        # Create ttk dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Insert Text")
        dialog.geometry("450x220")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        set_window_icon(dialog)
        dialog.grab_set()
        dialog.attributes('-topmost', True)
        
        # Center dialog on parent window
        try:
            dialog.update_idletasks()
            parent_x = self.root.winfo_x()
            parent_y = self.root.winfo_y()
            parent_width = self.root.winfo_width()
            parent_height = self.root.winfo_height()
            dialog_width = dialog.winfo_width()
            dialog_height = dialog.winfo_height()
            x = parent_x + (parent_width // 2) - (dialog_width // 2)
            y = parent_y + (parent_height // 2) - (dialog_height // 2)
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            pass
        
        # Result storage
        result = {"text": None, "font_size": 11}
        
        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Title label
        title_label = ttk.Label(
            main_frame,
            text="Enter Text",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # Text entry with placeholder (like room creation entries)
        text_entry = ttk.Entry(
            main_frame,
            width=45,
            font=("Arial", 11)
        )
        text_entry.pack(pady=(0, 15), ipady=8, padx=5)
        
        # Add placeholder functionality (similar to CTkEntry placeholder_text)
        get_text_value = add_placeholder(text_entry, "Type your text here...")
        
        # Focus after a short delay to avoid immediate placeholder removal
        dialog.after(100, lambda: text_entry.focus_set())
        
        # Font size selection frame
        font_size_frame = ttk.Frame(main_frame)
        font_size_frame.pack(pady=(0, 15))
        
        ttk.Label(
            font_size_frame,
            text="Font Size:",
            font=("Arial", 11)
        ).pack(side="left", padx=(0, 10))
        
        font_size_var = tk.StringVar(value="11")
        font_size_combo = ttk.Combobox(
            font_size_frame,
            textvariable=font_size_var,
            values=["8", "10", "11", "12", "14", "16", "18", "20", "24", "28", "32"],
            width=8,
            state="readonly"
        )
        font_size_combo.pack(side="left")
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))

        def on_ok():
            text = get_text_value().strip()
            if text:
                result["text"] = text
                result["font_size"] = int(font_size_var.get())
                dialog.destroy()
            else:
                dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # OK button
        ok_button = ttk.Button(
            button_frame,
            text="Insert",
            command=on_ok,
            width=15
        )
        ok_button.pack(side="left", padx=(0, 10))
        
        # Cancel button
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=on_cancel,
            width=15
        )
        cancel_button.pack(side="left")
        
        # Bind Enter key to OK
        text_entry.bind("<Return>", lambda e: on_ok())
        text_entry.bind("<Escape>", lambda e: on_cancel())
        dialog.bind("<Escape>", lambda e: on_cancel())
        
        # Wait for dialog to close
        dialog.wait_window()
        
        # Insert text if provided
        if result["text"]:
            x, y = event.x, event.y
            font_size = result["font_size"]
            text_id = self.canvas.create_text(
                x, y,
                text=result["text"],
                anchor="nw",
                font=("Arial", font_size),
                tags=("user_text", "user_text_editing"),
            )
            # Center text at click position (same as main text tool)
            try:
                bbox = self.canvas.bbox(text_id)
                if bbox and len(bbox) == 4:
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                    self.canvas.move(text_id, -w / 2, -h / 2)
            except Exception:
                pass
            self.actions.log({"type": "create", "items": [text_id]})

    # === Color Pickers ===
    def pick_line_color(self):
        color = colorchooser.askcolor(parent=self.root, color=getattr(self.model, "line_color", None))[1]
        if color:
            self.model.line_color = color

    def pick_fill_color(self):
        # Native OS color dialog (Windows/macOS/Linux)
        color = colorchooser.askcolor(parent=self.root, color=self.fill_color)[1]
        if color:
            self.fill_color = color
        return color


    def select_item_by_id(self, item_id):
        # Clear existing selection highlight
        if self.selection_rectangle_id:
            self.canvas.delete(self.selection_rectangle_id)
            self.selection_rectangle_id = None

        if item_id:
            self.model.selected_item = item_id
            coords = self.canvas.bbox(item_id) # Get bounding box of the item
            if coords:
                # Draw a selection rectangle around it
                self.selection_rectangle_id = self.canvas.create_rectangle(
                    coords[0] - 2, coords[1] - 2, coords[2] + 2, coords[3] + 2,
                    outline="blue", width=1, dash=(5, 2), tags="selection_highlight"
                )
                self.canvas.tag_raise(self.selection_rectangle_id) # Ensure it's on top
        else:
            self.model.selected_item = None     


    def bring_to_front(self, item_id):
        if item_id:
            self.canvas.tag_raise(item_id)
            print(f"Item {item_id} brought to front.")

    def send_to_back(self, item_id):
        if item_id:
            # Send item towards the back, but keep it ABOVE the grid.
            # Implementation: first push to absolute bottom, then raise just above grid.
            try:
                self.canvas.tag_lower(item_id)
            except Exception:
                pass
            try:
                # If grid exists, place item just above it (so it never goes behind the grid)
                self.canvas.tag_raise(item_id, "grid")
            except Exception:
                # If grid is not present, the item is already lowered
                pass
            print(f"Item {item_id} sent to back.")

    def clear_all_drawing_items(self):
        # Get all items on the canvas
        all_items = self.canvas.find_all()
        items_to_delete = []
        for item_id in all_items:
            tags = self.canvas.gettags(item_id)
            # Only delete items that are not 'grid' or 'room_group_*'
            if "grid" not in tags and not any(tag.startswith("room_group_") for tag in tags):
                items_to_delete.append(item_id)
        
        # Also clear furniture list
        for furniture_obj in self.image_furniture_items:
            furniture_obj.delete() # Deletes image and handles
        self.image_furniture_items.clear()
        self.selected_furniture_obj = None

        for item_id in items_to_delete:
            self.canvas.delete(item_id)
        
        self.model.selected_item = None # Clear generic selection
        print("All drawing and furniture items cleared.")
        # Trigger redraw if your drawing system isn't self-healing
        self.view.redraw_all_dynamic_elements()                    

    def reset_all_canvas(self, confirm: bool = True) -> None:
        """
        Hard reset: clears the entire canvas (including rooms/polygons/furniture),
        resets zoom to 100%, clears selections/modes, and redraws the grid.

        Note: This is intentionally separate from `reset_modes()` (do not modify `reset_modes`).
        """
        if confirm:
            ok = messagebox.askyesno(
                "Reset All",
                "This will clear the entire canvas and cannot be undone.\n\nContinue?",
            )
            if not ok:
                return

        # Reset modes & transient state first (do not modify reset_modes implementation)
        try:
            self.reset_modes()
        except Exception:
            pass

        # Clear transient drawing state
        self.polygon_points = []
        self.current_preview = None
        if self.polygon_preview_line:
            try:
                self.canvas.delete(self.polygon_preview_line)
            except Exception:
                pass
            self.polygon_preview_line = None
        self.current_line_label = None
        self._active_polygon_group_tag = None
        self.freeform_points = []
        self.first_point = None

        self.measure_points = []
        self.temp_measure_items = []
        self.selection_rectangle_id = None

        # Clear Vastu transient state
        if hasattr(self, "vastu_polygon_points"):
            self.vastu_polygon_points = []
        if hasattr(self, "vastu_zones"):
            self.vastu_zones = []

        # Delete furniture (image + handles) and clear registries
        if getattr(self, "selected_furniture_obj", None):
            try:
                self.selected_furniture_obj.delete_handles()
            except Exception:
                pass
            self.selected_furniture_obj = None

        for furniture_obj in list(getattr(self, "image_furniture_items", [])):
            try:
                furniture_obj.delete()  # deletes image and handles
            except Exception:
                pass
        self.image_furniture_items = []
        self.furniture_objects = []

        # Clear room + flooring registries (canvas items will be deleted below)
        try:
            self.room_entities_by_group_tag.clear()
        except Exception:
            pass
        try:
            self.room_flooring_images.clear()
        except Exception:
            pass
        self.windows = []
        self.selected_window = None

        # Clear Trace Image variables
        if getattr(self, 'trace_manager', None):
            try:
                self.trace_manager.remove_image()
            except Exception:
                pass

        # Clear grid items first, then clear canvas fully
        grid_was_visible = True
        try:
            grid_was_visible = getattr(self.view, "grid_visible", True)
            self.view.clear_grid()
            self.view.reset_grid_pool()
        except Exception:
            pass

        self.canvas.delete("all")

        # Reset zoom (no need to rescale since canvas is empty now)
        try:
            self.model.zoom_level = 1.0
        except Exception:
            pass

        # Clear undo/redo history (reset is destructive)
        try:
            self.actions.undo_stack.clear()
            self.actions.redo_stack.clear()
        except Exception:
            pass

        # Reset label serial count
        self._polygon_label_serial = 0

        # Ensure active measurement options are enabled
        try:
            self.model.auto_polygon_dimensions = True
            self.model.auto_vastu_polygon_dimensions = True
            self.model.auto_generate_layout_dimensions = True
        except Exception:
            pass

        # Re-initialize dimension and label helpers to clear cached/stale states
        try:
            self.dimension_drawer = DimensionDrawer(self.canvas, self.model)
        except Exception:
            pass
        try:
            self.polygon_label_placer = PolygonLabelPlacer(self.canvas)
        except Exception:
            pass

        # Redraw grid and restore cursor (snap view to origin once after full wipe)
        try:
            if hasattr(self.view, "request_scroll_home_on_next_grid_draw"):
                self.view.request_scroll_home_on_next_grid_draw()
        except Exception:
            pass
        try:
            self.view.grid_visible = grid_was_visible
            if grid_was_visible:
                self.view.draw_grid()
        except Exception:
            pass
        try:
            self.canvas.config(cursor="arrow")
        except Exception:
            pass


            # === Reset All Drawing Modes ===
    def reset_modes(self):
        self.finish_entire_layout_move()
        # Reset internal flags
        self.drawing_line_mode = False
        self.polygon_mode = False
        self.polygon_points = []  # Clear unfinished polygon points
        self.eraser_mode = False
        self.furniture_mode = False
        self.window_mode = False
        self.flooring_enabled = False
        self.paste_ready = False
        self.selected_item = None
        self.selected_image_item = None
        self.freeform_points = []
        self.first_point = None
        
        # CRITICAL: Clean up temp_entry when resetting modes
        if self.temp_entry:
            try:
                self.temp_entry.destroy()
            except:
                pass
            self.temp_entry = None
        self.temp_direction = None
        self.temp_origin = None
        
        # Clean up polygon preview line
        if self.polygon_preview_line:
            try:
                self.canvas.delete(self.polygon_preview_line)
            except Exception:
                pass
            self.polygon_preview_line = None
        
        self.current_line_label = None
        self.current_preview = None
        
        # Clear guidelines
        self.guideline_helper.clear_guides()
        
        self.canvas.config(cursor="arrow")

        # Reset model-level tool modes
        self.model.set("drawing_enabled", False)
        self.model.set("polygon_mode", False)
        self.model.set("fill_mode_enabled", False)
        self.model.set("text_insertion_mode", False)
        self.model.set("furniture_mode", False)
        self.model.set("window_mode", False)
        self.model.set("eraser_mode", False)
        self.model.set("vastu_polygon_mode", False)
        self.model.set("multi_eraser_mode", False)


#=== Furniture Placement ===
    def select_furniture_item(self, name):
        self.reset_modes()
        self.model.set("furniture_mode", True)
        self.selected_furniture = name
        self.canvas.config(cursor="hand2")
        try:
            self.canvas.focus_set()
        except Exception:
            pass

    def place_furniture(self, event):
        from Furniture import Furniture, find_image_path, furniture_data
        from PIL import Image

        # Auto-commit any uncommitted furniture before placing a new one
        self.auto_commit_uncommitted_furniture()

        name = self.selected_furniture
        if not name:
            return

        path = find_image_path(name)
        if not path:
            print(f"❌ Image not found for {name}")
            return

        # Load image and remove padding to get exact furniture size
        from Furniture import remove_padding
        img = Image.open(path).convert("RGBA")
        img = remove_padding(img)  # Remove padding/transparency
        img_width, img_height = img.size

        # Get standard size in feet - normalize name for lookup (lowercase, remove spaces)
        normalized_name = name.lower().replace(" ", "")
        # Try normalized name first, then try with underscore
        real_w_ft, real_h_ft = furniture_data.STANDARD_FURNITURE_SIZES.get(normalized_name) or \
                               furniture_data.STANDARD_FURNITURE_SIZES.get(normalized_name.replace("_", "")) or \
                               furniture_data.STANDARD_FURNITURE_SIZES.get(name.lower().replace(" ", "_")) or \
                               (3, 3)
        # Standard sizes are in feet. Convert standard feet size into current active unit.
        try:
            active_unit = str(self.model.unit).lower()
            if active_unit == "m":
                conversion_factor = 1.0 / 3.28084
            elif active_unit == "cm":
                conversion_factor = 100.0 / 3.28084
            elif active_unit == "in":
                conversion_factor = 12.0
            elif active_unit == "yards":
                conversion_factor = 1.0 / 3.0
            else:
                conversion_factor = 1.0
        except Exception:
            conversion_factor = 1.0

        real_w_ft *= conversion_factor
        real_h_ft *= conversion_factor
        print(f"Placing {name} (normalized: {normalized_name}) at {event.x}, {event.y} with size {real_w_ft} {self.model.unit} x {real_h_ft} {self.model.unit}")

        # Convert to target pixel dimensions based on actual size
        # Match grid drawing formula: pixel_interval = spacing * zoom / unit_scale
        unit_factor = self.model.unit_scale[self.model.unit]
        # Calculate pixels per foot using same formula as grid drawing
        pixels_per_foot_calculated = (self.model.grid_spacing * self.model.zoom_level) / unit_factor
        
        # If visual grid appears different, we may need to adjust
        # Try to get actual visual grid spacing from canvas if possible
        # For now, use calculated value - if visual grid is different, user can tell us
        pixels_per_foot = pixels_per_foot_calculated
        
        # Calculate target pixel dimensions: furniture size in feet * pixels per foot
        # This ensures 6ft = 6 blocks visually
        target_w_px = real_w_ft * pixels_per_foot
        target_h_px = real_h_ft * pixels_per_foot
        
        # Visual grid spacing (1 block = 1 foot visually)
        visual_grid_spacing = pixels_per_foot
        
        # Debug output
        print(f"[place_furniture] Furniture: {name}, Size: {real_w_ft}ft x {real_h_ft}ft")
        print(f"[place_furniture] Image size: {img_width}x{img_height}, Target: {target_w_px:.1f}x{target_h_px:.1f}px")
        print(f"[place_furniture] Grid spacing: {self.model.grid_spacing}, Zoom: {self.model.zoom_level}, Unit factor: {unit_factor}")
        print(f"[place_furniture] Pixels per foot: {pixels_per_foot:.2f} (Visual grid: {visual_grid_spacing:.2f}px per block)")
        print(f"[place_furniture] {real_w_ft}ft should = {real_w_ft} blocks = {target_w_px:.1f}px")

        # Calculate scale based on actual furniture size
        # Ensure furniture matches the target pixel size exactly (6ft = 6 blocks)
        scale_w = target_w_px / img_width if img_width > 0 else 1.0
        scale_h = target_h_px / img_height if img_height > 0 else 1.0
        
        # For square furniture (like 6x6 bed), ensure it's exactly N blocks x N blocks
        # Use the scale that ensures the larger dimension matches exactly
        # This ensures 6ft furniture appears as exactly 6 blocks x 6 blocks
        is_square = abs(real_w_ft - real_h_ft) < 0.1
        print(f"[place_furniture] Is square furniture: {is_square} (w: {real_w_ft}, h: {real_h_ft})")
        
        if is_square:  # Square furniture (like 6x6 bed)
            # For square furniture, use max scale to ensure both dimensions are AT LEAST target size
            # This ensures 6x6 ft = exactly 6 blocks x 6 blocks (or slightly larger to maintain aspect ratio)
            scale = max(scale_w, scale_h)  # Use max to ensure both dimensions meet or exceed target
            print(f"[place_furniture] Square furniture - using max scale: {scale:.3f} to ensure {real_w_ft}ft = {real_w_ft} blocks minimum")
        else:
            # For rectangular furniture, use max scale to ensure both dimensions meet target
            # This ensures both width and height match their target sizes
            scale = max(scale_w, scale_h)  # Use max to ensure both dimensions meet or exceed target
            print(f"[place_furniture] Rectangular furniture - using max scale: {scale:.3f} to ensure both dimensions match target")
        
        print(f"[place_furniture] Calculated scale: {scale:.3f} (w: {scale_w:.3f}, h: {scale_h:.3f})")
        final_w = img_width * scale
        final_h = img_height * scale
        print(f"[place_furniture] Final size: {final_w:.1f}x{final_h:.1f}px (Target: {target_w_px:.1f}x{target_h_px:.1f}px)")
        print(f"[place_furniture] Should be {real_w_ft} blocks x {real_h_ft} blocks = {target_w_px:.1f}x{target_h_px:.1f}px")
        scale = max(0.05, min(scale, 20.0))  # Allow scale up to 20.0 for proper sizing

        # For all furniture, pass target_size to force exact target dimensions
        target_size = (int(target_w_px), int(target_h_px))  # Force exact size for all furniture
        if is_square:
            print(f"[place_furniture] Forcing square furniture to exact size: {target_size}")
        else:
            print(f"[place_furniture] Forcing rectangular furniture to exact size: {target_size}")

        furniture_item = Furniture(
            canvas=self.canvas,
            image_path=path,
            x=event.x,
            y=event.y,
            select_callback=self.select_image_item,
            scale=scale,
            angle=0,
            get_freeze_state=lambda: self.canvas_frozen,
            edit_callback=self.enter_furniture_edit_mode,
            duplicate_callback=self.duplicate_furniture,
            delete_callback=self.delete_furniture_item,
            target_size=target_size,  # Pass target size for square furniture
        )
        
        # Store real size in feet and model reference for zoom updates
        furniture_item.real_size_ft = (real_w_ft, real_h_ft)
        furniture_item.model_ref = self.model

        self.image_furniture_items.append(furniture_item)
        self.select_image_item(furniture_item)
        self.canvas.itemconfig(furniture_item.image_id, tags=("furniture",))
        try:
            self.select_item_by_id(None)
        except Exception:
            pass

        # Check if placed furniture is a door and cut wall if needed
        if "door" in name.lower():
            # Mark for dynamic re-cutting when moved
            try:
                setattr(furniture_item, "is_door", True)
            except Exception:
                pass
            self._cut_wall_for_door(furniture_item, real_w_ft, real_h_ft)
            # Ensure furniture (door) stays on top after wall cutting
            try:
                self.canvas.tag_raise(furniture_item.image_id)
            except Exception:
                pass

        # By default, lock furniture: user must right-click → Edit before direct editing.
        # First, try to commit to an underlying room/polygon so it follows group drags.
        locked = False
        try:
            ok = self.commit_furniture_to_underlying_group(furniture_item)
            locked = bool(ok)
        except Exception:
            locked = False
        if not locked:
            try:
                furniture_item.committed = True
                furniture_item.editing = False
            except Exception:
                pass

        # Log furniture placement for undo
        self.actions.log({
            "type": "create_furniture",
            "image_id": furniture_item.image_id,
            "image_path": path,
            "x": event.x,
            "y": event.y,
            "scale": scale,
            "angle": 0,
            "initial_angle": furniture_item.initial_angle,
            "real_size_ft": (real_w_ft, real_h_ft),
            "target_size": target_size,
        })

        self.selected_furniture = None
        self.model.set("furniture_mode", False)
        self.canvas.config(cursor="arrow")
        

    def select_image_item(self, furniture_item):
        if self.selected_furniture_obj and self.selected_furniture_obj != furniture_item:
            self.selected_furniture_obj.is_selected = False
            self.selected_furniture_obj.delete_handles()
            self.selected_furniture_obj.delete_highlight()

        self.selected_furniture_obj = furniture_item
        furniture_item.is_selected = True
        self.clear_window_selection()
        furniture_item.draw_highlight()
        # Show handles only when furniture is in edit mode (not committed/locked)
        try:
            if getattr(furniture_item, "committed", False) and not getattr(furniture_item, "editing", False):
                furniture_item.delete_handles()
            else:
                furniture_item.draw_handles()
        except Exception:
            furniture_item.draw_handles()
        try:
            self.canvas.focus_set()
        except Exception:
            pass

    def clear_furniture_selection(self):
        obj = getattr(self, "selected_furniture_obj", None)
        if obj:
            obj.is_selected = False
            obj.delete_handles()
            obj.delete_highlight()
        self.selected_furniture_obj = None

    def finish_entire_layout_move(self):
        tag = getattr(self, "_entire_layout_tag", None)
        if tag:
            try:
                self.canvas.dtag("all", tag)
            except Exception:
                pass
        if getattr(self, "_entire_layout_outline_id", None):
            try:
                self.canvas.delete(self._entire_layout_outline_id)
            except Exception:
                pass
        self.layout_move_mode = False
        self._entire_layout_tag = None
        self._entire_layout_outline_id = None
        self._entire_layout_state_scope = None
        try:
            self.canvas.config(cursor="arrow")
        except Exception:
            pass

    def select_entire_layout(self, item_ids=None, state_scope=None):
        """Select the whole design, or supplied copied items, as one movable group."""
        requested_ids = list(item_ids) if item_ids is not None else None
        self.reset_modes()
        self.clear_furniture_selection()
        excluded = {
            "grid", "furniture_resize_handle", "furniture_selection_highlight",
            "selection_highlight", "active_preview", "active_snap_indicator",
            "multi_erase_rect", "multi_erase_highlight", "wall_erase_preview",
            "screenshot_region", "measure_temp", "measure_dot", "guideline_info",
            "polygon_shape_preview", "polygon_preview_line", "polygon_preview_label",
            "vastu_polygon_temp", "vastu_polygon_preview", "vastu_preview_line",
            "trace_image",
        }
        candidates = requested_ids if requested_ids is not None else list(self.canvas.find_all())
        tag = f"entire_layout_{uuid.uuid4().hex[:10]}"
        selected_ids = []
        for item in candidates:
            try:
                if not self.canvas.type(item):
                    continue
                tags = set(self.canvas.gettags(item))
                if requested_ids is None and (tags & excluded or any(t.startswith("guideline") for t in tags)):
                    continue
                self.canvas.addtag_withtag(tag, item)
                selected_ids.append(item)
            except Exception:
                continue
        bbox = self.canvas.bbox(tag) if selected_ids else None
        if not bbox:
            show_message("info", "Move Layout", "There is no layout to move.")
            return False
        self._entire_layout_outline_id = self.canvas.create_rectangle(
            bbox[0] - 8, bbox[1] - 8, bbox[2] + 8, bbox[3] + 8,
            fill="", outline="#FACC15", width=3, dash=(8, 4),
            tags=(tag, "entire_layout_outline"),
        )
        self.canvas.tag_raise(self._entire_layout_outline_id)
        self.layout_move_mode = True
        self._entire_layout_tag = tag
        self._entire_layout_state_scope = state_scope
        if state_scope is not None:
            state_scope["selection_outline_id"] = self._entire_layout_outline_id
        self.canvas.config(cursor="fleur")
        message = "Drag the highlighted copy to place it. Press Escape when finished." if state_scope else "Drag any part of the highlighted layout. Press Escape when finished."
        show_message("info", "Move Layout", message)
        return True

    def shift_entire_layout_state(self, dx, dy, scope=None):
        """Keep geometry caches and duplicate replay data aligned with a layout move."""
        dx, dy = float(dx), float(dy)
        scope = self._entire_layout_state_scope if scope is None else scope
        polygon_tags = set(scope.get("polygon_tags", [])) if scope else None
        line_tags = set(scope.get("line_tags", [])) if scope else None
        room_tags = set(scope.get("room_tags", [])) if scope else None
        window_ids = set(scope.get("window_ids", [])) if scope else None
        for group_tag, baseline in list(self._polygon_baseline_coords_by_group.items()):
            if polygon_tags is not None and group_tag not in polygon_tags:
                continue
            self._polygon_baseline_coords_by_group[group_tag] = [
                float(value) + (dx if index % 2 == 0 else dy)
                for index, value in enumerate(baseline)
            ]
        for line_tag, meta in self.line_metadata.items():
            if line_tags is not None and line_tag not in line_tags:
                continue
            for key in ("x0", "x1"):
                if key in meta:
                    meta[key] = float(meta[key]) + dx
            for key in ("y0", "y1"):
                if key in meta:
                    meta[key] = float(meta[key]) + dy
        zoom = max(float(getattr(self.model, "zoom_level", 1.0)), 1e-9)
        for window in self.windows:
            if scope and window.get("id") not in window_ids and window.get("room_group_tag") not in room_tags:
                continue
            delta = dx / zoom if window.get("wall_side") in ("top", "bottom") else dy / zoom
            window["start"] = float(window.get("start", 0)) + delta
            window["end"] = float(window.get("end", 0)) + delta

        data = scope.get("data") if scope and scope.get("type") == "duplicate_layout" else None
        if isinstance(data, dict):
            for room in data.get("rooms", []):
                for key in ("x0", "x1", "x"):
                    if key in room:
                        room[key] = float(room[key]) + dx
                for key in ("y0", "y1", "y"):
                    if key in room:
                        room[key] = float(room[key]) + dy
                for side, intervals in (room.get("wall_erased_regions") or {}).items():
                    delta = dx / zoom if side in ("top", "bottom") else dy / zoom
                    for interval in intervals:
                        interval[0], interval[1] = float(interval[0]) + delta, float(interval[1]) + delta
            for shape in data.get("shapes", []):
                shape["points"] = [
                    [float(point[0]) + dx, float(point[1]) + dy]
                    for point in shape.get("points", [])
                ]
            for furniture in data.get("furniture", []):
                furniture["x"] = float(furniture.get("x", 0)) + dx
                furniture["y"] = float(furniture.get("y", 0)) + dy
            unit_scale = float(self.model.unit_scale.get(self.model.unit, 1.0))
            real_dx = dx / (float(self.model.grid_spacing) * zoom) * unit_scale
            real_dy = dy / (float(self.model.grid_spacing) * zoom) * unit_scale
            for text in data.get("text", []):
                if text.get("x_real") is not None and text.get("y_real") is not None:
                    text["x_real"] = float(text["x_real"]) + real_dx
                    text["y_real"] = float(text["y_real"]) + real_dy
                else:
                    text["x"] = float(text.get("x", 0)) + dx
                    text["y"] = float(text.get("y", 0)) + dy
            for window in data.get("windows", []):
                delta = dx / zoom if window.get("wall_side") in ("top", "bottom") else dy / zoom
                window["start"] = float(window.get("start", 0)) + delta
                window["end"] = float(window.get("end", 0)) + delta
        try:
            self.shift_vastu_slice_baseline(dx, dy, set(scope.get("item_ids", [])) if scope else None)
        except Exception:
            pass

    def delete_selected(self):
        """Delete the current semantic selection, including an auto-selected layout copy."""
        scope = getattr(self, "_entire_layout_state_scope", None)
        serializer = getattr(self.actions, "serializer", None)
        if scope and scope.get("type") == "duplicate_layout" and serializer:
            serializer._remove_duplicated_layout(scope)
            self.actions.log({"type": "delete_duplicated_layout", "scope": scope})
            return True
        obj = getattr(self, "selected_furniture_obj", None)
        if obj:
            return self.delete_furniture_item(obj)
        if self.selected_window:
            return self.delete_selected_window()
        return False

    def delete_selected_furniture(self):
        if self.selected_furniture_obj:
            self.selected_furniture_obj.delete_handles()
            self.selected_furniture_obj.delete_highlight()
            self.selected_furniture_obj.delete()
            self.image_furniture_items.remove(self.selected_furniture_obj)
            self.selected_furniture_obj = None
        
    def _cut_wall_for_door(self, door_item, door_width_ft, door_height_ft):
        """
        Cut 0.4 ft from the wall in front of a door when it's placed.
        Only cuts the area covered by the door image.
        """
        try:
            print(f"[DEBUG] _cut_wall_for_door called for door")
            
            # Get door position and bounding box
            door_coords = self.canvas.coords(door_item.image_id)
            if not door_coords or len(door_coords) < 2:
                print(f"[DEBUG] No door coordinates found")
                return
            
            door_x, door_y = door_coords[0], door_coords[1]
            print(f"[DEBUG] Door position: ({door_x}, {door_y})")
            
            # Calculate door dimensions in pixels
            unit_factor = self.model.unit_scale[self.model.unit]
            pixels_per_foot = (self.model.grid_spacing * self.model.zoom_level) / unit_factor
            
            # Get door's actual size in pixels (accounting for rotation)
            door_w_px = door_width_ft * pixels_per_foot
            door_h_px = door_height_ft * pixels_per_foot
            
            # Calculate door bounding box (accounting for rotation)
            # For simplicity, use a bounding box that covers the door
            door_bbox = {
                'x0': door_x - door_w_px / 2,
                'y0': door_y - door_h_px / 2,
                'x1': door_x + door_w_px / 2,
                'y1': door_y + door_h_px / 2
            }
            print(f"[DEBUG] Door bbox: x0={door_bbox['x0']:.1f}, y0={door_bbox['y0']:.1f}, x1={door_bbox['x1']:.1f}, y1={door_bbox['y1']:.1f}")
            
            # Find which room the door is near/on (check all rooms, not just walls_only)
            containing_room = None
            min_distance = float('inf')
            
            print(f"[DEBUG] Checking {len(self.room_entities_by_group_tag)} rooms")
            for group_tag, room_entity in self.room_entities_by_group_tag.items():
                # Get current room coordinates (may have been moved)
                room_coords = self.canvas.coords(room_entity.rect_id)
                if len(room_coords) < 4:
                    continue
                
                room_x0, room_y0, room_x1, room_y1 = room_coords[0], room_coords[1], room_coords[2], room_coords[3]
                
                # Check if door is near or on the room (including walls)
                # Door can be on wall edge, so check with tolerance
                tolerance = 50  # pixels tolerance for wall edge detection
                if (room_x0 - tolerance <= door_x <= room_x1 + tolerance and 
                    room_y0 - tolerance <= door_y <= room_y1 + tolerance):
                    # Calculate distance to room center
                    room_center_x = (room_x0 + room_x1) / 2
                    room_center_y = (room_y0 + room_y1) / 2
                    distance = ((door_x - room_center_x)**2 + (door_y - room_center_y)**2)**0.5
                    
                    if distance < min_distance:
                        min_distance = distance
                        containing_room = room_entity
                        print(f"[DEBUG] Found room: {room_entity.name}, distance: {distance:.1f}")
            
            # Also check polygon walls if no room found or door is on polygon edge
            containing_polygon = None
            if not containing_room:
                print(f"[DEBUG] No room found, checking polygons...")
                # Find polygon that contains or is near the door
                from vastu_geometry import VastuPolygonGenerator
                all_polygons = self.canvas.find_withtag("polygon_shape")
                for poly_item in all_polygons:
                    # Get polygon group tag first
                    poly_tags = self.canvas.gettags(poly_item)
                    polygon_group_tag = None
                    for tag in poly_tags:
                        if tag.startswith("polygon_group_"):
                            polygon_group_tag = tag
                            break
                    
                    if not polygon_group_tag:
                        continue
                    
                    # Use baseline coordinates if available (original polygon before door cuts)
                    # This ensures consistent detection even after first door modifies the polygon
                    if polygon_group_tag in self._polygon_baseline_coords_by_group:
                        poly_coords = self._polygon_baseline_coords_by_group[polygon_group_tag]
                        print(f"[DEBUG] Using baseline coordinates for polygon detection")
                    else:
                        # Fallback to current coordinates if baseline not stored yet
                        poly_coords = self.canvas.coords(poly_item)
                        print(f"[DEBUG] Using current coordinates for polygon detection (baseline not stored)")
                    
                    if len(poly_coords) < 6:  # Need at least 3 points
                        continue
                    # Convert to list of points
                    poly_points = [(poly_coords[i], poly_coords[i+1]) for i in range(0, len(poly_coords), 2)]
                    # Check if door is near polygon edge
                    if VastuPolygonGenerator.point_in_polygon((door_x, door_y), poly_points):
                        containing_polygon = polygon_group_tag
                        print(f"[DEBUG] Found polygon: {polygon_group_tag}")
                        break
            
            if not containing_room and not containing_polygon:
                print(f"[DEBUG] No room or polygon found near door")
                return
            
            # Process room wall cutting
            if containing_room:
                print(f"[DEBUG] Using room: {containing_room.name}, fill_mode: {containing_room.fill_mode}")
                
                # Get room coordinates
                room_coords = self.canvas.coords(containing_room.rect_id)
                if len(room_coords) < 4:
                    return
                
                room_x0, room_y0, room_x1, room_y1 = room_coords[0], room_coords[1], room_coords[2], room_coords[3]
                wall_thickness = containing_room._wall_thickness_pixels()
                cut_depth_ft = 0.4  # Cut 0.4 ft from wall
                cut_depth_px = cut_depth_ft * pixels_per_foot
                
                print(f"[DEBUG] Room coords: ({room_x0:.1f}, {room_y0:.1f}) to ({room_x1:.1f}, {room_y1:.1f})")
                print(f"[DEBUG] Wall thickness: {wall_thickness:.1f}px, Cut depth: {cut_depth_px:.1f}px")
                
                # Determine which wall the door is on and cut it (only for walls_only rooms)
                # Check distance to each wall edge
                dist_to_top = abs(door_y - room_y0)
                dist_to_bottom = abs(door_y - room_y1)
                dist_to_left = abs(door_x - room_x0)
                dist_to_right = abs(door_x - room_x1)
                
                print(f"[DEBUG] Distances - Top: {dist_to_top:.1f}, Bottom: {dist_to_bottom:.1f}, Left: {dist_to_left:.1f}, Right: {dist_to_right:.1f}")
                
                # Find closest wall (within wall thickness + some tolerance)
                tolerance = wall_thickness + 20  # pixels - increased tolerance
                wall_to_cut = None
                cut_start = None
                cut_end = None
                
                # Find all rooms that share this wall (adjacent rooms)
                # Only consider rooms that are explicitly walls_only
                rooms_to_cut = []
                if getattr(containing_room, "fill_mode", "") == "walls_only":
                    rooms_to_cut.append(containing_room)
                
                if dist_to_top < tolerance and dist_to_top <= min(dist_to_bottom, dist_to_left, dist_to_right):
                    # Door on top wall - find room whose bottom wall aligns with this top wall
                    wall_to_cut = "top"
                    # Intersect door bbox with room boundaries to get valid cut range
                    # Door might be partially outside room, so clamp to room boundaries
                    cut_start = max(room_x0, door_bbox['x0'])
                    cut_end = min(room_x1, door_bbox['x1'])
                    # If cut range is invalid (door outside room), use door center projected onto wall
                    if cut_start >= cut_end:
                        door_center_x = (door_bbox['x0'] + door_bbox['x1']) / 2
                        door_width = door_w_px
                        # Clamp door center to room boundaries
                        clamped_center_x = max(room_x0 + door_width / 2, min(room_x1 - door_width / 2, door_center_x))
                        cut_start = clamped_center_x - door_width / 2
                        cut_end = clamped_center_x + door_width / 2
                        # Final clamp to ensure within room
                        cut_start = max(room_x0, cut_start)
                        cut_end = min(room_x1, cut_end)
                    print(f"[DEBUG] Door on TOP wall, cut from x={cut_start:.1f} to x={cut_end:.1f}")
                    
                    # Find adjacent room sharing this wall (bottom wall of adjacent room = top wall of this room)
                    wall_alignment_tolerance = wall_thickness + 5  # pixels
                    for group_tag, other_room in self.room_entities_by_group_tag.items():
                        if other_room == containing_room:
                            continue
                        other_coords = self.canvas.coords(other_room.rect_id)
                        if len(other_coords) < 4:
                            continue
                        other_x0, other_y0, other_x1, other_y1 = other_coords[0], other_coords[1], other_coords[2], other_coords[3]
                        # Check if other room's bottom wall aligns with this room's top wall
                        if (abs(other_y1 - room_y0) < wall_alignment_tolerance and
                            not (other_x1 < room_x0 or other_x0 > room_x1)):  # Walls overlap horizontally
                            print(f"[DEBUG] Found adjacent room: {other_room.name} sharing top/bottom wall")
                            rooms_to_cut.append(other_room)
                    
                    # Cut wall for all rooms sharing this wall
                    # Handle each room based on its fill_mode
                    for room in rooms_to_cut:
                        room_coords = self.canvas.coords(room.rect_id)
                        if len(room_coords) < 4:
                            continue
                        r_x0, r_y0, r_x1, r_y1 = room_coords[0], room_coords[1], room_coords[2], room_coords[3]
                        # Adjust cut coordinates for this room's boundaries
                        room_cut_start = max(r_x0, cut_start)
                        room_cut_end = min(r_x1, cut_end)
                        
                        # Skip if cut range is invalid
                        if room_cut_start >= room_cut_end:
                            print(f"[DEBUG] Skipping room {room.name}: invalid cut range")
                            continue
                        
                        # Determine which wall to cut for this room
                        # If this is the containing room, cut top wall; if adjacent, cut bottom wall
                        wall_side = "top" if room == containing_room else "bottom"
                        
                        print(f"[DEBUG] Cutting {wall_side} wall for room {room.name} (fill_mode: {room.fill_mode})")
                        
                        # Handle based on room type - only walls_only rooms are cut
                        if getattr(room, "fill_mode", "") == "walls_only":
                            # For walls_only mode, cut the specific wall segment
                            if wall_side == "top":
                                wall_cut = False
                                # First try the stored wall_id if it exists
                                if hasattr(room, 'top_wall_id') and self._item_exists(room.top_wall_id):
                                    try:
                                        if self.canvas.type(room.top_wall_id) == "rectangle":
                                            # Check if this wall segment overlaps with the cut area
                                            wall_coords = self.canvas.coords(room.top_wall_id)
                                            if len(wall_coords) >= 4:
                                                wall_x0, wall_x1 = wall_coords[0], wall_coords[2]
                                                # Check if cut overlaps with this wall segment
                                                if not (room_cut_end < wall_x0 or room_cut_start > wall_x1):
                                                    self._cut_wall_segment(room.top_wall_id, room_cut_start, room_cut_end, cut_depth_px, "top", r_y0)
                                                    wall_cut = True
                                    except tk.TclError:
                                        print(f"[DEBUG] top_wall_id {room.top_wall_id} no longer exists, finding by tag")
                                        pass
                                
                                # If wall_id doesn't exist or wasn't found, find ALL segments on this wall line by tag
                                if not wall_cut:
                                    wall_items = self.canvas.find_withtag(room.group_tag)
                                    for item in wall_items:
                                        try:
                                            if self.canvas.type(item) == "rectangle":
                                                coords = self.canvas.coords(item)
                                                if len(coords) >= 4:
                                                    # Check if this rectangle is on the top wall (same Y position)
                                                    item_y0, item_y1 = coords[1], coords[3]
                                                    if abs(item_y0 - r_y0) < 2 and abs(item_y1 - (r_y0 + wall_thickness)) < 2:
                                                        item_x0, item_x1 = coords[0], coords[2]
                                                        # Check if cut overlaps with this wall segment
                                                        if not (room_cut_end < item_x0 or room_cut_start > item_x1):
                                                            self._cut_wall_segment(item, room_cut_start, room_cut_end, cut_depth_px, "top", r_y0)
                                                            wall_cut = True
                                                            # Don't break - there might be multiple segments to cut
                                        except tk.TclError:
                                            # Item was deleted, skip it
                                            continue
                                
                                if not wall_cut:
                                    print(f"[DEBUG] Warning: Could not find top wall for room {room.name}")
                            else:  # bottom
                                wall_cut = False
                                if hasattr(room, 'bottom_wall_id') and self._item_exists(room.bottom_wall_id):
                                    try:
                                        if self.canvas.type(room.bottom_wall_id) == "rectangle":
                                            self._cut_wall_segment(room.bottom_wall_id, room_cut_start, room_cut_end, cut_depth_px, "bottom", r_y1)
                                            wall_cut = True
                                    except tk.TclError:
                                        print(f"[DEBUG] bottom_wall_id {room.bottom_wall_id} no longer exists, finding by tag")
                                        pass
                                
                                # If wall_id doesn't exist or wasn't found, find by tag
                                if not wall_cut:
                                    wall_items = self.canvas.find_withtag(room.group_tag)
                                    for item in wall_items:
                                        try:
                                            if self.canvas.type(item) == "rectangle":
                                                coords = self.canvas.coords(item)
                                                if len(coords) >= 4:
                                                    if abs(coords[1] - (r_y1 - wall_thickness)) < 2 and abs(coords[3] - r_y1) < 2:
                                                        self._cut_wall_segment(item, room_cut_start, room_cut_end, cut_depth_px, "bottom", r_y1)
                                                        wall_cut = True
                                                        break
                                        except tk.TclError:
                                            # Item was deleted, skip it
                                            continue
                                
                                if not wall_cut:
                                    print(f"[DEBUG] Warning: Could not find bottom wall for room {room.name}")
                        else:
                            print(f"[DEBUG] Warning: Unknown fill_mode '{room.fill_mode}' for room {room.name}")
                    
                    # Skip the old single-room cutting logic below
                    return
                
                elif dist_to_bottom < tolerance and dist_to_bottom <= min(dist_to_top, dist_to_left, dist_to_right):
                    # Door on bottom wall - find room whose top wall aligns with this bottom wall
                    wall_to_cut = "bottom"
                    # Intersect door bbox with room boundaries to get valid cut range
                    cut_start = max(room_x0, door_bbox['x0'])
                    cut_end = min(room_x1, door_bbox['x1'])
                    # If cut range is invalid (door outside room), use door center projected onto wall
                    if cut_start >= cut_end:
                        door_center_x = (door_bbox['x0'] + door_bbox['x1']) / 2
                        door_width = door_w_px
                        # Clamp door center to room boundaries
                        clamped_center_x = max(room_x0 + door_width / 2, min(room_x1 - door_width / 2, door_center_x))
                        cut_start = clamped_center_x - door_width / 2
                        cut_end = clamped_center_x + door_width / 2
                        # Final clamp to ensure within room
                        cut_start = max(room_x0, cut_start)
                        cut_end = min(room_x1, cut_end)
                    print(f"[DEBUG] Door on BOTTOM wall, cut from x={cut_start:.1f} to x={cut_end:.1f}")
                    
                    # Find adjacent room sharing this wall (top wall of adjacent room = bottom wall of this room)
                    wall_alignment_tolerance = wall_thickness + 5  # pixels
                    for group_tag, other_room in self.room_entities_by_group_tag.items():
                        if other_room == containing_room:
                            continue
                        other_coords = self.canvas.coords(other_room.rect_id)
                        if len(other_coords) < 4:
                            continue
                        other_x0, other_y0, other_x1, other_y1 = other_coords[0], other_coords[1], other_coords[2], other_coords[3]
                        # Check if other room's top wall aligns with this room's bottom wall
                        if (abs(other_y0 - room_y1) < wall_alignment_tolerance and
                            not (other_x1 < room_x0 or other_x0 > room_x1)):  # Walls overlap horizontally
                            print(f"[DEBUG] Found adjacent room: {other_room.name} sharing bottom/top wall")
                            rooms_to_cut.append(other_room)
                    
                    # Cut wall for all rooms sharing this wall
                    # Handle each room based on its fill_mode
                    for room in rooms_to_cut:
                        room_coords = self.canvas.coords(room.rect_id)
                        if len(room_coords) < 4:
                            continue
                        r_x0, r_y0, r_x1, r_y1 = room_coords[0], room_coords[1], room_coords[2], room_coords[3]
                        # Adjust cut coordinates for this room's boundaries
                        room_cut_start = max(r_x0, cut_start)
                        room_cut_end = min(r_x1, cut_end)
                        
                        # Skip if cut range is invalid
                        if room_cut_start >= room_cut_end:
                            print(f"[DEBUG] Skipping room {room.name}: invalid cut range")
                            continue
                        
                        # Determine which wall to cut for this room
                        # If this is the containing room, cut bottom wall; if adjacent, cut top wall
                        wall_side = "bottom" if room == containing_room else "top"
                        
                        print(f"[DEBUG] Cutting {wall_side} wall for room {room.name} (fill_mode: {room.fill_mode})")
                        
                        # Handle based on room type - only walls_only rooms are cut
                        if getattr(room, "fill_mode", "") == "walls_only":
                            # For walls_only mode, cut the specific wall segment
                            if wall_side == "bottom":
                                wall_cut = False
                                # Find ALL wall segments on bottom wall that overlap with cut area
                                wall_items = self.canvas.find_withtag(room.group_tag)
                                segments_to_cut = []
                                
                                for item in wall_items:
                                    try:
                                        if self.canvas.type(item) == "rectangle":
                                            coords = self.canvas.coords(item)
                                            if len(coords) >= 4:
                                                item_x0, item_y0, item_x1, item_y1 = coords[0], coords[1], coords[2], coords[3]
                                                # Check if this is a bottom wall segment (same Y position)
                                                if abs(item_y0 - (r_y1 - wall_thickness)) < 2 and abs(item_y1 - r_y1) < 2:
                                                    # Check if this segment overlaps with cut area
                                                    if not (item_x1 < room_cut_start or item_x0 > room_cut_end):
                                                        # Segment overlaps with cut area - add to list
                                                        segments_to_cut.append(item)
                                    except tk.TclError:
                                        # Item was deleted, skip it
                                        continue
                                
                                # Cut all overlapping segments (door-induced gaps – do NOT record as manual)
                                for segment_item in segments_to_cut:
                                    try:
                                        self._cut_wall_segment(segment_item, room_cut_start, room_cut_end, cut_depth_px, "bottom", r_y1)
                                        wall_cut = True
                                    except Exception as e:
                                        print(f"[DEBUG] Error cutting bottom wall segment: {e}")
                                        continue
                                
                                if not wall_cut:
                                    print(f"[DEBUG] Warning: Could not find bottom wall segments overlapping cut area for room {room.name}")
                            else:  # top
                                wall_cut = False
                                # Find ALL wall segments on top wall that overlap with cut area
                                wall_items = self.canvas.find_withtag(room.group_tag)
                                segments_to_cut = []
                                
                                for item in wall_items:
                                    try:
                                        if self.canvas.type(item) == "rectangle":
                                            coords = self.canvas.coords(item)
                                            if len(coords) >= 4:
                                                item_x0, item_y0, item_x1, item_y1 = coords[0], coords[1], coords[2], coords[3]
                                                # Check if this is a top wall segment (same Y position)
                                                if abs(item_y0 - r_y0) < 2 and abs(item_y1 - (r_y0 + wall_thickness)) < 2:
                                                    # Check if this segment overlaps with cut area
                                                    if not (item_x1 < room_cut_start or item_x0 > room_cut_end):
                                                        # Segment overlaps with cut area - add to list
                                                        segments_to_cut.append(item)
                                    except tk.TclError:
                                        # Item was deleted, skip it
                                        continue
                                
                                # Cut all overlapping segments (door-induced gaps – do NOT record as manual)
                                for segment_item in segments_to_cut:
                                    try:
                                        self._cut_wall_segment(segment_item, room_cut_start, room_cut_end, cut_depth_px, "top", r_y0)
                                        wall_cut = True
                                    except Exception as e:
                                        print(f"[DEBUG] Error cutting top wall segment: {e}")
                                        continue
                                
                                if not wall_cut:
                                    print(f"[DEBUG] Warning: Could not find top wall segments overlapping cut area for room {room.name}")
                        else:
                            print(f"[DEBUG] Warning: Unknown fill_mode '{room.fill_mode}' for room {room.name}")
                    
                    # Skip the old single-room cutting logic below
                    return
                
                elif dist_to_left < tolerance and dist_to_left <= min(dist_to_top, dist_to_bottom, dist_to_right):
                    # Door on left wall - find room whose right wall aligns with this left wall
                    wall_to_cut = "left"
                    # Intersect door bbox with room boundaries to get valid cut range
                    cut_start = max(room_y0, door_y - door_w_px / 2)
                    cut_end = min(room_y1, door_y + door_w_px / 2)
                    # If cut range is invalid (door outside room), use door center projected onto wall
                    if cut_start >= cut_end:
                        door_center_y = door_y
                        door_height = door_w_px
                        # Clamp door center to room boundaries
                        clamped_center_y = max(room_y0 + door_height / 2, min(room_y1 - door_height / 2, door_center_y))
                        cut_start = clamped_center_y - door_height / 2
                        cut_end = clamped_center_y + door_height / 2
                        # Final clamp to ensure within room
                        cut_start = max(room_y0, cut_start)
                        cut_end = min(room_y1, cut_end)
                    print(f"[DEBUG] Door on LEFT wall, cut from y={cut_start:.1f} to y={cut_end:.1f}")
                    
                    # Find adjacent room sharing this wall (right wall of adjacent room = left wall of this room)
                    wall_alignment_tolerance = wall_thickness + 5  # pixels
                    for group_tag, other_room in self.room_entities_by_group_tag.items():
                        if other_room == containing_room:
                            continue
                        other_coords = self.canvas.coords(other_room.rect_id)
                        if len(other_coords) < 4:
                            continue
                        other_x0, other_y0, other_x1, other_y1 = other_coords[0], other_coords[1], other_coords[2], other_coords[3]
                        # Check if other room's right wall aligns with this room's left wall
                        if (abs(other_x1 - room_x0) < wall_alignment_tolerance and
                            not (other_y1 < room_y0 or other_y0 > room_y1)):  # Walls overlap vertically
                            print(f"[DEBUG] Found adjacent room: {other_room.name} sharing left/right wall")
                            rooms_to_cut.append(other_room)
                    
                    # Cut wall for all rooms sharing this wall
                    # Handle each room based on its fill_mode
                    for room in rooms_to_cut:
                        room_coords = self.canvas.coords(room.rect_id)
                        if len(room_coords) < 4:
                            continue
                        r_x0, r_y0, r_x1, r_y1 = room_coords[0], room_coords[1], room_coords[2], room_coords[3]
                        # Adjust cut coordinates for this room's boundaries
                        room_cut_start = max(r_y0, cut_start)
                        room_cut_end = min(r_y1, cut_end)
                        
                        # Skip if cut range is invalid
                        if room_cut_start >= room_cut_end:
                            print(f"[DEBUG] Skipping room {room.name}: invalid cut range")
                            continue
                        
                        # Determine which wall to cut for this room
                        # If this is the containing room, cut left wall; if adjacent, cut right wall
                        wall_side = "left" if room == containing_room else "right"
                        
                        print(f"[DEBUG] Cutting {wall_side} wall for room {room.name} (fill_mode: {room.fill_mode})")
                        
                        # Handle based on room type - only walls_only rooms are cut
                        if getattr(room, "fill_mode", "") == "walls_only":
                            # For walls_only mode, cut the specific wall segment
                            if wall_side == "left":
                                wall_cut = False
                                # Find ALL wall segments on left wall that overlap with cut area
                                wall_items = self.canvas.find_withtag(room.group_tag)
                                segments_to_cut = []
                                
                                for item in wall_items:
                                    try:
                                        if self.canvas.type(item) == "rectangle":
                                            coords = self.canvas.coords(item)
                                            if len(coords) >= 4:
                                                item_x0, item_y0, item_x1, item_y1 = coords[0], coords[1], coords[2], coords[3]
                                                # Check if this is a left wall segment (same X position)
                                                if abs(item_x0 - r_x0) < 2 and abs(item_x1 - (r_x0 + wall_thickness)) < 2:
                                                    # Check if this segment overlaps with cut area
                                                    if not (item_y1 < room_cut_start or item_y0 > room_cut_end):
                                                        # Segment overlaps with cut area - add to list
                                                        segments_to_cut.append(item)
                                    except tk.TclError:
                                        # Item was deleted, skip it
                                        continue
                                
                                # Cut all overlapping segments (door-induced gaps – do NOT record as manual)
                                for segment_item in segments_to_cut:
                                    try:
                                        self._cut_wall_segment(segment_item, room_cut_start, room_cut_end, cut_depth_px, "left", r_x0)
                                        wall_cut = True
                                    except Exception as e:
                                        print(f"[DEBUG] Error cutting left wall segment: {e}")
                                        continue
                                
                                if not wall_cut:
                                    print(f"[DEBUG] Warning: Could not find left wall segments overlapping cut area for room {room.name}")
                            else:  # right
                                wall_cut = False
                                # Find ALL wall segments on right wall that overlap with cut area
                                wall_items = self.canvas.find_withtag(room.group_tag)
                                segments_to_cut = []
                                
                                for item in wall_items:
                                    try:
                                        if self.canvas.type(item) == "rectangle":
                                            coords = self.canvas.coords(item)
                                            if len(coords) >= 4:
                                                item_x0, item_y0, item_x1, item_y1 = coords[0], coords[1], coords[2], coords[3]
                                                # Check if this is a right wall segment (same X position)
                                                if abs(item_x0 - (r_x1 - wall_thickness)) < 2 and abs(item_x1 - r_x1) < 2:
                                                    # Check if this segment overlaps with cut area
                                                    if not (item_y1 < room_cut_start or item_y0 > room_cut_end):
                                                        # Segment overlaps with cut area - add to list
                                                        segments_to_cut.append(item)
                                    except tk.TclError:
                                        # Item was deleted, skip it
                                        continue
                                
                                # Cut all overlapping segments (door-induced gaps – do NOT record as manual)
                                for segment_item in segments_to_cut:
                                    try:
                                        self._cut_wall_segment(segment_item, room_cut_start, room_cut_end, cut_depth_px, "right", r_x1)
                                        wall_cut = True
                                    except Exception as e:
                                        print(f"[DEBUG] Error cutting right wall segment: {e}")
                                        continue
                                
                                if not wall_cut:
                                    print(f"[DEBUG] Warning: Could not find right wall segments overlapping cut area for room {room.name}")
                        else:
                            print(f"[DEBUG] Warning: Unknown fill_mode '{room.fill_mode}' for room {room.name}")
                    
                    # Skip the old single-room cutting logic below
                    return
                
                elif dist_to_right < tolerance and dist_to_right <= min(dist_to_top, dist_to_bottom, dist_to_left):
                    # Door on right wall - find room whose left wall aligns with this right wall
                    wall_to_cut = "right"
                    # Intersect door bbox with room boundaries to get valid cut range
                    cut_start = max(room_y0, door_y - door_w_px / 2)
                    cut_end = min(room_y1, door_y + door_w_px / 2)
                    # If cut range is invalid (door outside room), use door center projected onto wall
                    if cut_start >= cut_end:
                        door_center_y = door_y
                        door_height = door_w_px
                        # Clamp door center to room boundaries
                        clamped_center_y = max(room_y0 + door_height / 2, min(room_y1 - door_height / 2, door_center_y))
                        cut_start = clamped_center_y - door_height / 2
                        cut_end = clamped_center_y + door_height / 2
                        # Final clamp to ensure within room
                        cut_start = max(room_y0, cut_start)
                        cut_end = min(room_y1, cut_end)
                    print(f"[DEBUG] Door on RIGHT wall, cut from y={cut_start:.1f} to y={cut_end:.1f}")
                    
                    # Find adjacent room sharing this wall (left wall of adjacent room = right wall of this room)
                    wall_alignment_tolerance = wall_thickness + 5  # pixels
                    for group_tag, other_room in self.room_entities_by_group_tag.items():
                        if other_room == containing_room:
                            continue
                        other_coords = self.canvas.coords(other_room.rect_id)
                        if len(other_coords) < 4:
                            continue
                        other_x0, other_y0, other_x1, other_y1 = other_coords[0], other_coords[1], other_coords[2], other_coords[3]
                        # Check if other room's left wall aligns with this room's right wall
                        if (abs(other_x0 - room_x1) < wall_alignment_tolerance and
                            not (other_y1 < room_y0 or other_y0 > room_y1)):  # Walls overlap vertically
                            print(f"[DEBUG] Found adjacent room: {other_room.name} sharing right/left wall")
                            rooms_to_cut.append(other_room)
                    
                    # Cut wall for all rooms sharing this wall
                    # Handle each room based on its fill_mode
                    for room in rooms_to_cut:
                        room_coords = self.canvas.coords(room.rect_id)
                        if len(room_coords) < 4:
                            continue
                        r_x0, r_y0, r_x1, r_y1 = room_coords[0], room_coords[1], room_coords[2], room_coords[3]
                        # Adjust cut coordinates for this room's boundaries
                        room_cut_start = max(r_y0, cut_start)
                        room_cut_end = min(r_y1, cut_end)
                        
                        # Skip if cut range is invalid
                        if room_cut_start >= room_cut_end:
                            print(f"[DEBUG] Skipping room {room.name}: invalid cut range")
                            continue
                        
                        # Determine which wall to cut for this room
                        # If this is the containing room, cut right wall; if adjacent, cut left wall
                        wall_side = "right" if room == containing_room else "left"
                        
                        print(f"[DEBUG] Cutting {wall_side} wall for room {room.name} (fill_mode: {room.fill_mode})")
                        
                        # Handle based on room type - only walls_only rooms are cut
                        if getattr(room, "fill_mode", "") == "walls_only":
                            # For walls_only mode, cut the specific wall segment
                            if wall_side == "right":
                                wall_cut = False
                                # Find ALL wall segments on right wall that overlap with cut area
                                wall_items = self.canvas.find_withtag(room.group_tag)
                                segments_to_cut = []
                                
                                for item in wall_items:
                                    try:
                                        if self.canvas.type(item) == "rectangle":
                                            coords = self.canvas.coords(item)
                                            if len(coords) >= 4:
                                                item_x0, item_y0, item_x1, item_y1 = coords[0], coords[1], coords[2], coords[3]
                                                # Check if this is a right wall segment (same X position)
                                                if abs(item_x0 - (r_x1 - wall_thickness)) < 2 and abs(item_x1 - r_x1) < 2:
                                                    # Check if this segment overlaps with cut area
                                                    if not (item_y1 < room_cut_start or item_y0 > room_cut_end):
                                                        # Segment overlaps with cut area - add to list
                                                        segments_to_cut.append(item)
                                    except tk.TclError:
                                        # Item was deleted, skip it
                                        continue
                                
                                # Cut all overlapping segments
                                for segment_item in segments_to_cut:
                                    try:
                                        self._cut_wall_segment(segment_item, room_cut_start, room_cut_end, cut_depth_px, "right", r_x1)
                                        wall_cut = True
                                    except Exception as e:
                                        print(f"[DEBUG] Error cutting right wall segment: {e}")
                                        continue
                                
                                if not wall_cut:
                                    print(f"[DEBUG] Warning: Could not find right wall segments overlapping cut area for room {room.name}")
                            else:  # left
                                wall_cut = False
                                # Find ALL wall segments on left wall that overlap with cut area
                                wall_items = self.canvas.find_withtag(room.group_tag)
                                segments_to_cut = []
                                
                                for item in wall_items:
                                    try:
                                        if self.canvas.type(item) == "rectangle":
                                            coords = self.canvas.coords(item)
                                            if len(coords) >= 4:
                                                item_x0, item_y0, item_x1, item_y1 = coords[0], coords[1], coords[2], coords[3]
                                                # Check if this is a left wall segment (same X position)
                                                if abs(item_x0 - r_x0) < 2 and abs(item_x1 - (r_x0 + wall_thickness)) < 2:
                                                    # Check if this segment overlaps with cut area
                                                    if not (item_y1 < room_cut_start or item_y0 > room_cut_end):
                                                        # Segment overlaps with cut area - add to list
                                                        segments_to_cut.append(item)
                                    except tk.TclError:
                                        # Item was deleted, skip it
                                        continue
                                
                                # Cut all overlapping segments
                                for segment_item in segments_to_cut:
                                    try:
                                        self._cut_wall_segment(segment_item, room_cut_start, room_cut_end, cut_depth_px, "left", r_x0)
                                        wall_cut = True
                                    except Exception as e:
                                        print(f"[DEBUG] Error cutting left wall segment: {e}")
                                        continue
                                
                                if not wall_cut:
                                    print(f"[DEBUG] Warning: Could not find left wall segments overlapping cut area for room {room.name}")
                        else:
                            print(f"[DEBUG] Warning: Unknown fill_mode '{room.fill_mode}' for room {room.name}")
                    
                    # Skip the old single-room cutting logic below
                    return
                else:
                    print(f"[DEBUG] Door not close enough to any wall (tolerance: {tolerance:.1f})")
            
            # Process polygon wall cutting if door is on polygon edge
            if containing_polygon:
                print(f"[DEBUG] Processing polygon wall cutting for {containing_polygon}")
                self._cut_polygon_wall_for_door(door_item, door_bbox, containing_polygon, pixels_per_foot)
        
        except Exception as e:
            print(f"Error cutting wall for door: {e}")
            import traceback
            traceback.print_exc()

    def schedule_recompute_door_cuts(self, delay_ms: int = 60) -> None:
        """
        Debounced recompute for door wall cuts.
        Call this after a door (or its group) is moved so old gaps are restored and the new gap is cut.
        """
        try:
            # Check if root window still exists before scheduling
            if not hasattr(self.root, 'winfo_exists') or not self.root.winfo_exists():
                self._door_recut_after_id = None
                return
                
            if self._door_recut_after_id is not None:
                try:
                    self.root.after_cancel(self._door_recut_after_id)
                except Exception:
                    pass
                self._door_recut_after_id = None

            self._door_recut_after_id = self.root.after(int(delay_ms), self.recompute_all_door_cuts)
        except Exception as e:
            # Don't crash UI due to scheduling
            try:
                print(f"[DEBUG] schedule_recompute_door_cuts failed: {e}")
            except Exception:
                pass

    def _is_door_furniture(self, furniture_obj) -> bool:
        try:
            if getattr(furniture_obj, "is_door", False):
                return True
        except Exception:
            pass
        try:
            p = getattr(furniture_obj, "image_path", "") or ""
            base = os.path.basename(p).lower()
            return "door" in base
        except Exception:
            return False

    def _sync_room_items_to_existing(self, room_entity) -> None:
        """Remove deleted canvas items from room_entity.items to prevent leaks."""
        try:
            if not hasattr(room_entity, "items"):
                return
            room_entity.items = [i for i in room_entity.items if self._item_exists(i)]
        except Exception:
            pass

    def _reset_room_after_door_cuts(self, room_entity) -> None:
        """
        Restore a room to an 'uncut' wall state.
        - walls_only: delete all wall rectangles (keep hit-rect), recreate 4 walls, update wall_id fields
        - filled/transparent: remove perimeter outline lines created by cutting, recreate standard rectangle with outline
        """
        try:
            rect_id = getattr(room_entity, "rect_id", None)
            if not rect_id or not self._item_exists(rect_id):
                return

            coords = self.canvas.coords(rect_id)
            if not coords or len(coords) < 4:
                return
            x0, y0, x1, y1 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])

            group_tag = getattr(room_entity, "group_tag", None)
            if not group_tag:
                return

            # Clear any remembered door-cut intervals / outline state for this room.
            try:
                if hasattr(self, "_door_cut_registry") and self._door_cut_registry:
                    self._door_cut_registry.clear_room(group_tag)
            except Exception:
                pass
            try:
                if hasattr(room_entity, "_door_outline_line_ids"):
                    room_entity._door_outline_line_ids = []
            except Exception:
                pass
            try:
                if hasattr(room_entity, "_door_outline_style"):
                    delattr(room_entity, "_door_outline_style")
            except Exception:
                pass

            items = list(self.canvas.find_withtag(group_tag))

            if getattr(room_entity, "fill_mode", "filled") == "walls_only":
                # Remove all visible wall rectangles (including previously cut segments), keep the invisible hit rect.
                for it in items:
                    try:
                        tags_it = self.canvas.gettags(it)
                        if (
                            "furniture" in tags_it
                            or "furniture_committed" in tags_it
                            or "flooring_border" in tags_it
                        ):
                            continue
                        if self.canvas.type(it) != "rectangle":
                            continue
                        fill = self.canvas.itemcget(it, "fill")
                        outline = self.canvas.itemcget(it, "outline")
                        # Hit rectangle: fill="" and outline=""
                        if (fill == "" and outline == ""):
                            continue
                        self.canvas.delete(it)
                    except Exception:
                        continue

                t = float(room_entity._wall_thickness_pixels())
                tags = ("room", group_tag)

                top_id = self.canvas.create_rectangle(x0, y0, x1, y0 + t, fill="black", outline="black", tags=tags)
                bottom_id = self.canvas.create_rectangle(x0, y1 - t, x1, y1, fill="black", outline="black", tags=tags)
                left_id = self.canvas.create_rectangle(x0, y0 + t, x0 + t, y1 - t, fill="black", outline="black", tags=tags)
                right_id = self.canvas.create_rectangle(x1 - t, y0 + t, x1, y1 - t, fill="black", outline="black", tags=tags)

                room_entity.top_wall_id = top_id
                room_entity.bottom_wall_id = bottom_id
                room_entity.left_wall_id = left_id
                room_entity.right_wall_id = right_id

                # Keep rect_id (hit rect) as-is; refresh items bookkeeping
                self._sync_room_items_to_existing(room_entity)
                try:
                    for new_id in (top_id, bottom_id, left_id, right_id):
                        room_entity.items.append(new_id)
                except Exception:
                    pass

            else:
                # Remove perimeter outline lines (axis-aligned on room border). Keep diagonal decorations (shaft) etc.
                eps = 1.5
                for it in items:
                    try:
                        tags_it = self.canvas.gettags(it)
                        if "furniture" in tags_it or "furniture_committed" in tags_it:
                            continue
                        if self.canvas.type(it) != "line":
                            continue
                        lcoords = self.canvas.coords(it)
                        if not lcoords or len(lcoords) != 4:
                            continue
                        xA, yA, xB, yB = float(lcoords[0]), float(lcoords[1]), float(lcoords[2]), float(lcoords[3])
                        horizontal = abs(yA - yB) < eps
                        vertical = abs(xA - xB) < eps
                        if not (horizontal or vertical):
                            continue
                        # Must lie on border
                        on_top = horizontal and abs(yA - y0) < eps
                        on_bottom = horizontal and abs(yA - y1) < eps
                        on_left = vertical and abs(xA - x0) < eps
                        on_right = vertical and abs(xA - x1) < eps
                        if on_top or on_bottom or on_left or on_right:
                            self.canvas.delete(it)
                    except Exception:
                        continue

                # Recreate a standard rectangle with outline. Delete old rect_id and create a fresh one.
                try:
                    fill_mode = getattr(room_entity, "fill_mode", "filled")
                    tags = ("room", group_tag)
                    # Preserve label if any (we won't delete text items)
                    try:
                        self.canvas.delete(rect_id)
                    except Exception:
                        pass

                    if fill_mode == "transparent":
                        new_rect = self.canvas.create_rectangle(x0, y0, x1, y1, fill="", outline="black", tags=tags)
                    else:
                        fill_color = getattr(room_entity, "fill_color", None) or "#d0f0c0"
                        new_rect = self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill_color, outline="black", tags=tags)

                    room_entity.rect_id = new_rect
                    self._sync_room_items_to_existing(room_entity)
                    try:
                        room_entity.items.append(new_rect)
                    except Exception:
                        pass

                    # Keep label and furniture above
                    label_id = getattr(room_entity, "label_id", None)
                    if label_id and self._item_exists(label_id):
                        try:
                            self.canvas.tag_raise(label_id)
                        except Exception:
                            pass
                    try:
                        self.canvas.tag_raise("furniture")
                    except Exception:
                        pass
                except Exception:
                    pass

        except Exception as e:
            try:
                print(f"[DEBUG] _reset_room_after_door_cuts failed: {e}")
            except Exception:
                pass

    def _get_polygon_shape_for_group(self, polygon_group_tag: str):
        try:
            for it in self.canvas.find_withtag(polygon_group_tag):
                if self.canvas.type(it) == "polygon":
                    return it
        except Exception:
            pass
        return None

    def move_user_text_inside_polygon(
        self, polygon_group_tag: str, dx: float, dy: float,
        text_check_offset=None,
    ) -> None:
        """
        Move user text items whose center lies inside the polygon by (dx, dy).
        Polygon has already been moved; original = current - (dx, dy).
        text_check_offset: for undo, use (dx, dy) to check (text_pos - offset) inside polygon.
        """
        try:
            poly_item = self._get_polygon_shape_for_group(polygon_group_tag)
            if not poly_item:
                return
            flat_coords = self.canvas.coords(poly_item)
            if not flat_coords or len(flat_coords) < 6:
                return
            ox, oy = text_check_offset or (0.0, 0.0)
            poly_points = [
                (float(flat_coords[i]) - dx, float(flat_coords[i + 1]) - dy)
                for i in range(0, len(flat_coords), 2)
            ]
            for item in self.canvas.find_all():
                try:
                    if self.canvas.type(item) != "text":
                        continue
                    tags = self.canvas.gettags(item) or ()
                    if "user_text" not in tags:
                        continue
                    bbox = self.canvas.bbox(item)
                    if not bbox or len(bbox) < 4:
                        continue
                    cx = (float(bbox[0]) + float(bbox[2])) / 2.0 - ox
                    cy = (float(bbox[1]) + float(bbox[3])) / 2.0 - oy
                    if VastuPolygonGenerator.point_in_polygon((cx, cy), poly_points):
                        self.canvas.move(item, dx, dy)
                except Exception:
                    continue
        except Exception:
            pass

    def _centroid_of_flat_coords(self, flat_coords):
        pts = [(flat_coords[i], flat_coords[i + 1]) for i in range(0, len(flat_coords), 2)]
        if not pts:
            return (0.0, 0.0)
        sx = sum(p[0] for p in pts)
        sy = sum(p[1] for p in pts)
        return (sx / len(pts), sy / len(pts))

    def _reset_polygons_after_door_cuts(self) -> None:
        """
        Restore polygons to their baseline (pre-door-cut) coordinates if baseline was recorded.
        Directly restores synchronized baseline coordinates, which prevents centroid shifts from door cuts.
        """
        for group_tag, baseline in list(getattr(self, "_polygon_baseline_coords_by_group", {}).items()):
            try:
                poly = self._get_polygon_shape_for_group(group_tag)
                if not poly:
                    continue
                current = self.canvas.coords(poly)
                if not current or len(current) < 6 or not baseline or len(baseline) < 6:
                    continue
                # Directly restore the synchronized baseline coordinates
                self.canvas.coords(poly, *baseline)
            except Exception:
                continue

    def recompute_all_door_cuts(self) -> None:
        """
        Rebuild all room/polygon walls to an uncut state, then re-apply door cuts at current positions.
        This enables dynamic door moving: old gap is restored, new gap is cut.
        """
        # Check if root window still exists before executing
        try:
            if not hasattr(self.root, 'winfo_exists') or not self.root.winfo_exists():
                self._recomputing_door_cuts = False
                return
        except Exception:
            self._recomputing_door_cuts = False
            return
            
        if self._recomputing_door_cuts:
            return
        try:
            self._recomputing_door_cuts = True

            # Collect doors that currently exist
            doors = []
            for furn in list(getattr(self, "image_furniture_items", []) or []):
                try:
                    if not hasattr(furn, "image_id") or not self._item_exists(furn.image_id):
                        continue
                    if self._is_door_furniture(furn):
                        doors.append(furn)
                except Exception:
                    continue

            # Capture user-erased wall regions BEFORE reset (so we can re-apply after door cuts).
            # IMPORTANT:
            # - When DOORS exist, we only trust explicit manual regions stored on the room
            #   (from eraser tools). Door gaps should move with the door and must NOT be
            #   captured as "manual" erasures.
            # - When there are NO doors, we can safely fall back to geometric detection.
            user_erased_by_room = {}
            for _, room in list(getattr(self, "room_entities_by_group_tag", {}).items()):
                if getattr(room, "fill_mode", "") != "walls_only":
                    continue
                try:
                    rect_id = getattr(room, "rect_id", None)
                    if not rect_id or not self._item_exists(rect_id):
                        continue
                    coords = self.canvas.coords(rect_id)
                    if not coords or len(coords) < 4:
                        continue
                    x0, y0, x1, y1 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])
                    regions = getattr(room, "_manual_wall_erased_regions", None)
                    # Only when there are no doors at all do we fall back to
                    # geometry-based detection of erased regions.
                    if not regions and not doors:
                        regions = self._get_room_wall_erased_regions(room, x0, y0, x1, y1)
                    if regions:
                        user_erased_by_room[room] = (regions, x0, y0, x1, y1)
                except Exception:
                    continue

            # Reset rooms and polygons (remove old gaps) for all room types.
            # For walls_only rooms, this recreates wall rectangles.
            # For filled/transparent rooms, this restores their original rectangle outline.
            for _, room in list(getattr(self, "room_entities_by_group_tag", {}).items()):
                self._reset_room_after_door_cuts(room)

            self._reset_polygons_after_door_cuts()

            if not doors:
                # Re-apply user-erased regions even when no doors
                for room, (regions, x0, y0, x1, y1) in user_erased_by_room.items():
                    try:
                        self.apply_wall_erased_regions(room, regions, x0, y0, x1, y1)
                    except Exception:
                        pass
                return

            # Re-apply cuts for every door at its current position
            for door in doors:
                try:
                    real = getattr(door, "real_size_ft", None)
                    if real and isinstance(real, (list, tuple)) and len(real) >= 2:
                        w_ft, h_ft = float(real[0]), float(real[1])
                    else:
                        w_ft, h_ft = 3.0, 3.0
                    self._cut_wall_for_door(door, w_ft, h_ft)
                    try:
                        self.canvas.tag_raise(door.image_id)
                    except Exception:
                        pass
                except Exception:
                    continue

            # Re-apply user-erased wall regions (manual gaps) on top of current door cuts.
            for room, (regions, x0, y0, x1, y1) in user_erased_by_room.items():
                try:
                    rect_id = getattr(room, "rect_id", None)
                    if rect_id and self._item_exists(rect_id):
                        c = self.canvas.coords(rect_id)
                        if c and len(c) >= 4:
                            self.apply_wall_erased_regions(room, regions, float(c[0]), float(c[1]), float(c[2]), float(c[3]))
                except Exception:
                    continue
        finally:
            self._recomputing_door_cuts = False
            try:
                self._door_recut_after_id = None
            except Exception:
                pass
    
    def _cut_polygon_wall_for_door(self, door_item, door_bbox, polygon_group_tag, pixels_per_foot):
        """
        Cut a segment from polygon wall where door is placed.
        """
        try:
            # Find polygon shape
            poly_items = self.canvas.find_withtag(polygon_group_tag)
            polygon_shape = None
            for item in poly_items:
                if self.canvas.type(item) == "polygon":
                    polygon_shape = item
                    break
            
            if not polygon_shape:
                print(f"[DEBUG] Polygon shape not found")
                return
            
            # Get current polygon coordinates for updating
            current_poly_coords = self.canvas.coords(polygon_shape)
            if len(current_poly_coords) < 6:
                return

            # Record baseline coords once (pre-door-cut) for dynamic recompute.
            # If the polygon later moves as a group, we restore baseline via centroid translation.
            try:
                if polygon_group_tag not in self._polygon_baseline_coords_by_group:
                    self._polygon_baseline_coords_by_group[polygon_group_tag] = list(current_poly_coords)
            except Exception:
                pass
            
            # Use baseline coordinates for edge detection to ensure consistent behavior
            # even after previous doors have cut the polygon
            if polygon_group_tag in self._polygon_baseline_coords_by_group:
                baseline_coords = self._polygon_baseline_coords_by_group[polygon_group_tag]
                print(f"[DEBUG] Using baseline coordinates for edge detection")
            else:
                baseline_coords = current_poly_coords
                print(f"[DEBUG] Using current coordinates for edge detection (baseline not stored)")
            
            if len(baseline_coords) < 6:
                return
            
            # Convert baseline to list of points for edge detection
            baseline_points = [(baseline_coords[i], baseline_coords[i+1]) for i in range(0, len(baseline_coords), 2)]
            
            # Convert current polygon to list of points for cutting
            current_poly_points = [(current_poly_coords[i], current_poly_coords[i+1]) for i in range(0, len(current_poly_coords), 2)]
            
            # Find the edge segment closest to door center using BASELINE coordinates
            # This ensures correct edge detection even after previous door cuts
            door_center_x = (door_bbox['x0'] + door_bbox['x1']) / 2
            door_center_y = (door_bbox['y0'] + door_bbox['y1']) / 2
            
            min_dist = float('inf')
            closest_edge_idx = -1
            
            for i in range(len(baseline_points)):
                p1 = baseline_points[i]
                p2 = baseline_points[(i + 1) % len(baseline_points)]
                
                # Distance from point to line segment
                dist = self._point_to_segment_distance((door_center_x, door_center_y), p1, p2)
                if dist < min_dist:
                    min_dist = dist
                    closest_edge_idx = i
            
            if closest_edge_idx == -1 or min_dist > 30:  # 30px tolerance
                print(f"[DEBUG] Door not close enough to polygon edge (dist: {min_dist:.1f})")
                return
            
            # Get the baseline edge segment for calculation
            baseline_p1 = baseline_points[closest_edge_idx]
            baseline_p2 = baseline_points[(closest_edge_idx + 1) % len(baseline_points)]
            
            # Calculate cut area (door width along the edge) using baseline edge
            cut_depth_ft = 0.4
            cut_depth_px = cut_depth_ft * pixels_per_foot
            
            # Project door bbox onto the baseline edge to find cut start/end
            baseline_edge_length = ((baseline_p2[0] - baseline_p1[0])**2 + (baseline_p2[1] - baseline_p1[1])**2)**0.5
            if baseline_edge_length < 1:
                return
            
            # Direction vector of baseline edge
            dx = (baseline_p2[0] - baseline_p1[0]) / baseline_edge_length
            dy = (baseline_p2[1] - baseline_p1[1]) / baseline_edge_length
            
            # Project door center onto baseline edge
            door_vec_x = door_center_x - baseline_p1[0]
            door_vec_y = door_center_y - baseline_p1[1]
            proj_length = door_vec_x * dx + door_vec_y * dy
            
            # Cut segment (door width along edge)
            door_width_px = door_bbox['x1'] - door_bbox['x0']
            cut_start_proj = max(0, proj_length - door_width_px / 2)
            cut_end_proj = min(baseline_edge_length, proj_length + door_width_px / 2)
            
            # Calculate cut points in world coordinates using baseline edge
            cut_start_pt = (baseline_p1[0] + cut_start_proj * dx, baseline_p1[1] + cut_start_proj * dy)
            cut_end_pt = (baseline_p1[0] + cut_end_proj * dx, baseline_p1[1] + cut_end_proj * dy)
            
            # Find where to insert cut points in current polygon
            # The current polygon may have cuts from previous doors, so we need to find
            # segments that are collinear with the baseline edge and insert cut points there
            new_poly_points = []
            
            # Helper function to check if a point is collinear with baseline edge
            def is_point_on_baseline_edge(pt, tolerance=5.0):
                """Check if point is on the baseline edge line within tolerance"""
                dist = self._point_to_segment_distance(pt, baseline_p1, baseline_p2)
                return dist < tolerance
            
            # Find all segments in current polygon that are part of the baseline edge
            # These segments may have been split by previous door cuts
            segments_on_baseline = []
            for i in range(len(current_poly_points)):
                curr_p1 = current_poly_points[i]
                curr_p2 = current_poly_points[(i + 1) % len(current_poly_points)]
                
                # Check if both endpoints are on the baseline edge
                if is_point_on_baseline_edge(curr_p1) and is_point_on_baseline_edge(curr_p2):
                    segments_on_baseline.append((i, curr_p1, curr_p2))
            
            # If we found segments on baseline edge, insert cut points in the right segment
            if segments_on_baseline:
                # Build new polygon, inserting cut points in the appropriate segments
                cut_inserted = False
                
                for i in range(len(current_poly_points)):
                    curr_p1 = current_poly_points[i]
                    curr_p2 = current_poly_points[(i + 1) % len(current_poly_points)]
                    
                    # Check if this segment is on the baseline edge
                    is_on_baseline = is_point_on_baseline_edge(curr_p1) and is_point_on_baseline_edge(curr_p2)
                    
                    if is_on_baseline and not cut_inserted:
                        # This segment is on baseline - check if cut points should be inserted here
                        seg_length = ((curr_p2[0] - curr_p1[0])**2 + (curr_p2[1] - curr_p1[1])**2)**0.5
                        
                        if seg_length > 1:
                            # Project segment endpoints onto baseline edge to find their position
                            seg_vec_x = curr_p1[0] - baseline_p1[0]
                            seg_vec_y = curr_p1[1] - baseline_p1[1]
                            seg_start_proj = seg_vec_x * dx + seg_vec_y * dy
                            
                            seg_vec_x2 = curr_p2[0] - baseline_p1[0]
                            seg_vec_y2 = curr_p2[1] - baseline_p1[1]
                            seg_end_proj = seg_vec_x2 * dx + seg_vec_y2 * dy
                            
                            # Ensure seg_start_proj < seg_end_proj for comparison
                            seg_min_proj = min(seg_start_proj, seg_end_proj)
                            seg_max_proj = max(seg_start_proj, seg_end_proj)
                            
                            # Check if cut points fall within this segment's projection range
                            cut_start_in_seg = seg_min_proj <= cut_start_proj <= seg_max_proj
                            cut_end_in_seg = seg_min_proj <= cut_end_proj <= seg_max_proj
                            
                            if cut_start_in_seg or cut_end_in_seg:
                                # Add start point of segment (only if not already added)
                                if not new_poly_points or new_poly_points[-1] != curr_p1:
                                    new_poly_points.append(curr_p1)
                                
                                # Project cut points onto this segment to get insertion order
                                seg_dx = (curr_p2[0] - curr_p1[0]) / seg_length
                                seg_dy = (curr_p2[1] - curr_p1[1]) / seg_length
                                
                                # Calculate projection of cut points on this segment
                                cut1_vec_x = cut_start_pt[0] - curr_p1[0]
                                cut1_vec_y = cut_start_pt[1] - curr_p1[1]
                                cut1_proj_on_seg = cut1_vec_x * seg_dx + cut1_vec_y * seg_dy
                                
                                cut2_vec_x = cut_end_pt[0] - curr_p1[0]
                                cut2_vec_y = cut_end_pt[1] - curr_p1[1]
                                cut2_proj_on_seg = cut2_vec_x * seg_dx + cut2_vec_y * seg_dy
                                
                                # Collect points to insert (cut points that are within segment)
                                points_to_insert = []
                                if cut_start_in_seg and 0 <= cut1_proj_on_seg <= seg_length:
                                    points_to_insert.append((cut1_proj_on_seg, cut_start_pt))
                                if cut_end_in_seg and 0 <= cut2_proj_on_seg <= seg_length:
                                    points_to_insert.append((cut2_proj_on_seg, cut_end_pt))
                                
                                # Sort by projection on segment to maintain order
                                points_to_insert.sort(key=lambda x: x[0])
                                
                                # Insert points in order
                                for _, pt in points_to_insert:
                                    new_poly_points.append(pt)
                                
                                cut_inserted = True
                                
                                # Add end point of segment
                                new_poly_points.append(curr_p2)
                            else:
                                # Cut points not in this segment, add both points normally
                                if not new_poly_points or new_poly_points[-1] != curr_p1:
                                    new_poly_points.append(curr_p1)
                                new_poly_points.append(curr_p2)
                        else:
                            # Very short segment, add both points normally
                            if not new_poly_points or new_poly_points[-1] != curr_p1:
                                new_poly_points.append(curr_p1)
                            new_poly_points.append(curr_p2)
                    else:
                        # Not on baseline edge or cut already inserted
                        # Add curr_p1 only if it's not already the last point
                        if not new_poly_points or new_poly_points[-1] != curr_p1:
                            new_poly_points.append(curr_p1)
            else:
                # No segments found on baseline - use fallback: find closest segment
                print(f"[DEBUG] No segments found on baseline edge, using fallback")
                min_seg_dist = float('inf')
                best_seg_idx = -1
                
                for i in range(len(current_poly_points)):
                    curr_p1 = current_poly_points[i]
                    curr_p2 = current_poly_points[(i + 1) % len(current_poly_points)]
                    dist_to_seg = self._point_to_segment_distance(cut_start_pt, curr_p1, curr_p2)
                    if dist_to_seg < min_seg_dist:
                        min_seg_dist = dist_to_seg
                        best_seg_idx = i
                
                if best_seg_idx >= 0:
                    # Build polygon and insert cut points
                    for i in range(len(current_poly_points)):
                        new_poly_points.append(current_poly_points[i])
                        if i == best_seg_idx:
                            # Insert cut points after this segment
                            new_poly_points.append(cut_start_pt)
                            new_poly_points.append(cut_end_pt)
                else:
                    # Last resort: just append to current polygon
                    new_poly_points = list(current_poly_points)
                    new_poly_points.append(cut_start_pt)
                    new_poly_points.append(cut_end_pt)
            
            # Update polygon coordinates
            flat_coords = [coord for pt in new_poly_points for coord in pt]
            self.canvas.coords(polygon_shape, *flat_coords)
            
            print(f"[DEBUG] Polygon wall cut completed")
        
        except Exception as e:
            print(f"Error cutting polygon wall: {e}")
            import traceback
            traceback.print_exc()
    
    def _point_to_segment_distance(self, point, seg_start, seg_end):
        """Calculate distance from point to line segment."""
        px, py = point
        x1, y1 = seg_start
        x2, y2 = seg_end
        
        # Vector from seg_start to seg_end
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            # Segment is a point
            return ((px - x1)**2 + (py - y1)**2)**0.5
        
        # Vector from seg_start to point
        px_vec = px - x1
        py_vec = py - y1
        
        # Project point onto segment
        t = max(0, min(1, (px_vec * dx + py_vec * dy) / (dx * dx + dy * dy)))
        
        # Closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        # Distance
        return ((px - closest_x)**2 + (py - closest_y)**2)**0.5
    
    def _item_exists(self, item_id):
        """Check if a canvas item still exists."""
        try:
            self.canvas.type(item_id)
            return True
        except tk.TclError:
            return False

    def _get_room_wall_erased_regions(self, room, x0: float, y0: float, x1: float, y1: float):
        """Capture current wall gaps from canvas for walls_only room (same logic as serializer)."""
        result = {}
        try:
            group_tag = getattr(room, "group_tag", None)
            if not group_tag:
                return result
            try:
                t = float(room._wall_thickness_pixels())
            except Exception:
                t = 10.0
            eps = 2.0

            def _merge(intervals):
                if not intervals:
                    return []
                data = sorted([(min(a, b), max(a, b)) for a, b in intervals])
                out = [data[0]]
                for s, e in data[1:]:
                    if s <= out[-1][1] + eps:
                        out[-1] = (out[-1][0], max(out[-1][1], e))
                    else:
                        out.append((s, e))
                return out

            def _gaps(seg_spans, full_min, full_max):
                if not seg_spans:
                    return [[full_min, full_max]]
                merged = _merge(seg_spans)
                g = []
                cur = full_min
                for s, e in merged:
                    if s > cur + eps:
                        g.append([cur, s])
                    cur = max(cur, e)
                if cur < full_max - eps:
                    g.append([cur, full_max])
                return g

            sides = {
                "top": (x0, x1, y0, y0 + t, 0),
                "bottom": (x0, x1, y1 - t, y1, 0),
                "left": (y0 + t, y1 - t, x0, x0 + t, 1),
                "right": (y0 + t, y1 - t, x1 - t, x1, 1),
            }
            for side, (axis_min, axis_max, perp_min, perp_max, use_y) in sides.items():
                seg_spans = []
                for item_id in self.canvas.find_withtag(group_tag):
                    try:
                        if self.canvas.type(item_id) != "rectangle":
                            continue
                        c = self.canvas.coords(item_id)
                        if len(c) < 4:
                            continue
                        rx0, ry0, rx1, ry1 = float(c[0]), float(c[1]), float(c[2]), float(c[3])
                        if use_y == 0:
                            if (abs(ry0 - perp_min) < eps and abs(ry1 - perp_max) < eps) or (abs(ry1 - perp_min) < eps and abs(ry0 - perp_max) < eps):
                                seg_spans.append((min(rx0, rx1), max(rx0, rx1)))
                        else:
                            if (abs(rx0 - perp_min) < eps and abs(rx1 - perp_max) < eps) or (abs(rx1 - perp_min) < eps and abs(rx0 - perp_max) < eps):
                                seg_spans.append((min(ry0, ry1), max(ry0, ry1)))
                    except Exception:
                        continue
                g = _gaps(seg_spans, axis_min, axis_max)
                if g:
                    result[side] = g
        except Exception:
            pass
        return result

    def apply_wall_erased_regions(self, room_entity, wall_erased_regions: dict, x0: float, y0: float, x1: float, y1: float):
        """
        Apply saved wall erased regions after room.create().
        wall_erased_regions: {wall_side: [[start, end], ...]} in wall-axis coords.
        """
        if not wall_erased_regions or getattr(room_entity, "fill_mode", "") != "walls_only":
            return
        try:
            t = float(room_entity._wall_thickness_pixels())
        except Exception:
            t = 10.0
        eps = 2.0

        def _get_wall_items_for_side(side: str):
            out = []
            group_tag = getattr(room_entity, "group_tag", "")
            rect_id = getattr(room_entity, "rect_id", None)
            for item_id in self.canvas.find_withtag(group_tag):
                try:
                    if self.canvas.type(item_id) != "rectangle":
                        continue
                    if item_id == rect_id:
                        continue
                    c = self.canvas.coords(item_id)
                    if len(c) < 4:
                        continue
                    rx0, ry0, rx1, ry1 = float(c[0]), float(c[1]), float(c[2]), float(c[3])
                    w, h = abs(rx1 - rx0), abs(ry1 - ry0)
                    thin = min(w, h) <= t + eps
                    if not thin:
                        continue
                    if side == "top" and abs(ry0 - y0) < eps:
                        out.append(item_id)
                    elif side == "bottom" and abs(ry1 - y1) < eps:
                        out.append(item_id)
                    elif side == "left" and abs(rx0 - x0) < eps:
                        out.append(item_id)
                    elif side == "right" and abs(rx1 - x1) < eps:
                        out.append(item_id)
                except Exception:
                    continue
            return out

        def _delete_side(side: str):
            for iid in _get_wall_items_for_side(side):
                try:
                    self.canvas.delete(iid)
                except Exception:
                    pass

        for side, gaps in wall_erased_regions.items():
            if not gaps:
                continue
            axis_min = x0 if side in ("top", "bottom") else y0
            axis_max = x1 if side in ("top", "bottom") else y1
            wall_pos = y0 if side == "top" else (y1 if side == "bottom" else (x0 if side == "left" else x1))
            
            zoom = self.model.zoom_level
            scaled_gaps = []
            for (g0, g1) in gaps:
                scaled_gaps.append([float(g0) * zoom, float(g1) * zoom])

            for (g0, g1) in scaled_gaps:
                if g0 <= axis_min + eps and g1 >= axis_max - eps:
                    _delete_side(side)
                    break
            else:
                for (g0, g1) in scaled_gaps:
                    items = _get_wall_items_for_side(side)
                    for iid in items:
                        if not self._item_exists(iid):
                            continue
                        c = self.canvas.coords(iid)
                        if len(c) < 4:
                            continue
                        rx0, ry0, rx1, ry1 = c[0], c[1], c[2], c[3]
                        seg_min = rx0 if side in ("top", "bottom") else ry0
                        seg_max = rx1 if side in ("top", "bottom") else ry1
                        seg_min, seg_max = min(seg_min, seg_max), max(seg_min, seg_max)
                        if g0 < seg_max - eps and g1 > seg_min + eps:
                            self._cut_wall_segment(iid, g0, g1, 0, side, wall_pos, record_action=False)
                            break

    def _cut_wall_segment(self, wall_item, cut_start, cut_end, cut_depth_px, wall_side, wall_position, record_action=True):
        """
        Cut a segment from a wall rectangle by splitting it into two parts.
        Creates a gap in the wall where the door is (0.4 ft depth).
        Handles multiple doors on same wall by checking if wall segment overlaps with cut area.
        """
        try:
            def _snapshot_item(item_id: int):
                try:
                    snap = self.actions._snapshot_canvas_items(self.canvas, [item_id])
                    if snap:
                        return snap[0]
                except Exception:
                    pass
                # Fallback schema (best-effort)
                try:
                    item_type = self.canvas.type(item_id)
                except Exception:
                    item_type = ""
                try:
                    coords = self.canvas.coords(item_id)
                except Exception:
                    coords = []
                try:
                    tags = self.canvas.gettags(item_id)
                except Exception:
                    tags = ()
                return {"type": item_type, "coords": coords, "options": {}, "tags": tags}

            print(f"[DEBUG] _cut_wall_segment: wall_side={wall_side}, cut_start={cut_start:.1f}, cut_end={cut_end:.1f}, wall_item={wall_item}")
            
            # Check if wall_item exists and is valid
            if wall_item is None:
                print(f"[DEBUG] Wall item is None")
                return
            
            try:
                # Check if item exists on canvas
                item_type = self.canvas.type(wall_item)
                if item_type != "rectangle":
                    print(f"[DEBUG] Wall item is not a rectangle, type: {item_type}")
                    return
            except tk.TclError:
                print(f"[DEBUG] Wall item does not exist on canvas")
                return
            
            coords = self.canvas.coords(wall_item)
            if len(coords) < 4:
                print(f"[DEBUG] Invalid wall coordinates: {coords}")
                return
            
            x0, y0, x1, y1 = coords[0], coords[1], coords[2], coords[3]
            
            # Validate coordinates are not NaN or invalid
            try:
                x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
                # Check for NaN (NaN != NaN in Python)
                if any(math.isnan(coord) or math.isinf(coord) for coord in [x0, y0, x1, y1]):
                    print(f"[DEBUG] Invalid coordinate values (NaN or Inf): ({x0}, {y0}, {x1}, {y1})")
                    return
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] Cannot convert coordinates to float: ({x0}, {y0}, {x1}, {y1}), error: {e}")
                return
            
            print(f"[DEBUG] Wall original coords: ({x0:.1f}, {y0:.1f}) to ({x1:.1f}, {y1:.1f})")
            
            # Clamp cut coordinates to wall segment boundaries to handle overlapping cuts
            # This ensures we only cut within the actual wall segment
            if wall_side in ("top", "bottom"):
                # For horizontal walls, clamp X coordinates
                actual_cut_start = max(x0, min(cut_start, x1))
                actual_cut_end = min(x1, max(cut_end, x0))
            else:
                # For vertical walls, clamp Y coordinates
                actual_cut_start = max(y0, min(cut_start, y1))
                actual_cut_end = min(y1, max(cut_end, y0))
            
            # Check if cut is valid (must have some overlap with wall segment)
            if actual_cut_start >= actual_cut_end:
                print(f"[DEBUG] Cut area does not overlap with wall segment, skipping")
                return
            
            # Get wall properties
            fill_color = self.canvas.itemcget(wall_item, "fill")
            outline_color = self.canvas.itemcget(wall_item, "outline")
            tags = self.canvas.gettags(wall_item)
            
            print(f"[DEBUG] Wall color: {fill_color}, tags: {tags}")
            print(f"[DEBUG] Actual cut range: {actual_cut_start:.1f} to {actual_cut_end:.1f}")
            
            old_items_snapshot = [_snapshot_item(wall_item)]
            new_items_snapshot = []

            if wall_side == "top":
                # Cut from top wall: create gap by splitting into two rectangles
                if actual_cut_start > x0:
                    # Left segment (before door)
                    left_id = self.canvas.create_rectangle(
                        x0, y0, actual_cut_start, y1,
                        fill=fill_color, outline=outline_color, tags=tags
                    )
                    new_items_snapshot.append(_snapshot_item(left_id))
                    print(f"[DEBUG] Created left segment: ({x0:.1f}, {y0:.1f}) to ({actual_cut_start:.1f}, {y1:.1f})")
                if actual_cut_end < x1:
                    # Right segment (after door)
                    right_id = self.canvas.create_rectangle(
                        actual_cut_end, y0, x1, y1,
                        fill=fill_color, outline=outline_color, tags=tags
                    )
                    new_items_snapshot.append(_snapshot_item(right_id))
                    print(f"[DEBUG] Created right segment: ({actual_cut_end:.1f}, {y0:.1f}) to ({x1:.1f}, {y1:.1f})")
                # Delete original wall - the gap (actual_cut_start to actual_cut_end) is left open
                self.canvas.delete(wall_item)
                print(f"[DEBUG] Deleted original wall, gap created from x={actual_cut_start:.1f} to x={actual_cut_end:.1f}")
            
            elif wall_side == "bottom":
                # Cut from bottom wall
                if actual_cut_start > x0:
                    # Left segment
                    left_id = self.canvas.create_rectangle(
                        x0, y0, actual_cut_start, y1,
                        fill=fill_color, outline=outline_color, tags=tags
                    )
                    new_items_snapshot.append(_snapshot_item(left_id))
                    print(f"[DEBUG] Created left segment")
                if actual_cut_end < x1:
                    # Right segment
                    right_id = self.canvas.create_rectangle(
                        actual_cut_end, y0, x1, y1,
                        fill=fill_color, outline=outline_color, tags=tags
                    )
                    new_items_snapshot.append(_snapshot_item(right_id))
                    print(f"[DEBUG] Created right segment")
                # Delete original wall
                self.canvas.delete(wall_item)
                print(f"[DEBUG] Deleted original wall, gap created from x={actual_cut_start:.1f} to x={actual_cut_end:.1f}")
            
            elif wall_side == "left":
                # Cut from left wall
                if actual_cut_start > y0:
                    # Top segment
                    top_id = self.canvas.create_rectangle(
                        x0, y0, x1, actual_cut_start,
                        fill=fill_color, outline=outline_color, tags=tags
                    )
                    new_items_snapshot.append(_snapshot_item(top_id))
                    print(f"[DEBUG] Created top segment")
                if actual_cut_end < y1:
                    # Bottom segment
                    bottom_id = self.canvas.create_rectangle(
                        x0, actual_cut_end, x1, y1,
                        fill=fill_color, outline=outline_color, tags=tags
                    )
                    new_items_snapshot.append(_snapshot_item(bottom_id))
                    print(f"[DEBUG] Created bottom segment")
                # Delete original wall
                self.canvas.delete(wall_item)
                print(f"[DEBUG] Deleted original wall, gap created from y={actual_cut_start:.1f} to y={actual_cut_end:.1f}")
            
            elif wall_side == "right":
                # Cut from right wall
                if actual_cut_start > y0:
                    # Top segment
                    top_id = self.canvas.create_rectangle(
                        x0, y0, x1, actual_cut_start,
                        fill=fill_color, outline=outline_color, tags=tags
                    )
                    new_items_snapshot.append(_snapshot_item(top_id))
                    print(f"[DEBUG] Created top segment")
                if actual_cut_end < y1:
                    # Bottom segment
                    bottom_id = self.canvas.create_rectangle(
                        x0, actual_cut_end, x1, y1,
                        fill=fill_color, outline=outline_color, tags=tags
                    )
                    new_items_snapshot.append(_snapshot_item(bottom_id))
                    print(f"[DEBUG] Created bottom segment")
                # Delete original wall
                self.canvas.delete(wall_item)
                print(f"[DEBUG] Deleted original wall, gap created from y={actual_cut_start:.1f} to y={actual_cut_end:.1f}")

            if new_items_snapshot and record_action:
                try:
                    self.actions.log(
                        {
                            "type": "replace_group",
                            "old_items": old_items_snapshot,
                            "new_items": new_items_snapshot,
                        }
                    )
                except Exception:
                    pass
        
        except Exception as e:
            print(f"Error cutting wall segment: {e}")
            import traceback
            traceback.print_exc()
    
    def _cut_rectangle_outline_for_door(self, room_entity, cut_start, cut_end, wall_side, room_x0, room_y0, room_x1, room_y1):
        """
        Cut the outline of a filled or transparent room rectangle where a door is placed.
        Recreates the rectangle with line segments that skip the door area.
        """
        try:
            # This method must support multiple doors on the same wall.
            # Strategy:
            # - Maintain merged cut intervals per room+wall (registry)
            # - Remove any previously drawn outline lines
            # - Redraw the FULL outline with ALL gaps (all 4 sides) every time

            rect_item = getattr(room_entity, "rect_id", None)
            if not rect_item or not self._item_exists(rect_item):
                return

            # Use live rectangle coords (room may have moved)
            try:
                rc = self.canvas.coords(rect_item)
                x0, y0, x1, y1 = float(rc[0]), float(rc[1]), float(rc[2]), float(rc[3])
            except Exception:
                x0, y0, x1, y1 = float(room_x0), float(room_y0), float(room_x1), float(room_y1)

            tags = self.canvas.gettags(rect_item)
            group_tag = getattr(room_entity, "group_tag", None)
            if not group_tag:
                for t in tags:
                    if isinstance(t, str) and t.startswith("room_group_"):
                        group_tag = t
                        break
            if not group_tag:
                return

            # Remember outline style once (rect outline may be blanked after first cut)
            style = getattr(room_entity, "_door_outline_style", None)
            if not isinstance(style, dict):
                oc = ""
                ow = ""
                try:
                    oc = self.canvas.itemcget(rect_item, "outline") or ""
                except Exception:
                    oc = ""
                try:
                    ow = self.canvas.itemcget(rect_item, "width") or ""
                except Exception:
                    ow = ""
                outline_color = oc.strip() or "black"
                try:
                    outline_width = int(float(ow)) if ow else 1
                except Exception:
                    outline_width = 1
                style = {"outline_color": outline_color, "outline_width": outline_width}
                try:
                    setattr(room_entity, "_door_outline_style", style)
                except Exception:
                    pass
            else:
                outline_color = (style.get("outline_color") or "").strip() or "black"
                try:
                    outline_width = int(style.get("outline_width") or 1)
                except Exception:
                    outline_width = 1

            # Remove the rectangle's built-in outline; we will draw the outline as lines with gaps.
            try:
                self.canvas.itemconfig(rect_item, outline="", width=0)
            except Exception:
                try:
                    self.canvas.itemconfig(rect_item, outline="")
                except Exception:
                    pass

            # Register this cut interval (merged) for the current wall
            try:
                if wall_side in ("top", "bottom"):
                    self._door_cut_registry.add_cut(
                        group_tag, wall_side, float(cut_start), float(cut_end), wall_min=x0, wall_max=x1
                    )
                else:
                    self._door_cut_registry.add_cut(
                        group_tag, wall_side, float(cut_start), float(cut_end), wall_min=y0, wall_max=y1
                    )
            except Exception:
                pass

            # Delete previously drawn outline lines for this room (only border axis-aligned lines).
            eps = 1.5
            to_delete = []
            try:
                prior = list(getattr(room_entity, "_door_outline_line_ids", []) or [])
            except Exception:
                prior = []
            if prior:
                to_delete = prior
            else:
                # Best-effort: remove axis-aligned border lines for this room group
                try:
                    for it in list(self.canvas.find_withtag(group_tag)):
                        try:
                            tags_it = self.canvas.gettags(it)
                            if "furniture" in tags_it or "furniture_committed" in tags_it:
                                continue
                            if self.canvas.type(it) != "line":
                                continue
                            lcoords = self.canvas.coords(it)
                            if not lcoords or len(lcoords) != 4:
                                continue
                            xA, yA, xB, yB = float(lcoords[0]), float(lcoords[1]), float(lcoords[2]), float(lcoords[3])
                            horizontal = abs(yA - yB) < eps
                            vertical = abs(xA - xB) < eps
                            if not (horizontal or vertical):
                                continue
                            on_top = horizontal and abs(yA - y0) < eps
                            on_bottom = horizontal and abs(yA - y1) < eps
                            on_left = vertical and abs(xA - x0) < eps
                            on_right = vertical and abs(xA - x1) < eps
                            if on_top or on_bottom or on_left or on_right:
                                to_delete.append(it)
                        except Exception:
                            continue
                except Exception:
                    pass

            for it in to_delete:
                try:
                    if self._item_exists(it):
                        self.canvas.delete(it)
                except Exception:
                    pass

            # Clean items bookkeeping (removes deleted line ids)
            try:
                if hasattr(room_entity, "items"):
                    room_entity.items = [i for i in room_entity.items if self._item_exists(i)]
            except Exception:
                pass

            def _complement_segments(span0: float, span1: float, gaps):
                a0 = float(min(span0, span1))
                a1 = float(max(span0, span1))
                segs = []
                cur = a0
                clamped = []
                for gs, ge in list(gaps or []):
                    try:
                        gs = float(gs)
                        ge = float(ge)
                    except Exception:
                        continue
                    if gs > ge:
                        gs, ge = ge, gs
                    gs = max(a0, min(gs, a1))
                    ge = max(a0, min(ge, a1))
                    if ge - gs <= 0.75:
                        continue
                    clamped.append((gs, ge))
                clamped.sort(key=lambda t: t[0])
                for gs, ge in clamped:
                    if gs > cur + 0.75:
                        segs.append((cur, gs))
                    cur = max(cur, ge)
                if cur < a1 - 0.75:
                    segs.append((cur, a1))
                return segs

            # Redraw full outline using ALL registered cuts on each wall
            created_line_ids = []
            for side in ("top", "bottom", "left", "right"):
                gaps = []
                try:
                    gaps = self._door_cut_registry.get_merged(group_tag, side)
                except Exception:
                    gaps = []

                if side in ("top", "bottom"):
                    y = y0 if side == "top" else y1
                    for sx, ex in _complement_segments(x0, x1, gaps):
                        try:
                            lid = self.canvas.create_line(
                                sx, y, ex, y, fill=outline_color, width=outline_width, tags=tags
                            )
                            created_line_ids.append(lid)
                        except Exception:
                            continue
                else:
                    x = x0 if side == "left" else x1
                    for sy, ey in _complement_segments(y0, y1, gaps):
                        try:
                            lid = self.canvas.create_line(
                                x, sy, x, ey, fill=outline_color, width=outline_width, tags=tags
                            )
                            created_line_ids.append(lid)
                        except Exception:
                            continue

            try:
                setattr(room_entity, "_door_outline_line_ids", list(created_line_ids))
            except Exception:
                pass

            # Keep line ids in room_entity.items (for later redraw/delete flows)
            try:
                existing = set(getattr(room_entity, "items", []) or [])
                for lid in created_line_ids:
                    if lid not in existing:
                        room_entity.items.append(lid)
                        existing.add(lid)
            except Exception:
                pass

            # Keep label above
            try:
                label_id = getattr(room_entity, "label_id", None)
                if label_id and self._item_exists(label_id):
                    self.canvas.tag_raise(label_id)
            except Exception:
                pass

            # Keep furniture above (doors etc.)
            try:
                for furn_id in self.canvas.find_withtag("furniture"):
                    self.canvas.tag_raise(furn_id)
            except Exception:
                pass
            
        except Exception as e:
            print(f"Error cutting rectangle outline: {e}")
            import traceback
            traceback.print_exc()

        #=== Room formation===#
    def redraw_all_rooms(self):
     # Re-draw all rooms based on stored room entities
     for group_tag, room in list(self.room_entities_by_group_tag.items()): # Iterate on a copy
        try:
            coords = None
            if hasattr(room, "rect_id"):
                coords = room.canvas.coords(room.rect_id)
            if coords and len(coords) >= 4:
                room.x0, room.y0 = coords[0], coords[1]
        except Exception:
            pass

        room.unit_scale = self.model.unit_scale[self.model.unit]
        room.grid_spacing = self.model.grid_spacing
        room.zoom_level = self.model.zoom_level
        room.width_px = room.wlabel / room.unit_scale * room.grid_spacing * room.zoom_level
        room.height_px = room.hlabel / room.unit_scale * room.grid_spacing * room.zoom_level
        room.x1 = room.x0 + room.width_px
        room.y1 = room.y0 + room.height_px

        safe_items = []
        for item in list(room.items):
            try:
                tags_it = room.canvas.gettags(item)
            except Exception:
                continue
            if "furniture" in tags_it or "furniture_committed" in tags_it:
                safe_items.append(item)
                continue
            try:
                room.canvas.delete(item)
            except Exception:
                pass
        room.items = safe_items
        room.create()


    def insert_room_template(self, name, width, height):
        from entities import RoomEntity
        from tkinter import simpledialog
        from Helper.showMessage import show_message
        import importlib.util

        # Check for duplicate room name (case-insensitive)
        name_lower = name.strip().lower()
        for existing_room in self.room_entities_by_group_tag.values():
            if hasattr(existing_room, 'name') and existing_room.name.strip().lower() == name_lower:
                show_message(
                    "error",
                    "Room Already Exists",
                    f"A room with the name '{name}' already exists.\nPlease change the name and try again."
                )
                return None

        # Ask user how the room should be drawn: filled, transparent, or walls-only.
        # Preferred: custom Toplevel dialog for a nicer UI.
        fill_mode = "filled"
        fill_color = None
        used_custom_dialog = False
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            dlg_path = os.path.join(base_dir, "Helper", "room_style_dialog.py")
            if os.path.isfile(dlg_path):
                spec = importlib.util.spec_from_file_location("_mini_autocad_room_style_dialog", dlg_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    try:
                        sys.modules[spec.name] = module
                    except Exception:
                        pass
                    spec.loader.exec_module(module)  # type: ignore[attr-defined]
                    RoomStyleDialog = getattr(module, "RoomStyleDialog", None)
                    if RoomStyleDialog:
                        used_custom_dialog = True
                        dlg = RoomStyleDialog(self.root)
                        res = dlg.show()
                        if res is None:
                            # User cancelled: do not create a room, and do not show fallback popups.
                            return None
                        fill_mode = getattr(res, "fill_mode", "filled") or "filled"
                        fill_color = getattr(res, "fill_color", None)
        except Exception as e:
            try:
                print(f"[MiniAutoCAD][Room] Falling back to simple dialog (style): {e}")
            except Exception:
                pass

        # Fallback: simple text dialog (only if custom dialog wasn't used/available)
        if (not used_custom_dialog) and (fill_mode == "filled") and (fill_color is None):
            try:
                choice = simpledialog.askstring(
                    "Room Style",
                    (
                        "Select room style:\n"
                        "1 = Filled (default color)\n"
                        "2 = Transparent (no fill)\n"
                        "3 = Walls only (0.2 ft)\n\n"
                        "Enter 1, 2, or 3:"
                    ),
                    parent=self.root,
                )
            except Exception:
                choice = None
            if choice == "2":
                fill_mode = "transparent"
            elif choice == "3":
                fill_mode = "walls_only"

        group_id = getattr(self.model, "room_counter", 0)
        setattr(self.model, "room_counter", group_id + 1)

        room = RoomEntity(
            self.canvas,
            self.model,
            name,
            width,
            height,
            group_id,
            fill_mode=fill_mode,
            fill_color=fill_color,
        )
        # Store room entity for tracking
        self.room_entities_by_group_tag[room.group_tag] = room
        
        # Check if room is inside a polygon and track the relationship
        room_center_x = (room.x0 + room.x1) / 2
        room_center_y = (room.y0 + room.y1) / 2
        from vastu_geometry import VastuPolygonGenerator
        
        # Find polygon that contains this room
        all_polygons = self.canvas.find_withtag("polygon_shape")
        for poly_item in all_polygons:
            poly_coords = self.canvas.coords(poly_item)
            if len(poly_coords) < 6:  # Need at least 3 points
                continue
            # Convert to list of points
            poly_points = [(poly_coords[i], poly_coords[i+1]) for i in range(0, len(poly_coords), 2)]
            # Check if room center is inside polygon
            if VastuPolygonGenerator.point_in_polygon((room_center_x, room_center_y), poly_points):
                # Get polygon group tag
                poly_tags = self.canvas.gettags(poly_item)
                for tag in poly_tags:
                    if tag.startswith("polygon_group_"):
                        # Track room-polygon relationship
                        if tag not in self.polygon_rooms_map:
                            self.polygon_rooms_map[tag] = []
                        self.polygon_rooms_map[tag].append(room.group_tag)
                        print(f"[DEBUG] Room {room.group_tag} is inside polygon {tag}")
                        break
                break
        
        # Log room creation with group tag for proper undo support
        self.actions.log({
            "type": "create_room",
            "group_tag": room.group_tag,
            "items": room.items,
            "room_payload": {
                "name": name,
                "width": width,
                "height": height,
                "group_id": group_id,
                "fill_mode": fill_mode,
                "fill_color": fill_color,
                "polygon_group_tag": None,
            },
        })
        return room  # ✅ Return the room instance

    def rebuild_polygon_room_mapping(self) -> None:
        """
        Recompute the mapping between layout polygons and rooms whose
        centers lie inside those polygons. This is used after a layout
        import/load so that moving a polygon drags its rooms just like
        during interactive creation.
        """
        # Reset mapping safely
        try:
            self.polygon_rooms_map.clear()
        except Exception:
            self.polygon_rooms_map = {}

        try:
            from vastu_geometry import VastuPolygonGenerator
        except Exception:
            return

        canvas = self.canvas

        def _register_room_center(room_group_tag: str, cx: float, cy: float) -> None:
            try:
                all_polygons = canvas.find_withtag("polygon_shape")
                for poly_item in all_polygons:
                    poly_coords = canvas.coords(poly_item)
                    if not poly_coords or len(poly_coords) < 6:
                        continue
                    poly_points = [
                        (poly_coords[i], poly_coords[i + 1])
                        for i in range(0, len(poly_coords), 2)
                    ]
                    if VastuPolygonGenerator.point_in_polygon((cx, cy), poly_points):
                        poly_tags = canvas.gettags(poly_item)
                        for tag in poly_tags:
                            if isinstance(tag, str) and tag.startswith("polygon_group_"):
                                group_list = self.polygon_rooms_map.setdefault(tag, [])
                                if room_group_tag not in group_list:
                                    group_list.append(room_group_tag)
                                break
                        break
            except Exception:
                return

        # 1) Use RoomEntity instances when available (normal runtime path)
        try:
            for group_tag, room in getattr(self, "room_entities_by_group_tag", {}).items():
                try:
                    if not isinstance(group_tag, str) or not group_tag.startswith("room_group_"):
                        continue
                    x0 = float(getattr(room, "x0", 0.0))
                    y0 = float(getattr(room, "y0", 0.0))
                    x1 = float(getattr(room, "x1", x0))
                    y1 = float(getattr(room, "y1", y0))
                    cx = (x0 + x1) / 2.0
                    cy = (y0 + y1) / 2.0
                    _register_room_center(group_tag, cx, cy)
                except Exception:
                    continue
        except Exception:
            pass

        # 2) Fallback: scan plain room rectangles if no RoomEntity is registered.
        try:
            for item in canvas.find_withtag("room"):
                try:
                    if canvas.type(item) != "rectangle":
                        continue
                except Exception:
                    continue
                tags = canvas.gettags(item) or ()
                group_tag = next(
                    (
                        t
                        for t in tags
                        if isinstance(t, str) and t.startswith("room_group_")
                    ),
                    None,
                )
                if not group_tag:
                    continue
                coords = canvas.coords(item)
                if not coords or len(coords) < 4:
                    continue
                x0, y0, x1, y1 = coords[0], coords[1], coords[2], coords[3]
                cx = (x0 + x1) / 2.0
                cy = (y0 + y1) / 2.0
                _register_room_center(group_tag, cx, cy)
        except Exception:
            pass

    def enable_flooring_mode(self):
        from Helper.showMessage import show_message

        self.paste_ready = False
        self.reset_modes()
        self.flooring_enabled = True

        selected = (self.flooring_type_var.get() or "").strip().lower()
        normalized = selected.replace("_", " ").strip()

        # "None/Default" means: click to REMOVE flooring (no image required)
        if normalized.startswith("none") or normalized.startswith("default") or normalized.startswith("no flooring"):
            self.flooring_remove_mode = True
            self.flooring_image_path = ""
            try:
                print(f"[Flooring] remove mode enabled (selected='{selected}')")
            except Exception:
                pass
            self.canvas.config(cursor="crosshair")
            return
        self.flooring_remove_mode = False

        base_dir = os.path.dirname(os.path.abspath(__file__))
        flooring_dir = os.path.join(base_dir, "flooring")

        # Preferred names (supporting multiple extensions)
        preferred = {
            "wood": ["wood.jpeg", "wood.jpg", "wood.png"],
            "tile": ["tile.jpg", "tile.jpeg", "tile.png"],
            "marble": ["marble.jpeg", "marble.jpg", "marble.png"],
            "garden": ["garden.jpeg", "garden.jpg", "garden.png"],
        }

        def resolve_path(kind: str) -> str:
            # 1) Try preferred filenames
            for fname in preferred.get(kind, []):
                p = os.path.join(flooring_dir, fname)
                if os.path.exists(p):
                    return p
            # 2) Try generic name + common extensions
            for ext in (".jpg", ".jpeg", ".png"):
                p = os.path.join(flooring_dir, kind + ext)
                if os.path.exists(p):
                    return p
            return ""

        path = resolve_path(selected)
        if not path:
            show_message(
                "warning",
                "VastuCraft Pro",
                f"Flooring image not found for '{selected}'.\nUsing tile texture instead.",
            )
            path = resolve_path("tile")

        # Final fallback: keep empty string if even tile is missing
        self.flooring_image_path = path
        try:
            print(f"[Flooring] selected='{selected}' -> '{self.flooring_image_path}'")
        except Exception:
            pass

        self.canvas.config(cursor="crosshair")

    def apply_flooring_to_room(self, event):
        from PIL import Image, ImageTk
        from Helper.showMessage import show_message

        x, y = event.x, event.y
        overlapping = self.canvas.find_overlapping(x-1, y-1, x+1, y+1)

        for item_id in reversed(overlapping):
            tags = self.canvas.gettags(item_id)
            if "closed_shape" in tags:
                self.apply_flooring_to_polygon(event)
                return
            if "room" in tags:
                coords = self.canvas.coords(item_id)
                x0, y0, x1, y1 = map(int, coords)

                group_tag = next((tag for tag in tags if tag.startswith("room_group_")), None)

                # Remove flooring from room
                if self.flooring_remove_mode:
                    old_payload = None
                    if item_id in self.room_flooring_images:
                        old = self.room_flooring_images.get(item_id, {})
                        old_payload = {
                            "kind": "room",
                            "image_id": old.get("image_id"),
                            "border_id": old.get("border_id"),
                            "image_path": old.get("image_path"),
                            "group_tag": group_tag,
                            "room_bbox": [x0, y0, x1, y1],
                        }
                    self._remove_flooring_for_owner(item_id, group_tag=group_tag)
                    try:
                        self.actions.log({"type": "flooring_apply", "old": old_payload, "new": None})
                    except Exception:
                        pass
                    break

                if not os.path.exists(self.flooring_image_path):
                    from Helper.showMessage import show_message
                    show_message(
                        "error",
                        "VastuCraft Pro",
                        f"Could not find flooring image:\n{self.flooring_image_path}",
                    )
                    return

                old_payload = None
                if item_id in self.room_flooring_images:
                    old_data = self.room_flooring_images.get(item_id, {})
                    # Capture enough info for undo restore
                    old_payload = {
                        "kind": "room",
                        "image_id": old_data.get("image_id"),
                        "border_id": old_data.get("border_id"),
                        "image_path": old_data.get("image_path"),
                        "group_tag": group_tag,
                        "room_bbox": [x0, y0, x1, y1],
                    }
                    try:
                        if old_data.get("image_id"):
                            self.canvas.delete(old_data["image_id"])
                    except Exception:
                        pass
                    try:
                        if old_data.get("border_id"):
                            self.canvas.delete(old_data["border_id"])
                    except Exception:
                        pass

                img = Image.open(self.flooring_image_path)
                img = img.resize((abs(x1 - x0), abs(y1 - y0)), Image.Resampling.LANCZOS)
                tk_img = ImageTk.PhotoImage(img, master=self.canvas)

                image_id = self.canvas.create_image(
                    x0, y0,
                    image=tk_img,
                    anchor="nw",
                    tags=("flooring", group_tag) if group_tag else ("flooring",)
                )
                border_id = self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    outline="black",
                    width=2,
                    tags=("flooring_border", group_tag) if group_tag else ("flooring_border",)
                )

                # Z-order
                try:
                    # Keep flooring visible above the room's filled rectangle
                    self.canvas.tag_raise(image_id, item_id)
                except Exception:
                    pass
                self.canvas.tag_raise(border_id, image_id)
                if group_tag:
                    group_items = self.canvas.find_withtag(group_tag)
                    for item in group_items:
                        if self.canvas.type(item) == "text":
                            self.canvas.tag_raise(item, image_id)
                            self.canvas.tag_raise(item, border_id)
                # Keep furniture above flooring (if present)
                try:
                    self.canvas.tag_raise("furniture")
                except Exception:
                    pass
                # Keep lines and their labels above flooring
                try:
                    self.canvas.tag_raise("line")
                    self.canvas.tag_raise("line_label")
                    self.canvas.tag_raise("line_point")
                except Exception:
                    pass

                self.room_flooring_images[item_id] = {
                    "kind": "room",
                    'image_id': image_id,
                    'tk_img': tk_img,
                    'border_id': border_id,
                    'image_path': self.flooring_image_path,
                    'group_tag': group_tag,
                    "room_bbox": [x0, y0, x1, y1],
                }

                # Log flooring action so Undo removes flooring (and restores old flooring if replaced)
                try:
                    new_payload = {
                        "kind": "room",
                        "image_id": image_id,
                        "border_id": border_id,
                        "image_path": self.flooring_image_path,
                        "group_tag": group_tag,
                        "room_bbox": [x0, y0, x1, y1],
                    }
                    self.actions.log({"type": "flooring_apply", "old": old_payload, "new": new_payload})
                except Exception:
                    pass

                # --- New: Furniture Suggestion and Placement ---
                room_entity = self.room_entities_by_group_tag.get(group_tag)
                if room_entity:
                    room_name = room_entity.name
                    room_width_real = room_entity.wlabel
                    room_height_real = room_entity.hlabel
                    room_bbox = self.canvas.coords(item_id)

                    suggester = FurnitureSuggester()
                    suggested_furniture = suggester.suggest(room_name)

                    if suggested_furniture:
                        center_x = (room_bbox[0] + room_bbox[2]) / 2
                        center_y = (room_bbox[1] + room_bbox[3]) / 2
                        self.show_furniture_selection_dialog(
                            suggested_furniture,
                            room_name,
                            center_x,
                            center_y,
                            room_bbox,
                            room_width_real,
                            room_height_real,
                        )
                    else:
                        from Helper.showMessage import show_message
                        show_message(
                            "info",
                            "VastuCraft Pro",
                            f"No specific furniture suggestions for a {(room_name or 'Room').title()} room at this time.",
                        )
                # --- End: Furniture Suggestion and Placement ---
                break

        self.flooring_enabled = False
        self.canvas.config(cursor="arrow")
        self.flooring_remove_mode = False

    def apply_flooring_to_polygon(self, event):
        from PIL import Image, ImageTk, ImageDraw

        x, y = event.x, event.y
        overlapping = self.canvas.find_overlapping(x - 1, y - 1, x + 1, y + 1)

        for item_id in reversed(overlapping):
            tags = self.canvas.gettags(item_id)
            if "closed_shape" in tags:  # your tag for polygons
                # Ensure this polygon has a polygon_group_* tag so dragging moves the full group.
                group_tag = next((t for t in tags if t.startswith("polygon_group_")), None)
                if not group_tag:
                    try:
                        group_tag = self.ensure_polygon_grouping(item_id)
                    except Exception:
                        group_tag = None

                # Remove flooring from polygon
                if self.flooring_remove_mode:
                    old_payload = None
                    if item_id in self.room_flooring_images:
                        old = self.room_flooring_images.get(item_id, {})
                        old_payload = {
                            "kind": "polygon",
                            "image_id": old.get("image_id"),
                            "border_id": old.get("border_id"),
                            "image_path": old.get("image_path"),
                            "group_tag": group_tag,
                            "polygon_coords": list(self.canvas.coords(item_id)),
                            "owner_original_style": old.get("owner_original_style"),
                        }

                    # Remove image + restore original style (best-effort)
                    removed_payload = self._remove_flooring_for_owner(item_id, group_tag=group_tag)
                    original_style = None
                    if old_payload:
                        original_style = old_payload.get("owner_original_style")
                    if (not original_style) and removed_payload:
                        original_style = removed_payload.get("owner_original_style")
                    # If no stored style, default to transparent (no fill)
                    if not original_style:
                        original_style = {"fill": "", "stipple": ""}
                    self._apply_item_floor_style(item_id, original_style)
                    try:
                        self.actions.log({"type": "flooring_apply", "old": old_payload, "new": None})
                    except Exception:
                        pass

                    self.canvas.config(cursor="arrow")
                    self.flooring_enabled = False
                    self.flooring_remove_mode = False
                    break

                # Capture polygon style before flooring so "None/Default" can restore it later.
                style_before = self._get_item_floor_style(item_id)

                # Ensure the polygon's fill doesn't hide the flooring texture.
                # We keep the polygon outline on top of the flooring.
                try:
                    # Clear fill + stipple so texture is visible
                    self.canvas.itemconfig(item_id, fill="", stipple="")
                except Exception:
                    pass

                # If flooring already exists for this polygon, replace it (and allow undo restore)
                old_payload = None
                if item_id in self.room_flooring_images:
                    old = self.room_flooring_images.get(item_id, {})
                    old_payload = {
                        "kind": "polygon",
                        "image_id": old.get("image_id"),
                        "border_id": old.get("border_id"),
                        "image_path": old.get("image_path"),
                        "group_tag": group_tag,
                        # store polygon coords at the moment (best-effort)
                        "polygon_coords": list(self.canvas.coords(item_id)),
                        # preserve original polygon style (for removal later)
                        "owner_original_style": old.get("owner_original_style"),
                    }
                    try:
                        if old.get("image_id"):
                            self.canvas.delete(old["image_id"])
                    except Exception:
                        pass
                    try:
                        if old.get("border_id"):
                            self.canvas.delete(old["border_id"])
                    except Exception:
                        pass

                coords = self.canvas.coords(item_id)
                if len(coords) < 6:
                    continue  # not a valid polygon

                # Bounding box
                xs = coords[::2]
                ys = coords[1::2]
                x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
                width, height = x1 - x0, y1 - y0

                if not os.path.exists(self.flooring_image_path):
                    from Helper.showMessage import show_message
                    show_message(
                        "error",
                        "VastuCraft Pro",
                        f"Could not find flooring image:\n{self.flooring_image_path}",
                    )
                    return

                # Load and resize flooring image
                img = Image.open(self.flooring_image_path).resize((width, height), Image.Resampling.LANCZOS)

                # Create polygon mask
                mask = Image.new("L", (width, height), 0)
                draw = ImageDraw.Draw(mask)
                polygon_relative = [(coords[i] - x0, coords[i + 1] - y0) for i in range(0, len(coords), 2)]
                draw.polygon(polygon_relative, fill=255)

                # Apply mask to flooring
                result = Image.new("RGBA", (width, height))
                result.paste(img, (0, 0), mask)

                # Display on canvas
                tk_img = ImageTk.PhotoImage(result, master=self.canvas)
                image_tags = ("flooring", group_tag) if group_tag else ("flooring",)
                image_id = self.canvas.create_image(
                    x0, y0,
                    image=tk_img,
                    anchor="nw",
                    tags=image_tags,
                )

                # Place below shape outline so polygon border stays visible
                try:
                    self.canvas.tag_lower(image_id, item_id)
                except Exception:
                    pass

                # Ensure vertex dots/labels are above flooring (prevents "jumping" / late appearance)
                try:
                    if group_tag:
                        for it in self.canvas.find_withtag(group_tag):
                            t = self.canvas.type(it)
                            if t == "oval" and "polygon_vertex" in self.canvas.gettags(it):
                                self.canvas.tag_raise(it, image_id)
                            if t == "text" and "polygon_label" in self.canvas.gettags(it):
                                self.canvas.tag_raise(it, image_id)
                        # Keep polygon outline on top
                        self.canvas.tag_raise(item_id, image_id)
                    # Keep lines and their labels above flooring
                    self.canvas.tag_raise("line")
                    self.canvas.tag_raise("line_label")
                    self.canvas.tag_raise("line_point")
                except Exception:
                    pass

                self.room_flooring_images[item_id] = {
                    "kind": "polygon",
                    'image_id': image_id,
                    'tk_img': tk_img,
                    'image_path': self.flooring_image_path,
                    'group_tag': group_tag,
                    'border_id': None,
                    "polygon_coords": list(coords),
                    # Only set original style if not already tracked (replacement should keep original)
                    "owner_original_style": (old_payload or {}).get("owner_original_style") or style_before,
                }

                # Log flooring action so Undo removes flooring (and restores old flooring if replaced)
                try:
                    new_payload = {
                        "kind": "polygon",
                        "image_id": image_id,
                        "border_id": None,
                        "image_path": self.flooring_image_path,
                        "group_tag": group_tag,
                        "polygon_coords": list(coords),
                        "owner_original_style": (old_payload or {}).get("owner_original_style") or style_before,
                    }
                    self.actions.log({"type": "flooring_apply", "old": old_payload, "new": new_payload})
                except Exception:
                    pass

                self.canvas.config(cursor="arrow")
                self.flooring_enabled = False
    def schedule_furniture_update(self, delay_ms: int = 100):
        """Debounce furniture scaling during zoom."""
        if hasattr(self, "_furniture_zoom_id") and self._furniture_zoom_id:
            try: self.canvas.after_cancel(self._furniture_zoom_id)
            except Exception: pass
        
        def _do_update():
            self._furniture_zoom_id = None
            if hasattr(self, 'image_furniture_items'):
                for furniture in self.image_furniture_items:
                    if hasattr(furniture, 'apply_global_zoom'):
                        furniture.apply_global_zoom(self.model.zoom_level, self.model)
            
            # Sync trace image zoom
            if getattr(self, 'trace_manager', None):
                try:
                    self.trace_manager.update_zoom()
                except Exception as e:
                    print(f"[TraceImageManager] Update zoom failed: {e}")
        
        self._furniture_zoom_id = self.canvas.after(delay_ms, _do_update)

    def schedule_flooring_rescale(self, delay_ms: int = 80):
        """Debounce the existing flooring texture resize after canvas zoom."""
        if self._flooring_rescale_id:
            try:
                self.canvas.after_cancel(self._flooring_rescale_id)
            except Exception:
                pass

        def _resize():
            self._flooring_rescale_id = None
            self._rescale_flooring_images()

        self._flooring_rescale_id = self.canvas.after(delay_ms, _resize)

    def _rescale_flooring_images(self):
        from PIL import Image, ImageTk, ImageDraw

        for room_id, flooring_data in self.room_flooring_images.items():
            border_id = flooring_data.get("border_id")
            image_path = flooring_data.get("image_path")
            if not image_path:
                continue

            if border_id and self._item_exists(border_id):
                current_coords = self.canvas.coords(border_id)
                if len(current_coords) < 4:
                    continue
                x0, y0, x1, y1 = current_coords
                new_width = int(abs(x1 - x0))
                new_height = int(abs(y1 - y0))

                img = Image.open(image_path)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                new_tk_img = ImageTk.PhotoImage(img, master=self.canvas)

                old_tags = self.canvas.gettags(flooring_data['image_id'])
                group_tag = next((tag for tag in old_tags if tag.startswith("room_group_")), None)

                self.canvas.delete(flooring_data['image_id'])
                new_image_id = self.canvas.create_image(
                    x0, y0,
                    image=new_tk_img,
                    anchor="nw",
                    tags=("flooring", group_tag) if group_tag else ("flooring",)
                )

                flooring_data['image_id'] = new_image_id
                flooring_data['tk_img'] = new_tk_img

                self.canvas.tag_raise(border_id, new_image_id)

                if group_tag:
                    group_items = self.canvas.find_withtag(group_tag)
                    for item in group_items:
                        if self.canvas.type(item) == "text":
                            self.canvas.tag_raise(item, new_image_id)
                            self.canvas.tag_raise(item, border_id)
                    for furniture_item in self.image_furniture_items:
                        if hasattr(furniture_item, 'image_id'):
                            self.canvas.tag_raise(furniture_item.image_id, new_image_id)
                            self.canvas.tag_raise(furniture_item.image_id, border_id)
                try:
                    self.canvas.tag_raise("line")
                    self.canvas.tag_raise("line_label")
                    self.canvas.tag_raise("line_point")
                except Exception:
                    pass
                continue

            if not self._item_exists(room_id):
                continue

            coords = self.canvas.coords(room_id)
            if len(coords) < 6:
                continue

            xs = coords[::2]
            ys = coords[1::2]
            x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
            width = max(int(x1 - x0), 1)
            height = max(int(y1 - y0), 1)

            img = Image.open(image_path).resize((width, height), Image.Resampling.LANCZOS)

            mask = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(mask)
            polygon_relative = [(coords[i] - x0, coords[i + 1] - y0) for i in range(0, len(coords), 2)]
            draw.polygon(polygon_relative, fill=255)

            result = Image.new("RGBA", (width, height))
            result.paste(img, (0, 0), mask)
            new_tk_img = ImageTk.PhotoImage(result, master=self.canvas)

            old_tags = self.canvas.gettags(flooring_data['image_id'])
            group_tag = next((tag for tag in old_tags if tag.startswith("polygon_group_")), None)

            self.canvas.delete(flooring_data['image_id'])
            new_image_id = self.canvas.create_image(
                x0, y0,
                image=new_tk_img,
                anchor="nw",
                tags=("flooring", group_tag) if group_tag else ("flooring",)
            )

            flooring_data['image_id'] = new_image_id
            flooring_data['tk_img'] = new_tk_img

            try:
                self.canvas.tag_lower(new_image_id, room_id)
                if group_tag:
                    for it in self.canvas.find_withtag(group_tag):
                        t = self.canvas.type(it)
                        if t == "oval" and "polygon_vertex" in self.canvas.gettags(it):
                            self.canvas.tag_raise(it, new_image_id)
                        if t == "text" and "polygon_label" in self.canvas.gettags(it):
                            self.canvas.tag_raise(it, new_image_id)
                    self.canvas.tag_raise(room_id, new_image_id)
                self.canvas.tag_raise("line")
                self.canvas.tag_raise("line_label")
                self.canvas.tag_raise("line_point")
            except Exception:
                pass

    #===copy paste===#
    def copy_selected_item(self):
        # ✅ First, try to copy selected furniture object
        if hasattr(self, 'selected_furniture_obj') and self.selected_furniture_obj:
            furniture = self.selected_furniture_obj
            self.copied_item_data = {
                "type": "furniture_image",
                "image_path": furniture.image_path,
                "scale": furniture.scale,
                "angle": furniture.angle
            }
            print("📋 Copied furniture image.")
            return

        # ✅ Otherwise, fallback to canvas shape
        if not hasattr(self, 'selected_item') or not self.selected_item:
            print("⚠️ No item selected to copy.")
            return

        item = self.selected_item
        item_type = self.canvas.type(item)
        coords = self.canvas.coords(item)
        tags = self.canvas.gettags(item)
        options = {}

        if item_type == "line":
            options["fill"] = self.canvas.itemcget(item, "fill")
            options["width"] = self.canvas.itemcget(item, "width")
        elif item_type in ("oval", "rectangle", "polygon"):
            options["fill"] = self.canvas.itemcget(item, "fill")
            options["outline"] = self.canvas.itemcget(item, "outline")
            options["width"] = self.canvas.itemcget(item, "width")
        elif item_type == "text":
            options["text"] = self.canvas.itemcget(item, "text")
            options["fill"] = self.canvas.itemcget(item, "fill")

        self.copied_item_data = {
            "type": item_type,
            "coords": coords,
            "options": options,
            "tags": tags
        }

        print("📋 Copied canvas shape:", self.copied_item_data)


    def prepare_to_paste_item(self):
        if not self.copied_item_data:
            print("⚠️ Nothing copied.")
            return
        print("🖱️ Click to paste item.")
        self.paste_ready = True
        self.model.set("paste_mode", True)


    def paste_item_at_click(self, event):
        if not self.paste_ready or not self.copied_item_data:
            return

        paste_x, paste_y = event.x, event.y
        data = self.copied_item_data

        # Furniture paste
        if data["type"] == "furniture_image":
            from Furniture import Furniture
            image_item = Furniture(
                self.canvas,
                data["image_path"],
                paste_x,
                paste_y,
                self.select_image_item,
                data["scale"],
                data["angle"],
                get_freeze_state=lambda: self.canvas_frozen,
                edit_callback=self.enter_furniture_edit_mode,
                duplicate_callback=self.duplicate_furniture,
                delete_callback=self.delete_furniture_item,
            )
            self.image_furniture_items.append(image_item)
            self.select_image_item(image_item)
            print("✅ Pasted furniture.")
            self._finish_paste()
            return

        # Geometry paste
        coords = data["coords"]
        cx = sum(coords[::2]) / (len(coords)//2)
        cy = sum(coords[1::2]) / (len(coords)//2)
        dx, dy = paste_x - cx, paste_y - cy
        new_coords = [c + dx if i % 2 == 0 else c + dy for i, c in enumerate(coords)]

        # Handle group tag (for room items)
        original_tags = data["tags"]
        new_tags = []
        old_group_tag = None

        for tag in original_tags:
            if tag.startswith("room_group_"):
                old_group_tag = tag
            else:
                new_tags.append(tag)

        if old_group_tag and "room" in original_tags:
            new_group_tag = f"room_group_{self.group_id_counter}"
            self.group_id_counter += 1
            new_tags.append(new_group_tag)
        else:
            new_tags = original_tags

        new_id = None
        if data["type"] == "line":
            new_id = self.canvas.create_line(*new_coords, **data["options"], tags=new_tags)
        elif data["type"] == "oval":
            new_id = self.canvas.create_oval(*new_coords, **data["options"], tags=new_tags)
        elif data["type"] == "rectangle":
            new_id = self.canvas.create_rectangle(*new_coords, **data["options"], tags=new_tags)
        elif data["type"] == "polygon":
            new_id = self.canvas.create_polygon(*new_coords, **data["options"], tags=new_tags)
        elif data["type"] == "text":
            new_id = self.canvas.create_text(*new_coords, **data["options"], tags=new_tags)

        # If it was a group (like a room), re-bind drag
        if old_group_tag and new_group_tag:
            self.canvas.tag_bind(new_group_tag, "<Button-1>", self.start_drag_room)
            self.canvas.tag_bind(new_group_tag, "<B1-Motion>", self.drag_room)
            self.canvas.tag_bind(new_group_tag, "<ButtonRelease-1>", self.end_drag_room)

        if new_id:
            print("✅ Pasted item.")
        
        self._finish_paste()

    def _finish_paste(self):
        self.paste_ready = False
        self.model.set("paste_mode", False)
        

    def select_shape(self, event):
        item = self.canvas.find_closest(event.x, event.y)[0]
        self.selected_item = item
        print("Selected:", item)

#== coordinate system ===#
    def draw_line_by_coords(self, x1, y1, x2, y2):
        px1, py1 = self.view.real_to_pixel(x1, y1)
        px2, py2 = self.view.real_to_pixel(x2, y2)

        line_id = self.canvas.create_line(px1, py1, px2, py2, fill=self.model.line_color, width=2)
        self.actions.log({"type": "create", "items": [line_id]})
        self.canvas.tag_raise(line_id)

    def draw_rectangle_by_coords(self, x1, y1, x2, y2):
        px1, py1 = self.view.real_to_pixel(x1, y1)
        px2, py2 = self.view.real_to_pixel(x2, y2)

        rect_id = self.canvas.create_rectangle(
            px1, py1, px2, py2,
            fill=self.model.fill_color or "#d0f0c0",
            outline=self.model.line_color,
            width=2
        )
        self.actions.log({"type": "create", "items": [rect_id]})
        self.canvas.tag_raise(rect_id)

    def draw_circle_by_coords(self, x, y, radius):
        px, py = self.view.real_to_pixel(x, y)
        pixel_radius = radius / self.model.unit_scale[self.model.unit] * self.model.grid_spacing * self.model.zoom_level

        oval_id = self.canvas.create_oval(
            px - pixel_radius, py - pixel_radius,
            px + pixel_radius, py + pixel_radius,
            fill=self.model.fill_color or "#d0f0c0",
            outline=self.model.line_color,
            width=2
        )
        self.actions.log({"type": "create", "items": [oval_id]})
        self.canvas.tag_raise(oval_id)
    def set_coord_label(self, label):
        self.coord_label = label

    def update_coord_label(self, event):
        if self.coord_label:
            real_x, real_y = self.view.pixel_to_real(event.x, event.y)
            self.coord_label.configure(text=f"Coordinates: ({real_x:.2f}, {real_y:.2f})")

    def toggle_canvas_freeze(self):
        self.canvas_frozen = not self.canvas_frozen
        state = "frozen" if self.canvas_frozen else "active"
        print(f"🧊 Canvas is now {state}.")

        # Optional visual cue
        if self.canvas_frozen:
            self.canvas.config(cursor="X_cursor")  # Freeze look
        else:
            self.canvas.config(cursor="arrow")     # Back to normal



    def rotate_selected_furniture(self, clockwise=True):
        """Rotate selected furniture 15 degrees in the requested screen direction."""
        obj = getattr(self, "selected_furniture_obj", None)
        if not obj:
            show_message("info", "Rotate Furniture", "Select furniture first.")
            return False
        # Pillow positive angles are anti-clockwise.
        if not obj.rotate(-15 if clockwise else 15):
            return False
        if self._is_door_furniture(obj):
            self.recompute_all_door_cuts()
        return True

    def rotate_selected_furniture_counterclockwise(self):
        return self.rotate_selected_furniture(clockwise=False)

    def reset_selected_furniture_rotation(self):
        obj = getattr(self, "selected_furniture_obj", None)
        if not obj:
            show_message("info", "Reset Rotation", "Select furniture first.")
            return False
        if not obj.set_rotation(getattr(obj, "initial_angle", 0)):
            return False
        if self._is_door_furniture(obj):
            self.recompute_all_door_cuts()
        return True

    def edit_selected_item(self):
        if self.selected_window:
            return self.edit_selected_window()
        if self.selected_furniture_obj:
            return self.enter_furniture_edit_mode(self.selected_furniture_obj)
        show_message("info", "Edit Selected", "Select a furniture item or window first.")
        return False

    def resize_selected_furniture(self, factor):
        obj = self.selected_furniture_obj
        if not obj:
            show_message("info", "Resize Furniture", "Select furniture first.")
            return False
        self.enter_furniture_edit_mode(obj)
        obj.resize(factor)
        return True

    def set_selected_furniture_size(self):
        obj = self.selected_furniture_obj
        if not obj:
            show_message("info", "Furniture Size", "Select furniture first.")
            return False
        current = obj.real_size_ft or (3.0, 3.0)
        width = simpledialog.askfloat("Furniture Size", "Width (feet):", initialvalue=current[0], minvalue=0.1, parent=self.root)
        if width is None:
            return False
        depth = simpledialog.askfloat("Furniture Size", "Depth (feet):", initialvalue=current[1], minvalue=0.1, parent=self.root)
        if depth is None:
            return False
        self.enter_furniture_edit_mode(obj)
        obj.set_exact_size(width, depth)
        return True

    def create_room_from_closed_lines(self):
        """Convert the newest clean four-line axis-aligned loop into a real room."""
        import itertools
        lines = list(self.canvas.find_withtag("committed_line"))[-12:]
        tolerance = 12.0
        chosen = None
        for combo in reversed(list(itertools.combinations(lines, 4))):
            segments = [self.canvas.coords(item) for item in combo]
            if any(len(c) != 4 or (abs(c[0] - c[2]) > tolerance and abs(c[1] - c[3]) > tolerance) for c in segments):
                continue
            points = [(c[i], c[i + 1]) for c in segments for i in (0, 2)]
            clusters = []
            for point in points:
                for cluster in clusters:
                    if math.dist(point, cluster[0]) <= tolerance:
                        cluster.append(point)
                        break
                else:
                    clusters.append([point])
            if len(clusters) == 4 and all(len(cluster) == 2 for cluster in clusters):
                chosen = combo, [
                    (sum(p[0] for p in cluster) / len(cluster), sum(p[1] for p in cluster) / len(cluster))
                    for cluster in clusters
                ]
                break
        if not chosen:
            show_message("error", "Create Room", "Draw one clean closed rectangle with four joined lines first.")
            return False
        combo, corners = chosen
        xs, ys = [p[0] for p in corners], [p[1] for p in corners]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        unit_scale = self.model.unit_scale.get(self.model.unit, 1.0)
        scale = self.model.grid_spacing * self.model.zoom_level
        width, height = (x1 - x0) / scale * unit_scale, (y1 - y0) / scale * unit_scale
        name = simpledialog.askstring("Create Room", "Room name:", parent=self.root)
        if not name:
            return False
        room = self.insert_room_template(name.strip(), width, height)
        if not room:
            return False
        self.canvas.move(room.group_tag, x0 - room.x0, y0 - room.y0)
        room.sync_to_canvas()
        for polygon in self.canvas.find_withtag("closed_shape"):
            bbox = self.canvas.bbox(polygon)
            if bbox and all(abs(value - target) <= tolerance for value, target in zip(bbox, (x0, y0, x1, y1))):
                self.canvas.delete(polygon)
        for line in combo:
            tags = self.canvas.gettags(line)
            line_tag = next((tag for tag in tags if tag.startswith("line_")), None)
            if line_tag:
                for item in self.canvas.find_withtag(line_tag):
                    self.canvas.delete(item)
            else:
                self.canvas.delete(line)
        return True

    def delete_selected_furniture(self):
        """Delete the selected item through the shared undo-aware path."""
        obj = getattr(self, "selected_furniture_obj", None)
        if obj:
            return self.delete_furniture_item(obj)
        if self.selected_window:
            return self.delete_selected_window()
        print("No furniture or window selected for deletion")
        return False

    def enable_window_mode(self):
        self.reset_modes()
        self.window_mode = True
        self.model.set("window_mode", True)
        self.canvas.config(cursor="crosshair")

    def _window_room_side(self, x, y):
        best = None
        for room in self.room_entities_by_group_tag.values():
            if getattr(room, "fill_mode", "") != "walls_only":
                continue
            coords = self.canvas.coords(room.rect_id)
            if len(coords) < 4:
                continue
            x0, y0, x1, y1 = map(float, coords[:4])
            candidates = ((abs(y - y0), "top"), (abs(y - y1), "bottom"), (abs(x - x0), "left"), (abs(x - x1), "right"))
            distance, side = min(candidates)
            inside = (x0 - 12 <= x <= x1 + 12) if side in ("top", "bottom") else (y0 - 12 <= y <= y1 + 12)
            if inside and (best is None or distance < best[0]):
                best = distance, room, side
        return best if best and best[0] <= 18 else None

    def place_window(self, event):
        x, y = self._event_to_canvas_coords(event)
        match = self._window_room_side(x, y)
        if not match:
            show_message("error", "Window", "Click on a wall of a Walls Only room.")
            return False
        _, room, side = match
        width = simpledialog.askfloat("Window", f"Window width ({self.model.unit}):", initialvalue=4.0, minvalue=0.1, parent=self.root)
        if width is None:
            return False
        window_type = simpledialog.askstring("Window", "Type (sliding/casement/fixed):", initialvalue="sliding", parent=self.root) or "sliding"
        unit_scale = self.model.unit_scale.get(self.model.unit, 1.0)
        width_px = width / unit_scale * self.model.grid_spacing * self.model.zoom_level
        coords = self.canvas.coords(room.rect_id)
        axis_min, axis_max, center = (coords[0], coords[2], x) if side in ("top", "bottom") else (coords[1], coords[3], y)
        start, end = max(axis_min, center - width_px / 2), min(axis_max, center + width_px / 2)
        self._record_manual_wall_erase(room, side, start, end)
        window = {
            "id": f"window_{len(self.windows) + 1}_{int(x)}_{int(y)}",
            "room_group_tag": room.group_tag,
            "wall_side": side,
            "start": start / self.model.zoom_level,
            "end": end / self.model.zoom_level,
            "window_type": window_type.strip() or "sliding",
        }
        self.windows.append(window)
        self._refresh_window_room(room)
        self.select_window(window)
        self.window_mode = False
        self.model.set("window_mode", False)
        self.canvas.config(cursor="arrow")
        return True

    def _draw_window_object(self, window):
        room = self.room_entities_by_group_tag.get(window.get("room_group_tag"))
        if not room:
            return
        coords = self.canvas.coords(room.rect_id)
        if len(coords) < 4:
            return
        side, zoom = window["wall_side"], self.model.zoom_level
        start, end = window["start"] * zoom, window["end"] * zoom
        thickness = max(4.0, float(room._wall_thickness_pixels()))
        if side in ("top", "bottom"):
            wall = coords[1] if side == "top" else coords[3]
            line_coords = ((start, wall - thickness / 4, end, wall - thickness / 4), (start, wall + thickness / 4, end, wall + thickness / 4))
        else:
            wall = coords[0] if side == "left" else coords[2]
            line_coords = ((wall - thickness / 4, start, wall - thickness / 4, end), (wall + thickness / 4, start, wall + thickness / 4, end))
        tags = ("window_object", "window_symbol", window["id"], room.group_tag)
        color = "#FACC15" if self.selected_window is window else "#1687D9"
        window["item_ids"] = [self.canvas.create_line(*line, fill=color, width=2, tags=tags) for line in line_coords]
        for item in window["item_ids"]:
            self.canvas.tag_bind(item, "<Button-1>", lambda _event, w=window: self.select_window(w))

    def clear_window_selection(self):
        for window in self.windows:
            for item in window.get("item_ids", []):
                try:
                    self.canvas.itemconfig(item, fill="#1687D9", width=2)
                except Exception:
                    pass
        self.selected_window = None

    def select_window(self, window):
        self.clear_window_selection()
        self.select_item_by_id(None)
        self.selected_window = window
        self.clear_furniture_selection()
        for item in window.get("item_ids", []):
            try:
                self.canvas.itemconfig(item, fill="#FACC15", width=2)
            except Exception:
                pass
        return "break"

    def _refresh_window_room(self, room):
        # Preserve this room's existing door openings while rebuilding its window gaps.
        group_tag = getattr(room, "group_tag", "")
        zoom = max(float(getattr(self.model, "zoom_level", 1.0)), 1e-9)
        door_regions = {}
        registry = getattr(self, "_door_cut_registry", None)
        if registry:
            for side in ("top", "bottom", "left", "right"):
                intervals = registry.get_merged(group_tag, side)
                if intervals:
                    door_regions[side] = [[float(start) / zoom, float(end) / zoom] for start, end in intervals]
        self._reset_room_after_door_cuts(room)
        coords = self.canvas.coords(room.rect_id)
        regions = {
            side: [list(interval) for interval in intervals]
            for side, intervals in (getattr(room, "_manual_wall_erased_regions", {}) or {}).items()
        }
        for side, intervals in door_regions.items():
            regions.setdefault(side, []).extend(intervals)
        self.apply_wall_erased_regions(room, regions, *map(float, coords[:4]))
        if registry:
            x0, y0, x1, y1 = map(float, coords[:4])
            for side, intervals in door_regions.items():
                wall_min, wall_max = (x0, x1) if side in ("top", "bottom") else (y0, y1)
                for start, end in intervals:
                    registry.add_cut(group_tag, side, start * zoom, end * zoom, wall_min=wall_min, wall_max=wall_max)
        for window in self.windows:
            if window.get("room_group_tag") == room.group_tag:
                for item in window.get("item_ids", []):
                    self.canvas.delete(item)
                self._draw_window_object(window)

    def _remove_window_interval(self, window):
        room = self.room_entities_by_group_tag.get(window.get("room_group_tag"))
        if not room:
            return None
        regions = getattr(room, "_manual_wall_erased_regions", {})
        side = window["wall_side"]
        regions[side] = [iv for iv in regions.get(side, []) if abs(iv[0] - window["start"]) > 0.01 or abs(iv[1] - window["end"]) > 0.01]
        return room

    def edit_selected_window(self):
        window = self.selected_window
        if not window:
            show_message("info", "Edit Window", "Select a blue window first.")
            return False
        room = self.room_entities_by_group_tag.get(window.get("room_group_tag"))
        if not room:
            return False
        current_width = (window["end"] - window["start"]) * self.model.unit_scale.get(self.model.unit, 1.0) / self.model.grid_spacing
        width = simpledialog.askfloat("Edit Window", f"Width ({self.model.unit}):", initialvalue=current_width, minvalue=0.1, parent=self.root)
        if width is None:
            return False
        unit_scale = self.model.unit_scale.get(self.model.unit, 1.0)
        room_coords = self.canvas.coords(room.rect_id)
        axis_origin = (room_coords[0] if window["wall_side"] in ("top", "bottom") else room_coords[1]) / self.model.zoom_level
        current_offset = ((window["start"] + window["end"]) / 2 - axis_origin) * unit_scale / self.model.grid_spacing
        offset = simpledialog.askfloat("Edit Window", f"Center offset from wall start ({self.model.unit}):", initialvalue=current_offset, minvalue=0.0, parent=self.root)
        if offset is None:
            return False
        window_type = simpledialog.askstring("Edit Window", "Type:", initialvalue=window.get("window_type", "sliding"), parent=self.root)
        self._remove_window_interval(window)
        center = axis_origin + offset / unit_scale * self.model.grid_spacing
        half = width / unit_scale * self.model.grid_spacing / 2
        axis_limit = (room_coords[2] if window["wall_side"] in ("top", "bottom") else room_coords[3]) / self.model.zoom_level
        window["start"], window["end"] = max(axis_origin, center - half), min(axis_limit, center + half)
        window["window_type"] = window_type or window.get("window_type", "sliding")
        regions = getattr(room, "_manual_wall_erased_regions", {})
        regions.setdefault(window["wall_side"], []).append([window["start"], window["end"]])
        self._refresh_window_room(room)
        return True

    def delete_selected_window(self):
        window = self.selected_window
        if not window:
            return False
        room = self._remove_window_interval(window)
        for item in window.get("item_ids", []):
            self.canvas.delete(item)
        if window in self.windows:
            self.windows.remove(window)
        self.selected_window = None
        if room:
            self._refresh_window_room(room)
        return True

    def load_window_object(self, data):
        window = dict(data)
        window.pop("item_ids", None)
        self.windows.append(window)
        self._draw_window_object(window)
        return window
            
#compass
    def draw_compass(self, direction="N", angle=None):
        """Draw compass. Use angle (0-360) if provided, else use direction string."""
        # Remove previous compass if any
        if hasattr(self, 'compass_items'):
            for item in self.compass_items:
                self.canvas.delete(item)
        
        self.compass_items = []

        # Compass position
        x_center, y_center = 60, 60
        size = 30

        # Direction angles
        direction_map = {
            "N": 90,
            "E": 0,
            "S": 270,
            "W": 180,
            "NE": 45,
            "SE": 315,
            "SW": 225,
            "NW": 135
        }

        if angle is not None:
            try:
                angle = float(angle) % 360.0
            except (TypeError, ValueError):
                angle = direction_map.get(str(direction).upper(), 90)
        else:
            angle = direction_map.get(str(direction).upper(), 90)
        
        import math

        items = [
            self.canvas.create_oval(
                x_center - size, y_center - size, x_center + size, y_center + size,
                outline="#94A3B8", width=1, fill="", tags="compass",
            )
        ]

        # North sits at `angle`; each following cardinal is 90 deg clockwise (angle - 90).
        label_radius = size + 13
        tick_inner = size - 7
        for name, cardinal_angle, color in (
            ("N", angle, "#DC2626"),
            ("E", angle - 90, "#334155"),
            ("S", angle - 180, "#334155"),
            ("W", angle - 270, "#334155"),
        ):
            r = math.radians(cardinal_angle % 360.0)
            cx, cy = math.cos(r), -math.sin(r)
            items.append(self.canvas.create_line(
                x_center + tick_inner * cx, y_center + tick_inner * cy,
                x_center + size * cx, y_center + size * cy,
                fill=color, width=2, tags="compass",
            ))
            items.append(self.canvas.create_text(
                x_center + label_radius * cx, y_center + label_radius * cy,
                text=name, font=("Arial", 10, "bold"), fill=color, tags="compass",
            ))

        # Red arrow pointing to North.
        r = math.radians(angle)
        items.append(self.canvas.create_line(
            x_center, y_center, x_center + size * math.cos(r), y_center - size * math.sin(r),
            arrow=tk.LAST, width=3, fill="#DC2626", tags="compass",
        ))

        self.compass_items = items
        angle_deg = angle
        direction_str = direction if isinstance(direction, str) else ""
        self.current_compass_direction = direction_str or str(angle_deg)
        self.current_compass_angle = angle_deg
        valid_directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        if (
            direction_str
            and direction_str.upper() in valid_directions
            and hasattr(self, "compass_combo_widget")
            and self.compass_combo_widget
        ):
            try:
                self.compass_combo_widget.set(direction_str.upper())
            except Exception:
                pass

#=== Auto place furniture ===#
    def toggle_canvas_freeze(self):
        self.canvas_frozen = not self.canvas_frozen
        state = "frozen" if self.canvas_frozen else "active"
        print(f"🧊 Canvas is now {state}.")

        # Optional visual cue
        if self.canvas_frozen:
            self.canvas.config(cursor="X_cursor")  # Freeze look
        else:
            self.canvas.config(cursor="arrow")     # Back to normal
    def insert_furniture(self, name, x, y, room_width=None, room_height=None):
     from Furniture import Furniture, find_image_path
     from PIL import Image

     path = find_image_path(name.lower().replace(" ", "_"))
     if not path:
        print(f"No image for {name}")
        return

     # Load image size
     img = Image.open(path)
     img_width, img_height = img.size

    # Compute target scale based on room size if available
     if room_width and room_height:
        padding_factor = 0.8  # keep some margin
        max_scale_w = (room_width * padding_factor) / img_width
        max_scale_h = (room_height * padding_factor) / img_height
        scale = min(max_scale_w, max_scale_h)
     else:
        scale = self.model.zoom_level  # fallback default

     obj = Furniture(
        self.canvas,
        path,
        x, y,
        select_callback=self.select_furniture_item,
        scale=scale,
        angle=0,
        get_freeze_state=self.get_canvas_freeze_state,
        edit_callback=self.enter_furniture_edit_mode,
        duplicate_callback=self.duplicate_furniture,
        delete_callback=self.delete_furniture_item,
     )

     if not hasattr(self, 'furniture_objects'):
        self.furniture_objects = []
     self.furniture_objects.append(obj)


    def show_furniture_selection_dialog(self, suggested_furniture, room_name, center_x, center_y, room_bbox, room_width_real, room_height_real):
        """Room-suggestion furniture picker: same card-style UI as main furniture place dialog."""
        try:
            import ttkbootstrap as ttkb
        except ImportError:
            ttkb = None

        def _place_selected(vars_dict, dlg):
            offset_x = offset_y = 0
            for name, var in vars_dict.items():
                if var.get() == 1:
                    self.insert_furniture_scaled(
                        name,
                        center_x + offset_x,
                        center_y + offset_y,
                        room_bbox,
                        room_width_real,
                        room_height_real,
                    )
                    offset_x += 50
                    if offset_x > 100:
                        offset_x = 0
                        offset_y += 50
            dlg.destroy()

        if ttkb is not None:
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Select Furniture for {room_name}")
            dialog.geometry("720x520")
            dialog.transient(self.root)
            try:
                from Helper.set_window_icon import set_window_icon
                set_window_icon(dialog)
            except Exception:
                pass
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (720 // 2)
            y = (dialog.winfo_screenheight() // 2) - (520 // 2)
            dialog.geometry(f"720x520+{x}+{y}")
            try:
                dialog.grab_set()
            except Exception:
                pass

            main_frame = ttkb.Frame(dialog, padding=12)
            main_frame.pack(fill="both", expand=True)

            ttkb.Label(
                main_frame,
                text=f"Furniture for {room_name}",
                font=("Arial", 18, "bold"),
            ).pack(anchor="w", pady=(0, 4))
            ttkb.Label(
                main_frame,
                text="Select items to place, then click Apply.",
                font=("Arial", 10),
                bootstyle="secondary",
            ).pack(anchor="w", pady=(0, 10))
            try:
                ttkb.Separator(main_frame).pack(fill="x", pady=(0, 8))
            except Exception:
                pass

            scroll_container = ttkb.Frame(main_frame, padding=2)
            scroll_container.pack(fill="both", expand=True, pady=(0, 10))
            canvas = tk.Canvas(scroll_container, highlightthickness=0, bd=0)
            vscroll = ttkb.Scrollbar(scroll_container, orient="vertical", command=canvas.yview, bootstyle="round")
            canvas.configure(yscrollcommand=vscroll.set)
            vscroll.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            grid_frame = ttkb.Frame(canvas)
            canvas.create_window((0, 0), window=grid_frame, anchor="nw")

            def _on_configure(_e):
                canvas.configure(scrollregion=canvas.bbox("all"))

            grid_frame.bind("<Configure>", _on_configure)

            vars_dict = {}
            cols = 3
            try:
                from Furniture import find_image_path
                from PIL import Image
            except Exception:
                find_image_path = None
                Image = None

            for idx, name in enumerate(suggested_furniture):
                row, col = idx // cols, idx % cols
                card = ttkb.Frame(grid_frame, padding=8)
                card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
                try:
                    card.grid_propagate(False)
                except Exception:
                    pass
                card.configure(width=200, height=200)

                inner = ttkb.Frame(card)
                inner.pack(fill="both", expand=True)
                img_box = ttkb.Frame(inner, width=100, height=90)
                img_box.pack(pady=(0, 6))
                try:
                    img_box.pack_propagate(False)
                except Exception:
                    pass
                if find_image_path and Image:
                    path = find_image_path(name.lower().replace(" ", "_"))
                    if path:
                        try:
                            img = Image.open(path).convert("RGBA")
                            img.thumbnail((90, 90), Image.Resampling.LANCZOS)
                            from PIL import ImageTk
                            photo = ImageTk.PhotoImage(img)
                            lbl = ttkb.Label(img_box, image=photo)
                            lbl.image = photo
                            lbl.pack(expand=True)
                        except Exception:
                            ttkb.Label(img_box, text="—", bootstyle="secondary").pack(expand=True)
                    else:
                        ttkb.Label(img_box, text="—", bootstyle="secondary").pack(expand=True)
                else:
                    ttkb.Label(img_box, text="—", bootstyle="secondary").pack(expand=True)

                ttkb.Label(
                    inner,
                    text=name.replace("_", " ").title(),
                    font=("Arial", 11, "bold"),
                    wraplength=180,
                ).pack(pady=(0, 6))
                var = tk.IntVar(value=1)
                vars_dict[name] = var
                ttkb.Checkbutton(
                    inner,
                    text="Place",
                    variable=var,
                    bootstyle="round-toggle",
                ).pack(anchor="w")
                for c in range(cols):
                    grid_frame.grid_columnconfigure(c, weight=1)

            try:
                ttkb.Separator(main_frame).pack(fill="x", pady=(0, 8))
            except Exception:
                pass
            action_frame = ttkb.Frame(main_frame, padding=(0, 4))
            action_frame.pack(fill="x", pady=(8, 0))
            ttkb.Button(
                action_frame,
                text="Apply",
                command=lambda: _place_selected(vars_dict, dialog),
                bootstyle="primary",
            ).pack(side="left", padx=6, pady=6)
            ttkb.Button(
                action_frame,
                text="Cancel",
                command=dialog.destroy,
                bootstyle="secondary-outline",
            ).pack(side="left", padx=6, pady=6)
            try:
                dialog.bind("<Escape>", lambda e: dialog.destroy())
            except Exception:
                pass
            return

        import tkinter as tk
        from tkinter import Toplevel, Checkbutton, IntVar, Button, Label, Frame
        _bg, _fg = "#2e2e2e", "#e0e0e0"
        _btn_bg, _btn_fg = "#404040", "#ffffff"
        dialog = Toplevel(self.root)
        dialog.title(f"Select Furniture for {room_name}")
        dialog.geometry("320x420")
        dialog.configure(bg=_bg)
        try:
            from Helper.set_window_icon import set_window_icon
            set_window_icon(dialog)
        except Exception:
            pass
        main = Frame(dialog, bg=_bg, padx=12, pady=12)
        main.pack(fill="both", expand=True)
        Label(main, text="Select items to place", bg=_bg, fg=_fg, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))
        vars_dict = {}
        for name in suggested_furniture:
            var = IntVar(value=1)
            Checkbutton(
                main, text=name.replace("_", " ").title(), variable=var,
                bg=_bg, fg=_fg, selectcolor="#444444", activebackground=_bg, activeforeground=_fg,
                highlightthickness=0, font=("Arial", 10),
            ).pack(anchor="w", padx=4, pady=2)
            vars_dict[name] = var
        Button(
            main, text="Apply", command=lambda: _place_selected(vars_dict, dialog),
            bg=_btn_bg, fg=_btn_fg, activebackground="#505050", activeforeground=_btn_fg,
            highlightthickness=0, font=("Arial", 10), relief="flat", padx=16, pady=6,
        ).pack(pady=12)


    def get_canvas_freeze_state(self):
     return getattr(self, "canvas_frozen", False)
 
    def select_furniture_item(self, name):
     # Your selection logic: e.g., highlight, delete, show handles
        self.reset_modes()
        self.model.set("furniture_mode", True)
        self.selected_furniture = name
        self.canvas.config(cursor="hand2")

    # ✅ Bind mouse click to place furniture
        # self.canvas.bind("<Button-1>", self.place_furniture)

    def apply_zoom_to_furniture(self):
     zoom = self.model.zoom_level
     if hasattr(self, 'furniture_objects'):
        for obj in self.furniture_objects:
            obj.apply_global_zoom(zoom)

    def insert_furniture_scaled(self, name, x, y, room_bbox, room_width_real, room_height_real):
        from Furniture import Furniture, find_image_path, furniture_data
        from PIL import Image

        # Auto-commit any uncommitted furniture before placing a new one
        self.auto_commit_uncommitted_furniture()

        path = find_image_path(name.lower().replace(" ", "_"))
        if not path:
            print(f"No image for {name}")
            return None

        # Load image and remove padding to get exact furniture size
        from Furniture import remove_padding
        img = Image.open(path).convert("RGBA")
        img = remove_padding(img)  # Remove padding/transparency
        img_width, img_height = img.size

        # Get standard size in feet from STANDARD_FURNITURE_SIZES - normalize name for lookup
        normalized_name = name.lower().replace(" ", "")
        # Try normalized name first, then try with underscore
        real_w_ft, real_h_ft = furniture_data.STANDARD_FURNITURE_SIZES.get(normalized_name) or \
                               furniture_data.STANDARD_FURNITURE_SIZES.get(normalized_name.replace("_", "")) or \
                               furniture_data.STANDARD_FURNITURE_SIZES.get(name.lower().replace(" ", "_")) or \
                               (3, 3)
        # Standard sizes are in feet. Convert standard feet size into current active unit.
        try:
            active_unit = str(self.model.unit).lower()
            if active_unit == "m":
                conversion_factor = 1.0 / 3.28084
            elif active_unit == "cm":
                conversion_factor = 100.0 / 3.28084
            elif active_unit == "in":
                conversion_factor = 12.0
            elif active_unit == "yards":
                conversion_factor = 1.0 / 3.0
            else:
                conversion_factor = 1.0
        except Exception:
            conversion_factor = 1.0

        real_w_ft *= conversion_factor
        real_h_ft *= conversion_factor
        print(f"Furniture name: {name} -> normalized: {normalized_name} -> size: {real_w_ft} {self.model.unit} x {real_h_ft} {self.model.unit}")

        # Scale furniture according to layout/grid size
        # Match the grid drawing formula: pixel_interval = spacing * zoom / unit_scale
        # So 1 foot = (grid_spacing * zoom) / unit_scale pixels
        unit_factor = self.model.unit_scale[self.model.unit]
        # Use same formula as grid drawing to ensure furniture matches visual grid
        pixels_per_foot = (self.model.grid_spacing * self.model.zoom_level) / unit_factor
        target_w_px = real_w_ft * pixels_per_foot
        target_h_px = real_h_ft * pixels_per_foot

        # Debug output
        print(f"Furniture: {name}, Size: {real_w_ft}ft x {real_h_ft}ft")
        print(f"Image size: {img_width}x{img_height}, Target: {target_w_px:.1f}x{target_h_px:.1f}px")
        print(f"Grid spacing: {self.model.grid_spacing}, Zoom: {self.model.zoom_level}, Unit factor: {unit_factor}")

        # Calculate scale to match layout grid size
        scale_w = target_w_px / img_width if img_width > 0 else 1.0
        scale_h = target_h_px / img_height if img_height > 0 else 1.0
        # For all furniture, use max scale to ensure both dimensions meet or exceed target
        # This ensures furniture matches exact target dimensions
        scale = max(scale_w, scale_h)  # Use max to ensure both dimensions meet or exceed target
        print(f"Calculated scale: {scale:.3f} (w: {scale_w:.3f}, h: {scale_h:.3f})")
        print(f"Final size will be: {img_width * scale:.1f}x{img_height * scale:.1f}px")
        print(f"Target was: {target_w_px:.1f}x{target_h_px:.1f}px for {real_w_ft}ft x {real_h_ft}ft")
        scale = max(0.05, min(scale, 20.0))  # Allow scale up to 20.0 for proper sizing

        # For all furniture, pass target_size to force exact target dimensions
        is_square = abs(real_w_ft - real_h_ft) < 0.1
        target_size = (int(target_w_px), int(target_h_px))  # Force exact size for all furniture
        if is_square:
            print(f"Forcing square furniture to exact size: {target_size}")
        else:
            print(f"Forcing rectangular furniture to exact size: {target_size}")

        # Use the provided placement coords
        center_x = x
        center_y = y

        # create furniture
        furniture_item = Furniture(
            canvas=self.canvas,
            image_path=path,
            x=center_x,
            y=center_y,
            select_callback=self.select_image_item,
            scale=scale,
            angle=0,
            get_freeze_state=self.get_canvas_freeze_state,
            edit_callback=self.enter_furniture_edit_mode,
            duplicate_callback=self.duplicate_furniture,
            delete_callback=self.delete_furniture_item,
            target_size=target_size,  # Pass target size for square furniture
        )

        # Store real size in feet and model reference for zoom updates
        furniture_item.real_size_ft = (real_w_ft, real_h_ft)
        furniture_item.model_ref = self.model

        # track and return
        self.image_furniture_items.append(furniture_item)
        self.select_image_item(furniture_item)
        self.canvas.itemconfig(furniture_item.image_id, tags=("furniture",))

        # Lock furniture by default; require right-click → Edit for modifications.
        # Try to commit to underlying room/polygon so it follows group drags.
        try:
            ok = self.commit_furniture_to_underlying_group(furniture_item)
        except Exception:
            ok = False
        if not ok:
            try:
                furniture_item.committed = True
                furniture_item.editing = False
            except Exception:
                pass

        # If this furniture is a door (by name), mark and cut wall once so that
        # JSON-loaded layouts get the same door gap behavior as newly placed doors.
        try:
            if "door" in str(name).lower():
                try:
                    setattr(furniture_item, "is_door", True)
                except Exception:
                    pass
                # real_w_ft / real_h_ft are in current units already
                self._cut_wall_for_door(furniture_item, real_w_ft, real_h_ft)
                try:
                    self.canvas.tag_raise(furniture_item.image_id)
                except Exception:
                    pass
        except Exception:
            pass

        return furniture_item


    def place_furniture_in_room(self, item_name, canvas, room_bbox):
     x0, y0, x1, y1 = room_bbox
     room_width = x1 - x0
     room_height = y1 - y0

     # Place at room center
     x = (x0 + x1) / 2
     y = (y0 + y1) / 2

     if self.tools:
        self.tools.insert_furniture_scaled(item_name, x, y, room_bbox) # This call now needs



    def save_canvas_image(self):
        """Save the entire canvas as an image (PNG/JPEG).
        Uses screenshot (ImageGrab) when available for pixel-perfect capture;
        falls back to canvas render on Mac without Screen Recording permission."""
        current_window = self.root
        current_window.update_idletasks()

        # macOS: save dialog on fullscreen/overrideredirect window can crash
        was_fullscreen = False
        had_override = False
        try:
            was_fullscreen = bool(current_window.attributes("-fullscreen"))
        except Exception:
            pass
        try:
            had_override = bool(current_window.overrideredirect())
        except Exception:
            pass

        restore_needed = sys.platform == "darwin" and (was_fullscreen or had_override)
        if restore_needed:
            try:
                if was_fullscreen:
                    current_window.attributes("-fullscreen", False)
                if had_override:
                    current_window.overrideredirect(False)
                current_window.update_idletasks()
            except Exception:
                pass

        dialog_kwargs = dict(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")],
            title="Save Canvas as Image",
        )
        if not (sys.platform == "darwin" and restore_needed):
            dialog_kwargs["parent"] = current_window

        try:
            file_path = filedialog.asksaveasfilename(**dialog_kwargs)
        finally:
            if restore_needed:
                try:
                    if was_fullscreen:
                        current_window.attributes("-fullscreen", True)
                    if had_override:
                        current_window.overrideredirect(True)
                    current_window.update_idletasks()
                except Exception:
                    pass

        current_window.focus_force()
        current_window.lift()

        if not file_path:
            return

        try:
            self.canvas.update_idletasks()
            w_canvas = max(1, self.canvas.winfo_width() or 1200)
            h_canvas = max(1, self.canvas.winfo_height() or 800)
            # 1) ImageGrab (Windows, Mac with permission), 2) PostScript+gs (Mac), 3) manual render
            img = self._grab_canvas_screenshot(0, 0, w_canvas, h_canvas)
            if img is None:
                img = self._canvas_postscript_region_to_png(
                    0, 0, w_canvas, h_canvas
                )
            if img is None:
                region = self.canvas.bbox("all")
                if region:
                    x0, y0, x1, y1 = region
                    if (x1 - x0) < 1 or (y1 - y0) < 1:
                        region = None
                if not region:
                    w_ = max(1, self.canvas.winfo_width() or 1200)
                    h_ = max(1, self.canvas.winfo_height() or 800)
                    x0, y0, x1, y1 = 0, 0, w_, h_
                img = self._render_canvas_region_to_image(
                    int(x0), int(y0), int(x1), int(y1), None, include_grid=True
                )
            if file_path.lower().endswith((".jpg", ".jpeg")):
                img.convert("RGB").save(file_path, "JPEG")
            else:
                img.save(file_path, "PNG")
        except Exception as e:
            messagebox.showerror(
                "Save Canvas",
                f"Failed to save canvas image.\n\n{e}",
                parent=self.root,
            )
            return

        print(f"✅ Canvas saved to: {file_path}")
        self._prompt_create_project_from_image(file_path)

    # === Region screenshot (Save selected area as PNG) ===
    def start_region_screenshot(self) -> None:
        """
        Enable a temporary mode where the user can drag on the canvas
        to select a rectangular region, then save that region as a PNG.
        """
        # Reset other modes so drawing tools don't interfere
        try:
            self.reset_modes()
        except Exception:
            pass

        # Clear any previous screenshot state
        self._screenshot_start = None
        if self._screenshot_rect_id:
            try:
                self.canvas.delete(self._screenshot_rect_id)
            except Exception:
                pass
            self._screenshot_rect_id = None

        # Update cursor to indicate selection mode
        try:
            self.canvas.config(cursor="crosshair")
        except Exception:
            pass

        # Bind mouse events for drag-selection
        self._screenshot_bind_ids = {}
        self._screenshot_bind_ids["<ButtonPress-1>"] = self.canvas.bind(
            "<ButtonPress-1>", self._on_screenshot_start
        )
        self._screenshot_bind_ids["<B1-Motion>"] = self.canvas.bind(
            "<B1-Motion>", self._on_screenshot_drag
        )
        self._screenshot_bind_ids["<ButtonRelease-1>"] = self.canvas.bind(
            "<ButtonRelease-1>", self._on_screenshot_end
        )

    def _end_region_screenshot_mode(self) -> None:
        """Cleanup bindings and visual rectangle for screenshot mode."""
        # Restore cursor
        try:
            self.canvas.config(cursor="arrow")
        except Exception:
            pass

        # Remove bindings
        try:
            for seq, bid in (self._screenshot_bind_ids or {}).items():
                if bid:
                    try:
                        self.canvas.unbind(seq, bid)
                    except Exception:
                        # Some Tk builds don't take the id argument
                        try:
                            self.canvas.unbind(seq)
                        except Exception:
                            pass
        except Exception:
            pass
        self._screenshot_bind_ids = {}

        # Remove selection rectangle
        if self._screenshot_rect_id:
            try:
                self.canvas.delete(self._screenshot_rect_id)
            except Exception:
                pass
            self._screenshot_rect_id = None

        self._screenshot_start = None

    def _on_screenshot_start(self, event) -> None:
        self._screenshot_start = (event.x, event.y)
        # Remove any previous rectangle
        if self._screenshot_rect_id:
            try:
                self.canvas.delete(self._screenshot_rect_id)
            except Exception:
                pass
            self._screenshot_rect_id = None

        self._screenshot_rect_id = self.canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="orange",
            width=2,
            dash=(4, 2),
            tags=("screenshot_region",),
        )
        # Keep on top of other items
        try:
            self.canvas.tag_raise(self._screenshot_rect_id)
        except Exception:
            pass

    def _on_screenshot_drag(self, event) -> None:
        if not self._screenshot_start or not self._screenshot_rect_id:
            return
        x0, y0 = self._screenshot_start
        x1, y1 = event.x, event.y
        try:
            self.canvas.coords(self._screenshot_rect_id, x0, y0, x1, y1)
            self.canvas.tag_raise(self._screenshot_rect_id)
        except Exception:
            pass

    def _on_screenshot_end(self, event) -> None:
        if not self._screenshot_start:
            self._end_region_screenshot_mode()
            return

        x0, y0 = self._screenshot_start
        x1, y1 = event.x, event.y

        left = min(x0, x1)
        top = min(y0, y1)
        right = max(x0, x1)
        bottom = max(y0, y1)

        if right - left < 5 or bottom - top < 5:
            self._end_region_screenshot_mode()
            return

        try:
            self.canvas.update_idletasks()
            root_x = self.canvas.winfo_rootx()
            root_y = self.canvas.winfo_rooty()
            scale = 1.0
            if sys.platform != "darwin":
                try:
                    scale = float(self.root.tk.call("tk", "scaling"))
                except Exception:
                    scale = 1.0
            grab_box = (
                int((root_x + left) * scale),
                int((root_y + top) * scale),
                int((root_x + right) * scale),
                int((root_y + bottom) * scale),
            )
        except Exception:
            self._end_region_screenshot_mode()
            return

        img = None
        try:
            img = ImageGrab.grab(bbox=grab_box)
        except Exception as e:
            try:
                print(f"[MiniAutoCAD] Screenshot capture failed: {e}")
            except Exception:
                pass
            self._end_region_screenshot_mode()
            return

        # macOS: filedialog on fullscreen/overrideredirect window can crash
        current_window = self.root
        was_fullscreen = False
        had_override = False
        try:
            was_fullscreen = bool(current_window.attributes("-fullscreen"))
        except Exception:
            pass
        try:
            had_override = bool(current_window.overrideredirect())
        except Exception:
            pass
        restore_needed = sys.platform == "darwin" and (was_fullscreen or had_override)
        if restore_needed:
            try:
                if was_fullscreen:
                    current_window.attributes("-fullscreen", False)
                if had_override:
                    current_window.overrideredirect(False)
                current_window.update_idletasks()
            except Exception:
                pass

        dialog_kwargs = dict(
            title="Save selected area as PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
        )
        if not (sys.platform == "darwin" and restore_needed):
            dialog_kwargs["parent"] = current_window

        try:
            file_path = filedialog.asksaveasfilename(**dialog_kwargs)
        finally:
            if restore_needed:
                try:
                    if was_fullscreen:
                        current_window.attributes("-fullscreen", True)
                    if had_override:
                        current_window.overrideredirect(True)
                    current_window.update_idletasks()
                except Exception:
                    pass

        if sys.platform == "darwin":
            try:
                current_window.focus_force()
                current_window.lift()
            except Exception:
                pass

        if file_path:
            try:
                if not file_path.lower().endswith(".png"):
                    file_path = f"{file_path}.png"
                img.save(file_path, "PNG")
                print(f"✅ Screenshot saved to: {file_path}")
                self._prompt_create_project_from_image(file_path)
            except Exception as e:
                try:
                    print(f"[MiniAutoCAD] Failed to save screenshot: {e}")
                except Exception:
                    pass

        self._end_region_screenshot_mode()

    def _render_canvas_region_to_image(
        self, x0: int, y0: int, x1: int, y1: int, exclude_item=None, include_grid=True
    ) -> "Image.Image":
        """Render a canvas region to a PIL Image (fallback when ImageGrab unavailable)."""
        width = abs(x1 - x0)
        height = abs(y1 - y0)
        img = Image.new("RGB", (width, height), "white")
        sel_rect = (x0, y0, x1, y1)

        overlapping = self.canvas.find_overlapping(x0, y0, x1, y1)
        items_in_area = []
        for item in reversed(overlapping):
            if item == exclude_item:
                continue
            try:
                tags = self.canvas.gettags(item)
                if "selection_highlight" in tags or "screenshot_region" in tags:
                    continue
                if not include_grid and "grid" in tags:
                    continue
                if include_grid and "grid" in tags:
                    pass  # include grid
            except Exception:
                pass
            item_bbox = self.canvas.bbox(item)
            if item_bbox and self._rectangles_overlap(sel_rect, item_bbox):
                items_in_area.append(item)

        draw = ImageDraw.Draw(img)
        for item in items_in_area:
            try:
                item_type = self.canvas.type(item)
                if item_type == "image":
                    img_bbox = self.canvas.bbox(item)
                    if not img_bbox:
                        continue
                    pil_img = self._get_pil_from_canvas_image(item)
                    if pil_img is not None:
                        iw_canvas = int(img_bbox[2] - img_bbox[0])
                        ih_canvas = int(img_bbox[3] - img_bbox[1])
                        resized = pil_img.resize(
                            (iw_canvas, ih_canvas),
                            Image.Resampling.LANCZOS,
                        )
                        ix0 = max(0, int(x0 - img_bbox[0]))
                        iy0 = max(0, int(y0 - img_bbox[1]))
                        px = max(0, int(img_bbox[0] - x0))
                        py = max(0, int(img_bbox[1] - y0))
                        cw = min(width - px, iw_canvas - ix0)
                        ch = min(height - py, ih_canvas - iy0)
                        if cw > 0 and ch > 0:
                            crop = resized.crop((ix0, iy0, ix0 + cw, iy0 + ch))
                            img.paste(crop, (px, py))
                    continue
                coords = self.canvas.coords(item)

                if item_type == "line":
                    adj = [coords[i] - (x0 if i % 2 == 0 else y0) for i in range(len(coords))]
                    fill = self.canvas.itemcget(item, "fill")
                    try:
                        w = int(self.canvas.itemcget(item, "width"))
                    except Exception:
                        w = 1
                    draw.line(adj, fill=fill, width=w)

                elif item_type == "polygon" and len(coords) >= 6:
                    adj = [
                        coords[i] - (x0 if i % 2 == 0 else y0)
                        for i in range(len(coords))
                    ]
                    outline = self.canvas.itemcget(item, "outline")
                    fill = self.canvas.itemcget(item, "fill")
                    draw.polygon(
                        adj,
                        outline=outline if outline else None,
                        fill=fill if fill and fill != "" else None,
                    )

                elif item_type == "oval" and len(coords) == 4:
                    adj = [
                        coords[0] - x0, coords[1] - y0,
                        coords[2] - x0, coords[3] - y0,
                    ]
                    outline = self.canvas.itemcget(item, "outline")
                    fill = self.canvas.itemcget(item, "fill")
                    draw.ellipse(
                        adj,
                        outline=outline if outline else None,
                        fill=fill if fill and fill != "" else None,
                    )

                elif item_type == "rectangle" and len(coords) == 4 and item != exclude_item:
                    adj = [
                        coords[0] - x0, coords[1] - y0,
                        coords[2] - x0, coords[3] - y0,
                    ]
                    outline = self.canvas.itemcget(item, "outline")
                    fill = self.canvas.itemcget(item, "fill")
                    draw.rectangle(
                        adj,
                        outline=outline if outline else None,
                        fill=fill if fill and fill != "" else None,
                    )

                elif item_type == "text":
                    tx, ty = coords[0] - x0, coords[1] - y0
                    text = self.canvas.itemcget(item, "text")
                    fill = self.canvas.itemcget(item, "fill")
                    size = 10
                    try:
                        font_str = self.canvas.itemcget(item, "font")
                        parts = font_str.split()
                        if len(parts) >= 2:
                            size = max(6, min(72, int(parts[1])))
                    except Exception:
                        pass
                    font = self._load_font_for_render(size)
                    draw.text((tx, ty), text, fill=fill, font=font)
            except Exception:
                pass

        return img

    def _load_font_for_render(self, size: int = 10) -> "ImageFont.FreeTypeFont | ImageFont.ImageFont":
        """Load a cross-platform font for canvas-to-image text rendering."""
        font_names = ["Arial", "DejaVuSans", "LiberationSans", "Helvetica"]
        if sys.platform == "darwin":
            arial_paths = [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
            for p in arial_paths:
                if os.path.exists(p):
                    try:
                        return ImageFont.truetype(p, size)
                    except Exception:
                        pass
        elif sys.platform != "win32":
            for name in font_names:
                for base in ["/usr/share/fonts", "/usr/local/share/fonts"]:
                    for ext in ["ttf", "ttc"]:
                        path = os.path.join(base, "truetype", "dejavu", f"DejaVuSans.{ext}")
                        if os.path.exists(path):
                            try:
                                return ImageFont.truetype(path, size)
                            except Exception:
                                pass
        for name in font_names:
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _rectangles_overlap(self, rect1: tuple, rect2: tuple) -> bool:
        """Check if two rectangles overlap."""
        x1_min, y1_min, x1_max, y1_max = rect1
        x2_min, y2_min, x2_max, y2_max = rect2
        if x1_max < x2_min or x2_max < x1_min:
            return False
        if y1_max < y2_min or y2_max < y1_min:
            return False
        return True

    def _find_ghostscript_binary(self) -> str:
        """Find ghostscript for PostScript to PNG. Mac: Homebrew paths."""
        if sys.platform == "darwin":
            for p in ["/opt/homebrew/bin/gs", "/usr/local/bin/gs"]:
                if os.path.isfile(p):
                    return p
        candidates = (
            ["gswin64c", "gswin32c"] if sys.platform == "win32" else ["gs"]
        )
        for name in candidates:
            path = shutil.which(name)
            if path:
                return path
        return ""

    def _canvas_postscript_region_to_png(
        self, x0: int, y0: int, x1: int, y1: int
    ) -> "Image.Image | None":
        """
        Use Tk postscript + Ghostscript for pixel-perfect capture.
        Works on Mac without Screen Recording - same output as Windows ImageGrab.
        Returns None if ghostscript unavailable.
        """
        w = max(1, abs(x1 - x0))
        h = max(1, abs(y1 - y0))
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".ps", delete=False
            ) as f_ps:
                ps_path = f_ps.name
            try:
                self.canvas.postscript(
                    file=ps_path,
                    x=min(x0, x1),
                    y=min(y0, y1),
                    width=w,
                    height=h,
                    colormode="color",
                )
                with tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False
                ) as f_out:
                    png_path = f_out.name
                gs_cmd = self._find_ghostscript_binary()
                if not gs_cmd:
                    return None
                try:
                    result = subprocess.run(
                        [
                            gs_cmd,
                            "-sDEVICE=png16m",
                            "-r144",
                            "-dNOPAUSE",
                            "-dBATCH",
                            "-dSAFER",
                            "-q",
                            "-sOutputFile=" + png_path,
                            ps_path,
                        ],
                        capture_output=True,
                        timeout=30,
                        creationflags=getattr(
                            subprocess, "CREATE_NO_WINDOW", 0
                        ) if sys.platform == "win32" else 0,
                    )
                    if result.returncode == 0 and os.path.exists(png_path):
                        img = Image.open(png_path).convert("RGB")
                        return img
                    return None
                finally:
                    try:
                        os.unlink(png_path)
                    except Exception:
                        pass
            finally:
                try:
                    os.unlink(ps_path)
                except Exception:
                    pass
        except Exception:
            return None

    def _grab_canvas_screenshot(
        self, x0: int, y0: int, x1: int, y1: int
    ) -> "Image.Image | None":
        """
        Capture canvas region via ImageGrab (real screenshot).
        Returns None on failure (Mac without Screen Recording, etc.).
        Cross-platform: Windows, Mac (with permission), Linux X11.
        """
        try:
            self.canvas.update_idletasks()
            root_x = self.canvas.winfo_rootx()
            root_y = self.canvas.winfo_rooty()
            left = root_x + min(x0, x1)
            top = root_y + min(y0, y1)
            right = root_x + max(x0, x1)
            bottom = root_y + max(y0, y1)
            if right - left < 1 or bottom - top < 1:
                return None
            img = ImageGrab.grab(bbox=(int(left), int(top), int(right), int(bottom)))
            return img
        except Exception:
            return None

    def _get_pil_from_canvas_image(self, item_id: int) -> "Image.Image | None":
        """Get PIL Image for a canvas image item (flooring, furniture, etc.)."""
        # 1. room_flooring_images stores image_path - most reliable
        for _owner_id, fd in getattr(self, "room_flooring_images", {}).items():
            if fd.get("image_id") == item_id:
                path = fd.get("image_path")
                if path and os.path.exists(path):
                    try:
                        return Image.open(path).convert("RGBA")
                    except Exception:
                        pass
                break
        # 2. canvas._flooring_image_refs has PhotoImage refs
        refs = getattr(self.canvas, "_flooring_image_refs", {})
        ph = refs.get(item_id)
        if ph is not None:
            pil_img = self._photoimage_from_obj(ph)
            if pil_img is not None:
                return pil_img
        # 3. Try itemcget + getvar (PhotoImage by name)
        ph_name = self.canvas.itemcget(item_id, "image")
        return self._photoimage_to_pil(ph_name)

    def _photoimage_from_obj(self, ph) -> "Image.Image | None":
        """Try to get PIL Image from a PhotoImage object."""
        if ph is None:
            return None
        try:
            if hasattr(ph, "_PhotoImage__photo") and ph._PhotoImage__photo:
                inner = ph._PhotoImage__photo
                if hasattr(inner, "getimage"):
                    return inner.getimage()
        except Exception:
            pass
        return None

    def _photoimage_to_pil(self, ph_name: str) -> "Image.Image | None":
        """Try to get PIL Image from PhotoImage by Tk variable name."""
        if not ph_name:
            return None
        try:
            ph = self.root.getvar(ph_name)
        except Exception:
            ph = None
        return self._photoimage_from_obj(ph)


    def handle_measure_click(self, event):
        x, y = event.x, event.y
        self.clear_temp_measurements()
        

    # Mark the dot (permanent)
        dot = self.view.canvas.create_oval(
            x - 3, y - 3, x + 3, y + 3,
            fill="red", outline="black", tags=("measure_dot",)
        )
        self.measure_points.append((x, y))

        if len(self.measure_points) == 2:
            x0, y0 = self.measure_points[0]
            x1, y1 = self.measure_points[1]

        # Draw temp line
            line = self.view.canvas.create_line(
                x0, y0, x1, y1, fill="blue", dash=(4, 2), tags=("measure_temp",)
            )

        # Get real-world label
            from drawing_helpers import get_distance_label
            label, mx, my = get_distance_label(x0, y0, x1, y1, self.model.unit, self.model.zoom_level)

            text = self.view.canvas.create_text(mx, my - 10, text=label, fill="blue", font=("Arial", 10), tags=("measure_temp",))

        # Store for deletion
            self.temp_measure_items = [line, text]

        # Schedule cleanup after 2 seconds
            try:
                # Check if canvas still exists before scheduling
                if hasattr(self.view.canvas, 'winfo_exists') and self.view.canvas.winfo_exists():
                    self.view.canvas.after(2000, self.clear_temp_measurements)
            except Exception:
                pass

        # Reset for next pair
            self.measure_points = []   

    def clear_temp_measurements(self):
        # Check if canvas still exists before trying to delete items
        try:
            if not hasattr(self.view.canvas, 'winfo_exists') or not self.view.canvas.winfo_exists():
                self.temp_measure_items.clear()
                return
            for item in self.temp_measure_items:
                try:
                    self.view.canvas.delete(item)
                except Exception:
                    pass
            self.temp_measure_items.clear()
        except Exception:
            self.temp_measure_items.clear()         

    def _prompt_create_project_from_image(self, image_path: str) -> None:
        if not image_path:
            return
        try:
            should_create = messagebox.askyesno(
                "Create Project",
                "Do you want to create a project using this layout image?",
                parent=self.root,
            )
        except Exception:
            return

        if not should_create:
            return

        try:
            # Prefer opening Project Management directly to avoid PID lock issues
            self._open_project_management_fallback(image_path)
        except Exception as e:
            try:
                print(f"[MiniAutoCAD] Failed to launch project flow: {e}")
            except Exception:
                pass

    def _launch_vastu_project_with_image(self, image_path: str) -> None:
        if not image_path or not os.path.exists(image_path):
            return

        try:
            from pathlib import Path
            project_root = Path(__file__).resolve().parents[2]
            app_entry = project_root / "VastuApp.py"
        except Exception:
            return

        try:
            is_frozen = bool(getattr(sys, "frozen", False))
        except Exception:
            is_frozen = False

        try:
            if is_frozen:
                cmd = [
                    sys.executable,
                    "--open-project-from-image",
                    image_path,
                ]
                subprocess.Popen(cmd)
                return

            if app_entry.is_file():
                cmd = [
                    sys.executable,
                    str(app_entry),
                    "--open-project-from-image",
                    image_path,
                ]
                subprocess.Popen(cmd, cwd=str(project_root))
                return
        except Exception as e:
            try:
                print(f"[MiniAutoCAD] VastuApp launch failed: {e}")
            except Exception:
                pass

        self._open_project_management_fallback(image_path)

    def _open_project_management_fallback(self, image_path: str) -> None:
        try:
            from types import SimpleNamespace
            from MapAnalysisWindow.project_management import project_management
        except Exception:
            return

        try:
            app_stub = SimpleNamespace()
            app_stub.root = self.root
            app_stub.project_management_window = None
            app_stub.connectivity_manager = None
            try:
                self.root.withdraw()
            except Exception:
                pass

            project_management(self.root, app_stub, prefill_image_path=image_path)

            # If project window is closed without starting a project, restore MiniAutoCAD
            try:
                if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
                    self.root.deiconify()
            except Exception:
                pass
        except Exception as e:
            try:
                print(f"[MiniAutoCAD] Project management fallback failed: {e}")
            except Exception:
                pass

#===lets add vaastu functionalities===#
    def start_vastu_polygon(self):
        from Helper.showMessage import show_message

        # If a Vastu polygon already exists, confirm with the user before
        # erasing it. This action is intentionally not undoable.
        existing_vastu_items = ()
        try:
            existing_vastu_items = self.canvas.find_withtag("vastu_group")
        except Exception:
            existing_vastu_items = ()

        if existing_vastu_items:
            message = (
                "A Vastu polygon already exists in this layout.\n\n"
                "If you create a new Vastu polygon, the previous polygon and all "
                "its Vastu partitions (zones, centroid, markers) will be erased.\n\n"
                "This operation cannot be undone. Do you want to continue?"
            )
            try:
                proceed = show_message(
                    "yesno",
                    "Vastu Polygon",
                    message,
                    auto_close=False,
                )
            except Exception:
                proceed = False

            if not proceed:
                return

            # Erase all existing Vastu visuals without logging an undoable action.
            for tag in (
                "vastu_polygon",
                "vastu_polygon_temp",
                "vastu_centroid",
                "vastu_dimensions",
                "vastu_zone_fill",
                "vastu_zone_label",
                "vastu_north_marker",
                "vastu_division_line",
                "vastu_group",
            ):
                try:
                    self.canvas.delete(tag)
                except Exception:
                    pass

            # Reset Vastu runtime state
            try:
                self.vastu_polygon_points = []
            except Exception:
                pass
            try:
                self.vastu_zones = []
            except Exception:
                pass
            try:
                self._vastu_zone_baseline_by_item = {}
            except Exception:
                pass

            # Drop Vastu-related actions from undo/redo so old polygons
            # cannot reappear via redo.
            try:
                if hasattr(self, "actions") and hasattr(self.actions, "drop_vastu_actions"):
                    self.actions.drop_vastu_actions()
            except Exception:
                pass

        self.reset_modes()
        # Clear any previous temp strokes for a clean start
        try:
            self.canvas.delete("vastu_polygon_temp")
            self.canvas.delete("vastu_north_marker")
        except Exception:
            pass
        self.guideline_helper.clear_guides()
        if self.vastu_preview_polygon:
            try:
                self.canvas.delete(self.vastu_preview_polygon)
            except Exception:
                pass
            self.vastu_preview_polygon = None
        if self.vastu_preview_line:
            try:
                self.canvas.delete(self.vastu_preview_line)
            except Exception:
                pass
            self.vastu_preview_line = None
        self.vastu_polygon_points = []
        self.model.set("vastu_polygon_mode", True)
        self.canvas.config(cursor="tcross")
        print("🟢 Vastu polygon mode started. Click to add points.")
        
    def add_vastu_polygon_point(self, event):
        # Use canvas coordinates so Vastu polygon drawing stays stable while panning.
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        snapped_x, snapped_y, snap_info = self.guideline_helper.get_snap_point(
            cx, cy, self.vastu_polygon_points
        )
        # Optional ortho locking: Shift constrains the next edge relative to last vertex.
        if self.vastu_polygon_points:
            last_x, last_y = self.vastu_polygon_points[-1]
            snapped_x, snapped_y, snap_info = self._apply_shift_ortho_lock(
                event,
                mouse_cx=cx,
                mouse_cy=cy,
                snapped_x=snapped_x,
                snapped_y=snapped_y,
                snap_info=snap_info,
                last_x=last_x,
                last_y=last_y,
            )
        x, y = snapped_x, snapped_y
        self.guideline_helper.clear_guides()

        if self.vastu_polygon_points:
            if math.dist((x, y), self.vastu_polygon_points[0]) < 10:
                self.finish_vastu_polygon()
                return
            x0, y0 = self.vastu_polygon_points[-1]
            line = self.canvas.create_line(
                x0, y0, x, y, fill="purple", width=2, tags=("vastu_polygon_temp",)
            )
            self.actions.log({"type": "create", "items": [line]})
        else:
            self.vastu_preview_polygon = self.canvas.create_polygon(
                x, y,
                outline="purple",
                fill="",
                width=2,
                tags=("vastu_polygon_temp", "vastu_polygon_preview"),
            )

        self.vastu_polygon_points.append((x, y))
        flat = [coord for pt in self.vastu_polygon_points for coord in pt]
        if self.vastu_preview_polygon:
            try:
                self.canvas.coords(self.vastu_preview_polygon, *flat)
            except Exception:
                pass
        dot = self.canvas.create_oval(
            x - 1, y - 1, x + 1, y + 1, fill="purple", tags=("vastu_polygon_temp",)
        )
        self.actions.log({"type": "create", "items": [dot]})

    def update_vastu_polygon_preview(self, event):
        if not self.model.get("vastu_polygon_mode"):
            self.guideline_helper.clear_guides()
            return
        if not self.vastu_polygon_points:
            self.guideline_helper.clear_guides()
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        snapped_x, snapped_y, snap_info = self.guideline_helper.get_snap_point(
            cx, cy, self.vastu_polygon_points
        )
        # Optional ortho locking: Shift constrains preview edge relative to last vertex.
        if self.vastu_polygon_points:
            last_x, last_y = self.vastu_polygon_points[-1]
            snapped_x, snapped_y, snap_info = self._apply_shift_ortho_lock(
                event,
                mouse_cx=cx,
                mouse_cy=cy,
                snapped_x=snapped_x,
                snapped_y=snapped_y,
                snap_info=snap_info,
                last_x=last_x,
                last_y=last_y,
            )
        x, y = snapped_x, snapped_y

        self.guideline_helper.draw_guides(
            cx, cy, self.vastu_polygon_points, x, y, snap_info
        )

        if self.vastu_preview_polygon:
            preview_coords = []
            for pt in self.vastu_polygon_points:
                preview_coords.extend(pt)
            preview_coords.extend([x, y])
            try:
                self.canvas.coords(self.vastu_preview_polygon, *preview_coords)
            except Exception:
                pass

        last_x, last_y = self.vastu_polygon_points[-1]
        if len(self.vastu_polygon_points) >= 3:
            first_x, first_y = self.vastu_polygon_points[0]
            dist_to_first = math.dist((x, y), (first_x, first_y))
            if dist_to_first < 10:
                if self.vastu_preview_line:
                    try:
                        self.canvas.delete(self.vastu_preview_line)
                    except Exception:
                        pass
                self.vastu_preview_line = self.canvas.create_line(
                    last_x, last_y, first_x, first_y,
                    fill="purple",
                    width=2,
                    dash=(4, 2),
                    tags=("vastu_polygon_temp", "vastu_preview_line"),
                )
                return

        if self.vastu_preview_line:
            try:
                self.canvas.coords(self.vastu_preview_line, last_x, last_y, x, y)
            except Exception:
                try:
                    self.canvas.delete(self.vastu_preview_line)
                except Exception:
                    pass
                self.vastu_preview_line = self.canvas.create_line(
                    last_x, last_y, x, y,
                    fill="purple",
                    width=2,
                    dash=(4, 2),
                    tags=("vastu_polygon_temp", "vastu_preview_line"),
                )
        else:
            self.vastu_preview_line = self.canvas.create_line(
                last_x, last_y, x, y,
                fill="purple",
                width=2,
                dash=(4, 2),
                tags=("vastu_polygon_temp", "vastu_preview_line"),
            )

        # Segment distance label in red color
        try:
            pixel_dist = math.dist((last_x, last_y), (x, y))
            zoom = float(getattr(self.model, "zoom_level", 1.0) or 1.0)
            grid_spacing = float(getattr(self.model, "grid_spacing", 20.0) or 20.0)
            unit = getattr(self.model, "unit", "ft")
            unit_scale_map = getattr(self.model, "unit_scale", {}) or {}
            unit_factor = float(unit_scale_map.get(unit, 1.0) or 1.0)

            denom = max(1e-6, grid_spacing * zoom)
            real_dist = (pixel_dist / denom) * unit_factor
            label_text = f"{real_dist:.2f} {unit}"

            mx = (last_x + x) / 2.0
            my = (last_y + y) / 2.0

            if self.current_line_label:
                self.canvas.coords(self.current_line_label, mx, my - 10)
                self.canvas.itemconfig(self.current_line_label, text=label_text, fill="red", font=("Arial", 9, "bold"))
            else:
                self.current_line_label = self.canvas.create_text(
                    mx, my - 10,
                    text=label_text,
                    font=("Arial", 9, "bold"),
                    fill="red",
                    tags=("vastu_polygon_temp", "vastu_polygon_preview_label")
                )
        except Exception:
            pass

    def finish_vastu_polygon(self):
        if len(self.vastu_polygon_points) < 3:
            return

        # Remove only temporary strokes from the current drawing session.
        # Existing Vastu polygons, zones, and markers from earlier sessions remain.
        for tag in (
            "vastu_polygon_temp",
        ):
            try:
                self.canvas.delete(tag)
            except Exception:
                pass

        if self.current_line_label:
            try:
                self.canvas.delete(self.current_line_label)
            except Exception:
                pass
            self.current_line_label = None

        flat = [coord for pt in self.vastu_polygon_points for coord in pt]

        polygon_id = self.canvas.create_polygon(
            flat,
            outline="purple",
            fill="",
            width=2,
            tags=("vastu_polygon", "vastu_group"),
        )

        # Robust: pick a center point inside polygon (prevents missing/partial zones)
        gen = VastuPolygonGenerator(self.vastu_polygon_points)
        center = gen.get_center_inside()
        if center is None:
            cx, cy = self.calculate_polygon_centroid(self.vastu_polygon_points)
        else:
            cx, cy = center

        self.vastu_north_deg = self._ask_vastu_north_deg(default_deg=self.vastu_north_deg)
        self._draw_vastu_north_marker(cx, cy, self.vastu_north_deg)

        radius = 4
        circle_id = self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                            fill="red", outline="black", tags=("vastu_centroid", "vastu_group"))

        draw_type = str(self.model.get("vastu_polygon_draw_type"))
        is_normal = draw_type == "normal"
        if not is_normal:
            zone_count = int(self.model.get("vastu_zone_count") or 8)
            self.draw_vastu_compass_inside_polygon(
                cx,
                cy,
                polygon_points=self.vastu_polygon_points,
                north_deg_offset=(-float(self.vastu_north_deg)) % 360.0,
                zone_count=zone_count,
            )

            if draw_type != "slices_clean":
                self.draw_vastu_division_lines(
                    cx,
                    cy,
                    polygon_points=self.vastu_polygon_points,
                    north_deg_offset=(-float(self.vastu_north_deg)) % 360.0,
                    zone_count=zone_count,
                )
                try:
                    self.canvas.tag_raise("vastu_zone_label")
                except Exception:
                    pass
            else:
                try:
                    self.canvas.delete("vastu_division_line")
                except Exception:
                    pass

            try:
                self._capture_vastu_zone_baseline()
            except Exception:
                pass
        else:
            try:
                self.vastu_zones = []
            except Exception:
                pass
            try:
                self._vastu_zone_baseline_by_item = {}
            except Exception:
                pass

        # Engineering-style dimensions for each Vastu polygon edge (same as normal polygon)
        dim_items = []
        try:
            if getattr(self.model, "auto_vastu_polygon_dimensions", True) and hasattr(self, "dimension_drawer"):
                dim_items = self.dimension_drawer.draw_polygon_edge_dimensions(
                    self.vastu_polygon_points,
                    group_tag="vastu_group",
                    dim_tag="vastu_dimensions",
                )
        except Exception:
            dim_items = []

        # Log as one grouped create so undo removes the full Vastu visual set
        # (zones, labels, division lines, markers, and dimensions).
        try:
            vastu_ids = list(self.canvas.find_withtag("vastu_group"))
        except Exception:
            vastu_ids = [polygon_id, circle_id, *dim_items]
        self.actions.log(
            {
                "type": "create",
                "items": vastu_ids,
                "dimension_recompute": {
                    "group_tag": "vastu_group",
                    "dim_tag": "vastu_dimensions",
                },
            }
        )
        if not is_normal:
            self.score_furniture_in_vastu_zones()
        self.guideline_helper.clear_guides()
        if self.vastu_preview_polygon:
            try:
                self.canvas.delete(self.vastu_preview_polygon)
            except Exception:
                pass
            self.vastu_preview_polygon = None
        if self.vastu_preview_line:
            try:
                self.canvas.delete(self.vastu_preview_line)
            except Exception:
                pass
            self.vastu_preview_line = None
        self.vastu_polygon_points = []
        self.model.set("vastu_polygon_mode", False)
        self.canvas.config(cursor="arrow")

    def calculate_polygon_centroid(self, points):
        x_list = [p[0] for p in points]
        y_list = [p[1] for p in points]
        n = len(points)
        x = sum(x_list) / n
        y = sum(y_list) / n
        return x, y

    def draw_vastu_grid(self, polygon_points):
        # Calculate bounding box of polygon
        xs = [x for x, _ in polygon_points]
        ys = [y for _, y in polygon_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max_x - min_x
        height = max_y - min_y

        third_w = width / 3
        third_h = height / 3

        directions = [
            ("NW", min_x,          min_y),
            ("N",  min_x+third_w,  min_y),
            ("NE", min_x+2*third_w,min_y),
            ("W",  min_x,          min_y+third_h),
            ("C",  min_x+third_w,  min_y+third_h),
            ("E",  min_x+2*third_w,min_y+third_h),
            ("SW", min_x,          min_y+2*third_h),
            ("S",  min_x+third_w,  min_y+2*third_h),
            ("SE", min_x+2*third_w,min_y+2*third_h),
        ]

        labels = []
        for label, x, y in directions:
            txt = self.canvas.create_text(x + third_w/2, y + third_h/2,
                                        text=label,
                                        font=("Arial", 9, "bold"),
                                        fill="blue",
                                        tags=("vastu_direction",))
            labels.append(txt)

        # Optional: draw grid lines
        for i in range(1, 3):
            self.canvas.create_line(min_x + i*third_w, min_y, min_x + i*third_w, max_y, dash=(2, 2), fill="gray", tags=("vastu_grid",))
            self.canvas.create_line(min_x, min_y + i*third_h, max_x, min_y + i*third_h, dash=(2, 2), fill="gray", tags=("vastu_grid",))

        return labels   

    def draw_vastu_compass_inside_polygon(
        self,
        center_x,
        center_y,
        polygon_points=None,
        north_deg_offset: float = 0.0,
        zone_count: int = 8,
    ):
        """
        Draw 8, 16, or 32 Vastu zone labels and keep zone data for scoring. No fill colors; divisions from draw_vastu_division_lines.
        """
        poly = polygon_points if polygon_points is not None else getattr(self, "vastu_polygon_points", [])
        if not poly or len(poly) < 3:
            return

        try:
            self.canvas.delete("vastu_zone_fill")
            self.canvas.delete("vastu_zone_label")
        except Exception:
            pass

        self.vastu_zones = []

        from vastu_polygon.geometry import VastuPolygonGenerator

        gen = VastuPolygonGenerator(poly)
        chakra_mode = str(self.model.get("vastu_32_chakra_mode"))
        zones = gen.generate_zones(
            center=(float(center_x), float(center_y)),
            north_deg_offset=float(north_deg_offset),
            zone_count=int(zone_count),
            chakra_32_mode=chakra_mode,
        )

        draw_type = str(self.model.get("vastu_polygon_draw_type"))

        # Light palette for zone slices (cycled). Tk canvas has no alpha, so keep it subtle.
        slice_colors = (
            "#E0F2FE",  # sky-100
            "#E0E7FF",  # indigo-100
            "#FCE7F3",  # pink-100
            "#DCFCE7",  # green-100
            "#FEF9C3",  # yellow-100
            "#FFEDD5",  # orange-100
            "#F3E8FF",  # purple-100
            "#FFE4E6",  # rose-100
        )

        for z in zones:
            if not z.polygon or len(z.polygon) < 3:
                continue
            # Create an actual slice polygon per zone so "Move Slices Only" can drag it.
            try:
                flat = []
                for px, py in z.polygon:
                    flat.extend((float(px), float(py)))
                fill_color = slice_colors[len(self.vastu_zones) % len(slice_colors)] if draw_type == "slices_clean" else ""
                self.canvas.create_polygon(
                    flat,
                    fill=fill_color,
                    outline="#9CA3AF",
                    width=1,
                    tags=("vastu_zone_fill", "vastu_group", f"vastu_zone_{z.name}"),
                )
            except Exception:
                pass
            lx, ly = z.label_point
            font_size = 7 if zone_count == 32 else 8
            self.canvas.create_text(
                lx,
                ly,
                text=z.name,
                font=("Arial", font_size, "bold"),
                fill="black",
                tags=("vastu_zone_label", "vastu_group", f"vastu_zone_{z.name}"),
            )
            self.vastu_zones.append({"name": z.name, "polygon": z.polygon, "score": 0})

    def draw_vastu_division_lines(
        self,
        center_x,
        center_y,
        polygon_points=None,
        north_deg_offset: float = 0.0,
        zone_count: int = 8,
    ):
        poly = polygon_points if polygon_points is not None else getattr(self, "vastu_polygon_points", [])
        if not poly or len(poly) < 3:
            return

        try:
            self.canvas.delete("vastu_division_line")
        except Exception:
            pass

        from vastu_polygon.geometry import VastuPolygonGenerator

        chakra_mode = str(self.model.get("vastu_32_chakra_mode"))
        boundary_angles = VastuPolygonGenerator.get_boundary_angles(
            int(zone_count),
            chakra_32_mode=chakra_mode,
        )
        for ang in boundary_angles:
            compass = (float(ang) + float(north_deg_offset)) % 360.0
            vx, vy = VastuPolygonGenerator.angle_to_unit_vector(compass)
            seg = VastuPolygonGenerator.clip_infinite_line_to_polygon(
                poly,
                center=(float(center_x), float(center_y)),
                line_dir=(float(vx), float(vy)),
            )
            if not seg:
                continue
            (x1, y1), (x2, y2) = seg

            # Choose the boundary point that lies in the forward direction of (vx, vy)
            dx1 = (float(x1) - float(center_x)) * float(vx) + (float(y1) - float(center_y)) * float(vy)
            dx2 = (float(x2) - float(center_x)) * float(vx) + (float(y2) - float(center_y)) * float(vy)
            if dx2 >= dx1:
                bx, by = float(x2), float(y2)
            else:
                bx, by = float(x1), float(y1)
            try:
                self.canvas.create_line(
                    float(center_x),
                    float(center_y),
                    bx,
                    by,
                    fill="gray",
                    width=1,
                    tags=("vastu_division_line", "vastu_group"),
                )
            except Exception:
                continue

    def refresh_vastu_zones_to_current_count(
        self,
        vastu_model_before: dict | None = None,
    ) -> None:
        """Redraw zone fills and division lines for existing vastu polygon using current zone count."""
        draw_type = str(self.model.get("vastu_polygon_draw_type"))

        # Snapshot current zone visuals so zone-count/type changes are undoable step-wise.
        def _collect_zone_visual_ids() -> list[int]:
            """
            Collect ids for Vastu zone visuals (fills, labels, division lines).
            We scan items under 'vastu_group' and filter by tags so this stays robust
            even if some items don't carry the expected direct tag.
            """
            try:
                candidates = self.canvas.find_withtag("vastu_group")
            except Exception:
                candidates = ()
            out: set[int] = set()
            for item_id in candidates or ():
                try:
                    tags = self.canvas.gettags(item_id)
                except Exception:
                    continue
                if (
                    ("vastu_zone_fill" in tags)
                    or ("vastu_zone_label" in tags)
                    or ("vastu_division_line" in tags)
                ):
                    try:
                        out.add(int(item_id))
                    except Exception:
                        continue
            return list(out)

        old_ids: list[int] = _collect_zone_visual_ids()

        try:
            old_items = self.actions._snapshot_canvas_items(self.canvas, old_ids) if old_ids else []
        except Exception:
            old_items = []

        try:
            items = self.canvas.find_withtag("vastu_polygon")
        except Exception:
            items = ()
        if not items:
            return
        item_id = items[0]
        try:
            flat = list(self.canvas.coords(item_id))
        except Exception:
            return
        if len(flat) < 6:
            return
        poly_points = [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]
        if len(poly_points) < 3:
            return

        # If switching to normal (outline only), remove zone visuals and log the change.
        if draw_type == "normal":
            try:
                self.canvas.delete("vastu_zone_fill")
                self.canvas.delete("vastu_zone_label")
                self.canvas.delete("vastu_division_line")
            except Exception:
                pass
            try:
                self.vastu_zones = []
            except Exception:
                pass
            try:
                self._vastu_zone_baseline_by_item = {}
            except Exception:
                pass

            vastu_model_after = {"vastu_zone_count": int(self.model.get("vastu_zone_count") or 8), "vastu_polygon_draw_type": draw_type}
            log_payload = {
                "type": "replace_group",
                "old_ids": old_ids,
                "new_ids": [],
                "old_items": old_items,
                "new_items": [],
                "vastu_model_before": vastu_model_before or vastu_model_after,
                "vastu_model_after": vastu_model_after,
            }
            if vastu_model_before:
                log_payload["subtype"] = "vastu_zone_change"
            try:
                self.actions.log(log_payload)
            except Exception:
                pass

            # Keep the most recent Vastu create action's `items` aligned with the current
            # zone visual ids, so a subsequent Undo of the Vastu creation deletes the
            # current zone visuals too (prevents orphan labels when zone count changed).
            try:
                for a in reversed(getattr(self.actions, "undo_stack", []) or []):
                    if a.get("type") != "create":
                        continue
                    dim_rec = a.get("dimension_recompute") or {}
                    if isinstance(dim_rec, dict) and dim_rec.get("group_tag") == "vastu_group":
                        items = set(a.get("items") or [])
                        items.difference_update(set(old_ids))
                        a["items"] = list(items)
                        break
            except Exception:
                pass
            return

        from vastu_polygon.geometry import VastuPolygonGenerator
        gen = VastuPolygonGenerator(poly_points)
        center = gen.get_center_inside()
        if center is None:
            center = self.calculate_polygon_centroid(poly_points)
        cx, cy = center
        north_offset = (-float(getattr(self, "vastu_north_deg", 270.0))) % 360.0
        zone_count = int(self.model.get("vastu_zone_count") or 8)
        self.draw_vastu_compass_inside_polygon(
            cx, cy,
            polygon_points=poly_points,
            north_deg_offset=north_offset,
            zone_count=zone_count,
        )
        if draw_type != "slices_clean":
            self.draw_vastu_division_lines(
                cx, cy,
                polygon_points=poly_points,
                north_deg_offset=north_offset,
                zone_count=zone_count,
            )
            try:
                self.canvas.tag_raise("vastu_zone_label")
            except Exception:
                pass
        else:
            try:
                self.canvas.delete("vastu_division_line")
            except Exception:
                pass
        try:
            self._capture_vastu_zone_baseline()
        except Exception:
            pass

        # Snapshot new zone visuals and log replace_group for undo/redo.
        new_ids: list[int] = _collect_zone_visual_ids()

        try:
            new_items = self.actions._snapshot_canvas_items(self.canvas, new_ids) if new_ids else []
        except Exception:
            new_items = []

        vastu_model_after = {"vastu_zone_count": zone_count, "vastu_polygon_draw_type": draw_type}
        log_payload = {
            "type": "replace_group",
            "old_ids": old_ids,
            "new_ids": new_ids,
            "old_items": old_items,
            "new_items": new_items,
            "vastu_model_before": vastu_model_before or vastu_model_after,
            "vastu_model_after": vastu_model_after,
        }
        if vastu_model_before:
            log_payload["subtype"] = "vastu_zone_change"
        try:
            self.actions.log(log_payload)
        except Exception:
            pass

        # Update the most recent Vastu create action's `items` to point at the CURRENT
        # zone visuals so that undoing the Vastu creation cleans up everything.
        try:
            for a in reversed(getattr(self.actions, "undo_stack", []) or []):
                if a.get("type") != "create":
                    continue
                dim_rec = a.get("dimension_recompute") or {}
                if isinstance(dim_rec, dict) and dim_rec.get("group_tag") == "vastu_group":
                    items = set(a.get("items") or [])
                    items.difference_update(set(old_ids))
                    items.update(set(new_ids))
                    a["items"] = list(items)
                    break
        except Exception:
            pass

    def _capture_vastu_zone_baseline(self) -> None:
        baseline = {}
        for zone in getattr(self, "vastu_zones", []) or []:
            name = None
            try:
                name = zone.get("name")
            except Exception:
                name = None
            if not name:
                continue
            zone_tag = f"vastu_zone_{name}"
            try:
                items = self.canvas.find_withtag(zone_tag)
            except Exception:
                items = ()
            for item_id in items:
                try:
                    coords = self.canvas.coords(item_id)
                except Exception:
                    coords = None
                if coords is None:
                    continue
                baseline[int(item_id)] = list(coords)
        self._vastu_zone_baseline_by_item = baseline

    def reset_vastu_slices(self) -> None:
        baseline = getattr(self, "_vastu_zone_baseline_by_item", None) or {}
        if not baseline:
            return
        for item_id, coords in baseline.items():
            try:
                self.canvas.coords(int(item_id), *coords)
            except Exception:
                continue

    def shift_vastu_slice_baseline(self, dx: float, dy: float, item_ids=None) -> None:
        baseline = getattr(self, "_vastu_zone_baseline_by_item", None)
        if not baseline:
            return
        selected_ids = set(item_ids) if item_ids is not None else None
        ndx = float(dx)
        ndy = float(dy)
        for item_id, coords in list(baseline.items()):
            if selected_ids is not None and item_id not in selected_ids:
                continue
            if not coords:
                continue
            new_coords = list(coords)
            for i in range(0, len(new_coords) - 1, 2):
                try:
                    new_coords[i] = float(new_coords[i]) + ndx
                    new_coords[i + 1] = float(new_coords[i + 1]) + ndy
                except Exception:
                    pass
            baseline[item_id] = new_coords
        
    def is_point_inside_triangle(self, p, a, b, c):
        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - \
                   (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1 = sign(p, a, b)
        d2 = sign(p, b, c)
        d3 = sign(p, c, a)
        return not ((d1 < 0) or (d2 < 0) or (d3 < 0)) or ((d1 > 0) or (d2 > 0) or (d3 > 0))

    def score_item_at_position(self, x, y):
        point = (x, y)
        for zone in getattr(self, "vastu_zones", []):
            poly = zone.get("polygon") or []
            if poly and VastuPolygonGenerator.point_in_polygon(point, poly):
                zone["score"] += 1
                print(f"✅ Item at {point} falls in {zone['name']} zone. Score updated to {zone['score']}")
                return zone["name"]
        print(f"⚠️ Item at {point} is outside all zones.")
        return None
    
    def print_vastu_scores(self):
        print("\n📋 Vastu Zone Scores:")
        for zone in self.vastu_zones:
            print(f"{zone['name']}: {zone['score']}")

    def score_furniture_in_vastu_zones(self):
        # Loop through all furniture items and score them
        if not hasattr(self, "vastu_zones"):
            print("No vastu zones defined.")
            return

        for furniture in self.image_furniture_items:
            # Get center of furniture image
            x, y = furniture.get_position()
            found_zone = None
            for zone in self.vastu_zones:
                poly = zone.get("polygon") or []
                if poly and VastuPolygonGenerator.point_in_polygon((x, y), poly):
                    zone["score"] += 1
                    found_zone = zone["name"]
                    print(f"Furniture '{os.path.basename(furniture.image_path)}' at ({x:.1f},{y:.1f}) is in {found_zone} zone.")
                    break
            if not found_zone:
                print(f"Furniture '{os.path.basename(furniture.image_path)}' at ({x:.1f},{y:.1f}) is outside all zones.")

        self.print_vastu_scores()
        
    def start_room_edit(self, group_tag):
        """Populate sidebar widgets with room data for editing."""
        room = self.room_entities_by_group_tag.get(group_tag)
        if not room:
            return
            
        self.currently_editing_room_tag = group_tag
        
        # Ensure we are in the Room tab (optional, but good for UI consistency)
        # Populate widgets
        widgets = getattr(self, "room_widgets", {})
        if not widgets:
            return
            
        # Fill name
        widgets["name"].delete(0, tk.END)
        widgets["name"].insert(0, room.name)
        
        # Fill dimensions
        widgets["length"].delete(0, tk.END)
        widgets["length"].insert(0, str(round(room.wlabel, 2)))
        
        widgets["breadth"].delete(0, tk.END)
        widgets["breadth"].insert(0, str(round(room.hlabel, 2)))
        
        # Find balcony for this room
        balcony_side = "None"
        balcony_depth = ""
        
        items = self.canvas.find_withtag(group_tag)
        balconies = []
        for item in items:
            tags = self.canvas.gettags(item)
            if "balcony" in tags:
                balconies.append(item)
        
        if balconies:
            room_coords = self.canvas.coords(room.rect_id)
            if len(room_coords) >= 4:
                rx1, ry1, rx2, ry2 = room_coords
                has_left = False
                has_right = False
                unit_factor = self.model.unit_scale[self.model.unit]
                px_per_unit = self.model.grid_spacing * self.model.zoom_level / unit_factor
                
                for b in balconies:
                    b_coords = self.canvas.coords(b)
                    if len(b_coords) >= 4:
                        bx_mid = (b_coords[0] + b_coords[2]) / 2
                        # Check proximity to left or right wall
                        if abs(bx_mid - rx1) < 20:
                            has_left = True
                            balcony_depth = (b_coords[2] - b_coords[0]) / 2 / px_per_unit
                        elif abs(bx_mid - rx2) < 20:
                            has_right = True
                            balcony_depth = (b_coords[2] - b_coords[0]) / 2 / px_per_unit
                
                if has_left and has_right: balcony_side = "Both"
                elif has_left: balcony_side = "Left"
                elif has_right: balcony_side = "Right"
        
        widgets["balcony_side"].set(balcony_side)
        widgets["balcony_depth"].delete(0, tk.END)
        if balcony_depth:
            widgets["balcony_depth"].insert(0, str(round(abs(balcony_depth), 1)))
            
        # Switch buttons: hide Create, show Update/Cancel
        if "create_btn" in widgets: widgets["create_btn"].pack_forget()
        if "update_btn" in widgets: widgets["update_btn"].pack(fill="x", padx=8, pady=(6, 2))
        if "cancel_btn" in widgets: widgets["cancel_btn"].pack(fill="x", padx=8, pady=(2, 4))

    def cancel_room_edit(self):
        """Reset sidebar to creation mode."""
        self.currently_editing_room_tag = None
        widgets = getattr(self, "room_widgets", {})
        if not widgets:
            return
            
        widgets["name"].delete(0, tk.END)
        widgets["length"].delete(0, tk.END)
        widgets["breadth"].delete(0, tk.END)
        widgets["balcony_side"].set("None")
        widgets["balcony_depth"].delete(0, tk.END)
        
        if "update_btn" in widgets: widgets["update_btn"].pack_forget()
        if "cancel_btn" in widgets: widgets["cancel_btn"].pack_forget()
        if "create_btn" in widgets: widgets["create_btn"].pack(fill="x", padx=8, pady=(6, 4))

    def update_currently_editing_room(self):
        """Apply changes from sidebar to the room being edited."""
        group_tag = getattr(self, "currently_editing_room_tag", None)
        if not group_tag:
            return
            
        room = self.room_entities_by_group_tag.get(group_tag)
        if not room:
            return
            
        widgets = self.room_widgets
        name = widgets["name"].get().strip()
        try:
            length = float(widgets["length"].get())
            breadth = float(widgets["breadth"].get())
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter valid numbers for length and breadth.")
            return
            
        # Update room entity data
        room.name = name
        room.wlabel = length
        room.hlabel = breadth
        
        # Keep track of current position
        room.sync_to_canvas()
        
        # Clean up old geometry
        room.destroy()
        
        # Find and delete old balconies associated with this group
        all_items = self.canvas.find_withtag(group_tag)
        for item in all_items:
            if "balcony" in self.canvas.gettags(item):
                self.canvas.delete(item)
        
        # Re-initialize pixels based on new dimensions
        room.unit_scale = self.model.unit_scale[self.model.unit]
        room.grid_spacing = self.model.grid_spacing
        room.zoom_level = self.model.zoom_level
        room.width_px = length / room.unit_scale * room.grid_spacing * room.zoom_level
        room.height_px = breadth / room.unit_scale * room.grid_spacing * room.zoom_level
        room.x1 = room.x0 + room.width_px
        room.y1 = room.y0 + room.height_px
        
        # Redraw
        room.create()
        
        # Update balcony
        side = widgets["balcony_side"].get()
        depth_str = widgets["balcony_depth"].get().strip()
        if side != "None" and depth_str:
            try:
                depth = float(depth_str)
                if depth > 0:
                    self._draw_balcony_for_room(room, side, depth)
            except ValueError:
                pass
        
        # Log for undo
        self.actions.log({
            "type": "edit_room",
            "group_tag": group_tag,
            "name": name,
            "width": length,
            "height": breadth,
        })
        
        self.cancel_room_edit()
        print(f"✅ Room '{name}' updated successfully.")

    def _draw_balcony_for_room(self, room, side, depth):
        """Helper to draw balcony arc for a room."""
        room_coords = self.canvas.coords(room.rect_id)
        if len(room_coords) < 4:
            return
        rx1, ry1, rx2, ry2 = room_coords
        
        unit_factor = self.model.unit_scale[self.model.unit]
        px_per_unit = self.model.grid_spacing * self.model.zoom_level / unit_factor
        radius = depth * px_per_unit
        group_tag = room.group_tag

        if side in ("Left", "Both"):
            balcony_left = self.canvas.create_arc(
                rx1 - radius, ry1, rx1 + radius, ry2,
                start=90, extent=180, style="arc", width=2, outline="black",
                tags=("balcony", group_tag)
            )
            self.canvas.addtag_withtag(group_tag, balcony_left)
            self.canvas.tag_raise(balcony_left)

        if side in ("Right", "Both"):
            balcony_right = self.canvas.create_arc(
                rx2 - radius, ry1, rx2 + radius, ry2,
                start=270, extent=180, style="arc", width=2, outline="black",
                tags=("balcony", group_tag)
            )
            self.canvas.addtag_withtag(group_tag, balcony_right)
            self.canvas.tag_raise(balcony_right)
    def delete_room_by_group(self, group_tag):
        """Delete a room and all its items from the canvas."""
        room = self.room_entities_by_group_tag.get(group_tag)
        if room:
            room.destroy()
            if group_tag in self.room_entities_by_group_tag:
                del self.room_entities_by_group_tag[group_tag]
        
        # Also clean up any loose items with this tag (like balconies or text)
        try:
            items = self.canvas.find_withtag(group_tag)
            for item in items:
                self.canvas.delete(item)
        except Exception:
            pass
            
        print(f"🗑️ Room {group_tag} deleted.")

    def restore_foreground_z_order(self):
        """Restore proper z-order by raising foreground elements above rooms/flooring."""
        for tag in ["furniture", "door", "balcony", "line", "line_label", "line_point", "dimension_item", "measure", "user_text", "compass", "vastu_zone_label"]:
            try:
                self.canvas.tag_raise(tag)
            except Exception:
                pass
