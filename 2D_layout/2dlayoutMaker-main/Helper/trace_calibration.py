# Helper/trace_calibration.py
import math
import tkinter as tk
from typing import Optional

try:
    import ttkbootstrap as ttkb
    TTKBOOTSTRAP_AVAILABLE = True
except ImportError:
    import tkinter.ttk as ttkb
    TTKBOOTSTRAP_AVAILABLE = False

try:
    from Helper.set_window_icon import set_window_icon
except ImportError:
    try:
        from set_window_icon import set_window_icon
    except ImportError:
        def set_window_icon(root, icon_path=None): pass


class TraceCalibrationDialog:
    """
    A premium, highly polished, and cross-platform modal dialog for entering
    the real-world distance during background template calibration.
    Uses ttkbootstrap (ttkb) when available, falling back to a clean, beautifully styled
    standard ttk dialog otherwise. Fully responsive to light/dark modes and DPI scaling.
    """
    def __init__(
        self,
        parent: tk.Misc,
        title: str = "Trace Scale Calibration",
        prompt: str = "Enter the real-world distance:",
        current_measure: float = 0.0,
        unit: str = "ft",
        initial_value: float = 10.0
    ) -> None:
        self.parent = parent
        self.title = title
        self.prompt = prompt
        self.current_measure = current_measure
        self.unit = unit
        self.initial_value = initial_value
        self.result: Optional[float] = None

        # Create standard modal Toplevel
        self.win = tk.Toplevel(parent)
        self.win.title(self.title)
        
        # Apply fallback background color if ttkbootstrap is not styling automatically
        if not TTKBOOTSTRAP_AVAILABLE:
            self.win.configure(bg="#F9FAFB")

        self.win.resizable(False, False)

        # Apply application icon
        try:
            set_window_icon(self.win)
        except Exception:
            pass

        # Make it modal & transient to prevent clicking outside
        try:
            self.win.transient(parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent)
        except Exception:
            pass
        
        self.win.grab_set()
        
        # Window closing / cancel handlers
        self.win.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.win.bind("<Escape>", lambda e: self.on_cancel())
        self.win.bind("<Return>", lambda e: self.on_ok())
        self.win.bind("<Unmap>", self.on_unmap)

        # Build UI layout using ttkb
        self._build_ui()

        # Center on parent window
        self.center_on_parent()

    def _build_ui(self) -> None:
        pad = 20
        
        # Base frame
        if TTKBOOTSTRAP_AVAILABLE:
            main_frame = ttkb.Frame(self.win, padding=pad)
        else:
            style = ttkb.Style()
            style.configure("Trace.TFrame", background="#F9FAFB")
            main_frame = ttkb.Frame(self.win, padding=pad, style="Trace.TFrame")
            
        main_frame.pack(fill="both", expand=True)

        # Header Frame
        if TTKBOOTSTRAP_AVAILABLE:
            header_frame = ttkb.Frame(main_frame)
        else:
            header_frame = ttkb.Frame(main_frame, style="Trace.TFrame")
        header_frame.pack(fill="x", pady=(0, 15))

        # Big emoji or icon
        if TTKBOOTSTRAP_AVAILABLE:
            icon_lbl = ttkb.Label(
                header_frame,
                text="📐",
                font=("Segoe UI", 24)
            )
        else:
            icon_lbl = ttkb.Label(
                header_frame,
                text="📐",
                font=("Segoe UI", 24),
                background="#F9FAFB"
            )
        icon_lbl.pack(side="left", padx=(0, 10))

        # Title Label
        if TTKBOOTSTRAP_AVAILABLE:
            title_lbl = ttkb.Label(
                header_frame,
                text="Trace Scale Calibration",
                font=("Segoe UI", 16, "bold"),
                bootstyle="primary"
            )
        else:
            title_lbl = ttkb.Label(
                header_frame,
                text="Trace Scale Calibration",
                font=("Segoe UI", 14, "bold"),
                background="#F9FAFB",
                foreground="#111827"
            )
        title_lbl.pack(side="left", fill="x", expand=True)

        # Prompt description
        if TTKBOOTSTRAP_AVAILABLE:
            prompt_lbl = ttkb.Label(
                main_frame,
                text=self.prompt,
                font=("Segoe UI", 11),
                wraplength=340,
                justify="left"
            )
        else:
            prompt_lbl = ttkb.Label(
                main_frame,
                text=self.prompt,
                font=("Segoe UI", 11),
                background="#F9FAFB",
                foreground="#111827",
                wraplength=340,
                justify="left"
            )
        prompt_lbl.pack(fill="x", pady=(0, 15), anchor="w")

        # Sleek information box showing current canvas measurements (a modern card)
        if TTKBOOTSTRAP_AVAILABLE:
            info_card = ttkb.Labelframe(
                main_frame,
                text=" Current Canvas Length ",
                padding=12,
                bootstyle="info"
            )
        else:
            info_card = ttkb.LabelFrame(
                main_frame,
                text=" Current Canvas Length ",
                padding=10
            )
        info_card.pack(fill="x", pady=(0, 15))

        if TTKBOOTSTRAP_AVAILABLE:
            info_lbl = ttkb.Label(
                info_card,
                text=f"{self.current_measure:.2f} {self.unit}",
                font=("Segoe UI", 12, "bold italic"),
                bootstyle="secondary"
            )
        else:
            info_lbl = ttkb.Label(
                info_card,
                text=f"{self.current_measure:.2f} {self.unit}",
                font=("Segoe UI", 11, "bold italic"),
                foreground="#6B7280"
            )
        info_lbl.pack(anchor="w")

        # Entry row with unit suffix
        if TTKBOOTSTRAP_AVAILABLE:
            entry_frame = ttkb.Frame(main_frame)
        else:
            entry_frame = ttkb.Frame(main_frame, style="Trace.TFrame")
        entry_frame.pack(fill="x", pady=(0, 5))

        self.entry_var = tk.StringVar(value=str(self.initial_value))
        if TTKBOOTSTRAP_AVAILABLE:
            self.entry = ttkb.Entry(
                entry_frame,
                textvariable=self.entry_var,
                font=("Segoe UI", 12, "bold"),
                bootstyle="primary",
                width=22
            )
        else:
            self.entry = ttkb.Entry(
                entry_frame,
                textvariable=self.entry_var,
                font=("Segoe UI", 11, "bold"),
                width=25
            )
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.focus_set()
        
        # Autoselect contents to facilitate quick typing
        self.win.after(100, lambda: self.entry.select_range(0, tk.END))

        if TTKBOOTSTRAP_AVAILABLE:
            unit_lbl = ttkb.Label(
                entry_frame,
                text=self.unit,
                font=("Segoe UI", 12, "bold")
            )
        else:
            unit_lbl = ttkb.Label(
                entry_frame,
                text=self.unit,
                font=("Segoe UI", 11, "bold"),
                background="#F9FAFB",
                foreground="#111827"
            )
        unit_lbl.pack(side="left", padx=(10, 0))

        # Status / Validation Message Label
        if TTKBOOTSTRAP_AVAILABLE:
            self.error_lbl = ttkb.Label(
                main_frame,
                text="",
                font=("Segoe UI", 10, "bold"),
                bootstyle="danger",
                anchor="w"
            )
        else:
            self.error_lbl = ttkb.Label(
                main_frame,
                text="",
                font=("Segoe UI", 10),
                foreground="#EF4444",
                background="#F9FAFB",
                anchor="w"
            )
        self.error_lbl.pack(fill="x", pady=(0, 15))

        # Divider line
        if TTKBOOTSTRAP_AVAILABLE:
            ttkb.Separator(main_frame, orient="horizontal").pack(fill="x", pady=(0, 15))
        else:
            ttk_sep = ttkb.Separator(main_frame, orient="horizontal")
            ttk_sep.pack(fill="x", pady=(0, 15))

        # Action Buttons
        if TTKBOOTSTRAP_AVAILABLE:
            btn_frame = ttkb.Frame(main_frame)
        else:
            btn_frame = ttkb.Frame(main_frame, style="Trace.TFrame")
        btn_frame.pack(fill="x")

        if TTKBOOTSTRAP_AVAILABLE:
            cancel_btn = ttkb.Button(
                btn_frame,
                text="Cancel",
                command=self.on_cancel,
                bootstyle="secondary-outline",
                width=10
            )
            ok_btn = ttkb.Button(
                btn_frame,
                text="Calibrate",
                command=self.on_ok,
                bootstyle="primary",
                width=12
            )
        else:
            cancel_btn = ttkb.Button(
                btn_frame,
                text="Cancel",
                command=self.on_cancel
            )
            ok_btn = ttkb.Button(
                btn_frame,
                text="Calibrate Scale",
                command=self.on_ok
            )
        cancel_btn.pack(side="left")
        ok_btn.pack(side="right")

    def center_on_parent(self) -> None:
        try:
            self.win.update_idletasks()
            pw = self.parent.winfo_toplevel()
            px = pw.winfo_rootx()
            py = pw.winfo_rooty()
            pww = pw.winfo_width()
            phh = pw.winfo_height()
            ww = self.win.winfo_width()
            wh = self.win.winfo_height()
            x = px + max(0, (pww - ww) // 2)
            y = py + max(0, (phh - wh) // 2)
            self.win.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def on_ok(self) -> None:
        val_str = self.entry_var.get().strip()
        try:
            val = float(val_str)
            if val < 0.01:
                raise ValueError("Value must be positive")
            self.result = val
            self.win.grab_release()
            self.win.destroy()
        except ValueError:
            self.error_lbl.configure(text="⚠️ Please enter a valid number >= 0.01!")

    def on_cancel(self) -> None:
        self.result = None
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass

    def on_unmap(self, _event) -> None:
        try:
            if str(self.win.state()) == "iconic":
                self.on_cancel()
        except Exception:
            self.on_cancel()

    def show(self) -> Optional[float]:
        try:
            self.win.wait_window()
        except Exception:
            pass
        return self.result




def center_view_on_canvas_point(tools, cx: float, cy: float) -> None:
    """
    Scrolls the canvas viewport so that the canvas coordinate (cx, cy) 
    is centered in the visible window.
    """
    try:
        canvas = tools.canvas
        # Get current widget size
        w_width = max(100, canvas.winfo_width())
        w_height = max(100, canvas.winfo_height())
        
        # Get current scrollregion bounds
        sr = canvas.cget("scrollregion")
        if not sr:
            return
        
        if isinstance(sr, str):
            sr_parts = tuple(map(float, sr.split()))
        else:
            sr_parts = tuple(map(float, sr))
            
        if len(sr_parts) < 4:
            return
            
        x0, y0, x1, y1 = sr_parts
        total_w = x1 - x0
        total_h = y1 - y0
        
        if total_w <= 0 or total_h <= 0:
            return
            
        # Determine current visible width/height in canvas coordinates
        canvas_left = float(canvas.canvasx(0))
        canvas_right = float(canvas.canvasx(w_width))
        canvas_top = float(canvas.canvasy(0))
        canvas_bottom = float(canvas.canvasy(w_height))
        
        visible_w = canvas_right - canvas_left
        visible_h = canvas_bottom - canvas_top
        
        # Center target scroll left and top
        left_target = cx - visible_w / 2.0
        top_target = cy - visible_h / 2.0
        
        # Calculate scroll fractions between 0.0 and 1.0
        fx = (left_target - x0) / total_w
        fy = (top_target - y0) / total_h
        
        fx = max(0.0, min(1.0, fx))
        fy = max(0.0, min(1.0, fy))
        
        # Apply scroll position changes
        canvas.xview_moveto(fx)
        canvas.yview_moveto(fy)
    except Exception as e:
        print(f"[Center View] Auto-scroll viewport centering failed: {e}")

def calibrate_trace_image(tools, pt1: tuple[float, float], pt2: tuple[float, float]) -> bool:
    """
    Calibrates the trace image scale and all canvas elements strictly around the drawn segment's anchor (pt1).
    Prompts the user for the real-world distance of the segment,
    calculates the ratio between entered distance and current canvas distance,
    scales EVERYTHING (reference image, drawn lines, polygons, furniture, markers)
    around pt1, and centers the viewport on pt1 so the specific area being drawn
    scales up/down right in front of the user without shifting away.
    
    Compatible with cross-platform (Windows, macOS, Linux).
    """
    if not hasattr(tools, 'trace_manager') or not tools.trace_manager:
        return False
        
    trace_mgr = tools.trace_manager
    if not trace_mgr.original_image:
        return False

    if not getattr(trace_mgr, 'auto_calibrate', True):
        return False

    # Get coordinate conversion parameters from the model/view
    model = tools.model
    zoom = model.zoom_level
    grid_spacing = model.grid_spacing
    unit = model.unit
    unit_factor = model.unit_scale.get(unit, 1.0)
    
    # Determine segment orientation and compute non-uniform scaling ratio on the active dimension
    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]
    pixel_dist = math.sqrt(dx*dx + dy*dy)
    
    # Avoid zero division
    if pixel_dist < 1e-4:
        return False
        
    # Convert pixel length to the current canvas real-world units
    scale_denominator = grid_spacing * zoom
    current_real_dist = (pixel_dist / scale_denominator) * unit_factor
    
    # Prompt the user for the actual expected distance using custom TraceCalibrationDialog
    dialog = TraceCalibrationDialog(
        parent=tools.root,
        title="Trace Scale Calibration",
        prompt=f"Enter the real-world distance for this drawn wall:",
        current_measure=current_real_dist,
        unit=unit,
        initial_value=round(current_real_dist, 2)
    )
    actual_dist = dialog.show()
    
    # If the user clicks Cancel, leave the scale untouched
    if actual_dist is None:
        return False
        
    # Check if we have already calibrated the image scale.
    # If already calibrated, we just adjust the segment's endpoint to the exact length entered.
    if getattr(trace_mgr, "scale_calibrated", False):
        target_pixel_dist = (actual_dist / unit_factor) * scale_denominator
        new_pt2_x = pt1[0] + (dx / pixel_dist) * target_pixel_dist
        new_pt2_y = pt1[1] + (dy / pixel_dist) * target_pixel_dist
        new_pt2 = (new_pt2_x, new_pt2_y)
        
        # Update whichever point list has pt2 as its last element
        for attr in ["polygon_points", "vastu_polygon_points", "freeform_points"]:
            lst = getattr(tools, attr, None)
            if isinstance(lst, list) and len(lst) >= 2 and lst[-1] == pt2:
                lst[-1] = new_pt2
                break
                
        # Redraw grid lines to refresh visual background
        try:
            tools.view.schedule_grid_redraw(delay_ms=0)
        except Exception:
            pass
        return True

    # Mark scale as calibrated
    trace_mgr.scale_calibrated = True

    # Calculate scale adjustment ratio
    ratio = actual_dist / current_real_dist
    if abs(ratio - 1.0) < 1e-5:
        return True # No change needed
        
    # Uniform scale ratios: stretch both axes proportionally to preserve aspect ratio!
    ratio_x = ratio
    ratio_y = ratio
        
    anchor_x, anchor_y = pt1[0], pt1[1]

    # --- 1. Scale all canvas items natively in Tkinter around the segment anchor ---
    tools.canvas.scale("all", anchor_x, anchor_y, ratio_x, ratio_y)

    # --- 2. Scale stored Python in-memory coordinates in tools around the segment anchor ---
    def _scale_pt(p):
        return (
            anchor_x + (p[0] - anchor_x) * ratio_x,
            anchor_y + (p[1] - anchor_y) * ratio_y
        )

    # Scale active drawing lists
    if hasattr(tools, "polygon_points") and isinstance(tools.polygon_points, list):
        tools.polygon_points = [_scale_pt(p) for p in tools.polygon_points]
    if hasattr(tools, "vastu_polygon_points") and isinstance(tools.vastu_polygon_points, list):
        tools.vastu_polygon_points = [_scale_pt(p) for p in tools.vastu_polygon_points]
    if hasattr(tools, "freeform_points") and isinstance(tools.freeform_points, list):
        tools.freeform_points = [_scale_pt(p) for p in tools.freeform_points]

    if getattr(tools, "first_point", None):
        tools.first_point = _scale_pt(tools.first_point)
    if getattr(tools, "temp_origin", None):
        tools.temp_origin = _scale_pt(tools.temp_origin)

    # Scale two-point eraser preview anchor
    if getattr(tools, "_wall_erase_first_point", None):
        tools._wall_erase_first_point = _scale_pt(tools._wall_erase_first_point)

    # Scale line editing endpoints & update visual coordinate positions
    if hasattr(tools, "line_metadata") and isinstance(tools.line_metadata, dict):
        for meta in tools.line_metadata.values():
            if "x0" in meta: meta["x0"] = anchor_x + (meta["x0"] - anchor_x) * ratio_x
            if "y0" in meta: meta["y0"] = anchor_y + (meta["y0"] - anchor_y) * ratio_y
            if "x1" in meta: meta["x1"] = anchor_x + (meta["x1"] - anchor_x) * ratio_x
            if "y1" in meta: meta["y1"] = anchor_y + (meta["y1"] - anchor_y) * ratio_y

            # Recompute intermediate coordinate positions and distance labels
            try:
                from drawing_helpers import get_distance_label
                label_text, mid_x, mid_y = get_distance_label(
                    meta["x0"], meta["y0"], meta["x1"], meta["y1"], model.unit, zoom
                )
                if "label" in meta:
                    tools.canvas.coords(meta["label"], mid_x, mid_y - 10)
                    tools.canvas.itemconfig(meta["label"], text=label_text)
                if "point" in meta:
                    tools.canvas.coords(meta["point"], meta["x1"] - 0.5, meta["y1"] - 0.5, meta["x1"] + 0.5, meta["y1"] + 0.5)
            except Exception:
                pass

    # Scale polygon baselines (for door cuts)
    if hasattr(tools, "_polygon_baseline_coords_by_group") and isinstance(tools._polygon_baseline_coords_by_group, dict):
        for k, flat in list(tools._polygon_baseline_coords_by_group.items()):
            if isinstance(flat, list):
                tools._polygon_baseline_coords_by_group[k] = [
                    (anchor_x + (v - anchor_x) * ratio_x if i % 2 == 0 else anchor_y + (v - anchor_y) * ratio_y)
                    for i, v in enumerate(flat)
                ]

    # --- 3. Scale trace image center relative to the segment anchor ---
    trace_mgr.x = anchor_x + (trace_mgr.x - anchor_x) * ratio_x
    trace_mgr.y = anchor_y + (trace_mgr.y - anchor_y) * ratio_y
    
    # Scale image scale values uniformly
    trace_mgr.scale = max(0.05, min(5.0, trace_mgr.scale * ratio))
    trace_mgr.scale_x = trace_mgr.scale
    trace_mgr.scale_y = trace_mgr.scale
    trace_mgr.render()

    # --- 4. Scale furniture items ---
    for furniture in getattr(tools, "image_furniture_items", []):
        try:
            if hasattr(furniture, "image_id"):
                if getattr(furniture, "target_size", None):
                    new_w = int(furniture.target_size[0] * ratio_x)
                    new_h = int(furniture.target_size[1] * ratio_y)
                    furniture.target_size = (new_w, new_h)
                furniture.scale *= ratio
                furniture.update_image()
                tools.canvas.itemconfig(furniture.image_id, image=furniture.tk_image)
        except Exception:
            pass

    # --- 5. Auto Zoom Out and Shift to center of the viewport ---
    try:
        # Expand canvas scrollregion boundary so canvas bounds grow with the scaled image
        tools.view.draw_grid()
        
        view_w = max(100, tools.canvas.winfo_width())
        view_h = max(100, tools.canvas.winfo_height())
        w_base = trace_mgr.original_image.width * trace_mgr.scale_x
        h_base = trace_mgr.original_image.height * trace_mgr.scale_y
        
        # Desired zoom level to comfortably fit 85% of screen
        desired_zoom = min((0.85 * view_w) / w_base, (0.85 * view_h) / h_base)
        
        zoom_factor = 1.0
        if desired_zoom < model.zoom_level:
            zoom_factor = desired_zoom / model.zoom_level
            # Apply zoom out centered on the viewport center to keep resizing clean
            tools.view.apply_zoom(zoom_factor)
            
            # Recalculate expanded scrollregion at new zoom
            tools.view.draw_grid()
            
        # 1. Determine trace image's center coordinate after zoom
        cx = trace_mgr.x
        cy = trace_mgr.y
        if zoom_factor != 1.0:
            cx *= zoom_factor
            cy *= zoom_factor
            
        # 2. Get the current viewport center canvas coordinates
        viewport_cx = float(tools.canvas.canvasx(view_w / 2.0))
        viewport_cy = float(tools.canvas.canvasy(view_h / 2.0))
        
        # 3. Calculate translation offset to center the trace image
        shift_x = viewport_cx - cx
        shift_y = viewport_cy - cy
        
        if abs(shift_x) > 1e-4 or abs(shift_y) > 1e-4:
            # Shift all canvas items physically by the offset
            tools.canvas.move("all", shift_x, shift_y)
            
            # Shift all in-memory coordinates by the exact same offset
            def _shift_pt(p):
                return (p[0] + shift_x, p[1] + shift_y)
                
            # Shift trace image center coordinates in Python memory
            trace_mgr.x = cx + shift_x
            trace_mgr.y = cy + shift_y
            
            # Shift active drawing lists
            if hasattr(tools, "polygon_points") and isinstance(tools.polygon_points, list):
                tools.polygon_points = [_shift_pt(p) for p in tools.polygon_points]
            if hasattr(tools, "vastu_polygon_points") and isinstance(tools.vastu_polygon_points, list):
                tools.vastu_polygon_points = [_shift_pt(p) for p in tools.vastu_polygon_points]
            if hasattr(tools, "freeform_points") and isinstance(tools.freeform_points, list):
                tools.freeform_points = [_shift_pt(p) for p in tools.freeform_points]
                
            if getattr(tools, "first_point", None):
                tools.first_point = _shift_pt(tools.first_point)
            if getattr(tools, "temp_origin", None):
                tools.temp_origin = _shift_pt(tools.temp_origin)
            if getattr(tools, "_wall_erase_first_point", None):
                tools._wall_erase_first_point = _shift_pt(tools._wall_erase_first_point)
                
            # Shift line editing endpoints
            if hasattr(tools, "line_metadata") and isinstance(tools.line_metadata, dict):
                for meta in tools.line_metadata.values():
                    if "x0" in meta: meta["x0"] += shift_x
                    if "y0" in meta: meta["y0"] += shift_y
                    if "x1" in meta: meta["x1"] += shift_x
                    if "y1" in meta: meta["y1"] += shift_y
                    
                    # Recompute intermediate coordinate positions and distance labels
                    try:
                        from drawing_helpers import get_distance_label
                        label_text, mid_x, mid_y = get_distance_label(
                            meta["x0"], meta["y0"], meta["x1"], meta["y1"], model.unit, model.zoom_level
                        )
                        if "label" in meta:
                            tools.canvas.coords(meta["label"], mid_x, mid_y - 10)
                            tools.canvas.itemconfig(meta["label"], text=label_text)
                        if "point" in meta:
                            tools.canvas.coords(meta["point"], meta["x1"] - 0.5, meta["y1"] - 0.5, meta["x1"] + 0.5, meta["y1"] + 0.5)
                    except Exception:
                        pass
                        
            # Shift polygon baselines
            if hasattr(tools, "_polygon_baseline_coords_by_group") and isinstance(tools._polygon_baseline_coords_by_group, dict):
                for k, flat in list(tools._polygon_baseline_coords_by_group.items()):
                    if isinstance(flat, list):
                        tools._polygon_baseline_coords_by_group[k] = [
                            (v + shift_x if i % 2 == 0 else v + shift_y)
                            for i, v in enumerate(flat)
                        ]
                        
        # Redraw trace manager immediately to keep pixels crisp
        trace_mgr.render()
        
        # Redraw grid lines to refresh visual background
        tools.view.draw_grid()
        
        # Center the scrollbar viewport EXACTLY on the trace image center as safety fallback
        center_view_on_canvas_point(tools, trace_mgr.x, trace_mgr.y)
    except Exception as ez:
        print(f"[Trace Calibration] Auto zoom-out & centering viewport failed: {ez}")

    # --- 6. Update UI Controls ---
    if trace_mgr.scale_slider:
        try:
            trace_mgr.scale_slider.set(trace_mgr.scale)
        except Exception:
            pass
    if trace_mgr.scale_value_lbl:
        try:
            trace_mgr.scale_value_lbl.configure(text=f"Image Size: {int(trace_mgr.scale * 100)}%")
        except Exception:
            pass

    # Redraw grid lines to refresh visual background
    try:
        tools.view.schedule_grid_redraw(delay_ms=0)
    except Exception:
        pass

    return True
