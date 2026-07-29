# coor_toolbar_tab.py
import tkinter as tk
from tkinter import messagebox
import os
import sys
import importlib.util
import re

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


class CoordinateToolbarTab:
    """Class representing the Coordinate Drawing sidebar tab."""

    def __init__(self, tools) -> None:
        self.tools = tools

    def _apply_coord_input_validation(self, entry_widget) -> None:
        allowed_chars = set("0123456789.-")

        def _validate(proposed: str) -> bool:
            if proposed == "":
                return True
            return all(ch in allowed_chars for ch in proposed)

        try:
            entry_widget.configure(
                validate="key",
                validatecommand=(entry_widget.register(_validate), "%P"),
            )
        except Exception:
            pass

    def _show_invalid_input(self, message: str) -> None:
        try:
            messagebox.showwarning("Invalid Coordinates", message)
        except Exception:
            print(message)

    def build(self, coor_body) -> None:
        # 1. Info Help Card
        help_card = ctk.CTkFrame(
            coor_body,
            fg_color=(COLORS.get("primary_light", "#6366F1"), "#312E81"),
            corner_radius=8,
            border_width=1,
            border_color=COLORS.get("primary", "#4F46E5"),
        )
        help_card.pack(fill="x", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(
            help_card,
            text="📍 Coordinates / सटीक नाप (संख्या द्वारा)",
            font=("Segoe UI", 12, "bold"),
            text_color="#FFFFFF",
            anchor="w",
            wraplength=180
        ).pack(fill="x", padx=10, pady=(6, 2))
        
        ctk.CTkLabel(
            help_card,
            text="• Enter exact coordinates in the boxes below.\n• Line & Rectangle: set X & Y for both points.\n• Circle: set center CX, CY and radius R.\n• Click 'Draw' to render.",
            font=("Segoe UI", 10),
            text_color="#E2E8F0",
            justify="left",
            anchor="w",
            wraplength=180
        ).pack(fill="x", padx=10, pady=(0, 6))

        # 2. Header
        ctk.CTkLabel(
            coor_body,
            text="Coordinate Drawing",
            font=("Segoe UI", 16, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(0, 5))
        
        # Coordinate label
        coord_label = ctk.CTkLabel(
            coor_body, 
            text="Coordinates: (0.0, 0.0)",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        )
        coord_label.pack(pady=5, anchor="w")
        self.tools.set_coord_label(coord_label)
        
        # Line by Coordinates section
        line_frame = ctk.CTkFrame(
            coor_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        line_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            line_frame,
            text="Draw Line",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(5, 2))
        
        grid_line = ctk.CTkFrame(line_frame, fg_color="transparent")
        grid_line.pack(fill="x", padx=8, pady=4)
        grid_line.columnconfigure(0, weight=1)
        grid_line.columnconfigure(1, weight=1)
        
        x1_entry = ctk.CTkEntry(grid_line, placeholder_text="x1 (Start X)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        x1_entry.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        y1_entry = ctk.CTkEntry(grid_line, placeholder_text="y1 (Start Y)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        y1_entry.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        
        x2_entry = ctk.CTkEntry(grid_line, placeholder_text="x2 (End X)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        x2_entry.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        y2_entry = ctk.CTkEntry(grid_line, placeholder_text="y2 (End Y)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        y2_entry.grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        self._apply_coord_input_validation(x1_entry)
        self._apply_coord_input_validation(y1_entry)
        self._apply_coord_input_validation(x2_entry)
        self._apply_coord_input_validation(y2_entry)

        def parse_and_draw_line():
            try:
                x1 = float(x1_entry.get().strip() or 0)
                y1 = float(y1_entry.get().strip() or 0)
                x2 = float(x2_entry.get().strip() or 0)
                y2 = float(y2_entry.get().strip() or 0)
                self.tools.draw_line_by_coords(x1, y1, x2, y2)
            except ValueError:
                self._show_invalid_input("Please enter valid numeric coordinates!")

        line_draw_btn = ctk.CTkButton(
            line_frame, 
            text="✏️ Draw Line", 
            command=parse_and_draw_line,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            height=32,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        line_draw_btn.pack(fill="x", padx=8, pady=(2, 8))
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(line_draw_btn, "Draw a line with exact start (x1,y1) and end (x2,y2) coordinates.")

        # Rectangle by Coordinates section
        rect_frame = ctk.CTkFrame(
            coor_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        rect_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            rect_frame,
            text="Draw Rectangle",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(5, 2))
        
        grid_rect = ctk.CTkFrame(rect_frame, fg_color="transparent")
        grid_rect.pack(fill="x", padx=8, pady=4)
        grid_rect.columnconfigure(0, weight=1)
        grid_rect.columnconfigure(1, weight=1)
        
        rx1_entry = ctk.CTkEntry(grid_rect, placeholder_text="x1 (Corner 1 X)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        rx1_entry.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ry1_entry = ctk.CTkEntry(grid_rect, placeholder_text="y1 (Corner 1 Y)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        ry1_entry.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        
        rx2_entry = ctk.CTkEntry(grid_rect, placeholder_text="x2 (Corner 2 X)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        rx2_entry.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        ry2_entry = ctk.CTkEntry(grid_rect, placeholder_text="y2 (Corner 2 Y)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        ry2_entry.grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        self._apply_coord_input_validation(rx1_entry)
        self._apply_coord_input_validation(ry1_entry)
        self._apply_coord_input_validation(rx2_entry)
        self._apply_coord_input_validation(ry2_entry)

        def parse_and_draw_rectangle():
            try:
                x1 = float(rx1_entry.get().strip() or 0)
                y1 = float(ry1_entry.get().strip() or 0)
                x2 = float(rx2_entry.get().strip() or 0)
                y2 = float(ry2_entry.get().strip() or 0)
                self.tools.draw_rectangle_by_coords(x1, y1, x2, y2)
            except ValueError:
                self._show_invalid_input("Please enter valid numeric coordinates!")

        rect_draw_btn = ctk.CTkButton(
            rect_frame, 
            text="⬜ Draw Rectangle", 
            command=parse_and_draw_rectangle,
            fg_color=COLORS["text_secondary"],
            hover_color="#4B5563",
            height=32,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        rect_draw_btn.pack(fill="x", padx=8, pady=(2, 8))
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(rect_draw_btn, "Draw a rectangle specifying opposite corners (x1,y1) and (x2,y2).")

        # Circle by Coordinates section
        circle_frame = ctk.CTkFrame(
            coor_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        circle_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            circle_frame,
            text="Draw Circle",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(5, 2))
        
        grid_circle = ctk.CTkFrame(circle_frame, fg_color="transparent")
        grid_circle.pack(fill="x", padx=8, pady=4)
        grid_circle.columnconfigure(0, weight=1)
        grid_circle.columnconfigure(1, weight=1)
        
        cx_entry = ctk.CTkEntry(grid_circle, placeholder_text="cx (Center X)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        cx_entry.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        cy_entry = ctk.CTkEntry(grid_circle, placeholder_text="cy (Center Y)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        cy_entry.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        
        r_entry = ctk.CTkEntry(circle_frame, placeholder_text="r (Radius)", border_color=COLORS["border"], fg_color="white", text_color=COLORS["text_primary"], height=28)
        r_entry.pack(fill="x", padx=10, pady=2)

        self._apply_coord_input_validation(cx_entry)
        self._apply_coord_input_validation(cy_entry)
        self._apply_coord_input_validation(r_entry)

        def parse_and_draw_circle():
            try:
                cx = float(cx_entry.get().strip() or 0)
                cy = float(cy_entry.get().strip() or 0)
                r = float(r_entry.get().strip() or 0)
                if r <= 0:
                    self._show_invalid_input("Radius must be greater than 0!")
                    return
                self.tools.draw_circle_by_coords(cx, cy, r)
            except ValueError:
                self._show_invalid_input("Please enter valid numeric values!")

        circle_draw_btn = ctk.CTkButton(
            circle_frame, 
            text="⭕ Draw Circle", 
            command=parse_and_draw_circle,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=32,
            corner_radius=6,
            text_color=COLORS["text_white"]
        )
        circle_draw_btn.pack(fill="x", padx=8, pady=(2, 8))
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(circle_draw_btn, "Draw a circle specifying center (cx,cy) and radius (r).")
