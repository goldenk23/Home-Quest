import tkinter as tk
from tkinter import ttk
import os
import sys
import importlib.util
import re

# Resolve dependencies
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from Helper.ctk_global import ctk
except ImportError:
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
except ImportError:
    _helper_dir = os.path.join(_THIS_DIR, "Helper")
    _color_path = os.path.join(_helper_dir, "color_scheme.py")
    _spec = importlib.util.spec_from_file_location("mini_autocad_color_scheme", _color_path)
    if _spec and _spec.loader:
        _module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        COLORS = getattr(_module, "COLORS", {})
    else:
        COLORS = {}

def create_room_tab(room_body, model, tools, view, actions):
    """
    Create and populate the Room tab (unit, grid, room templates, compass).
    Extracted from toolbar.py to improve modularity and fix unit synchronization bugs.
    """
    # 1. Info Help Card
    help_card = ctk.CTkFrame(
        room_body,
        fg_color=(COLORS.get("primary_light", "#6366F1"), "#312E81"),
        corner_radius=8,
        border_width=1,
        border_color=COLORS.get("primary", "#4F46E5"),
    )
    help_card.pack(fill="x", padx=10, pady=(5, 10))
    
    ctk.CTkLabel(
        help_card,
        text="🏠 Room Tools / कमरा (रूम टेम्पलेट्स)",
        font=("Segoe UI", 12, "bold"),
        text_color="#FFFFFF",
        anchor="w",
        wraplength=180
    ).pack(fill="x", padx=10, pady=(6, 2))
    
    ctk.CTkLabel(
        help_card,
        text="• Set your preferred unit scale first.\n• Enter Room Name, Length, & Breadth.\n• Click 'Create Room' and add balconies.\n• Draw compass to indicate North.",
        font=("Segoe UI", 10),
        text_color="#E2E8F0",
        justify="left",
        anchor="w",
        wraplength=180
    ).pack(fill="x", padx=10, pady=(0, 6))

    # Header with modern styling
    ctk.CTkLabel(
        room_body,
        text="Room Tools",
        font=("Segoe UI", 16, "bold"),
        text_color=COLORS.get("text_primary", "#0F172A")
    ).pack(pady=(10, 4))

    ctk.CTkLabel(
        room_body,
        text="Set units, create rooms and add balconies or compass.",
        font=("Segoe UI", 11),
        text_color=COLORS.get("text_secondary", "#475569"),
        wraplength=180,
        anchor="w",
        justify="left",
    ).pack(fill="x", padx=8, pady=(0, 10))

    # === Unit & Grid section ===
    unit_group = ctk.CTkFrame(
        room_body,
        fg_color=COLORS.get("surface", "#f0f0f0"),
        border_color=COLORS.get("border", "#cccccc"),
        border_width=1
    )
    unit_group.pack(fill="x", padx=8, pady=(0, 8))

    ctk.CTkLabel(
        unit_group,
        text="Units & Grid",
        font=("Arial", 12, "bold"),
        anchor="w",
        text_color=COLORS.get("text_primary", "black")
    ).pack(fill="x", padx=8, pady=(6, 2))

    unit_row = ctk.CTkFrame(unit_group, fg_color="transparent")
    unit_row.pack(fill="x", padx=8, pady=(0, 4))

    ctk.CTkLabel(
        unit_row, 
        text="Unit:", 
        width=40, 
        anchor="w",
        text_color=COLORS.get("text_secondary", "#666666")
    ).pack(side="left")
    
    unit_var = ctk.StringVar(value=model.unit)

    def update_placeholders(unit):
        """Update entry placeholders to show the current unit suffix."""
        suffix = unit
        if hasattr(tools, "room_widgets"):
            widgets = tools.room_widgets
            if "length" in widgets:
                widgets["length"].configure(placeholder_text=f"Length ({suffix})")
            if "breadth" in widgets:
                widgets["breadth"].configure(placeholder_text=f"Breadth ({suffix})")
            if "balcony_depth" in widgets:
                widgets["balcony_depth"].configure(placeholder_text=f"Balcony Depth ({suffix})")

    def on_unit_change(selected_unit):
        model.set_unit(selected_unit)
        view.draw_grid()
        update_placeholders(selected_unit)

    unit_menu = ctk.CTkOptionMenu(
        unit_row,
        values=list(model.unit_scale.keys()),
        variable=unit_var,
        command=on_unit_change,
        width=120,
        fg_color=COLORS.get("primary", "#3b82f6"),
        button_color=COLORS.get("primary_hover", "#2563eb"),
        button_hover_color=COLORS.get("primary", "#3b82f6"),
        text_color=COLORS.get("text_white", "white")
    )
    unit_menu.pack(side="left", padx=(4, 0))

    def _sync_unit_selection():
        """Background loop to keep the unit dropdown and placeholders in sync with global model changes."""
        try:
            current_model_unit = getattr(model, "unit", "ft")
            if unit_var.get() != current_model_unit:
                unit_var.set(current_model_unit)
                update_placeholders(current_model_unit)
            room_body.after(500, _sync_unit_selection)
        except Exception:
            pass

    # Start the sync loop
    room_body.after(500, _sync_unit_selection)

    def on_toggle_grid():
        view.toggle_grid()
        try:
            actions.log({"type": "grid_toggle"})
        except Exception:
            pass

    ctk.CTkButton(
        unit_group,
        text="🔲 Toggle Grid",
        command=on_toggle_grid,
        fg_color=COLORS.get("secondary", "#10b981"),
        hover_color=COLORS.get("secondary_hover", "#059669"),
        height=32,
        corner_radius=6,
        text_color=COLORS.get("text_white", "white")
    ).pack(fill="x", padx=8, pady=(6, 4))


    # === Room creation section ===
    room_group = ctk.CTkFrame(
        room_body,
        fg_color=COLORS.get("surface", "#f0f0f0"),
        border_color=COLORS.get("border", "#cccccc"),
        border_width=1
    )
    room_group.pack(fill="x", padx=8, pady=(0, 8))

    ctk.CTkLabel(
        room_group,
        text="Add New Room",
        font=("Arial", 12, "bold"),
        anchor="w",
        text_color=COLORS.get("text_primary", "black")
    ).pack(fill="x", padx=8, pady=(6, 2))

    def _select_all_on_focus(entry_widget):
        def _handler(event):
            try:
                if entry_widget.winfo_exists():
                    entry_widget.select_range(0, tk.END)
                    entry_widget.icursor(tk.END)
            except (tk.TclError, AttributeError):
                pass
        return _handler

    room_name_entry = ctk.CTkEntry(
        room_group,
        placeholder_text="Room Name (e.g., Bedroom)",
        border_color=COLORS.get("border", "#cccccc"),
        fg_color="white",
        text_color=COLORS.get("text_primary", "black")
    )
    room_name_entry.pack(fill="x", padx=8, pady=2)
    room_name_entry.bind("<FocusIn>", _select_all_on_focus(room_name_entry))

    room_length_entry = ctk.CTkEntry(
        room_group,
        placeholder_text=f"Length ({model.unit})",
        border_color=COLORS.get("border", "#cccccc"),
        fg_color="white",
        text_color=COLORS.get("text_primary", "black")
    )
    room_length_entry.pack(fill="x", padx=8, pady=2)
    room_length_entry.bind("<FocusIn>", _select_all_on_focus(room_length_entry))

    room_breadth_entry = ctk.CTkEntry(
        room_group,
        placeholder_text=f"Breadth ({model.unit})",
        border_color=COLORS.get("border", "#cccccc"),
        fg_color="white",
        text_color=COLORS.get("text_primary", "black")
    )
    room_breadth_entry.pack(fill="x", padx=8, pady=2)
    room_breadth_entry.bind("<FocusIn>", _select_all_on_focus(room_breadth_entry))

    # Balcony controls
    balcony_row = ctk.CTkFrame(room_group, fg_color="transparent")
    balcony_row.pack(fill="x", padx=8, pady=(6, 2))

    ctk.CTkLabel(
        balcony_row, 
        text="Curved Balcony:", 
        anchor="w",
        text_color=COLORS.get("text_secondary", "#666666"),
        width=100
    ).pack(side="left")
    
    balcony_side_combo = ctk.CTkComboBox(
        balcony_row,
        values=["None", "Left", "Right", "Both"],
        state="readonly",
        fg_color=COLORS.get("surface", "#f0f0f0"),
        border_color=COLORS.get("border", "#cccccc"),
        button_color=COLORS.get("primary", "#3b82f6"),
        button_hover_color=COLORS.get("primary_hover", "#2563eb"),
        text_color=COLORS.get("text_primary", "black")
    )
    balcony_side_combo.set("None")
    balcony_side_combo.pack(side="left", fill="x", expand=True)

    balcony_depth_entry = ctk.CTkEntry(
        room_group,
        placeholder_text=f"Balcony Depth ({model.unit})",
        border_color=COLORS.get("border", "#cccccc"),
        fg_color="white",
        text_color=COLORS.get("text_primary", "black")
    )
    balcony_depth_entry.pack(fill="x", padx=8, pady=(2, 6))
    balcony_depth_entry.bind("<FocusIn>", _select_all_on_focus(balcony_depth_entry))

    # Register widgets in tools for remote access (editing)
    tools.room_widgets = {
        "name": room_name_entry,
        "length": room_length_entry,
        "breadth": room_breadth_entry,
        "balcony_side": balcony_side_combo,
        "balcony_depth": balcony_depth_entry
    }

    def create_room_with_balcony():
        from Helper.showMessage import show_message

        name_raw = room_name_entry.get().strip()
        length_raw = room_length_entry.get().strip()
        breadth_raw = room_breadth_entry.get().strip()

        if not name_raw:
            show_message("error", "Room Validation", "Room name is required.")
            return
        if not length_raw or not breadth_raw:
            show_message("error", "Room Validation", "Length and Breadth are required.")
            return

        try:
            length = float(length_raw)
            breadth = float(breadth_raw)
        except ValueError:
            show_message("error", "Room Validation", "Length and Breadth must be valid numbers.")
            return

        if length <= 0 or breadth <= 0:
            show_message("error", "Room Validation", "Length and Breadth must be greater than 0.")
            return

        room = tools.insert_room_template(name_raw, length, breadth)

        if room is None:
            return

        side = balcony_side_combo.get()
        balcony_depth_str = balcony_depth_entry.get().strip()

        if side == "None" and balcony_depth_str:
            show_message(
                "error",
                "Balcony Validation",
                "Balcony depth entered but Curved Balcony is set to None. Please choose a side."
            )
            return

        if side != "None" and balcony_depth_str:
            try:
                balcony_depth = float(balcony_depth_str)
                if balcony_depth > 0:
                    room_coords = tools.canvas.coords(room.rect_id)
                    if len(room_coords) >= 4:
                        rx1, ry1, rx2, ry2 = room_coords[0], room_coords[1], room_coords[2], room_coords[3]
                    else:
                        rx1, ry1, rx2, ry2 = room.x0, room.y0, room.x1, room.y1

                    unit_factor = tools.model.unit_scale.get(tools.model.unit, 1.0)
                    px_per_unit = tools.model.grid_spacing * tools.model.zoom_level / unit_factor
                    
                    radius = balcony_depth * px_per_unit
                    group_tag = room.group_tag

                    if side in ("Left", "Both"):
                        balcony_left = tools.canvas.create_arc(
                            rx1 - radius, ry1, rx1 + radius, ry2,
                            start=90, extent=180, style="arc", width=2, outline="black",
                            tags=("balcony", group_tag),
                        )
                        tools.canvas.tag_raise(balcony_left)

                    if side in ("Right", "Both"):
                        balcony_right = tools.canvas.create_arc(
                            rx2 - radius, ry1, rx2 + radius, ry2,
                            start=270, extent=180, style="arc", width=2, outline="black",
                            tags=("balcony", group_tag),
                        )
                        tools.canvas.tag_raise(balcony_right)

                    print(f"✅ Balcony created with depth {balcony_depth}{tools.model.unit} on {side} side")
            except ValueError:
                print("⚠️ Please enter a valid number for balcony depth.")

    create_room_btn = ctk.CTkButton(
        room_group,
        text="🏠 Create Room",
        command=create_room_with_balcony,
        fg_color=COLORS.get("primary", "#3b82f6"),
        hover_color=COLORS.get("primary_hover", "#2563eb"),
        height=36,
        corner_radius=6,
        text_color=COLORS.get("text_white", "white")
    )
    create_room_btn.pack(fill="x", padx=8, pady=(6, 4))
    tools.room_widgets["create_btn"] = create_room_btn

    update_room_btn = ctk.CTkButton(
        room_group,
        text="🔄 Update Room",
        command=lambda: tools.update_currently_editing_room(),
        fg_color=COLORS.get("secondary", "#10b981"),
        hover_color=COLORS.get("secondary_hover", "#059669"),
        height=36,
        corner_radius=6,
        text_color=COLORS.get("text_white", "white")
    )
    tools.room_widgets["update_btn"] = update_room_btn

    cancel_edit_btn = ctk.CTkButton(
        room_group,
        text="❌ Cancel Edit",
        command=lambda: tools.cancel_room_edit(),
        fg_color=COLORS.get("error", "#ef4444"),
        hover_color="#DC2626",
        height=32,
        corner_radius=6,
        text_color=COLORS.get("text_white", "white")
    )
    tools.room_widgets["cancel_btn"] = cancel_edit_btn

    # === Compass section ===
    compass_group = ctk.CTkFrame(
        room_body,
        fg_color=COLORS.get("surface", "#f0f0f0"),
        border_color=COLORS.get("border", "#cccccc"),
        border_width=1
    )
    compass_group.pack(fill="x", padx=8, pady=(4, 8))

    ctk.CTkLabel(
        compass_group,
        text="Compass Direction",
        font=("Segoe UI", 12, "bold"),
        anchor="w",
        text_color=COLORS.get("text_primary", "black")
    ).pack(fill="x", padx=8, pady=(6, 2))

    # Row 1: Direction dropdown
    dir_row = ctk.CTkFrame(compass_group, fg_color="transparent")
    dir_row.pack(fill="x", padx=8, pady=2)
    
    ctk.CTkLabel(
        dir_row,
        text="Direction:",
        font=("Segoe UI", 11),
        text_color=COLORS.get("text_secondary", "#666666"),
        width=80,
        anchor="w"
    ).pack(side="left")

    compass_combo = ctk.CTkComboBox(
        dir_row,
        values=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
        state="readonly",
        fg_color=COLORS.get("surface", "#f0f0f0"),
        border_color=COLORS.get("border", "#cccccc"),
        button_color=COLORS.get("secondary", "#10b981"),
        button_hover_color=COLORS.get("secondary_hover", "#059669"),
        text_color=COLORS.get("text_primary", "black"),
        height=28
    )
    initial_direction = getattr(tools, "current_compass_direction", "N") or "N"
    compass_combo.set(initial_direction)
    compass_combo.pack(side="left", fill="x", expand=True)
    tools.compass_combo_widget = compass_combo

    # Row 2: Custom Angle
    angle_row = ctk.CTkFrame(compass_group, fg_color="transparent")
    angle_row.pack(fill="x", padx=8, pady=2)
    
    ctk.CTkLabel(
        angle_row,
        text="or Angle (°):",
        font=("Segoe UI", 11),
        text_color=COLORS.get("text_secondary", "#666666"),
        width=80,
        anchor="w"
    ).pack(side="left")

    compass_angle_entry = ctk.CTkEntry(
        angle_row,
        placeholder_text="Angle (0-360°)",
        fg_color="white",
        border_color=COLORS.get("border", "#cccccc"),
        text_color=COLORS.get("text_primary", "black"),
        height=28
    )
    compass_angle_entry.pack(side="left", fill="x", expand=True)

    def set_compass():
        angle_text = compass_angle_entry.get().strip()
        if angle_text:
            try:
                angle_val = float(angle_text) % 360.0
                tools.draw_compass(direction="", angle=angle_val)
            except ValueError:
                direction = compass_combo.get()
                tools.draw_compass(direction)
        else:
            direction = compass_combo.get()
            tools.draw_compass(direction)

    # Row 3: Action Button
    set_compass_btn = ctk.CTkButton(
        compass_group,
        text="🧭 Set Compass",
        command=set_compass,
        fg_color=COLORS.get("secondary", "#10b981"),
        hover_color=COLORS.get("secondary_hover", "#059669"),
        height=32,
        corner_radius=6,
        text_color=COLORS.get("text_white", "white")
    )
    set_compass_btn.pack(fill="x", padx=8, pady=(4, 8))
    if hasattr(tools, "create_tooltip"):
        tools.create_tooltip(set_compass_btn, "Draw directional compass overlay on the canvas / दिशा कम्पास ड्रा करें")
