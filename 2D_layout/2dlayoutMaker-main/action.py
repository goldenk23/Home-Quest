# actions.py
#
# UNDO/REDO ROOT CAUSE ANALYSIS (Mac / cross-platform):
# --------------------------------------------------------
# 1. KEYBOARD SHORTCUTS ON MAC: On macOS, users expect Command+Z (undo) and
#    Command+Shift+Z or Command+Y (redo). Only binding <Control-z> / <Control-y>
#    meant Cmd+Z did nothing. Fix: In controller, bind <Mod1-z> and <Mod1-Shift-Z>
#    (and <Mod1-y>) when platform is Darwin so Mac shortcuts work.
# 2. CANVAS REFERENCE: undo/redo must run against the same canvas that holds
#    the items. If None is passed (e.g. binding fired before canvas set, or
#    toolbar passed wrong ref), reverse/apply would no-op or fail. Fix:
#    ActionManager.undo/redo now fall back to self.tools.canvas when canvas
#    is None; controller uses _canvas_for_undo() for a single source of truth.
# 3. SNAPSHOT ON LOG: For "create" actions we store items_snapshot so redo can
#    recreate. If _snapshot_canvas_items raises (e.g. Mac Tk returning different
#    itemcget values), snapshot could be missing and redo would restore nothing.
#    Existing code already wraps snapshot in try/except; ensure canvas.type(),
#    canvas.coords(), canvas.itemcget(), canvas.gettags() are used defensively.
# 4. ITEM IDS: On undo we delete action["items"] by ID. Those IDs are valid only
#    on the same canvas that created them; using the wrong canvas would leave
#    items on screen or delete wrong ones. Using a single canvas ref (above)
#    avoids this.

class ActionManager:
    def __init__(self, tools=None):
        self.undo_stack = []
        self.redo_stack = []
        self.tools = tools  # Reference to CanvasTools for cleanup operations
        self.serializer = None
        self.post_mutation_callback = None
        self._replaying = False

    def notify_post_mutation(self):
        callback = self.post_mutation_callback
        if callable(callback):
            try:
                callback()
            except Exception as exc:
                print(f"[ActionManager] post-mutation callback failed: {exc}")

    def _normalize_dash(self, dash_value):
        """
        Convert whatever Tk returns for the 'dash' option into a tuple[int, ...]
        that works cross‑platform when recreating items.
        """
        if dash_value in (None, "", 0, "0", "()"):
            return None
        try:
            # Already a sequence of numbers
            if isinstance(dash_value, (list, tuple)):
                ints = [int(float(v)) for v in dash_value if float(v) > 0]
                return tuple(ints) if ints else None
            # Tk commonly returns a string, sometimes wrapped with braces: "4 2" or "{4 2}"
            if isinstance(dash_value, str):
                import re

                s = dash_value.strip()
                if not s:
                    return None
                nums = re.findall(r"[-+]?\d*\.?\d+", s)
                ints = [int(float(n)) for n in nums if float(n) > 0]
                if ints:
                    return tuple(ints)
                # Non‑empty but no numeric tokens: treat as "some dashed style"
                return (4, 2)
        except Exception:
            return None
        return None

    def _recreate_items(self, canvas, items):
        created_ids = []
        for item_data in items:
            item_type = item_data.get("type")
            coords = item_data.get("coords") or []
            options = item_data.get("options") or {}
            tags = item_data.get("tags", ())

            created_id = None
            if item_type == "text":
                kwargs = {
                    "text": options.get("text", ""),
                    "fill": options.get("fill", "black"),
                    "font": options.get("font", ("Arial", 10)),
                    "tags": tags,
                }
                anchor = options.get("anchor")
                if anchor:
                    kwargs["anchor"] = anchor
                justify = options.get("justify")
                if justify:
                    kwargs["justify"] = justify
                # Tk expects integer pixels for width (wrap length)
                try:
                    w = options.get("width")
                    if str(w).strip():
                        kwargs["width"] = int(float(w))
                except Exception:
                    pass
                created_id = canvas.create_text(*coords, **kwargs)
            elif item_type == "line":
                kwargs = {
                    "fill": options.get("fill", "black"),
                    "width": int(float(options.get("width", 1) or 1)),
                    "tags": tags,
                }
                dash = self._normalize_dash(options.get("dash"))
                if dash:
                    kwargs["dash"] = dash
                created_id = canvas.create_line(*coords, **kwargs)
            elif item_type == "oval":
                kwargs = {
                    "fill": options.get("fill", ""),
                    "outline": options.get("outline", ""),
                    "width": int(float(options.get("width", 1) or 1)),
                    "tags": tags,
                }
                dash = options.get("dash")
                if dash:
                    kwargs["dash"] = dash
                created_id = canvas.create_oval(*coords, **kwargs)
            elif item_type == "rectangle":
                kwargs = {
                    "fill": options.get("fill", ""),
                    "outline": options.get("outline", ""),
                    "width": int(float(options.get("width", 1) or 1)),
                    "tags": tags,
                }
                dash = options.get("dash")
                if dash:
                    kwargs["dash"] = dash
                created_id = canvas.create_rectangle(*coords, **kwargs)
            elif item_type == "polygon":
                kwargs = {
                    "fill": options.get("fill", ""),
                    "outline": options.get("outline", ""),
                    "width": int(float(options.get("width", 1) or 1)),
                    "tags": tags,
                }
                dash = options.get("dash")
                if dash:
                    kwargs["dash"] = dash
                created_id = canvas.create_polygon(*coords, **kwargs)

            if created_id is not None:
                created_ids.append(created_id)
        return created_ids

    def log(self, action):
        if self._replaying:
            return
        if (
            action.get("type") == "create"
            and "items_snapshot" not in action
            and self.tools
            and hasattr(self.tools, "canvas")
        ):
            try:
                action["items_snapshot"] = self._snapshot_canvas_items(
                    self.tools.canvas,
                    action.get("items", []),
                )
            except Exception:
                pass
        self.undo_stack.append(action)
        self.redo_stack.clear()
        self.notify_post_mutation()

    def undo(self, canvas):
        if not self.undo_stack:
            return
        c = canvas if canvas is not None else (getattr(self.tools, "canvas", None) if self.tools else None)
        action = self.undo_stack[-1]
        if c is None and action.get("type") != "project_snapshot":
            return
        action = self.undo_stack.pop()
        self._replaying = True
        try:
            self._reverse_action(c, action)
        except Exception:
            self.undo_stack.append(action)
            raise
        finally:
            self._replaying = False
        self.redo_stack.append(action)
        self.notify_post_mutation()

    def redo(self, canvas):
        if not self.redo_stack:
            return
        c = canvas if canvas is not None else (getattr(self.tools, "canvas", None) if self.tools else None)
        action = self.redo_stack[-1]
        if c is None and action.get("type") != "project_snapshot":
            return
        action = self.redo_stack.pop()
        self._replaying = True
        try:
            self._apply_action(c, action)
        except Exception:
            self.redo_stack.append(action)
            raise
        finally:
            self._replaying = False
        self.undo_stack.append(action)
        self.notify_post_mutation()

    def _reverse_action(self, canvas, action):
        t = action["type"]

        if t == "project_snapshot":
            if not self.serializer:
                raise RuntimeError("project snapshot history requires a serializer")
            self.serializer.apply_project_snapshot(action["before"])
            return

        if t == "delete_duplicated_layout":
            scope = action.get("scope")
            if self.serializer and scope:
                self.serializer._recreate_duplicated_layout(scope.get("data", {}), scope)
            return

        if t == "duplicate_layout":
            if self.serializer:
                self.serializer._remove_duplicated_layout(action)
            return

        if t == "create":
            # Ensure we have a snapshot so redo can faithfully recreate items
            if "items_snapshot" not in action:
                try:
                    action["items_snapshot"] = self._snapshot_canvas_items(
                        canvas,
                        action.get("items", []),
                    )
                except Exception:
                    pass

            dim_recompute = action.get("dimension_recompute")
            if dim_recompute and self.tools and hasattr(self.tools, "dimension_drawer"):
                dim_tag = dim_recompute.get("dim_tag")
                if dim_tag:
                    self.tools.dimension_drawer.clear_dimensions_for_group(dim_tag)
            
            for item in action.get("items") or []:
                try:
                    canvas.delete(item)
                except Exception:
                    continue
            return
        
        elif t == "create_furniture":
            # Undo furniture creation: remove the image and all selection artifacts.
            image_id = action.get("image_id")
            if image_id:
                removed_object = False
                if self.tools and hasattr(self.tools, "image_furniture_items"):
                    try:
                        for furniture_obj in list(self.tools.image_furniture_items):
                            if getattr(furniture_obj, "image_id", None) != image_id:
                                continue
                            furniture_obj.delete()
                            furniture_obj.is_selected = False
                            self.tools.image_furniture_items.remove(furniture_obj)
                            if getattr(self.tools, "selected_furniture_obj", None) is furniture_obj:
                                self.tools.selected_furniture_obj = None
                            removed_object = True
                            break
                    except Exception as e:
                        print(f"[Undo] Error removing furniture from list: {e}")
                if not removed_object:
                    try:
                        canvas.delete(image_id)
                    except Exception:
                        pass
                # If the undone furniture was a door, restore walls by recomputing all door cuts.
                if (
                    self.tools
                    and hasattr(self.tools, "schedule_recompute_door_cuts")
                ):
                    try:
                        image_path = str(action.get("image_path", "")).lower()
                        if "door" in image_path:
                            self.tools.schedule_recompute_door_cuts(delay_ms=30)
                    except Exception:
                        pass
        
        elif t == "create_room":
            # Delete all items with the room's group tag (including flooring, borders, etc.)
            group_tag = action.get("group_tag")
            if group_tag:
                # Clean up dimensions specifically using dimension_drawer to clear image refs
                if self.tools and hasattr(self.tools, "dimension_drawer"):
                    dim_tag = action.get("dim_tag") or f"{group_tag}__dims"
                    self.tools.dimension_drawer.clear_dimensions_for_group(dim_tag)
                
                # Delete all items with the room's group tag
                items_to_delete = list(canvas.find_withtag(group_tag))
                for item in items_to_delete:
                    try:
                        canvas.delete(item)
                    except Exception:
                        pass
                # Also check for flooring items that might have the group tag in a different way
                # (some flooring items might be tagged differently)
                try:
                    all_items = canvas.find_all()
                    for item in all_items:
                        tags = canvas.gettags(item)
                        # Delete if item has both flooring/flooring_border tag AND the room group tag
                        if group_tag in tags and ("flooring" in tags or "flooring_border" in tags):
                            try:
                                canvas.delete(item)
                            except Exception:
                                pass
                except Exception:
                    pass
                # Clean up room entity tracking if tools reference is available
                if self.tools and hasattr(self.tools, "room_entities_by_group_tag"):
                    try:
                        self.tools.room_entities_by_group_tag.pop(group_tag, None)
                    except Exception:
                        pass
            else:
                # Fallback: delete items by ID if group_tag is missing
                for item in action.get("items", []):
                    try:
                        canvas.delete(item)
                    except Exception:
                        pass

        elif t == "delete":
            # Two supported schemas:
            # 1) Snapshot-based delete (undo recreates, redo deletes recreated id):
            #    {type:"delete", item_type, coords, options, tags, new_id?: None|int}
            # 2) Legacy id-list delete (best-effort; cannot restore without snapshot):
            #    {type:"delete", items:[item_id,...]}

            # Legacy schema: nothing to recreate (no snapshot). Keep safe.
            if "item_type" not in action:
                return

            item_type = action.get("item_type")
            coords = action.get("coords") or []
            options = action.get("options") or {}
            tags = action.get("tags", ())

            created_id = None
            if item_type == "text":
                kwargs = {
                    "text": options.get("text", ""),
                    "fill": options.get("fill", "black"),
                    "font": options.get("font", ("Arial", 10)),
                    "tags": tags,
                }
                anchor = options.get("anchor")
                if anchor:
                    kwargs["anchor"] = anchor
                justify = options.get("justify")
                if justify:
                    kwargs["justify"] = justify
                try:
                    w = options.get("width")
                    if str(w).strip():
                        kwargs["width"] = int(float(w))
                except Exception:
                    pass
                created_id = canvas.create_text(*coords, **kwargs)
            elif item_type == "line":
                dash = self._normalize_dash(options.get("dash"))
                if dash:
                    created_id = canvas.create_line(
                        *coords,
                        fill=options.get("fill", "black"),
                        width=int(float(options.get("width", 1))),
                        dash=dash,
                        tags=tags,
                    )
                else:
                    created_id = canvas.create_line(
                        *coords,
                        fill=options.get("fill", "black"),
                        width=int(float(options.get("width", 1))),
                        tags=tags,
                    )
            elif item_type == "oval":
                created_id = canvas.create_oval(
                    *coords,
                    fill=options.get("fill", ""),
                    outline=options.get("outline", ""),
                    width=int(float(options.get("width", 1))),
                    tags=tags,
                )
            elif item_type == "rectangle":
                created_id = canvas.create_rectangle(
                    *coords,
                    fill=options.get("fill", ""),
                    outline=options.get("outline", ""),
                    width=int(float(options.get("width", 1))),
                    tags=tags,
                )
            elif item_type == "polygon":
                created_id = canvas.create_polygon(
                    *coords,
                    fill=options.get("fill", ""),
                    outline=options.get("outline", ""),
                    width=int(float(options.get("width", 1))),
                    tags=tags,
                )

            # Store recreated id so redo can delete it.
            if created_id is not None:
                action["new_id"] = created_id
        
        elif t == "delete_furniture":
            # Undo furniture deletion: recreate the furniture item
            from Furniture import Furniture
            
            try:
                image_path = action.get("image_path")
                x = action.get("x", 0)
                y = action.get("y", 0)
                scale = action.get("scale", 1.0)
                angle = action.get("angle", 0)
                
                if image_path and self.tools:
                    furniture_item = Furniture(
                        canvas=canvas,
                        image_path=image_path,
                        x=x,
                        y=y,
                        select_callback=getattr(self.tools, "select_image_item", None),
                        scale=scale,
                        angle=angle,
                        get_freeze_state=lambda: getattr(self.tools, "canvas_frozen", False),
                        edit_callback=getattr(self.tools, "enter_furniture_edit_mode", None),
                        duplicate_callback=getattr(self.tools, "duplicate_furniture", None),
                        delete_callback=getattr(self.tools, "delete_furniture_item", None),
                        target_size=action.get("target_size"),
                    )
                    furniture_item.real_size_ft = action.get("real_size_ft")
                    furniture_item.model_ref = getattr(self.tools, "model", None)
                    furniture_item.initial_angle = float(action.get("initial_angle", angle)) % 360
                    
                    # Add to furniture items list
                    if hasattr(self.tools, "image_furniture_items"):
                        self.tools.image_furniture_items.append(furniture_item)
                    
                    # Lock furniture by default; require right-click → Edit for changes
                    try:
                        ok = getattr(self.tools, "commit_furniture_to_underlying_group", lambda _f: False)(furniture_item)
                    except Exception:
                        ok = False
                    if not ok:
                        try:
                            furniture_item.committed = True
                            furniture_item.editing = False
                        except Exception:
                            pass
                    
                    # Update action with new image_id for future redo
                    action["image_id"] = furniture_item.image_id
            except Exception as e:
                print(f"[Undo delete_furniture] Error: {e}")


        elif t == "delete_group":
            # Restore all items in the group
            self._recreate_items(canvas, action["items"])

        elif t == "replace_group":
            # Replace new items with old items (undo a replace)
            for item_id in action.get("new_ids") or []:
                try:
                    canvas.delete(item_id)
                except Exception:
                    pass
            old_items = action.get("old_items") or []
            old_ids_created = self._recreate_items(canvas, old_items)
            action["old_ids"] = old_ids_created

            if action.get("subtype") == "vastu_zone_change" and self.tools:
                model = getattr(self.tools, "model", None)
                if model:
                    try:
                        before = action.get("vastu_model_before") or {}
                        if before:
                            model.set("vastu_zone_count", before.get("vastu_zone_count", 8))
                            model.set("vastu_polygon_draw_type", before.get("vastu_polygon_draw_type", "slices"))
                    except Exception:
                        pass
                try:
                    new_ids_set = set(action.get("new_ids") or [])
                    for a in reversed(self.undo_stack or []):
                        if a.get("type") != "create":
                            continue
                        dim_rec = a.get("dimension_recompute") or {}
                        if isinstance(dim_rec, dict) and dim_rec.get("group_tag") == "vastu_group":
                            items = set(a.get("items") or [])
                            items -= new_ids_set
                            items.update(old_ids_created)
                            a["items"] = list(items)
                            break
                except Exception:
                    pass

        elif t == "flooring_apply":
            # Undo flooring: remove new, restore old (if any)
            self._delete_flooring_items(canvas, action.get("new") or {})
            old = action.get("old")
            if old:
                created = self._recreate_flooring(canvas, old)
                if created:
                    # Update ids in action dict so redo can delete them correctly
                    old["image_id"] = created.get("image_id")
                    old["border_id"] = created.get("border_id")

        elif t == "move":
            item = action["item"]
            # For user_text: before reversing, update the create action's snapshot with
            # current (relocated) position so Redo create restores text at moved position
            try:
                tags = canvas.gettags(item)
                if canvas.type(item) == "text" and tags and "user_text" in tags:
                    curr_coords = canvas.coords(item)
                    if curr_coords and len(curr_coords) >= 2:
                        for create_action in self.undo_stack:
                            if create_action.get("type") != "create":
                                continue
                            items_list = create_action.get("items") or []
                            if item not in items_list:
                                continue
                            idx = items_list.index(item)
                            snapshots = create_action.get("items_snapshot") or []
                            if idx < len(snapshots):
                                snapshots[idx]["coords"] = list(curr_coords)
                            break
            except Exception:
                pass

            dx = action["from"][0] - action["to"][0]
            dy = action["from"][1] - action["to"][1]
            canvas.move(item, dx, dy)

        elif t == "fill":
            item = action.get("item")
            if not item:
                return
            old_color = action.get("old_color", "")
            try:
                canvas.itemconfig(item, fill=old_color)
            except Exception:
                pass

        elif t == "move_group":
            group_tag = action.get("tag")
            if not group_tag:
                return
            dx = action["from"][0] - action["to"][0]
            dy = action["from"][1] - action["to"][1]

            if action.get("entire_layout"):
                scope = action.get("layout_scope")
                items = list(scope.get("item_ids", [])) if scope else list(action.get("items", []))
                if scope and scope.get("selection_outline_id"):
                    items.append(scope["selection_outline_id"])
                for item in items:
                    try:
                        canvas.move(item, dx, dy)
                    except Exception:
                        pass
                if self.tools and hasattr(self.tools, "shift_entire_layout_state"):
                    self.tools.shift_entire_layout_state(dx, dy, scope)
                return

            # Shift in-memory baseline coordinates to prevent centroid drift shift during door cuts
            if group_tag.startswith("polygon_group_") and self.tools and hasattr(self.tools, "_polygon_baseline_coords_by_group"):
                try:
                    baseline = self.tools._polygon_baseline_coords_by_group.get(group_tag)
                    if baseline:
                        self.tools._polygon_baseline_coords_by_group[group_tag] = [
                            (float(v) + dx if i % 2 == 0 else float(v) + dy)
                            for i, v in enumerate(baseline)
                        ]
                except Exception:
                    pass

            items = canvas.find_withtag(group_tag)
            for item in items:
                canvas.move(item, dx, dy)

            if group_tag.startswith("polygon_group_") and self.tools and hasattr(self.tools, "polygon_rooms_map"):
                room_groups = self.tools.polygon_rooms_map.get(group_tag, [])
                for room_group_tag in room_groups:
                    room_items = canvas.find_withtag(room_group_tag)
                    for room_item in room_items:
                        canvas.move(room_item, dx, dy)
                if hasattr(self.tools, "move_user_text_inside_polygon"):
                    try:
                        self.tools.move_user_text_inside_polygon(
                            group_tag, dx, dy, text_check_offset=(dx, dy)
                        )
                    except Exception:
                        pass

        elif t == "grid_toggle":
            # Reverse grid toggle: toggle it back
            if self.tools and hasattr(self.tools, "view"):
                self.tools.view.toggle_grid()

        elif t == "delete_dimension":
            # Undo deletion: recreate the dimension
            if self.tools and hasattr(self.tools, "dimension_drawer"):
                group_tag = action.get("group_tag")
                points = action.get("points")
                edge_idx = action.get("edge_idx")
                if group_tag and points and edge_idx is not None:
                    try:
                        # We need to draw just this edge. 
                        # DimensionDrawer.draw_polygon_edge_dimensions draws all, 
                        # but we can pass just the two points of the edge.
                        # Wait, that might not work perfectly because of centroid/normals.
                        # Better to have a way to draw specific edge or just draw all and delete others?
                        # Actually, we can just call draw_polygon_edge_dimensions with all points
                        # but only if we want to restore ALL.
                        # The user wants "jo select kiya sirf vo gayab hoga".
                        # So undo should only restore THAT one.
                        
                        # Let's add a helper to DimensionDrawer to draw a single edge.
                        p0 = points[edge_idx]
                        p1 = points[(edge_idx + 1) % len(points)]
                        dim_tag = action.get("dim_tag")
                        
                        # Re-draw the edge dimensions
                        # We need the centroid for outward normal
                        centroid = action.get("centroid")
                        parent_dim_tag = f"{group_tag}__dims"
                        
                        # I'll add draw_single_edge_dimension to DimensionDrawer.
                        if hasattr(self.tools.dimension_drawer, "draw_single_edge_dimension"):
                            self.tools.dimension_drawer.draw_single_edge_dimension(
                                p0, p1, centroid,
                                group_tag=group_tag,
                                dim_tag=dim_tag,
                                parent_dim_tag=parent_dim_tag
                            )
                    except Exception as e:
                        print(f"[Undo delete_dimension] Error: {e}")

    def _apply_action(self, canvas, action):
        t = action["type"]

        if t == "project_snapshot":
            if not self.serializer:
                raise RuntimeError("project snapshot history requires a serializer")
            self.serializer.apply_project_snapshot(action["after"])
            return

        if t == "delete_duplicated_layout":
            scope = action.get("scope")
            if self.serializer and scope:
                self.serializer._remove_duplicated_layout(scope)
            return

        if t == "duplicate_layout":
            if self.serializer:
                self.serializer._recreate_duplicated_layout(action.get("data", {}), action)
            return

        if t == "create":
            snapshots = action.get("items_snapshot") or []
            if not snapshots:
                return
            new_ids = []
            for item_data in snapshots:
                item_type = item_data.get("type")
                coords = item_data.get("coords") or []
                options = item_data.get("options") or {}
                tags = item_data.get("tags", ())

                created_id = None
                if item_type == "text":
                    kwargs = {
                        "text": options.get("text", ""),
                        "fill": options.get("fill", "black"),
                        "font": options.get("font", ("Arial", 10)),
                        "tags": tags,
                    }
                    anchor = options.get("anchor")
                    if anchor:
                        kwargs["anchor"] = anchor
                    justify = options.get("justify")
                    if justify:
                        kwargs["justify"] = justify
                    try:
                        w = options.get("width")
                        if str(w).strip():
                            kwargs["width"] = int(float(w))
                    except Exception:
                        pass
                    created_id = canvas.create_text(*coords, **kwargs)
                elif item_type == "line":
                    dash = self._normalize_dash(options.get("dash"))
                    if dash:
                        created_id = canvas.create_line(
                            *coords,
                            fill=options.get("fill", "black"),
                            width=int(float(options.get("width", 1))),
                            dash=dash,
                            tags=tags,
                        )
                    else:
                        created_id = canvas.create_line(
                            *coords,
                            fill=options.get("fill", "black"),
                            width=int(float(options.get("width", 1))),
                            tags=tags,
                        )
                elif item_type == "oval":
                    created_id = canvas.create_oval(
                        *coords,
                        fill=options.get("fill", ""),
                        outline=options.get("outline", ""),
                        width=int(float(options.get("width", 1))),
                        tags=tags,
                    )
                elif item_type == "rectangle":
                    created_id = canvas.create_rectangle(
                        *coords,
                        fill=options.get("fill", ""),
                        outline=options.get("outline", ""),
                        width=int(float(options.get("width", 1))),
                        tags=tags,
                    )
                elif item_type == "polygon":
                    dash = self._normalize_dash(options.get("dash"))
                    if dash:
                        created_id = canvas.create_polygon(
                            *coords,
                            fill=options.get("fill", ""),
                            outline=options.get("outline", ""),
                            width=int(float(options.get("width", 1))),
                            dash=dash,
                            tags=tags,
                        )
                    else:
                        created_id = canvas.create_polygon(
                            *coords,
                            fill=options.get("fill", ""),
                            outline=options.get("outline", ""),
                            width=int(float(options.get("width", 1))),
                            tags=tags,
                        )

                if created_id is not None:
                    new_ids.append(created_id)

            # If original snapshot contained dimension labels rendered as images,
            # recreate them procedurally from the polygon geometry so measurements
            # (text) also reappear after redo.
            try:
                has_dim_images = any(
                    (item.get("type") == "image" and "dimension_item" in (item.get("tags") or ()))
                    for item in snapshots
                )
            except Exception:
                has_dim_images = False

            # Normal dimension labels are rendered as images (PIL rotated text), which are not
            # snapshot-able in a cross-platform way. So we support explicit recompute metadata
            # from the action dict as well.
            dim_recompute = action.get("dimension_recompute") or None

            if (has_dim_images or dim_recompute) and self.tools and hasattr(self.tools, "dimension_drawer"):
                poly_points = []
                group_tag = None
                dim_tag = None
                try:
                    if isinstance(dim_recompute, dict):
                        group_tag = dim_recompute.get("group_tag")
                        dim_tag = dim_recompute.get("dim_tag")
                except Exception:
                    group_tag = None
                    dim_tag = None

                # Extract polygon coords for the requested group_tag
                for snap in snapshots:
                    if snap.get("type") != "polygon":
                        continue
                    tags = snap.get("tags") or ()

                    if group_tag:
                        try:
                            if group_tag not in tags:
                                continue
                        except Exception:
                            continue
                    else:
                        for tag in tags:
                            if isinstance(tag, str) and tag.startswith("polygon_group_"):
                                group_tag = tag
                                break
                        if not group_tag:
                            continue

                    coords = snap.get("coords") or []
                    if coords and len(coords) >= 6:
                        poly_points = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
                    if group_tag and poly_points:
                        break

                if group_tag and poly_points:
                    if not dim_tag:
                        dim_tag = f"{group_tag}__dims"
                    try:
                        dim_ids = self.tools.dimension_drawer.draw_polygon_edge_dimensions(
                            poly_points,
                            group_tag=str(group_tag),
                            dim_tag=str(dim_tag),
                        )
                        for did in dim_ids or []:
                            new_ids.append(did)
                    except Exception:
                        pass

            if new_ids:
                action["items"] = new_ids

        elif t == "replace_group":
            # Redo replace: delete old items and recreate new items
            for item_id in action.get("old_ids") or []:
                try:
                    canvas.delete(item_id)
                except Exception:
                    pass
            new_items = action.get("new_items") or []
            new_ids_created = self._recreate_items(canvas, new_items)
            action["new_ids"] = new_ids_created

            if action.get("subtype") == "vastu_zone_change" and self.tools:
                model = getattr(self.tools, "model", None)
                if model:
                    try:
                        after = action.get("vastu_model_after") or {}
                        if after:
                            model.set("vastu_zone_count", after.get("vastu_zone_count", 8))
                            model.set("vastu_polygon_draw_type", after.get("vastu_polygon_draw_type", "slices"))
                    except Exception:
                        pass
                try:
                    old_ids_set = set(action.get("old_ids") or [])
                    for a in reversed(self.undo_stack or []):
                        if a.get("type") != "create":
                            continue
                        dim_rec = a.get("dimension_recompute") or {}
                        if isinstance(dim_rec, dict) and dim_rec.get("group_tag") == "vastu_group":
                            items = set(a.get("items") or [])
                            items -= old_ids_set
                            items.update(new_ids_created)
                            a["items"] = list(items)
                            break
                except Exception:
                    pass

        elif t == "create_room":
            payload = action.get("room_payload") or {}
            if not payload or not self.tools:
                return
            try:
                from entities import RoomEntity
            except Exception:
                return

            try:
                room = RoomEntity(
                    canvas,
                    getattr(self.tools, "model", None),
                    payload.get("name", "Room"),
                    payload.get("width", 0),
                    payload.get("height", 0),
                    payload.get("group_id", 0),
                    fill_mode=payload.get("fill_mode", "filled"),
                    fill_color=payload.get("fill_color"),
                )
            except Exception:
                return

            if hasattr(self.tools, "room_entities_by_group_tag"):
                try:
                    self.tools.room_entities_by_group_tag[room.group_tag] = room
                except Exception:
                    pass

            polygon_group_tag = payload.get("polygon_group_tag")
            if polygon_group_tag and hasattr(self.tools, "polygon_rooms_map"):
                try:
                    group_list = self.tools.polygon_rooms_map.setdefault(polygon_group_tag, [])
                    if room.group_tag not in group_list:
                        group_list.append(room.group_tag)
                except Exception:
                    pass

            action["group_tag"] = room.group_tag
            action["items"] = getattr(room, "items", [])

        elif t == "create_furniture":
            # Redo furniture creation: recreate the furniture item
            from Furniture import Furniture
            
            try:
                image_path = action.get("image_path")
                x = action.get("x", 0)
                y = action.get("y", 0)
                scale = action.get("scale", 1.0)
                angle = action.get("angle", 0)
                target_size = action.get("target_size")
                
                if image_path and self.tools:
                    furniture_item = Furniture(
                        canvas=canvas,
                        image_path=image_path,
                        x=x,
                        y=y,
                        select_callback=getattr(self.tools, "select_image_item", None),
                        scale=scale,
                        angle=angle,
                        get_freeze_state=lambda: getattr(self.tools, "canvas_frozen", False),
                        edit_callback=getattr(self.tools, "enter_furniture_edit_mode", None),
                        duplicate_callback=getattr(self.tools, "duplicate_furniture", None),
                        delete_callback=getattr(self.tools, "delete_furniture_item", None),
                        target_size=target_size,
                    )
                    
                    # Store real size if available
                    real_size_ft = action.get("real_size_ft")
                    if real_size_ft:
                        furniture_item.real_size_ft = real_size_ft
                        furniture_item.model_ref = getattr(self.tools, "model", None)
                    furniture_item.initial_angle = float(action.get("initial_angle", angle)) % 360
                    
                    # Add to furniture items list
                    if hasattr(self.tools, "image_furniture_items"):
                        self.tools.image_furniture_items.append(furniture_item)
                    
                    # If it was a door, cut wall again
                    if "door" in image_path.lower() and hasattr(self.tools, "_cut_wall_for_door"):
                        real_w_ft, real_h_ft = real_size_ft if real_size_ft else (3, 3)
                        self.tools._cut_wall_for_door(furniture_item, real_w_ft, real_h_ft)
                    
                    # Lock furniture by default; require right-click → Edit for changes
                    try:
                        ok = getattr(self.tools, "commit_furniture_to_underlying_group", lambda _f: False)(furniture_item)
                    except Exception:
                        ok = False
                    if not ok:
                        try:
                            furniture_item.committed = True
                            furniture_item.editing = False
                        except Exception:
                            pass
                    
                    # Update action with new image_id for future undo
                    action["image_id"] = furniture_item.image_id
            except Exception as e:
                print(f"[Redo] Error recreating furniture: {e}")

        elif t == "delete":
            # Two supported schemas:
            # 1) Snapshot-based delete: delete the recreated id
            # 2) Legacy id-list delete: delete the ids (best-effort)
            new_id = action.get("new_id")
            if new_id:
                try:
                    canvas.delete(new_id)
                except Exception:
                    pass
                return

            items = action.get("items") or []
            for item_id in items:
                try:
                    canvas.delete(item_id)
                except Exception:
                    pass
        
        elif t == "delete_furniture":
            # Redo furniture deletion: remove the image and all selection artifacts.
            image_id = action.get("image_id")
            if image_id:
                removed_object = False
                if self.tools and hasattr(self.tools, "image_furniture_items"):
                    try:
                        for furniture_obj in list(self.tools.image_furniture_items):
                            if getattr(furniture_obj, "image_id", None) != image_id:
                                continue
                            furniture_obj.delete()
                            furniture_obj.is_selected = False
                            self.tools.image_furniture_items.remove(furniture_obj)
                            if getattr(self.tools, "selected_furniture_obj", None) is furniture_obj:
                                self.tools.selected_furniture_obj = None
                            removed_object = True
                            break
                    except Exception as e:
                        print(f"[Redo delete_furniture] Error removing furniture from list: {e}")
                if not removed_object:
                    try:
                        canvas.delete(image_id)
                    except Exception:
                        pass

        elif t == "move":
            item = action["item"]
            dx = action["to"][0] - action["from"][0]
            dy = action["to"][1] - action["from"][1]
            canvas.move(item, dx, dy)

        elif t == "fill":
            item = action.get("item")
            if not item:
                return
            new_color = action.get("color", "")
            try:
                canvas.itemconfig(item, fill=new_color)
            except Exception:
                pass

        elif t == "move_group":
            group_tag = action.get("tag")
            if not group_tag:
                return
            dx = action["to"][0] - action["from"][0]
            dy = action["to"][1] - action["from"][1]

            if action.get("entire_layout"):
                scope = action.get("layout_scope")
                items = list(scope.get("item_ids", [])) if scope else list(action.get("items", []))
                if scope and scope.get("selection_outline_id"):
                    items.append(scope["selection_outline_id"])
                for item in items:
                    try:
                        canvas.move(item, dx, dy)
                    except Exception:
                        pass
                if self.tools and hasattr(self.tools, "shift_entire_layout_state"):
                    self.tools.shift_entire_layout_state(dx, dy, scope)
                return

            # Shift in-memory baseline coordinates to prevent centroid drift shift during door cuts
            if group_tag.startswith("polygon_group_") and self.tools and hasattr(self.tools, "_polygon_baseline_coords_by_group"):
                try:
                    baseline = self.tools._polygon_baseline_coords_by_group.get(group_tag)
                    if baseline:
                        self.tools._polygon_baseline_coords_by_group[group_tag] = [
                            (float(v) + dx if i % 2 == 0 else float(v) + dy)
                            for i, v in enumerate(baseline)
                        ]
                except Exception:
                    pass

            items = canvas.find_withtag(group_tag)
            for item in items:
                canvas.move(item, dx, dy)

            if group_tag.startswith("polygon_group_") and self.tools and hasattr(self.tools, "polygon_rooms_map"):
                room_groups = self.tools.polygon_rooms_map.get(group_tag, [])
                for room_group_tag in room_groups:
                    room_items = canvas.find_withtag(room_group_tag)
                    for room_item in room_items:
                        canvas.move(room_item, dx, dy)
                if hasattr(self.tools, "move_user_text_inside_polygon"):
                    try:
                        self.tools.move_user_text_inside_polygon(group_tag, dx, dy)
                    except Exception:
                        pass

        elif t == "flooring_apply":
            # Redo flooring: remove old (if present), recreate new
            old = action.get("old")
            if old:
                self._delete_flooring_items(canvas, old)
            new = action.get("new") or {}
            created = self._recreate_flooring(canvas, new)
            if created:
                new["image_id"] = created.get("image_id")
                new["border_id"] = created.get("border_id")

        elif t == "grid_toggle":
            # Apply grid toggle: toggle it
            if self.tools and hasattr(self.tools, "view"):
                self.tools.view.toggle_grid()

        elif t == "delete_dimension":
            # Redo deletion: delete the dimension again
            dim_tag = action.get("dim_tag")
            if dim_tag and self.tools and hasattr(self.tools, "dimension_drawer"):
                self.tools.dimension_drawer.clear_dimensions_for_group(dim_tag)

    # ---------------- Flooring helpers (internal) ----------------

    def _delete_flooring_items(self, canvas, payload: dict) -> None:
        """
        Best-effort removal of flooring visuals associated with the payload.
        Deletes by explicit ids first, then by group tag to catch rescaled/recreated
        flooring items whose ids may have changed.
        """
        try:
            img_id = payload.get("image_id")
            if img_id:
                canvas.delete(img_id)
        except Exception:
            pass
        try:
            border_id = payload.get("border_id")
            if border_id:
                canvas.delete(border_id)
        except Exception:
            pass

        # Extra safety: if a group tag is provided, remove any flooring items
        # currently associated with that group, even if their ids changed
        # (for example after zoom-driven rescaling).
        try:
            group_tag = payload.get("group_tag")
        except Exception:
            group_tag = None
        if not group_tag:
            return

        try:
            items = canvas.find_withtag(group_tag)
        except Exception:
            items = ()

        for item_id in items:
            try:
                tags = canvas.gettags(item_id)
            except Exception:
                continue
            if ("flooring" in tags) or ("flooring_border" in tags):
                try:
                    canvas.delete(item_id)
                except Exception:
                    continue

    def _recreate_flooring(self, canvas, payload: dict) -> dict | None:
        """
        Recreate flooring image from payload.
        Payload format (minimal):
        - kind: "room" | "polygon"
        - image_path: str
        - group_tag: str|None
        - room_bbox: [x0,y0,x1,y1] (kind="room")
        - polygon_coords: [x0,y0,x1,y1,...] (kind="polygon")
        """
        kind = payload.get("kind")
        image_path = payload.get("image_path")
        if not kind or not image_path:
            return None
        group_tag = payload.get("group_tag")

        # Lazily import PIL only when needed
        try:
            from PIL import Image, ImageTk, ImageDraw
        except Exception:
            return None

        # Keep PhotoImage references on canvas to prevent GC
        if not hasattr(canvas, "_flooring_image_refs"):
            try:
                setattr(canvas, "_flooring_image_refs", {})
            except Exception:
                pass

        refs = getattr(canvas, "_flooring_image_refs", {})

        if kind == "room":
            bbox = payload.get("room_bbox")
            if not bbox or len(bbox) != 4:
                return None
            x0, y0, x1, y1 = map(int, bbox)
            w = max(1, int(abs(x1 - x0)))
            h = max(1, int(abs(y1 - y0)))

            img = Image.open(image_path)
            img = img.resize((w, h), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img, master=canvas)
            tags = ("flooring", group_tag) if group_tag else ("flooring",)
            image_id = canvas.create_image(x0, y0, image=tk_img, anchor="nw", tags=tags)

            border_tags = ("flooring_border", group_tag) if group_tag else ("flooring_border",)
            border_id = canvas.create_rectangle(x0, y0, x1, y1, outline="black", width=2, tags=border_tags)

            # Z‑order: mimic tools.apply_flooring_to_room so that room labels/furniture
            # stay visible above flooring even after redo.
            try:
                if group_tag:
                    try:
                        group_items = canvas.find_withtag(group_tag)
                    except Exception:
                        group_items = ()
                    for item in group_items:
                        try:
                            if canvas.type(item) == "text":
                                canvas.tag_raise(item, image_id)
                                canvas.tag_raise(item, border_id)
                        except Exception:
                            continue
                # Keep furniture above flooring (best-effort)
                try:
                    canvas.tag_raise("furniture")
                except Exception:
                    pass
            except Exception:
                pass

            try:
                refs[image_id] = tk_img
            except Exception:
                pass
            try:
                setattr(canvas, "_flooring_image_refs", refs)
            except Exception:
                pass

            return {"image_id": image_id, "border_id": border_id}

        if kind == "polygon":
            coords = payload.get("polygon_coords")
            if not coords or len(coords) < 6:
                return None

            xs = coords[::2]
            ys = coords[1::2]
            x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
            w = max(1, int(x1 - x0))
            h = max(1, int(y1 - y0))

            img = Image.open(image_path).resize((w, h), Image.Resampling.LANCZOS)

            mask = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(mask)
            poly_rel = [(coords[i] - x0, coords[i + 1] - y0) for i in range(0, len(coords), 2)]
            draw.polygon(poly_rel, fill=255)

            result = Image.new("RGBA", (w, h))
            result.paste(img, (0, 0), mask)

            tk_img = ImageTk.PhotoImage(result, master=canvas)
            tags = ("flooring", group_tag) if group_tag else ("flooring",)
            image_id = canvas.create_image(x0, y0, image=tk_img, anchor="nw", tags=tags)

            # Z‑order for polygon flooring: keep flooring under polygon outline
            # and keep polygon vertices/labels above flooring, same as when
            # flooring is first applied in tools.apply_flooring_to_polygon.
            try:
                if group_tag:
                    polygon_item_id = None
                    try:
                        group_items = canvas.find_withtag(group_tag)
                    except Exception:
                        group_items = ()
                    for it in group_items:
                        try:
                            t = canvas.type(it)
                            tags_it = canvas.gettags(it)
                        except Exception:
                            continue
                        if polygon_item_id is None and "closed_shape" in tags_it:
                            polygon_item_id = it
                        if t == "oval" and "polygon_vertex" in tags_it:
                            try:
                                canvas.tag_raise(it, image_id)
                            except Exception:
                                pass
                        if t == "text" and "polygon_label" in tags_it:
                            try:
                                canvas.tag_raise(it, image_id)
                            except Exception:
                                pass
                    if polygon_item_id is not None:
                        try:
                            canvas.tag_lower(image_id, polygon_item_id)
                            canvas.tag_raise(polygon_item_id, image_id)
                        except Exception:
                            pass
            except Exception:
                pass

            try:
                refs[image_id] = tk_img
            except Exception:
                pass
            try:
                setattr(canvas, "_flooring_image_refs", refs)
            except Exception:
                pass

            return {"image_id": image_id, "border_id": None}

        return None

    def _snapshot_canvas_items(self, canvas, items):
        snapshots = []
        for item_id in items or []:
            try:
                item_type = canvas.type(item_id)
            except Exception:
                continue
            try:
                coords = list(canvas.coords(item_id))
            except Exception:
                coords = []

            options = {}
            try:
                if item_type == "text":
                    options["text"] = canvas.itemcget(item_id, "text")
                    options["fill"] = canvas.itemcget(item_id, "fill")
                    options["font"] = canvas.itemcget(item_id, "font")
                    options["anchor"] = canvas.itemcget(item_id, "anchor")
                    options["justify"] = canvas.itemcget(item_id, "justify")
                    options["width"] = canvas.itemcget(item_id, "width")
                elif item_type in {"line", "oval", "rectangle", "polygon"}:
                    options["fill"] = canvas.itemcget(item_id, "fill")
                    options["outline"] = canvas.itemcget(item_id, "outline")
                    options["width"] = canvas.itemcget(item_id, "width")
                    options["dash"] = canvas.itemcget(item_id, "dash")
            except Exception:
                pass

            try:
                tags = canvas.gettags(item_id)
            except Exception:
                tags = ()

            snapshots.append({
                "type": item_type,
                "coords": coords,
                "options": options,
                "tags": tags,
            })
        return snapshots

    def drop_vastu_actions(self):
        """
        Remove Vastu-related create actions from undo/redo stacks so that
        erasing a Vastu polygon cannot be undone/redone later.
        """
        def _filter(stack):
            filtered = []
            for action in list(stack or []):
                try:
                    t = action.get("type")
                except Exception:
                    filtered.append(action)
                    continue
                if t != "create":
                    filtered.append(action)
                    continue
                snapshots = action.get("items_snapshot") or []
                if not snapshots:
                    filtered.append(action)
                    continue
                remove = False
                for snap in snapshots:
                    try:
                        tags = snap.get("tags") or ()
                    except Exception:
                        continue
                    for tag in tags:
                        if not isinstance(tag, str):
                            continue
                        if tag in {
                            "vastu_group",
                            "vastu_polygon",
                            "vastu_centroid",
                            "vastu_north_marker",
                            "vastu_division_line",
                        }:
                            remove = True
                            break
                        if tag.startswith("vastu_zone_"):
                            remove = True
                            break
                    if remove:
                        break
                if remove:
                    continue
                filtered.append(action)
            return filtered

        try:
            self.undo_stack = _filter(self.undo_stack)
            self.redo_stack = _filter(self.redo_stack)
        except Exception:
            pass
