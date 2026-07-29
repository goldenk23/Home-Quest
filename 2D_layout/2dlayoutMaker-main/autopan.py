import platform
import tkinter as tk
from typing import Callable, Optional, Tuple


class AutoPanWhileDrawing:
    """
    Auto-pan controller intended for CAD-like tools (polygon/Vastu polygon).

    Contract:
    - Call `auto_pan(event)` from a Canvas `<Motion>` handler.
    - It starts a smooth repeated `after()` loop only once.
    - The loop continues while the cursor stays near the canvas edge.
    - It stops automatically when the cursor moves away from the edge or
      when the active drawing tool ends.
    """

    def __init__(
        self,
        *,
        canvas: tk.Canvas,
        view,
        model,
        tools,
        is_active_fn: Callable[[], bool],
        edge_threshold_px: int = 50,
        speed: int = 1,
        interval_ms: int = 90,
        step_canvas_x_px: float = 15,
        step_canvas_y_px: float = 10,
        stuck_limit: int = 8,
        eps: float = 1e-6,
    ):
        self.canvas = canvas
        self.view = view
        self.model = model
        self.tools = tools
        self.is_active_fn = is_active_fn

        self.edge_threshold_px = float(edge_threshold_px)
        self.speed = int(speed)
        self.interval_ms = int(interval_ms)
        self.step_canvas_x_px = float(step_canvas_x_px)
        self.step_canvas_y_px = float(step_canvas_y_px)
        self.stuck_limit = int(stuck_limit)
        self.eps = float(eps)

        self._job: Optional[str] = None
        self._dx_sign = 0.0  # -1 left, +1 right, 0 none
        self._dy_sign = 0.0  # -1 up, +1 down, 0 none

        # Anchor used by `view.extend_scrollregion(...)` to keep the pointer stable.
        self._anchor_widget_x: Optional[float] = None
        self._anchor_widget_y: Optional[float] = None

        # Stuck detection
        self._stuck_count = 0
        self._last_view_before: Optional[Tuple[float, float, float, float]] = None
        
        # Inactivity timeout (stop panning if mouse hasn't moved for 5 seconds)
        import time
        self._last_mouse_move_time = time.time()

    def set_anchor(self, x: float, y: float) -> None:
        """
        Manually set the widget-space anchor point (in pixels) for infinite 
        scrollregion extensions. This ensures that the world point under the 
        cursor stays stable when the canvas bounds expand in any direction.
        """
        self._anchor_widget_x = float(x)
        self._anchor_widget_y = float(y)

    def reset_session(self) -> None:
        """Reset internal session state (used between polygon drawing sessions)."""
        self.stop()
        # Between drawing sessions, drop grid-snap hysteresis so the next tool starts clean.
        try:
            gh = getattr(self.tools, "guideline_helper", None)
            if gh is not None and hasattr(gh, "_grid_snap_last_coord"):
                gh._grid_snap_last_coord = {"x": None, "y": None}
        except Exception:
            pass

    def stop(self) -> None:
        """Stop the auto-pan loop and reset desired movement direction."""
        # Only clear guideline grid-snap memory when we cancel a *running* after() job.
        # Calling stop() on every <Motion> (cursor not in edge, or other tools active)
        # must NOT reset _grid_snap_last_coord — that caused distance/measurement labels
        # to jump or "reset" after auto-pan or while drawing lines/polygons.
        had_running_job = self._job is not None
        if had_running_job:
            try:
                self.canvas.after_cancel(self._job)
            except Exception:
                pass
        self._job = None
        self._dx_sign = 0.0
        self._dy_sign = 0.0
        self._stuck_count = 0
        self._last_view_before = None

        if had_running_job:
            try:
                gh = getattr(self.tools, "guideline_helper", None)
                if gh is not None and hasattr(gh, "_grid_snap_last_coord"):
                    gh._grid_snap_last_coord = {"x": None, "y": None}
            except Exception:
                pass

    def auto_pan(self, event) -> None:
        """
        Update desired pan direction from cursor position and start/stop loop.

        This is intended to be called on every `<Motion>` event.
        """
        if not self.is_active_fn():
            self.stop()
            return

        try:
            widget_w = max(1, int(self.canvas.winfo_width()))
            widget_h = max(1, int(self.canvas.winfo_height()))
        except Exception:
            widget_w, widget_h = 1200, 800

        try:
            self._anchor_widget_x = float(getattr(event, "x", 0.0))
            self._anchor_widget_y = float(getattr(event, "y", 0.0))
        except Exception:
            self._anchor_widget_x = None
            self._anchor_widget_y = None

        # Edge detection in canvas coordinates keeps behavior stable across zoom.
        try:
            mouse_cx = float(self.canvas.canvasx(getattr(event, "x", 0)))
            mouse_cy = float(self.canvas.canvasy(getattr(event, "y", 0)))

            left_edge_cx = float(self.canvas.canvasx(self.edge_threshold_px))
            right_edge_cx = float(self.canvas.canvasx(widget_w - self.edge_threshold_px))

            top_edge_cy = float(self.canvas.canvasy(self.edge_threshold_px))
            bottom_edge_cy = float(self.canvas.canvasy(widget_h - self.edge_threshold_px))

            dx_sign = 0.0
            if mouse_cx >= right_edge_cx:
                dx_sign = 1.0 * self.speed
            elif mouse_cx <= left_edge_cx:
                # Stop left-pan as soon as the viewport's left edge reaches world zero.
                try:
                    if float(self.canvas.canvasx(0)) > 0.0:
                        dx_sign = -1.0 * self.speed
                except Exception:
                    dx_sign = -1.0 * self.speed

            dy_sign = 0.0
            if mouse_cy >= bottom_edge_cy:
                dy_sign = 1.0 * self.speed
            elif mouse_cy <= top_edge_cy:
                # Stop top-pan as soon as the viewport's top edge reaches world zero.
                try:
                    if float(self.canvas.canvasy(0)) > 0.0:
                        dy_sign = -1.0 * self.speed
                except Exception:
                    dy_sign = -1.0 * self.speed
        except Exception:
            # Fallback: widget-space comparisons (still correct for pixel threshold).
            ex = float(getattr(event, "x", 0.0))
            ey = float(getattr(event, "y", 0.0))
            thr = self.edge_threshold_px
            
            dx_sign = 0.0
            if ex > widget_w - thr:
                dx_sign = 1.0 * self.speed
            elif ex < thr:
                # Fallback check: check viewport edge for world zero.
                try:
                    if float(self.canvas.canvasx(0)) > 0.0:
                        dx_sign = -1.0 * self.speed
                except Exception:
                    dx_sign = -1.0 * self.speed

            dy_sign = 0.0
            if ey > widget_h - thr:
                dy_sign = 1.0 * self.speed
            elif ey < thr:
                # Fallback check: check viewport edge for world zero.
                try:
                    if float(self.canvas.canvasy(0)) > 0.0:
                        dy_sign = -1.0 * self.speed
                except Exception:
                    dy_sign = -1.0 * self.speed

        if dx_sign == 0.0 and dy_sign == 0.0:
            self.stop()
            return

        import time
        self._last_mouse_move_time = time.time()
        self._dx_sign = float(dx_sign)
        self._dy_sign = float(dy_sign)

        # Run one step immediately so polygon preview in the *same* Motion callback
        # uses updated canvas coordinates (prevents 1-frame point discontinuities).
        if self._job is None:
            self._step()

    def _parse_scrollregion(self) -> Tuple[float, float, float, float]:
        try:
            sr = self.canvas.cget("scrollregion")
            x0, y0, x1, y1 = map(float, str(sr or "").split())
            return x0, y0, x1, y1
        except Exception:
            return 0.0, 0.0, float(max(1, self.canvas.winfo_width())), float(
                max(1, self.canvas.winfo_height())
            )

    def _get_visible_span_canvas(self) -> Tuple[float, float]:
        widget_w = max(1, int(self.canvas.winfo_width()))
        widget_h = max(1, int(self.canvas.winfo_height()))
        left_canvas = float(self.canvas.canvasx(0))
        right_canvas = float(self.canvas.canvasx(widget_w))
        top_canvas = float(self.canvas.canvasy(0))
        bottom_canvas = float(self.canvas.canvasy(widget_h))
        visible_w = max(1e-9, right_canvas - left_canvas)
        visible_h = max(1e-9, bottom_canvas - top_canvas)
        return visible_w, visible_h

    def _step(self) -> None:
        if not self.is_active_fn() or (self._dx_sign == 0.0 and self._dy_sign == 0.0):
            self.stop()
            return

        # Safety: Stop auto-panning if mouse hasn't moved in 5 seconds.
        import time
        if time.time() - self._last_mouse_move_time > 5.0:
            self.stop()
            return

        if platform.system() == "Darwin":
            self._step_darwin()
            return

        # Generic fraction-based panning (works well on Windows/Linux).
        x0_sr, y0_sr, x1_sr, y1_sr = self._parse_scrollregion()
        total_w = max(1.0, x1_sr - x0_sr)
        total_h = max(1.0, y1_sr - y0_sr)

        visible_w, visible_h = self._get_visible_span_canvas()
        range_w = max(1e-9, total_w - visible_w)
        range_h = max(1e-9, total_h - visible_h)

        try:
            x_view0, x_view1 = self.canvas.xview()
            y_view0, y_view1 = self.canvas.yview()
        except Exception:
            x_view0, x_view1, y_view0, y_view1 = 0.0, 1.0, 0.0, 1.0

        # Track previous view for stuck detection.
        view_before = (float(x_view0), float(x_view1), float(y_view0), float(y_view1))
        if self._last_view_before is None:
            self._last_view_before = view_before

        moved = False

        # Boundary hit detection (check if pan WOULD hit boundary)
        x0_hit = self._dx_sign < 0.0 and float(x_view0) <= self.eps
        x1_hit = self._dx_sign > 0.0 and float(x_view1) >= 1.0 - self.eps
        y0_hit = self._dy_sign < 0.0 and float(y_view0) <= self.eps
        y1_hit = self._dy_sign > 0.0 and float(y_view1) >= 1.0 - self.eps

        # 1. Panning (only execute if we are NOT at a boundary that requires extension)
        # This prevents a frame where we clamp to 0.0 before extending to e.g. -5000.
        if (not x0_hit and not x1_hit and not y0_hit and not y1_hit):
            if self._dx_sign != 0.0:
                # We want to move the view by 'step_canvas_x_px' screen pixels.
                # In terms of fraction, this is (step / range_w).
                # But wait, range_w is in canvas units. We need step in canvas units too.
                # Since visible_w (canvas units) corresponds to widget_w (screen pixels),
                # 1 screen pixel = (visible_w / widget_w) canvas units.
                widget_w = max(1, int(self.canvas.winfo_width()))
                canvas_step_x = (self.step_canvas_x_px * visible_w / widget_w)
                delta_frac_x = (canvas_step_x * self._dx_sign) / range_w
                
                new_x0 = x_view0 + delta_frac_x
                view_w_frac = max(1e-9, (x_view1 - x_view0))
                max_x0 = max(0.0, 1.0 - view_w_frac)
                new_x0 = max(0.0, min(new_x0, max_x0))
                if abs(new_x0 - x_view0) > self.eps:
                    self.canvas.xview_moveto(new_x0)
                    moved = True
                    if hasattr(self.view, "schedule_grid_redraw"):
                        self.view.schedule_grid_redraw(delay_ms=0)

            if self._dy_sign != 0.0:
                widget_h = max(1, int(self.canvas.winfo_height()))
                canvas_step_y = (self.step_canvas_y_px * visible_h / widget_h)
                delta_frac_y = (canvas_step_y * self._dy_sign) / range_h
                
                new_y0 = y_view0 + delta_frac_y
                view_h_frac = max(1e-9, (y_view1 - y_view0))
                max_y0 = max(0.0, 1.0 - view_h_frac)
                new_y0 = max(0.0, min(new_y0, max_y0))
                if abs(new_y0 - y_view0) > self.eps:
                    self.canvas.yview_moveto(new_y0)
                    moved = True
                    if hasattr(self.view, "schedule_grid_redraw"):
                        self.view.schedule_grid_redraw(delay_ms=0)
        
        # Capture view results for extension logic
        try:
            x_after0, x_after1 = self.canvas.xview()
            y_after0, y_after1 = self.canvas.yview()
            view_after = (float(x_after0), float(x_after1), float(y_after0), float(y_after1))
        except Exception:
            view_after = view_before

        same = (
            abs(view_after[0] - view_before[0]) < 1e-7
            and abs(view_after[1] - view_before[1]) < 1e-7
            and abs(view_after[2] - view_before[2]) < 1e-7
            and abs(view_after[3] - view_before[3]) < 1e-7
        )

        if same and not moved:
            self._stuck_count += 1
        else:
            self._stuck_count = 0

        x0_hit = self._dx_sign < 0.0 and view_after[0] <= self.eps
        x1_hit = self._dx_sign > 0.0 and view_after[1] >= 1.0 - self.eps
        y0_hit = self._dy_sign < 0.0 and view_after[2] <= self.eps
        y1_hit = self._dy_sign > 0.0 and view_after[3] >= 1.0 - self.eps

        # Infinite extension (now supports all 4 directions).
        if (x0_hit or x1_hit or y0_hit or y1_hit) and hasattr(self.view, "extend_scrollregion"):
            try:
                widget_w = max(1, int(self.canvas.winfo_width()))
                widget_h = max(1, int(self.canvas.winfo_height()))
                
                ext_left = widget_w * 4.0 if x0_hit else 0.0
                ext_right = widget_w * 4.0 if x1_hit else 0.0
                ext_top = widget_h * 4.0 if y0_hit else 0.0
                ext_bottom = widget_h * 4.0 if y1_hit else 0.0

                self.view.extend_scrollregion(
                    extend_left=ext_left,
                    extend_right=ext_right,
                    extend_top=ext_top,
                    extend_bottom=ext_bottom,
                    anchor_widget_x=self._anchor_widget_x,
                    anchor_widget_y=self._anchor_widget_y,
                )
                self._stuck_count = 0
            except Exception:
                pass

        if self._stuck_count >= self.stuck_limit:
            self.stop()
            return

        self._job = self.canvas.after(self.interval_ms, self._step)

    def _step_darwin(self) -> None:
        # On macOS, xview_moveto can be inconsistent during rapid after()-driven updates.
        # Use xview_scroll/yview_scroll then do the same boundary/extend logic.
        dx_i = int(1 if self._dx_sign > 0 else (-1 if self._dx_sign < 0 else 0))
        dy_i = int(1 if self._dy_sign > 0 else (-1 if self._dy_sign < 0 else 0))

        try:
            x0_before, x1_before = self.canvas.xview()
            y0_before, y1_before = self.canvas.yview()
        except Exception:
            x0_before, x1_before, y0_before, y1_before = 0.0, 1.0, 0.0, 1.0

        if dx_i != 0:
            self.canvas.xview_scroll(dx_i, "units")
            if hasattr(self.view, "schedule_grid_redraw"):
                self.view.schedule_grid_redraw(delay_ms=0)
        if dy_i != 0:
            self.canvas.yview_scroll(dy_i, "units")
            if hasattr(self.view, "schedule_grid_redraw"):
                self.view.schedule_grid_redraw(delay_ms=0)

        try:
            x0_after, x1_after = self.canvas.xview()
            y0_after, y1_after = self.canvas.yview()
        except Exception:
            x0_after, x1_after, y0_after, y1_after = x0_before, x1_before, y0_before, y1_before

        same = (
            abs(x0_after - x0_before) < 1e-7
            and abs(x1_after - x1_before) < 1e-7
            and abs(y0_after - y0_before) < 1e-7
            and abs(y1_after - y1_before) < 1e-7
        )
        if same:
            self._stuck_count += 1
        else:
            self._stuck_count = 0

        x0_hit = self._dx_sign < 0.0 and x0_after <= self.eps
        x1_hit = self._dx_sign > 0.0 and x1_after >= 1.0 - self.eps
        y0_hit = self._dy_sign < 0.0 and y0_after <= self.eps
        y1_hit = self._dy_sign > 0.0 and y1_after >= 1.0 - self.eps

        if (x0_hit or x1_hit or y0_hit or y1_hit) and hasattr(self.view, "extend_scrollregion"):
            try:
                widget_w = max(1, int(self.canvas.winfo_width()))
                widget_h = max(1, int(self.canvas.winfo_height()))
                
                ext_left = widget_w * 4.0 if x0_hit else 0.0
                ext_right = widget_w * 4.0 if x1_hit else 0.0
                ext_top = widget_h * 4.0 if y0_hit else 0.0
                ext_bottom = widget_h * 4.0 if y1_hit else 0.0

                self.view.extend_scrollregion(
                    extend_left=ext_left,
                    extend_right=ext_right,
                    extend_top=ext_top,
                    extend_bottom=ext_bottom,
                    anchor_widget_x=self._anchor_widget_x,
                    anchor_widget_y=self._anchor_widget_y,
                )
                self._stuck_count = 0
            except Exception:
                pass

        if self._stuck_count >= self.stuck_limit:
            self.stop()
            return

        self._job = self.canvas.after(self.interval_ms, self._step)

