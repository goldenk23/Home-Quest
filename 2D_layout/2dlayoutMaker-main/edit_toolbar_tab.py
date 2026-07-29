# edit_toolbar_tab.py
import tkinter as tk
from tkinter import messagebox
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

from layout_serializer import LayoutSerializer
from local_autosave import try_load_json
from app_paths import AppPathManager

LOCAL_AUTOSAVE_PATH = AppPathManager.get_autosave_file()


class EditToolbarTab:
    """Class representing the Edit & Save sidebar tab."""

    def __init__(self, root, model, tools, view, actions, on_local_save=None,
                 on_local_load_last=None, on_local_load_file=None,
                 on_cloud_upload=None, on_cloud_download=None) -> None:
        self.root = root
        self.model = model
        self.tools = tools
        self.view = view
        self.actions = actions
        self.on_local_save = on_local_save
        self.on_local_load_last = on_local_load_last
        self.on_local_load_file = on_local_load_file

    def build(self, edit_body) -> None:
        # 1. Info Help Card
        help_card = ctk.CTkFrame(
            edit_body,
            fg_color=(COLORS.get("primary_light", "#6366F1"), "#312E81"),
            corner_radius=8,
            border_width=1,
            border_color=COLORS.get("primary", "#4F46E5"),
        )
        help_card.pack(fill="x", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(
            help_card,
            text="⚙️ Edit & Save / बदलाव और सेव",
            font=("Segoe UI", 12, "bold"),
            text_color="#FFFFFF",
            anchor="w",
            wraplength=180
        ).pack(fill="x", padx=10, pady=(6, 2))
        
        ctk.CTkLabel(
            help_card,
            text="• Use Undo/Redo to fix mistakes.\n• Save as JSON/YAML to reload your work later.\n• Export layout as a PNG/Image or Clear Canvas.",
            font=("Segoe UI", 10),
            text_color="#E2E8F0",
            justify="left",
            anchor="w",
            wraplength=180
        ).pack(fill="x", padx=10, pady=(0, 6))

        # 2. Header
        ctk.CTkLabel(
            edit_body,
            text="Edit & Save",
            font=("Segoe UI", 18, "bold"),
            anchor="w",
            wraplength=180,
            text_color=COLORS["text_primary"]
        ).pack(fill="x", pady=(0, 4), padx=8)

        ctk.CTkLabel(
            edit_body,
            text="Common editing tools and layout saving options.",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            anchor="w",
            wraplength=180,
        ).pack(fill="x", pady=(0, 8), padx=8)

        # === Quick actions (Undo / Redo) ===
        quick_group = ctk.CTkFrame(
            edit_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        quick_group.pack(fill="x", pady=(4, 8), padx=8)

        ctk.CTkLabel(
            quick_group,
            text="Quick Actions",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            text_color=COLORS["text_primary"]
        ).pack(fill="x", pady=(6, 4), padx=8)

        quick_buttons = ctk.CTkFrame(quick_group, fg_color="transparent")
        quick_buttons.pack(fill="x", pady=(0, 8), padx=6)

        # Make two evenly-spaced buttons in a row
        for i in range(2):
            quick_buttons.columnconfigure(i, weight=1)

        undo_btn = ctk.CTkButton(
            quick_buttons,
            text="⟲ Undo",
            command=lambda: self.actions.undo(self.view.canvas),
            height=32,
            corner_radius=6,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_white"]
        )
        undo_btn.grid(row=0, column=0, sticky="ew", padx=4)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(undo_btn, "Undo the last action (Ctrl+Z)")

        redo_btn = ctk.CTkButton(
            quick_buttons,
            text="⟳ Redo",
            command=lambda: self.actions.redo(self.view.canvas),
            height=32,
            corner_radius=6,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["text_white"]
        )
        redo_btn.grid(row=0, column=1, sticky="ew", padx=4)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(redo_btn, "Redo the undone action (Ctrl+Y)")

        edit_selected_btn = ctk.CTkButton(
            quick_buttons, text="✥ Move / Edit Selected", command=self.tools.edit_selected_item,
            height=32, fg_color=COLORS["info"], hover_color="#2563EB",
            text_color=COLORS["text_white"],
        )
        edit_selected_btn.grid(row=1, column=0, sticky="ew", padx=4, pady=(6, 0))
        delete_selected_btn = ctk.CTkButton(
            quick_buttons, text="🗑 Delete Selected", command=self.tools.delete_selected_furniture,
            height=32, fg_color=COLORS["error"], hover_color="#DC2626",
            text_color=COLORS["text_white"],
        )
        delete_selected_btn.grid(row=1, column=1, sticky="ew", padx=4, pady=(6, 0))
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(delete_selected_btn, "Delete selected furniture/window (Delete key also works).")

        # === Erase tools row (single / multiple) ===
        erase_group = ctk.CTkFrame(
            edit_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        erase_group.pack(fill="x", pady=(0, 8), padx=8)

        ctk.CTkLabel(
            erase_group,
            text="Erase Walls",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            text_color=COLORS["text_primary"]
        ).pack(fill="x", pady=(2, 4), padx=8)

        point_erase_btn = ctk.CTkButton(
            erase_group,
            text="✏️ Erase Part (2 Points)",
            command=lambda: self.tools.enable_eraser_mode(),
            height=32,
            corner_radius=6,
            fg_color=COLORS["warning"],
            hover_color="#D97706",
            text_color=COLORS["text_white"],
            state="disabled",
        )
        point_erase_btn.pack(fill="x", pady=(0, 4), padx=8)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(point_erase_btn, "Erase a wall segment by clicking two points.")

        multi_erase_btn = ctk.CTkButton(
            erase_group,
            text="🧹 Erase Multiple (Select area)",
            command=lambda: self.tools.enable_multi_eraser_mode(),
            height=32,
            corner_radius=6,
            fg_color=COLORS["warning"],
            hover_color="#D97706",
            text_color=COLORS["text_white"],
            state="disabled",
        )
        multi_erase_btn.pack(fill="x", pady=(0, 4), padx=8)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(multi_erase_btn, "Erase multiple walls by selecting a box area.")

        # Enable wall-eraser buttons only when at least one 'walls_only' room exists
        def _sync_wall_eraser_buttons():
            try:
                has_walls_only = False
                if hasattr(self.tools, "has_walls_only_room"):
                    has_walls_only = bool(self.tools.has_walls_only_room())
                new_state = "normal" if has_walls_only else "disabled"
                try:
                    point_erase_btn.configure(state=new_state)
                except Exception:
                    pass
                try:
                    multi_erase_btn.configure(state=new_state)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                erase_group.after(1000, _sync_wall_eraser_buttons)
            except Exception:
                pass

        _sync_wall_eraser_buttons()

        # === Visibility / View Options ===
        view_group = ctk.CTkFrame(
            edit_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        view_group.pack(fill="x", pady=(0, 8), padx=8)

        ctk.CTkLabel(
            view_group,
            text="Visibility",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            text_color=COLORS["text_primary"]
        ).pack(fill="x", pady=(2, 4), padx=8)

        poly_trans_btn = ctk.CTkButton(
            view_group,
            text="👁️ Show Polygon" if self.model.get("polygon_transparent") else "👁️ Hide Polygon",
            command=lambda: toggle_poly_btn(),
            height=32,
            corner_radius=6,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["text_white"]
        )
        poly_trans_btn.pack(fill="x", pady=(0, 4), padx=8)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(poly_trans_btn, "Toggle transparency of polygon boundaries.")

        def toggle_poly_btn():
            self.tools.toggle_polygon_transparency()
            is_trans = self.model.get("polygon_transparent")
            poly_trans_btn.configure(text="👁️ Show Polygon" if is_trans else "👁️ Hide Polygon")

        freeze_btn_text = tk.StringVar(value="Freeze Canvas")

        # Create serializer instance
        serializer = LayoutSerializer(self.model, self.view, self.tools, self.actions)

        # === Local layout section ===
        local_group = ctk.CTkFrame(
            edit_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        local_group.pack(fill="x", pady=(4, 4), padx=4)

        ctk.CTkLabel(
            local_group,
            text="Local Layout",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            text_color=COLORS["text_primary"]
        ).pack(fill="x", pady=(4, 2), padx=4)

        # Save/Load buttons
        duplicate_layout_btn = ctk.CTkButton(
            local_group, text="⧉ Duplicate Entire Layout", command=serializer.duplicate_layout,
            fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
            height=32, corner_radius=6, text_color=COLORS["text_white"],
        )
        duplicate_layout_btn.pack(fill="x", pady=2, padx=4)

        save_load_buttons = [
            ("💾 Save as JSON", serializer.save_to_json, COLORS["success"], COLORS["text_white"], "Save layout in JSON format."),
            ("📂 Load from JSON", serializer.load_from_json, COLORS["info"], COLORS["text_white"], "Load a layout from a JSON file."),
            ("💾 Save as YAML", serializer.save_to_yaml, COLORS["success"], COLORS["text_white"], "Save layout in YAML format."),
            ("📂 Load from YAML", serializer.load_from_yaml, COLORS["info"], COLORS["text_white"], "Load a layout from a YAML file."),
            ("⚡ Auto Save (Ctrl+S)", serializer.auto_save_layout, COLORS["accent"], COLORS["text_white"], "Triggers manual autosave of current canvas.")
        ]
        
        for text, command, color, text_color, tooltip_text in save_load_buttons:
            btn = ctk.CTkButton(
                local_group,
                text=text,
                command=command,
                fg_color=color,
                hover_color=color.replace("B9", "A3") if "B9" in color else color,
                height=32,
                corner_radius=6,
                text_color=text_color
            )
            btn.pack(fill="x", pady=2, padx=4)
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(btn, tooltip_text)
        
        # Bind Ctrl+S for quick save
        self.root.bind('<Control-s>', lambda e: serializer.auto_save_layout())

        def toggle_freeze():
            self.tools.toggle_canvas_freeze()
            freeze_btn_text.set("Unfreeze Canvas" if self.tools.canvas_frozen else "Freeze Canvas")

        # Freeze canvas toggle
        freeze_frame = ctk.CTkFrame(
            edit_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        freeze_frame.pack(fill="x", pady=(4, 4), padx=4)

        freeze_btn = ctk.CTkButton(
            freeze_frame,
            textvariable=freeze_btn_text,
            command=toggle_freeze,
            fg_color=COLORS["info"],
            hover_color="#2563EB",
            height=36,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        freeze_btn.pack(fill="x", pady=4, padx=4)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(freeze_btn, "Freeze background drawing to prevent accidental edits.")
        
        # === Export section ===
        export_group = ctk.CTkFrame(
            edit_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        export_group.pack(fill="x", pady=(8, 4), padx=4)

        ctk.CTkLabel(
            export_group,
            text="Export Image",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            text_color=COLORS["text_primary"]
        ).pack(fill="x", pady=(4, 2), padx=4)

        export_full_btn = ctk.CTkButton(
            export_group,
            text="🖼 Save Full Canvas as Image",
            command=self.tools.save_canvas_image,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=32,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        export_full_btn.pack(fill="x", pady=2, padx=4)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(export_full_btn, "Save the complete canvas workspace as a PNG image.")

        export_area_btn = ctk.CTkButton(
            export_group,
            text="🔲 Save Area as PNG",
            command=self.tools.start_region_screenshot,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=32,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        export_area_btn.pack(fill="x", pady=2, padx=4)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(export_area_btn, "Select a rectangular area of canvas to save as PNG.")
        
        # === Danger zone ===
        danger_group = ctk.CTkFrame(
            edit_body,
            fg_color="#FEF2F2",
            border_color="#FECACA",
            border_width=1
        )
        danger_group.pack(fill="x", pady=(10, 8), padx=4)

        ctk.CTkLabel(
            danger_group,
            text="Reset / Cleanup",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["error"],
            anchor="w",
        ).pack(fill="x", pady=(4, 2), padx=4)

        reset_btn = ctk.CTkButton(
            danger_group,
            text="❗ Reset All (Clears Canvas)",
            fg_color=COLORS["error"],
            hover_color="#DC2626",
            command=lambda: self.tools.reset_all_canvas(confirm=True),
            height=32,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        reset_btn.pack(fill="x", pady=2, padx=4)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(reset_btn, "WARNING: Clears all walls, rooms, and furniture permanently.")
