from __future__ import annotations

import os
import sys
import importlib.util
import tkinter as tk
from tkinter import Menu
from help_guide_dialog import HelpGuideDialog

# Ensure this module's directory is on sys.path so local `Helper/*` resolves when this
# file is imported from the parent Vastu app (which may have a different cwd).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

def _import_local_module(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if not spec or not spec.loader:
        raise ModuleNotFoundError(f"Could not load module from: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


try:
    from Helper.color_scheme import COLORS
except ModuleNotFoundError:
    _helper_dir = os.path.join(_THIS_DIR, "Helper")
    _color_path = os.path.join(_helper_dir, "color_scheme.py")
    _m = _import_local_module("mini_autocad_color_scheme", _color_path)
    COLORS = getattr(_m, "COLORS", {})

try:
    from Helper.ctk_global import ctk
except ModuleNotFoundError:
    _helper_dir = os.path.join(_THIS_DIR, "Helper")
    _ctk_path = os.path.join(_helper_dir, "ctk_global.py")
    _m = _import_local_module("mini_autocad_ctk_global", _ctk_path)
    ctk = getattr(_m, "ctk")


class TopActionToolbar:
    """
    Compact, premium toolbar for global actions.
    Optimized for smaller screen real-estate while maintaining high usability.
    """

    def __init__(self, parent, controller, actions, tools, serializer, on_project_tools=None) -> None:
        self._parent = parent
        self._controller = controller
        self._actions = actions
        self._tools = tools
        self._serializer = serializer
        self._on_project_tools = on_project_tools

        self.frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS.get("workspace_header", "#081321"),
            border_color=COLORS.get("border", "#363C44"),
            border_width=0,
            corner_radius=0,
            height=44,
        )
        self.frame.pack(side="left", fill="both", expand=True)
        self.frame.pack_propagate(False)

        # A compact draggable slider handles toolbar overflow.
        self._scroll_slider = ctk.CTkSlider(
            self.frame,
            from_=0,
            to=1,
            command=self._on_slider_change,
            height=8,
            button_length=14,
            corner_radius=3,
            border_width=0,
            fg_color=COLORS.get("surface_muted", "#2B3138"),
            progress_color=COLORS.get("primary", "#55D6C2"),
            button_color=COLORS.get("primary_light", "#78E2D2"),
            button_hover_color=COLORS.get("primary", "#55D6C2"),
        )
        self._scroll_slider.pack(side="bottom", fill="x", padx=(40, 8), pady=(0, 1))
        self._scroll_slider.set(0)
        # Debounce handle for slider/overflow refresh so rapid canvas resizes (e.g.
        # sidebar drag) don't force a synchronous full-window reflow each event.
        self._scroll_slider_after_id = None

        self._scroll_row = ctk.CTkFrame(
            self.frame,
            fg_color=COLORS.get("workspace_header", "#081321"),
            corner_radius=0,
        )
        self._scroll_row.pack(side="top", fill="both", expand=True)

        # Keep only the sidebar collapse control fixed; all actions use the freed space.
        context_row = ctk.CTkFrame(self._scroll_row, fg_color=COLORS.get("workspace_header", "#081321"))
        context_row.pack(side="left", fill="y", padx=(5, 5), pady=2)
        self._section_title_var = tk.StringVar(value="VastuCraft Pro")
        self._sidebar_toggle_btn = ctk.CTkButton(
            context_row,
            text="◀",
            command=self._toggle_sidebar,
            width=30,
            height=28,
            corner_radius=6,
            fg_color=COLORS.get("surface", "#1E293B"),
            hover_color=COLORS.get("primary_surface", "#153B3D"),
            border_width=1,
            border_color=COLORS.get("secondary", "#0F766E"),
            text_color="#FFFFFF",
            font=("Segoe UI Symbol", 10, "bold"),
        )
        self._sidebar_toggle_btn.pack(side="left")
        self._controller.set_sidebar_collapsed = self._set_sidebar_collapsed_state

        self._scroll_canvas = tk.Canvas(
            self._scroll_row,
            bg=COLORS.get("workspace_header", "#081321"),
            highlightthickness=0,
            bd=0,
            takefocus=0,
        )
        self._scroll_canvas.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=(2, 0))

        # Inner Frame container inside canvas
        self._inner_frame = ctk.CTkFrame(
            self._scroll_canvas,
            fg_color=self.frame.cget("fg_color")
        )
        self._canvas_window = self._scroll_canvas.create_window(
            (0, 0),
            window=self._inner_frame,
            anchor="nw"
        )

        # Ribbon scrolling handlers
        self._inner_frame.bind("<Configure>", self._on_inner_configure)
        self._scroll_canvas.bind("<Configure>", self._on_canvas_configure)
        self._scroll_canvas.configure(xscrollcommand=self._on_scroll)

        # Setup mousewheel scroll listeners on child widgets
        self._setup_mousewheel_scrolling()

        inner = self._inner_frame

        # --- Group 1: File Operations ---
        file_row = ctk.CTkFrame(inner, fg_color=inner.cget("fg_color"))
        file_row.pack(side="left")

        self._new_btn = self._create_btn(
            file_row, "📄 New", self._on_reset_canvas, 
            color=COLORS.get("surface", "#F9FAFB"), 
            width=60,
            text_color=COLORS.get("text_primary", "#111827"),
            border_width=1,
            border_color=COLORS.get("border", "#E5E7EB")
        )
        self._load_btn = self._create_btn(
            file_row, "📂 Load", self._on_load_layout, 
            color=COLORS.get("surface", "#F9FAFB"), 
            width=65,
            text_color=COLORS.get("text_primary", "#111827"),
            border_width=1,
            border_color=COLORS.get("border", "#E5E7EB")
        )


        # Create Dropdown (Room + Generate Layout)
        self._create_btn_obj = self._create_btn(
            file_row,
            "✦ Create⌄",
            self._show_create_menu,
            COLORS.get("primary_surface", "#153B3D"),
            width=88,
            text_color=COLORS.get("primary", "#2DD4BF"),
            border_color=COLORS.get("secondary", "#0F766E"),
        )
        
        # Premium Styled Create Menu
        self._create_menu = tk.Menu(
            self._parent,
            tearoff=0,
            font=("Segoe UI", 10),
            bg=COLORS.get("surface", "white"),
            fg=COLORS.get("text_primary", "black"),
            activebackground=COLORS.get("primary", "#4F46E5"),
            activeforeground="white",
            relief="flat",
            bd=1
        )
        self._create_menu.add_command(label="  🏠  Create Room", command=self._on_open_room_tab)
        self._create_menu.add_command(label="  🏗️  Generate Layout", command=self._on_open_layout_tab)
        
        # Save Button with Dropdown (Primary action opens the menu)
        self._save_btn = self._create_btn(file_row, "💾 Save ▼", self._show_save_menu, COLORS.get("success", "#10B981"), width=90)
        
        # Premium Styled Save Menu
        self._save_menu = tk.Menu(
            self._parent,
            tearoff=0,
            font=("Segoe UI", 10),
            bg=COLORS.get("surface", "white"),
            fg=COLORS.get("text_primary", "black"),
            activebackground=COLORS.get("primary", "#4F46E5"),
            activeforeground="white",
            relief="flat",
            bd=1
        )
        self._save_menu.add_command(label="  💾  Save Layout", command=self._on_save_layout)
        self._save_menu.add_command(label="  📄  Save As JSON", command=self._on_save_as_json)
        self._save_menu.add_command(label="  📝  Save As YAML", command=self._on_save_as_yaml)
        self._save_menu.add_separator()
        self._save_menu.add_command(label="  📸  Area Screenshot", command=self._on_save_area_png)
        self._save_menu.add_command(label="  🖼️  Full Canvas PNG", command=self._on_save_canvas_image)

        # Always-visible access to the editing features added across the sidebar tabs.
        self._tools_btn = self._create_btn(
            file_row,
            "✨ Editing Tools ▼",
            self._show_tools_menu,
            COLORS.get("accent", "#7C3AED"),
            width=125,
        )
        self._tools_menu = tk.Menu(
            self._parent,
            tearoff=0,
            font=("Segoe UI", 10),
            bg=COLORS.get("surface", "white"),
            fg=COLORS.get("text_primary", "black"),
            activebackground=COLORS.get("accent", "#7C3AED"),
            activeforeground="white",
            relief="flat",
            bd=1,
        )
        self._tools_menu.add_command(label="  🪟  Place Window / Ventilation", command=self._tools.enable_window_mode)
        self._tools_menu.add_command(label="  🏠  Create Room from Closed Lines", command=self._tools.create_room_from_closed_lines)
        self._tools_menu.add_separator()
        self._tools_menu.add_command(label="  ✥  Move / Edit Selected", command=self._tools.edit_selected_item)
        self._tools_menu.add_command(label="  ↻  Rotate Clockwise 15°", command=lambda: self._tools.rotate_selected_furniture(clockwise=True))

        if self._on_project_tools is not None:
            self._project_tools_btn = self._create_btn(
                file_row,
                "⌂ Project⌄",
                lambda: self._on_project_tools(self._project_tools_btn),
                COLORS.get("primary_surface", "#153B3D"),
                width=90,
                text_color=COLORS.get("primary", "#2DD4BF"),
                border_color=COLORS.get("secondary", "#0F766E"),
            )
            self._project_tools_btn.pack_configure(before=self._new_btn)
        self._tools_menu.add_command(label="  ↺  Rotate Anti-clockwise 15°", command=self._tools.rotate_selected_furniture_counterclockwise)
        self._tools_menu.add_command(label="  ⟲  Reset to Initial Orientation", command=self._tools.reset_selected_furniture_rotation)
        self._tools_menu.add_command(label="  ⧉  Duplicate Selected Furniture", command=self._duplicate_selected_furniture)
        self._tools_menu.add_command(label="  🗑  Delete Selected", command=self._tools.delete_selected)
        self._tools_menu.add_separator()
        self._tools_menu.add_command(label="  ➖  Reduce Furniture Size", command=lambda: self._tools.resize_selected_furniture(0.9))
        self._tools_menu.add_command(label="  📐  Set Exact Furniture Size", command=self._tools.set_selected_furniture_size)
        self._tools_menu.add_command(label="  ➕  Increase Furniture Size", command=lambda: self._tools.resize_selected_furniture(1.1))
        self._tools_menu.add_separator()
        self._tools_menu.add_command(label="  ✥  Select / Move Entire Layout", command=self._tools.select_entire_layout)
        self._tools_menu.add_command(label="  ⧉  Duplicate Entire Layout", command=self._serializer.duplicate_layout)
        self._tools_menu.add_command(label="  ⛶  Fit Design", command=self._controller.view.fit_design)
        self._tools_menu.add_command(label="  ↺  Reset View", command=self._controller.view.reset_view)
        self._tools_menu.add_command(label="  ⟳  Refresh UI / Cancel Tool", command=self._on_refresh_ui)

        self._add_separator(inner)

        # --- Group 2: History (Undo/Redo) ---
        hist_row = ctk.CTkFrame(inner, fg_color=inner.cget("fg_color"))
        hist_row.pack(side="left")

        self._undo_btn = self._create_btn(
            hist_row, "⟲ Undo", self._on_undo, 
            color=COLORS.get("surface", "#F9FAFB"), 
            width=75,
            text_color=COLORS.get("text_primary", "#111827"),
            border_width=1,
            border_color=COLORS.get("border", "#E5E7EB")
        )
        self._redo_btn = self._create_btn(
            hist_row, "↷ Redo", self._on_redo,
            color=COLORS.get("surface", "#1E293B"),
            width=66,
            text_color=COLORS.get("text_secondary", "#CBD5E1"),
            border_width=1,
            border_color=COLORS.get("border", "#2A3A52")
        )

        self._add_separator(inner)

        # --- Group 3: Grid & Units ---
        grid_unit_row = ctk.CTkFrame(inner, fg_color=inner.cget("fg_color"))
        grid_unit_row.pack(side="left")

        self._grid_btn = self._create_btn(
            grid_unit_row, "🌐 Grid", self._on_toggle_grid, 
            color=COLORS.get("surface", "#F9FAFB"), 
            width=70,
            text_color=COLORS.get("text_primary", "#111827"),
            border_width=1,
            border_color=COLORS.get("border", "#E5E7EB")
        )
        
        unit_lbl = ctk.CTkLabel(
            grid_unit_row,
            text="Unit",
            font=("Segoe UI", 8),
            text_color=COLORS.get("text_secondary", "#CBD5E1")
        )
        unit_lbl.pack(side="left", padx=(4, 2))

        self._unit_var = tk.StringVar(value=self._controller.model.unit)
        self._unit_menu = ctk.CTkOptionMenu(
            grid_unit_row,
            variable=self._unit_var,
            values=list(self._controller.model.unit_scale.keys()),
            command=self._on_unit_change,
            width=46,
            height=24,
            corner_radius=5,
            fg_color=COLORS.get("surface_dark", "#0B1220"),
            button_color=COLORS.get("secondary", "#0F766E"),
            button_hover_color=COLORS.get("primary_hover", "#14B8A6"),
            text_color=COLORS.get("text_primary", "#F1F5F9"),
            font=("Segoe UI", 8, "bold"),
            dropdown_font=("Segoe UI", 8),
            dropdown_fg_color=COLORS.get("surface", "#1E293B"),
            dropdown_text_color=COLORS.get("text_primary", "#F1F5F9"),
            dropdown_hover_color=COLORS.get("surface_muted", "#263449"),
        )
        self._unit_menu.pack(side="left", padx=(0, 4))

        self._add_separator(inner)

        # --- Group 4: Global Utils ---
        util_row = ctk.CTkFrame(inner, fg_color=inner.cget("fg_color"))
        util_row.pack(side="left")

        self._erase_walls_btn = self._create_btn(util_row, "🧹 Erase Walls ▼", self._show_erase_menu, COLORS.get("warning", "#F59E0B"), width=110)
        self._clear_all_btn = self._create_btn(util_row, "🗑️ Clear All", self._on_reset_canvas, "#DC2626", width=95)

        # Premium Styled Erase Menu
        self._erase_menu = tk.Menu(
            self._parent,
            tearoff=0,
            font=("Segoe UI", 10),
            bg=COLORS.get("surface", "white"),
            fg=COLORS.get("text_primary", "black"),
            activebackground=COLORS.get("warning", "#F59E0B"),
            activeforeground="white",
            relief="flat",
            bd=1
        )
        self._erase_menu.add_command(label="  ✏️  Erase Part (2 Points)", command=self._on_erase_part)
        self._erase_menu.add_command(label="  🧹  Erase Multiple (Area Selection)", command=self._on_erase_multiple)

        # --- Group 5: Help & Guides ---
        self._add_separator(inner)
        help_row = ctk.CTkFrame(inner, fg_color=inner.cget("fg_color"))
        help_row.pack(side="left")
        self._help_btn = self._create_btn(
            help_row, 
            "❓ Help Guide", 
            self._show_help_dialog, 
            COLORS.get("info", "#3B82F6"), 
            width=105
        )

        # Attach tooltips to all buttons
        if hasattr(self._tools, "create_tooltip"):
            self._tools.create_tooltip(self._new_btn, "Create a fresh empty canvas / नया खाली कैनवास बनाएं")
            self._tools.create_tooltip(self._load_btn, "Open a saved layout file / लेआउट फाइल लोड करें")
            self._tools.create_tooltip(self._create_btn_obj, "Create Room or generate auto-layouts / रूम या लेआउट बनाएं")
            self._tools.create_tooltip(self._save_btn, "Save layout as JSON/YAML or PNG Image / लेआउट सेव या निर्यात करें")
            self._tools.create_tooltip(self._tools_btn, "All enhanced window, line, room, furniture, duplicate, and view commands")
            self._tools.create_tooltip(self._undo_btn, "Undo last drawing action (Ctrl+Z) / पिछला एक्शन पूर्ववत करें")
            self._tools.create_tooltip(self._redo_btn, "Redo undone action (Ctrl+Y) / रद्द किया गया एक्शन फिर से करें")
            self._tools.create_tooltip(self._grid_btn, "Toggle background grid lines / ग्रिड लाइन्स ऑन-ऑफ करें")
            self._tools.create_tooltip(self._unit_menu, "Change workspace units / नाप की यूनिट बदलें")
            self._tools.create_tooltip(self._erase_walls_btn, "Erase wall segments / दीवार की रेखाएं मिटाएं")
            self._tools.create_tooltip(self._clear_all_btn, "Clear entire canvas workspace / पूरा कैनवास खाली करें")
            self._tools.create_tooltip(self._help_btn, "Open quick tutorials and control shortcuts / मदद और शॉर्टकट निर्देशिका")

        # Spacer
        ctk.CTkFrame(inner, fg_color=inner.cget("fg_color")).pack(side="left", fill="x", expand=True)

        # Explicit update to resolve initial rendering glitches on Windows.
        self.frame.update()
        self.frame.after_idle(self._schedule_scroll_slider_update)
        self._sync_button_state()

    def _create_btn(self, parent, text, command, color, width=None, side="left", padx=(2, 2), text_color=None, border_width=1, border_color=None):
        btn = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=28,
            width=max(46, int((width if width else 75) * 0.78)),
            corner_radius=6,
            fg_color=color,
            hover_color=self._get_hover_color(color),
            text_color=text_color if text_color else COLORS.get("text_primary", "#F1F5F9"),
            border_width=border_width,
            border_color=border_color or COLORS.get("border", "#2A3A52"),
            font=("Segoe UI", 9, "bold"),
        )
        btn.pack(side=side, padx=padx)
        return btn

    def _get_hover_color(self, hex_color):
        if hex_color.startswith("#") and len(hex_color) == 7:
            try:
                r = int(hex_color[1:3], 16)
                g = int(hex_color[3:5], 16)
                b = int(hex_color[5:7], 16)
                return f"#{min(255, r+14):02x}{min(255, g+14):02x}{min(255, b+14):02x}"
            except Exception:
                return hex_color
        return hex_color

    def _add_separator(self, parent):
        sep = ctk.CTkFrame(parent, width=1, fg_color=COLORS.get("border", "#2A3A52"))
        sep.pack(side="left", fill="y", padx=4, pady=6)

    def _show_create_menu(self) -> None:
        """Show the create dropdown menu at the button position."""
        self._parent.update_idletasks()
        x = self._create_btn_obj.winfo_rootx()
        y = self._create_btn_obj.winfo_rooty() + self._create_btn_obj.winfo_height()
        try:
            self._create_menu.tk_popup(x, y)
        finally:
            self._create_menu.grab_release()

    def _show_save_menu(self) -> None:
        """Show the save dropdown menu at the button position."""
        self._parent.update_idletasks()
        x = self._save_btn.winfo_rootx()
        y = self._save_btn.winfo_rooty() + self._save_btn.winfo_height()
        try:
            self._save_menu.tk_popup(x, y)
        finally:
            self._save_menu.grab_release()

    def _show_tools_menu(self) -> None:
        """Show all enhanced editing commands from any active sidebar tab."""
        self._parent.update_idletasks()
        x = self._tools_btn.winfo_rootx()
        y = self._tools_btn.winfo_rooty() + self._tools_btn.winfo_height()
        try:
            self._tools_menu.tk_popup(x, y)
        finally:
            self._tools_menu.grab_release()

    def _duplicate_selected_furniture(self) -> None:
        self._tools.duplicate_furniture(getattr(self._tools, "selected_furniture_obj", None))

    def _on_refresh_ui(self) -> None:
        self._controller.refresh_ui()
        self._sync_button_state(reschedule=False)

    def _on_undo(self) -> None:
        self._controller._do_undo()
        self._sync_button_state(reschedule=False)

    def _on_redo(self) -> None:
        self._controller._do_redo()
        self._sync_button_state(reschedule=False)

    def _on_save_layout(self) -> None:
        if hasattr(self._serializer, "save_layout"):
            self._serializer.save_layout()
        else:
            self._serializer.save_to_json()

    def _on_save_as_json(self) -> None:
        self._serializer.save_to_json()

    def _on_save_as_yaml(self) -> None:
        if hasattr(self._serializer, "save_to_yaml"):
            self._serializer.save_to_yaml()

    def _on_save_area_png(self) -> None:
        self._tools.start_region_screenshot()

    def _on_save_canvas_image(self) -> None:
        if hasattr(self._tools, "save_canvas_image"):
            self._tools.save_canvas_image()

    def _on_load_layout(self) -> None:
        self._serializer.load_from_dialog()

    def _on_open_room_tab(self) -> None:
        """Switch the sidebar to the Room tab."""
        if hasattr(self._controller, "switch_tab"):
            self._controller.switch_tab("Room")

    def _on_open_layout_tab(self) -> None:
        """Switch the sidebar to the Generate Layout tab."""
        if hasattr(self._controller, "switch_tab"):
            self._controller.switch_tab("Generate Layout")

    def _on_erase_part(self) -> None:
        self._tools.enable_eraser_mode()

    def _on_erase_multiple(self) -> None:
        if hasattr(self._tools, "enable_multi_eraser_mode"):
            self._tools.enable_multi_eraser_mode()

    def _show_erase_menu(self) -> None:
        """Show the erase dropdown menu at the button position."""
        self._parent.update_idletasks()
        x = self._erase_walls_btn.winfo_rootx()
        y = self._erase_walls_btn.winfo_rooty() + self._erase_walls_btn.winfo_height()
        try:
            self._erase_menu.tk_popup(x, y)
        finally:
            self._erase_menu.grab_release()

    def _on_toggle_grid(self) -> None:
        if hasattr(self._controller.view, "toggle_grid"):
            self._controller.view.toggle_grid()

    def _on_unit_change(self, selected_unit: str) -> None:
        self._controller.model.set_unit(selected_unit)
        self._controller.view.draw_grid()
        
        # Also update placeholders in tools.room_widgets if they exist
        if hasattr(self._tools, "room_widgets"):
            suffix = selected_unit
            widgets = self._tools.room_widgets
            try:
                if "length" in widgets and widgets["length"].winfo_exists():
                    widgets["length"].configure(placeholder_text=f"Length ({suffix})")
                if "breadth" in widgets and widgets["breadth"].winfo_exists():
                    widgets["breadth"].configure(placeholder_text=f"Breadth ({suffix})")
                if "balcony_depth" in widgets and widgets["balcony_depth"].winfo_exists():
                    widgets["balcony_depth"].configure(placeholder_text=f"Balcony Depth ({suffix})")
            except Exception:
                pass

    def _on_reset_canvas(self) -> None:
        try:
            if hasattr(self._controller, "_stop_auto_pan"):
                self._controller._stop_auto_pan()
        except Exception:
            pass
        self._tools.reset_all_canvas(confirm=True)

    def _show_help_dialog(self) -> None:
        HelpGuideDialog(self._parent)

    def _sync_button_state(self, *, reschedule: bool = True) -> None:
        if not self.frame.winfo_exists():
            return
        
        # Enable "Erase Walls" only when a walls_only room exists.
        try:
            can_erase = bool(self._tools.has_walls_only_room())
        except Exception:
            can_erase = False
        
        target_state = "normal" if can_erase else "disabled"
        
        # Performance: Only re-configure if the state actually changed.
        try:
            current_state = self._erase_walls_btn.cget("state")
            if current_state != target_state:
                self._erase_walls_btn.configure(state=target_state)
        except Exception:
            pass

        # Highlight Active States (Grid and Erase)
        try:
            grid_active = bool(getattr(self._controller.view, "grid_visible", False))
            if grid_active:
                grid_color = COLORS.get("primary_surface", "#153B3D")
                grid_text = COLORS.get("primary", "#2DD4BF")
                grid_border = 1
            else:
                grid_color = COLORS.get("surface", "#F9FAFB")
                grid_text = COLORS.get("text_primary", "#111827")
                grid_border = 1
                
            if self._grid_btn.cget("fg_color") != grid_color:
                self._grid_btn.configure(
                    fg_color=grid_color, 
                    hover_color=self._get_hover_color(grid_color),
                    text_color=grid_text,
                    border_width=grid_border,
                    border_color=COLORS.get("border", "#E5E7EB"),
                )

            # Erase mode detection
            erase_active = bool(self._tools.model.get("eraser_mode")) or bool(self._tools.model.get("multi_eraser_mode"))
            erase_color = COLORS.get("error", "#DC2626") if erase_active else COLORS.get("warning", "#F59E0B")
            if self._erase_walls_btn.cget("fg_color") != erase_color:
                self._erase_walls_btn.configure(fg_color=erase_color, hover_color=self._get_hover_color(erase_color))
        except Exception:
            pass

        # Sync unit selection dropdown with global model unit state
        try:
            current_model_unit = getattr(self._controller.model, "unit", "ft")
            if self._unit_var.get() != current_model_unit:
                self._unit_var.set(current_model_unit)
        except Exception:
            pass

        if reschedule:
            # Increased interval to 1000ms to reduce idle load.
            self.frame.after(1000, self._sync_button_state)

    def _set_section_title(self, title: str) -> None:
        self._section_title_var.set(str(title))

    def _toggle_sidebar(self) -> None:
        toggle = getattr(self._controller, "toggle_sidebar", None)
        if callable(toggle):
            toggle()

    def _set_sidebar_collapsed_state(self, collapsed: bool) -> None:
        self._sidebar_toggle_btn.configure(text="▶" if collapsed else "◀")

    def _on_zoom_slider(self, value) -> None:
        try:
            current = max(0.000001, float(getattr(self._controller.model, "zoom_level", 1.0)))
            target = max(0.25, min(4.0, float(value) / 100.0))
            self._controller.view.apply_zoom(target / current)
        except (AttributeError, TypeError, ValueError):
            pass

    def _on_inner_configure(self, event) -> None:
        try:
            self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))
            # Make the inner frame height match the canvas height so it matches layout scaling
            canvas_height = self._scroll_canvas.winfo_height()
            if canvas_height > 1:
                self._scroll_canvas.itemconfig(self._canvas_window, height=canvas_height)
            self._schedule_scroll_slider_update()
        except Exception:
            pass

    def _on_canvas_configure(self, event) -> None:
        try:
            # Stretch content vertically inside the canvas
            canvas_height = event.height
            if canvas_height > 1:
                self._scroll_canvas.itemconfig(self._canvas_window, height=canvas_height)
            self._schedule_scroll_slider_update()
        except Exception:
            pass

    def _on_scroll(self, *args) -> None:
        try:
            if len(args) >= 2:
                left, right = float(args[0]), float(args[1])
                max_left = max(0.0, 1.0 - (right - left))
                self._scroll_slider.set(left / max_left if max_left else 0.0)
        except (TypeError, ValueError):
            pass

    def _on_slider_change(self, value) -> None:
        try:
            left, right = self._scroll_canvas.xview()
            max_left = max(0.0, 1.0 - (right - left))
            self._scroll_canvas.xview_moveto(float(value) * max_left)
        except (tk.TclError, TypeError, ValueError):
            pass

    def _schedule_scroll_slider_update(self, delay_ms: int = 40) -> None:
        """Coalesce rapid canvas-resize driven slider refreshes into one deferred pass
        so a sidebar drag (60-125Hz Configure events) doesn't synchronously reflow the
        whole window on every event (~270ms each)."""
        try:
            if self._scroll_slider_after_id is not None:
                self.frame.after_cancel(self._scroll_slider_after_id)
        except Exception:
            pass
        self._scroll_slider_after_id = self.frame.after(delay_ms, self._refresh_scroll_slider)

    def _refresh_scroll_slider(self) -> None:
        self._scroll_slider_after_id = None
        try:
            if not self._scroll_canvas.winfo_exists() or not self._inner_frame.winfo_exists():
                return
            # Sync only the inner frame subtree (cheap) instead of the whole canvas/window
            # idle queue, which would recursively reflow every widget in the application.
            try:
                self._inner_frame.update_idletasks()
            except Exception:
                pass
            has_overflow = self._inner_frame.winfo_reqwidth() > self._scroll_canvas.winfo_width()
            if not has_overflow:
                if self._scroll_canvas.xview()[0] > 0.001:
                    self._scroll_canvas.xview_moveto(0)
                else:
                    self._scroll_slider.set(0)
            else:
                left, right = self._scroll_canvas.xview()
                max_left = max(0.0, 1.0 - (right - left))
                self._scroll_slider.set(left / max_left if max_left else 0.0)
        except Exception:
            pass

    def _setup_mousewheel_scrolling(self) -> None:
        def _on_global_mousewheel(event):
            try:
                # Walk up parent tree to check if event started inside our toolbar
                curr = event.widget
                inside = False
                while curr:
                    if curr == self.frame:
                        inside = True
                        break
                    parent_path = curr.winfo_parent()
                    if not parent_path:
                        break
                    try:
                        curr = curr.nametowidget(parent_path)
                    except Exception:
                        break
                
                if inside:
                    # Scroll canvas horizontally
                    if event.delta:
                        self._scroll_canvas.xview_scroll(-1 * int(event.delta / 120), "units")
                    elif event.num == 4:
                        self._scroll_canvas.xview_scroll(-1, "units")
                    elif event.num == 5:
                        self._scroll_canvas.xview_scroll(1, "units")
            except Exception:
                pass

        try:
            self._parent.bind_all("<MouseWheel>", _on_global_mousewheel, add="+")
            self._parent.bind_all("<Button-4>", _on_global_mousewheel, add="+")
            self._parent.bind_all("<Button-5>", _on_global_mousewheel, add="+")
        except Exception:
            pass
