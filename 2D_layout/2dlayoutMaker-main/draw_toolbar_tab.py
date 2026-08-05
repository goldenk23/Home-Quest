# draw_toolbar_tab.py
import tkinter as tk
import os
import sys
import importlib.util

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

# Resolve CTK & COLORS
try:
    from Helper.ctk_global import ctk
except ModuleNotFoundError:
    _helper_dir = os.path.join(_THIS_DIR, "Helper")
    _ctk_path = os.path.join(_helper_dir, "ctk_global.py")
    _spec = importlib.util.spec_from_file_location("mini_autocad_ctk_global", _ctk_path)
    if _spec and _spec.loader:
        _module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        ctk = getattr(_module, "ctk")
    else:
        raise

try:
    from Helper.color_scheme import COLORS
except ModuleNotFoundError:
    _helper_dir = os.path.join(_THIS_DIR, "Helper")
    _color_path = os.path.join(_helper_dir, "color_scheme.py")
    _spec = importlib.util.spec_from_file_location("mini_autocad_color_scheme", _color_path)
    if _spec and _spec.loader:
        _module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        COLORS = getattr(_module, "COLORS", {})
    else:
        COLORS = {}

from Helper.zoom_helper import CanvasZoomController


class PolygonMeasurementsToggleController:
    """
    Under the Polygon tool, show a toggle that controls whether measurement/dimension
    lines are drawn when a polygon is completed.
    """

    def __init__(self, parent, model) -> None:
        self._parent = parent
        self._model = model

        default_on = bool(getattr(model, "auto_polygon_dimensions", True))
        try:
            setattr(model, "auto_polygon_dimensions", default_on)
        except Exception:
            pass

        self._var = tk.BooleanVar(value=default_on)
        self._switch = ctk.CTkSwitch(
            parent,
            text="📐 Measurements",
            variable=self._var,
            command=self._on_toggle,
            fg_color=(COLORS["border"], COLORS["border_dark"]),
            progress_color=(COLORS["secondary"], COLORS["secondary"]),
            button_color=(COLORS["error"], COLORS["error"]),
            button_hover_color=("#DC2626", "#DC2626"),
            text_color=(COLORS["text_primary"], COLORS["text_white"]),
        )

        # Start disabled until polygon tool is selected
        try:
            self._switch.configure(state="disabled")
        except Exception:
            pass

    def pack(self, **kwargs) -> None:
        self._switch.pack(**kwargs)

    def start_sync(self, interval_ms: int = 500) -> None:
        self._interval_ms = max(200, int(interval_ms))
        self._sync_once()

    def _on_toggle(self) -> None:
        try:
            self._model.auto_polygon_dimensions = bool(self._var.get())
        except Exception:
            pass

    def _sync_once(self) -> None:
        # Keep model <-> UI in sync and enable/disable based on polygon_mode
        try:
            enabled = bool(self._model.get("polygon_mode"))
        except Exception:
            enabled = False

        try:
            target_state = "normal" if enabled else "disabled"
            if self._switch.cget("state") != target_state:
                self._switch.configure(state=target_state)
        except Exception:
            pass

        try:
            current = bool(getattr(self._model, "auto_polygon_dimensions", True))
            if bool(self._var.get()) != current:
                self._var.set(current)
        except Exception:
            pass

        try:
            self._parent.after(max(1000, self._interval_ms), self._sync_once)
        except Exception:
            pass


class DrawToolbarTab:
    """Class representing the Drawing Tools sidebar tab."""

    def __init__(self, model, tools, view) -> None:
        self.model = model
        self.tools = tools
        self.view = view

    def _enable_tool(self, mode_key: str) -> None:
        """Helper to activate a drawing/fill/text mode and update cursor."""
        self.tools.reset_modes()
        self.model.set(mode_key, True)

        cursor_map = {
            "drawing_enabled": "crosshair",
            "polygon_mode": "crosshair",
            "text_insertion_mode": "xterm",
            "fill_mode_enabled": "dotbox"
        }
        self.view.canvas.config(cursor=cursor_map.get(mode_key, "arrow"))

    def build(self, draw_body) -> None:
        # 1. Info Help Card
        help_card = ctk.CTkFrame(
            draw_body,
            fg_color=(COLORS.get("primary_light", "#6366F1"), "#312E81"),
            corner_radius=8,
            border_width=1,
            border_color=COLORS.get("primary", "#4F46E5"),
        )
        help_card.pack(fill="x", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(
            help_card,
            text="✏️ Draw / चित्रकारी (दीवार और रेखाएं)",
            font=("Segoe UI", 12, "bold"),
            text_color="#FFFFFF",
            anchor="w",
            wraplength=180
        ).pack(fill="x", padx=10, pady=(6, 2))
        
        ctk.CTkLabel(
            help_card,
            text="• Click on Line/Polygon, then click on Canvas.\n• Press ESC or Right-Click to finish/cancel.\n• Click 'Add Flooring' for textures.",
            font=("Segoe UI", 10),
            text_color="#E2E8F0",
            justify="left",
            anchor="w",
            wraplength=180
        ).pack(fill="x", padx=10, pady=(0, 6))

        # 2. Header
        ctk.CTkLabel(
            draw_body, 
            text="Drawing Tools", 
            font=("Segoe UI", 16, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(0, 5))
        
        # Canvas Zoom Controls
        zoom_ctrl = CanvasZoomController(draw_body, self.view, self.tools)
        zoom_ctrl.pack(pady=(5, 10), padx=10, fill="x")
        
        # Drawing tool buttons with subtle colors
        line_btn = ctk.CTkButton(
            draw_body, 
            text="✏️ Line", 
            command=lambda: self._enable_tool("drawing_enabled"),
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            height=36,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        line_btn.pack(pady=4, padx=10, fill="x")
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(line_btn, "Draw connected, snapping line segments. Press Escape or right-click to stop.")

        # Windows & Ventilation moved to the Furniture panel (see toolbar.py).

        line_actions = ctk.CTkFrame(draw_body, fg_color="transparent")
        line_actions.pack(pady=(0, 4), padx=10, fill="x")
        ctk.CTkButton(line_actions, text="Lines → Room", command=self.tools.create_room_from_closed_lines, height=30).pack(fill="x")
        
        line_color_btn = ctk.CTkButton(
            draw_body,
            text="🎨 Line Color",
            command=self.tools.pick_line_color,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=32,
            corner_radius=6,
            text_color=COLORS["text_white"],
        )
        line_color_btn.pack(pady=(0, 4), padx=10, fill="x")
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(line_color_btn, "Choose a custom color for your lines/walls.")
        
        # Line style section
        ctk.CTkLabel(
            draw_body, 
            text="Line Style",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(10, 2))

        line_style_var = ctk.StringVar(value="solid")
        def on_line_style_change(style):
            self.model.line_style = style
        line_style_menu = ctk.CTkOptionMenu(
            draw_body,
            variable=line_style_var,
            values=["solid", "bold", "dashed"],
            command=on_line_style_change,
            fg_color=COLORS["surface"],
            button_color=COLORS["primary"],
            button_hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_primary"]
        )
        line_style_menu.pack(pady=2, padx=10, fill="x")
        
        # Line Arrow section
        ctk.CTkLabel(
            draw_body, 
            text="Line Arrow",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(10, 2))

        line_arrow_var = ctk.StringVar(value="none")
        def on_line_arrow_change(arrow):
            self.model.line_arrow = arrow
        line_arrow_menu = ctk.CTkOptionMenu(
            draw_body,
            variable=line_arrow_var,
            values=["none", "first", "last", "both"],
            command=on_line_arrow_change,
            fg_color=COLORS["surface"],
            button_color=COLORS["primary"],
            button_hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_primary"]
        )
        line_arrow_menu.pack(pady=2, padx=10, fill="x")
        
        # More drawing tools
        poly_btn = ctk.CTkButton(
            draw_body, 
            text="⬟ Polygon", 
            command=lambda: self._enable_tool("polygon_mode"),
            fg_color=COLORS["text_secondary"],
            hover_color="#4B5563",
            height=36,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        poly_btn.pack(pady=4, padx=10, fill="x")
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(poly_btn, "Draw customized rooms or boundaries with multiple points.")

        # Explicit finish/cancel actions for polygon drawing (enabled only in polygon mode)
        poly_actions = ctk.CTkFrame(draw_body, fg_color="transparent")
        poly_actions.pack(pady=(0, 4), padx=10, fill="x")
        poly_actions.columnconfigure(0, weight=1)
        poly_actions.columnconfigure(1, weight=1)
        finish_poly_btn = ctk.CTkButton(
            poly_actions,
            text="✔ Finish",
            command=self.tools.finish_polygon,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            height=30,
            corner_radius=6,
            text_color=COLORS["text_white"],
            state="disabled",
        )
        finish_poly_btn.grid(row=0, column=0, padx=(0, 2), sticky="ew")
        cancel_poly_btn = ctk.CTkButton(
            poly_actions,
            text="✖ Cancel",
            command=self.tools.cancel_polygon,
            fg_color=COLORS["error"],
            hover_color="#DC2626",
            height=30,
            corner_radius=6,
            text_color=COLORS["text_white"],
            state="disabled",
        )
        cancel_poly_btn.grid(row=0, column=1, padx=(2, 0), sticky="ew")
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(finish_poly_btn, "Finish and close the polygon (or click the highlighted first point).")
            self.tools.create_tooltip(cancel_poly_btn, "Discard the in-progress polygon and all its points.")

        # Toggle: draw measurement (dimension) lines on polygon completion
        poly_dims_toggle = PolygonMeasurementsToggleController(draw_body, self.model)
        poly_dims_toggle.pack(pady=(0, 6), padx=24, fill="x")
        poly_dims_toggle.start_sync(interval_ms=150)
        
        def enable_fill_with_color_picker():
            self.tools.pick_fill_color()
            self._enable_tool("fill_mode_enabled")

        fill_btn = ctk.CTkButton(
            draw_body, 
            text="🎨 Fill", 
            command=enable_fill_with_color_picker,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=36,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        fill_btn.pack(pady=4, padx=10, fill="x")
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(fill_btn, "Fill a bounded room or closed region with color.")
        
        text_btn = ctk.CTkButton(
            draw_body, 
            text="📝 Text", 
            command=lambda: self._enable_tool("text_insertion_mode"),
            fg_color=COLORS["info"],
            hover_color="#2563EB",
            height=36,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        text_btn.pack(pady=4, padx=10, fill="x")
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(text_btn, "Click anywhere on the canvas to place custom text labels.")

        # --- Sidebar Mode Highlighting Logic ---
        def _sync_tool_highlight():
            try:
                if not draw_body.winfo_exists():
                    return
                
                def _update_btn(btn, mode_key, active_color):
                    is_active = bool(self.model.get(mode_key))
                    target_color = active_color if is_active else COLORS["surface"]
                    target_text = COLORS["text_white"] if is_active else COLORS["text_primary"]
                    
                    if btn.cget("fg_color") != target_color:
                        btn.configure(fg_color=target_color, text_color=target_text)
                
                _update_btn(line_btn, "drawing_enabled", COLORS["primary"])
                _update_btn(poly_btn, "polygon_mode", COLORS["accent"])
                _update_btn(fill_btn, "fill_mode_enabled", COLORS["secondary"])
                _update_btn(text_btn, "text_insertion_mode", COLORS["info"])

                poly_state = "normal" if bool(self.model.get("polygon_mode")) else "disabled"
                for action_btn in (finish_poly_btn, cancel_poly_btn):
                    if action_btn.cget("state") != poly_state:
                        action_btn.configure(state=poly_state)
                
                draw_body.after(1000, _sync_tool_highlight)
            except Exception:
                pass
            
        _sync_tool_highlight()
        
        # Flooring section
        ctk.CTkLabel(
            draw_body,
            text="Flooring",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(15, 5))
        
        flooring_btn = ctk.CTkButton(
            draw_body, 
            text="🏠 Add Flooring", 
            command=self.tools.enable_flooring_mode,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            height=36,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        flooring_btn.pack(pady=4, padx=10, fill="x")
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(flooring_btn, "Draw/fill textures (wood, tile, marble, garden) in bounded rooms.")
        
        ctk.CTkLabel(
            draw_body, 
            text="Flooring Type:",
            font=("Segoe UI", 11),
            text_color=COLORS["text_primary"]
        ).pack(pady=(5, 2))
        
        flooring_menu = ctk.CTkOptionMenu(
            draw_body,
            variable=self.tools.flooring_type_var,
            values=["None / Default (No Flooring)", "wood", "tile", "marble", "garden"],
            command=lambda _: self.tools.enable_flooring_mode(),
            fg_color=COLORS["surface"],
            button_color=COLORS["secondary"],
            button_hover_color=COLORS["secondary_hover"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"]
        )
        flooring_menu.pack(pady=2, padx=10, fill="x")
