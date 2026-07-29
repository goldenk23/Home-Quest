import math
import tkinter as tk

class GuidelineHelper:
    """
    Provides AutoCAD-style guidelines for polygon creation:
    - Snap to existing vertices
    - Orthogonal alignment guides (horizontal/vertical)
    - Distance and angle display
    """
    
    def __init__(self, canvas, model):
        self.canvas = canvas
        self.model = model
        self.snap_distance = 10  # pixels
        self.ortho_tolerance = 3  # pixels for orthogonal alignment
        self.grid_interval = 1.0  # interval for grid guidelines (1 unit)
        self.grid_snap_tolerance = 8  # pixels tolerance for grid snapping
        self.guide_lines = []  # No longer strictly needed but kept for backward compatibility if any
        self.info_label_id = None
        
        self.line_pool = []
        self.arc_pool = []
        self.oval_pool = []
        self.text_pool = []
        self._line_idx = 0
        self._arc_idx = 0
        self._oval_idx = 0
        self._text_idx = 0

        # Stabilize grid snapping near half-boundaries during auto-pan/infinite scroll.
        self._grid_snap_last_coord: dict[str, float | None] = {"x": None, "y": None}

        # Advanced CAD Snap Engine integration
        from Helper.cad_snapping import AdvancedCADSnapper
        self.cad_snapper = AdvancedCADSnapper(self.canvas, self.model)

    def on_zoom_changed(self, scale_factor: float) -> None:
        """
        Keep snap/ortho tolerances stable in *world* units.
        """
        try:
            sf = float(scale_factor)
        except Exception:
            return
        if abs(sf - 1.0) < 1e-12:
            return
        try:
            self.snap_distance = float(self.snap_distance) * sf
            self.ortho_tolerance = float(self.ortho_tolerance) * sf
            self.grid_snap_tolerance = float(self.grid_snap_tolerance) * sf
        except Exception:
            pass
        
    def clear_guides(self):
        """Hide all guide items instead of deleting them to enable pooling."""
        for item in self.line_pool:
            try: self.canvas.itemconfig(item, state="hidden")
            except Exception: pass
        for item in self.arc_pool:
            try: self.canvas.itemconfig(item, state="hidden")
            except Exception: pass
        for item in self.oval_pool:
            try: self.canvas.itemconfig(item, state="hidden")
            except Exception: pass
        for item in self.text_pool:
            try: self.canvas.itemconfig(item, state="hidden")
            except Exception: pass
        
        try:
            self.cad_snapper.clear_snaps()
        except Exception:
            pass

        self._line_idx = 0
        self._arc_idx = 0
        self._oval_idx = 0
        self._text_idx = 0
        self.info_label_id = None

    def _get_pooled_line(self, x0, y0, x1, y1, **kwargs):
        if self._line_idx < len(self.line_pool):
            line_id = self.line_pool[self._line_idx]
            self.canvas.coords(line_id, x0, y0, x1, y1)
            self.canvas.itemconfig(line_id, state="normal", **kwargs)
        else:
            line_id = self.canvas.create_line(x0, y0, x1, y1, **kwargs)
            self.line_pool.append(line_id)
        self._line_idx += 1
        return line_id

    def _get_pooled_arc(self, bbox, **kwargs):
        if self._arc_idx < len(self.arc_pool):
            arc_id = self.arc_pool[self._arc_idx]
            self.canvas.coords(arc_id, *bbox)
            self.canvas.itemconfig(arc_id, state="normal", **kwargs)
        else:
            arc_id = self.canvas.create_arc(*bbox, **kwargs)
            self.arc_pool.append(arc_id)
        self._arc_idx += 1
        return arc_id

    def _get_pooled_oval(self, bbox, **kwargs):
        if self._oval_idx < len(self.oval_pool):
            oval_id = self.oval_pool[self._oval_idx]
            self.canvas.coords(oval_id, *bbox)
            self.canvas.itemconfig(oval_id, state="normal", **kwargs)
        else:
            oval_id = self.canvas.create_oval(*bbox, **kwargs)
            self.oval_pool.append(oval_id)
        self._oval_idx += 1
        return oval_id

    def _get_pooled_text(self, x, y, text, **kwargs):
        if self._text_idx < len(self.text_pool):
            text_id = self.text_pool[self._text_idx]
            self.canvas.coords(text_id, x, y)
            self.canvas.itemconfig(text_id, state="normal", text=text, **kwargs)
        else:
            text_id = self.canvas.create_text(x, y, text=text, **kwargs)
            self.text_pool.append(text_id)
        self._text_idx += 1
        return text_id
    
    def _get_grid_snap_point(self, coord, origin_coord: float = 0.0, *, axis: str = "x"):
        """
        Calculate the nearest grid interval point for a coordinate.
        """
        delta_px = coord - origin_coord
        unit_factor = self.model.unit_scale.get(self.model.unit, 1.0)
        scale = self.model.grid_spacing * self.model.zoom_level
        
        if scale <= 0:
            return coord, False
        
        real_delta = (delta_px / scale) * unit_factor
        
        grid_multiple = real_delta / self.grid_interval

        def _round_half_away_from_zero(v: float) -> float:
            return math.floor(v + 0.5) if v >= 0 else math.ceil(v - 0.5)

        last_coord = self._grid_snap_last_coord.get(axis)
        direction = 0.0
        if last_coord is not None:
            direction = float(coord) - float(last_coord)

        lower = math.floor(grid_multiple)
        frac = grid_multiple - lower
        candidate_multiple = _round_half_away_from_zero(grid_multiple)

        boundary_eps = 0.001
        if last_coord is not None and abs(frac - 0.5) <= boundary_eps and direction != 0.0:
            chosen_multiple = (lower + 1) if direction > 0 else lower
        else:
            chosen_multiple = candidate_multiple

        nearest_grid = chosen_multiple * self.grid_interval
        
        if self.model.unit == "ft":
            snapped_delta_px = (nearest_grid / unit_factor) * scale
        elif self.model.unit == "m":
            snapped_delta_px = ((nearest_grid / 3.281) / unit_factor) * scale
        elif self.model.unit == "cm":
            snapped_delta_px = ((nearest_grid / 0.03281) / unit_factor) * scale

        snapped_coord = origin_coord + snapped_delta_px
        
        if abs(delta_px - snapped_delta_px) < self.grid_snap_tolerance:
            self._grid_snap_last_coord[axis] = float(coord)
            return snapped_coord, True

        self._grid_snap_last_coord[axis] = float(coord)
        return coord, False
    
    def get_snap_point(self, mouse_x, mouse_y, polygon_points, snap_to_existing=True):
        """
        Calculate the best snap point for the mouse position.
        """
        # Try Advanced CAD Snapping First (Endpoints, Midpoints, Perpendiculars)
        try:
            first_pt = polygon_points[-1] if polygon_points else None
            cad_x, cad_y, cad_info = self.cad_snapper.find_snap_point(mouse_x, mouse_y, first_point=first_pt)
            if cad_info and cad_info.get("snap_type") != "none":
                return cad_x, cad_y, {
                    'snap_type': cad_info["snap_type"],
                    'has_h_align': False,
                    'has_v_align': False,
                    'has_grid_h': False,
                    'has_grid_v': False
                }
        except Exception as e:
            print(f"[Advanced Snapping Error] {e}")

        grid_enabled = bool(self.model.get("grid_snap_enabled"))
        if not polygon_points:
            if not grid_enabled:
                return mouse_x, mouse_y, {
                    'snap_type': 'none',
                    'has_h_align': False,
                    'has_v_align': False,
                    'has_grid_h': False,
                    'has_grid_v': False
                }

            grid_x, grid_snap_x = self._get_grid_snap_point(mouse_x, 0.0, axis="x")
            grid_y, grid_snap_y = self._get_grid_snap_point(mouse_y, 0.0, axis="y")

            snapped_x = grid_x if grid_snap_x else mouse_x
            snapped_y = grid_y if grid_snap_y else mouse_y

            if grid_snap_x or grid_snap_y:
                return snapped_x, snapped_y, {
                    'snap_type': 'grid',
                    'has_h_align': False,
                    'has_v_align': False,
                    'has_grid_h': grid_snap_y,
                    'has_grid_v': grid_snap_x,
                }
            return mouse_x, mouse_y, {
                'snap_type': 'none',
                'has_h_align': False,
                'has_v_align': False,
                'has_grid_h': False,
                'has_grid_v': False
            }
        
        last_point = polygon_points[-1]
        best_x, best_y = mouse_x, mouse_y
        snap_type = 'none'
        has_h_align = False
        has_v_align = False
        has_grid_h = False
        has_grid_v = False
        min_dist = float('inf')
        
        if snap_to_existing:
            for pt in polygon_points:
                dist = math.dist((mouse_x, mouse_y), pt)
                if dist < self.snap_distance and dist < min_dist:
                    min_dist = dist
                    best_x, best_y = pt
                    snap_type = 'vertex'
        
        last_x, last_y = last_point
        
        if abs(mouse_y - last_y) < self.ortho_tolerance:
            best_y = last_y
            has_h_align = True
            if snap_type == 'none':
                snap_type = 'ortho_h'
            elif snap_type == 'ortho_v':
                snap_type = 'ortho_both'
        
        if abs(mouse_x - last_x) < self.ortho_tolerance:
            best_x = last_x
            has_v_align = True
            if snap_type == 'none':
                snap_type = 'ortho_v'
            elif snap_type == 'ortho_h':
                snap_type = 'ortho_both'
        
        for pt in polygon_points[:-1]:
            px, py = pt
            if abs(mouse_y - py) < self.ortho_tolerance:
                if not has_h_align or abs(mouse_y - py) < abs(best_y - py):
                    best_y = py
                    has_h_align = True
                    if snap_type == 'none':
                        snap_type = 'ortho_h'
                    elif snap_type == 'ortho_v':
                        snap_type = 'ortho_both'
            
            if abs(mouse_x - px) < self.ortho_tolerance:
                if not has_v_align or abs(mouse_x - px) < abs(best_x - px):
                    best_x = px
                    has_v_align = True
                    if snap_type == 'none':
                        snap_type = 'ortho_v'
                    elif snap_type == 'ortho_h':
                        snap_type = 'ortho_both'
        
        if grid_enabled and snap_type != 'vertex':
            grid_x, grid_snap_x = self._get_grid_snap_point(best_x, last_x, axis="x")
            grid_y, grid_snap_y = self._get_grid_snap_point(best_y, last_y, axis="y")
            
            if grid_snap_x:
                best_x = grid_x
                has_grid_v = True
                if snap_type == 'none':
                    snap_type = 'grid'
            
            if grid_snap_y:
                best_y = grid_y
                has_grid_h = True
                if snap_type == 'none':
                    snap_type = 'grid'
        
        return best_x, best_y, {
            'snap_type': snap_type,
            'has_h_align': has_h_align,
            'has_v_align': has_v_align,
            'has_grid_h': has_grid_h,
            'has_grid_v': has_grid_v
        }
    
    def draw_guides(self, mouse_x, mouse_y, polygon_points, snapped_x, snapped_y, snap_info):
        """Draw guide lines and info based on snap type."""
        self.clear_guides()
        
        if not polygon_points:
            return
        
        last_x, last_y = polygon_points[-1]
        snap_type = snap_info.get('snap_type', 'none')
        has_h_align = snap_info.get('has_h_align', False)
        has_v_align = snap_info.get('has_v_align', False)
        has_grid_h = snap_info.get('has_grid_h', False)
        has_grid_v = snap_info.get('has_grid_v', False)
        
        try:
            widget_width = self.canvas.winfo_width()
            widget_height = self.canvas.winfo_height()
            if widget_width <= 1 or widget_height <= 1:
                widget_width, widget_height = 1200, 800
        except Exception:
            widget_width, widget_height = 1200, 800

        try:
            view_x0 = self.canvas.canvasx(0)
            view_x1 = self.canvas.canvasx(widget_width)
            view_y0 = self.canvas.canvasy(0)
            view_y1 = self.canvas.canvasy(widget_height)
        except Exception:
            view_x0, view_y0 = 0.0, 0.0
            view_x1, view_y1 = float(widget_width), float(widget_height)
        
        guide_color = "#e63946"
        grid_guide_color = "#ff6b6b"
        guide_width = 1.5
        grid_guide_width = 1.0
        
        if has_grid_h:
            self._get_pooled_line(
                view_x0, snapped_y, view_x1, snapped_y,
                fill=grid_guide_color, width=grid_guide_width, dash=(3, 5),
                tags="guideline_grid"
            )
            
        if has_grid_v:
            self._get_pooled_line(
                snapped_x, view_y0, snapped_x, view_y1,
                fill=grid_guide_color, width=grid_guide_width, dash=(3, 5),
                tags="guideline_grid"
            )
        
        if has_h_align:
            self._get_pooled_line(
                view_x0, snapped_y, view_x1, snapped_y,
                fill=guide_color, width=guide_width, dash=(5, 3),
                tags="guideline"
            )
            
        if has_v_align:
            self._get_pooled_line(
                snapped_x, view_y0, snapped_x, view_y1,
                fill=guide_color, width=guide_width, dash=(5, 3),
                tags="guideline"
            )
        
        dx = snapped_x - last_x
        dy = snapped_y - last_y
        distance = math.hypot(dx, dy)
        
        unit_factor = self.model.unit_scale.get(self.model.unit, 1.0)
        scale = self.model.grid_spacing * self.model.zoom_level
        real_distance = (distance / scale) * unit_factor if scale > 0 else 0
        
        info_text = f"Distance: {real_distance:.2f} {self.model.unit}"
        
        label_x = snapped_x + 15
        label_y = snapped_y - 30
        
        max_x = view_x1 - 100
        min_x = view_x0 + 2
        label_x = max(min_x, min(label_x, max_x))

        if label_y < view_y0 + 20:
            label_y = snapped_y + 20
        max_y = view_y1 - 5
        min_y = view_y0 + 2
        label_y = max(min_y, min(label_y, max_y))
        
        self.info_label_id = self._get_pooled_text(
            label_x, label_y,
            text=info_text,
            font=("Arial", 10),
            fill="#c1121f",
            anchor="nw",
            tags="guideline_info"
        )
        try:
            self.canvas.tag_raise(self.info_label_id)
        except Exception:
            pass
        
        if len(polygon_points) >= 2:
            prev_x, prev_y = polygon_points[-2] if len(polygon_points) >= 2 else polygon_points[0]
            vertex_x, vertex_y = last_x, last_y
            
            vec1_x = vertex_x - prev_x
            vec1_y = vertex_y - prev_y
            
            vec2_x = snapped_x - vertex_x
            vec2_y = snapped_y - vertex_y
            
            if (vec1_x != 0 or vec1_y != 0) and (vec2_x != 0 or vec2_y != 0):
                len1 = math.hypot(vec1_x, vec1_y)
                len2 = math.hypot(vec2_x, vec2_y)
                
                if len1 > 0 and len2 > 0:
                    dot = (vec1_x * vec2_x + vec1_y * vec2_y) / (len1 * len2)
                    dot = max(-1.0, min(1.0, dot))
                    angle_rad = math.acos(dot)
                    angle_deg = math.degrees(angle_rad)
                    
                    vec1_dir_x = vec1_x / len1
                    vec1_dir_y = vec1_y / len1
                    vec2_dir_x = vec2_x / len2
                    vec2_dir_y = vec2_y / len2
                    
                    angle1 = math.degrees(math.atan2(-vec1_dir_y, -vec1_dir_x))
                    angle2 = math.degrees(math.atan2(vec2_dir_y, vec2_dir_x))
                    
                    if angle1 < 0: angle1 += 360
                    if angle2 < 0: angle2 += 360
                    
                    angle_from_start = angle2 - angle1
                    if angle_from_start < 0: angle_from_start += 360
                    
                    cross = vec1_dir_x * vec2_dir_y - vec1_dir_y * vec2_dir_x
                    
                    if angle_from_start > 180:
                        inner_angle = 360 - angle_from_start
                    else:
                        inner_angle = angle_from_start
                    
                    if abs(inner_angle - 360) < 0.1: inner_angle = 0
                    
                    start_angle = angle1
                    
                    signed_diff = angle2 - angle1
                    if signed_diff > 180: signed_diff -= 360
                    elif signed_diff < -180: signed_diff += 360
                    
                    if angle_from_start > 180:
                        display_angle_value = 360 - angle_from_start
                    else:
                        display_angle_value = angle_from_start

                    if angle_from_start > 180:
                        if signed_diff > 0: extent = -inner_angle
                        else: extent = inner_angle
                    else:
                        if signed_diff > 0:
                            if cross > 0: extent = inner_angle
                            else: extent = -inner_angle
                        else:
                            if cross > 0: extent = inner_angle
                            else: extent = -inner_angle
                        
                        if len(polygon_points) == 2:
                            extent = -extent
                    
                    if start_angle < 0: start_angle += 360
                    
                    arc_radius = 25
                    bbox = (vertex_x - arc_radius, vertex_y - arc_radius, vertex_x + arc_radius, vertex_y + arc_radius)
                    
                    if abs(angle_from_start - 360) < 0.1:
                        extent = 360
                        start_angle = angle1
                    
                    self._get_pooled_arc(
                        bbox,
                        start=start_angle, extent=extent,
                        outline="#e63946", width=2,
                        style="arc",
                        tags="guideline_angle"
                    )
                    
                    if abs(angle_from_start - 360) < 0.1 or abs(display_angle_value) < 0.1:
                        display_angle = 0
                    else:
                        display_angle = display_angle_value
                    
                    # Calculate label position for angle
                    mid_angle_rad = math.radians(start_angle + extent / 2)
                    text_x = vertex_x + (arc_radius + 15) * math.cos(mid_angle_rad)
                    text_y = vertex_y - (arc_radius + 15) * math.sin(mid_angle_rad)

                    self._get_pooled_text(
                        text_x, text_y,
                        text=f"{display_angle:.1f}°",
                        font=("Arial", 9),
                        fill="#c1121f",
                        tags="guideline_angle"
                    )


        # Draw snap indicator circle if snapped to vertex - professional orange-red
        # Draw snap indicator circle if snapped to vertex - professional orange-red
        if snap_type == 'vertex':
            self._get_pooled_oval(
                (snapped_x - 5, snapped_y - 5, snapped_x + 5, snapped_y + 5),
                outline="#d62828", width=2.5,
                fill="#ffb4a2", tags="guideline"  # Light coral fill
            )
        
        # Draw intersection point indicator when both guides are active
        if has_h_align and has_v_align:
            self._get_pooled_oval(
                (snapped_x - 4, snapped_y - 4, snapped_x + 4, snapped_y + 4),
                outline="#e63946", width=2,
                fill="#e63946", tags="guideline"
            )


    def get_room_alignment_snap(self, room_bbox, other_rooms, tolerance=5):
        """
        Calculate alignment snap for a room being dragged.
        
        Args:
            room_bbox: (x0, y0, x1, y1) of the room being dragged
            other_rooms: List of (group_tag, room_entity) tuples for other rooms
            tolerance: Pixel tolerance for alignment detection
            
        Returns:
            (snapped_x0, snapped_y0, snap_info)
            snap_info: dict with alignment flags
        """
        x0, y0, x1, y1 = room_bbox
        room_width = x1 - x0
        room_height = y1 - y0
        room_center_x = (x0 + x1) / 2
        room_center_y = (y0 + y1) / 2
        
        snap_info = {
            'has_top_align': False,
            'has_bottom_align': False,
            'has_left_align': False,
            'has_right_align': False,
            'has_center_h_align': False,
            'has_center_v_align': False,
            'align_y': None,
            'align_x': None,
            'center_align_y': None,
            'center_align_x': None
        }
        
        best_x0, best_y0 = x0, y0
        best_x_dist = float('inf')
        best_y_dist = float('inf')
        
        for group_tag, other_room in other_rooms:
            try:
                # Get current coordinates of other room
                if not hasattr(other_room, 'rect_id'):
                    continue
                    
                other_coords = self.canvas.coords(other_room.rect_id)
                if not other_coords or len(other_coords) < 4:
                    continue
                    
                ox0, oy0, ox1, oy1 = other_coords
                other_center_x = (ox0 + ox1) / 2
                other_center_y = (oy0 + oy1) / 2
                
                # Check top edge alignment (room's top with other's top or bottom)
                dist_top_top = abs(y0 - oy0)
                dist_top_bottom = abs(y0 - oy1)
                
                if dist_top_top < tolerance and dist_top_top < best_y_dist:
                    snap_info['has_top_align'] = True
                    snap_info['align_y'] = oy0
                    best_y0 = oy0
                    best_y_dist = dist_top_top
                elif dist_top_bottom < tolerance and dist_top_bottom < best_y_dist:
                    snap_info['has_top_align'] = True
                    snap_info['align_y'] = oy1
                    best_y0 = oy1
                    best_y_dist = dist_top_bottom
                
                # Check bottom edge alignment (room's bottom with other's top or bottom)
                room_bottom = y1
                dist_bottom_top = abs(room_bottom - oy0)
                dist_bottom_bottom = abs(room_bottom - oy1)
                
                if dist_bottom_top < tolerance:
                    new_y0 = oy0 - room_height
                    dist = abs(y0 - new_y0)
                    if dist < best_y_dist:
                        snap_info['has_bottom_align'] = True
                        snap_info['align_y'] = oy0
                        best_y0 = new_y0
                        best_y_dist = dist
                elif dist_bottom_bottom < tolerance:
                    new_y0 = oy1 - room_height
                    dist = abs(y0 - new_y0)
                    if dist < best_y_dist:
                        snap_info['has_bottom_align'] = True
                        snap_info['align_y'] = oy1
                        best_y0 = new_y0
                        best_y_dist = dist
                
                # Check left edge alignment
                dist_left_left = abs(x0 - ox0)
                dist_left_right = abs(x0 - ox1)
                
                if dist_left_left < tolerance and dist_left_left < best_x_dist:
                    snap_info['has_left_align'] = True
                    snap_info['align_x'] = ox0
                    best_x0 = ox0
                    best_x_dist = dist_left_left
                elif dist_left_right < tolerance and dist_left_right < best_x_dist:
                    snap_info['has_left_align'] = True
                    snap_info['align_x'] = ox1
                    best_x0 = ox1
                    best_x_dist = dist_left_right
                
                # Check right edge alignment
                room_right = x1
                dist_right_left = abs(room_right - ox0)
                dist_right_right = abs(room_right - ox1)
                
                if dist_right_left < tolerance:
                    new_x0 = ox0 - room_width
                    dist = abs(x0 - new_x0)
                    if dist < best_x_dist:
                        snap_info['has_right_align'] = True
                        snap_info['align_x'] = ox0
                        best_x0 = new_x0
                        best_x_dist = dist
                elif dist_right_right < tolerance:
                    new_x0 = ox1 - room_width
                    dist = abs(x0 - new_x0)
                    if dist < best_x_dist:
                        snap_info['has_right_align'] = True
                        snap_info['align_x'] = ox1
                        best_x0 = new_x0
                        best_x_dist = dist
                
                # Check center alignment (vertical - horizontal center line)
                dist_center_v = abs(room_center_x - other_center_x)
                if dist_center_v < tolerance and dist_center_v < best_x_dist:
                    snap_info['has_center_v_align'] = True
                    snap_info['center_align_x'] = other_center_x
                    best_x0 = other_center_x - room_width / 2
                    best_x_dist = dist_center_v
                
                # Check center alignment (horizontal - vertical center line)
                dist_center_h = abs(room_center_y - other_center_y)
                if dist_center_h < tolerance and dist_center_h < best_y_dist:
                    snap_info['has_center_h_align'] = True
                    snap_info['center_align_y'] = other_center_y
                    best_y0 = other_center_y - room_height / 2
                    best_y_dist = dist_center_h
                    
            except Exception:
                continue

        return best_x0, best_y0, snap_info

    def draw_room_alignment_guides(self, room_bbox, snap_info, other_rooms=None):
        """
        Draw alignment guidelines for room dragging.
        
        Args:
            room_bbox: (x0, y0, x1, y1) of the room
            snap_info: Alignment information from get_room_alignment_snap
            other_rooms: Optional list of other rooms to compute and draw distance guides
        """
        self.clear_guides()
        
        x0, y0, x1, y1 = room_bbox
        
        # Get canvas dimensions
        try:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            if canvas_width <= 1 or canvas_height <= 1:
                canvas_width = 1200
                canvas_height = 800
        except Exception:
            canvas_width = 1200
            canvas_height = 800
        
        guide_color = "#e63946"  # Professional red/coral
        guide_width = 1.5
        
        # Draw top edge alignment guide
        if snap_info.get('has_top_align') and snap_info.get('align_y') is not None:
            align_y = snap_info['align_y']
            self._get_pooled_line(
                0, align_y, canvas_width, align_y,
                fill=guide_color, width=guide_width, dash=(5, 3),
                tags="guideline_room"
            )
        
        # Draw bottom edge alignment guide
        if snap_info.get('has_bottom_align') and snap_info.get('align_y') is not None:
            align_y = snap_info['align_y']
            self._get_pooled_line(
                0, align_y, canvas_width, align_y,
                fill=guide_color, width=guide_width, dash=(5, 3),
                tags="guideline_room"
            )
        
        # Draw left edge alignment guide
        if snap_info.get('has_left_align') and snap_info.get('align_x') is not None:
            align_x = snap_info['align_x']
            self._get_pooled_line(
                align_x, 0, align_x, canvas_height,
                fill=guide_color, width=guide_width, dash=(5, 3),
                tags="guideline_room"
            )
        
        # Draw right edge alignment guide
        if snap_info.get('has_right_align') and snap_info.get('align_x') is not None:
            align_x = snap_info['align_x']
            self._get_pooled_line(
                align_x, 0, align_x, canvas_height,
                fill=guide_color, width=guide_width, dash=(5, 3),
                tags="guideline_room"
            )
        
        # Draw center alignment guides
        if snap_info.get('has_center_h_align') and snap_info.get('center_align_y') is not None:
            center_y = snap_info['center_align_y']
            self._get_pooled_line(
                0, center_y, canvas_width, center_y,
                fill="#ff6b6b", width=1.0, dash=(3, 5),
                tags="guideline_room_center"
            )
        
        if snap_info.get('has_center_v_align') and snap_info.get('center_align_x') is not None:
            center_x = snap_info['center_align_x']
            self._get_pooled_line(
                center_x, 0, center_x, canvas_height,
                fill="#ff6b6b", width=1.0, dash=(3, 5),
                tags="guideline_room_center"
            )
            
        # Draw AutoCAD-style real-world distance between rooms if available
        if other_rooms:
            self.draw_room_distance_guides(room_bbox, other_rooms)
    def draw_room_distance_guides(self, room_bbox, other_rooms):
        x0, y0, x1, y1 = room_bbox
        unit = getattr(self.model, "unit", "m")
        scale = (self.model.grid_spacing * self.model.zoom_level) / float(self.model.unit_scale.get(unit, 1.0))
        dist_color = "#3a86c8"
        for group_tag, other_room in other_rooms or []:
            try:
                if not hasattr(other_room, 'rect_id'): continue
                coords = self.canvas.coords(other_room.rect_id)
                if not coords or len(coords) < 4: continue
                ox0, oy0, ox1, oy1 = coords
                if max(y0, oy0) < min(y1, oy1):
                    y_mid = (max(y0, oy0) + min(y1, oy1)) / 2
                    if ox1 <= x0 and x0 - ox1 > 2:
                        self._get_pooled_line(ox1, y_mid, x0, y_mid, fill=dist_color, width=1.5, dash=(4, 2), tags="guideline_room")
                        self._get_pooled_line(ox1, y_mid-6, ox1, y_mid+6, fill=dist_color, width=2, tags="guideline_room")
                        self._get_pooled_line(x0, y_mid-6, x0, y_mid+6, fill=dist_color, width=2, tags="guideline_room")
                        self._get_pooled_text((ox1+x0)/2, y_mid-12, f"{(x0-ox1)/scale:.1f} {unit}", fill=dist_color, font=("Arial", 9, "bold"), tags="guideline_room")
                    elif x1 <= ox0 and ox0 - x1 > 2:
                        self._get_pooled_line(x1, y_mid, ox0, y_mid, fill=dist_color, width=1.5, dash=(4, 2), tags="guideline_room")
                        self._get_pooled_line(x1, y_mid-6, x1, y_mid+6, fill=dist_color, width=2, tags="guideline_room")
                        self._get_pooled_line(ox0, y_mid-6, ox0, y_mid+6, fill=dist_color, width=2, tags="guideline_room")
                        self._get_pooled_text((x1+ox0)/2, y_mid-12, f"{(ox0-x1)/scale:.1f} {unit}", fill=dist_color, font=("Arial", 9, "bold"), tags="guideline_room")
                if max(x0, ox0) < min(x1, ox1):
                    x_mid = (max(x0, ox0) + min(x1, ox1)) / 2
                    if oy1 <= y0 and y0 - oy1 > 2:
                        self._get_pooled_line(x_mid, oy1, x_mid, y0, fill=dist_color, width=1.5, dash=(4, 2), tags="guideline_room")
                        self._get_pooled_line(x_mid-6, oy1, x_mid+6, oy1, fill=dist_color, width=2, tags="guideline_room")
                        self._get_pooled_line(x_mid-6, y0, x_mid+6, y0, fill=dist_color, width=2, tags="guideline_room")
                        self._get_pooled_text(x_mid+12, (oy1+y0)/2, f"{(y0-oy1)/scale:.1f} {unit}", fill=dist_color, font=("Arial", 9, "bold"), tags="guideline_room")
                    elif y1 <= oy0 and oy0 - y1 > 2:
                        self._get_pooled_line(x_mid, y1, x_mid, oy0, fill=dist_color, width=1.5, dash=(4, 2), tags="guideline_room")
                        self._get_pooled_line(x_mid-6, y1, x_mid+6, y1, fill=dist_color, width=2, tags="guideline_room")
                        self._get_pooled_line(x_mid-6, oy0, x_mid+6, oy0, fill=dist_color, width=2, tags="guideline_room")
                        self._get_pooled_text(x_mid+12, (y1+oy0)/2, f"{(oy0-y1)/scale:.1f} {unit}", fill=dist_color, font=("Arial", 9, "bold"), tags="guideline_room")
            except Exception: pass
