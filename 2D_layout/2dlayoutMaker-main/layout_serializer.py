import datetime
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List
import copy

import tkinter as tk
import yaml
from tkinter import filedialog, messagebox

from app_paths import AppPathManager
from Helper.showMessage import show_message
from layout_schema import empty_geometry, validate_document
from project_state import ProjectState
import room_detection
import structural_joints


def _point_on_polygon_outline(point: tuple[float, float], polygon: list[tuple[float, float]], tol: float = 6.0) -> bool:
    """Return True if ``point`` lies within ``tol`` of any polygon edge."""
    n = len(polygon)
    if n < 2:
        return False
    px, py = float(point[0]), float(point[1])
    for i in range(n):
        ax, ay = float(polygon[i][0]), float(polygon[i][1])
        bx, by = float(polygon[(i + 1) % n][0]), float(polygon[(i + 1) % n][1])
        dx, dy = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy
        if seg_len2 <= 1e-9:
            dist2 = (px - ax) ** 2 + (py - ay) ** 2
        else:
            t = ((px - ax) * dx + (py - ay) * dy) / seg_len2
            t = max(0.0, min(1.0, t))
            proj_x = ax + t * dx
            proj_y = ay + t * dy
            dist2 = (px - proj_x) ** 2 + (py - proj_y) ** 2
        if dist2 <= tol * tol:
            return True
    return False


def atomic_write_document(document: dict[str, Any], path: str) -> None:
    """Atomically write JSON or YAML using a flushed sibling temporary file."""
    target = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(target) or os.curdir
    os.makedirs(parent, exist_ok=True)
    extension = os.path.splitext(target)[1].lower()
    if extension not in (".json", ".yaml", ".yml"):
        raise ValueError("unsupported layout extension; expected .json, .yaml, or .yml")
    fd, temporary = tempfile.mkstemp(prefix=f".{os.path.basename(target)}.", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            if extension == ".json":
                json.dump(document, stream, ensure_ascii=False, indent=2)
            else:
                yaml.safe_dump(document, stream, allow_unicode=True, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class LayoutSerializer:
    def __init__(self, model, view, tools, actions, project_state=None):
        self.model = model
        self.view = view
        self.canvas = view.canvas
        self.tools = tools
        self.actions = actions
        self.project_state = project_state if project_state is not None else ProjectState()
        if not isinstance(self.project_state, ProjectState):
            raise TypeError("project_state must be a ProjectState")
        existing_serializer = getattr(self.actions, "serializer", None)
        if existing_serializer is not None and existing_serializer is not self:
            raise RuntimeError(
                "Only one LayoutSerializer may own the application ProjectState; reuse actions.serializer"
            )
        self.actions.serializer = self

        # User-assigned name + fill style for detected (line-loop) rooms, keyed by
        # the stable detected-face room id produced in _derive_canvas_geometry. The
        # overlay is recomputed from scratch on every canvas mutation, so without
        # an override store the label/color applied via "Lines → Room" is wiped.
        self._detected_room_overrides: dict[str, dict[str, Any]] = {}

        if not hasattr(self.tools, "image_furniture_items"):
            self.tools.image_furniture_items = []
        if not hasattr(self.tools, "room_flooring_images"):
            self.tools.room_flooring_images = {}

        # ------------------------------------------------------------------
        # Paths: use centralized cross‑platform app data directory
        # e.g. on Windows → %LOCALAPPDATA%\\VastuApp\\saved_layouts
        # ------------------------------------------------------------------
        AppPathManager.ensure_directories()
        self.default_save_dir = AppPathManager.get_saved_layouts_dir()
        self.ensure_save_directory()

        # Auto-save settings
        self.auto_save_enabled = True
        self.current_layout_file = None

        # Use the file’s folder as the anchor for bundled assets (images etc.)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.asset_dirs = [
            os.path.join(self.base_dir, "Images"),
            os.path.join(self.base_dir, "flooring"),
            self.base_dir,  # last resort
        ]
        self._missing_asset_logged = set()

        # (optional) wherever you had a default save dir (kept for backwards
        # compatibility but now redundant because default_save_dir already
        # points to the app-data saved_layouts directory)
        # self.default_save_dir = os.path.join(self.base_dir, "saved_layouts")
            # ---------- Portable path helpers (methods) ----------
    def _to_portable_path(self, p: str | None) -> str | None:
        """Store paths in a machine-independent way (relative to project, or filename only)."""
        if not p:
            return None
        p = os.path.abspath(p)
        try:
            rel = os.path.relpath(p, self.base_dir)
            if not rel.startswith(".."):
                return rel.replace("\\", "/")
        except Exception:
            pass
        # fallback: just the filename (works with asset_dirs on load)
        return os.path.basename(p)

    def _resolve_asset_path(self, p: str | None) -> str | None:
        """Resolve absolute/relative/filename to a real file on THIS machine."""
        if not p:
            return None
        p = p.replace("\\", "/")

        # absolute path that exists?
        if os.path.isabs(p) and os.path.exists(p):
            return p

        # project-relative?
        candidate = os.path.join(self.base_dir, p)
        if os.path.exists(candidate):
            return candidate

        # try by filename in known asset dirs (case-insensitive)
        name = os.path.basename(p).lower()
        for d in self.asset_dirs:
            try:
                for fname in os.listdir(d):
                    if fname.lower() == name:
                        path = os.path.join(d, fname)
                        if os.path.exists(path):
                            return path
            except FileNotFoundError:
                continue
        return None

    def _warn_asset_once(self, key: str, msg: str):
        if key not in self._missing_asset_logged:
            print(msg)
            self._missing_asset_logged.add(key)



    def ensure_save_directory(self):
        # """Create the default save directory if it doesn't exist."""
        Path(self.default_save_dir).mkdir(parents=True, exist_ok=True)

    def _serialize_canvas_v1(self) -> dict[str, Any]:
        """Capture the live Tk canvas in the established lossless v1 format."""
        layout = {
            "version": "1.0",
            "metadata": self._serialize_metadata(),
            "rooms": self._serialize_rooms(),
            "furniture": self._serialize_furniture(),
            "windows": [
                {key: value for key, value in window.items() if key != "item_ids"}
                for window in getattr(self.tools, "windows", [])
            ],
            # Vector openings placed on hand-drawn walls (Windows & Ventilation tool). The web
            # importer projects each onto the nearest wall and renders it in 3D.
            "wall_openings": self._serialize_wall_openings(),
            "shapes": self._serialize_shapes(),
            "text": self._serialize_text(),
        }
        compass_data = self._serialize_compass()
        if compass_data is not None:
            layout["compass"] = compass_data
        return layout

    @staticmethod
    def _stable_canvas_id(floor_id: str, kind: str, source: Any, index: int = 0) -> str:
        token = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(source or index)).strip("-") or str(index)
        return f"{floor_id}:canvas:{kind}:{token}"

    @staticmethod
    def _floor_material(room_or_shape: dict[str, Any]) -> str:
        flooring = room_or_shape.get("flooring") or {}
        return {
            "wood": "floor-wood",
            "tile": "floor-tile",
            "marble": "floor-marble",
            "garden": "floor-grass",
            "grass": "floor-grass",
        }.get(str(flooring.get("flooring_type", "")).lower(), "default-floor")

    def _derive_canvas_geometry(
        self, floor_id: str, canvas_payload: dict[str, Any], existing: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge deterministic canonical geometry derived from a v1 canvas snapshot."""
        geometry = copy.deepcopy(existing) if isinstance(existing, dict) else empty_geometry()
        for collection in empty_geometry():
            geometry.setdefault(collection, [])
        geometry["canvas"] = copy.deepcopy(canvas_payload)
        if "compass" in canvas_payload:
            geometry["compass"] = copy.deepcopy(canvas_payload["compass"])

        generated: dict[str, list[dict[str, Any]]] = {"vertices": [], "walls": [], "rooms": []}

        def append_polygon(points, source, label, floor_material, wall_thickness_cm, source_kind):
            clean = []
            for point in points or []:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    return
                pair = [float(point[0]), float(point[1])]
                if not clean or pair != clean[-1]:
                    clean.append(pair)
            if len(clean) > 1 and clean[0] == clean[-1]:
                clean.pop()
            if len(clean) < 3 or len({tuple(point) for point in clean}) < 3:
                return
            source_token = str(source)
            vertex_ids = []
            for point_index, point in enumerate(clean):
                vertex_id = self._stable_canvas_id(floor_id, "vertex", f"{source_token}-{point_index}")
                generated["vertices"].append({
                    "id": vertex_id,
                    "position": point,
                    "source_canvas_id": source_token,
                })
                vertex_ids.append(vertex_id)
            room_id = self._stable_canvas_id(floor_id, "room", source_token)
            generated["rooms"].append({
                "id": room_id,
                "boundary_vertex_ids": vertex_ids,
                "label": str(label or "Room"),
                "room_type": "custom",
                "floor_material_id": floor_material,
                "source_canvas_id": source_token,
                "source_canvas_kind": source_kind,
            })
            for edge_index, start_id in enumerate(vertex_ids):
                generated["walls"].append({
                    "id": self._stable_canvas_id(floor_id, "wall", f"{source_token}-{edge_index}"),
                    "start_vertex_id": start_id,
                    "end_vertex_id": vertex_ids[(edge_index + 1) % len(vertex_ids)],
                    "thickness_cm": max(0.1, float(wall_thickness_cm)),
                    "height_cm": float(canvas_payload.get("metadata", {}).get("wall_height_cm", 280) or 280),
                    "material_id": "default-wall",
                    "opening_ids": [],
                    "source_canvas_id": source_token,
                })

        for index, room in enumerate(canvas_payload.get("rooms", []) or []):
            if not isinstance(room, dict):
                continue
            source = room.get("id") or room.get("group_tag") or f"room-{index}"
            try:
                x0 = float(room.get("x0", room.get("x", 0)))
                y0 = float(room.get("y0", room.get("y", 0)))
                x1 = float(room.get("x1", x0 + float(room.get("width", 0))))
                y1 = float(room.get("y1", y0 + float(room.get("height", 0))))
            except (TypeError, ValueError):
                continue
            if x0 == x1 or y0 == y1:
                continue
            thickness_cm = max(0.1, float(room.get("wall_thickness_ft", 0.2) or 0.2) * 30.48)
            append_polygon(
                [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], source,
                room.get("name"), self._floor_material(room), thickness_cm, "rectangle_room",
            )

        for index, shape in enumerate(canvas_payload.get("shapes", []) or []):
            if not isinstance(shape, dict):
                continue
            points = shape.get("points") or []
            source = shape.get("id") or next(
                (tag for tag in shape.get("tags", []) if str(tag).startswith(("polygon_group_", "line_"))),
                f"shape-{index}",
            )
            if shape.get("type") == "polygon":
                append_polygon(
                    points, source, shape.get("name") or "Room", self._floor_material(shape),
                    max(10.0, float(shape.get("width", 1) or 1)), "polygon_room",
                )
            elif shape.get("type") == "line" and len(points) == 2:
                try:
                    start, end = [float(points[0][0]), float(points[0][1])], [float(points[1][0]), float(points[1][1])]
                except (IndexError, TypeError, ValueError):
                    continue
                if start == end:
                    continue
                source_token = str(source)
                start_id = self._stable_canvas_id(floor_id, "vertex", f"{source_token}-0")
                end_id = self._stable_canvas_id(floor_id, "vertex", f"{source_token}-1")
                generated["vertices"].extend([
                    {"id": start_id, "position": start, "source_canvas_id": source_token},
                    {"id": end_id, "position": end, "source_canvas_id": source_token},
                ])
                generated["walls"].append({
                    "id": self._stable_canvas_id(floor_id, "wall", source_token),
                    "start_vertex_id": start_id,
                    "end_vertex_id": end_id,
                    "thickness_cm": max(10.0, float(shape.get("width", 1) or 1)),
                    "height_cm": float(canvas_payload.get("metadata", {}).get("wall_height_cm", 280) or 280),
                    "material_id": "default-wall",
                    "opening_ids": [],
                    "source_canvas_id": source_token,
                })

        for collection, derived in generated.items():
            previous = {
                item.get("id"): item for item in geometry.get(collection, [])
                if isinstance(item, dict) and item.get("id")
            }
            retained = [
                copy.deepcopy(item) for item in geometry.get(collection, [])
                if isinstance(item, dict) and "source_canvas_id" not in item
            ]
            retained_ids = {item.get("id") for item in retained}
            finish_fields = (
                ("material_id", "material_side_a", "material_side_b")
                if collection == "walls" else ("floor_material_id",) if collection == "rooms" else ()
            )
            for item in derived:
                old = previous.get(item["id"], {})
                for field in finish_fields:
                    if field in old:
                        item[field] = old[field]
            geometry[collection] = retained + [item for item in derived if item["id"] not in retained_ids]

        # === Planar-graph room detection (port of React detectRooms) ===
        # Merge vertices by canvas position so a wall drawn across a shared edge, or
        # a chain of Line-tool segments forming an enclosure, becomes a single
        # connected wall graph. Then trace every directed edge using the standard
        # smallest-CCW-turn face walk; interior faces become canonical rooms. This
        # replaces the per-shape ring rooms generated above so adjacent rectangles
        # merge into shared-wall rooms and loose line segments cleanly enclose a
        # polygon. Original label/finish material is preserved by inheriting from
        # the smallest enclosing canvas-derived ring room.
        merged_vertices, vertex_alias = room_detection.merge_vertices_by_position(
            generated["vertices"]
        )
        merged_walls = room_detection.dedupe_walls(generated["walls"], vertex_alias)
        # Make the graph planar: add vertices where walls cross and break walls at
        # T-junctions, so divider lines drawn across a room actually split the
        # enclosure into separately detectable faces.
        merged_vertices, merged_walls = room_detection.planarize(merged_vertices, merged_walls)

        vertex_index = {v["id"]: v for v in merged_vertices.values()}
        wall_index = {w["id"]: w for w in merged_walls}
        detected_faces = room_detection.detect_rooms(vertex_index, wall_index) if wall_index else []

        # Index existing ring rooms for finish/label inheritance.
        ring_by_area = []
        for ring in generated.get("rooms", []):
            boundary = ring.get("boundary_vertex_ids", [])
            # Ring rooms reference the original per-shape vertex ids; alias them to the
            # merged canonical ids before shadowing the position lookup against the merged
            # vertex index so inheritance matches detected faces correctly.
            aliased_boundary = [vertex_alias.get(vid, vid) for vid in boundary]
            polygon = [vertex_index.get(vid) for vid in aliased_boundary if vid in vertex_index]
            if any(p is None for p in polygon) or len(polygon) < 3:
                continue
            try:
                area = abs(room_detection.compute_signed_area([p["position"] for p in polygon]))
            except Exception:
                continue
            polygon_pts = [p["position"] for p in polygon]
            ring_by_area.append((area, polygon_pts, ring))

        def centroid(polygon_pts):
            sx = sum(p[0] for p in polygon_pts)
            sy = sum(p[1] for p in polygon_pts)
            return sx / len(polygon_pts), sy / len(polygon_pts)

        def point_in_polygon(point, polygon_pts):
            x, y = point
            inside = False
            previous = polygon_pts[-1]
            for current in polygon_pts:
                x1, y1 = previous
                x2, y2 = current
                if (y1 > y) != (y2 > y):
                    cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                    if x < cross:
                        inside = not inside
                previous = current
            return inside

        detected_rooms = []
        for index, face in enumerate(detected_faces):
            boundary = list(face["boundary_vertex_ids"])
            polygon_pts = [vertex_index[vid]["position"] for vid in boundary if vid in vertex_index]
            if len(polygon_pts) < 3:
                continue
            cx, cy = centroid(polygon_pts)
            # Inherit finish material + friendly label from the smallest enclosing ring room.
            inherited = next(
                (
                    ring for _area, poly, ring in sorted(ring_by_area, key=lambda item: item[0])
                    if point_in_polygon((cx, cy), poly)
                ),
                None,
            )
            room_id = self._stable_canvas_id(
                floor_id, "room", "detected:" + "-".join(boundary)
            )
            record = {
                "id": room_id,
                "boundary_vertex_ids": boundary,
                "label": (inherited or {}).get("label", f"Room {index + 1}"),
                "room_type": (inherited or {}).get("room_type", "custom"),
                "floor_material_id": (inherited or {}).get("floor_material_id", "default-floor"),
                "source_canvas_id": f"detected-room-{index}",
                "source_canvas_kind": "detected_face",
            }
            if (inherited or {}).get("fill_color"):
                record["fill_color"] = inherited["fill_color"]
            if (inherited or {}).get("fill_mode"):
                record["fill_mode"] = inherited["fill_mode"]
            detected_rooms.append(record)

        if detected_rooms:
            # Preserve finish assignments from the prior derived rooms so painted
            # floors survive a re-snapshot without losing their swatch.
            prior_rooms = {
                item.get("id"): item for item in geometry.get("rooms", [])
                if isinstance(item, dict) and "source_canvas_id" in item
            }
            for record in detected_rooms:
                old = prior_rooms.get(record["id"], {})
                if old.get("floor_material_id"):
                    record["floor_material_id"] = old["floor_material_id"]
                if old.get("fill_color"):
                    record["fill_color"] = old["fill_color"]
                if old.get("label") and old.get("source_canvas_kind") == "detected_face":
                    record["label"] = old["label"]
            geometry["rooms"] = detected_rooms + [
                item for item in geometry.get("rooms", [])
                if isinstance(item, dict) and "source_canvas_id" not in item
            ]
            # Replace derived vertices/walls with the merged graph so downstream
            # tools (paint, vastu analysis) operate on the shared-wall topology.
            merged_vertex_records = [copy.deepcopy(v) for v in merged_vertices.values()]
            for v in merged_vertex_records:
                if "source_canvas_id" not in v:
                    v["source_canvas_id"] = v["id"]
                self._attach_position_fields(v)
            geometry["vertices"] = merged_vertex_records + [
                item for item in geometry.get("vertices", [])
                if isinstance(item, dict) and "source_canvas_id" not in item
            ]
            merged_wall_records = [copy.deepcopy(w) for w in merged_walls]
            for w in merged_wall_records:
                if "source_canvas_id" not in w:
                    w["source_canvas_id"] = w["id"]
            geometry["walls"] = merged_wall_records + [
                item for item in geometry.get("walls", [])
                if isinstance(item, dict) and "source_canvas_id" not in item
            ]
        return geometry

    @staticmethod
    def _attach_position_fields(vertex: dict) -> None:
        """Ensure vertices expose both ``position`` and legacy {x, y} for older readers."""
        position = vertex.get("position")
        if isinstance(position, (list, tuple)) and len(position) == 2:
            vertex.setdefault("x", float(position[0]))
            vertex.setdefault("y", float(position[1]))
        elif isinstance(position, dict):
            vertex.setdefault("x", float(position.get("x", 0.0)))
            vertex.setdefault("y", float(position.get("y", 0.0)))
            vertex["position"] = [float(position.get("x", 0.0)), float(position.get("y", 0.0))]

    def _snapshot_active_canvas(self) -> dict[str, Any]:
        canvas_payload = self._serialize_canvas_v1()
        active = self.project_state.active_floor
        geometry = self._derive_canvas_geometry(active["id"], canvas_payload, active["geometry"])
        self.project_state.replace_active_geometry(geometry)
        return canvas_payload

    def serialize_layout(self):
        """Snapshot the live active floor and return one validated native v2 project."""
        canvas_payload = self._snapshot_active_canvas()
        document = self.project_state.snapshot()
        document["metadata"] = copy.deepcopy(canvas_payload.get("metadata", {}))
        candidate = validate_document(document)
        self.project_state.replace(candidate)
        return candidate


    def save_to_json(self):
        layout = self.serialize_layout()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Layout as JSON",
        )
        if not file_path:
            return False
        try:
            atomic_write_document(layout, file_path)
            self.current_layout_file = file_path
            show_message("info", "VastuCraft Pro", f"Layout saved to:\n{file_path}")
            return True
        except Exception as e:
            show_message("error", "VastuCraft Pro", f"Failed to save layout:\n{e}")
            return False

    def save_layout(self) -> bool:
        """Save atomically to the current JSON/YAML path, or prompt for JSON."""
        if not self.current_layout_file:
            return self.save_to_json()
        try:
            atomic_write_document(self.serialize_layout(), self.current_layout_file)
            show_message("info", "VastuCraft Pro", f"Layout saved to:\n{self.current_layout_file}")
            return True
        except ValueError:
            return self.save_to_json()
        except Exception as e:
            show_message("error", "VastuCraft Pro", f"Failed to save layout:\n{e}")
            return False













        




    def deserialize_layout(self, layout_data):
    # """Convert a layout dictionary back to canvas objects."""
        from Furniture import find_image_path

        # Clear the canvas first (except for grid)
        self._clear_canvas()
        try:
            self.tools.windows.clear()
            self.tools.selected_window = None
        except Exception:
            pass
        # Clear runtime room state (so loaded rooms behave like newly created ones)
        try:
            if hasattr(self.tools, "room_entities_by_group_tag"):
                self.tools.room_entities_by_group_tag.clear()
        except Exception:
            pass
        try:
            if hasattr(self.tools, "polygon_rooms_map"):
                self.tools.polygon_rooms_map.clear()
        except Exception:
            pass
        try:
            if hasattr(self.tools, "room_flooring_images"):
                self.tools.room_flooring_images.clear()
        except Exception:
            pass

        # Apply metadata if available
        if "metadata" in layout_data:
            self._deserialize_metadata(layout_data["metadata"])

        # Recreate vector shapes first so background polygons stay behind
        # rooms and furniture, matching the typical user drawing flow.
        if "shapes" in layout_data:
            for shape_data in layout_data["shapes"]:
                self._recreate_shape(shape_data)

        # Recreate rooms next so they sit above plot polygons.
        if "rooms" in layout_data:
            for room_data in layout_data["rooms"]:
                self._recreate_room(room_data)

        # After rooms and polygons exist, rebuild polygon -> room mapping so
        # moving a polygon drags its rooms, just like during normal drawing.
        try:
            if hasattr(self.tools, "rebuild_polygon_room_mapping"):
                self.tools.rebuild_polygon_room_mapping()
        except Exception:
            pass

        # Recreate furniture above rooms/shapes.
        if "furniture" in layout_data:
            for furniture_data in layout_data["furniture"]:
                self._recreate_furniture(furniture_data)

        # Native v1.1 can store semantic windows. Legacy v1 files still infer them
        # from unclaimed wall gaps for backward compatibility.
        semantic_windows = layout_data.get("windows") or []
        if semantic_windows and hasattr(self.tools, "load_window_object"):
            for window_data in semantic_windows:
                self.tools.load_window_object(window_data)
        else:
            self._recreate_inferred_windows(layout_data)

        # Recreate text last so labels remain on top.
        if "text" in layout_data:
            for text_data in layout_data["text"]:
                self._recreate_text(text_data)

        # Restore compass direction so UI matches saved state.
        # If no compass was ever set for this layout, do not introduce one on load.
        compass_data = layout_data.get("compass")
        if isinstance(compass_data, dict) and (
            compass_data.get("direction") or compass_data.get("north_deg_clockwise") is not None
        ):
            self._deserialize_compass(compass_data)
        else:
            self._sync_compass_from_canvas()

        # Ensure tools are back in a normal, editable state so the user can
        # continue adding rooms and furniture after loading a layout.
        try:
            if hasattr(self.tools, "reset_modes"):
                self.tools.reset_modes()
            if hasattr(self.tools, "canvas_frozen"):
                self.tools.canvas_frozen = False
        except Exception:
            pass

        print("Layout loaded successfully")

    def _recreate_inferred_windows(self, layout_data):
        """Render window symbols for native-v1 wall gaps not occupied by doors."""
        doors = []
        for furniture in layout_data.get("furniture", []) or []:
            name = str(
                furniture.get("image_name")
                or furniture.get("image_filename")
                or furniture.get("image_path")
                or ""
            ).lower()
            if "door" not in name:
                continue
            try:
                doors.append((float(furniture["x"]), float(furniture["y"])))
            except (KeyError, TypeError, ValueError):
                continue

        seen = set()
        created = 0
        room_map = getattr(self.tools, "room_entities_by_group_tag", {}) or {}
        for room_data in layout_data.get("rooms", []) or []:
            if str(room_data.get("fill_mode", "filled")) != "walls_only":
                continue
            erased = room_data.get("wall_erased_regions")
            if not isinstance(erased, dict):
                continue
            try:
                x0 = float(room_data.get("x0", room_data.get("x", 0)))
                y0 = float(room_data.get("y0", room_data.get("y", 0)))
                raw_x1, raw_y1 = room_data.get("x1"), room_data.get("y1")
                x1 = float(raw_x1) if raw_x1 is not None else x0 + float(room_data.get("width", 0))
                y1 = float(raw_y1) if raw_y1 is not None else y0 + float(room_data.get("height", 0))
            except (TypeError, ValueError):
                continue

            group_tag = str(room_data.get("group_tag") or "")
            room = room_map.get(group_tag)
            try:
                thickness = float(room._wall_thickness_pixels()) if room else 10.0
            except Exception:
                thickness = 10.0
            half_frame = max(2.0, thickness * 0.25)
            door_tolerance = max(8.0, thickness)

            for side, gaps in erased.items():
                if side not in ("top", "bottom", "left", "right") or not isinstance(gaps, list):
                    continue
                horizontal = side in ("top", "bottom")
                wall_pos = y0 if side == "top" else y1 if side == "bottom" else x0 if side == "left" else x1
                axis_min = x0 if horizontal else y0 + thickness
                axis_max = x1 if horizontal else y1 - thickness
                for gap in gaps:
                    try:
                        g0, g1 = sorted((float(gap[0]), float(gap[1])))
                    except (IndexError, TypeError, ValueError):
                        continue
                    if g1 <= g0 or g1 - g0 >= axis_max - axis_min - 2:
                        continue
                    # ponytail: v1 has no opening type; remove this center match when the
                    # native schema explicitly stores doors and windows.
                    if any(
                        abs((dy if horizontal else dx) - wall_pos) <= door_tolerance
                        and g0 - door_tolerance <= (dx if horizontal else dy) <= g1 + door_tolerance
                        for dx, dy in doors
                    ):
                        continue

                    key = (horizontal, round(wall_pos, 2), round(g0, 2), round(g1, 2))
                    if key in seen:
                        continue
                    seen.add(key)
                    tags = ("room", group_tag, "window_symbol")
                    if horizontal:
                        frame = self.canvas.create_line(
                            g0, wall_pos - half_frame, g1, wall_pos - half_frame,
                            g1, wall_pos + half_frame, g0, wall_pos + half_frame,
                            g0, wall_pos - half_frame, fill="#2563eb", width=2, tags=tags,
                        )
                        pane = self.canvas.create_line(g0, wall_pos, g1, wall_pos, fill="#93c5fd", width=3, tags=tags)
                    else:
                        frame = self.canvas.create_line(
                            wall_pos - half_frame, g0, wall_pos - half_frame, g1,
                            wall_pos + half_frame, g1, wall_pos + half_frame, g0,
                            wall_pos - half_frame, g0, fill="#2563eb", width=2, tags=tags,
                        )
                        pane = self.canvas.create_line(wall_pos, g0, wall_pos, g1, fill="#93c5fd", width=3, tags=tags)
                    if room is not None and hasattr(room, "items"):
                        room.items.extend((frame, pane))
                    created += 1
        return created

    def _recreate_room(self, room_data):
        """Recreate a room from serialized data (with label + interactions)."""
        # Prefer recreating via RoomEntity so room double-click + room label work everywhere (mac/win/linux).
        try:
            from entities import RoomEntity
        except Exception:
            RoomEntity = None  # type: ignore[assignment]

        # Geometry (support both new and legacy schemas)
        x0 = room_data.get("x0", room_data.get("x", 0))
        y0 = room_data.get("y0", room_data.get("y", 0))
        x1 = room_data.get("x1")
        y1 = room_data.get("y1")
        if x1 is None:
            x1 = x0 + float(room_data.get("width", 0) or 0)
        if y1 is None:
            y1 = y0 + float(room_data.get("height", 0) or 0)
        width_px = float(x1) - float(x0)
        height_px = float(y1) - float(y0)

        group_tag = room_data.get("group_tag") or ""
        group_id = room_data.get("group_id")
        if group_id is None and isinstance(group_tag, str) and group_tag.startswith("room_group_"):
            try:
                group_id = int(group_tag.split("_")[-1])
            except Exception:
                group_id = None
        if group_id is None:
            group_id = int(getattr(self.model, "room_counter", 0) or 0)
            setattr(self.model, "room_counter", int(group_id) + 1)
        # Keep room_counter ahead to avoid duplicate group ids after load
        try:
            cur = int(getattr(self.model, "room_counter", 0) or 0)
            nxt = int(group_id) + 1
            if nxt > cur:
                setattr(self.model, "room_counter", nxt)
        except Exception:
            pass

        if not (isinstance(group_tag, str) and group_tag.startswith("room_group_")):
            group_tag = f"room_group_{group_id}"

        # Dimensions in real-world units (fallback: infer from pixels and current unit/grid/zoom)
        width_real = room_data.get("width_real")
        height_real = room_data.get("height_real")
        if width_real is None or height_real is None:
            try:
                unit_scale = self.model.unit_scale[self.model.unit]
                denom = float(self.model.grid_spacing) * float(self.model.zoom_level)
                if denom > 0:
                    width_real = (float(width_px) / denom) * float(unit_scale)
                    height_real = (float(height_px) / denom) * float(unit_scale)
            except Exception:
                width_real = width_real if width_real is not None else 0
                height_real = height_real if height_real is not None else 0

        name = room_data.get("name") or "Room"
        fill_mode = room_data.get("fill_mode") or "filled"
        fill_color = room_data.get("fill_color")
        wall_thickness_ft = float(room_data.get("wall_thickness_ft", 0.2) or 0.2)

        room_id = None
        if RoomEntity is not None and self.tools is not None:
            try:
                room = RoomEntity(
                    self.canvas,
                    self.model,
                    name,
                    float(width_real or 0),
                    float(height_real or 0),
                    int(group_id),
                    fill_mode=fill_mode,
                    fill_color=fill_color,
                    wall_thickness_ft=wall_thickness_ft,
                )
                # Reposition to serialized coordinates
                try:
                    for item in getattr(room, "items", []) or []:
                        self.canvas.delete(item)
                except Exception:
                    pass
                room.x0, room.y0, room.x1, room.y1 = float(x0), float(y0), float(x1), float(y1)
                room.width_px = float(width_px)
                room.height_px = float(height_px)
                room.wlabel = float(width_real or 0)
                room.hlabel = float(height_real or 0)
                room.create()

                # Apply saved wall erased regions (restores erase state from save)
                wall_erased = room_data.get("wall_erased_regions")
                if wall_erased and hasattr(self.tools, "apply_wall_erased_regions"):
                    try:
                        # Treat serialized wall_erased_regions as manual erasures so they
                        # persist across door recuts and room moves.
                        try:
                            setattr(room, "_manual_wall_erased_regions", copy.deepcopy(wall_erased))
                        except Exception:
                            pass
                        self.tools.apply_wall_erased_regions(
                            room, wall_erased, float(x0), float(y0), float(x1), float(y1)
                        )
                    except Exception as e:
                        print(f"[Serializer] apply_wall_erased_regions: {e}")

                # Register for runtime room operations
                try:
                    if hasattr(self.tools, "room_entities_by_group_tag"):
                        self.tools.room_entities_by_group_tag[room.group_tag] = room
                except Exception:
                    pass
                room_id = getattr(room, "rect_id", None)
            except Exception:
                room_id = None

        # Fallback: raw rectangle (no label/bindings)
        if room_id is None:
            # ponytail: Warn once per load session instead of per room to avoid spam
            if not hasattr(self, "_load_fallback_warned"):
                self._load_fallback_warned = True
                room_name = room_data.get("name", "Unknown")
                messagebox.showwarning(
                    "Room Loading Fallback",
                    f"Room '{room_name}' could not be fully restored.\n\n"
                    f"It will appear as a basic rectangle without labels or normal editing behavior.\n\n"
                    f"This usually happens when:\n"
                    f"• RoomEntity class is unavailable\n"
                    f"• Room data format is incompatible\n\n"
                    f"Subsequent rooms with similar issues will load silently."
                )
            room_id = self.canvas.create_rectangle(
                float(x0),
                float(y0),
                float(x1),
                float(y1),
                fill=room_data.get("fill_color", ""),
                outline=room_data.get("outline_color", "black"),
                tags=("room", group_tag or f"room_group_{group_id}"),
            )

        # Recreate flooring if it exists
        if room_data.get("flooring", {}).get("has_flooring", False):
            flooring_info = room_data.get("flooring") or {}
            self._recreate_room_flooring(room_id, room_data, flooring_info)
    
    def _recreate_room_flooring(self, room_id, room_data, flooring_info):
        # """Recreate flooring for a room."""
        from PIL import Image, ImageTk
        import os
        
        # Resolve flooring image path in a cross-platform way.
        flooring_path_raw = flooring_info.get("image_path", "")
        flooring_path = self._resolve_asset_path(flooring_path_raw)
        flooring_type = flooring_info.get("flooring_type", "wood")

        # If the stored path cannot be resolved (moved project, different OS),
        # fall back to the standard flooring directory used at runtime.
        if not flooring_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            flooring_dir = os.path.join(base_dir, "flooring")
            for ext in ("png", "jpeg", "jpg"):
                alt_path = os.path.join(flooring_dir, f"{flooring_type}.{ext}")
                if os.path.exists(alt_path):
                    flooring_path = alt_path
                    break

        if not flooring_path or not os.path.exists(flooring_path):
            print(f"Warning: Flooring image not found: {flooring_path_raw or flooring_path}")
            return
        
        try:
            # Calculate room dimensions (support both new and legacy schemas)
            x0 = float(room_data.get("x0", room_data.get("x", 0)))
            y0 = float(room_data.get("y0", room_data.get("y", 0)))
            width = float(room_data.get("width", 0))
            height = float(room_data.get("height", 0))
            x1 = x0 + width
            y1 = y0 + height
            
            # Load and resize flooring image
            img = Image.open(flooring_path)
            img = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img, master=self.canvas)
            
            # Create flooring image
            image_id = self.canvas.create_image(
                x0,
                y0,
                image=tk_img,
                anchor="nw",
                tags=("flooring", room_data.get("group_tag", "")),
            )
            
            # Create border
            border_id = self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                outline="black",
                width=2,
                tags=("flooring_border", room_data.get("group_tag", "")),
            )
            
            # Store flooring data in tools for future operations
            if not hasattr(self.tools, "room_flooring_images"):
                self.tools.room_flooring_images = {}
                
            self.tools.room_flooring_images[room_id] = {
                "image_id": image_id,
                "tk_img": tk_img,
                "border_id": border_id,
                "image_path": flooring_path,
            }
            
            # Manage z-order
            self.canvas.tag_raise(border_id, image_id)
            try:
                self.canvas.tag_raise("line")
                self.canvas.tag_raise("line_label")
                self.canvas.tag_raise("line_point")
            except Exception:
                pass

        except Exception as e:
            print(f"Error recreating flooring: {e}")

    def _recreate_polygon_flooring(self, poly_id, shape_data, flooring_info, group_tag):
        """Recreate flooring for a polygon from serialized data."""
        from PIL import Image, ImageTk, ImageDraw
        import os

        flooring_path_raw = flooring_info.get("image_path", "")
        flooring_path = self._resolve_asset_path(flooring_path_raw)
        flooring_type = flooring_info.get("flooring_type", "wood")
        if not flooring_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            flooring_dir = os.path.join(base_dir, "flooring")
            for ext in ("png", "jpeg", "jpg"):
                alt_path = os.path.join(flooring_dir, f"{flooring_type}.{ext}")
                if os.path.exists(alt_path):
                    flooring_path = alt_path
                    break
        if not flooring_path or not os.path.exists(flooring_path):
            print(f"Warning: Polygon flooring image not found: {flooring_path_raw or flooring_path}")
            return
        try:
            points = shape_data.get("points", [])
            if len(points) < 3:
                return
            coords = [c for p in points for c in p]
            xs, ys = coords[::2], coords[1::2]
            x0 = int(min(xs))
            y0 = int(min(ys))
            x1 = int(max(xs))
            y1 = int(max(ys))
            width, height = max(1, x1 - x0), max(1, y1 - y0)
            img = Image.open(flooring_path).resize((width, height), Image.Resampling.LANCZOS)
            mask = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(mask)
            poly_rel = [(coords[i] - x0, coords[i + 1] - y0) for i in range(0, len(coords), 2)]
            draw.polygon(poly_rel, fill=255)
            result = Image.new("RGBA", (width, height))
            result.paste(img, (0, 0), mask)
            tk_img = ImageTk.PhotoImage(result, master=self.canvas)
            image_tags = ("flooring", group_tag) if group_tag else ("flooring",)
            image_id = self.canvas.create_image(
                x0, y0, image=tk_img, anchor="nw", tags=image_tags,
            )
            try:
                self.canvas.tag_lower(image_id, poly_id)
            except Exception:
                pass
            try:
                if group_tag:
                    for it in self.canvas.find_withtag(group_tag):
                        try:
                            t = self.canvas.type(it)
                            tags_it = self.canvas.gettags(it)
                            if t == "oval" and "polygon_vertex" in tags_it:
                                self.canvas.tag_raise(it, image_id)
                            if t == "text" and "polygon_label" in tags_it:
                                self.canvas.tag_raise(it, image_id)
                        except Exception:
                            continue
                    self.canvas.tag_raise(poly_id, image_id)
                # Keep lines and their labels above flooring
                self.canvas.tag_raise("line")
                self.canvas.tag_raise("line_label")
                self.canvas.tag_raise("line_point")
            except Exception:
                pass
            if not hasattr(self.tools, "room_flooring_images"):
                self.tools.room_flooring_images = {}
            self.tools.room_flooring_images[poly_id] = {
                "kind": "polygon",
                "image_id": image_id,
                "tk_img": tk_img,
                "image_path": flooring_path,
                "group_tag": group_tag,
                "border_id": None,
                "polygon_coords": list(coords),
            }
        except Exception as e:
            print(f"Error recreating polygon flooring: {e}")

    def _furniture_size_for_load(self, furniture_data, name):
        """Return plan-scale target pixels and real dimensions for old and new files."""
        target = furniture_data.get("target_size")
        if isinstance(target, (list, tuple)) and len(target) == 2:
            try:
                target = (max(8, int(float(target[0]))), max(8, int(float(target[1]))))
            except (TypeError, ValueError):
                target = None
        else:
            target = None

        real_size = furniture_data.get("real_size_ft")
        if isinstance(real_size, (list, tuple)) and len(real_size) == 2:
            try:
                real_size = (float(real_size[0]), float(real_size[1]))
                if real_size[0] <= 0 or real_size[1] <= 0:
                    real_size = None
            except (TypeError, ValueError):
                real_size = None
        else:
            real_size = None

        unit_factor = float(self.model.unit_scale.get(self.model.unit, 1.0))
        pixels_per_unit = float(self.model.grid_spacing) * float(self.model.zoom_level) / max(unit_factor, 1e-9)
        if real_size is None and target is None:
            from Furniture import furniture_data as furniture_sizes
            normalized = str(name).lower().replace(" ", "").replace("_", "")
            real_size = (
                furniture_sizes.STANDARD_FURNITURE_SIZES.get(normalized)
                or furniture_sizes.STANDARD_FURNITURE_SIZES.get(str(name).lower().replace(" ", "_"))
                or (3.0, 3.0)
            )
            conversion = {
                "m": 1.0 / 3.28084,
                "cm": 100.0 / 3.28084,
                "in": 12.0,
                "yards": 1.0 / 3.0,
            }.get(str(self.model.unit).lower(), 1.0)
            real_size = (float(real_size[0]) * conversion, float(real_size[1]) * conversion)
        if target is None:
            target = (
                max(8, int(real_size[0] * pixels_per_unit)),
                max(8, int(real_size[1] * pixels_per_unit)),
            )
        if real_size is None:
            real_size = (target[0] / pixels_per_unit, target[1] / pixels_per_unit)
        return target, real_size

    def _recreate_furniture(self, furniture_data):
        # """Recreate furniture from serialized data."""
        from Furniture import find_image_path
        image_path = None
        stored = furniture_data.get("image_path")
        # Method 1: Try the stored full path (absent in engine/AI-authored native furniture).
        if stored and os.path.exists(stored):
            image_path = stored
        # Method 2: Try using the image name with find_image_path function
        elif furniture_data.get("image_name"):
            image_path = find_image_path(furniture_data["image_name"])
        # Method 3: Try using the filename in local Images directory
        elif furniture_data.get("image_filename"):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            local_path = os.path.join(base_dir, "Images", furniture_data["image_filename"])
            if os.path.exists(local_path):
                image_path = local_path
        # Method 4: Extract a name from a stored (but unresolved) path and search
        elif stored:
            original_name = os.path.splitext(os.path.basename(stored))[0]
            image_path = find_image_path(original_name)

        if not image_path:
            missing = furniture_data.get("image_name") or furniture_data.get("image_filename") or stored
            print(f"Warning: Could not locate furniture image: {missing}")
            return
        
        # Recreate furniture using the current model's grid/zoom/unit so sizes match
        # even after loading on a different machine or after zoom/unit changes.
        try:
            raw_name = (
                furniture_data.get("image_name")
                or os.path.splitext(os.path.basename(image_path))[0]
                or "furniture"
            )
            name = str(raw_name).replace("_", " ").strip() or str(raw_name)

            from Furniture import Furniture
            target_size, saved_real_size = self._furniture_size_for_load(furniture_data, raw_name)
            item = Furniture(
                canvas=self.canvas,
                image_path=image_path,
                x=float(furniture_data["x"]),
                y=float(furniture_data["y"]),
                select_callback=self.tools.select_image_item,
                scale=float(furniture_data.get("scale", 1.0)),
                angle=float(furniture_data.get("angle", 0)) % 360,
                get_freeze_state=self.tools.get_canvas_freeze_state,
                edit_callback=self.tools.enter_furniture_edit_mode,
                duplicate_callback=self.tools.duplicate_furniture,
                delete_callback=self.tools.delete_furniture_item,
                target_size=target_size,
            )
            self.tools.image_furniture_items.append(item)
            item.real_size_ft = saved_real_size
            item.model_ref = self.model
            item.initial_angle = float(furniture_data.get("initial_angle", furniture_data.get("angle", 0))) % 360

            # Restore angle
            try:
                item.angle = float(furniture_data.get("angle", 0)) % 360
            except Exception:
                item.angle = 0
            try:
                item.update_image()
                self.canvas.itemconfig(item.image_id, image=item.tk_image)
            except Exception:
                pass

            # Deselect furniture after loading (since insert_furniture_scaled auto-selects)
            # This ensures furniture can be properly selected when user clicks on it
            if hasattr(self.tools, 'selected_furniture_obj') and self.tools.selected_furniture_obj == item:
                if hasattr(self.tools.selected_furniture_obj, 'delete_handles'):
                    try:
                        self.tools.selected_furniture_obj.delete_handles()
                    except Exception:
                        pass
                self.tools.selected_furniture_obj = None

            try:
                committed = self.tools.commit_furniture_to_underlying_group(item)
            except Exception:
                committed = False
            if not committed:
                item.committed = True
                item.editing = False
            item.delete_handles()
            item.is_selected = False
            item.delete_highlight()
            item.model_ref = self.model
            item.is_door = "door" in os.path.basename(image_path).lower()
            print(f"Successfully recreated furniture (scaled): {os.path.basename(image_path)}")
            return item
        except Exception as e:
            print(f"Error recreating furniture: {e}")
            return None









    def _recreate_shape(self, shape_data):
        # """Recreate shapes from serialized data."""
        coords = [coord for point in shape_data["points"] for coord in point]
        tag_values = list(shape_data.get("tags", []))
        source_tag = f"source_shape:{shape_data.get('id')}"
        if shape_data.get("id") and source_tag not in tag_values:
            tag_values.append(source_tag)
        tags = tuple(tag_values)
        dash = shape_data.get("dash") or ((4, 2) if shape_data.get("style") == "dashed" else "")

        if shape_data["type"] == "line":
            self.canvas.create_line(
                *coords,
                fill=shape_data["outline_color"],
                width=shape_data["width"],
                dash=dash,
                tags=tags,
                arrow=shape_data.get("arrow", "none"),
            )
        elif shape_data["type"] == "rectangle":
            self.canvas.create_rectangle(
                *coords,
                fill=shape_data["fill_color"],
                outline=shape_data["outline_color"],
                width=shape_data["width"],
                dash=dash,
                tags=tags,
            )
        elif shape_data["type"] == "oval":
            self.canvas.create_oval(
                *coords,
                fill=shape_data["fill_color"],
                outline=shape_data["outline_color"],
                width=shape_data["width"],
                dash=dash,
                tags=tags,
            )
        elif shape_data["type"] == "polygon":
            group_tag = next(
                (t for t in tags if isinstance(t, str) and t.startswith("polygon_group_")),
                None,
            )
            # Clear fill so flooring texture shows through when flooring is applied
            fill_color = shape_data["fill_color"]
            flooring_info = shape_data.get("flooring") or {}
            if flooring_info.get("has_flooring"):
                fill_color = ""
            poly_id = self.canvas.create_polygon(
                *coords,
                fill=fill_color,
                outline=shape_data["outline_color"],
                width=shape_data["width"],
                dash=dash,
                tags=tags,
            )

            # Recreate polygon flooring if it was saved
            if flooring_info.get("has_flooring"):
                try:
                    self._recreate_polygon_flooring(poly_id, shape_data, flooring_info, group_tag)
                except Exception:
                    pass

            # Regenerate edge dimensions
            try:
                if "polygon_shape" in tags and hasattr(self.tools, "dimension_drawer"):
                    pts = [
                        (float(p[0]), float(p[1]))
                        for p in shape_data.get("points", [])
                    ]
                    dim_tag = f"{group_tag}__dims"
                    self.tools.dimension_drawer.draw_polygon_edge_dimensions(
                        pts,
                        group_tag=group_tag,
                        dim_tag=dim_tag,
                    )
            except Exception:
                pass

            # Regenerate Vastu polygon edge dimensions (if enabled)
            try:
                if (
                    "vastu_polygon" in tags
                    and "vastu_group" in tags
                    and hasattr(self.tools, "dimension_drawer")
                    and getattr(getattr(self.tools, "model", None), "auto_vastu_polygon_dimensions", True)
                ):
                    pts = [
                        (float(p[0]), float(p[1]))
                        for p in shape_data.get("points", [])
                    ]
                    self.tools.dimension_drawer.draw_polygon_edge_dimensions(
                        pts,
                        group_tag="vastu_group",
                        dim_tag="vastu_dimensions",
                    )
            except Exception:
                pass

    def _recreate_text(self, text_data):
        # """Recreate text from serialized data."""
        tags = tuple(text_data.get("tags") or ())

        # Skip persisted auto-generated labels and dimension annotations.
        if any(
            t in (
                "grid",
                "room_label",
                "dimension_item",
                "dimension_label",
                "dimension_text_bg",
                "room_dimensions",
            )
            for t in tags
        ):
            return

        # Vastu centroid label is no longer used; skip old persisted ones on load.
        if "vastu_centroid" in tags:
            return

        # Backwards‑compat: older files may not have tags. Best‑effort skip of
        # typical room auto‑labels (e.g. "kitchen\n12.0×12.0 ft") so they are
        # not duplicated on top of RoomEntity labels.
        if not tags:
            content = str(text_data.get("content", ""))
            if (
                "\n" in content
                and "×" in content
                and any(unit in content for unit in (" ft", " m", " in", " yd"))
            ):
                return

        # Prefer model coordinates for zoom-independent placement; fallback to pixels (old format)
        x_real = text_data.get("x_real")
        y_real = text_data.get("y_real")
        if x_real is not None and y_real is not None:
            px, py = self.view.real_to_pixel(x_real, y_real)
        else:
            px = float(text_data.get("x", 0))
            py = float(text_data.get("y", 0))

        self.canvas.create_text(
            px,
            py,
            text=text_data["content"],
            font=text_data["font"],
            fill=text_data["color"],
            anchor="nw",
            tags=tags,
        )


    def load_from_json(self):
        file_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Layout from JSON",
        )
        return bool(file_path and self.load_from_file(file_path))

    def _validate_native_layout(self, data):
        """Validate the native v1 document before any current canvas state is touched."""
        if not isinstance(data, dict) or str(data.get("version")) != "1.0":
            raise ValueError("Not a native VastuCraft Layout Maker v1.0 file (Home Quest .hq.json is not supported here).")
        for key in ("metadata", "rooms", "furniture", "shapes", "text"):
            if key not in data:
                raise ValueError(f"Incomplete native layout: missing '{key}'.")
        if not isinstance(data["metadata"], dict):
            raise ValueError("Invalid native layout metadata.")
        for key in ("rooms", "furniture", "shapes", "text", "windows"):
            if key in data and not isinstance(data[key], list):
                raise ValueError(f"Invalid native layout '{key}' collection.")
        for room in data["rooms"]:
            if not isinstance(room, dict) or not all(k in room or legacy in room for k, legacy in (("x0", "x"), ("y0", "y"), ("x1", "width"), ("y1", "height"))):
                raise ValueError("Invalid room geometry in native layout.")
        for shape in data["shapes"]:
            if not isinstance(shape, dict) or shape.get("type") not in ("line", "rectangle", "oval", "polygon") or not isinstance(shape.get("points"), list):
                raise ValueError("Invalid shape in native layout.")
        for furniture in data["furniture"]:
            if not isinstance(furniture, dict) or "x" not in furniture or "y" not in furniture or not any(k in furniture for k in ("image_path", "image_name", "image_filename")):
                raise ValueError("Invalid furniture in native layout.")
        for text in data["text"]:
            if not isinstance(text, dict) or "content" not in text:
                raise ValueError("Invalid text item in native layout.")
        for window in data.get("windows", []):
            if not isinstance(window, dict) or not all(k in window for k in ("id", "room_group_tag", "wall_side", "start", "end", "window_type")):
                raise ValueError("Invalid window in native layout.")
        return True

    def _confirm_and_backup_current_layout(self):
        design_items = [item for item in self.canvas.find_all() if "grid" not in self.canvas.gettags(item)]
        if not design_items:
            return True
        if not messagebox.askyesno(
            "Replace Current Layout",
            "Loading will replace the current drawing. Create a backup and continue?",
            parent=self.canvas.winfo_toplevel(),
        ):
            return False
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.default_save_dir, f"before_load_{timestamp}.json")
        atomic_write_document(self.serialize_layout(), backup_path)
        return True

    def _canvas_from_geometry(self, document: dict[str, Any], floor: dict[str, Any]) -> dict[str, Any]:
        """Return the exact parked canvas or a v1 view reconstructed from canonical v2."""
        geometry = floor["geometry"]
        canvas = geometry.get("canvas")
        if isinstance(canvas, dict):
            return copy.deepcopy(canvas)

        vertices = {
            vertex["id"]: vertex.get("position", [vertex.get("x", 0), vertex.get("y", 0)])
            for vertex in geometry.get("vertices", []) if isinstance(vertex, dict)
        }
        rooms, shapes = [], []
        room_edges = set()
        for index, room in enumerate(geometry.get("rooms", [])):
            boundary = list(room.get("boundary_vertex_ids", []))
            points = [vertices[vertex_id] for vertex_id in boundary if vertex_id in vertices]
            if len(points) < 3:
                continue
            for edge_index, start in enumerate(boundary):
                room_edges.add(frozenset((start, boundary[(edge_index + 1) % len(boundary)])))
            xs = {float(point[0]) for point in points}
            ys = {float(point[1]) for point in points}
            if len(points) == 4 and len(xs) == 2 and len(ys) == 2:
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                rooms.append({
                    "id": room["id"], "name": room.get("label", room.get("name", "Room")),
                    "group_tag": f"room_group_{index}", "group_id": index,
                    "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                    "width": x1 - x0, "height": y1 - y0,
                    "fill_mode": room.get("fill_mode", "filled"),
                    "fill_color": room.get("fill_color", ""),
                    "wall_thickness_ft": 0.2, "flooring": {"has_flooring": False},
                })
            else:
                shapes.append({
                    "id": room["id"], "type": "polygon", "points": copy.deepcopy(points),
                    "outline_color": "black", "fill_color": room.get("fill_color", ""),
                    "width": 2, "style": "solid", "dash": "",
                    "tags": ["closed_shape", f"polygon_group_{index}"],
                    "flooring": {"has_flooring": False},
                })
        for wall in geometry.get("walls", []):
            start_id, end_id = wall.get("start_vertex_id"), wall.get("end_vertex_id")
            if start_id not in vertices or end_id not in vertices or frozenset((start_id, end_id)) in room_edges:
                continue
            shapes.append({
                "id": wall["id"], "type": "line",
                "points": [copy.deepcopy(vertices[start_id]), copy.deepcopy(vertices[end_id])],
                "outline_color": "black", "fill_color": "", "width": 2,
                "style": "solid", "dash": "", "tags": ["line", f"line_{wall['id']}"],
            })
        text = []
        for item in geometry.get("text", []):
            position = item.get("position", [item.get("x", 0), item.get("y", 0)])
            text.append({
                "id": item["id"], "content": item.get("text", item.get("content", "")),
                "x": position[0], "y": position[1], "font": item.get("font", "Arial 10"),
                "color": item.get("color", "black"), "tags": item.get("tags", ["user_text"]),
            })
        result = {
            "version": "1.0", "metadata": copy.deepcopy(document.get("metadata", {})),
            "rooms": rooms, "furniture": [], "windows": [], "shapes": shapes, "text": text,
        }
        if isinstance(geometry.get("compass"), dict):
            result["compass"] = copy.deepcopy(geometry["compass"])
        return result

    def commit_active_geometry(self, mutation, *, redraw_structures=False):
        """Validate and commit one active-floor geometry edit with one history snapshot."""
        self._snapshot_active_canvas()
        before = self.project_state.snapshot()
        geometry = copy.deepcopy(self.project_state.active_floor["geometry"])
        result = mutation(geometry)
        self.project_state.replace_active_geometry(geometry)
        after = self.project_state.snapshot()
        if redraw_structures:
            try:
                self._draw_active_structures()
            except Exception as exc:
                print(f"[Serializer] structure redraw failed: {exc}")
        if before != after:
            self.actions.log({"type": "project_snapshot", "before": before, "after": after})
        return copy.deepcopy(result)

    def _structure_scale(self) -> float:
        """Return native plan pixels per centimeter for basic structure symbols."""
        metadata = self.project_state.snapshot().get("metadata", {})
        units = {
            "mm": .1, "millimeter": .1, "millimeters": .1,
            "cm": 1.0, "centimeter": 1.0, "centimeters": 1.0,
            "m": 100.0, "meter": 100.0, "meters": 100.0,
            "in": 2.54, "inch": 2.54, "inches": 2.54,
            "ft": 30.48, "foot": 30.48, "feet": 30.48,
            "yd": 91.44, "yard": 91.44, "yards": 91.44,
        }
        try:
            cm_per_unit = units.get(str(metadata.get("unit", "feet")).lower(), 30.48)
            spacing = float(metadata.get("grid_spacing", 20) or 20)
            zoom = float(metadata.get("zoom_level", 1) or 1)
            unit_scale = float(metadata.get("unit_scale", 1) or 1)
            return max(.001, spacing * zoom / (unit_scale * cm_per_unit))
        except (TypeError, ValueError, ZeroDivisionError):
            return 20 / 30.48

    def _draw_floor_underlay(self) -> None:
        """Draw the nearest lower floor as a muted, non-editable reference."""
        document = self.project_state.snapshot()
        active = next(
            floor for floor in document["floors"]
            if floor["id"] == document["active_floor_id"]
        )
        lower_floors = [
            floor for floor in document["floors"]
            if float(floor["elevation_cm"]) < float(active["elevation_cm"])
        ]
        if not lower_floors:
            return

        floor = max(lower_floors, key=lambda item: float(item["elevation_cm"]))
        layout = self._canvas_from_geometry(document, floor)
        tags = ("parity_structure", "parity_floor_underlay", f"floor:{floor['id']}")
        # ponytail: Tk canvas vectors have no alpha. An unfilled dashed outline is
        # clearer than stippling on the regular dark grid and still reads as reference geometry.
        outline, dash = "#60a5fa", (6, 4)

        for shape in layout.get("shapes", []) or []:
            try:
                coords = [float(value) for point in shape.get("points", []) for value in point]
                kind = shape.get("type")
                if kind == "line" and len(coords) >= 4:
                    self.canvas.create_line(
                        *coords, fill=outline, width=2, dash=dash, tags=tags,
                    )
                elif kind in ("rectangle", "oval") and len(coords) == 4:
                    creator = self.canvas.create_rectangle if kind == "rectangle" else self.canvas.create_oval
                    creator(
                        *coords, fill="", outline=outline, width=2,
                        dash=dash, tags=tags,
                    )
                elif kind == "polygon" and len(coords) >= 6:
                    self.canvas.create_polygon(
                        *coords, fill="", outline=outline, width=2,
                        dash=dash, tags=tags,
                    )
            except (TypeError, ValueError, tk.TclError):
                continue

        for room in layout.get("rooms", []) or []:
            try:
                x0 = float(room.get("x0", room.get("x", 0)))
                y0 = float(room.get("y0", room.get("y", 0)))
                raw_x1, raw_y1 = room.get("x1"), room.get("y1")
                x1 = float(raw_x1) if raw_x1 is not None else x0 + float(room.get("width", 0))
                y1 = float(raw_y1) if raw_y1 is not None else y0 + float(room.get("height", 0))
                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill="", outline=outline,
                    width=2, dash=dash, tags=tags,
                )
            except (TypeError, ValueError, tk.TclError):
                continue

        # Keep the grid at the very back, then the underlay, then active-floor items.
        self.canvas.tag_lower("parity_floor_underlay")
        self.canvas.tag_lower("grid")

    def _draw_active_structures(self) -> None:
        """Redraw canonical structures without disturbing the stable floor underlay."""
        for item in self.canvas.find_withtag("parity_structure"):
            if "parity_floor_underlay" not in self.canvas.gettags(item):
                self.canvas.delete(item)
        floor = self.project_state.active_floor
        floor_id, geometry = floor["id"], floor["geometry"]
        swatches = {}
        try:
            with open(os.path.join(self.base_dir, "finish_manifest.json"), encoding="utf-8") as stream:
                swatches = {item["id"]: item["swatch"] for item in json.load(stream).get("finishes", [])}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        scale = self._structure_scale()

        def tags(kind, entity_id):
            return (
                "parity_structure", f"parity_{kind}",
                f"entity:{entity_id}", f"floor:{floor_id}",
            )

        for stair in geometry.get("stairs", []):
            points = stair.get("path_points", [])
            if len(points) < 2:
                continue
            try:
                coords = [float(coordinate) for point in points for coordinate in point]
                width_px = max(2, float(stair.get("width_cm", 110)) * scale)
            except (TypeError, ValueError):
                continue
            stair_tags = tags("stair", stair["id"])
            self.canvas.create_line(
                *coords, fill="#c7d2fe", width=width_px,
                capstyle="projecting", joinstyle="miter", tags=stair_tags,
            )
            self.canvas.create_line(
                *coords, fill="#6366f1", width=2, arrow="last", tags=stair_tags,
            )
            for point in points[1:-1]:
                x, y = map(float, point)
                half = width_px / 2
                self.canvas.create_rectangle(
                    x - half, y - half, x + half, y + half,
                    fill="", outline="#6366f1", width=2, tags=stair_tags,
                )
            middle = points[len(points) // 2]
            self.canvas.create_text(
                float(middle[0]), float(middle[1]) - width_px / 2 - 10,
                text=f"Stair {float(stair.get('width_cm', 110)):g} cm",
                fill="#4f46e5", font=("Segoe UI", 9, "bold"), tags=stair_tags,
            )

        for deck in geometry.get("deck_slabs", []):
            points = deck.get("polygon", [])
            if len(points) >= 3:
                coords = [coordinate for point in points for coordinate in point]
                self.canvas.create_polygon(
                    *coords, fill=swatches.get(deck.get("material_id"), "#d6d3d1"),
                    outline="#475569", width=2,
                    tags=tags("deck", deck["id"]),
                )
        for beam in geometry.get("beams", []):
            start, end = beam.get("start", []), beam.get("end", [])
            if len(start) == 2 and len(end) == 2:
                self.canvas.create_line(
                    *start, *end, fill=swatches.get(beam.get("material_id"), "#64748b"),
                    width=max(3, min(20, float(beam.get("width_cm", 20)) * scale)),
                    tags=tags("beam", beam["id"]),
                )
        for pillar in geometry.get("pillars", []):
            position = pillar.get("position", [])
            if len(position) != 2:
                continue
            x, y = map(float, position)
            half_width = max(4, float(pillar.get("width_cm", 30)) * scale / 2)
            half_depth = max(4, float(pillar.get("depth_cm", 30)) * scale / 2)
            options = {
                "fill": swatches.get(pillar.get("material_id"), "#94a3b8"),
                "outline": "#334155", "width": 2,
                "tags": tags("pillar", pillar["id"]),
            }
            creator = self.canvas.create_oval if pillar.get("shape") == "round" else self.canvas.create_rectangle
            creator(x - half_width, y - half_depth, x + half_width, y + half_depth, **options)

        # Detected rooms have one overlay owner. Rebuild the live overlay after
        # canonical structures are drawn instead of creating an ungrouped copy here.
        self.refresh_detected_room_overlay()
        # Filled room overlays are recreated above earlier items. Keep load-bearing
        # members and stairs visible without raising deck fills over the room.
        self.canvas.tag_raise("parity_stair")
        self.canvas.tag_raise("parity_beam")
        self.canvas.tag_raise("parity_pillar")
        if not self.canvas.find_withtag("parity_floor_underlay"):
            self._draw_floor_underlay()

    def refresh_detected_room_overlay(self) -> None:
        """Recompute detected rooms from the LIVE canvas and redraw overlays.

        Runs the planar-graph face extraction on a fresh derived geometry
        (without mutating the persisted project state) so the user sees
        enclosures update in real time as walls/lines are drawn. The
        authoritative detected rooms are still written to v2 geometry on
        save via ``_derive_canvas_geometry``.
        """
        try:
            canvas_payload = self._serialize_canvas_v1()
        except Exception as exc:
            print(f"[Serializer] overlay snapshot failed: {exc}")
            return
        try:
            derived = self._derive_canvas_geometry(
                self.project_state.active_floor_id,
                canvas_payload,
                empty_geometry(),
            )
        except Exception as exc:
            print(f"[Serializer] overlay derive failed: {exc}")
            return
        rooms = [r for r in derived.get("rooms", []) if r.get("source_canvas_kind") == "detected_face"]
        # Overlay polygons are recreated on every detection pass, but boundary lines
        # persist. Remove their previous synthetic room tags before rebuilding the
        # current groups; otherwise edited room topology can select a stale group.
        try:
            for item in self.canvas.find_all():
                for tag in self.canvas.gettags(item):
                    if str(tag).startswith("parity_room_drag:"):
                        self.canvas.dtag(item, tag)
        except tk.TclError:
            pass
        if not rooms:
            try:
                self.canvas.delete("parity_detected_room")
            except tk.TclError:
                pass
            return
        vertices = {
            v.get("id"): v for v in derived.get("vertices", []) if isinstance(v, dict)
        }
        try:
            self.canvas.delete("parity_detected_room")
        except tk.TclError:
            pass
        floor_id = self.project_state.active_floor_id
        overrides = getattr(self, "_detected_room_overrides", {}) or {}
        # A room's id is built from its boundary vertex ids, and those change when
        # corners merge as rooms are patched together or pulled apart. Keying the
        # name/colour purely by id therefore loses the styling on the first snap, so
        # fall back to the last known centroid and re-key the override.

        for index, room in enumerate(rooms):
            boundary = list(room.get("boundary_vertex_ids", []))
            points = []
            for vid in boundary:
                v = vertices.get(vid)
                if not v:
                    break
                pos = v.get("position", [v.get("x", 0), v.get("y", 0)])
                if not isinstance(pos, (list, tuple)) or len(pos) != 2:
                    break
                points.extend((float(pos[0]), float(pos[1])))
            if len(points) < 6:
                continue
            # This overlay only exists to visualize enclosures drawn as loose lines.
            # A face derived from a real room rectangle or polygon shape is already
            # drawn and draggable by its own entity, so drawing an overlay on top of
            # it would steal the click and drag only the overlay + its label.
            poly_pts = [
                (points[i], points[i + 1]) for i in range(0, len(points) - 1, 2)
            ]
            # Skip faces that coincide with a real RoomEntity — those already have their
            # own label and fill from the entity itself; overlaying another label causes
            # the "duplicate room name" the user sees.
            face_bbox = (min(p[0] for p in poly_pts), min(p[1] for p in poly_pts),
                         max(p[0] for p in poly_pts), max(p[1] for p in poly_pts))
            skip = False
            for room_entity in getattr(self.tools, "room_entities_by_group_tag", {}).values():
                try:
                    rc = self.canvas.coords(getattr(room_entity, "rect_id", None))
                    if rc and len(rc) >= 4:
                        if (abs(rc[0] - face_bbox[0]) < 8 and abs(rc[1] - face_bbox[1]) < 8
                                and abs(rc[2] - face_bbox[2]) < 8 and abs(rc[3] - face_bbox[3]) < 8):
                            skip = True
                            break
                except Exception:
                    continue
            if skip:
                continue
            boundary_lines = self._boundary_line_items(room, derived, poly_pts)
            if not boundary_lines:
                continue
            # Apply user-assigned name + fill style (from "Lines → Room") so the
            # overlay survives the periodic re-detection triggered on every canvas
            # mutation (drag, click, wall erase, …) instead of being wiped.
            # A room's id is rebuilt from its geometry, so it changes when the room is
            # dragged or snapped and an id-keyed override would be lost (the "name/colour
            # vanished" report). The room's boundary WALL ITEMS (line_<uuid>) are stable
            # across a move, so recover the styling by wall signature and re-key it to the
            # room's current id when the id lookup misses.
            room_id = room.get("id")
            override = overrides.get(room_id) or {}
            wall_sig = self._detected_room_wall_signature(boundary_lines)
            if not override and wall_sig:
                recovered_key = self._match_override_by_walls(wall_sig, overrides)
                if recovered_key is not None:
                    override = overrides.pop(recovered_key)
            if override:
                override["_walls"] = sorted(wall_sig)  # keep signature current for next move
                overrides[room_id] = override
            label_text = str(
                override.get("label")
                or room.get("label")
                or f"Room {index + 1}"
            )
            fill_mode = str(override.get("fill_mode") or "")
            fill_color = override.get("fill_color") or ""
            if fill_mode == "filled" and fill_color:
                poly_fill = fill_color
                poly_outline = "black"
                poly_width = 2
            elif fill_mode == "transparent":
                poly_fill = ""
                poly_outline = "black"
                poly_width = 2
            elif fill_mode == "walls_only":
                poly_fill = ""
                poly_outline = "black"
                poly_width = 4
            else:
                poly_fill = ""
                poly_outline = ""
                poly_width = 1
            poly_id = self.canvas.create_polygon(
                *points, fill=poly_fill, outline=poly_outline, width=poly_width,
                tags=("parity_detected_room", f"entity:{room['id']}", f"floor:{floor_id}"),
            )
            cx = sum(points[0::2]) / (len(points) // 2)
            cy = sum(points[1::2]) / (len(points) // 2)
            label_id = self.canvas.create_text(
                cx, cy, text=label_text,
                fill="#0f172a", font=("Segoe UI", 9, "bold"),
                tags=("parity_detected_room", f"detected_room_label:{room['id']}", f"floor:{floor_id}"),
            )
            # Keep the label ABOVE the polygon so a colored fill never hides the
            # room name. (Tk z-order is creation order, so the label is already
            # above the polygon; tag_raise(label_id) makes sure it stays there
            # even after later stacking changes.)
            try:
                self.canvas.tag_raise(label_id)
            except tk.TclError:
                pass
            # Synthesize a draggable group that includes the polygon, the label,
            # and the committed line walls that form this room's boundary, so the
            # detected room can be moved as a unit (polygon + underlying walls)
            # and the colored fill no longer detaches from the boundary on drag.
            try:
                self._tag_detected_room_drag_group(
                    room.get("id"), poly_id, label_id, boundary_lines, poly_pts,
                )
            except Exception:
                pass



    def _detected_room_wall_signature(self, boundary_lines) -> frozenset:
        """The set of stable wall-group tags (line_<uuid>) forming this room's boundary.

        Unlike the room id (rebuilt from geometry, so it changes on every move), these wall
        item tags travel with the room, so they are a durable key for its name/colour.
        """
        tags = set()
        for item in boundary_lines or ():
            try:
                for t in self.canvas.gettags(item):
                    t_str = str(t)
                    if t_str.startswith("line_") and t_str not in ("line_label", "line_point"):
                        tags.add(t_str)
            except tk.TclError:
                continue
        return frozenset(tags)

    def _match_override_by_walls(self, wall_sig: frozenset, overrides: dict):
        """Key of the stored override whose remembered wall signature best matches `wall_sig`.

        Used only when the id lookup misses (the room moved/snapped and its id changed).
        Requires a majority of walls to coincide so an unrelated room is never adopted.
        Returns the matching key, or None.
        """
        best_key, best_overlap = None, 0
        for key, data in overrides.items():
            if not isinstance(data, dict):
                continue
            stored = set(data.get("_walls") or ())
            if not stored:
                continue
            overlap = len(stored & wall_sig)
            # Majority of BOTH sets must agree, so a shared wall between neighbours is
            # not enough to steal another room's styling.
            if overlap > best_overlap and overlap * 2 > len(stored) and overlap * 2 > len(wall_sig):
                best_key, best_overlap = key, overlap
        return best_key

    def _boundary_line_items(
        self, room: dict, derived: dict[str, Any],
        poly_pts: list[tuple[float, float]], tol: float = 6.0,
    ) -> set[int]:
        """Return the canvas LINE items that form ``room``'s boundary.

        Resolution is exact first: derived walls keep ``source_canvas_id`` from
        ``_serialize_shapes`` (``shape_<canvas-item-id>`` for fresh lines,
        ``source_shape:<id>`` after a reload), so grouping does not depend on
        tolerance or on which tags a wall happened to be created with. A geometric
        pass then catches lines lying on the outline that identity missed.

        An empty result means the face is not made of lines (a real room rectangle
        or polygon shape), and the caller must not draw an overlay for it.
        """
        boundary = set(room.get("boundary_vertex_ids", []))
        # Map each live line back to the token _serialize_shapes used for it, so both
        # freshly drawn lines (shape_<item>) and reloaded lines (source_shape:<id>)
        # resolve exactly.
        token_to_item: dict[str, int] = {}
        for item in self.canvas.find_all():
            try:
                if self.canvas.type(item) != "line":
                    continue
                tags = self.canvas.gettags(item)
            except tk.TclError:
                continue
            token = next(
                (str(t).split(":", 1)[1] for t in tags if str(t).startswith("source_shape:")),
                f"shape_{item}",
            )
            token_to_item[token] = item
        items: set[int] = set()
        for wall in derived.get("walls", []):
            if not isinstance(wall, dict):
                continue
            if wall.get("start_vertex_id") not in boundary or wall.get("end_vertex_id") not in boundary:
                continue
            item_id = token_to_item.get(str(wall.get("source_canvas_id") or ""))
            if item_id is not None:
                items.add(item_id)

        # Geometric pass catches lines identity missed (e.g. a rehydrated document).
        if len(poly_pts) >= 3:
            for line_item in self.canvas.find_withtag("line"):
                if line_item in items:
                    continue
                try:
                    if self.canvas.type(line_item) != "line":
                        continue
                    lc = self.canvas.coords(line_item)
                except tk.TclError:
                    continue
                if len(lc) < 4:
                    continue
                p0 = (float(lc[0]), float(lc[1]))
                p1 = (float(lc[2]), float(lc[3]))
                if _point_on_polygon_outline(p0, poly_pts, tol) and _point_on_polygon_outline(p1, poly_pts, tol):
                    items.add(line_item)

        return items

    def _tag_detected_room_drag_group(
        self, room_id: Any, poly_id: int, label_id: int,
        boundary_lines: set[int], poly_pts: list[tuple[float, float]],
        tol: float = 6.0,
    ) -> None:
        """Tag the detected-room polygon, label, and its boundary lines together so
        dragging the room moves the overlay AND the underlying lines as one unit
        (instead of the colored fill detaching from the boundary).
        """
        if room_id is None:
            return
        drag_tag = f"parity_room_drag:{room_id}"
        # Polygon + label.
        self.canvas.addtag_withtag(drag_tag, poly_id)
        self.canvas.addtag_withtag(drag_tag, label_id)
        # Boundary lines, each with its measurement label and endpoint marker.
        for item_id in boundary_lines:
            self._tag_line_group(drag_tag, item_id)
        if len(poly_pts) < 3:
            return

        # The Line tool also creates a `closed_shape` polygon when a loop closes. It is
        # drawn in the line colour directly over the walls, so if it is left behind the
        # room looks like its boundary detached. Move it with the room.
        for shape in self.canvas.find_withtag("closed_shape"):
            try:
                if self.canvas.type(shape) != "polygon":
                    continue
                coords = self.canvas.coords(shape)
            except tk.TclError:
                continue
            if len(coords) < 6:
                continue
            shape_pts = [
                (float(coords[i]), float(coords[i + 1]))
                for i in range(0, len(coords) - 1, 2)
            ]
            if not all(_point_on_polygon_outline(point, poly_pts, tol) for point in shape_pts):
                continue
            group_tag = next(
                (t for t in self.canvas.gettags(shape) if str(t).startswith("polygon_group_")),
                None,
            )
            for item in (self.canvas.find_withtag(group_tag) if group_tag else (shape,)):
                self.canvas.addtag_withtag(drag_tag, item)

    def _tag_line_group(self, drag_tag: str, line_item: int) -> None:
        """Tag a wall plus its measurement label and endpoint marker."""
        try:
            tags = self.canvas.gettags(line_item)
        except tk.TclError:
            return
        line_tag = next((t for t in tags if str(t).startswith("line_")), None)
        if line_tag:
            for item in self.canvas.find_withtag(line_tag):
                self.canvas.addtag_withtag(drag_tag, item)
        else:
            self.canvas.addtag_withtag(drag_tag, line_item)

    def _materialize_active_floor(self) -> None:
        document = self.project_state.snapshot()
        floor = next(item for item in document["floors"] if item["id"] == document["active_floor_id"])
        self.deserialize_layout(self._canvas_from_geometry(document, floor))
        self._draw_active_structures()

    def load_document(self, data: dict[str, Any], confirm: bool = True) -> bool:
        """Validate completely, then atomically replace project and active canvas."""
        candidate = validate_document(data)
        if confirm and not self._confirm_and_backup_current_layout():
            return False
        previous_project = self.project_state.snapshot()
        previous_canvas = self._serialize_canvas_v1()
        try:
            self.project_state.replace(candidate)
            self._materialize_active_floor()
        except Exception:
            self.project_state.replace(previous_project)
            try:
                self.deserialize_layout(previous_canvas)
            except Exception as restore_error:
                print(f"[Serializer] canvas rollback failed: {restore_error}")
            raise
        self.actions.undo_stack.clear()
        self.actions.redo_stack.clear()
        notify = getattr(self.actions, "notify_post_mutation", None)
        if callable(notify):
            notify()
        return True

    def load_from_file(self, file_path: str) -> bool:
        ext = str(os.path.splitext(str(file_path))[1] or "").lower()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                if ext == ".json":
                    layout_data = json.load(f)
                elif ext in (".yaml", ".yml"):
                    layout_data = yaml.safe_load(f)
                else:
                    raise ValueError("Unsupported layout file; supported extensions are .json, .yaml, and .yml")
            if not self.load_document(layout_data, confirm=True):
                return False
            self.current_layout_file = file_path
            show_message("info", "VastuCraft Pro", f"Layout loaded from:\n{file_path}")
            return True
        except Exception as e:
            show_message("error", "VastuCraft Pro", f"Failed to load layout:\n{e}")
            return False

    def _commit_project_change(self, mutation, *, materialize: bool = True):
        """Apply one floor/project mutation with canvas rollback and one history record."""
        self._snapshot_active_canvas()
        before = self.project_state.snapshot()
        previous_canvas = self._canvas_from_geometry(
            before, next(f for f in before["floors"] if f["id"] == before["active_floor_id"])
        )
        try:
            result = mutation(self.project_state.floor_manager)
            after = self.project_state.snapshot()
            if materialize:
                self._materialize_active_floor()
        except Exception:
            self.project_state.replace(before)
            if materialize:
                try:
                    self.deserialize_layout(previous_canvas)
                except Exception as restore_error:
                    print(f"[Serializer] project rollback failed: {restore_error}")
            raise
        if before != after:
            self.actions.log({"type": "project_snapshot", "before": before, "after": after})
        return result

    def add_floor(self, name="New Floor", elevation_cm=None):
        def mutation(manager):
            floor = manager.add(name, elevation_cm)
            manager.activate(floor["id"])
            return floor
        return self._commit_project_change(mutation)

    def duplicate_floor(self, floor_id=None, name=None, elevation_cm=None):
        def mutation(manager):
            floor = manager.duplicate(floor_id, name, elevation_cm)
            manager.activate(floor["id"])
            return floor
        return self._commit_project_change(mutation)

    def activate_floor(self, floor_id):
        if floor_id == self.project_state.active_floor_id:
            return self.project_state.active_floor
        return self._commit_project_change(lambda manager: manager.activate(floor_id))

    def rename_floor(self, floor_id, name):
        return self._commit_project_change(lambda manager: manager.rename(floor_id, name), materialize=False)

    def set_floor_elevation(self, floor_id, elevation_cm):
        return self._commit_project_change(
            lambda manager: manager.set_elevation(floor_id, float(elevation_cm))
        )

    def delete_floor(self, floor_id):
        return self._commit_project_change(lambda manager: manager.delete(floor_id))

    def set_sun_settings(self, *, time_hours=None, direction_override=None, azimuth_deg=None):
        before = self.project_state.snapshot()
        settings = self.project_state.sun_settings
        if time_hours is not None:
            settings["time_hours"] = float(time_hours)
        if direction_override is not None:
            settings["direction_override"] = bool(direction_override)
        if azimuth_deg is not None:
            settings["azimuth_deg"] = float(azimuth_deg) % 360.0
        self.project_state.replace_sun_settings(settings)
        after = self.project_state.snapshot()
        if before != after:
            self.actions.log({"type": "project_snapshot", "before": before, "after": after})
        return self.project_state.sun_settings

    def apply_project_snapshot(self, document: dict[str, Any]) -> None:
        """Apply history state without creating another history entry."""
        candidate = validate_document(document)
        previous_project = self.project_state.snapshot()
        previous_canvas = self._serialize_canvas_v1()
        try:
            self.project_state.replace(candidate)
            self._materialize_active_floor()
        except Exception:
            self.project_state.replace(previous_project)
            try:
                self.deserialize_layout(previous_canvas)
            except Exception as restore_error:
                print(f"[Serializer] history rollback failed: {restore_error}")
            raise

    def load_from_dialog(self) -> bool:
        file_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[
                ("Layout files", "*.json *.yaml *.yml"),
                ("JSON files", "*.json"),
                ("YAML files", "*.yaml *.yml"),
                ("All files", "*.*"),
            ],
            title="Load Layout",
        )
        if not file_path:
            return False
        return bool(self.load_from_file(file_path))

    # NOTE: the 3D-floor-plan bridge (layout_2d_to_3d.py / layout_3d_adapter.py /
    # layout_3d_to_2d.py and the "Import 3D" dialog) was removed. Home Quest now imports
    # this app's NATIVE layout JSON directly, so no .hq.json conversion step exists.

    # def load_from_json(self):
    #     """Load a layout from a JSON file."""
    #     file_path = filedialog.askopenfilename(
    #         defaultextension=".json",
    #         filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    #         title="Load Layout from JSON"
    #     )
        
    #     if file_path:
    #         try:
    #             with open(file_path, 'r') as f:
    #                 layout_data = json.load(f)
    #         self.deserialize_layout(layout_data)
    #         self.current_layout_file = file_path
   
    #     return False

    def _recreate_duplicated_layout(self, data, action=None):
        """Recreate one transformed layout copy and capture it as one undo unit."""
        data = copy.deepcopy(data)
        before_items = set(self.canvas.find_all())
        before_furniture = {id(item) for item in self.tools.image_furniture_items}
        for shape in data["shapes"]:
            self._recreate_shape(shape)
        for room in data["rooms"]:
            self._recreate_room(room)
        for furniture in data["furniture"]:
            self._recreate_furniture(furniture)
        for window in data.get("windows", []):
            self.tools.load_window_object(window)
        for text in data["text"]:
            self._recreate_text(text)
        self.tools.rebuild_polygon_room_mapping()
        payload = {
            "item_ids": list(set(self.canvas.find_all()) - before_items),
            "furniture_ids": [
                item.image_id for item in self.tools.image_furniture_items
                if id(item) not in before_furniture
            ],
            "room_tags": [room.get("group_tag") for room in data["rooms"] if room.get("group_tag")],
            "window_ids": [window.get("id") for window in data.get("windows", []) if window.get("id")],
            "polygon_tags": list({
                tag for shape in data["shapes"] for tag in shape.get("tags", [])
                if str(tag).startswith("polygon_group_")
            }),
            "line_tags": list({
                tag for shape in data["shapes"] for tag in shape.get("tags", [])
                if str(tag).startswith("line_")
            }),
        }
        if action is not None:
            action.update(payload)
            self.tools.select_entire_layout(payload["item_ids"], state_scope=action)
        return payload

    def _remove_duplicated_layout(self, action):
        """Remove only the copied layout, preserving original canvas IDs and history."""
        if getattr(self.tools, "_entire_layout_state_scope", None) is action:
            self.tools.finish_entire_layout_move()
        copied_items = set(action.get("item_ids", []))
        copied_furniture = set(action.get("furniture_ids", []))
        if getattr(self.tools, "selected_furniture_obj", None) and getattr(self.tools.selected_furniture_obj, "image_id", None) in copied_furniture:
            self.tools.clear_furniture_selection()
        for item in list(self.tools.image_furniture_items):
            if getattr(item, "image_id", None) in copied_furniture:
                item.delete_handles()
                item.delete_highlight()
                self.tools.image_furniture_items.remove(item)
        for tag in action.get("room_tags", []):
            self.tools.room_entities_by_group_tag.pop(tag, None)
            try:
                self.tools._door_cut_registry.clear_room(tag)
            except Exception:
                pass
            try:
                self.tools.dimension_drawer.clear_dimensions_for_group(f"{tag}__dims")
            except Exception:
                pass
        for line_tag in action.get("line_tags", []):
            self.tools.line_metadata.pop(line_tag, None)
        window_ids = set(action.get("window_ids", []))
        self.tools.windows[:] = [window for window in self.tools.windows if window.get("id") not in window_ids]
        for owner_id, flooring in list(self.tools.room_flooring_images.items()):
            if owner_id in copied_items or flooring.get("image_id") in copied_items or flooring.get("border_id") in copied_items:
                self.tools.room_flooring_images.pop(owner_id, None)
        for group_tag in action.get("polygon_tags", []):
            self.tools._polygon_baseline_coords_by_group.pop(group_tag, None)
            try:
                self.tools.dimension_drawer.clear_dimensions_for_group(f"{group_tag}__dims")
            except Exception:
                pass
        for item_id in copied_items:
            try:
                self.canvas.delete(item_id)
            except Exception:
                pass
        self.tools.rebuild_polygon_room_mapping()

    def duplicate_layout(self):
        """Duplicate the complete current plan with a small visible offset."""
        self.tools.finish_entire_layout_move()
        data = copy.deepcopy(self._serialize_canvas_v1())
        offset = 40.0
        real_offset = offset / (self.model.grid_spacing * self.model.zoom_level) * self.model.unit_scale.get(self.model.unit, 1.0)
        tag_map = {}
        next_room = int(getattr(self.model, "room_counter", 0))
        for room in data["rooms"]:
            old_tag = room.get("group_tag")
            new_tag = f"room_group_{next_room}"
            next_room += 1
            if old_tag:
                tag_map[old_tag] = new_tag
            room["group_tag"], room["group_id"] = new_tag, next_room - 1
            for key in ("x0", "x1", "x"):
                if key in room:
                    room[key] = float(room[key]) + offset
            for key in ("y0", "y1", "y"):
                if key in room:
                    room[key] = float(room[key]) + offset
            for intervals in (room.get("wall_erased_regions") or {}).values():
                for interval in intervals:
                    interval[0] += offset / self.model.zoom_level
                    interval[1] += offset / self.model.zoom_level
        self.model.room_counter = next_room
        for shape in data["shapes"]:
            for tag in shape.get("tags", []):
                if str(tag).startswith("polygon_group_") and tag not in tag_map:
                    tag_map[tag] = f"polygon_group_{uuid.uuid4().hex[:8]}"
        for shape in data["shapes"]:
            shape["points"] = [[float(x) + offset, float(y) + offset] for x, y in shape["points"]]
            shape["tags"] = [tag_map.get(tag, tag) for tag in shape.get("tags", []) if not str(tag).startswith("line_")]
            if shape.get("type") == "line":
                shape["tags"].append(f"line_{uuid.uuid4().hex[:8]}")
        for furniture in data["furniture"]:
            furniture["x"], furniture["y"] = float(furniture["x"]) + offset, float(furniture["y"]) + offset
        for text in data["text"]:
            if "x_real" in text:
                text["x_real"], text["y_real"] = float(text["x_real"]) + real_offset, float(text["y_real"]) + real_offset
            else:
                text["x"], text["y"] = float(text.get("x", 0)) + offset, float(text.get("y", 0)) + offset
        for window in data.get("windows", []):
            window["id"] = f"window_{uuid.uuid4().hex[:10]}"
            window["room_group_tag"] = tag_map.get(window["room_group_tag"], window["room_group_tag"])
            window["start"] += offset / self.model.zoom_level
            window["end"] += offset / self.model.zoom_level
        action = {
            "type": "duplicate_layout",
            "data": copy.deepcopy(data),
        }
        self._recreate_duplicated_layout(data, action)
        self.actions.log(action)
        show_message("info", "Duplicate Layout", f"A copy of the full plan, including {len(data['furniture'])} furniture item(s), was created 40 px down-right.")
        return True

    def save_to_yaml(self):
        layout = self.serialize_layout()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            title="Save Layout as YAML",
        )
        if not file_path:
            return False
        try:
            atomic_write_document(layout, file_path)
            self.current_layout_file = file_path
            show_message("info", "VastuCraft Pro", f"Layout saved to:\n{file_path}")
            return True
        except Exception as e:
            show_message("error", "VastuCraft Pro", f"Failed to save layout:\n{e}")
            return False

    def load_from_yaml(self):
        file_path = filedialog.askopenfilename(
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
            title="Load Layout from YAML",
        )
        return bool(file_path and self.load_from_file(file_path))

    def auto_save_layout(self):
        # """Auto-save the current layout."""
        if not self.auto_save_enabled:
            return False
        
        # Generate timestamp filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"autosave_{timestamp}.json"
        file_path = os.path.join(self.default_save_dir, filename)
        
        layout = self.serialize_layout()
        try:
            atomic_write_document(layout, file_path)
            print(f"Auto-saved to: {file_path}")
            # Keep autosave quiet in UI to avoid spam; rely on status logs
            return True
        except Exception as e:
            print(f"Auto-save error: {e}")
            return False

    def _serialize_metadata(self):
        """Serialize the coordinate contract used by external importers."""
        unit = str(getattr(self.model, "unit", "m"))
        unit_scale = float((getattr(self.model, "unit_scale", {}) or {}).get(unit, 1.0) or 1.0)
        return {
            "project_name": "Floor Plan",
            "description": "Auto-generated layout",
            "created": datetime.datetime.now().isoformat(),
            "modified": datetime.datetime.now().isoformat(),
            "unit": unit,
            "unit_scale": unit_scale,
            "grid_spacing": getattr(self.model, "grid_spacing", 20),
            "canvas_width": self.canvas.winfo_width(),
            "canvas_height": self.canvas.winfo_height(),
            "zoom_level": getattr(self.model, "zoom_level", 1.0),
            "wall_height_cm": 280,
            "grid_visible": getattr(self.view, "grid_visible", True),
        }

    def _serialize_compass(self) -> Dict[str, Any] | None:
        """Serialize north in the web app's clockwise-from-up convention."""
        direction = getattr(self.tools, "current_compass_direction", None)
        has_canvas_compass = False
        has_oriented_layout = False

        for item in self.canvas.find_all():
            tags = self.canvas.gettags(item) or ()
            if "vastu_polygon" in tags or "vastu_oriented_layout" in tags:
                has_oriented_layout = True
            if self.canvas.type(item) != "text" or "compass" not in tags:
                continue
            has_canvas_compass = True
            if direction is None:
                try:
                    content = self.canvas.itemcget(item, "text")
                    if content.startswith("North → "):
                        direction = content.split("→", 1)[-1].strip().upper()
                except (tk.TclError, IndexError):
                    pass

        valid = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        direction_to_deg = {name: index * 45 for index, name in enumerate(valid)}
        if direction in valid:
            return {"direction": direction, "north_deg_clockwise": direction_to_deg[direction]}

        if has_oriented_layout:
            # Python stores anti-clockwise degrees; Home Quest stores clockwise degrees.
            python_deg = float(getattr(self.tools, "vastu_north_deg", 0.0) or 0.0)
            return {"north_deg_clockwise": (-python_deg) % 360.0}

        if has_canvas_compass:
            return {"direction": "N", "north_deg_clockwise": 0.0}
        return None

    def _deserialize_compass(self, compass_data: Dict[str, Any]) -> None:
        """Restore both the visible 8-point compass and exact Vastu north angle."""
        valid = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        clockwise = compass_data.get("north_deg_clockwise")
        if clockwise is not None:
            clockwise = float(clockwise) % 360.0
            direction = valid[int(round(clockwise / 45.0)) % len(valid)]
            self.tools.draw_compass(direction)
            self.tools.vastu_north_deg = (-clockwise) % 360.0
            return

        direction = str(compass_data.get("direction", "N")).upper()
        if direction not in valid:
            direction = "N"
        self.tools.draw_compass(direction)

    def _sync_compass_from_canvas(self) -> None:
        """Backward compat: sync compass from old-format shapes/text then redraw properly."""
        direction = None
        to_delete = []
        for item in self.canvas.find_all():
            tags = self.canvas.gettags(item) or ()
            if "compass" not in tags:
                continue
            to_delete.append(item)
            if direction is None and self.canvas.type(item) == "text":
                try:
                    content = self.canvas.itemcget(item, "text")
                    if content.startswith("North → "):
                        direction = content.split("→", 1)[-1].strip().upper()
                except (tk.TclError, IndexError):
                    pass
        for item in to_delete:
            self.canvas.delete(item)
        if direction:
            valid = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
            if direction in valid:
                self.tools.draw_compass(direction)

    def _serialize_room_wall_erased_regions(
        self, room, x0: float, y0: float, x1: float, y1: float
    ) -> Dict[str, List[List[float]]] | None:
        """
        Capture erased/gap regions for walls_only room walls.
        Returns {wall_side: [[start, end], ...]} in wall-axis coords.
        Empty list = no erasures; [[min, max]] = full wall erased.
        """
        try:
            group_tag = getattr(room, "group_tag", None)
            if not group_tag:
                return None
            try:
                t = float(room._wall_thickness_pixels())
            except Exception:
                t = 10.0
            eps = 2.0

            def _merge_intervals(intervals: List[tuple]) -> List[tuple]:
                if not intervals:
                    return []
                data = sorted([(min(a, b), max(a, b)) for a, b in intervals])
                merged = [data[0]]
                for s, e in data[1:]:
                    if s <= merged[-1][1] + eps:
                        merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                    else:
                        merged.append((s, e))
                return merged

            def _gaps_from_segments(seg_spans: List[tuple], full_min: float, full_max: float) -> List[List[float]]:
                if not seg_spans:
                    return [[full_min, full_max]]
                merged = _merge_intervals(seg_spans)
                gaps = []
                cur = full_min
                for s, e in merged:
                    if s > cur + eps:
                        gaps.append([cur, s])
                    cur = max(cur, e)
                if cur < full_max - eps:
                    gaps.append([cur, full_max])
                return gaps

            result: Dict[str, List[List[float]]] = {}
            wall_sides = {
                "top": (x0, x1, y0, y0 + t, 0),
                "bottom": (x0, x1, y1 - t, y1, 0),
                "left": (y0 + t, y1 - t, x0, x0 + t, 1),
                "right": (y0 + t, y1 - t, x1 - t, x1, 1),
            }

            for side, (axis_min, axis_max, perp_min, perp_max, use_y) in wall_sides.items():
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
                            if abs(ry0 - perp_min) < eps and abs(ry1 - perp_max) < eps:
                                seg_spans.append((min(rx0, rx1), max(rx0, rx1)))
                            elif abs(ry1 - perp_min) < eps and abs(ry0 - perp_max) < eps:
                                seg_spans.append((min(rx0, rx1), max(rx0, rx1)))
                        else:
                            if abs(rx0 - perp_min) < eps and abs(rx1 - perp_max) < eps:
                                seg_spans.append((min(ry0, ry1), max(ry0, ry1)))
                            elif abs(rx1 - perp_min) < eps and abs(rx0 - perp_max) < eps:
                                seg_spans.append((min(ry0, ry1), max(ry0, ry1)))
                    except Exception:
                        continue
                gaps = _gaps_from_segments(seg_spans, axis_min, axis_max)
                if gaps:
                    result[side] = gaps
        except Exception as e:
            print(f"[Serializer] _serialize_room_wall_erased_regions: {e}")
            return None
        return result if result else None

    def _serialize_rooms(self):
        """Serialize rooms (including name + style) in a runtime-safe way."""
        rooms = []

        room_map = getattr(self.tools, "room_entities_by_group_tag", None)
        if isinstance(room_map, dict) and room_map:
            for group_tag, room in room_map.items():
                rect_id = getattr(room, "rect_id", None)
                if not rect_id:
                    continue
                coords = self.canvas.coords(rect_id)
                if not coords or len(coords) < 4:
                    continue
                x0, y0, x1, y1 = coords[0], coords[1], coords[2], coords[3]
                group_id = None
                if isinstance(group_tag, str) and group_tag.startswith("room_group_"):
                    try:
                        group_id = int(group_tag.split("_")[-1])
                    except Exception:
                        group_id = None

                room_data = {
                    "id": f"room_{group_tag}",
                    "name": getattr(room, "name", "Room"),
                    "group_tag": group_tag,
                    "group_id": group_id,
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "width": x1 - x0,
                    "height": y1 - y0,
                    "width_real": getattr(room, "wlabel", None),
                    "height_real": getattr(room, "hlabel", None),
                    "fill_mode": getattr(room, "fill_mode", "filled"),
                    "fill_color": getattr(room, "fill_color", self.canvas.itemcget(rect_id, "fill")),
                    "outline_color": self.canvas.itemcget(rect_id, "outline") or "black",
                    "wall_thickness_ft": getattr(room, "wall_thickness_ft", 0.2),
                }

                # Attach flooring info if present (keyed by room rect_id)
                if hasattr(self.tools, "room_flooring_images") and rect_id in getattr(self.tools, "room_flooring_images", {}):
                    fd = self.tools.room_flooring_images.get(rect_id, {})
                    image_path_raw = fd.get("image_path", "")
                    room_data["flooring"] = {
                        # Store a portable path so layouts move between
                        # Windows/macOS/Linux without breaking flooring.
                        "image_path": self._to_portable_path(image_path_raw),
                        "has_flooring": True,
                        "flooring_type": self._get_flooring_type_from_path(image_path_raw),
                    }
                else:
                    room_data["flooring"] = {"has_flooring": False}

                # Serialize wall erased regions for this room (preserves door/wall cuts)
                wall_erased = self._serialize_room_wall_erased_regions(room, x0, y0, x1, y1)
                if wall_erased:
                    room_data["wall_erased_regions"] = wall_erased

                rooms.append(room_data)
            return rooms

        # Fallback (older runtime): serialize by scanning canvas rectangles with room_group_* tag
        for item in self.canvas.find_withtag("room"):
            try:
                if self.canvas.type(item) != "rectangle":
                    continue
            except Exception:
                continue
            tags = self.canvas.gettags(item) or ()
            group_tag = next((t for t in tags if isinstance(t, str) and t.startswith("room_group_")), None)
            if not group_tag:
                continue
            coords = self.canvas.coords(item)
            if not coords or len(coords) < 4:
                continue
            room_data = {
                "id": f"room_{group_tag}",
                "name": "Room",
                "group_tag": group_tag,
                "x0": coords[0],
                "y0": coords[1],
                "x1": coords[2],
                "y1": coords[3],
                "width": coords[2] - coords[0],
                "height": coords[3] - coords[1],
                "fill_color": self.canvas.itemcget(item, "fill"),
                "outline_color": self.canvas.itemcget(item, "outline"),
            }
            if hasattr(self.tools, "room_flooring_images") and item in getattr(self.tools, "room_flooring_images", {}):
                fd = self.tools.room_flooring_images.get(item, {})
                image_path_raw = fd.get("image_path", "")
                room_data["flooring"] = {
                    "image_path": self._to_portable_path(image_path_raw),
                    "has_flooring": True,
                    "flooring_type": self._get_flooring_type_from_path(image_path_raw),
                }
            else:
                room_data["flooring"] = {"has_flooring": False}
            rooms.append(room_data)
        return rooms



    # def _get_flooring_type_from_path(self, image_path):
    # # """Extract flooring type from image path."""
    #     if not image_path:
    #         return "none"
        
    #     filename = os.path.basename(image_path).lower()
    #     if "wood" in filename:
    #         return "wood"
    #     elif "tile" in filename:
    #         return "tile"
    #     elif "marble" in filename:
    #         return "marble"
    #     elif "garden" in filename:
    #         return "garden"
    #     else:
    #         return "unknown"
    def _get_flooring_type_from_path(self, image_path):
    # """Extract flooring type from image path."""
        import os
        if not image_path:
            return "none"
        fname = os.path.basename(image_path).lower()
        if "wood"   in fname: return "wood"
        if "tile"   in fname: return "tile"
        if "marble" in fname: return "marble"
        if "garden" in fname: return "garden"
        return "unknown"







    def _serialize_wall_openings(self):
        """Serialize windows/ventilation placed on hand-drawn walls for the web 3D importer.

        Centre is recomputed from the symbol's live canvas items so a dragged opening
        exports at its current position; width is the physical span in cm; `kind`/`type`
        map to the web opening catalog.
        """
        out = []
        for opening in getattr(self.tools, "wall_openings", []) or []:
            xs, ys = [], []
            for item in opening.get("item_ids", []) or []:
                try:
                    coords = self.canvas.coords(item)
                except Exception:
                    continue
                xs.extend(coords[0::2])
                ys.extend(coords[1::2])
            if xs and ys:
                cx = (min(xs) + max(xs)) / 2.0
                cy = (min(ys) + max(ys)) / 2.0
            else:
                cx, cy = opening.get("cx", 0.0), opening.get("cy", 0.0)
            out.append({
                "id": opening.get("id"),
                "type": opening.get("otype", "window"),
                "kind": opening.get("kind_id", "window-standard"),
                "x": float(cx), "y": float(cy),
                "width_cm": float(opening.get("width_cm", 90.0)),
            })
        return out

    def _serialize_furniture(self):
        furniture = []
        items = list(getattr(self.tools, "image_furniture_items", []) or [])
        orphans = []
        for idx, f in enumerate(items):
            try:
                if not hasattr(f, "image_id") or not hasattr(f, "image_path"):
                    continue
                if hasattr(self.tools, "_item_exists") and not self.tools._item_exists(f.image_id):
                    orphans.append(f)
                    continue
                coords = self.canvas.coords(f.image_id)
                if not coords or len(coords) < 2:
                    continue
                x, y = float(coords[0]), float(coords[1])

                image_filename = os.path.basename(f.image_path)
                image_name = os.path.splitext(image_filename)[0]

                furniture_data = {
                    "id": f"furniture_{idx}",
                    "image_path": f.image_path,
                    "image_filename": image_filename,
                    "image_name": image_name,
                    "x": x,
                    "y": y,
                    "scale": getattr(f, "scale", 1.0),
                    "angle": getattr(f, "angle", 0),
                    "initial_angle": getattr(f, "initial_angle", getattr(f, "angle", 0)),
                    "real_size_ft": list(f.real_size_ft) if getattr(f, "real_size_ft", None) else None,
                    "target_size": list(f.target_size) if getattr(f, "target_size", None) else None,
                }
                furniture.append(furniture_data)
            except (tk.TclError, ValueError, TypeError, IndexError) as e:
                orphans.append(f)
                continue
        for o in orphans:
            try:
                if o in self.tools.image_furniture_items:
                    self.tools.image_furniture_items.remove(o)
            except Exception:
                pass
        return furniture

    def _serialize_shapes(self):
    # """Serialize shape data."""
        shapes = []
        for item in self.canvas.find_all():
            tags = self.canvas.gettags(item)
            # Skip helper/overlay items that should not be persisted
            if (
                "grid" in tags
                or any(str(tag).startswith("guideline") for tag in tags)  # pooled snap guides are never walls
                or "room" in tags
                or "furniture" in tags
                or "flooring" in tags
                or "flooring_border" in tags
                or "dimension_item" in tags  # polygon edge dimensions are re-computed on load
                or "compass" in tags  # compass is serialized separately
                or "window_object" in tags  # semantic windows are serialized separately
                or "window_symbol" in tags  # inferred legacy window visuals are regenerated
                or "opening_symbol" in tags  # vector openings are serialized separately; never room walls
                or "furniture_resize_handle" in tags
                or "furniture_selection_highlight" in tags
                or "entire_layout_outline" in tags
                or "selection_highlight" in tags
                or "active_preview" in tags
                or "active_snap_indicator" in tags
                or "parity_structure" in tags  # canonical structures are stored separately
                or "parity_capture" in tags  # unfinished one-shot tool preview
                or "parity_finish_preview" in tags  # canonical finish visualization
                or "parity_detected_room" in tags  # live detected-room overlays (recomputed on the fly)
            ):
                continue

            item_type = self.canvas.type(item)
            coords = self.canvas.coords(item)
            if not coords:
                continue

            points = [[coords[i], coords[i + 1]] for i in range(0, len(coords), 2)]

            # Safely get width
            try:
                width_str = self.canvas.itemcget(item, "width")
                width = float(width_str) if width_str else 1.0
            except (ValueError, TypeError, tk.TclError):
                width = 1.0

            # Safely get colors based on item type
            outline_color = ""
            fill_color = ""

            try:
                if item_type == "line":
                    outline_color = self.canvas.itemcget(item, "fill")
                elif item_type in ["rectangle", "oval", "polygon"]:
                    outline_color = self.canvas.itemcget(item, "outline")
                elif item_type == "text":
                    outline_color = self.canvas.itemcget(item, "fill")
            except tk.TclError:
                outline_color = "black"

            try:
                if item_type in ["rectangle", "oval", "polygon"]:
                    fill_color = self.canvas.itemcget(item, "fill")
            except tk.TclError:
                fill_color = ""

            # Use fill color as outline for items that don't have outline
            if not outline_color and fill_color:
                outline_color = fill_color
            elif not outline_color:
                outline_color = "black"

            dash = ""
            if item_type in ("line", "rectangle", "oval", "polygon"):
                try:
                    dash = self.canvas.itemcget(item, "dash") or ""
                except tk.TclError:
                    dash = ""
            style = "dashed" if dash else ("bold" if width >= 4 else "solid")
            stable_shape_id = next(
                (tag.split(":", 1)[1] for tag in tags if str(tag).startswith("source_shape:")),
                f"shape_{item}",
            )
            shape_entry = {
                "id": stable_shape_id,
                "type": item_type,
                "points": points,
                "outline_color": outline_color,
                "fill_color": fill_color,
                "width": width,
                "style": style,
                "dash": dash,
                "tags": list(tags) if tags else [],
            }
            if item_type == "line":
                try:
                    shape_entry["arrow"] = self.canvas.itemcget(item, "arrow")
                except tk.TclError:
                    shape_entry["arrow"] = "none"
            # Attach polygon flooring if present
            if (
                item_type == "polygon"
                and hasattr(self.tools, "room_flooring_images")
                and item in getattr(self.tools, "room_flooring_images", {})
            ):
                fd = self.tools.room_flooring_images.get(item, {})
                image_path_raw = fd.get("image_path", "")
                shape_entry["flooring"] = {
                    "image_path": self._to_portable_path(image_path_raw),
                    "has_flooring": True,
                    "flooring_type": self._get_flooring_type_from_path(image_path_raw),
                }
            elif item_type == "polygon":
                shape_entry["flooring"] = {"has_flooring": False}
            shapes.append(shape_entry)
        return shapes



    def _serialize_text(self):
    # """Serialize text data."""
        texts = []
        for item in self.canvas.find_all():
            if self.canvas.type(item) != "text":
                continue

            tags = self.canvas.gettags(item) or ()

            # Skip auto-generated labels / dimension annotations which are
            # recreated from rooms and shapes on load.
            if any(
                t in (
                    "grid",
                    "room_label",
                    "dimension_item",
                    "dimension_label",
                    "dimension_text_bg",
                    "room_dimensions",
                    "compass",
                )
                for t in tags
            ):
                continue

            coords = self.canvas.coords(item)

            # Safely get text properties
            try:
                content = self.canvas.itemcget(item, "text")
            except tk.TclError:
                content = ""

            try:
                font = self.canvas.itemcget(item, "font")
            except tk.TclError:
                font = "Arial 10"

            try:
                color = self.canvas.itemcget(item, "fill")
            except tk.TclError:
                color = "black"

            if coords and content:
                # Store in model (real) coordinates for zoom-independent save/load
                px, py = float(coords[0]), float(coords[1])
                real_x, real_y = self.view.pixel_to_real(px, py)
                texts.append(
                    {
                        "id": f"text_{item}",
                        "content": content,
                        "x": px,
                        "y": py,
                        "x_real": real_x,
                        "y_real": real_y,
                        "font": font,
                        "color": color,
                        "tags": list(tags),
                    }
                )
        return texts


    def _clear_canvas(self):
        # """Clear all canvas items except grid."""
        for item in self.canvas.find_all():
            if "grid" not in self.canvas.gettags(item):
                self.canvas.delete(item)
        # Clear furniture list
        self.tools.image_furniture_items.clear()

    def _deserialize_metadata(self, metadata):
        # """Apply metadata to the model."""
        if hasattr(self.model, 'unit'):
            self.model.unit = metadata.get("unit", "m")
        if hasattr(self.model, 'grid_spacing'):
            self.model.grid_spacing = metadata.get("grid_spacing", 20)
        if hasattr(self.model, 'zoom_level'):
            self.model.zoom_level = metadata.get("zoom_level", 1.0)
        
        if "grid_visible" in metadata:
            try:
                visible = bool(metadata["grid_visible"])
                if visible:
                    self.view.grid_visible = True
                    self.view.draw_grid()
                else:
                    self.view.clear_grid()
            except Exception:
                pass
    def export_to_dict(self) -> Dict[str, Any]:
        c = self.view.canvas
        items: List[Dict[str, Any]] = []

        for item_id in c.find_all():
            tags = c.gettags(item_id) or ()
            if "grid" in tags:
                continue

            t = c.type(item_id)
            entry: Dict[str, Any] = {"type": t, "tags": list(tags)}

            # geometry
            try:
                entry["coords"] = c.coords(item_id)
            except Exception:
                entry["coords"] = []

            # vector styling
            if t in ("line", "oval", "rectangle", "polygon", "text"):
                opts = {}
                for k in ("fill", "outline", "width", "dash", "text", "font"):
                    try:
                        v = c.itemcget(item_id, k)
                        if v not in ("", None):
                            opts[k] = v
                    except Exception:
                        pass
                entry["options"] = opts

            # images: furniture or flooring
            if t == "image":
                tags_set = set(tags)

                # ---- Furniture (match runtime object by image_id)
                furn_info = None
                try:
                    for f in getattr(self.tools, "image_furniture_items", []):
                        if getattr(f, "image_id", None) == item_id:
                            furn_info = {
                                "image_path": getattr(f, "image_path", None),
                                "scale": getattr(f, "scale", 1.0),
                                "angle": getattr(f, "angle", 0),
                            }
                            break
                except Exception:
                    pass
                if furn_info:
                    entry["furniture"] = furn_info

                # ---- Flooring (tagged 'flooring') — store path/size/owner rect id if known
                if "flooring" in tags_set:
                    image_path = None
                    width = None
                    height = None
                    owner_rect_id = None

                    try:
                        for k, data in getattr(self.tools, "room_flooring_images", {}).items():
                            if data.get("image_id") == item_id:
                                image_path = data.get("image_path")
                                if isinstance(k, int):
                                    owner_rect_id = k
                                break
                        bbox = c.bbox(item_id)
                        if bbox:
                            x0, y0, x1, y1 = bbox
                            width, height = int(x1 - x0), int(y1 - y0)
                    except Exception:
                        pass

                    entry["flooring"] = {
                        "image_path": image_path,
                        "width": width,
                        "height": height,
                        "owner_rect_id": owner_rect_id,
                    }

            items.append(entry)

        meta = {
            "unit": getattr(self.model, "unit", "feet"),
            "grid_spacing": getattr(self.model, "grid_spacing", 20),
            "zoom_level": getattr(self.model, "zoom_level", 1.0),
            "canvas_width": self.view.canvas.winfo_width(),
            "canvas_height": self.view.canvas.winfo_height(),
        }
        return {"meta": meta, "items": items}

    # -------------------------------------------------------------------------
    # Import
    # -------------------------------------------------------------------------
    def import_from_dict(self, payload: Dict[str, Any]) -> None:
        c = self.view.canvas

        # Clear non-grid
        for iid in c.find_all():
            if "grid" not in c.gettags(iid):
                c.delete(iid)

        # Reset containers
        self.tools.image_furniture_items = []
        self.tools.room_flooring_images = {}

        # Restore meta
        meta = payload.get("meta", {})
        if hasattr(self.model, "set_unit"):
            self.model.set_unit(meta.get("unit", getattr(self.model, "unit", "feet")))
        if "grid_spacing" in meta:
            setattr(self.model, "grid_spacing", meta["grid_spacing"])
        if "zoom_level" in meta:
            setattr(self.model, "zoom_level", meta["zoom_level"])
        if hasattr(self.view, "draw_grid"):
            self.view.draw_grid()

        # 0) Build a mapping old_group_tag -> new unique group tag (avoid collisions)
        old_to_new_group: Dict[str, str] = {}
        for it in payload.get("items", []):
            for tg in it.get("tags", []):
                if isinstance(tg, str) and tg.startswith("room_group_"):
                    if tg not in old_to_new_group:
                        old_to_new_group[tg] = f"room_group_{uuid.uuid4().hex[:8]}"

        def remap_tags(tags_tuple):
            # replace any old group tag with the new one
            out = []
            for tg in tags_tuple:
                if isinstance(tg, str) and tg in old_to_new_group:
                    out.append(old_to_new_group[tg])
                else:
                    out.append(tg)
            return tuple(out)

        # 1) PASS: create vectors first; collect mapping: new_group_tag -> rect_id
        new_group_to_rect: Dict[str, int] = {}

        for it in payload.get("items", []):
            t = it.get("type")
            if t not in ("line", "oval", "rectangle", "polygon", "text"):
                continue

            coords = it.get("coords", [])
            tags = remap_tags(tuple(it.get("tags", [])))
            opts = it.get("options", {})

            try:
                if t == "line":
                    c.create_line(*coords, **opts, tags=tags)
                elif t == "oval":
                    c.create_oval(*coords, **opts, tags=tags)
                elif t == "rectangle":
                    # Check if this is a walls_only room rectangle
                    # Walls_only rooms have 4 small wall rectangles + 1 large invisible hit rectangle
                    # If we see multiple rectangles with same room_group, check if this is the large one
                    is_large_room_rect = False
                    room_group_tag = None
                    for tg in tags:
                        if isinstance(tg, str) and tg.startswith("room_group_"):
                            room_group_tag = tg
                            # Check if there are multiple rectangles with same group tag
                            same_group_rects = [it2 for it2 in payload.get("items", [])
                                               if it2.get("type") == "rectangle" 
                                               and tg in it2.get("tags", [])]
                            if len(same_group_rects) >= 4:  # 4 wall rectangles + possibly hit rect
                                # Check if this rectangle is large (likely the hit rect or main fill)
                                if len(coords) >= 4:
                                    rect_width = abs(coords[2] - coords[0])
                                    rect_height = abs(coords[3] - coords[1])
                                    # Check if this is larger than typical wall thickness (walls are ~10-20px)
                                    # If it's a large rectangle with black fill, it's likely the problem
                                    if rect_width > 50 and rect_height > 50:
                                        is_large_room_rect = True
                            new_group_to_rect[tg] = rect_id
                            break
                    
                    # For large rectangles in walls_only rooms, remove black fill
                    if is_large_room_rect and opts.get("fill") == "black":
                        opts = opts.copy()  # Don't modify original
                        opts["fill"] = ""  # Empty fill for walls_only room hit rectangle
                    
                    rect_id = c.create_rectangle(*coords, **opts, tags=tags)
                elif t == "polygon":
                    c.create_polygon(*coords, **opts, tags=tags)
                elif t == "text":
                    if coords:
                        c.create_text(*coords, **opts, tags=tags)
            except Exception as e:
                print("[Serializer] rebuild vector item error:", e)

        # 2) PASS: images (furniture + flooring)
        for it in payload.get("items", []):
            if it.get("type") != "image":
                continue

            coords = it.get("coords", [])
            tags = remap_tags(tuple(it.get("tags", [])))

            # ---- Furniture ----
            furn = it.get("furniture")
            if furn and furn.get("image_path"):
                try:
                    from Furniture import Furniture
                    x = int(coords[0]) if coords else 120
                    y = int(coords[1]) if coords else 120
                    obj = Furniture(
                        canvas=c,
                        image_path=furn["image_path"],
                        x=x,
                        y=y,
                        select_callback=getattr(self.tools, "select_image_item", None),
                        scale=furn.get("scale", 1.0),
                        angle=furn.get("angle", 0),
                        get_freeze_state=lambda: getattr(self.tools, "canvas_frozen", False),
                    )
                    self.tools.image_furniture_items.append(obj)

                    # Furniture must be independent and on top:
                    try:
                        for tg in c.gettags(obj.image_id):
                            if isinstance(tg, str) and tg.startswith("room_group_"):
                                c.dtag(obj.image_id, tg)
                        c.addtag_withtag("furniture", obj.image_id)
                        c.tag_raise(obj.image_id)
                    except Exception:
                        pass
                except Exception as e:
                    print("[Serializer] furniture import failed:", e)
                continue

            # ---- Flooring ----
            flo = it.get("flooring")
            if flo and flo.get("image_path"):
                try:
                    from PIL import Image, ImageTk
                    path = flo["image_path"]
                    w = flo.get("width")
                    h = flo.get("height")
                    x = int(coords[0]) if coords else 0
                    y = int(coords[1]) if coords else 0

                    # Fallback to a default if file missing (keeps demo robust)
                    if not os.path.isfile(path):
                        base = os.path.join(os.path.dirname(__file__), "Images")
                        fallback = os.path.join(base, "tile.jpg")
                        if os.path.isfile(fallback):
                            path = fallback

                    img = Image.open(path)
                    if w and h:
                        img = img.resize((int(w), int(h)), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(img, master=c)

                    new_tags = tuple(set(tags) | {"flooring"})
                    image_id = c.create_image(x, y, image=tk_img, anchor="nw", tags=new_tags)

                    border_id = None
                    if w and h:
                        border_id = c.create_rectangle(
                            x, y, x + int(w), y + int(h),
                            outline="black", width=2,
                            tags=("flooring_border",)
                        )

                    # Re-link to owner room: prefer group tag mapping, ignore stale owner ids
                    owner_rect_id = None
                    group_tag = next((tg for tg in new_tags
                                      if isinstance(tg, str) and tg.startswith("room_group_")), None)
                    if group_tag and group_tag in new_group_to_rect:
                        owner_rect_id = new_group_to_rect[group_tag]

                    key = owner_rect_id if owner_rect_id else image_id

                    self.tools.room_flooring_images[key] = {
                        "image_id": image_id,
                        "tk_img": tk_img,
                        "border_id": border_id,
                        "image_path": path
                    }

                    # Put flooring ABOVE the room fill, but keep labels on top
                    if owner_rect_id:
                        try:
                            c.tag_raise(image_id, owner_rect_id)
                            if border_id:
                                c.tag_raise(border_id, image_id)

                            if group_tag:
                                group_items = c.find_withtag(group_tag)
                                for gi in group_items:
                                    if c.type(gi) == "text":
                                        c.tag_raise(gi, border_id or image_id)
                        except Exception:
                            pass
                except Exception as e:
                    print("[Serializer] flooring import failed:", e)
                continue
            # (generic images ignored)

        # 3) Raise common label/dimension tags if you use them
        for tag in ("room_label", "dimension_text", "room_dimensions"):
            try:
                c.tag_raise(tag)
            except Exception:
                pass

        if hasattr(self.view, "redraw_all_dynamic_elements"):
            try:
                self.view.redraw_all_dynamic_elements()
            except Exception:
                pass
# import uuid
# import json
# import yaml
# import os
# import datetime
# from tkinter import filedialog, messagebox
# import tkinter as tk
# from pathlib import Path
# from typing import Any, Dict, List
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))




# class LayoutSerializer:
#     def __init__(self, model, view, tools, actions):
#         self.model = model
#         self.view = view
#         self.canvas = view.canvas
#         self.tools = tools
#         self.actions = actions
#         if not hasattr(self.tools, "image_furniture_items"):
#             self.tools.image_furniture_items = []
#         if not hasattr(self.tools, "room_flooring_images"):
#             self.tools.room_flooring_images = {}


        
#         # Set up default save directory
#         self.default_save_dir = os.path.join(os.getcwd(), "saved_layouts")
#         self.ensure_save_directory()
        
#         # Auto-save settings
#         self.auto_save_enabled = True
#         self.current_layout_file = None
#         import os

#         BASE_DIR = os.path.dirname(os.path.abspath(__file__))
#         ASSET_DIRS = [
#          os.path.join(BASE_DIR, "Images"),
#          os.path.join(BASE_DIR, "flooring"),
#       ]
#         _missing_asset_logged = set()


#     def ensure_save_directory(self):
#         # """Create the default save directory if it doesn't exist."""
#         Path(self.default_save_dir).mkdir(parents=True, exist_ok=True)

#     def serialize_layout(self):
#         # """Convert the current canvas layout to a dictionary."""
#         layout = {
#             "version": "1.0",
#             "metadata": self._serialize_metadata(),
#             "rooms": self._serialize_rooms(),
#             "furniture": self._serialize_furniture(),
#             "shapes": self._serialize_shapes(),
#             "text": self._serialize_text()
#         }
#         return layout
#     # --- add at top of layout_serializer.py ---
  
#     def _to_portable_path(p: str | None) -> str | None:
#     #  """Convert an absolute path to a project-relative path when possible,
#     # else fall back to just the filename."""
#      if not p:
#         return None
#      p = os.path.abspath(p)
#      try:
#         rel = os.path.relpath(p, BASE_DIR)
#         # If rel stays inside the project, keep it; else just filename
#         if not rel.startswith(".."):
#             return rel.replace("\\", "/")
#      except Exception:
#         pass
#     # last-resort: return only the filename
#      return os.path.basename(p)

#     def _resolve_asset_path(p: str | None) -> str | None:
#      """Resolve an image path that might be absolute (old machine),
#      project-relative, or just a filename. Returns an existing full path or None."""
#      if not p:
#         return None
#      p = p.replace("\\", "/")

#     # If absolute and exists, use it
#      if os.path.isabs(p) and os.path.exists(p):
#         return p

#     # Try project-relative
#      candidate = os.path.join(BASE_DIR, p)
#      if os.path.exists(candidate):
#         return candidate

#     # Try by filename in known asset folders
#      name = os.path.basename(p)
#      for d in ASSET_DIRS:
#         candidate = os.path.join(d, name)
#         if os.path.exists(candidate):
#             return candidate

#      return None

#     def _warn_asset_once(key: str, msg: str):
#      if key not in _missing_asset_logged:
#         print(msg)
#         _missing_asset_logged.add(key)



#     def save_to_json(self):
#     # """Save the current layout to a JSON file."""
#         layout = self.serialize_layout()
#         print("Layout data to save:", layout)  # Debug print
        
#         file_path = filedialog.asksaveasfilename(
#             defaultextension=".json",
#             filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
#             title="Save Layout as JSON"
#         )
        
#         if file_path:
#             try:
#                 with open(file_path, 'w') as f:
#                     json.dump(layout, f, indent=2)
#                 print(f"File saved successfully to: {file_path}")  # Debug print
#                 self.current_layout_file = file_path
#                 messagebox.showinfo("Success", f"Layout saved to {file_path}")
#                 return True
#             except Exception as e:
#                 print(f"Save error: {e}")  # Debug print
#                 messagebox.showerror("Error", f"Failed to save layout: {str(e)}")
#                 return False
#         return False













        




#     def deserialize_layout(self, layout_data):
#     # """Convert a layout dictionary back to canvas objects."""
#         from Furniture import Furniture, find_image_path
        
#         # Clear the canvas first (except for grid)
#         self._clear_canvas()
        
#         # Apply metadata if available
#         if "metadata" in layout_data:
#             self._deserialize_metadata(layout_data["metadata"])
        
#         # Recreate rooms
#         if "rooms" in layout_data:
#             for room_data in layout_data["rooms"]:
#                 self._recreate_room(room_data)
        
#         # Recreate furniture
#         if "furniture" in layout_data:
#             for furniture_data in layout_data["furniture"]:
#                 self._recreate_furniture(furniture_data)
        
#         # Recreate shapes
#         if "shapes" in layout_data:
#             for shape_data in layout_data["shapes"]:
#                 self._recreate_shape(shape_data)
        
#         # Recreate text
#         if "text" in layout_data:
#             for text_data in layout_data["text"]:
#                 self._recreate_text(text_data)
        
#         print("Layout loaded successfully")

#     def _recreate_room(self, room_data):
#         # """Recreate a room from serialized data."""
#         # room_id = self.canvas.create_rectangle(
#         #     room_data["x"], room_data["y"],
#         #     room_data["x"] + room_data["width"], 
#         #     room_data["y"] + room_data["height"],
#         #     fill=room_data["fill_color"],
#         #     outline=room_data["outline_color"],
#         #     tags=("room", room_data["group_tag"])
#         # )
#         room_id = self.canvas.create_rectangle(
#         room_data["x"], room_data["y"],
#         room_data["x"] + room_data["width"],
#         room_data["y"] + room_data["height"],
#         fill=room_data["fill_color"],
#         outline=room_data["outline_color"],
#         tags=("room", room_data["group_tag"])
#     )
    
#         # Recreate flooring if it exists
#         if room_data.get("flooring", {}).get("has_flooring", False):
#             flooring_info = room_data["flooring"]
#             self._recreate_room_flooring(room_id, room_data, flooring_info)
    
#     def _recreate_room_flooring(self, room_id, room_data, flooring_info):
#         # """Recreate flooring for a room."""
#         from PIL import Image, ImageTk
#         import os
        
#         flooring_path = flooring_info.get("image_path", "")
        
#         # Try to find the flooring image
#         if not os.path.exists(flooring_path):
#             # Try to find in Images directory
#             base_dir = os.path.dirname(os.path.abspath(__file__))
#             flooring_type = flooring_info.get("flooring_type", "wood")
            
#             for ext in ('png', 'jpeg', 'jpg'):
#                 alt_path = os.path.join(base_dir, "Images", f"{flooring_type}.{ext}")
#                 if os.path.exists(alt_path):
#                     flooring_path = alt_path
#                     break
        
#         if not os.path.exists(flooring_path):
#             print(f"Warning: Flooring image not found: {flooring_path}")
#             return
        
#         try:
#             # Calculate room dimensions
#             x0, y0 = room_data["x"], room_data["y"]
#             x1, y1 = x0 + room_data["width"], y0 + room_data["height"]
            
#             # Load and resize flooring image
#             img = Image.open(flooring_path)
#             img = img.resize((int(room_data["width"]), int(room_data["height"])), Image.Resampling.LANCZOS)
#             tk_img = ImageTk.PhotoImage(img, master=self.canvas)
            
#             # Create flooring image
#             image_id = self.canvas.create_image(
#                 x0, y0,
#                 image=tk_img,
#                 anchor="nw",
#                 tags=("flooring", room_data["group_tag"])
#             )
            
#             # Create border
#             border_id = self.canvas.create_rectangle(
#                 x0, y0, x1, y1,
#                 outline="black",
#                 width=2,
#                 tags=("flooring_border", room_data["group_tag"])
#             )
            
#             # Store flooring data in tools for future operations
#             if not hasattr(self.tools, 'room_flooring_images'):
#                 self.tools.room_flooring_images = {}
                
#             self.tools.room_flooring_images[room_id] = {
#                 'image_id': image_id,
#                 'tk_img': tk_img,
#                 'border_id': border_id,
#                 'image_path': flooring_path
#             }
            
#             # Manage z-order
#             self.canvas.tag_raise(border_id, image_id)
            
#         except Exception as e:
#             print(f"Error recreating flooring: {e}")


#     def _recreate_furniture(self, furniture_data):
#         # """Recreate furniture from serialized data."""
#         from Furniture import Furniture, find_image_path
#         image_path = None
#         # Method 1: Try the stored full path
#         if os.path.exists(furniture_data["image_path"]):
#             image_path = furniture_data["image_path"]
        
#         # Method 2: Try using the image name with find_image_path function
#         elif "image_name" in furniture_data:
#             image_path = find_image_path(furniture_data["image_name"])
        
#         # Method 3: Try using the filename in local Images directory
#         elif "image_filename" in furniture_data:
#             base_dir = os.path.dirname(os.path.abspath(__file__))
#             local_path = os.path.join(base_dir, "Images", furniture_data["image_filename"])
#             if os.path.exists(local_path):
#                 image_path = local_path
#         # Method 4: Extract name from original path and search
#         else:
#             original_name = os.path.splitext(os.path.basename(furniture_data["image_path"]))[0]
#             image_path = find_image_path(original_name)
        
#         if not image_path:
#             print(f"Warning: Could not locate furniture image: {furniture_data.get('image_filename', furniture_data['image_path'])}")
#             return
        
#         try:
#             furniture_item = Furniture(
#                 canvas=self.canvas,
#                 image_path=image_path,
#                 x=furniture_data["x"],
#                 y=furniture_data["y"],
#                 select_callback=self.tools.select_image_item,
#                 scale=furniture_data["scale"],
#                 angle=furniture_data["angle"],
#                 get_freeze_state=lambda: self.tools.canvas_frozen
#             )
            
#             self.tools.image_furniture_items.append(furniture_item)
#             print(f"Successfully recreated furniture: {os.path.basename(image_path)}")
            
#         except Exception as e:
#             print(f"Error recreating furniture: {e}")








#         path = find_image_path(furniture_data["image_path"].split("/")[-1].split(".")[0])
#         if path:
#             furniture_item = Furniture(
#                 canvas=self.canvas,
#                 image_path=path,
#                 x=furniture_data["x"],
#                 y=furniture_data["y"],
#                 select_callback=self.tools.select_image_item,
#                 scale=furniture_data["scale"],
#                 angle=furniture_data["angle"],
#                 get_freeze_state=lambda: self.tools.canvas_frozen
#             )
#             self.tools.image_furniture_items.append(furniture_item)

#     def _recreate_shape(self, shape_data):
#         # """Recreate shapes from serialized data."""
#         coords = [coord for point in shape_data["points"] for coord in point]
        
#         if shape_data["type"] == "line":
#             self.canvas.create_line(
#                 *coords,
#                 fill=shape_data["outline_color"],
#                 width=shape_data["width"]
#             )
#         elif shape_data["type"] == "rectangle":
#             self.canvas.create_rectangle(
#                 *coords,
#                 fill=shape_data["fill_color"],
#                 outline=shape_data["outline_color"],
#                 width=shape_data["width"]
#             )
#         elif shape_data["type"] == "oval":
#             self.canvas.create_oval(
#                 *coords,
#                 fill=shape_data["fill_color"],
#                 outline=shape_data["outline_color"],
#                 width=shape_data["width"]
#             )

#     def _recreate_text(self, text_data):
#         # """Recreate text from serialized data."""
#         self.canvas.create_text(
#             text_data["x"], text_data["y"],
#             text=text_data["content"],
#             font=text_data["font"],
#             fill=text_data["color"],
#             anchor="nw"
#         )


#     def load_from_json(self):
#     # """Load a layout from a JSON file."""
#         file_path = filedialog.askopenfilename(
#             defaultextension=".json",
#             filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
#             title="Load Layout from JSON"
#         )
        
#         if file_path:
#             try:
#                 with open(file_path, 'r') as f:
#                     layout_data = json.load(f)
#                 self.deserialize_layout(layout_data)
#                 self.current_layout_file = file_path
#                 messagebox.showinfo("Success", f"Layout loaded from {file_path}")
#                 return True
#             except Exception as e:
#                 messagebox.showerror("Error", f"Failed to load layout: {str(e)}")
#                 return False
#         return False

#     # def load_from_json(self):
#     #     """Load a layout from a JSON file."""
#     #     file_path = filedialog.askopenfilename(
#     #         defaultextension=".json",
#     #         filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
#     #         title="Load Layout from JSON"
#     #     )
        
#     #     if file_path:
#     #         try:
#     #             with open(file_path, 'r') as f:
#     #                 layout_data = json.load(f)
#     #         self.deserialize_layout(layout_data)
#     #         self.current_layout_file = file_path
   
#     #     return False

#     def save_to_yaml(self):
#         # """Save the current layout to a YAML file."""
#         layout = self.serialize_layout()
        
#         file_path = filedialog.asksaveasfilename(
#             defaultextension=".yaml",
#             filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
#             title="Save Layout as YAML"
#         )
        
#         if file_path:
#             try:
#                 with open(file_path, 'w') as f:
#                     yaml.safe_dump(layout, f, indent=2)
#                 self.current_layout_file = file_path
#                 messagebox.showinfo("Success", f"Layout saved to {file_path}")
#                 return True
#             except Exception as e:
#                 messagebox.showerror("Error", f"Failed to save layout: {str(e)}")
#                 return False
#         return False

#     def load_from_yaml(self):
#         # """Load a layout from a YAML file."""
#         file_path = filedialog.askopenfilename(
#             defaultextension=".yaml",
#             filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
#             title="Load Layout from YAML"
#         )
        
#         if file_path:
#             try:
#                 with open(file_path, 'r') as f:
#                     layout_data = yaml.safe_load(f)
#                 self.deserialize_layout(layout_data)
#                 self.current_layout_file = file_path
#                 messagebox.showinfo("Success", f"Layout loaded from {file_path}")
#                 return True
#             except Exception as e:
#                 messagebox.showerror("Error", f"Failed to load layout: {str(e)}")
#                 return False
#         return False

#     def auto_save_layout(self):
#         # """Auto-save the current layout."""
#         if not self.auto_save_enabled:
#             return False
        
#         # Generate timestamp filename
#         timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#         filename = f"autosave_{timestamp}.json"
#         file_path = os.path.join(self.default_save_dir, filename)
        
#         layout = self.serialize_layout()
#         try:
#             with open(file_path, 'w') as f:
#                 json.dump(layout, f, indent=2)
#             print(f"Auto-saved to: {file_path}")
#             messagebox.showinfo("Auto-Save", f"Layout auto-saved to {filename}")
#             return True
#         except Exception as e:
#             print(f"Auto-save error: {e}")
#             return False

#     def _serialize_metadata(self):
#         # """Serialize canvas metadata."""
#         return {
#             "project_name": "Floor Plan",
#             "description": "Auto-generated layout",
#             "created": datetime.datetime.now().isoformat(),
#             "modified": datetime.datetime.now().isoformat(),
#             "unit": getattr(self.model, 'unit', 'm'),
#             "grid_spacing": getattr(self.model, 'grid_spacing', 20),
#             "canvas_width": self.canvas.winfo_width(),
#             "canvas_height": self.canvas.winfo_height(),
#             "zoom_level": getattr(self.model, 'zoom_level', 1.0)
#         }

#     def _serialize_rooms(self):
#     # """Serialize room data including flooring information."""
#         rooms = []
#         for item in self.canvas.find_withtag("room"):
#             coords = self.canvas.coords(item)
#             if len(coords) >= 4:
#                 # Build base room dict
#                 room_data = {
#                     "id":     f"room_{item}",
#                     "name":   "Room",
#                     "x":      coords[0],
#                     "y":      coords[1],
#                     "width":  coords[2] - coords[0],
#                     "height": coords[3] - coords[1],
#                     "fill_color":    self.canvas.itemcget(item, "fill"),
#                     "outline_color": self.canvas.itemcget(item, "outline"),
#                     "group_tag":     "room_group"
#                 }
#                 # Attach flooring info if present
#                 if hasattr(self.tools, 'room_flooring_images') \
#                 and item in self.tools.room_flooring_images:
#                     fd = self.tools.room_flooring_images[item]
#                     room_data["flooring"] = {
#                         "image_path":   fd.get('image_path', ''),
#                         "has_flooring": True,
#                         "flooring_type": self._get_flooring_type_from_path(
#                             fd.get('image_path', '')
#                         )
#                     }
#                 else:
#                     room_data["flooring"] = {"has_flooring": False}
#                 rooms.append(room_data)
#         return rooms



#     # def _get_flooring_type_from_path(self, image_path):
#     # # """Extract flooring type from image path."""
#     #     if not image_path:
#     #         return "none"
        
#     #     filename = os.path.basename(image_path).lower()
#     #     if "wood" in filename:
#     #         return "wood"
#     #     elif "tile" in filename:
#     #         return "tile"
#     #     elif "marble" in filename:
#     #         return "marble"
#     #     elif "garden" in filename:
#     #         return "garden"
#     #     else:
#     #         return "unknown"
#     def _get_flooring_type_from_path(self, image_path):
#     # """Extract flooring type from image path."""
#         import os
#         if not image_path:
#             return "none"
#         fname = os.path.basename(image_path).lower()
#         if "wood"   in fname: return "wood"
#         if "tile"   in fname: return "tile"
#         if "marble" in fname: return "marble"
#         if "garden" in fname: return "garden"
#         return "unknown"







#     def _serialize_furniture(self):
#         furniture = []
#         for idx, f in enumerate(self.tools.image_furniture_items):
#             x, y = self.canvas.coords(f.image_id)
            
#             # Extract just the filename for portability
#             image_filename = os.path.basename(f.image_path)
#             image_name = os.path.splitext(image_filename)[0]
            
#             furniture_data = {
#                 "id": f"furniture_{idx}",
#                 "image_path": f.image_path,  # Keep full path for backward compatibility
#                 "image_filename": image_filename,  # Add filename
#                 "image_name": image_name,  # Add base name without extension
#                 "x": x,
#                 "y": y,
#                 "scale": f.scale,
#                 "angle": f.angle
#             }
#             furniture.append(furniture_data)
#         return furniture

#     def _serialize_shapes(self):
#     # """Serialize shape data."""
#         shapes = []
#         for item in self.canvas.find_all():
#             tags = self.canvas.gettags(item)
#             if "grid" not in tags and "room" not in tags and "furniture" not in tags:
#                 item_type = self.canvas.type(item)
#                 coords = self.canvas.coords(item)
#                 if coords:
#                     points = [[coords[i], coords[i+1]] for i in range(0, len(coords), 2)]
                    
#                     # Safely get width
#                     try:
#                         width_str = self.canvas.itemcget(item, "width")
#                         width = float(width_str) if width_str else 1.0
#                     except (ValueError, TypeError, tk.TclError):
#                         width = 1.0
                    
#                     # Safely get colors based on item type
#                     outline_color = ""
#                     fill_color = ""
                    
#                     try:
#                         if item_type in ["line", "rectangle", "oval", "polygon"]:
#                             outline_color = self.canvas.itemcget(item, "outline")
#                         elif item_type == "text":
#                             outline_color = self.canvas.itemcget(item, "fill")
#                     except tk.TclError:
#                         outline_color = "black"
                    
#                     try:
#                         if item_type in ["rectangle", "oval", "polygon"]:
#                             fill_color = self.canvas.itemcget(item, "fill")
#                     except tk.TclError:
#                         fill_color = ""
                    
#                     # Use fill color as outline for items that don't have outline
#                     if not outline_color and fill_color:
#                         outline_color = fill_color
#                     elif not outline_color:
#                         outline_color = "black"
                    
#                     shapes.append({
#                         "id": f"shape_{item}",
#                         "type": item_type,
#                         "points": points,
#                         "outline_color": outline_color,
#                         "fill_color": fill_color,
#                         "width": width,
#                         "style": "solid"
#                     })
#         return shapes



#     def _serialize_text(self):
#     # """Serialize text data."""
#         texts = []
#         for item in self.canvas.find_all():
#             if self.canvas.type(item) == "text":
#                 coords = self.canvas.coords(item)
                
#                 # Safely get text properties
#                 try:
#                     content = self.canvas.itemcget(item, "text")
#                 except tk.TclError:
#                     content = ""
                
#                 try:
#                     font = self.canvas.itemcget(item, "font")
#                 except tk.TclError:
#                     font = "Arial 10"
                
#                 try:
#                     color = self.canvas.itemcget(item, "fill")
#                 except tk.TclError:
#                     color = "black"
                
#                 if coords and content:
#                     texts.append({
#                         "id": f"text_{item}",
#                         "content": content,
#                         "x": coords[0],
#                         "y": coords[1],
#                         "font": font,
#                         "color": color
#                     })
#         return texts


#     def _clear_canvas(self):
#         # """Clear all canvas items except grid."""
#         for item in self.canvas.find_all():
#             if "grid" not in self.canvas.gettags(item):
#                 self.canvas.delete(item)
#         # Clear furniture list
#         self.tools.image_furniture_items.clear()

#     def _deserialize_metadata(self, metadata):
#         # """Apply metadata to the model."""
#         if hasattr(self.model, 'unit'):
#             self.model.unit = metadata.get("unit", "m")
#         if hasattr(self.model, 'grid_spacing'):
#             self.model.grid_spacing = metadata.get("grid_spacing", 20)
#         if hasattr(self.model, 'zoom_level'):
#             self.model.zoom_level = metadata.get("zoom_level", 1.0)
#     def export_to_dict(self) -> Dict[str, Any]:
#         c = self.view.canvas
#         items: List[Dict[str, Any]] = []

#         for item_id in c.find_all():
#             tags = c.gettags(item_id) or ()
#             if "grid" in tags:
#                 continue

#             t = c.type(item_id)
#             entry: Dict[str, Any] = {"type": t, "tags": list(tags)}

#             # geometry
#             try:
#                 entry["coords"] = c.coords(item_id)
#             except Exception:
#                 entry["coords"] = []

#             # vector styling
#             if t in ("line", "oval", "rectangle", "polygon", "text"):
#                 opts = {}
#                 for k in ("fill", "outline", "width", "dash", "text", "font"):
#                     try:
#                         v = c.itemcget(item_id, k)
#                         if v not in ("", None):
#                             opts[k] = v
#                     except Exception:
#                         pass
#                 entry["options"] = opts

#             # images: furniture or flooring
#             if t == "image":
#                 tags_set = set(tags)

#                 # ---- Furniture (match runtime object by image_id)
#                 furn_info = None
#                 try:
#                     for f in getattr(self.tools, "image_furniture_items", []):
#                         if getattr(f, "image_id", None) == item_id:
#                             furn_info = {
#                                 "image_path": getattr(f, "image_path", None),
#                                 "scale": getattr(f, "scale", 1.0),
#                                 "angle": getattr(f, "angle", 0),
#                             }
#                             break
#                 except Exception:
#                     pass
#                 if furn_info:
#                     entry["furniture"] = furn_info

#                 # ---- Flooring (tagged 'flooring') — store path/size/owner rect id if known
#                 if "flooring" in tags_set:
#                     image_path = None
#                     width = None
#                     height = None
#                     owner_rect_id = None

#                     try:
#                         for k, data in getattr(self.tools, "room_flooring_images", {}).items():
#                             if data.get("image_id") == item_id:
#                                 image_path = data.get("image_path")
#                                 if isinstance(k, int):
#                                     owner_rect_id = k
#                                 break
#                         bbox = c.bbox(item_id)
#                         if bbox:
#                             x0, y0, x1, y1 = bbox
#                             width, height = int(x1 - x0), int(y1 - y0)
#                     except Exception:
#                         pass

#                     entry["flooring"] = {
#                         "image_path": image_path,
#                         "width": width,
#                         "height": height,
#                         "owner_rect_id": owner_rect_id,
#                     }

#             items.append(entry)

#         meta = {
#             "unit": getattr(self.model, "unit", "feet"),
#             "grid_spacing": getattr(self.model, "grid_spacing", 20),
#             "zoom_level": getattr(self.model, "zoom_level", 1.0),
#             "canvas_width": self.view.canvas.winfo_width(),
#             "canvas_height": self.view.canvas.winfo_height(),
#         }
#         return {"meta": meta, "items": items}

#     # -------------------------------------------------------------------------
#     # Import
#     # -------------------------------------------------------------------------
#     def import_from_dict(self, payload: Dict[str, Any]) -> None:
#         c = self.view.canvas

#         # Clear non-grid
#         for iid in c.find_all():
#             if "grid" not in c.gettags(iid):
#                 c.delete(iid)

#         # Reset containers
#         self.tools.image_furniture_items = []
#         self.tools.room_flooring_images = {}

#         # Restore meta
#         meta = payload.get("meta", {})
#         if hasattr(self.model, "set_unit"):
#             self.model.set_unit(meta.get("unit", getattr(self.model, "unit", "feet")))
#         if "grid_spacing" in meta:
#             setattr(self.model, "grid_spacing", meta["grid_spacing"])
#         if "zoom_level" in meta:
#             setattr(self.model, "zoom_level", meta["zoom_level"])
#         if hasattr(self.view, "draw_grid"):
#             self.view.draw_grid()

#         # 0) Build a mapping old_group_tag -> new unique group tag (avoid collisions)
#         old_to_new_group: Dict[str, str] = {}
#         for it in payload.get("items", []):
#             for tg in it.get("tags", []):
#                 if isinstance(tg, str) and tg.startswith("room_group_"):
#                     if tg not in old_to_new_group:
#                         old_to_new_group[tg] = f"room_group_{uuid.uuid4().hex[:8]}"

#         def remap_tags(tags_tuple):
#             # replace any old group tag with the new one
#             out = []
#             for tg in tags_tuple:
#                 if isinstance(tg, str) and tg in old_to_new_group:
#                     out.append(old_to_new_group[tg])
#                 else:
#                     out.append(tg)
#             return tuple(out)

#         # 1) PASS: create vectors first; collect mapping: new_group_tag -> rect_id
#         new_group_to_rect: Dict[str, int] = {}

#         for it in payload.get("items", []):
#             t = it.get("type")
#             if t not in ("line", "oval", "rectangle", "polygon", "text"):
#                 continue

#             coords = it.get("coords", [])
#             tags = remap_tags(tuple(it.get("tags", [])))
#             opts = it.get("options", {})

#             try:
#                 if t == "line":
#                     c.create_line(*coords, **opts, tags=tags)
#                 elif t == "oval":
#                     c.create_oval(*coords, **opts, tags=tags)
#                 elif t == "rectangle":
#                     rect_id = c.create_rectangle(*coords, **opts, tags=tags)
#                     for tg in tags:
#                         if isinstance(tg, str) and tg.startswith("room_group_"):
#                             new_group_to_rect[tg] = rect_id
#                 elif t == "polygon":
#                     c.create_polygon(*coords, **opts, tags=tags)
#                 elif t == "text":
#                     if coords:
#                         c.create_text(*coords, **opts, tags=tags)
#             except Exception as e:
#                 print("[Serializer] rebuild vector item error:", e)

#         # 2) PASS: images (furniture + flooring)
#         for it in payload.get("items", []):
#             if it.get("type") != "image":
#                 continue

#             coords = it.get("coords", [])
#             tags = remap_tags(tuple(it.get("tags", [])))

#             # ---- Furniture ----
#             furn = it.get("furniture")
#             if furn and furn.get("image_path"):
#                 try:
#                     from Furniture import Furniture
#                     x = int(coords[0]) if coords else 120
#                     y = int(coords[1]) if coords else 120
#                     obj = Furniture(
#                         canvas=c,
#                         image_path=furn["image_path"],
#                         x=x,
#                         y=y,
#                         select_callback=getattr(self.tools, "select_image_item", None),
#                         scale=furn.get("scale", 1.0),
#                         angle=furn.get("angle", 0),
#                         get_freeze_state=lambda: getattr(self.tools, "canvas_frozen", False),
#                     )
#                     self.tools.image_furniture_items.append(obj)

#                     # Furniture must be independent and on top:
#                     try:
#                         for tg in c.gettags(obj.image_id):
#                             if isinstance(tg, str) and tg.startswith("room_group_"):
#                                 c.dtag(obj.image_id, tg)
#                         c.addtag_withtag("furniture", obj.image_id)
#                         c.tag_raise(obj.image_id)
#                     except Exception:
#                         pass
#                 except Exception as e:
#                     print("[Serializer] furniture import failed:", e)
#                 continue

#             # ---- Flooring ----
#             flo = it.get("flooring")
#             if flo and flo.get("image_path"):
#                 try:
#                     from PIL import Image, ImageTk
#                     path = flo["image_path"]
#                     w = flo.get("width")
#                     h = flo.get("height")
#                     x = int(coords[0]) if coords else 0
#                     y = int(coords[1]) if coords else 0

#                     # Fallback to a default if file missing (keeps demo robust)
#                     if not os.path.isfile(path):
#                         base = os.path.join(os.path.dirname(__file__), "Images")
#                         fallback = os.path.join(base, "tile.jpg")
#                         if os.path.isfile(fallback):
#                             path = fallback

#                     img = Image.open(path)
#                     if w and h:
#                         img = img.resize((int(w), int(h)), Image.Resampling.LANCZOS)
#                     tk_img = ImageTk.PhotoImage(img, master=c)

#                     new_tags = tuple(set(tags) | {"flooring"})
#                     image_id = c.create_image(x, y, image=tk_img, anchor="nw", tags=new_tags)

#                     border_id = None
#                     if w and h:
#                         border_id = c.create_rectangle(
#                             x, y, x + int(w), y + int(h),
#                             outline="black", width=2,
#                             tags=("flooring_border",)
#                         )

#                     # Re-link to owner room: prefer group tag mapping, ignore stale owner ids
#                     owner_rect_id = None
#                     group_tag = next((tg for tg in new_tags
#                                       if isinstance(tg, str) and tg.startswith("room_group_")), None)
#                     if group_tag and group_tag in new_group_to_rect:
#                         owner_rect_id = new_group_to_rect[group_tag]

#                     key = owner_rect_id if owner_rect_id else image_id

#                     self.tools.room_flooring_images[key] = {
#                         "image_id": image_id,
#                         "tk_img": tk_img,
#                         "border_id": border_id,
#                         "image_path": path
#                     }

#                     # Put flooring UNDER the room so labels/dims remain visible
#                     if owner_rect_id:
#                         try:
#                             c.tag_lower(image_id, owner_rect_id)
#                             if border_id:
#                                 c.tag_lower(border_id, owner_rect_id)
#                         except Exception:
#                             pass
#                 except Exception as e:
#                     print("[Serializer] flooring import failed:", e)
#                 continue
#             # (generic images ignored)

#         # 3) Raise common label/dimension tags if you use them
#         for tag in ("room_label", "dimension_text", "room_dimensions"):
#             try:
#                 c.tag_raise(tag)
#             except Exception:
#                 pass

#         if hasattr(self.view, "redraw_all_dynamic_elements"):
#             try:
#                 self.view.redraw_all_dynamic_elements()
#             except Exception:
#                 pass
    