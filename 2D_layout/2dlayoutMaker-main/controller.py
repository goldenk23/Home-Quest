# controller.py

import platform
import tkinter as tk
import importlib.util
import os
import sys
import time

from line_edit_manager import LineEditManager
from autopan import AutoPanWhileDrawing


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def _import_local_set_window_icon():
    """
    VastuApp may already have imported a different top-level `Helper` package.
    Load MiniAutoCAD's `Helper/set_window_icon.py` via file path to avoid collisions.
    """
    path = os.path.join(_THIS_DIR, "Helper", "set_window_icon.py")
    spec = importlib.util.spec_from_file_location("_mini_autocad_set_window_icon_controller", path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Unable to load set_window_icon from '{path}'")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
    except Exception:
        pass
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return getattr(module, "set_window_icon")


try:
    set_window_icon = _import_local_set_window_icon()
except Exception:
    # Best-effort: if icon helper can't be loaded, just no-op.
    def set_window_icon(_win):  # type: ignore[no-redef]
        return None


class CanvasController:
    def __init__(self, root, model, view, tools, actions):
        self.root = root
        self.model = model
        self.view = view
        self.canvas = view.canvas
        self.tools = tools
        self.actions = actions
        self.line_editor = LineEditManager(self.canvas, self.model, self.actions, self.tools)

        self.dragging_item = None
        # Must exist before the first drag: on_release reads self.dragging_group
        # directly (not via hasattr), so a click that never resolves to a draggable
        # group (empty canvas, a protected label) would otherwise raise AttributeError
        # on release and the app "crashes" silently.
        self.dragging_group = None
        self.drag_start_pos = None
        self.drag_origin_pos = None
        self.initial_room_bbox = None  # Store initial room bbox for alignment
        self.initial_line_coords = None
        self.selected_group_tag = None
        self._drag_anchor = None
        self._guide_candidates = None  # (group, edge_xs, edge_ys) gathered once per drag
        self._wall_component_seq = 0  # unique suffix for temporary wall-drag group tags
        self._last_motion_time = 0
        self._motion_throttle_ms = 10  # Reduced to 10 ms for smoother cursor tracking and less lag
        
        # Canvas panning state (Right-click drag)
        self._pan_start_x = None
        self._pan_start_y = None
        self._is_panning = False
        # Auto-pan while drawing (polygon / Vastu polygon).
        # Encapsulated so other tools can reuse the same behavior.
        self._auto_pan_controller = AutoPanWhileDrawing(
            canvas=self.canvas,
            view=self.view,
            model=self.model,
            tools=self.tools,
            is_active_fn=self._is_polygon_draw_active,
            edge_threshold_px=35,  # Reduced from 70
            speed=1,
            interval_ms=50,       # Faster updates for smoothness
            step_canvas_x_px=5,   # Smaller steps for control
            step_canvas_y_px=5,
            stuck_limit=8,
        )
        # Bind events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)        
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        # Right-click / secondary button bindings for panning and context menus
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Button-2>", self.on_right_click)
        self.canvas.bind("<Control-Button-1>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<B2-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)
        self.canvas.bind("<ButtonRelease-2>", self.on_right_release)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        root.bind("<Control-z>", lambda e: self._do_undo())
        root.bind("<Control-y>", lambda e: self._do_redo())
        root.bind("<Control-Shift-z>", lambda e: self._do_redo())
        root.bind("<Control-Shift-Z>", lambda e: self._do_redo())
        if platform.system() == "Darwin":
            root.bind("<Mod1-z>", lambda e: self._do_undo())
            root.bind("<Mod1-Shift-Z>", lambda e: self._do_redo())
            root.bind("<Mod1-y>", lambda e: self._do_redo())
        root.bind("<Key>", self.on_key_press)
        self.canvas.bind("<Motion>", self.on_mouse_move)

    def _is_polygon_draw_active(self) -> bool:
        """Auto-pan only when user has actually started placing polygon points."""
        try:
            if self.model.get("polygon_mode"):
                pts = getattr(self.tools, "polygon_points", None) or []
                if len(pts) > 0:
                    return True
            if self.model.get("vastu_polygon_mode"):
                vpts = getattr(self.tools, "vastu_polygon_points", None) or []
                if len(vpts) > 0:
                    return True
        except Exception:
            pass
        return False

    def _canvas_for_undo(self):
        """Return the canvas used for undo/redo (same instance everywhere)."""
        c = getattr(self, "canvas", None)
        if c is not None:
            return c
        if self.tools and hasattr(self.tools, "canvas"):
            return self.tools.canvas
        return None

    def _do_undo(self):
        # If vastu polygon or normal polygon is in progress, undo the last placed point
        if self.model.get("vastu_polygon_mode"):
            if hasattr(self.tools, "undo_last_vastu_polygon_point"):
                if self.tools.undo_last_vastu_polygon_point():
                    try:
                        self.view.schedule_grid_redraw(delay_ms=0)
                    except Exception:
                        pass
                    return
        elif self.model.get("polygon_mode"):
            if hasattr(self.tools, "undo_last_polygon_point"):
                if self.tools.undo_last_polygon_point():
                    try:
                        self.view.schedule_grid_redraw(delay_ms=0)
                    except Exception:
                        pass
                    return

        c = self._canvas_for_undo()
        if c is not None:
            self.actions.undo(c)

    def _do_redo(self):
        c = self._canvas_for_undo()
        if c is not None:
            self.actions.redo(c)

    def refresh_ui(self):
        """Cancel active tools and selections, then repaint UI without changing the design."""
        self.tools.reset_modes()
        self.tools.clear_furniture_selection()
        if hasattr(self.tools, "clear_window_selection"):
            self.tools.clear_window_selection()
        self.tools.selected_item = None
        self.selected_group_tag = None
        self.dragging_item = None
        self.dragging_group = None
        self.drag_start_pos = None
        self.drag_origin_pos = None
        self.initial_room_bbox = None
        self.initial_line_coords = None
        self._dragging_group_item_ids = None
        try:
            if self.selected_dimension_tag:
                self.canvas.itemconfig(self.selected_dimension_tag, width=1)
        except Exception:
            pass
        self.selected_dimension_tag = None
        try:
            self.line_editor.clear()
        except Exception:
            pass
        try:
            self.tools.guideline_helper.clear_guides()
        except Exception:
            pass
        self.canvas.config(cursor="arrow")
        try:
            self.view.schedule_grid_redraw(delay_ms=0)
        except Exception:
            pass
        self.canvas.update_idletasks()
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        return True

    def on_click(self, event):
        # Project structure capture owns this click; its additive canvas binding
        # runs next and must not compete with normal selection/drawing behavior.
        if getattr(self.tools, "_parity_capture_active", False):
            return
        x, y = event.x, event.y
        print(f"Click at ({x}, {y})")
        if self.tools.canvas_frozen:
            print("Canvas is frozen — click ignored.")
            return
        if not self._is_line_handle_hit(event):
            self.line_editor.clear()
        # Multi-eraser: use simple left-click drag as selection start
        if self.model.get("multi_eraser_mode"):
            self.tools.start_multi_erase_selection(event)
            return
        # Active tools like drawing, filling, text, etc.
        elif self.model.get("paste_mode"):
            self.tools.paste_item_at_click(event)
            return
        elif self.model.get("drawing_enabled"):
            if hasattr(self.tools, 'temp_entry') and self.tools.temp_entry:
                return
            # Line mode owns canvas clicks; snapping decides whether nearby geometry is used.
            self.tools.start_line(event)
        elif self.model.get("vastu_polygon_mode"):
            self.tools.add_vastu_polygon_point(event)
            return
        elif self.model.get("polygon_mode"):
            self.tools.add_polygon_point(event)
        elif self.model.get("fill_mode_enabled"):
            self.tools.fill_shape(event)
        elif self.model.get("text_insertion_mode"):
            self.tools.insert_text(event)
        elif self.model.get("furniture_mode"):
            self.tools.place_furniture(event)
            return
        elif self.model.get("window_mode"):
            self.tools.place_window(event)
            return
        elif self.model.get("eraser_mode"):
            self.tools.handle_eraser_click(event)
            return
        elif self.tools.flooring_enabled:
            self.tools.apply_flooring_to_room(event)
            return
        else:
            self.select_item(event)
            

    def on_drag(self, event):
        now = time.time() * 1000
        if now - self._last_motion_time < self._motion_throttle_ms:
            return
        self._last_motion_time = now

        if self.drag_start_pos is None:
            # Allow drag even without prior left-press for some tools (e.g., multi-erase)
            if not self.model.get("multi_eraser_mode"):
                return

        if self.tools.canvas_frozen:
            return

        # Clear any preview/trace state as soon as drag starts (prevents ghost lines on Mac/Win)
        try:
            self.tools._cancel_line_input()
        except Exception:
            pass

        # Multi-eraser selection with left drag
        if self.model.get("multi_eraser_mode"):
            self.tools.update_multi_erase_selection(event)
            return

        dx = event.x - self.drag_start_pos[0]
        dy = event.y - self.drag_start_pos[1]

        # 🧱 Group dragging
        if hasattr(self, 'dragging_group') and self.dragging_group:
            # Handle room alignment with snapping
            if self.dragging_group.startswith("room_group_"):
                # Calculate alignment first, then move
                room_entity = self.tools.room_entities_by_group_tag.get(self.dragging_group)
                if room_entity and hasattr(room_entity, 'rect_id'):
                    try:
                        # Get current position before move
                        current_coords = self.canvas.coords(room_entity.rect_id)
                        if current_coords and len(current_coords) >= 4:
                            # Where the room WANTS to be, measured from the pointer rather
                            # than from where the room currently sits. `on_drag` resets
                            # `drag_start_pos` every event, so dx/dy are 1-3 px increments
                            # with no memory of the drag start: snapping those directly
                            # re-snapped a flush room straight back onto the same edge on
                            # every event, so it stayed glued until the mouse jerked more
                            # than the 12 px tolerance in a single event — the "sticks a
                            # bit while snapping and dragging" report — and the room also
                            # drifted away from the cursor by however much snapping had
                            # adjusted it. Summing the increments into an offset from a
                            # per-drag anchor lets many small moves add up, so the room
                            # releases exactly when the pointer has travelled past the
                            # tolerance and always ends up back under the cursor. Same
                            # anchored approach `_snap_room_delta` uses for draw-tool
                            # groups; a drag is only ever one kind, so they share the slot.
                            anchor = getattr(self, "_drag_anchor", None)
                            if anchor is None or anchor.get("group") != self.dragging_group:
                                anchor = {
                                    "group": self.dragging_group,
                                    "bounds": tuple(current_coords[:4]),
                                    "offset": [0.0, 0.0],
                                }
                                self._drag_anchor = anchor
                            anchor["offset"][0] += dx
                            anchor["offset"][1] += dy
                            base = anchor["bounds"]
                            off_x, off_y = anchor["offset"]
                            new_x0, new_y0 = base[0] + off_x, base[1] + off_y
                            new_x1, new_y1 = base[2] + off_x, base[3] + off_y
                            temp_bbox = (new_x0, new_y0, new_x1, new_y1)
                            
                            # Get all other rooms for alignment
                            other_rooms = [
                                (tag, room) for tag, room in self.tools.room_entities_by_group_tag.items()
                                if tag != self.dragging_group
                            ]
                            
                            # Calculate alignment snap. Tolerance 5 px was too tight for a
                            # real drag: the alignment only registered in a 5 px window, so
                            # the red dashed guides flickered in and out. 12 px makes both
                            # the snap and its guides appear reliably.
                            snapped_x0, snapped_y0, snap_info = self.tools.guideline_helper.get_room_alignment_snap(
                                temp_bbox, other_rooms, tolerance=12
                            )

                            # Rooms are solid: never let one penetrate another. Push the
                            # dragged room back out along whichever axis it entered least,
                            # so it comes to rest flush against the neighbour instead of
                            # overlapping it.
                            snapped_x0, snapped_y0 = self._prevent_room_overlap(
                                snapped_x0, snapped_y0,
                                new_x1 - new_x0, new_y1 - new_y0,
                                other_rooms,
                            )

                            # Calculate final offset (dx, dy adjusted for snap)
                            final_dx = snapped_x0 - current_coords[0]
                            final_dy = snapped_y0 - current_coords[1]
                            
                            # Move room with alignment using tag-based move (much faster)
                            self.canvas.move(self.dragging_group, final_dx, final_dy)
                            
                            # Draw alignment guides AFTER moving, from the position the
                            # room actually landed in (snap_info alone misses alignments
                            # produced by the overlap guard, and knows nothing about
                            # draw-tool neighbours).
                            updated_coords = self.canvas.coords(room_entity.rect_id)
                            if updated_coords and len(updated_coords) >= 4:
                                self._show_alignment_guides(
                                    self.dragging_group, tuple(updated_coords[:4]),
                                    snap_info, other_rooms,
                                )
                            
                            self.drag_start_pos = (event.x, event.y)
                            return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        # Fall through to normal drag if alignment fails
            
            # Draw-tool geometry snaps flush to neighbouring geometry, so patching a house
            # together feels the same as with the Room tool. Both draw-tool drag groups
            # need this: a detected room (parity_room_drag:<id>) *and* a bare wall group
            # (line_<uuid>), because a loop the detector never turned into a room can only
            # be dragged one wall at a time — that is the common real case, and leaving it
            # unsnapped is why the editor still felt like it had no snapping at all.
            snapping_group = self.dragging_group.startswith(
                ("parity_room_drag:", "line_", "wall_component_")
            )
            if snapping_group:
                dx, dy = self._snap_room_delta(self.dragging_group, dx, dy)

            # Normal group dragging (polygons, entire layout, etc.) using tag-based move
            self.canvas.move(self.dragging_group, dx, dy)

            # Same dashed feedback as the Room-tool path above: whichever tool made the
            # geometry, a flush edge shows a guide.
            if snapping_group:
                self._show_alignment_guides(self.dragging_group)

            if self.dragging_group == getattr(self.tools, "_entire_layout_tag", None):
                self.tools.shift_entire_layout_state(
                    dx, dy, getattr(self.tools, "_entire_layout_state_scope", None)
                )

            # Keep Vastu slice baseline in sync when the whole Vastu group is moved
            if self.dragging_group == "vastu_group":
                try:
                    self.tools.shift_vastu_slice_baseline(dx, dy)
                except Exception:
                    pass
            
            # If dragging a polygon, also move rooms (and their contents) inside it.
            # Skip items that already have polygon_group_ tag - they were moved above.
            # Furniture can have both polygon_group_ and room_group_; moving twice would double the offset.
            if self.dragging_group.startswith("polygon_group_"):
                # Update in-memory baseline coordinates to prevent centroid drift shift during door cuts
                try:
                    if hasattr(self.tools, "_polygon_baseline_coords_by_group"):
                        baseline = self.tools._polygon_baseline_coords_by_group.get(self.dragging_group)
                        if baseline:
                            self.tools._polygon_baseline_coords_by_group[self.dragging_group] = [
                                (float(v) + dx if i % 2 == 0 else float(v) + dy)
                                for i, v in enumerate(baseline)
                            ]
                except Exception:
                    pass

                # Use cached item IDs if available
                if not hasattr(self, "_dragging_group_item_ids") or self._dragging_group_item_ids is None:
                    self._dragging_group_item_ids = set(self.canvas.find_withtag(self.dragging_group))
                
                polygon_item_ids = self._dragging_group_item_ids
                if hasattr(self.tools, 'polygon_rooms_map'):
                    room_groups = self.tools.polygon_rooms_map.get(self.dragging_group, [])
                    for room_group_tag in room_groups:
                        # Move the whole room group at once if it's not the same as the dragging group
                        if room_group_tag != self.dragging_group:
                            # In Tkinter, if an item has multiple tags, calling move(tag1) then move(tag2)
                            # will move it twice. We must ensure we don't move overlapping items twice.
                            # Since we already moved self.dragging_group, we only move room_group_tag items
                            # that are NOT in self.dragging_group.
                            # Tag-based move is still better even with find_withtag.
                            room_item_ids = self.canvas.find_withtag(room_group_tag)
                            for rid in room_item_ids:
                                if rid not in polygon_item_ids:
                                    self.canvas.move(rid, dx, dy)
                try:
                    self.tools.move_user_text_inside_polygon(self.dragging_group, dx, dy)
                except Exception:
                    pass
            
            self.drag_start_pos = (event.x, event.y)
            return

        # 📦 Item dragging
        if self.dragging_item is not None:
            if "grid" in self.canvas.gettags(self.dragging_item):
                return
            tags = self.canvas.gettags(self.dragging_item)
            # For text (especially bold/italic), use coords() + update to avoid ghost traces on Mac/Win
            if self.canvas.type(self.dragging_item) == "text" and "user_text" in tags:
                try:
                    c = self.canvas.coords(self.dragging_item)
                    if c and len(c) >= 2:
                        self.canvas.coords(self.dragging_item, c[0] + dx, c[1] + dy)
                        self.canvas.update_idletasks()
                except Exception:
                    self.canvas.move(self.dragging_item, dx, dy)
            else:
                self.canvas.move(self.dragging_item, dx, dy)
            self.drag_start_pos = (event.x, event.y)
    def on_release(self, event):
        # Finish multi-eraser selection (left or right release) before other logic
        if self.model.get("multi_eraser_mode"):
            self.tools.finish_multi_erase_selection(event)
            return

        # Decide if we need to recompute door cuts BEFORE clearing drag state
        need_recut = False
        try:
            if self.dragging_item:
                tags = self.canvas.gettags(self.dragging_item)
                if "furniture" in tags:
                    # If a door furniture moved, restore previous wall and cut at new position
                    for furn in getattr(self.tools, "image_furniture_items", []) or []:
                        try:
                            if getattr(furn, "image_id", None) == self.dragging_item:
                                if getattr(self.tools, "_is_door_furniture", None) and self.tools._is_door_furniture(furn):
                                    need_recut = True
                                break
                        except Exception:
                            continue
            # IMPORTANT: dragging any group (room_group_ or polygon_group_) should NOT
            # trigger door recuts. Doors and walls/polygons move together, and existing
            # gaps should remain unchanged.
        except Exception:
            need_recut = False

        if self.dragging_item:
            self.actions.log({
                "type": "move",
                "item": self.dragging_item,
                "from": self.drag_origin_pos or self.drag_start_pos,
                "to": (event.x, event.y)
            })
        elif hasattr(self, 'dragging_group') and self.dragging_group:
            if self.dragging_group == getattr(self.tools, "_entire_layout_tag", None):
                self.actions.log({
                    "type": "move_group",
                    "tag": self.dragging_group,
                    "items": list(getattr(self, "_dragging_group_item_ids", set())),
                    "entire_layout": True,
                    "layout_scope": getattr(self.tools, "_entire_layout_state_scope", None),
                    "from": self.drag_origin_pos or self.drag_start_pos,
                    "to": (event.x, event.y),
                })
            elif self.dragging_group.startswith("line_") and self.initial_line_coords is not None:
                try:
                    line_item = None
                    for item in self.canvas.find_withtag(self.dragging_group):
                        if self.canvas.type(item) == "line":
                            line_item = item
                            break
                    current_coords = self.canvas.coords(line_item) if line_item else None
                except Exception:
                    current_coords = None
                if current_coords and len(current_coords) >= 4:
                    from_pos = (self.initial_line_coords[0], self.initial_line_coords[1])
                    to_pos = (current_coords[0], current_coords[1])
                    self.actions.log({
                        "type": "move_group",
                        "tag": self.dragging_group,
                        "from": from_pos,
                        "to": to_pos,
                    })
                else:
                    self.actions.log({
                        "type": "move_group",
                        "tag": self.dragging_group,
                        "from": self.drag_origin_pos or self.drag_start_pos,
                        "to": (event.x, event.y)
                    })
                self._sync_line_metadata(self.dragging_group)
            elif self.dragging_group.startswith("room_group_") and self.initial_room_bbox is not None:
                room_entity = self.tools.room_entities_by_group_tag.get(self.dragging_group)
                if room_entity and hasattr(room_entity, "rect_id"):
                    try:
                        current_coords = self.canvas.coords(room_entity.rect_id)
                    except Exception:
                        current_coords = None
                    if current_coords and len(current_coords) >= 4:
                        from_pos = (self.initial_room_bbox[0], self.initial_room_bbox[1])
                        to_pos = (current_coords[0], current_coords[1])
                        self.actions.log({
                            "type": "move_group",
                            "tag": self.dragging_group,
                            "from": from_pos,
                            "to": to_pos,
                        })
                    else:
                        self.actions.log({
                            "type": "move_group",
                            "tag": self.dragging_group,
                            "from": self.drag_origin_pos or self.drag_start_pos,
                            "to": (event.x, event.y)
                        })
                else:
                    self.actions.log({
                        "type": "move_group",
                        "tag": self.dragging_group,
                        "from": self.drag_origin_pos or self.drag_start_pos,
                        "to": (event.x, event.y)
                    })
            else:
                self.actions.log({
                    "type": "move_group",
                    "tag": self.dragging_group,
                    "from": self.drag_origin_pos or self.drag_start_pos,
                    "to": (event.x, event.y)
                })

        # Trigger dynamic door cutting after the drag ends.
        # Call recompute directly so walls always heal + recut, even if scheduling fails.
        if need_recut and hasattr(self.tools, "recompute_all_door_cuts"):
            try:
                self.tools.recompute_all_door_cuts()
            except Exception:
                pass

        # Clear room alignment guidelines
        if hasattr(self.tools, 'guideline_helper'):
            self.tools.guideline_helper.clear_guides()

        # Detected-room drag: the synthetic parity_room_drag:<id> group tagged
        # the polygon + label + the committed_line walls forming the boundary
        # so the colored fill moved together with the walls. Now resync the
        # line metadata for those walls and re-run planar-graph detection so
        # the overlay (with its persisted name + fill style) redraws cleanly
        # at the new wall positions.
        drag_group = self.dragging_group
        if drag_group and str(drag_group).startswith("parity_room_drag:"):
            try:
                seen_line_tags = set()
                for item in self.canvas.find_withtag(drag_group):
                    for t in self.canvas.gettags(item):
                        t_str = str(t)
                        if t_str.startswith("line_") and t_str not in seen_line_tags:
                            seen_line_tags.add(t_str)
                            self._sync_line_metadata(t_str)
                trigger = getattr(self.tools, "_trigger_room_detection", None)
                if callable(trigger):
                    trigger()
                else:
                    serializer = getattr(self.tools.actions, "serializer", None)
                    if serializer is not None and hasattr(serializer, "refresh_detected_room_overlay"):
                        serializer.refresh_detected_room_overlay()
            except Exception as exc:
                print(f"[drag] detected room refresh failed: {exc}")

        # Connected-wall-component drag (a bare loop moved as one shape): resync each wall's
        # metadata, drop the temporary tag so it never accumulates, and re-run detection so
        # a room is recognised at the new position. A fresh tag is built on the next press.
        if drag_group and str(drag_group).startswith("wall_component_"):
            try:
                for item in list(self.canvas.find_withtag(drag_group)):
                    for t in self.canvas.gettags(item):
                        t_str = str(t)
                        if t_str.startswith("line_"):
                            self._sync_line_metadata(t_str)
                self.canvas.dtag(drag_group, drag_group)
                trigger = getattr(self.tools, "_trigger_room_detection", None)
                if callable(trigger):
                    trigger()
            except Exception as exc:
                print(f"[drag] wall component refresh failed: {exc}")

        self.dragging_item = None
        self.dragging_group = None
        self.drag_start_pos = None
        self.drag_origin_pos = None
        self.initial_room_bbox = None
        self.initial_line_coords = None
        self._drag_anchor = None
        self._guide_candidates = None

    def _prevent_room_overlap(self, x0, y0, width, height, other_rooms, epsilon=0.5):
        """Nudge a dragged room out of any neighbour it would penetrate.

        Returns a corrected top-left. For each overlapping neighbour the room is pushed
        along the axis of *least* penetration, so it settles flush against the wall it
        came in through rather than jumping around it. Touching edges (zero overlap) are
        allowed — that is exactly the flush result snapping aims for. A couple of passes
        settle the common case of being wedged between two rooms.
        """
        for _pass in range(3):
            moved = False
            for _tag, other in other_rooms:
                try:
                    other_coords = self.canvas.coords(getattr(other, "rect_id", None))
                except Exception:
                    continue
                if not other_coords or len(other_coords) < 4:
                    continue
                ox0, oy0, ox1, oy1 = other_coords[:4]
                x1, y1 = x0 + width, y0 + height
                overlap_x = min(x1, ox1) - max(x0, ox0)
                overlap_y = min(y1, oy1) - max(y0, oy0)
                if overlap_x <= epsilon or overlap_y <= epsilon:
                    continue  # not penetrating (or merely touching)
                # Four ways out; take the shortest.
                candidates = (
                    (abs(ox0 - x1), "x", ox0 - width),  # push left of neighbour
                    (abs(ox1 - x0), "x", ox1),          # push right of neighbour
                    (abs(oy0 - y1), "y", oy0 - height), # push above neighbour
                    (abs(oy1 - y0), "y", oy1),          # push below neighbour
                )
                _dist, axis, value = min(candidates, key=lambda c: c[0])
                if axis == "x":
                    x0 = value
                else:
                    y0 = value
                moved = True
            if not moved:
                break
        return x0, y0

    def _show_alignment_guides(self, group, bounds=None, snap_info=None, other_rooms=None,
                               epsilon=1.5):
        """Dashed alignment guides for whatever is being dragged, on every drag path.

        Guides used to be drawn only on the Room-tool path, and only for alignments that
        path's own `snap_info` knew about — so they disappeared for detected rooms, bare
        wall loops, Room-tool rooms meeting draw-tool geometry, and any room pushed flush
        by the overlap guard. Here the flush edges are read back from the canvas *after*
        the move, against the same candidate set that drives snapping, so a guide appears
        exactly when the geometry is aligned regardless of which tool made it. A tool's
        `snap_info` is merged in rather than replaced, so the Room tool keeps its
        centre-line and distance guides.
        """
        helper = getattr(self.tools, "guideline_helper", None)
        if helper is None:
            return
        # Guides are cosmetic: a failure here must never disturb the drag itself (the
        # Room-tool caller treats an exception as "snapping failed" and re-moves the room).
        try:
            if bounds is None:
                bounds = self._dragged_group_bounds(group)
            if bounds is None:
                helper.clear_guides()
                return

            # Nothing but the dragged group moves mid-drag: gather neighbour edges once.
            cached = getattr(self, "_guide_candidates", None)
            if not cached or cached[0] != group:
                self._drop_dead_guide_pool(helper)
                cached = (group, *self._snap_candidates(group))
                self._guide_candidates = cached
            edge_xs, edge_ys = cached[1], cached[2]

            info = dict(snap_info or {})
            align_x = self._flush_edge(edge_xs, bounds[0], bounds[2], epsilon)
            if align_x is not None:
                info["has_left_align"] = True
                info["align_x"] = align_x
            align_y = self._flush_edge(edge_ys, bounds[1], bounds[3], epsilon)
            if align_y is not None:
                info["has_top_align"] = True
                info["align_y"] = align_y

            helper.draw_room_alignment_guides(bounds, info, other_rooms)
        except Exception:
            return
        # Guide items are pooled, so they are created during the first drag of the session
        # and any room drawn later stacks above them — an opaque room fill then hides the
        # dashes. Raising on every draw keeps them visible for the whole session.
        for tag in ("guideline_room", "guideline_room_center"):
            try:
                self.canvas.tag_raise(tag)
            except Exception:
                pass

    def _drop_dead_guide_pool(self, helper):
        """Forget pooled guide items that no longer exist on the canvas.

        `GuidelineHelper` reuses its canvas items forever, but a full wipe
        (`canvas.delete("all")` on New/Clear layout, `view.reset_grid_pool()`'s
        counterpart) destroys them while the pool keeps the dead ids. Tk silently ignores
        `coords`/`itemconfig` on a dead id, so the helper "reused" ghosts and no guide was
        ever drawn again for the rest of the session — the main reason guides came and
        went. Pruning here lets the helper recreate them, without touching the helper.
        """
        for name in ("line_pool", "arc_pool", "oval_pool", "text_pool"):
            items = getattr(helper, name, None)
            if not items:
                continue
            alive = [item for item in items if self.canvas.type(item) is not None]
            if len(alive) != len(items):
                setattr(helper, name, alive)

    @staticmethod
    def _flush_edge(candidates, low, high, epsilon):
        """Nearest neighbour edge that either side of the dragged bounds sits on, else None."""
        best = None
        for value in candidates:
            distance = min(abs(value - low), abs(value - high))
            if distance <= epsilon and (best is None or distance < best[0]):
                best = (distance, value)
        return best[1] if best else None

    def _room_bounds(self, item) -> tuple | None:
        """Bounds of a canvas item from its own coordinates (never its text extents)."""
        try:
            coords = self.canvas.coords(item)
        except Exception:
            return None
        if not coords or len(coords) < 4:
            return None
        xs = [float(v) for v in coords[0::2]]
        ys = [float(v) for v in coords[1::2]]
        return min(xs), min(ys), max(xs), max(ys)

    def _snap_room_delta(self, group, dx, dy, tolerance=10.0, breakaway=15.0):
        """Nudge a drag delta so the dragged room's edges land flush on nearby geometry.

        `dx`/`dy` are per-event increments of a few pixels, because `on_drag` resets
        `drag_start_pos` on every motion event. Snapping those increments directly cannot
        hold an alignment: once the room is flush, the next increment moves it off the
        edge and the room oscillates instead of sticking. So the increments are summed
        into a pointer offset from a drag anchor, the resulting *absolute* desired
        position is snapped, and the chosen edge is held until the pointer is more than
        `breakaway` px past it (that hysteresis is what makes it feel magnetic).

        Reads geometry only: room detection and the overlay pipeline are untouched.
        Returns the original delta when nothing is close enough.
        """
        try:
            bounds = self._dragged_group_bounds(group)
            if bounds is None:
                return dx, dy

            anchor = getattr(self, "_drag_anchor", None)
            if anchor is None or anchor["group"] != group:
                # First motion of this drag: the room has not moved yet, so its current
                # bounds are the anchor. Nothing else moves mid-drag, so the candidate
                # edges are gathered once instead of on every event.
                edge_xs, edge_ys = self._snap_candidates(group)
                anchor = {
                    "group": group, "bounds": bounds, "offset": [0.0, 0.0],
                    "xs": edge_xs, "ys": edge_ys, "lock": [None, None],
                }
                self._drag_anchor = anchor

            anchor["offset"][0] += dx
            anchor["offset"][1] += dy
            base, (off_x, off_y) = anchor["bounds"], anchor["offset"]
            desired = (base[0] + off_x, base[1] + off_y, base[2] + off_x, base[3] + off_y)

            # Either edge of the room may land on any candidate, so rooms can meet
            # edge-to-edge or line up flush on the same side; x and y are independent.
            shift_x, anchor["lock"][0] = self._snap_axis(
                desired[0], desired[2], anchor["xs"], anchor["lock"][0], tolerance, breakaway,
            )
            shift_y, anchor["lock"][1] = self._snap_axis(
                desired[1], desired[3], anchor["ys"], anchor["lock"][1], tolerance, breakaway,
            )
            # Move from where the room actually is to the snapped desired position.
            return desired[0] + shift_x - bounds[0], desired[1] + shift_y - bounds[1]
        except Exception:
            return dx, dy

    @staticmethod
    def _snap_axis(low, high, candidates, lock, tolerance, breakaway):
        """Shift that puts one axis flush, plus the edge to stay locked to.

        `lock` is `(side, coordinate)`: which edge of the room is snapped, and to what.
        Keeping it until the pointer-driven position drifts past `breakaway` stops the
        room flickering in and out of alignment at the tolerance boundary.
        """
        if lock is not None:
            mine = low if lock[0] == 0 else high
            if abs(lock[1] - mine) <= breakaway:
                return lock[1] - mine, lock
        best = None
        for side, mine in ((0, low), (1, high)):
            for theirs in candidates:
                shift = theirs - mine
                if abs(shift) <= tolerance and (best is None or abs(shift) < abs(best[0])):
                    best = (shift, (side, theirs))
        return best if best is not None else (0.0, None)

    def _dragged_group_bounds(self, group):
        """Bounds of the room being dragged, from its overlay or its own walls."""
        items = self.canvas.find_withtag(group)
        if not items:
            return None
        overlay = next(
            (
                item for item in items
                if self.canvas.type(item) == "polygon"
                and "parity_detected_room" in self.canvas.gettags(item)
            ),
            None,
        )
        if overlay is not None:
            return self._room_bounds(overlay)
        # No overlay (an open shape, or one still being edited): fall back to the walls.
        boxes = [
            self._room_bounds(item) for item in items
            if self.canvas.type(item) in ("line", "polygon", "rectangle")
        ]
        boxes = [box for box in boxes if box]
        if not boxes:
            return None
        return (
            min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes),
        )

    def _snap_candidates(self, exclude_group):
        """Edge coordinates worth snapping to: any wall or room not being dragged.

        Detected rooms alone are not enough — a neighbour may be an open shape or a
        single wall that never became a room, and the user still expects it to snap.
        """
        dragged = set(self.canvas.find_withtag(exclude_group))
        xs, ys = set(), set()

        def add(bounds):
            if bounds:
                xs.update((bounds[0], bounds[2]))
                ys.update((bounds[1], bounds[3]))

        for item in self.canvas.find_withtag("line"):
            try:
                if item in dragged or self.canvas.type(item) != "line":
                    continue
                if "grid" in self.canvas.gettags(item):
                    continue
            except Exception:
                continue
            add(self._room_bounds(item))
        for item in self.canvas.find_withtag("parity_detected_room"):
            try:
                if item in dragged or self.canvas.type(item) != "polygon":
                    continue
            except Exception:
                continue
            add(self._room_bounds(item))
        for tag, room in getattr(self.tools, "room_entities_by_group_tag", {}).items():
            if tag == exclude_group or not hasattr(room, "rect_id"):
                continue
            add(self._room_bounds(room.rect_id))
        return xs, ys

    def _wall_component_drag_tag(self, seed_item):
        """Tag the whole connected run of walls touching `seed_item` so a hand-drawn shape
        drags as one piece instead of tearing apart wall by wall.

        Connectivity is either endpoint coincidence (the outer loop's corners) or an
        endpoint lying on another wall's span (a T-junction, so a divider travels with its
        room). Two rooms that merely sit near each other are separate components, so one can
        still be dragged toward the other to snap; two that already share a wall are one
        shape and move together. Returns a temp group tag, or None to fall back to the
        single wall (nothing else connected).
        """
        try:
            walls = [
                it for it in self.canvas.find_withtag("committed_line")
                if self.canvas.type(it) == "line" and "grid" not in self.canvas.gettags(it)
            ]
            segs = {}
            for it in walls:
                c = self.canvas.coords(it)
                if len(c) >= 4:
                    segs[it] = ((c[0], c[1]), (c[2], c[3]))
            if seed_item not in segs:
                return None
            tol = 6.0
            dist = self.tools._point_to_segment_distance

            def touches(a, b):
                (a0, a1), (b0, b1) = a, b
                return (
                    dist(a0, b0, b1) <= tol or dist(a1, b0, b1) <= tol
                    or dist(b0, a0, a1) <= tol or dist(b1, a0, a1) <= tol
                )

            seen = {seed_item}
            stack = [seed_item]
            while stack:
                cur = stack.pop()
                for it in walls:
                    if it not in seen and it in segs and touches(segs[cur], segs[it]):
                        seen.add(it)
                        stack.append(it)
            if len(seen) <= 1:
                return None

            tag = f"wall_component_{self._wall_component_seq}"
            self._wall_component_seq += 1
            for it in seen:
                line_grp = next(
                    (t for t in self.canvas.gettags(it) if str(t).startswith("line_")), None
                )
                # Tag the wall's whole line_<uuid> group (line + label + endpoint) so the
                # measurement text and markers travel with the wall, not just the segment.
                members = self.canvas.find_withtag(line_grp) if line_grp else (it,)
                for member in members:
                    self.canvas.addtag_withtag(tag, member)
            return tag
        except Exception:
            return None

    def _sync_line_metadata(self, line_group_tag: str) -> None:
        if not line_group_tag or not line_group_tag.startswith("line_"):
            return
        if not hasattr(self.tools, "line_metadata"):
            return
        metadata = self.tools.line_metadata.get(line_group_tag)
        if not metadata:
            return
        try:
            line_item = None
            for item in self.canvas.find_withtag(line_group_tag):
                if self.canvas.type(item) == "line":
                    line_item = item
                    break
            if not line_item:
                return
            coords = self.canvas.coords(line_item)
            if not coords or len(coords) < 4:
                return
            x0, y0, x1, y1 = coords[0], coords[1], coords[2], coords[3]
            metadata.update({"x0": x0, "y0": y0, "x1": x1, "y1": y1})
            from drawing_helpers import get_distance_label
            label_text, mid_x, mid_y = get_distance_label(
                x0, y0, x1, y1, self.model.unit, self.model.zoom_level
            )
            label_id = metadata.get("label")
            if label_id:
                self.canvas.coords(label_id, mid_x, mid_y - 10)
                self.canvas.itemconfig(label_id, text=label_text)
            point_id = metadata.get("point")
            if point_id:
                self.canvas.coords(point_id, x1 - 0.5, y1 - 0.5, x1 + 0.5, y1 + 0.5)
        except Exception:
            return

    def on_mousewheel(self, event):
        scale = 1.1 if event.delta > 0 else 0.9
        # Anchor zoom around the mouse cursor for stable canvasx/canvasy mapping.
        try:
            self.view.apply_zoom(scale, float(event.x), float(event.y))
        except Exception:
            # Fallback for platforms where event.x/event.y may be missing.
            self.view.apply_zoom(scale)

        # Refresh the polygon/line previews immediately after zooming
        try:
            dragging_now = False
            try:
                dragging_now = (getattr(self, "dragging_item", None) is not None) or bool(
                    getattr(self, "dragging_group", None)
                )
            except Exception:
                pass
            if not dragging_now:
                if self.model.get("polygon_mode"):
                    self.tools.update_polygon_preview(event)
                elif self.model.get("vastu_polygon_mode"):
                    self.tools.update_vastu_polygon_preview(event)
                elif self.model.get("drawing_enabled"):
                    self.tools.update_line_preview(event)
        except Exception:
            pass

    def _click_hits_draggable_item(self, event, *, for_line_drawing=False):
        """Return True if the click overlaps a draggable item (text, room, polygon, furniture).
        When for_line_drawing=True, room/polygon are ignored so lines can be drawn inside them."""
        items = self.canvas.find_overlapping(event.x - 5, event.y - 5, event.x + 5, event.y + 5)
        if not items:
            return False
        for candidate in reversed(items):
            try:
                tags = set(self.canvas.gettags(candidate))
                if "grid" in tags:
                    continue
                if "user_text_editing" in tags and "user_text" in tags:
                    return True
                if not for_line_drawing and any(
                    t.startswith("room_group_") or t.startswith("polygon_group_") for t in tags
                ):
                    return True
                if (
                    not for_line_drawing
                    and (
                        "vastu_group" in tags
                        or any(
                            t.startswith("vastu_zone_")
                            for t in tags
                            if t not in ("vastu_zone_fill", "vastu_zone_label")
                        )
                    )
                ):
                    return True
                if any(t.startswith("line_") for t in tags):
                    return True
                if "furniture" in tags or "compass" in tags:
                    return True
                if self.canvas.type(candidate) == "image":
                    # Furniture image should remain draggable in all modes, but flooring
                    # should not block free line drawing inside rooms/polygons.
                    if "furniture" in tags:
                        return True
                    if not for_line_drawing and "flooring" in tags:
                        return True
            except Exception:
                continue
        return False

    def select_item(self, event):
        items = tuple(
            item for item in self.canvas.find_overlapping(
                event.x - 5, event.y - 5, event.x + 5, event.y + 5
            )
            if "parity_floor_underlay" not in self.canvas.gettags(item)
        )
        if not items:
            return

        if getattr(self.tools, "layout_move_mode", False) and getattr(self.tools, "_entire_layout_tag", None):
            self.dragging_item = None
            self.dragging_group = self.tools._entire_layout_tag
            self._dragging_group_item_ids = set(self.canvas.find_withtag(self.dragging_group))
            self.drag_start_pos = (event.x, event.y)
            self.drag_origin_pos = (event.x, event.y)
            return

        for candidate in reversed(items):
            window = next(
                (entry for entry in self.tools.windows if candidate in entry.get("item_ids", [])),
                None,
            )
            if window:
                self.dragging_item = None
                self.dragging_group = None
                self.selected_group_tag = None
                self.tools.select_window(window)
                return

        selected_furniture = getattr(self.tools, "selected_furniture_obj", None)
        if selected_furniture and getattr(selected_furniture, "image_id", None) not in items:
            self.tools.clear_furniture_selection()

        top_item = items[-1]
        tags = self.canvas.gettags(top_item)

        # Measurement selection (dimension labels/arrows)
        for candidate in reversed(items):
            ctags = self.canvas.gettags(candidate)
            if "dimension_item" in ctags:
                # Prioritize specific edge tags over the general group tag
                dim_tag = next((t for t in ctags if "_edge_" in t), None)
                if not dim_tag:
                    dim_tag = next((t for t in ctags if t.endswith("__dims")), None)
                
                if dim_tag:
                    self._select_dimension(dim_tag)
                    # Don't return, allow dragging if it's also a draggable item (unlikely for dims)
                    # but we want to mark it as selected.
                    break

        # Prefer user-editable text when present under the pointer.
        # This fixes cases where a room/polygon/wall segment sits above the text in z-order
        # after redraws, preventing text from being draggable even in edit mode.
        try:
            preferred_text = None
            for candidate in reversed(items):
                try:
                    if self.canvas.type(candidate) != "text":
                        continue
                    ctags = set(self.canvas.gettags(candidate))
                    if "user_text_editing" in ctags and "user_text" in ctags:
                        preferred_text = candidate
                        break
                except Exception:
                    continue
            if preferred_text is not None:
                top_item = preferred_text
                tags = self.canvas.gettags(top_item)
        except Exception:
            pass

        # If top_item is a locked furniture (committed and not in edit mode), skip it for
        # left-click so user must right-click → Edit first. This also lets the underlying
        # room/polygon be selected and dragged instead of the furniture image itself.
        try:
            locked_ids = set()
            for furn in getattr(self.tools, "image_furniture_items", []) or []:
                try:
                    if not hasattr(furn, "image_id"):
                        continue
                    if getattr(furn, "committed", False) and not getattr(furn, "editing", False):
                        locked_ids.add(furn.image_id)
                except Exception:
                    continue
            if top_item in locked_ids:
                replacement = None
                for candidate in reversed(items):
                    if candidate == top_item:
                        continue
                    if candidate in locked_ids:
                        continue
                    replacement = candidate
                    break
                if replacement is None:
                    return
                top_item = replacement
                tags = self.canvas.gettags(top_item)
        except Exception:
            pass

        # Vastu slice hit-test: in slices-only mode, the user often clicks on division lines
        # that sit above the colored zone polygons. Prefer selecting a zone from the
        # overlapping stack so the expected slice moves.
        try:
            slices_only = bool(getattr(self.model, "get", lambda _k: False)("vastu_move_slices_only"))
        except Exception:
            slices_only = False
        if slices_only:
            try:
                zone_candidate = None
                for candidate in reversed(items):
                    ctags = self.canvas.gettags(candidate)
                    if any(
                        t.startswith("vastu_zone_")
                        and t not in ("vastu_zone_fill", "vastu_zone_label")
                        for t in ctags
                    ):
                        zone_candidate = candidate
                        break
                if zone_candidate is not None:
                    top_item = zone_candidate
                    tags = self.canvas.gettags(top_item)
            except Exception:
                pass

        # If user clicks on a flooring image, attach it to the underlying polygon group
        # so dragging moves polygon + flooring together.
        if (
            self.canvas.type(top_item) == "image"
            and "flooring" in tags
            and not any(t.startswith("room_group_") or t.startswith("polygon_group_") for t in tags)
        ):
            try:
                underlying_poly = None
                for candidate in reversed(items[:-1]):
                    ctags = self.canvas.gettags(candidate)
                    if self.canvas.type(candidate) == "polygon" and "closed_shape" in ctags:
                        underlying_poly = candidate
                        break

                if underlying_poly is not None:
                    poly_tags = self.canvas.gettags(underlying_poly)
                    group = next((t for t in poly_tags if t.startswith("polygon_group_")), None)
                    if not group:
                        group = self.tools.ensure_polygon_grouping(underlying_poly)
                    if group:
                        # Merge group tag onto the flooring image, so group dragging works
                        try:
                            self.tools._merge_item_tags(top_item, (group,))
                        except Exception:
                            # Fallback: overwrite tags if helper is unavailable
                            self.canvas.itemconfig(top_item, tags=tuple(set(tags) | {group}))
                        tags = tuple(set(tags) | {group})
            except Exception:
                pass

        # Backward-compat: if user clicks an old polygon, retro-tag it + its vertex dots/label
        if (
            self.canvas.type(top_item) == "polygon"
            and "closed_shape" in tags
            and not any(t.startswith("polygon_group_") for t in tags)
        ):
            try:
                new_group = self.tools.ensure_polygon_grouping(top_item)
                tags = tuple(set(tags) | {new_group})
            except Exception:
                pass

        # Check if it's a committed furniture item - if so, use its group tag
        furniture_group_tag = None
        for furniture in self.tools.image_furniture_items:
            if hasattr(furniture, 'image_id') and furniture.image_id == top_item:
                # Check if furniture is committed and has a group tag
                if getattr(furniture, "committed", False) and hasattr(furniture, "committed_group_tag"):
                    furniture_group_tag = getattr(furniture, "committed_group_tag", None)
                break
        
        # Check if it's part of a group (room or polygon)
        group_tag = next(
            (
                tag
                for tag in tags
                if tag.startswith("room_group_") or tag.startswith("polygon_group_")
            ),
            None,
        )
        # Detected-room overlay (from "Lines → Room") exposes a synthetic
        # parity_room_drag:<entity_id> tag on the polygon, label, and the
        # underlying committed_line walls so dragging moves the entire room
        # as a unit and the colored fill no longer detaches from the boundary.
        parity_room_tag = next(
            (t for t in tags if str(t).startswith("parity_room_drag:")),
            None,
        )
        zone_tag = next(
            (
                t
                for t in tags
                if t.startswith("vastu_zone_") and t not in ("vastu_zone_fill", "vastu_zone_label")
            ),
            None,
        )
        slices_only = bool(getattr(self.model, "get", lambda _k: False)("vastu_move_slices_only"))

        # In slices-only mode, dragging should ONLY apply to a zone. Clicking other Vastu items
        # (division lines, outline, markers) should not trigger whole-group dragging.
        if slices_only and ("vastu_group" in tags) and not zone_tag:
            return

        if slices_only and zone_tag:
            # Drag only the selected slice (zone) in slices-only mode.
            vastu_group_tag = zone_tag
        else:
            vastu_group_tag = "vastu_group" if "vastu_group" in tags else None
        line_group_tag = next((tag for tag in tags if tag.startswith("line_")), None)
        is_label_text = self.canvas.type(top_item) == "text"
        is_room_label = is_label_text and group_tag is not None
        is_line_label = is_label_text and "line_label" in tags
        compass_group_tag = "compass" if "compass" in tags else None

        # Line measurement labels should not themselves start a drag –
        # user must grab the line or endpoints instead.
        if is_line_label:
            line_group_for_drag = None
        else:
            line_group_for_drag = line_group_tag

        # Use furniture's group tag if available, otherwise use the tag from canvas item.
        # A detected-room drag group (parity_room_drag:<id>) takes precedence over the
        # individual line_ tag on the wall: clicking a wall that belongs to a detected
        # (line-loop) room must move the entire room (polygon + label + all boundary
        # walls) together, otherwise the colored fill detaches from the boundary.
        if parity_room_tag:
            final_group_tag = parity_room_tag
        else:
            final_group_tag = (
                furniture_group_tag
                or group_tag
                or compass_group_tag
                or vastu_group_tag
                or line_group_for_drag
            )

        # If user is in whole-move mode and starts dragging Vastu, snap any moved slices back first
        if (not slices_only) and final_group_tag == "vastu_group":
            try:
                self.tools.reset_vastu_slices()
            except Exception:
                pass
        
        # A DETECTED room drags by its own parity_room_drag group (just that room's boundary
        # walls + its overlay), so two separate rooms — even overlapping or snapped flush —
        # detach and keep their own identity/colour. Only a BARE wall (a line loop the
        # detector never turned into a room) needs connected-component grouping, or it tears
        # apart one wall at a time. Grouping detected rooms by physical touch was wrong: it
        # fused any two rooms whose walls cross/coincide, so they could not be pulled apart
        # and re-detection dropped their name/colour.
        if final_group_tag and final_group_tag == line_group_for_drag and not parity_room_tag:
            seed = top_item if (
                self.canvas.type(top_item) == "line" and "committed_line" in tags
            ) else next(
                (i for i in self.canvas.find_withtag(final_group_tag)
                 if self.canvas.type(i) == "line" and "committed_line" in self.canvas.gettags(i)),
                None,
            )
            if seed is not None:
                component_tag = self._wall_component_drag_tag(seed)
                if component_tag:
                    final_group_tag = component_tag

        if final_group_tag:
            self.dragging_item = None
            self.dragging_group = final_group_tag
            # Cache item IDs for faster move checks in on_drag
            self._dragging_group_item_ids = set(self.canvas.find_withtag(final_group_tag))
            try:
                self.tools._cancel_line_input()
            except Exception:
                pass
            if final_group_tag.startswith("room_group_"):
                self.selected_group_tag = final_group_tag
            elif final_group_tag.startswith("line_"):
                self.selected_group_tag = None
            else:
                self.selected_group_tag = None

            # Store initial room bbox for alignment if dragging a room
            if final_group_tag.startswith("room_group_"):
                room_entity = self.tools.room_entities_by_group_tag.get(final_group_tag)
                if room_entity and hasattr(room_entity, 'rect_id'):
                    try:
                        coords = self.canvas.coords(room_entity.rect_id)
                        if coords and len(coords) >= 4:
                            self.initial_room_bbox = tuple(coords)
                    except Exception:
                        pass
            elif final_group_tag.startswith("line_"):
                try:
                    line_item = None
                    if self.canvas.type(top_item) == "line":
                        line_item = top_item
                    else:
                        for item in self.canvas.find_withtag(final_group_tag):
                            if self.canvas.type(item) == "line":
                                line_item = item
                                break
                    if line_item:
                        coords = self.canvas.coords(line_item)
                        if coords and len(coords) >= 4:
                            self.initial_line_coords = tuple(coords)
                except Exception:
                    self.initial_line_coords = None
        else:
            if is_label_text:
                # Allow moving user-inserted text, but protect "system" labels
                # such as grid labels, line measurement labels, temporary measure text, etc.
                protected_text_tags = {
                    "grid",
                    "line_label",
                    "guideline_info",
                    "measure_temp",
                    "active_text",      # text tool overlay (should not be dragged as a real item)
                    "vastu_zone_label",  # Vastu labels should move with the group/zone logic
                }
                try:
                    if any(t in protected_text_tags for t in tags):
                        return
                    # "Same like furniture": only allow dragging text after user explicitly
                    # enters edit mode via right-click -> Edit Text.
                    if "user_text_editing" not in tags:
                        return
                except Exception:
                    return

            self.dragging_item = top_item
            self.dragging_group = None
            self.selected_group_tag = None
            try:
                self.tools._cancel_line_input()
            except Exception:
                pass

        self.drag_start_pos = (event.x, event.y)
        # A new press starts a new drag, so the room-snap anchor must be rebuilt from
        # this press rather than inherited from the previous drag of the same room.
        self._drag_anchor = None
        self._guide_candidates = None

        # ✅ Furniture selection only happens on right-click, not left-click
        # Left-click on furniture only allows dragging, selection is handled by right-click context menu
        
    
    def on_key_press(self, event):
        if event.keysym == "Delete" and self.tools.delete_selected():
            return "break"

        obj = self.tools.selected_furniture_obj
        # Furniture controls (rotate, resize, flip) — only when focus is on canvas.
        # Do not steal focus from sidebar entries (Room name, Length, Breadth); let user type there.
        if obj:
            try:
                if event.widget is not self.canvas:
                    return  # Let key go to focused widget (e.g. CTkEntry in sidebar)
            except Exception:
                pass
            # Commit furniture to underlying polygon/room group (so it moves with the group)
            if event.keysym in ("Return", "KP_Enter"):
                try:
                    # If already committed/locked, do not re-commit. User must right-click to edit first.
                    if getattr(obj, "committed", False) and not getattr(obj, "editing", False):
                        print("ℹ️ Furniture is committed. Right-click it to edit, then press Enter to commit again.")
                        return

                    ok = self.tools.commit_furniture_to_underlying_group(obj)
                    if not ok:
                        print("⚠️ No polygon/room found under furniture to commit.")
                except Exception as e:
                    print(f"⚠️ Commit failed: {e}")
                return

            if event.char == "r":
                self.tools.rotate_selected_furniture(clockwise=True)
                return "break"
            elif event.char == "R":
                self.tools.rotate_selected_furniture_counterclockwise()
                return "break"
            elif event.char == "0":
                self.tools.reset_selected_furniture_rotation()
                return "break"
            elif event.char == "f":
                obj.flip_horizontal()
                return "break"
            elif event.char == "v":
                obj.flip_vertical()
                return "break"
            elif event.char in ("+", "="):
                self.tools.enter_furniture_edit_mode(obj)
                obj.resize(1.1)
                return "break"
            elif event.char in ("-", "_"):
                self.tools.enter_furniture_edit_mode(obj)
                obj.resize(0.9)
                return "break"
            elif event.keysym == "Delete":
                is_door = self.tools._is_door_furniture(obj)
                self.tools.delete_furniture_item(obj)
                if is_door:
                    self.tools.recompute_all_door_cuts()
                return "break"  # Stop propagation to entry widgets

        # Handle selected dimension deletion
        if event.keysym == "Delete":
            if hasattr(self, "selected_dimension_tag") and self.selected_dimension_tag:
                self._delete_dimension(self.selected_dimension_tag)
                return "break"

        # Global shortcuts (independent of selection)
        if event.keysym == "Escape":
            self.tools.reset_modes()
            # Clear measurement selection
            if hasattr(self, "selected_dimension_tag") and self.selected_dimension_tag:
                try:
                    self.canvas.itemconfig(self.selected_dimension_tag, width=1)
                except Exception:
                    pass
                self.selected_dimension_tag = None
        elif event.keysym == "Delete":
            if self.selected_group_tag and self.selected_group_tag.startswith("room_group_"):
                self.tools.delete_room_by_group(self.selected_group_tag)
                self.selected_group_tag = None
                return "break"
        elif event.state & 0x4:  # Ctrl key held
            if event.keysym.lower() == "c":
                self.tools.copy_selected_item()
            elif event.keysym.lower() == "v":
                self.tools.prepare_to_paste_item()
        
    def on_right_click(self, event):
        """
        Record start position for panning or multi-erase.
        Context menu is deferred until ButtonRelease to see if user panned.
        """
        if self.tools.canvas_frozen:
            return

        # Right-click is the explicit finish/cancel gesture for continuous Line mode.
        if self.model.get("drawing_enabled"):
            self._right_click_cancelled_line = True
            self.tools._cancel_line_input()
            self.model.set("drawing_enabled", False)
            self.canvas.config(cursor="arrow")
            return "break"
        self._right_click_cancelled_line = False

        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._is_panning = False

        # In multi-eraser mode, right-click begins selection rectangle immediately.
        if self.model.get("multi_eraser_mode"):
            self.tools.start_multi_erase_selection(event)

    def on_right_drag(self, event):
        """Handle panning or multi-eraser selection."""
        if self.tools.canvas_frozen:
            return

        if self.model.get("multi_eraser_mode"):
            self.tools.update_multi_erase_selection(event)
            return

        # Panning logic
        if self._pan_start_x is not None:
            dx = event.x - self._pan_start_x
            dy = event.y - self._pan_start_y

            # Threshold (3px) to differentiate between click and pan
            if not self._is_panning and (abs(dx) > 3 or abs(dy) > 3):
                self._is_panning = True

            if self._is_panning:
                self._pan_canvas(dx, dy)
                self._pan_start_x = event.x
                self._pan_start_y = event.y

    def _pan_canvas(self, dx, dy):
        """Move the canvas view based on widget-space pixel delta."""
        try:
            sr = self.canvas.cget("scrollregion")
            parts = str(sr or "").split()
            if len(parts) < 4:
                return
            x0, y0, x1, y1 = map(float, parts)
            total_w = max(1.0, x1 - x0)
            total_h = max(1.0, y1 - y0)

            # View move is opposite to drag
            dfx = -dx / total_w
            dfy = -dy / total_h

            xv0, xv1 = self.canvas.xview()
            yv0, yv1 = self.canvas.yview()

            self.canvas.xview_moveto(xv0 + dfx)
            self.canvas.yview_moveto(yv0 + dfy)
            
            # Update grid to show lines/labels for newly visible area during pan
            if hasattr(self.view, "schedule_grid_redraw"):
                self.view.schedule_grid_redraw(delay_ms=0)
        except Exception:
            pass

    def on_right_release(self, event):
        """Finish panning or multi-eraser; show context menu if no pan occurred."""
        if self.tools.canvas_frozen:
            return

        if getattr(self, "_right_click_cancelled_line", False):
            self._right_click_cancelled_line = False
            self._pan_start_x = None
            self._pan_start_y = None
            self._is_panning = False
            return "break"

        if self.model.get("multi_eraser_mode"):
            self.tools.finish_multi_erase_selection(event)
            return

        # If it was a simple click (not a pan), show context menus
        if not self._is_panning:
            self._handle_right_click_context_menu(event)

        self._pan_start_x = None
        self._pan_start_y = None
        self._is_panning = False

    def _handle_right_click_context_menu(self, event):
        """Original right-click context menu logic."""
        items = self.canvas.find_overlapping(event.x - 5, event.y - 5, event.x + 5, event.y + 5)
        if not items:
            return

        # User text context menu
        try:
            protected = {"grid", "line_label", "guideline_info", "measure_temp", "active_text", "vastu_zone_label"}
            for item in reversed(items):
                if self.canvas.type(item) != "text":
                    continue
                tags = self.canvas.gettags(item)
                if "user_text" not in tags:
                    continue
                if any(t in protected for t in tags):
                    continue
                if any(t.startswith(("room_group_", "polygon_group_", "line_")) for t in tags):
                    continue
                self._show_user_text_context_menu(event, item)
                return
        except Exception:
            pass

        # Dimension context menu (Measurement labels/arrows)
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            if "dimension_item" in tags:
                # Prioritize specific edge tags over the general group tag
                dim_tag = next((t for t in tags if "_edge_" in t), None)
                if not dim_tag:
                    dim_tag = next((t for t in tags if t.endswith("__dims")), None)

                if dim_tag:
                    self._show_dimension_context_menu(event, dim_tag)
                    return

        # topmost line context menu
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            if "committed_line" in tags or "line" in tags:
                line_tag = next((t for t in tags if t.startswith("line_")), None)
                if line_tag and hasattr(self.tools, 'line_metadata') and line_tag in self.tools.line_metadata:
                    self._show_line_context_menu(event, item, line_tag)
                    return

        # Room context menu
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            group_tag = next((t for t in tags if t.startswith("room_group_")), None)
            if group_tag:
                self._show_room_context_menu(event, group_tag)
                return

    def _show_dimension_context_menu(self, event, dim_tag):
        """Show context menu for a measurement group with Delete option."""
        # Highlight it visually first
        self._select_dimension(dim_tag)
        
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Delete Measurement", 
                         command=lambda: self._delete_dimension(dim_tag))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _select_dimension(self, dim_tag):
        """Highlight a measurement group."""
        # Deselect previous
        if hasattr(self, "selected_dimension_tag") and self.selected_dimension_tag:
            try:
                self.canvas.itemconfig(self.selected_dimension_tag, width=1)
            except Exception: pass
            
        self.selected_dimension_tag = dim_tag
        # Highlight by making lines thicker
        try:
            self.canvas.itemconfig(dim_tag, width=2.5)
            # Find the text bg items and highlight them too if any
            for item in self.canvas.find_withtag(dim_tag):
                if "dimension_text_bg" in self.canvas.gettags(item):
                    self.canvas.itemconfig(item, outline="#e63946", width=1)
        except Exception:
            pass
        print(f"📏 Measurement selected: {dim_tag}")

    def _delete_dimension(self, dim_tag):
        """Delete all items in a measurement group."""
        if hasattr(self.tools, "dimension_drawer"):
            # Log for undo/redo
            try:
                # dim_tag is e.g. "room_group_1__dims_edge_0"
                parts = dim_tag.split("__dims_edge_")
                if len(parts) == 2:
                    group_tag = parts[0]
                    edge_idx = int(parts[1])
                    
                    points = None
                    if hasattr(self.tools, "room_entities_by_group_tag"):
                        room = self.tools.room_entities_by_group_tag.get(group_tag)
                        if room:
                            if hasattr(room, "points") and room.points:
                                points = room.points
                            else:
                                # Rectangular room fallback
                                try:
                                    points = [
                                        (float(room.x0), float(room.y0)),
                                        (float(room.x1), float(room.y0)),
                                        (float(room.x1), float(room.y1)),
                                        (float(room.x0), float(room.y1))
                                    ]
                                except (AttributeError, TypeError, ValueError):
                                    points = None
                    
                    if points is None and hasattr(self.tools, "_polygon_baseline_coords_by_group"):
                        flat = self.tools._polygon_baseline_coords_by_group.get(group_tag)
                        if flat and len(flat) >= 6:
                            points = [(float(flat[i]), float(flat[i+1])) for i in range(0, len(flat) - 1, 2)]
                    
                    if points:
                        # Ensure points are floats for math ops
                        points = [(float(p[0]), float(p[1])) for p in points]
                        # Calculate centroid for outward normal orientation
                        sx = sum(p[0] for p in points)
                        sy = sum(p[1] for p in points)
                        centroid = (sx / len(points), sy / len(points))
                        
                        self.actions.log({
                            "type": "delete_dimension",
                            "dim_tag": dim_tag,
                            "group_tag": group_tag,
                            "edge_idx": edge_idx,
                            "points": points,
                            "centroid": centroid
                        })
            except Exception as e:
                print(f"DEBUG: Failed to log dimension deletion: {e}")

            # Use the existing helper in dimension_drawer
            self.tools.dimension_drawer.clear_dimensions_for_group(dim_tag)
            
            # Log for undo/redo if possible (best effort)
            # self.actions.log(...) 
            
            if hasattr(self, "selected_dimension_tag") and self.selected_dimension_tag == dim_tag:
                self.selected_dimension_tag = None
            
            print(f"🗑️ Measurement deleted: {dim_tag}")
    
    def _show_room_context_menu(self, event, group_tag):
        """Show context menu for a room with Edit and Delete options."""
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Edit Room", command=lambda: self._edit_room(group_tag))
        menu.add_separator()
        menu.add_command(label="Delete Room", command=lambda: self.tools.delete_room_by_group(group_tag))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _edit_room(self, group_tag):
        """Trigger room editing in the sidebar."""
        # Find the room entity and populate widgets
        if hasattr(self.tools, "start_room_edit"):
            self.tools.start_room_edit(group_tag)
            # Switch to the 'Room' tab if possible. 
            if hasattr(self, "switch_tab"):
                self.switch_tab("Room")
            print(f"🛠️ Editing room: {group_tag}")

    def _show_line_context_menu(self, event, line_id, line_tag):
        """Show context menu for a line with Edit and Duplicate options."""
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Edit Line", command=lambda: self._edit_line(line_id, line_tag))
        menu.add_command(label="Duplicate Line", command=lambda: self._duplicate_line(line_tag))
        menu.add_separator()
        menu.add_command(label="Delete Line", command=lambda: self._delete_line(line_id, line_tag))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_user_text_context_menu(self, event, text_id: int) -> None:
        """Right-click menu for user text (same flow as furniture: edit first, then drag)."""
        try:
            tags = set(self.canvas.gettags(text_id))
        except Exception:
            tags = set()

        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Edit Text", command=lambda: self._edit_user_text(text_id))
        menu.add_command(label="Duplicate Text", command=lambda: self._duplicate_user_text(text_id))
        menu.add_separator()
        if "user_text_editing" in tags:
            menu.add_command(label="Done (Lock Text)", command=lambda: self._lock_user_text(text_id))
        else:
            menu.add_command(label="Unlock Text", command=lambda: self._unlock_user_text(text_id))
        menu.add_command(label="Delete Text", command=lambda: self._delete_user_text(text_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _lock_user_text(self, text_id: int) -> None:
        """Exit edit mode for a user text (prevents dragging until re-edited)."""
        try:
            tags = set(self.canvas.gettags(text_id))
        except Exception:
            return
        if "user_text_editing" in tags:
            tags.discard("user_text_editing")
            try:
                self.canvas.itemconfig(text_id, tags=tuple(tags))
            except Exception:
                pass

    def _unlock_user_text(self, text_id: int) -> None:
        """Enter edit mode for user text to allow dragging, without opening the edit dialog."""
        try:
            if self.canvas.type(text_id) != "text":
                return
        except Exception:
            return
        try:
            tags = set(self.canvas.gettags(text_id))
            tags.add("user_text")
            tags.add("user_text_editing")
            self.canvas.itemconfig(text_id, tags=tuple(tags))
        except Exception:
            pass

    def _duplicate_user_text(self, text_id: int) -> None:
        """Duplicate a user text by copying its options and offsetting position slightly."""
        try:
            if self.canvas.type(text_id) != "text":
                return
        except Exception:
            return

        try:
            x, y = self.canvas.coords(text_id)[:2]
        except Exception:
            return

        # Offset duplicate so it is visible immediately
        dx = 20
        dy = 20

        def _safe_itemcget(opt: str, default: str = "") -> str:
            try:
                v = self.canvas.itemcget(text_id, opt)
                return v if v is not None else default
            except Exception:
                return default

        text_val = _safe_itemcget("text", "")
        fill_val = _safe_itemcget("fill", "black")
        font_val = _safe_itemcget("font", ("Arial", 12))
        anchor_val = _safe_itemcget("anchor", "nw")
        justify_val = _safe_itemcget("justify", "left")
        width_val = _safe_itemcget("width", "")

        try:
            tags = set(self.canvas.gettags(text_id))
        except Exception:
            tags = {"user_text"}
        tags.discard("user_text_editing")  # duplicated text starts locked
        tags.add("user_text")

        create_kwargs = {
            "text": text_val,
            "fill": fill_val,
            "font": font_val,
            "anchor": anchor_val,
            "justify": justify_val,
            "tags": tuple(tags),
        }
        # width is optional; Tk expects integer string or number
        try:
            if str(width_val).strip():
                create_kwargs["width"] = int(float(width_val))
        except Exception:
            pass

        try:
            new_id = self.canvas.create_text(x + dx, y + dy, **create_kwargs)
        except Exception:
            return

        try:
            self.actions.log({"type": "create", "items": [new_id]})
        except Exception:
            pass

    def _delete_user_text(self, text_id: int) -> None:
        """Delete a user text with undo support."""
        try:
            if self.canvas.type(text_id) != "text":
                return
        except Exception:
            return

        try:
            snapshot = self.actions._snapshot_canvas_items(self.canvas, [text_id])
        except Exception:
            snapshot = []
        try:
            self.canvas.delete(text_id)
        except Exception:
            return

        # Snapshot-based delete action (undo can recreate)
        if snapshot:
            item = snapshot[0]
            try:
                self.actions.log({
                    "type": "delete",
                    "item_type": item.get("type"),
                    "coords": item.get("coords"),
                    "options": item.get("options"),
                    "tags": item.get("tags"),
                    "new_id": None,
                })
            except Exception:
                pass

    def _edit_user_text(self, text_id: int) -> None:
        """Enter edit mode for user text and allow dragging afterwards."""
        try:
            if self.canvas.type(text_id) != "text":
                return
        except Exception:
            return

        # Mark editable (drag allowed) before opening dialog.
        try:
            tags = set(self.canvas.gettags(text_id))
            tags.add("user_text")
            tags.add("user_text_editing")
            self.canvas.itemconfig(text_id, tags=tuple(tags))
        except Exception:
            pass

        self._open_user_text_edit_dialog(text_id)

    def _open_user_text_edit_dialog(self, text_id: int) -> None:
        """Simple cross-platform dialog to edit text content and style."""
        try:
            import tkinter.font as tkfont
            from tkinter import ttk, colorchooser
        except Exception:
            return

        # Capture current state
        def _safe_itemcget(opt: str, default: str = "") -> str:
            try:
                v = self.canvas.itemcget(text_id, opt)
                return v if v is not None else default
            except Exception:
                return default

        cur_text = _safe_itemcget("text", "")
        cur_fill = _safe_itemcget("fill", "#000000")
        cur_font = _safe_itemcget("font", "")

        # Parse existing font best-effort
        family = "Arial"
        size = 24
        bold = False
        italic = False
        try:
            f = tkfont.Font(font=cur_font)
            family = f.actual("family") or family
            size = abs(int(f.actual("size") or size))
            bold = (str(f.actual("weight")).lower() == "bold")
            italic = (str(f.actual("slant")).lower() == "italic")
        except Exception:
            pass

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Text")
        dialog.transient(self.root)
        dialog.grab_set()
        try:
            set_window_icon(dialog)
        except Exception:
            pass
        try:
            dialog.resizable(False, False)
        except Exception:
            pass

        # Center dialog on parent (fix: it was opening top-left)
        try:
            dialog.update_idletasks()
            parent_x = self.root.winfo_x()
            parent_y = self.root.winfo_y()
            parent_width = self.root.winfo_width()
            parent_height = self.root.winfo_height()
            dialog_width = dialog.winfo_reqwidth()
            dialog_height = dialog.winfo_reqheight()
            x = parent_x + (parent_width // 2) - (dialog_width // 2)
            y = parent_y + (parent_height // 2) - (dialog_height // 2)
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        frm = ttk.Frame(dialog, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Text").grid(row=0, column=0, sticky="w")
        text_box = tk.Text(frm, width=38, height=4, wrap="word")
        text_box.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 10))
        try:
            text_box.insert("1.0", cur_text)
        except Exception:
            pass

        bold_var = tk.BooleanVar(value=bool(bold))
        italic_var = tk.BooleanVar(value=bool(italic))
        size_var = tk.IntVar(value=int(size))
        color_var = tk.StringVar(value=str(cur_fill))

        ttk.Label(frm, text="Size").grid(row=2, column=0, sticky="w")
        size_spin = ttk.Spinbox(frm, from_=6, to=200, textvariable=size_var, width=8)
        size_spin.grid(row=2, column=1, sticky="w")

        ttk.Checkbutton(frm, text="Bold", variable=bold_var).grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Checkbutton(frm, text="Italic", variable=italic_var).grid(row=3, column=1, sticky="w", pady=(6, 0))

        ttk.Label(frm, text="Color").grid(row=4, column=0, sticky="w", pady=(10, 0))
        color_ent = ttk.Entry(frm, textvariable=color_var, width=18)
        color_ent.grid(row=4, column=1, sticky="w", pady=(10, 0))

        def pick_color():
            try:
                picked = colorchooser.askcolor(parent=dialog, color=color_var.get())[1]
            except Exception:
                picked = None
            if picked:
                color_var.set(picked)

        ttk.Button(frm, text="Pick…", command=pick_color, width=8).grid(row=4, column=2, sticky="w", padx=(6, 0), pady=(10, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=3, sticky="e", pady=(14, 0))

        def on_cancel():
            try:
                dialog.destroy()
            except Exception:
                pass

        def on_save():
            # Snapshot old item for undo/redo replace_group
            try:
                old_snapshot = self.actions._snapshot_canvas_items(self.canvas, [text_id])
                old_item = old_snapshot[0] if old_snapshot else None
            except Exception:
                old_item = None

            new_content = ""
            try:
                new_content = text_box.get("1.0", "end-1c")
            except Exception:
                pass
            new_content = (new_content or "").rstrip("\n")
            if not new_content.strip():
                on_cancel()
                return

            # Build new font
            styles = []
            if bold_var.get():
                styles.append("bold")
            if italic_var.get():
                styles.append("italic")
            font_tuple = (family, int(size_var.get() or 24), " ".join(styles) if styles else "normal")

            # Preserve visual center and tags (keep editing tag so drag works)
            try:
                old_bbox = self.canvas.bbox(text_id)
            except Exception:
                old_bbox = None
            old_cx = old_cy = None
            if old_bbox and len(old_bbox) == 4:
                try:
                    old_cx = (float(old_bbox[0]) + float(old_bbox[2])) / 2.0
                    old_cy = (float(old_bbox[1]) + float(old_bbox[3])) / 2.0
                except Exception:
                    old_cx = old_cy = None

            try:
                x, y = self.canvas.coords(text_id)[:2]
            except Exception:
                x, y = 0, 0

            try:
                tags = set(self.canvas.gettags(text_id))
            except Exception:
                tags = {"user_text", "user_text_editing"}
            tags.add("user_text")
            tags.add("user_text_editing")

            try:
                anchor_val = self.canvas.itemcget(text_id, "anchor") or "nw"
            except Exception:
                anchor_val = "nw"

            # Replace: delete old id, create new id, log replace_group
            try:
                self.canvas.delete(text_id)
            except Exception:
                on_cancel()
                return

            new_id = None
            try:
                new_id = self.canvas.create_text(
                    x, y,
                    text=new_content,
                    fill=color_var.get() or "#000000",
                    font=font_tuple,
                    anchor=anchor_val,
                    tags=tuple(tags),
                )

                # Align new text so its visual center matches the old text.
                if old_cx is not None and old_cy is not None:
                    try:
                        new_bbox = self.canvas.bbox(new_id)
                    except Exception:
                        new_bbox = None
                    if new_bbox and len(new_bbox) == 4:
                        try:
                            new_cx = (float(new_bbox[0]) + float(new_bbox[2])) / 2.0
                            new_cy = (float(new_bbox[1]) + float(new_bbox[3])) / 2.0
                            dx = old_cx - new_cx
                            dy = old_cy - new_cy
                            if dx or dy:
                                self.canvas.move(new_id, dx, dy)
                        except Exception:
                            pass
            except Exception:
                # Best-effort restore old if creation fails
                try:
                    if old_item:
                        self.actions._recreate_items(self.canvas, [old_item])
                except Exception:
                    pass
                on_cancel()
                return

            # Update controller dragging reference if it was pointing to old id
            try:
                if self.dragging_item == text_id:
                    self.dragging_item = new_id
            except Exception:
                pass

            # Log undo/redo as replace_group
            if old_item:
                try:
                    new_item = self.actions._snapshot_canvas_items(self.canvas, [new_id])[0]
                except Exception:
                    new_item = None
                try:
                    if new_item:
                        self.actions.log({
                            "type": "replace_group",
                            "old_ids": [text_id],
                            "new_ids": [new_id],
                            "old_items": [old_item],
                            "new_items": [new_item],
                        })
                except Exception:
                    pass
            else:
                # Fallback: treat as create (undo deletes new id)
                try:
                    self.actions.log({"type": "create", "items": [new_id]})
                except Exception:
                    pass

            try:
                dialog.destroy()
            except Exception:
                pass

        ttk.Button(btns, text="Cancel", command=on_cancel, width=10).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="Save", command=on_save, width=10).pack(side="right")

        try:
            dialog.bind("<Escape>", lambda _e: on_cancel())
        except Exception:
            pass
    
    def _edit_line(self, line_id, line_tag):
        """Edit a line by allowing user to modify its endpoints."""
        if not hasattr(self.tools, 'line_metadata') or line_tag not in self.tools.line_metadata:
            return
        
        metadata = self.tools.line_metadata[line_tag]
        coords = self.canvas.coords(line_id)
        if len(coords) >= 4:
            # Store original for undo
            self.actions.log({
                "type": "modify",
                "item": line_id,
                "old_coords": coords[:]
            })
            
            print("✏️ Line edit mode: Drag the endpoints to resize/rotate the line.")
            self.line_editor.start_edit(line_id, line_tag, metadata)

    def _is_line_handle_hit(self, event) -> bool:
        items = self.canvas.find_overlapping(event.x - 4, event.y - 4, event.x + 4, event.y + 4)
        for item in items:
            try:
                tags = self.canvas.gettags(item)
            except Exception:
                continue
            if "line_edit_handle" in tags:
                return True
        return False
    
    def _duplicate_line(self, line_tag):
        """Duplicate a line by creating a copy offset from the original."""
        if not hasattr(self.tools, 'line_metadata') or line_tag not in self.tools.line_metadata:
            return
        
        metadata = self.tools.line_metadata[line_tag]
        x0, y0 = metadata['x0'], metadata['y0']
        x1, y1 = metadata['x1'], metadata['y1']
        
        # Create offset for duplicate (20 pixels offset)
        offset = 20
        new_x0, new_y0 = x0 + offset, y0 + offset
        new_x1, new_y1 = x1 + offset, y1 + offset
        
        # Create duplicate line
        import uuid
        new_line_tag = f"line_{uuid.uuid4().hex[:8]}"
        new_line = self.canvas.create_line(new_x0, new_y0, new_x1, new_y1,
                                          fill=metadata['color'],
                                          width=metadata['width'],
                                          dash=metadata['dash'],
                                          tags=("line", "committed_line", new_line_tag))
        
        # Duplicate label and point
        from drawing_helpers import get_distance_label
        label_text, mid_x, mid_y = get_distance_label(new_x0, new_y0, new_x1, new_y1, 
                                                       self.model.unit, self.model.zoom_level)
        new_label = self.canvas.create_text(
            mid_x, mid_y - 10, text=label_text, font=("Arial", 8),
            fill="black", tags=("line_label", new_line_tag),
        )
        new_point = self.canvas.create_oval(new_x1 - 0.5, new_y1 - 0.5, new_x1 + 0.5, new_y1 + 0.5, 
                                          fill="black", tags=("line_point", new_line_tag))
        
        # Store metadata for new line
        if not hasattr(self.tools, 'line_metadata'):
            self.tools.line_metadata = {}
        self.tools.line_metadata[new_line_tag] = {
            'x0': new_x0, 'y0': new_y0, 'x1': new_x1, 'y1': new_y1,
            'width': metadata['width'], 'dash': metadata['dash'], 'color': metadata['color'],
            'label': new_label, 'point': new_point
        }
        
        self.actions.log({
            "type": "create",
            "items": [new_line, new_label, new_point]
        })
        
        print(f"✅ Line duplicated")
    
    def _delete_line(self, line_id, line_tag):
        """Delete a line and its associated label and point."""
        if not hasattr(self.tools, 'line_metadata') or line_tag not in self.tools.line_metadata:
            return
        
        # Check if this is the last wall - prevent deletion if so
        def count_walls_on_canvas():
            """Count all wall-like items on the canvas, excluding the current line being deleted."""
            wall_count = 0
            all_items = self.canvas.find_all()
            
            for item_id in all_items:
                # Skip the item we're about to delete
                if item_id == line_id:
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
        
        # If this would be the last wall, show error and don't allow deletion
        if remaining_walls <= 0:
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "Cannot Delete Wall",
                    "This wall cannot be deleted.\n\nAt least one wall must remain on the canvas.",
                    icon="error"
                )
            except Exception:
                print("❌ This wall cannot be deleted. At least one wall must remain on the canvas.")
            return
        
        metadata = self.tools.line_metadata[line_tag]
        
        # Delete line, label, and point
        items_to_delete = [line_id]
        if metadata.get('label'):
            try:
                items_to_delete.append(metadata['label'])
            except:
                pass
        if metadata.get('point'):
            try:
                items_to_delete.append(metadata['point'])
            except:
                pass
        
        # Also find and delete any items with the same tag
        for item in self.canvas.find_withtag(line_tag):
            if item not in items_to_delete:
                items_to_delete.append(item)
        
        items_payload = []
        for item in items_to_delete:
            try:
                item_type = self.canvas.type(item)
                coords = self.canvas.coords(item)
                tags = self.canvas.gettags(item)
                options = {}

                if item_type == "text":
                    options["text"] = self.canvas.itemcget(item, "text")
                    options["fill"] = self.canvas.itemcget(item, "fill")
                elif item_type == "line":
                    options["fill"] = self.canvas.itemcget(item, "fill")
                    options["width"] = self.canvas.itemcget(item, "width")
                elif item_type in ("oval", "rectangle", "polygon"):
                    options["fill"] = self.canvas.itemcget(item, "fill")
                    options["outline"] = self.canvas.itemcget(item, "outline")
                    options["width"] = self.canvas.itemcget(item, "width")

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

        for item in items_to_delete:
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        
        # Remove metadata
        del self.tools.line_metadata[line_tag]
        
        if items_payload:
            self.actions.log(
                {
                    "type": "delete_group",
                    "items": items_payload,
                }
            )
        
        print(f"🗑️ Line deleted")
    
    def on_mouse_move(self, event):
        if getattr(self, "_in_mouse_move", False):
            return
        self._in_mouse_move = True
        try:
            now = time.time() * 1000
            if now - self._last_motion_time < self._motion_throttle_ms:
                self._in_mouse_move = False
                return
            self._last_motion_time = now

            self.tools.update_coord_label(event)
            dragging_now = False
            try:
                dragging_now = (getattr(self, "dragging_item", None) is not None) or bool(
                    getattr(self, "dragging_group", None)
                )
            except Exception:
                pass
            # While dragging, skip all preview updates to prevent traces/ghost lines.
            # Auto-pan only while polygons are actively being drawn (first point placed)
            # AND we are not dragging items/groups.
            # Important: run auto-pan *before* preview updates so the mouse position
            # is mapped using the latest scrollregion fractions (prevents 1-frame
            # coordinate mismatches and repeated points).
            if not dragging_now and self._is_polygon_draw_active():
                # Crucial: Anchor the extension to the current mouse position so the point 
                # under the cursor remains stable relative to the screen.
                self._auto_pan_controller.set_anchor(event.x, event.y)
                self._auto_pan_controller.auto_pan(event)
            else:
                self._auto_pan_controller.stop()

            # Update previews after auto-pan so they use up-to-date canvas coords.
            if not dragging_now:
                if self.model.get("polygon_mode"):
                    self.tools.update_polygon_preview(event)
                if self.model.get("vastu_polygon_mode"):
                    self.tools.update_vastu_polygon_preview(event)
                if self.model.get("drawing_enabled"):
                    self.tools.update_line_preview(event)
            else:
                # Alignment guides are handled directly in on_drag for better sync with snapping logic.
                pass
        finally:
            self._in_mouse_move = False
    
    def _update_room_alignment_guides(self, event):
        """Update room alignment guides during mouse move (before drag)."""
        if not hasattr(self, 'initial_room_bbox') or self.initial_room_bbox is None:
            return
        
        room_entity = self.tools.room_entities_by_group_tag.get(self.dragging_group)
        if not room_entity or not hasattr(room_entity, 'rect_id'):
            return
        
        try:
            # Get current room position
            current_coords = self.canvas.coords(room_entity.rect_id)
            if not current_coords or len(current_coords) < 4:
                return
            
            # Get all other rooms for alignment
            other_rooms = [
                (tag, room) for tag, room in self.tools.room_entities_by_group_tag.items()
                if tag != self.dragging_group
            ]
            
            # Calculate alignment snap
            snapped_x0, snapped_y0, snap_info = self.tools.guideline_helper.get_room_alignment_snap(
                tuple(current_coords), other_rooms, tolerance=5
            )
            
            # Draw alignment guides
            self.tools.guideline_helper.draw_room_alignment_guides(
                tuple(current_coords), snap_info, other_rooms
            )
        except Exception:
            pass

    def _is_polygon_draw_active(self):
        """Helper to determine if any point-based drawing is currently mid-operation."""
        return bool(
            getattr(self.tools, "polygon_points", []) or 
            getattr(self.tools, "vastu_polygon_points", []) or 
            getattr(self.tools, "first_point", None)
        )

    def _update_auto_pan_while_drawing(self, event: tk.Event) -> None:
        """Auto-pan canvas while drawing polygons when cursor nears edges.

        Horizontal:
        - Right edge: always allowed.
        - Left edge: only allowed after we've already auto-panned to the right at least once.
          Also, it will pan back only up to the initial view (canvas start) xview.
        """
        # Backward-compatible wrapper: the real auto-pan implementation lives
        # in `autopan.AutoPanWhileDrawing`.
        self._auto_pan_controller.auto_pan(event)
        return

        if not (self.model.get("polygon_mode") or self.model.get("vastu_polygon_mode")):
            self._reset_auto_pan_state()
            return

        # Safety: only auto-pan when points exist (drawing actually started).
        if not self._is_polygon_draw_active():
            self._stop_auto_pan()
            return

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        threshold = self._auto_pan_edge_threshold

        # Current horizontal view (0.0 = very left, 1.0 = very right)
        try:
            x0, x1 = self.canvas.xview()
        except Exception:
            x0, x1 = 0.0, 1.0

        # Current vertical view (0.0 = very top, 1.0 = very bottom)
        try:
            y0, y1 = self.canvas.yview()
        except Exception:
            y0, y1 = 0.0, 1.0

        # Capture initial view once per drawing session.
        if self._auto_pan_initial_view is None:
            self._auto_pan_initial_view = (x0, x1, y0, y1)

        # Store widget anchor coords for smooth infinite extension.
        self._auto_pan_anchor_widget_x = getattr(event, "x", None)
        self._auto_pan_anchor_widget_y = getattr(event, "y", None)

        dx = 0
        dy = 0

        # Horizontal: left / right edge
        # For right edge, do not depend on x1 < 1.0; when we hit the boundary,
        # _auto_pan_step() will extend scrollregion so panning continues.
        if event.x > width - threshold:
            dx = self._auto_pan_speed
            self._auto_pan_has_scrolled_right = True
        elif event.x < threshold and x0 > 0.0:
            # Only pan left if we previously panned right,
            # and do not go beyond the initial view start.
            if self._auto_pan_has_scrolled_right and self._auto_pan_initial_view:
                init_x0 = self._auto_pan_initial_view[0]
                if x0 > init_x0 + self._auto_pan_view_eps:
                    dx = -self._auto_pan_speed
        # Scroll down when near bottom.
        # Do not depend on y1 < 1.0; when we hit the boundary,
        # _auto_pan_step() will extend scrollregion ("infinity").
        if event.y > height - threshold:
            dy = self._auto_pan_speed
        # Scroll up when near top, if not already at absolute top
        elif event.y < threshold and y0 > 1e-6:
            dy = -self._auto_pan_speed

        self._auto_pan_dx = dx
        self._auto_pan_dy = dy

        if dx == 0 and dy == 0:
            self._stop_auto_pan()
            return

        # Starting a new auto-pan "session": reset snap hysteresis so any one-frame
        # coordinate discontinuity doesn't influence subsequent snapping decisions.
        if self._auto_pan_job is None:
            try:
                if hasattr(self.tools, "guideline_helper") and hasattr(
                    self.tools.guideline_helper, "_grid_snap_last_coord"
                ):
                    self.tools.guideline_helper._grid_snap_last_coord = {"x": None, "y": None}
            except Exception:
                pass

        if self._auto_pan_job is None:
            self._auto_pan_step()

    def _auto_pan_step(self) -> None:
        """Perform one auto-pan step and schedule the next while drawing."""
        # Backward-compatible no-op: stepping is handled by AutoPanWhileDrawing.
        return

        if not (self.model.get("polygon_mode") or self.model.get("vastu_polygon_mode")):
            self._stop_auto_pan()
            return

        dx = self._auto_pan_dx
        dy = self._auto_pan_dy

        if dx == 0 and dy == 0:
            self._stop_auto_pan()
            return

        # Capture current view before moving (stuck detection).
        try:
            x0_before, x1_before = self.canvas.xview()
        except Exception:
            x0_before, x1_before = 0.0, 1.0
        try:
            y0_before, y1_before = self.canvas.yview()
        except Exception:
            y0_before, y1_before = 0.0, 1.0

        # macOS Tk can behave inconsistently with xview_moveto/yview_moveto fractions
        # during rapid after()-driven updates. Use xview_scroll/yview_scroll as
        # a reliable fallback on Darwin.
        if platform.system() == "Darwin":
            if dx != 0:
                self.canvas.xview_scroll(1 if dx > 0 else -1, "units")
            if dy != 0:
                self.canvas.yview_scroll(1 if dy > 0 else -1, "units")
            # boundary/stuck check
            try:
                x0_after, x1_after = self.canvas.xview()
                y0_after, y1_after = self.canvas.yview()
            except Exception:
                x0_after, x1_after, y0_after, y1_after = x0_before, x1_before, y0_before, y1_before

            eps_boundary = 1e-6
            boundary_reached = (
                (dx > 0 and x1_after >= 1.0 - eps_boundary)
                or (dx < 0 and x0_after <= eps_boundary)
                or (dy > 0 and y1_after >= 1.0 - eps_boundary)
                or (dy < 0 and y0_after <= eps_boundary)
            )
            same = (
                abs(x0_after - x0_before) < 1e-7
                and abs(x1_after - x1_before) < 1e-7
                and abs(y0_after - y0_before) < 1e-7
                and abs(y1_after - y1_before) < 1e-7
            )
            if boundary_reached or same:
                # "Infinity" behavior on macOS too.
                try:
                    if dy > 0 and y1_after >= 1.0 - eps_boundary:
                        widget_h = max(1, int(self.canvas.winfo_height()))
                        if hasattr(self.view, "extend_scrollregion"):
                            ax = self._auto_pan_anchor_widget_x
                            ay = self._auto_pan_anchor_widget_y
                            self.view.extend_scrollregion(
                                extend_bottom=widget_h * 4.0,
                                anchor_widget_x=ax,
                                anchor_widget_y=ay,
                            )
                            self._auto_pan_stuck_count = 0
                            self._auto_pan_job = self.canvas.after(self._auto_pan_interval_ms, self._auto_pan_step)
                            return
                    if dx > 0 and x1_after >= 1.0 - eps_boundary:
                        widget_w = max(1, int(self.canvas.winfo_width()))
                        if hasattr(self.view, "extend_scrollregion"):
                            ax = self._auto_pan_anchor_widget_x
                            ay = self._auto_pan_anchor_widget_y
                            self.view.extend_scrollregion(
                                extend_right=widget_w * 4.0,
                                anchor_widget_x=ax,
                                anchor_widget_y=ay,
                            )
                            self._auto_pan_stuck_count = 0
                            self._auto_pan_job = self.canvas.after(self._auto_pan_interval_ms, self._auto_pan_step)
                            return
                except Exception:
                    pass
                self._auto_pan_stuck_count += 1
            else:
                self._auto_pan_stuck_count = 0

            if self._auto_pan_stuck_count >= self._auto_pan_stuck_limit:
                self._stop_auto_pan()
                return

            self._auto_pan_job = self.canvas.after(self._auto_pan_interval_ms, self._auto_pan_step)
            return

        # Use scrollregion-aware moveto so horizontal scrollbar thumb moves reliably.
        try:
            sr = self.canvas.cget("scrollregion")
            x0_sr, y0_sr, x1_sr, y1_sr = map(float, str(sr or "").split())
        except Exception:
            # Fallback to scroll if scrollregion can't be parsed.
            try:
                if dx != 0:
                    self.canvas.xview_scroll(1 if dx > 0 else -1, "units")
                if dy != 0:
                    self.canvas.yview_scroll(1 if dy > 0 else -1, "units")
            finally:
                self._auto_pan_job = self.canvas.after(self._auto_pan_interval_ms, self._auto_pan_step)
            return

        total_w = max(1.0, x1_sr - x0_sr)
        total_h = max(1.0, y1_sr - y0_sr)

        # Visible size in canvas coords
        try:
            widget_w = max(1, int(self.canvas.winfo_width()))
            widget_h = max(1, int(self.canvas.winfo_height()))
            left_canvas = self.canvas.canvasx(0)
            right_canvas = self.canvas.canvasx(widget_w)
            top_canvas = self.canvas.canvasy(0)
            bottom_canvas = self.canvas.canvasy(widget_h)
            visible_w = max(1.0, right_canvas - left_canvas)
            visible_h = max(1.0, bottom_canvas - top_canvas)
        except Exception:
            visible_w = float(getattr(self.canvas, "winfo_width", lambda: 1200)() or 1200)
            visible_h = float(getattr(self.canvas, "winfo_height", lambda: 800)() or 800)

        # Current view fractions
        try:
            x_view0, x_view1 = self.canvas.xview()
        except Exception:
            x_view0, x_view1 = 0.0, min(1.0, visible_w / total_w)
        try:
            y_view0, y_view1 = self.canvas.yview()
        except Exception:
            y_view0, y_view1 = 0.0, min(1.0, visible_h / total_h)

        view_w_frac = max(1e-9, x_view1 - x_view0)
        view_h_frac = max(1e-9, y_view1 - y_view0)

        # IMPORTANT: Tkinter view fractions are based on the scrollable range
        # (scrollregion_size - visible_size), not on full scrollregion_size.
        range_w = max(1e-9, total_w - visible_w)
        range_h = max(1e-9, total_h - visible_h)

        if dx != 0:
            sign = 1.0 if dx > 0 else -1.0
            delta_frac_x = (float(self._auto_pan_step_canvas_x) * sign) / float(range_w)
            new_x0 = x_view0 + delta_frac_x
            new_x0 = max(0.0, min(new_x0, 1.0 - view_w_frac))
            self.canvas.xview_moveto(new_x0)

        if dy != 0:
            sign = 1.0 if dy > 0 else -1.0
            delta_frac_y = (float(self._auto_pan_step_canvas_y) * sign) / float(range_h)
            new_y0 = y_view0 + delta_frac_y
            bottom_y0 = 1.0 - view_h_frac

            # Ensure we can reach the real "bottom" / "top" even when float math
            # would otherwise stop a bit short.
            eps_move = 1e-6
            if dy > 0:
                # going down
                if new_y0 >= bottom_y0 - eps_move:
                    new_y0 = bottom_y0
                else:
                    new_y0 = max(0.0, min(new_y0, bottom_y0))
            else:
                # going up
                if new_y0 <= eps_move:
                    new_y0 = 0.0
                else:
                    new_y0 = max(0.0, min(new_y0, bottom_y0))

            self.canvas.yview_moveto(new_y0)

        # boundary/stuck check after moveto
        try:
            x0_after, x1_after = self.canvas.xview()
            y0_after, y1_after = self.canvas.yview()
        except Exception:
            x0_after, x1_after, y0_after, y1_after = x0_before, x1_before, y0_before, y1_before

        eps_boundary = 1e-6
        boundary_reached = (
            (dx > 0 and x1_after >= 1.0 - eps_boundary)
            or (dx < 0 and x0_after <= eps_boundary)
            or (dy > 0 and y1_after >= 1.0 - eps_boundary)
            or (dy < 0 and y0_after <= eps_boundary)
        )
        same = (
            abs(x0_after - x0_before) < 1e-7
            and abs(x1_after - x1_before) < 1e-7
            and abs(y0_after - y0_before) < 1e-7
            and abs(y1_after - y1_before) < 1e-7
        )
        if boundary_reached or same:
            # "Infinity" behavior:
            # If we're at the bottom/right edge and the user is still drawing
            # (dy>0/dx>0), extend scrollregion so pan can continue.
            try:
                if dy > 0 and y1_after >= 1.0 - eps_boundary:
                    widget_h = max(1, int(self.canvas.winfo_height()))
                    if hasattr(self.view, "extend_scrollregion"):
                        ax = self._auto_pan_anchor_widget_x
                        ay = self._auto_pan_anchor_widget_y
                        self.view.extend_scrollregion(
                            extend_bottom=widget_h * 4.0,
                            anchor_widget_x=ax,
                            anchor_widget_y=ay,
                        )
                        self._auto_pan_stuck_count = 0
                        # Schedule next step immediately.
                        self._auto_pan_job = self.canvas.after(self._auto_pan_interval_ms, self._auto_pan_step)
                        return
                if dx > 0 and x1_after >= 1.0 - eps_boundary:
                    widget_w = max(1, int(self.canvas.winfo_width()))
                    if hasattr(self.view, "extend_scrollregion"):
                        ax = self._auto_pan_anchor_widget_x
                        ay = self._auto_pan_anchor_widget_y
                        self.view.extend_scrollregion(
                            extend_right=widget_w * 4.0,
                            anchor_widget_x=ax,
                            anchor_widget_y=ay,
                        )
                        self._auto_pan_stuck_count = 0
                        self._auto_pan_job = self.canvas.after(self._auto_pan_interval_ms, self._auto_pan_step)
                        return
            except Exception:
                pass
            self._auto_pan_stuck_count += 1
        else:
            self._auto_pan_stuck_count = 0

        if self._auto_pan_stuck_count >= self._auto_pan_stuck_limit:
            self._stop_auto_pan()
            return

        self._auto_pan_job = self.canvas.after(self._auto_pan_interval_ms, self._auto_pan_step)

    def _stop_auto_pan(self) -> None:
        # Backward-compatible wrapper for older code paths.
        self._auto_pan_controller.stop()

    def _reset_auto_pan_state(self) -> None:
        """Reset auto-pan session state when polygon drawing mode ends."""
        self._auto_pan_controller.reset_session()
        
        
    def handle_room_double_click(self, room_name, bbox, canvas, real_width, real_height):
        if hasattr(self.tools, "auto_place_furniture"):
            self.tools.auto_place_furniture(
                room_name,
                bbox,
                canvas,
                real_width,
                real_height
            )
