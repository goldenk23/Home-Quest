# view.py

import tkinter as tk
import math
from typing import TYPE_CHECKING, Any
from Helper.color_scheme import COLORS

if TYPE_CHECKING:
    from model import CanvasModel
else:
    CanvasModel = Any
class CanvasView:
    def __init__(self, root, model: 'CanvasModel'):
        self.model = model
        self.container = tk.Frame(
            root, bg=COLORS.get("canvas_bg", "#0B162B"), bd=0, highlightthickness=0
        )
        self.container.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.canvas = tk.Canvas(
            self.container,
            width=1,
            height=1,
            bg=COLORS.get("canvas_bg", "#0B162B"),
            highlightthickness=0,
            bd=0,
        )
        
        # Scrollbars removed in favor of right-click drag panning.
        # Minimal row/col config to keep canvas filling the entire container.
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        self.grid_lines = []
        self.grid_line_pool = []
        self.grid_label_pool = []
        self._line_pool_idx = 0
        self._label_pool_idx = 0
        
        self.grid_visible = True
        self._grid_redraw_after_id = None
        # Keep initial scroll position stable (Tk with negative scrollregion can shift thumbs).
        self._initial_scroll_position_set = False

        # If the window is resized, re-draw the grid (debounced).
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _get_scrollregion_bounds(self, width: int, height: int) -> tuple[float, float, float, float]:
        # Increase scrollable area significantly so scrollbars are always useful
        # and user can pan/scroll far in any direction.
        # We start from (0,0) by default to keep scrollbars at top/left,
        # and extend to negative values only when needed (infinite scroll logic).
        padding_x = max(5000.0, float(width) * 5.0)
        padding_y = max(5000.0, float(height) * 5.0)
        return (0.0, 0.0, float(width) + padding_x, float(height) + padding_y)

    def schedule_grid_redraw(self, delay_ms: int = 100) -> None:
        """Debounced grid redraw to maintain performance during rapid resizing/zooming."""
        if self._grid_redraw_after_id:
            try:
                self.canvas.after_cancel(self._grid_redraw_after_id)
            except Exception:
                pass
        self._grid_redraw_after_id = self.canvas.after(delay_ms, self.draw_grid)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Triggered when canvas widget changes size."""
        self.schedule_grid_redraw()

    def _parse_scrollregion(self) -> tuple[float, float, float, float]:
        """Safely parse the current scrollregion configuration."""
        sr_val = self.canvas.cget("scrollregion")
        if not sr_val:
            return 0.0, 0.0, 0.0, 0.0
        try:
            if isinstance(sr_val, str):
                return tuple(map(float, sr_val.split()))  # type: ignore[return-value]
            return tuple(map(float, sr_val))  # type: ignore[return-value]
        except (ValueError, TypeError):
            return 0.0, 0.0, 0.0, 0.0

    def _get_pooled_line(self, x0, y0, x1, y1):
        line_color = COLORS.get("grid_line", "#1C2D47")
        if self._line_pool_idx < len(self.grid_line_pool):
            line_id = self.grid_line_pool[self._line_pool_idx]
            self.canvas.coords(line_id, x0, y0, x1, y1)
            self.canvas.itemconfig(line_id, fill=line_color, state="normal")
        else:
            line_id = self.canvas.create_line(x0, y0, x1, y1, fill=line_color, tags="grid")
            self.grid_line_pool.append(line_id)
        self._line_pool_idx += 1
        return line_id

    def _get_pooled_label(self, x, y, text, anchor, tags):
        label_color = COLORS.get("grid_label", "#52627A")
        if self._label_pool_idx < len(self.grid_label_pool):
            label_id = self.grid_label_pool[self._label_pool_idx]
            self.canvas.coords(label_id, x, y)
            self.canvas.itemconfig(
                label_id,
                text=text,
                fill=label_color,
                anchor=anchor,
                state="normal",
                tags=tags,
            )
        else:
            label_id = self.canvas.create_text(
                x,
                y,
                text=text,
                font=("Arial", 7),
                fill=label_color,
                anchor=anchor,
                tags=tags,
            )
            self.grid_label_pool.append(label_id)
        self._label_pool_idx += 1
        return label_id

    def draw_grid(self):
        # Respect visibility flag
        if not getattr(self, "grid_visible", False):
            return

        # PERFORMANCE OPTIMIZATION: Use item pooling to avoid constant create/delete
        self._line_pool_idx = 0
        self._label_pool_idx = 0
        
        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:
            return

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 2 or height <= 2:
            try:
                # Use a small delay instead of after_idle to prevent 100% CPU when minimized.
                self.canvas.after(200, self.draw_grid)
            except Exception:
                pass
            return

        try:
            x0_curr, y0_curr, x1_curr, y1_curr = self._parse_scrollregion()
            sx0, sy0, sx1, sy1 = self._get_scrollregion_bounds(width, height)
            
            new_x0 = min(x0_curr, sx0)
            new_y0 = min(y0_curr, sy0)
            new_x1 = max(x1_curr, sx1)
            new_y1 = max(y1_curr, sy1)
            
            self.canvas.configure(scrollregion=(new_x0, new_y0, new_x1, new_y1))

            if not self._initial_scroll_position_set:
                span_x = new_x1 - new_x0
                span_y = new_y1 - new_y0
                if span_x > 0 and span_y > 0:
                    fx = -new_x0 / span_x
                    fy = -new_y0 / span_y
                    self.canvas.xview_moveto(fx)
                    self.canvas.yview_moveto(fy)
                self._initial_scroll_position_set = True
        except Exception:
            pass

        spacing = float(getattr(self.model, "grid_spacing", 20) or 20)
        zoom = float(getattr(self.model, "zoom_level", 1.0) or 1.0)
        unit = str(getattr(self.model, "unit", "ft") or "ft")
        scale = float(getattr(self.model, "unit_scale", {}).get(unit, 1.0) or 1.0)

        unit_step = 1
        if scale > 1.0:
            try:
                unit_step = max(int(scale), 1)
            except Exception:
                unit_step = 1

        pixel_interval = spacing * zoom
        if abs(scale) > 1e-9:
            pixel_interval = (spacing * zoom * float(unit_step)) / float(scale)
        
        # Safety: If intervals are extremely dense (e.g. < 15px), it will crash or lag the app.
        # Force a minimum interval for drawing, even if labeling remains at real_step.
        drawing_multiplier = 1
        draw_interval = pixel_interval
        while draw_interval > 0 and draw_interval < 15.0:
            drawing_multiplier *= 2
            draw_interval = pixel_interval * drawing_multiplier

        multiplier = 1
        real_step = float(unit_step) * float(multiplier)
        hide_zero_label = (unit.lower() == "m")

        def _fmt(value: float) -> str:
            if abs(real_step - round(real_step)) < 1e-6:
                return f"{value:.0f}"
            return f"{value:.1f}"

        try:
            # OPTIMIZATION: Hide all grid items at once using tag instead of a loop.
            self.canvas.itemconfig("grid", state="hidden")
            
            v_x0 = self.canvas.canvasx(0)
            v_y0 = self.canvas.canvasy(0)
            v_x1 = self.canvas.canvasx(width)
            v_y1 = self.canvas.canvasy(height)
            
            visible_w = v_x1 - v_x0
            visible_h = v_y1 - v_y0
            
            buffer_x = visible_w * 2  # Reduced buffer from 4 to 2 as we now have pooling
            buffer_y = visible_h * 2
            
            draw_x0 = v_x0 - buffer_x
            draw_y0 = v_y0 - buffer_y
            draw_x1 = v_x1 + buffer_x
            draw_y1 = v_y1 + buffer_y

            start_step_x = int(math.floor(draw_x0 / draw_interval))
            end_step_x = int(math.ceil(draw_x1 / draw_interval))
            
            # Vertical lines
            for step in range(start_step_x, end_step_x + 1):
                x = step * draw_interval
                self._get_pooled_line(x, draw_y0, x, draw_y1)

                label_value = step * real_step * drawing_multiplier
                is_zero = abs(label_value) < 1e-9
                if not (hide_zero_label and is_zero):
                    self._get_pooled_label(x + 2, v_y0 + 10, _fmt(label_value), "nw", ("grid", "grid_label_h"))

            # Horizontal lines
            start_step_y = int(math.floor(draw_y0 / draw_interval))
            end_step_y = int(math.ceil(draw_y1 / draw_interval))
            
            for step in range(start_step_y, end_step_y + 1):
                y = step * draw_interval
                self._get_pooled_line(draw_x0, y, draw_x1, y)

                label_value = step * real_step * drawing_multiplier
                is_zero = abs(label_value) < 1e-9
                if not (hide_zero_label and is_zero):
                    self._get_pooled_label(v_x0 + 2, y + 2, _fmt(label_value), "nw", ("grid", "grid_label_v"))
        except Exception:
            pass

        self._lower_grid_to_back()
        self.grid_visible = True

    def _lower_grid_to_back(self) -> None:
        """Lower all canvas items with tag 'grid' to the bottom so figures stay on top."""
        try:
            # Lowering by tag is more reliable than iterating item-by-item,
            # especially when the grid is recreated (toggle) while many items exist.
            self.canvas.tag_lower("grid")
        except Exception:
            pass

    def clear_grid(self):
        # Hide all items in the pool
        for item in self.grid_line_pool:
            try:
                self.canvas.itemconfig(item, state="hidden")
            except Exception:
                pass
        for item in self.grid_label_pool:
            try:
                self.canvas.itemconfig(item, state="hidden")
            except Exception:
                pass
        self.grid_visible = False
    
    def reset_grid_pool(self):
        """Hard reset of item pools. Call this if canvas.delete('all') was used."""
        self.grid_line_pool = []
        self.grid_label_pool = []
        self._line_pool_idx = 0
        self._label_pool_idx = 0

    def request_scroll_home_on_next_grid_draw(self) -> None:
        """Call after a full canvas wipe (e.g. Reset Canvas) so the next draw_grid() snaps view to origin."""
        self._initial_scroll_position_set = False

    def toggle_grid(self):
        if getattr(self, "grid_visible", False):
            self.clear_grid()
        else:
            self.grid_visible = True
            self.draw_grid()
            # Some operations can create/raise items immediately after toggling.
            # Re-assert z-order once Tk finishes processing the event queue.
            try:
                self.canvas.after_idle(self._lower_grid_to_back)
            except Exception:
                pass

    def apply_zoom(self, scale_factor, anchor_widget_x: float | None = None, anchor_widget_y: float | None = None):
        """
        Apply zoom consistently across:
        - model.zoom_level (used by labels/snapping)
        - canvas items (canvas.scale)
        - scrollregion + view fractions (used by canvasx/canvasy mapping)

        Without scaling scrollregion, canvasx/canvasy mapping and distance/snap math can
        drift after repeated pan/zoom.
        """
        if scale_factor == 1.0:
            return

        # Keep the view recoverable and use the effective factor at the limits.
        current_zoom = max(0.000001, float(getattr(self.model, "zoom_level", 1.0) or 1.0))
        target_zoom = max(0.25, min(4.0, current_zoom * float(scale_factor)))
        scale_factor = target_zoom / current_zoom
        if abs(scale_factor - 1.0) < 1e-9:
            return

        # Read current scrollregion (canvas coordinates).
        try:
            x0_sr, y0_sr, x1_sr, y1_sr = self._parse_scrollregion()
        except Exception:
            x0_sr, y0_sr, x1_sr, y1_sr = 0.0, 0.0, 1.0, 1.0

        widget_w = float(max(1, self.canvas.winfo_width()))
        widget_h = float(max(1, self.canvas.winfo_height()))

        # Choose zoom anchor: keep the same world point under the mouse (or center).
        if anchor_widget_x is None:
            anchor_widget_x = widget_w / 2.0
        if anchor_widget_y is None:
            anchor_widget_y = widget_h / 2.0

        try:
            anchor_canvas_x_before = float(self.canvas.canvasx(anchor_widget_x))
            anchor_canvas_y_before = float(self.canvas.canvasy(anchor_widget_y))
        except Exception:
            anchor_canvas_x_before = 0.0
            anchor_canvas_y_before = 0.0

        # Update model zoom and scale existing items around origin.
        # self.model.zoom_level *= scale_factor

        self.model.zoom_level *= scale_factor

        # 🔥 FIX: prevent floating drift
        self.model.zoom_level = round(self.model.zoom_level, 6)
        self.canvas.scale("all", 0, 0, scale_factor, scale_factor)

        # Scale scrollregion so canvasx/canvasy stays consistent after zoom.
        # Clamp to at least 1.0 range to avoid division by zero.
        x0_new = x0_sr * scale_factor
        y0_new = y0_sr * scale_factor
        x1_new = x1_sr * scale_factor
        y1_new = y1_sr * scale_factor
        x1_new = max(x1_new, x0_new + 1.0)
        y1_new = max(y1_new, y0_new + 1.0)
        self.canvas.configure(scrollregion=(x0_new, y0_new, x1_new, y1_new))

        # Re-position the view so the anchor canvas coordinate stays under the same
        # widget pixel.
        try:
            total_w = max(1e-9, x1_new - x0_new)
            total_h = max(1e-9, y1_new - y0_new)

            # Compute visible spans and anchor offsets in canvas coordinates.
            # We avoid assumptions about Tk's internal scaling by deriving offsets
            # from the canvas mapping itself.
            canvas_left = float(self.canvas.canvasx(0))
            canvas_right = float(self.canvas.canvasx(widget_w))
            canvas_top = float(self.canvas.canvasy(0))
            canvas_bottom = float(self.canvas.canvasy(widget_h))
            visible_w = max(1e-9, canvas_right - canvas_left)
            visible_h = max(1e-9, canvas_bottom - canvas_top)

            anchor_dx = float(self.canvas.canvasx(anchor_widget_x)) - canvas_left
            anchor_dy = float(self.canvas.canvasy(anchor_widget_y)) - canvas_top

            denom_w = max(1e-9, total_w - visible_w)
            denom_h = max(1e-9, total_h - visible_h)

            target_view_left_canvas = anchor_canvas_x_before - anchor_dx
            target_view_top_canvas = anchor_canvas_y_before - anchor_dy

            x_view0_new = (target_view_left_canvas - x0_new) / denom_w
            y_view0_new = (target_view_top_canvas - y0_new) / denom_h

            x_view0_new = max(0.0, min(float(x_view0_new), 1.0))
            y_view0_new = max(0.0, min(float(y_view0_new), 1.0))

            self.canvas.xview_moveto(x_view0_new)
            self.canvas.yview_moveto(y_view0_new)
        except Exception:
            pass

        # Grid should be re-rendered at the new zoom.
        if getattr(self, "grid_visible", False):
            self.schedule_grid_redraw(delay_ms=0)

        # Update furniture items (Debounced for performance).
        if hasattr(self, 'tools') and hasattr(self.tools, 'schedule_furniture_update'):
            self.tools.schedule_furniture_update()

        # Rescale flooring textures (Debounced for performance).
        try:
            if hasattr(self, "tools") and hasattr(self.tools, "schedule_flooring_rescale"):
                self.tools.schedule_flooring_rescale()
        except Exception:
            pass

        # Keep stored in-memory geometry state consistent with the canvas scaling.
        try:
            if hasattr(self, "tools") and hasattr(self.tools, "on_zoom_changed"):
                self.tools.on_zoom_changed(scale_factor)
        except Exception:
            pass

    def reset_view(self):
        """Restore 100% zoom and return the viewport to the canvas origin."""
        current = float(getattr(self.model, "zoom_level", 1.0) or 1.0)
        if abs(current - 1.0) > 1e-9:
            self.apply_zoom(1.0 / current)
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)

    def fit_design(self):
        """Fit persisted design items inside the visible canvas."""
        boxes = []
        ignored = {"grid", "selection_highlight", "active_snap_indicator", "furniture_resize_handle"}
        for item in self.canvas.find_all():
            if ignored.intersection(self.canvas.gettags(item)):
                continue
            box = self.canvas.bbox(item)
            if box:
                boxes.append(box)
        if not boxes:
            self.reset_view()
            return
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        width, height = max(1.0, x1 - x0), max(1.0, y1 - y0)
        factor = min(max(1, self.canvas.winfo_width()) * 0.9 / width, max(1, self.canvas.winfo_height()) * 0.9 / height)
        self.apply_zoom(factor)
        box = self.canvas.bbox("all")
        if box:
            sr = self._parse_scrollregion()
            span_x, span_y = max(1.0, sr[2] - sr[0]), max(1.0, sr[3] - sr[1])
            self.canvas.xview_moveto(max(0.0, min(1.0, ((box[0] + box[2]) / 2 - self.canvas.winfo_width() / 2 - sr[0]) / span_x)))
            self.canvas.yview_moveto(max(0.0, min(1.0, ((box[1] + box[3]) / 2 - self.canvas.winfo_height() / 2 - sr[1]) / span_y)))

    def real_to_pixel(self, x, y):
        unit_factor = self.model.unit_scale[self.model.unit]
        scale = self.model.grid_spacing * self.model.zoom_level
        return x / unit_factor * scale, y / unit_factor * scale

    def pixel_to_real(self, x, y):
        unit_factor = self.model.unit_scale[self.model.unit]
        scale = self.model.grid_spacing * self.model.zoom_level
        return round(x / scale * unit_factor, 2), round(y / scale * unit_factor, 2)

    def extend_scrollregion(
        self,
        *,
        extend_left: float = 0.0,
        extend_right: float = 0.0,
        extend_top: float = 0.0,
        extend_bottom: float = 0.0,
        anchor_widget_x: float | None = None,
        anchor_widget_y: float | None = None,
    ) -> None:
        """
        Dynamically expand the scrollable area and shift the view so the world content
        remains stable relative to the widget anchor point.
        """
        if extend_left <= 0 and extend_right <= 0 and extend_top <= 0 and extend_bottom <= 0:
            return

        try:
            x0_sr, y0_sr, x1_sr, y1_sr = self._parse_scrollregion()
        except Exception:
            x0_sr, y0_sr, x1_sr, y1_sr = 0.0, 0.0, 1.0, 1.0

        widget_w = float(max(1, self.canvas.winfo_width()))
        widget_h = float(max(1, self.canvas.winfo_height()))

        if anchor_widget_x is None:
            anchor_widget_x = widget_w / 2.0
        if anchor_widget_y is None:
            anchor_widget_y = widget_h / 2.0

        try:
            # Map widget anchor to canvas world before extension.
            cx_before = float(self.canvas.canvasx(anchor_widget_x))
            cy_before = float(self.canvas.canvasy(anchor_widget_y))
        except Exception:
            cx_before, cy_before = 0.0, 0.0

        # Constraint: Do not extend scrollregion to negative coordinates (keep origin at 0,0).
        nx0 = max(0.0, x0_sr - extend_left)
        ny0 = max(0.0, y0_sr - extend_top)
        nx1, ny1 = x1_sr + extend_right, y1_sr + extend_bottom

        # Safety: avoid collapsing.
        nx1 = max(nx1, nx0 + 1.0)
        ny1 = max(ny1, ny0 + 1.0)

        self.canvas.configure(scrollregion=(nx0, ny0, nx1, ny1))
        self.canvas.update_idletasks()

        # Re-map view fractions to keep the same world point under the widget anchor.
        try:
            total_w = max(1e-9, nx1 - nx0)
            total_h = max(1e-9, ny1 - ny0)

            # deriving visible width/height in canvas coordinates from mapping.
            v_left = float(self.canvas.canvasx(0))
            v_right = float(self.canvas.canvasx(widget_w))
            v_top = float(self.canvas.canvasy(0))
            v_bottom = float(self.canvas.canvasy(widget_h))
            visible_w = max(1e-9, v_right - v_left)
            visible_h = max(1e-9, v_bottom - v_top)

            # anchor offset in widget-space converted to canvas-space.
            anchor_dx = float(self.canvas.canvasx(anchor_widget_x)) - v_left
            anchor_dy = float(self.canvas.canvasy(anchor_widget_y)) - v_top

            denom_w = max(1e-9, total_w - visible_w)
            denom_h = max(1e-9, total_h - visible_h)

            target_v_left = cx_before - anchor_dx
            target_v_top = cy_before - anchor_dy

            # Calculate how much the anchor point world coordinate shifted compared to the viewport start.
            # We want current_world_at_anchor to stay at anchor_widget_pixels.
            nx_view = (cx_before - nx0 - anchor_dx) / denom_w
            ny_view = (cy_before - ny0 - anchor_dy) / denom_h

            self.canvas.xview_moveto(max(0.0, min(float(nx_view), 1.0)))
            self.canvas.yview_moveto(max(0.0, min(float(ny_view), 1.0)))
            self.canvas.update_idletasks()
        except Exception:
            pass

        # Since we modified the world bounds mapping, grid often needs a redraw.
        if getattr(self, "grid_visible", False):
            self.schedule_grid_redraw(delay_ms=0)
