"""
Helper/vastu_generator_dialog.py

Premium Wizard Dialog for AI Vastu Floor Plan & Furniture Planner.
Centers perfectly on parent, fully themed, and responsive across Windows, Mac, and Linux.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict

from Helper.set_window_icon import set_window_icon


class VastuGeneratorDialog:
    def __init__(self, parent: tk.Misc, default_unit: str = "m") -> None:
        self._parent = parent
        self._result: Optional[dict] = None

        self._win = tk.Toplevel(parent)
        self._win.title("AI Vastu Floor Plan Planner")
        self._win.resizable(False, False)

        try:
            set_window_icon(self._win)
        except Exception:
            pass

        self._win.transient(parent.winfo_toplevel())
        self._win.grab_set()
        
        # Set up variables
        self._unit_var = tk.StringVar(value=default_unit)
        self._len_var = tk.StringVar(value="40.0")
        self._br_var = tk.StringVar(value="30.0")
        self._bhk_var = tk.StringVar(value="2 BHK")
        self._facing_var = tk.StringVar(value="East")

        # Furniture checkboxes
        self._furn_bed = tk.BooleanVar(value=True)
        self._furn_sofa = tk.BooleanVar(value=True)
        self._furn_tv = tk.BooleanVar(value=True)
        self._furn_dining = tk.BooleanVar(value=True)
        self._furn_stove = tk.BooleanVar(value=True)
        self._furn_fridge = tk.BooleanVar(value=True)
        self._furn_toilet = tk.BooleanVar(value=True)
        self._furn_pooja = tk.BooleanVar(value=True)

        self._win.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._win.bind("<Escape>", lambda _e: self._on_cancel())
        self._win.bind("<Return>", lambda _e: self._on_ok())

        self._build_ui()
        self._center_on_parent()

    def show(self) -> Optional[dict]:
        try:
            self._win.wait_window()
        except Exception:
            pass
        return self._result

    def _build_ui(self) -> None:
        # Use the current active application theme to preserve main toolbar custom tab layouts

        pad = 16
        root = ttk.Frame(self._win, padding=pad)
        root.grid(row=0, column=0, sticky="nsew")

        # Header Title
        title = ttk.Label(root, text="🏗️ AI Vastu Floor Plan & Furniture Planner", font=("Segoe UI", 13, "bold"), foreground="#800000")
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))

        subtitle = ttk.Label(root, text="Specify plot size, BHK configuration, and let the AI draft a Vastu-compliant furnished plan.")
        subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        # ---- LEFT PANEL: Plot Details & BHK Configuration ----
        left_frame = ttk.LabelFrame(root, text=" 1. Plot Details & Rooms ", padding=10)
        left_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 8))

        # Length Input
        ttk.Label(left_frame, text="Plot Length (Vertical):").grid(row=0, column=0, sticky="w", pady=4)
        len_ent = ttk.Entry(left_frame, textvariable=self._len_var, width=12)
        len_ent.grid(row=0, column=1, sticky="w", pady=4, padx=(8, 0))

        # Width Input
        ttk.Label(left_frame, text="Plot Width (Horizontal):").grid(row=1, column=0, sticky="w", pady=4)
        br_ent = ttk.Entry(left_frame, textvariable=self._br_var, width=12)
        br_ent.grid(row=1, column=1, sticky="w", pady=4, padx=(8, 0))

        # Unit selection (read-only info based on current model unit)
        ttk.Label(left_frame, text="Active Unit:").grid(row=2, column=0, sticky="w", pady=4)
        unit_lbl = ttk.Label(left_frame, textvariable=self._unit_var, font=("Segoe UI", 10, "bold"), foreground="#10B981")
        unit_lbl.grid(row=2, column=1, sticky="w", pady=4, padx=(8, 0))

        # BHK Configuration
        ttk.Label(left_frame, text="BHK Configuration:").grid(row=3, column=0, sticky="w", pady=6)
        bhk_combo = ttk.Combobox(left_frame, values=["1 BHK", "2 BHK", "3 BHK", "4 BHK"], textvariable=self._bhk_var, width=10, state="readonly")
        bhk_combo.grid(row=3, column=1, sticky="w", pady=6, padx=(8, 0))

        # Plot Facing Direction
        ttk.Label(left_frame, text="Plot Facing:").grid(row=4, column=0, sticky="w", pady=6)
        facing_combo = ttk.Combobox(left_frame, values=["East", "North", "West", "South"], textvariable=self._facing_var, width=10, state="readonly")
        facing_combo.grid(row=4, column=1, sticky="w", pady=6, padx=(8, 0))

        # Show Dimensions Checkbox
        self._show_dims = tk.BooleanVar(value=True)
        cb_dims = ttk.Checkbutton(left_frame, text="Show Plot Dimensions", variable=self._show_dims)
        cb_dims.grid(row=5, column=0, columnspan=2, sticky="w", pady=8, padx=(4, 0))

        # ---- RIGHT PANEL: Vastu Auto-Furnishing Options ----
        right_frame = ttk.LabelFrame(root, text=" 2. Auto-Furnish Checklist ", padding=10)
        right_frame.grid(row=2, column=1, sticky="nsew", padx=(8, 0))

        # Checkboxes for furniture items to place in their correct Vastu sectors
        cb_bed = ttk.Checkbutton(right_frame, text="Bed in Bedrooms (SW/NW, Head South)", variable=self._furn_bed)
        cb_bed.grid(row=0, column=0, sticky="w", pady=4)

        cb_sofa = ttk.Checkbutton(right_frame, text="Sofa Set in Living Lounge (SW/West)", variable=self._furn_sofa)
        cb_sofa.grid(row=1, column=0, sticky="w", pady=4)

        cb_tv = ttk.Checkbutton(right_frame, text="TV Cabinet on East Wall", variable=self._furn_tv)
        cb_tv.grid(row=2, column=0, sticky="w", pady=4)

        cb_dining = ttk.Checkbutton(right_frame, text="Dining Table in lounge (East/NE)", variable=self._furn_dining)
        cb_dining.grid(row=3, column=0, sticky="w", pady=4)

        cb_stove = ttk.Checkbutton(right_frame, text="Kitchen Stove in South-East Corner", variable=self._furn_stove)
        cb_stove.grid(row=4, column=0, sticky="w", pady=4)

        cb_fridge = ttk.Checkbutton(right_frame, text="Kitchen Fridge in North-West Corner", variable=self._furn_fridge)
        cb_fridge.grid(row=5, column=0, sticky="w", pady=4)

        cb_toilet = ttk.Checkbutton(right_frame, text="Toilet Commode on South Wall", variable=self._furn_toilet)
        cb_toilet.grid(row=6, column=0, sticky="w", pady=4)

        cb_pooja = ttk.Checkbutton(right_frame, text="Pooja Altar on East Wall", variable=self._furn_pooja)
        cb_pooja.grid(row=7, column=0, sticky="w", pady=4)

        # Separator line
        ttk.Separator(root).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 10))

        # Bottom Buttons
        btns = ttk.Frame(root)
        btns.grid(row=4, column=0, columnspan=2, sticky="ew")
        btns.columnconfigure(0, weight=1)
        
        ttk.Button(btns, text="Cancel", command=self._on_cancel).grid(row=0, column=1, sticky="e")
        ttk.Button(btns, text="✨ Generate Floor Plan", command=self._on_ok, style="Accent.TButton").grid(row=0, column=2, sticky="e", padx=(10, 0))

        # Set default focus
        try:
            len_ent.focus_set()
        except Exception:
            pass

    def _center_on_parent(self) -> None:
        try:
            self._win.update_idletasks()
            pw = self._parent.winfo_toplevel()
            px = pw.winfo_rootx()
            py = pw.winfo_rooty()
            pww = pw.winfo_width()
            phh = pw.winfo_height()
            ww = self._win.winfo_width()
            wh = self._win.winfo_height()
            x = px + max(0, (pww - ww) // 2)
            y = py + max(0, (phh - wh) // 2)
            self._win.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_ok(self) -> None:
        try:
            length = float(self._len_var.get().strip())
            breadth = float(self._br_var.get().strip())
        except ValueError:
            from Helper.showMessage import show_message
            show_message("error", "Input Error", "Please enter valid numeric dimensions for plot Length & Width.")
            return

        self._result = {
            "length": length,
            "breadth": breadth,
            "bhk_type": self._bhk_var.get(),
            "facing": self._facing_var.get(),
            "show_dims": bool(self._show_dims.get()),
            "furniture": {
                "bed": bool(self._furn_bed.get()),
                "sofa": bool(self._furn_sofa.get()),
                "tv": bool(self._furn_tv.get()),
                "dining": bool(self._furn_dining.get()),
                "stove": bool(self._furn_stove.get()),
                "fridge": bool(self._furn_fridge.get()),
                "toilet": bool(self._furn_toilet.get()),
                "pooja": bool(self._furn_pooja.get()),
            }
        }
        self._win.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        self._win.destroy()
