# toolbar.py
import os
import sys
import importlib.util
import tkinter as tk
from tkinter import Menu, Menubutton, ttk, messagebox
from PIL import Image, ImageTk

# Ensure this module's directory is first on sys.path so local imports resolve
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    if _THIS_DIR:
        if _THIS_DIR in sys.path:
            sys.path.remove(_THIS_DIR)
        sys.path.insert(0, _THIS_DIR)
except Exception:
    pass

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

from app_paths import AppPathManager
from furniture_selection_dialog import FurnitureSelectionDialog
from FurnitureHelper.Category import FURNITURE_CATEGORIES
from generate_layout.tab import GenerateLayoutTab
from room_toolbar_tab import create_room_tab

# Import new modular tabs
from draw_toolbar_tab import DrawToolbarTab
from edit_toolbar_tab import EditToolbarTab
from coor_toolbar_tab import CoordinateToolbarTab
from vastu_toolbar_tab import VastuToolbarTab


class TabScrollFactory:
    """Per-tab scroll container so left sidebar tabs can scroll when content overflows."""

    @staticmethod
    def wrap(tab_frame):
        scroll = ctk.CTkScrollableFrame(
            tab_frame,
            fg_color="transparent",
            scrollbar_button_color=COLORS.get("sidebar_border", "#334155"),
            scrollbar_button_hover_color=COLORS.get("primary", "#4F46E5"),
            corner_radius=0,
        )
        scroll.pack(fill="both", expand=True, padx=(0, 2), pady=(0, 6))
        return scroll


def create_furniture_tab(furniture_body, root, tools):
    """Create and populate the Furniture tab with categories and controls."""
    # 1. Info Help Card
    help_card = ctk.CTkFrame(
        furniture_body,
        fg_color=(COLORS.get("primary_light", "#6366F1"), "#312E81"),
        corner_radius=8,
        border_width=1,
        border_color=COLORS.get("primary", "#4F46E5"),
    )
    help_card.pack(fill="x", padx=10, pady=(5, 10))
    
    ctk.CTkLabel(
        help_card,
        text="🪑 Furniture / फर्नीचर के साधन",
        font=("Segoe UI", 12, "bold"),
        text_color="#FFFFFF",
        anchor="w",
        wraplength=180
    ).pack(fill="x", padx=10, pady=(6, 2))
    
    ctk.CTkLabel(
        help_card,
        text="• Click a category to select furniture.\n• Click on Canvas to place it.\n• 'R' rotates clockwise; Shift+'R' rotates anti-clockwise.\n• '0' resets the initial orientation; 'F'/'V' flip.\n• Select furniture and press 'Delete' to delete.",
        font=("Segoe UI", 10),
        text_color="#E2E8F0",
        justify="left",
        anchor="w",
        wraplength=180
    ).pack(fill="x", padx=10, pady=(0, 6))

    # Header label with modern styling
    ctk.CTkLabel(
        furniture_body,
        text="Furniture Categories",
        font=("Segoe UI", 16, "bold"),
        text_color=COLORS["text_primary"]
    ).pack(pady=(0, 15))

    # Create modern buttons for each category
    def make_open_dialog(cat, item_list):
        """Factory function to create dialog opener with proper closure."""
        return lambda: FurnitureSelectionDialog(
            root,
            cat,
            item_list,
            lambda name: tools.select_furniture_item(name)
        )
    
    # Modern category button colors
    button_colors = [
        (COLORS["primary"], COLORS["primary_hover"]),      # Subtle indigo
        (COLORS["secondary"], COLORS["secondary_hover"]),  # Muted emerald
        (COLORS["info"], "#2563EB"),                       # Muted blue
        (COLORS["accent"], COLORS["accent_hover"]),        # Muted purple
        (COLORS["warning"], "#D97706"),                    # Muted amber
    ]
    
    for idx, (category, items) in enumerate(FURNITURE_CATEGORIES.items()):
        color_set = button_colors[idx % len(button_colors)]
        
        category_button = ctk.CTkButton(
            furniture_body,
            text=f"📦 {category}",
            font=("Segoe UI", 13, "bold"),
            height=48,
            width=250,
            corner_radius=8,
            command=make_open_dialog(category, items),
            fg_color=color_set[0],
            hover_color=color_set[1],
            text_color=COLORS["text_white"]
        )
        category_button.pack(pady=6, padx=10, fill="x")
        if hasattr(tools, "create_tooltip"):
            tools.create_tooltip(category_button, f"Open selection dialog for {category} items.")

    # Visible edit/duplicate controls make the locked-item workflow discoverable.
    edit_btn = ctk.CTkButton(
        furniture_body, text="✥ Move / Edit Selected", command=tools.edit_selected_item,
        fg_color=COLORS["info"], hover_color="#2563EB", height=36,
        corner_radius=6, text_color=COLORS["text_white"],
    )
    edit_btn.pack(pady=4, padx=10, fill="x")
    if hasattr(tools, "create_tooltip"):
        tools.create_tooltip(edit_btn, "Items are locked after placement. Select one, click Edit, drag/resize, then press Enter to lock.")

    duplicate_btn = ctk.CTkButton(
        furniture_body, text="⧉ Duplicate Selected",
        command=lambda: tools.duplicate_furniture(tools.selected_furniture_obj),
        fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
        height=34, corner_radius=6, text_color=COLORS["text_white"],
    )
    duplicate_btn.pack(pady=4, padx=10, fill="x")

    size_row = ctk.CTkFrame(furniture_body, fg_color="transparent")
    size_row.pack(pady=4, padx=10, fill="x")
    for column in range(3):
        size_row.columnconfigure(column, weight=1)
    ctk.CTkButton(size_row, text="− Size", command=lambda: tools.resize_selected_furniture(0.9), height=30).grid(row=0, column=0, padx=(0, 2), sticky="ew")
    ctk.CTkButton(size_row, text="Exact", command=tools.set_selected_furniture_size, height=30).grid(row=0, column=1, padx=2, sticky="ew")
    ctk.CTkButton(size_row, text="+ Size", command=lambda: tools.resize_selected_furniture(1.1), height=30).grid(row=0, column=2, padx=(2, 0), sticky="ew")

    # Action buttons
    rotation_row = ctk.CTkFrame(furniture_body, fg_color="transparent")
    rotation_row.pack(pady=4, padx=10, fill="x")
    for column in range(2):
        rotation_row.columnconfigure(column, weight=1)
    clockwise_btn = ctk.CTkButton(
        rotation_row, text="↻ CW 15°",
        command=lambda: tools.rotate_selected_furniture(clockwise=True),
        fg_color=COLORS["text_secondary"], hover_color="#4B5563", height=34,
    )
    clockwise_btn.grid(row=0, column=0, padx=(0, 2), sticky="ew")
    counterclockwise_btn = ctk.CTkButton(
        rotation_row, text="↺ CCW 15°",
        command=tools.rotate_selected_furniture_counterclockwise,
        fg_color=COLORS["text_secondary"], hover_color="#4B5563", height=34,
    )
    counterclockwise_btn.grid(row=0, column=1, padx=(2, 0), sticky="ew")
    if hasattr(tools, "create_tooltip"):
        tools.create_tooltip(clockwise_btn, "Rotate clockwise 15° (R).")
        tools.create_tooltip(counterclockwise_btn, "Rotate anti-clockwise 15° (Shift+R).")

    reset_rotation_btn = ctk.CTkButton(
        furniture_body,
        text="↺ Reset to Initial Orientation",
        command=tools.reset_selected_furniture_rotation,
        fg_color=COLORS["text_secondary"],
        hover_color="#4B5563",
        height=34,
        corner_radius=6,
        text_color=COLORS["text_white"],
    )
    reset_rotation_btn.pack(pady=4, padx=10, fill="x")
    
    delete_btn = ctk.CTkButton(
        furniture_body, 
        text="🗑️ Delete Selected", 
        command=lambda: tools.delete_selected_furniture(),
        fg_color=COLORS["error"],
        hover_color="#DC2626",
        height=36,
        corner_radius=6,
        text_color=COLORS["text_white"]
    )
    delete_btn.pack(pady=4, padx=10, fill="x")
    if hasattr(tools, "create_tooltip"):
        tools.create_tooltip(delete_btn, "Delete selected furniture item from the canvas (Press 'Delete').")
    
    # === Furniture Controls Dropdown ===
    controls_frame = ctk.CTkFrame(
        furniture_body,
        fg_color=COLORS["surface"],
        border_color=COLORS["border"],
        border_width=1
    )
    controls_frame.pack(pady=(10, 5), padx=10, fill="x")
    
    controls_visible = {"state": False}
    
    def toggle_controls():
        if controls_visible["state"]:
            controls_content.pack_forget()
            controls_toggle.configure(text="▶ Controls (Keyboard Shortcuts)")
            controls_visible["state"] = False
        else:
            controls_content.pack(pady=(5, 0), fill="x")
            controls_toggle.configure(text="▼ Controls (Keyboard Shortcuts)")
            controls_visible["state"] = True
    
    controls_toggle = ctk.CTkButton(
        controls_frame,
        text="▶ Controls (Keyboard Shortcuts)",
        command=toggle_controls,
        fg_color="transparent",
        hover_color=(COLORS["border"], "#374151"),
        anchor="w",
        height=35,
        text_color=COLORS["text_secondary"]
    )
    controls_toggle.pack(fill="x", pady=2)
    
    controls_content = ctk.CTkFrame(
        controls_frame,
        fg_color="transparent"
    )
    
    ctk.CTkLabel(
        controls_content,
        text="Keyboard Controls:",
        font=("Segoe UI", 12, "bold"),
        text_color=COLORS["text_primary"]
    ).pack(pady=(5, 10))
    
    controls_list = [
        "↻ Clockwise 15° - Press 'R' key",
        "↺ Anti-clockwise 15° - Press 'Shift+R'",
        "⟲ Reset orientation - Press '0' key",
        "↔️ Flip Horizontal - Press 'F' key",
        "↕️ Flip Vertical - Press 'V' key",
        "🗑️ Delete - Press 'Delete' key"
    ]
    
    for control_text in controls_list:
        ctk.CTkLabel(
            controls_content,
            text=control_text,
            font=("Segoe UI", 11),
            anchor="w",
            text_color=COLORS["text_secondary"]
        ).pack(pady=2, padx=10, fill="x")
    
    ctk.CTkLabel(
        controls_content,
        text="Note: Select furniture first to use these controls",
        font=("Segoe UI", 10),
        text_color=COLORS["text_secondary"]
    ).pack(pady=(10, 5))


def setup_toolbar(root, model, tools, controller, view, actions,
                  fb=None,
                  on_local_save=None,
                  on_local_load_last=None,
                  on_local_load_file=None,
                  on_cloud_upload=None,
                  on_cloud_download=None):
    """Creates a tabbed toolbar on the left with drawing, editing, and view tools."""
    sidebar_width = 288
    min_sidebar_width = 248
    min_canvas_width = 380
    collapse_threshold = 140
    splitter_width = 8
    is_collapsed = False
    last_expanded_width = sidebar_width

    main_frame = ctk.CTkFrame(
        root,
        width=sidebar_width,
        fg_color=COLORS.get("surface_dark", "#0B1220"),
        border_width=0,
        corner_radius=0,
    )
    main_frame.pack(side="left", fill="y")
    main_frame.pack_propagate(False)

    divider_color = COLORS.get("canvas_chrome", "#17243A")
    splitter = tk.Frame(
        root,
        width=splitter_width,
        bg=divider_color,
        bd=0,
        highlightthickness=0,
    )
    splitter.pack(side="left", fill="y")
    splitter.pack_propagate(False)

    def _clamp_sidebar_width(width):
        available_width = root.winfo_width() - min_canvas_width - splitter_width - 10
        max_width = max(min_sidebar_width, available_width)
        return max(min_sidebar_width, min(int(width), max_width))

    def _apply_sidebar_width(width=None, remember=False):
        nonlocal last_expanded_width
        if width is not None and remember:
            last_expanded_width = max(min_sidebar_width, int(width))
        if not is_collapsed:
            main_frame.configure(width=_clamp_sidebar_width(last_expanded_width))

    def _set_sidebar_collapsed(collapsed, width=None):
        nonlocal is_collapsed
        if controller and callable(getattr(controller, "set_sidebar_collapsed", None)):
            controller.set_sidebar_collapsed(bool(collapsed))
        if collapsed:
            if not is_collapsed:
                main_frame.pack_forget()
                is_collapsed = True
            collapse_btn.configure(text="›")
            return

        if is_collapsed:
            main_frame.pack(
                side="left",
                fill="y",
                before=splitter,
            )
            is_collapsed = False
        collapse_btn.configure(text="‹")
        _apply_sidebar_width(width, remember=width is not None)

    collapse_btn = ctk.CTkButton(
        splitter,
        text="‹",
        command=lambda: _set_sidebar_collapsed(not is_collapsed),
        width=26,
        height=36,
        corner_radius=8,
        font=("Segoe UI", 18, "bold"),
        fg_color=COLORS.get("surface_raised", "#FFFFFF"),
        hover_color=COLORS.get("primary", "#4F46E5"),
        text_color=COLORS.get("text_primary", "#0F172A"),
        border_width=1,
        border_color=COLORS.get("border_strong", "#CBD5E1"),
    )
    # Collapse control lives in the top navbar; this strip remains the resize target.

    drag_handle = tk.Frame(
        splitter,
        width=splitter_width,
        cursor="sb_h_double_arrow",
        bg=divider_color,
        bd=0,
        highlightthickness=0,
    )
    drag_handle.pack(side="top", fill="both", expand=True)
    drag_marker = tk.Label(
        drag_handle,
        text="⋮",
        cursor="sb_h_double_arrow",
        bg=divider_color,
        fg=COLORS.get("text_light", "#94A3B8"),
        font=("Segoe UI", 16, "bold"),
    )
    drag_marker.place(relx=0.5, rely=0.5, anchor="center")
    drag_state = {"start_x": 0, "start_width": sidebar_width}

    def _start_sidebar_drag(event):
        drag_state["start_x"] = event.x_root
        drag_state["start_width"] = 0 if is_collapsed else main_frame.winfo_width()
        # Keep motion on the splitter after the pointer crosses a populated canvas.
        try:
            drag_handle.grab_set()
        except tk.TclError:
            pass

    def _drag_sidebar(event):
        target_width = drag_state["start_width"] + event.x_root - drag_state["start_x"]
        # An expanded pane cannot become narrower than min_sidebar_width, so collapse
        # at that same boundary instead of leaving a visually dead drag zone.
        collapse_limit = collapse_threshold if is_collapsed else min_sidebar_width
        if target_width <= collapse_limit:
            _set_sidebar_collapsed(True)
        else:
            _set_sidebar_collapsed(False, target_width)

    def _finish_sidebar_drag(_event):
        try:
            if drag_handle.grab_current() == drag_handle:
                drag_handle.grab_release()
        except tk.TclError:
            pass

    for drag_widget in (splitter, drag_handle, drag_marker):
        drag_widget.bind("<ButtonPress-1>", _start_sidebar_drag)
        drag_widget.bind("<B1-Motion>", _drag_sidebar)
        drag_widget.bind("<ButtonRelease-1>", _finish_sidebar_drag)

    def _update_sidebar_for_window(_event=None):
        _apply_sidebar_width()

    root.bind("<Configure>", _update_sidebar_for_window, add="+")
    root.after_idle(_apply_sidebar_width)

    try:
        style = ttk.Style()
        style.configure("TNotebook.Tab", padding=(14, 8))
        for notebook_style in ("TNotebook", "Vastu.TNotebook"):
            style.configure(
                notebook_style,
                background=COLORS.get("surface_raised", "#111C2F"),
                borderwidth=0,
                relief="flat",
            )
        # Windows themes paint Notebook.client as a bright native rectangle.
        style.layout("Vastu.TNotebook", [])
    except Exception:
        pass

    def _update_tab_style(_event=None):
        try:
            total_width = root.winfo_width()
            style = ttk.Style()
            if total_width and total_width < 900:
                style.configure("TNotebook.Tab", padding=(8, 6), font=("Segoe UI", 9))
            else:
                style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI", 10))
        except Exception:
            pass

    _update_tab_style()
    root.bind("<Configure>", _update_tab_style, add="+")

    panel_shell = ctk.CTkFrame(
        main_frame,
        bg_color=COLORS.get("surface_dark", "#0B1220"),
        fg_color=COLORS.get("border_dark", "#334155"),
        border_width=0,
        corner_radius=20,
    )
    panel_content = ctk.CTkFrame(
        panel_shell,
        bg_color=COLORS.get("border_dark", "#334155"),
        fg_color=COLORS.get("surface_raised", "#111C2F"),
        border_width=0,
        corner_radius=18,
    )
    notebook = ttk.Notebook(panel_content, style="Vastu.TNotebook")

    # === Define Tabs ===
    tab_surface = COLORS.get("sidebar", "#0F172A")
    tab_background = COLORS.get("surface_raised", "#111C2F")
    draw_tab = ctk.CTkFrame(notebook, bg_color=tab_background, fg_color=tab_surface, corner_radius=0)
    edit_tab = ctk.CTkFrame(notebook, bg_color=tab_background, fg_color=tab_surface, corner_radius=0)
    room_tab = ctk.CTkFrame(notebook, bg_color=tab_background, fg_color=tab_surface, corner_radius=0)
    furniture_tab = ctk.CTkFrame(notebook, bg_color=tab_background, fg_color=tab_surface, corner_radius=0)
    coor_tab = ctk.CTkFrame(notebook, bg_color=tab_background, fg_color=tab_surface, corner_radius=0)
    vaastu_tab = ctk.CTkFrame(notebook, bg_color=tab_background, fg_color=tab_surface, corner_radius=0)
    gen_layout_tab = ctk.CTkFrame(notebook, bg_color=tab_background, fg_color=tab_surface, corner_radius=0)
    trace_tab = ctk.CTkFrame(notebook, bg_color=tab_background, fg_color=tab_surface, corner_radius=0)

    # Add tabs to notebook
    notebook.add(draw_tab, text="Draw")
    notebook.add(edit_tab, text="Edit")
    notebook.add(room_tab, text="Room")
    notebook.add(furniture_tab, text="Furniture")
    notebook.add(coor_tab, text="Coordinates")
    notebook.add(vaastu_tab, text="Vastu")
    notebook.add(gen_layout_tab, text="Generate Layout")
    notebook.add(trace_tab, text="Image Tracing")

    tab_names = ["Draw", "Edit", "Room", "Furniture", "Coordinates", "Vastu", "Generate Layout", "Image Tracing"]
    tab_map = {
        "Draw": draw_tab,
        "Edit": edit_tab,
        "Room": room_tab,
        "Furniture": furniture_tab,
        "Coordinates": coor_tab,
        "Vastu": vaastu_tab,
        "Generate Layout": gen_layout_tab,
        "Image Tracing": trace_tab,
    }

    current_tab_var = tk.StringVar(value="Generate Layout")

    sidebar_header = ctk.CTkFrame(
        main_frame,
        height=48,
        fg_color=COLORS.get("surface_raised", "#20252B"),
        corner_radius=0,
    )
    # The active section title is shown in the top navbar.
    sidebar_header.pack_propagate(False)
    ctk.CTkLabel(
        sidebar_header,
        textvariable=current_tab_var,
        font=("Segoe UI", 13, "bold"),
        text_color=COLORS.get("sidebar_text", "#EEF2F5"),
        anchor="w",
    ).pack(fill="both", expand=True, padx=12)

    # A fixed navigation rail leaves the remaining width for contextual controls.
    tab_selector_frame = ctk.CTkFrame(
        main_frame,
        width=64,
        fg_color=COLORS.get("sidebar", "#1E2329"),
        corner_radius=0,
        border_width=0,
    )
    tab_selector_frame.pack(side="left", fill="y")
    tab_selector_frame.pack_propagate(False)

    tab_display_names = {
        "Draw": "╱\nDraw",
        "Edit": "✥\nEdit",
        "Room": "□\nRoom",
        "Furniture": "▣\nFurn.",
        "Coordinates": "⌖\nCoords",
        "Vastu": "✦\nVastu",
        "Generate Layout": "▦\nLayout",
        "Image Tracing": "▧\nTrace",
    }

    tab_buttons = {}

    def _switch_tab(tab_name: str):
        tab = tab_map.get(tab_name)
        if tab is not None:
            _set_sidebar_collapsed(False)
            notebook.select(tab)
            current_tab_var.set(tab_name)
            if controller and callable(getattr(controller, "set_toolbar_title", None)):
                controller.set_toolbar_title(tab_name)
            _update_tab_button_styles()
            try:
                notebook.focus_set()
            except Exception:
                pass

    def _update_tab_button_styles():
        current_active = current_tab_var.get()
        for name, btn in tab_buttons.items():
            if name == current_active:
                btn.configure(
                    fg_color=COLORS.get("sidebar_active", "#203D3A"),
                    text_color=COLORS.get("primary", "#55D6C2"),
                    hover_color=COLORS.get("sidebar_active", "#203D3A"),
                    border_width=0,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS.get("sidebar_muted", "#8E98A4"),
                    hover_color=COLORS.get("sidebar_hover", "#292F36"),
                    border_width=0,
                )

    for tab_name in tab_names:
        btn = ctk.CTkButton(
            tab_selector_frame,
            text=tab_display_names.get(tab_name, tab_name),
            command=lambda name=tab_name: _switch_tab(name),
            width=56,
            height=48,
            corner_radius=8,
            font=("Segoe UI", 9, "bold"),
            fg_color="transparent",
            text_color=COLORS.get("sidebar_muted", "#8E98A4"),
            hover_color=COLORS.get("sidebar_hover", "#292F36"),
            border_spacing=3,
        )
        btn.pack(side="top", padx=4, pady=2)
        tab_buttons[tab_name] = btn

    def _on_notebook_change(event=None):
        try:
            selected = notebook.index(notebook.select())
            tab_name = tab_names[selected] if selected < len(tab_names) else "Draw"
            current_tab_var.set(tab_name)
            _update_tab_button_styles()
        except Exception:
            pass
            
    notebook.bind("<<NotebookTabChanged>>", _on_notebook_change)
    _switch_tab("Generate Layout")

    panel_shell.pack(side="left", fill="both", expand=True, padx=(8, 6), pady=8)
    # Two filled rounded layers avoid the pointed antialias join produced by a
    # stroked CTk border while preserving a uniform 2 px floating outline.
    panel_content.pack(fill="both", expand=True, padx=2, pady=2)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    try:
        style.layout("TNotebook.Tab", [])
        notebook.configure(style="Vastu.TNotebook")
    except Exception:
        pass

    draw_body = TabScrollFactory.wrap(draw_tab)
    edit_body = TabScrollFactory.wrap(edit_tab)
    room_body = TabScrollFactory.wrap(room_tab)
    furniture_body = TabScrollFactory.wrap(furniture_tab)
    coor_body = TabScrollFactory.wrap(coor_tab)
    vaastu_body = TabScrollFactory.wrap(vaastu_tab)
    gen_layout_body = TabScrollFactory.wrap(gen_layout_tab)
    trace_body = TabScrollFactory.wrap(trace_tab)

    # Build Draw tab
    DrawToolbarTab(model=model, tools=tools, view=view).build(draw_body)

    # Build Edit tab
    EditToolbarTab(
        root=root,
        model=model,
        tools=tools,
        view=view,
        actions=actions,
        on_local_save=on_local_save,
        on_local_load_last=on_local_load_last,
        on_local_load_file=on_local_load_file,
        on_cloud_upload=on_cloud_upload,
        on_cloud_download=on_cloud_download
    ).build(edit_body)

    # Build Room tab
    create_room_tab(room_body, model, tools, view, actions)

    # Build Furniture tab
    create_furniture_tab(furniture_body, root, tools)

    # Build Coordinates tab
    CoordinateToolbarTab(tools=tools).build(coor_body)

    # Build Vastu tab
    VastuToolbarTab(root=root, tools=tools).build(vaastu_body)

    # Build Generate Layout tab
    GenerateLayoutTab(model=model, tools=tools, view=view, actions=actions).build(gen_layout_body)
    
    # Initialize Tracing Image UI
    if getattr(tools, "trace_manager", None):
        try:
            tools.trace_manager.build_ui(trace_body)
        except Exception as e:
            print(f"[TraceImageManager] UI construction failed: {e}")

    if controller:
        controller.switch_tab = _switch_tab
        controller.toggle_sidebar = lambda: _set_sidebar_collapsed(not is_collapsed)

    # ttkbootstrap can recolor legacy Tk widgets while tab builders initialize.
    # Reapply the divider last so it cannot become a bright native strip.
    splitter.configure(bg=divider_color)
    drag_handle.configure(bg=divider_color)
    drag_marker.configure(bg=divider_color)

    return main_frame, {
        "draw": draw_tab,
        "edit": edit_tab,
        "view": room_tab,
        "furniture": furniture_tab,
        "coordinate": coor_tab,
        "vastu": vaastu_tab,
        "generate_layout": gen_layout_tab,
        "image_tracing": trace_tab,
    }
