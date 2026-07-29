from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from geometry import calculate_polygon_area, calculate_polygon_perimeter


Point = Tuple[float, float]


@dataclass(frozen=True)
class GenerateLayoutResult:
    group_tag: str
    polygon_id: int
    label_id: int
    dimension_item_ids: List[int]
    points: List[Point]
    actual_sides: Optional[Dict[str, float]] = None


class GenerateLayoutService:
    """
    Create a rectangle polygon from Length/Breadth (in current model units).

    This draws the polygon on the canvas using the same conventions as the normal polygon:
    - tag: "closed_shape"
    - area/perimeter label
    - optional edge dimensions (toggle)
    - actions logged for Undo
    """

    def __init__(self, *, tools, model, view, actions) -> None:
        self._tools = tools
        self._model = model
        self._view = view
        self._actions = actions

    def _real_to_px(self, value: float) -> float:
        unit = getattr(self._model, "unit", "m")
        unit_scale = getattr(self._model, "unit_scale", {}) or {}
        scale = float(unit_scale.get(unit, 1.0))
        grid = float(getattr(self._model, "grid_spacing", 20))
        zoom = float(getattr(self._model, "zoom_level", 1.0))
        return (float(value) / scale) * grid * zoom

    def _viewport_center_canvas_xy(self) -> Point:
        canvas = self._view.canvas
        w = float(canvas.winfo_width() or 0)
        h = float(canvas.winfo_height() or 0)
        cx = float(canvas.canvasx(w / 2.0))
        cy = float(canvas.canvasy(h / 2.0))
        return cx, cy

    def generate_rectangle(
        self,
        *,
        length: float,
        breadth: float,
        draw_dimensions: Optional[bool] = None,
    ) -> GenerateLayoutResult:
        if length <= 0 or breadth <= 0:
            raise ValueError("Length and Breadth must be greater than 0.")

        # --- Auto-Zoom / Fit to Screen logic ---
        try:
            canvas = self._view.canvas
            w = float(canvas.winfo_width() or 0)
            h = float(canvas.winfo_height() or 0)
            if w > 10 and h > 10:
                unit = getattr(self._model, "unit", "m")
                unit_scale = getattr(self._model, "unit_scale", {}) or {}
                scale = float(unit_scale.get(unit, 1.0) or 1.0)
                grid = float(getattr(self._model, "grid_spacing", 20) or 20)
                
                # Calculate required pixel dimensions at zoom_level = 1.0
                base_w_px = (float(length) / scale) * grid
                base_h_px = (float(breadth) / scale) * grid
                
                if base_w_px > 0 and base_h_px > 0:
                    # Target layout to occupy at most 75% of the viewport width/height
                    max_allowed_w = w * 0.75
                    max_allowed_h = h * 0.75
                    
                    ideal_zoom = min(max_allowed_w / base_w_px, max_allowed_h / base_h_px)
                    
                    # Clamp ideal_zoom to reasonable bounds (e.g., between 0.005 and 1.0)
                    ideal_zoom = min(ideal_zoom, 1.0)
                    ideal_zoom = max(ideal_zoom, 0.005)
                    
                    current_zoom = float(getattr(self._model, "zoom_level", 1.0) or 1.0)
                    
                    # Apply zoom if it's different
                    scale_factor = ideal_zoom / current_zoom
                    if abs(scale_factor - 1.0) > 1e-4:
                        self._view.apply_zoom(scale_factor)
        except Exception as e:
            print(f"[Auto-Zoom] Failed to apply auto-zoom: {e}")

        w_px = self._real_to_px(length)
        h_px = self._real_to_px(breadth)
        cx, cy = self._viewport_center_canvas_xy()

        x0 = cx - (w_px / 2.0)
        y0 = cy - (h_px / 2.0)
        x1 = cx + (w_px / 2.0)
        y1 = cy + (h_px / 2.0)

        points: List[Point] = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        flat = [coord for pt in points for coord in pt]

        group_tag = getattr(self._tools, "_new_polygon_group_tag")()

        style = getattr(self._model, "line_style", "solid")
        poly_width = 4 if style == "bold" else 2
        poly_dash = (4, 2) if style == "dashed" else None

        polygon_id = self._view.canvas.create_polygon(
            *flat,
            fill="",
            outline="green",
            width=poly_width,
            dash=poly_dash,
            tags=("closed_shape", group_tag, "polygon_shape", "generated_layout"),
        )

        unit = getattr(self._model, "unit", "m")
        zoom_level = float(getattr(self._model, "zoom_level", 1.0))
        area = calculate_polygon_area(points, unit, zoom_level)
        perimeter = calculate_polygon_perimeter(points, unit, zoom_level)

        self._tools._polygon_label_serial = int(getattr(self._tools, "_polygon_label_serial", 0) or 0) + 1
        serial = int(getattr(self._tools, "_polygon_label_serial"))
        
        # Dynamic font size and text formatting based on box size in pixels
        min_dim_px = min(w_px, h_px)
        area_font_size = 9
        dim_font_size = 11

        # Use ultra-compact labels for very small rooms to prevent overlap/overflow
        if min_dim_px < 100:
            label_text = f"A{serial}: {area:.2f}{unit}²\nP{serial}: {perimeter:.2f}{unit}"
        else:
            label_text = f"Area {serial}: {area:.2f} {unit}²\nPerimeter {serial}: {perimeter:.2f} {unit}"

        # Adaptive font size thresholds
        if min_dim_px < 50:
            area_font_size = 6
            dim_font_size = 7
        elif min_dim_px < 80:
            area_font_size = 7
            dim_font_size = 8
        elif min_dim_px < 150:
            area_font_size = 8
            dim_font_size = 9

        label_id = self._tools.polygon_label_placer.create_polygon_label(
            points,
            label_text,
            tags=(group_tag, "polygon_label", "generated_layout_label"),
            fill="black",
            font=("Arial", area_font_size),
        )
        self._view.canvas.tag_raise(label_id)

        if draw_dimensions is None:
            draw_dimensions = bool(getattr(self._model, "auto_generate_layout_dimensions", True))

        dim_items: List[int] = []
        if draw_dimensions and hasattr(self._tools, "dimension_drawer"):
            drawer = self._tools.dimension_drawer
            style_override = None
            if dim_font_size != 11:
                from dataclasses import replace
                try:
                    style_override = replace(drawer._style, text_font=("Arial", dim_font_size))
                except Exception:
                    style_override = None

            dim_items = list(
                drawer.draw_polygon_edge_dimensions(
                    points,
                    group_tag=group_tag,
                    dim_tag=f"{group_tag}__gen_dims",
                    style_override=style_override,
                )
                or []
            )

        self._actions.log({"type": "create", "items": [polygon_id, label_id, *dim_items]})

        return GenerateLayoutResult(
            group_tag=group_tag,
            polygon_id=polygon_id,
            label_id=label_id,
            dimension_item_ids=dim_items,
            points=points,
        )

    def generate_compass_layout(
        self,
        *,
        north: float,
        south: float,
        east: float,
        west: float,
        draw_dimensions: Optional[bool] = None,
    ) -> GenerateLayoutResult:
        if north <= 0 or south <= 0 or east <= 0 or west <= 0:
            raise ValueError("All wall distances must be greater than 0.")

        # Max dimensions for auto-zoom
        length = max(west, east)
        breadth = max(north, south)

        # --- Auto-Zoom / Fit to Screen logic ---
        try:
            canvas = self._view.canvas
            w = float(canvas.winfo_width() or 0)
            h = float(canvas.winfo_height() or 0)
            if w > 10 and h > 10:
                unit = getattr(self._model, "unit", "m")
                unit_scale = getattr(self._model, "unit_scale", {}) or {}
                scale = float(unit_scale.get(unit, 1.0) or 1.0)
                grid = float(getattr(self._model, "grid_spacing", 20) or 20)
                
                # Calculate required pixel dimensions at zoom_level = 1.0
                base_w_px = (float(length) / scale) * grid
                base_h_px = (float(breadth) / scale) * grid
                
                if base_w_px > 0 and base_h_px > 0:
                    max_allowed_w = w * 0.75
                    max_allowed_h = h * 0.75
                    ideal_zoom = min(max_allowed_w / base_w_px, max_allowed_h / base_h_px)
                    ideal_zoom = min(ideal_zoom, 1.0)
                    ideal_zoom = max(ideal_zoom, 0.005)
                    
                    current_zoom = float(getattr(self._model, "zoom_level", 1.0) or 1.0)
                    scale_factor = ideal_zoom / current_zoom
                    if abs(scale_factor - 1.0) > 1e-4:
                        self._view.apply_zoom(scale_factor)
        except Exception as e:
            print(f"[Auto-Zoom] Failed to apply auto-zoom: {e}")

        # Sides converted to canvas pixels
        px_N = self._real_to_px(north)
        px_S = self._real_to_px(south)
        px_E = self._real_to_px(east)
        px_W = self._real_to_px(west)
        
        cx, cy = self._viewport_center_canvas_xy()

        # Bounding box of the asymmetrical polygon:
        # Width of the bounding box = max(px_W, px_E)
        # Height of the bounding box = max(px_N, px_S)
        max_w_px = max(px_W, px_E)
        max_h_px = max(px_N, px_S)

        # Offsets to center the bounding box at (cx, cy)
        x_off = cx - (max_w_px / 2.0)
        y_off = cy - (max_h_px / 2.0)

        # Corners:
        # Top-Left: (x_off, y_off)
        # Top-Right: (x_off + px_W, y_off)
        # Bottom-Right: (x_off + px_E, y_off + px_N)
        # Bottom-Left: (x_off, y_off + px_S)
        x0, y0 = x_off, y_off
        x1, y1 = x_off + px_W, y_off
        x2, y2 = x_off + px_E, y_off + px_N
        x3, y3 = x_off, y_off + px_S

        points: List[Point] = [(x0, y0), (x1, y1), (x2, y2), (x3, y3)]
        flat = [coord for pt in points for coord in pt]

        group_tag = getattr(self._tools, "_new_polygon_group_tag")()

        style = getattr(self._model, "line_style", "solid")
        poly_width = 4 if style == "bold" else 2
        poly_dash = (4, 2) if style == "dashed" else None

        polygon_id = self._view.canvas.create_polygon(
            *flat,
            fill="",
            outline="green",
            width=poly_width,
            dash=poly_dash,
            tags=("closed_shape", group_tag, "polygon_shape", "generated_layout", "vastu_oriented_layout"),
        )

        unit = getattr(self._model, "unit", "m")
        zoom_level = float(getattr(self._model, "zoom_level", 1.0))
        area = calculate_polygon_area(points, unit, zoom_level)
        perimeter = calculate_polygon_perimeter(points, unit, zoom_level)

        self._tools._polygon_label_serial = int(getattr(self._tools, "_polygon_label_serial", 0) or 0) + 1
        serial = int(getattr(self._tools, "_polygon_label_serial"))
        
        # Dimensions for layout label
        min_dim_px = min(max_w_px, max_h_px)
        area_font_size = 9
        dim_font_size = 11

        if min_dim_px < 100:
            label_text = f"A{serial}: {area:.2f}{unit}²\nP{serial}: {perimeter:.2f}{unit}"
        else:
            label_text = f"Area {serial}: {area:.2f} {unit}²\nPerimeter {serial}: {perimeter:.2f} {unit}"

        if min_dim_px < 50:
            area_font_size = 6
            dim_font_size = 7
        elif min_dim_px < 80:
            area_font_size = 7
            dim_font_size = 8
        elif min_dim_px < 150:
            area_font_size = 8
            dim_font_size = 9

        label_id = self._tools.polygon_label_placer.create_polygon_label(
            points,
            label_text,
            tags=(group_tag, "polygon_label", "generated_layout_label"),
            fill="black",
            font=("Arial", area_font_size),
        )
        self._view.canvas.tag_raise(label_id)

        # Do NOT draw the vastu north marker on the canvas (per user instructions)
        # However, keep self._tools.vastu_north_deg updated just in case
        try:
            self._tools.vastu_north_deg = 270.0
        except Exception:
            pass

        if draw_dimensions is None:
            draw_dimensions = bool(getattr(self._model, "auto_generate_layout_dimensions", True))

        dim_items: List[int] = []
        if draw_dimensions and hasattr(self._tools, "dimension_drawer"):
            drawer = self._tools.dimension_drawer
            style_override = None
            if dim_font_size != 11:
                from dataclasses import replace
                try:
                    style_override = replace(drawer._style, text_font=("Arial", dim_font_size))
                except Exception:
                    style_override = None

            dim_items = list(
                drawer.draw_polygon_edge_dimensions(
                    points,
                    group_tag=group_tag,
                    dim_tag=f"{group_tag}__gen_dims",
                    style_override=style_override,
                )
                or []
            )

        import math
        actual_east = math.sqrt((east - west)**2 + (south - north)**2)
        actual_sides = {
            "north": north,
            "south": south,
            "east": actual_east,
            "west": west
        }

        self._actions.log({"type": "create", "items": [polygon_id, label_id, *dim_items]})

        return GenerateLayoutResult(
            group_tag=group_tag,
            polygon_id=polygon_id,
            label_id=label_id,
            dimension_item_ids=dim_items,
            points=points,
            actual_sides=actual_sides,
        )
