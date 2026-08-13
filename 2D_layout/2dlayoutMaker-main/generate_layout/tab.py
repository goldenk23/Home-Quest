from __future__ import annotations

import importlib.util
import os
import queue
import sys
import threading
import tkinter as tk

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LAYOUT_MAKER_DIR = os.path.dirname(_BASE_DIR)
try:
    if _LAYOUT_MAKER_DIR in sys.path:
        sys.path.remove(_LAYOUT_MAKER_DIR)
except Exception:
    pass
sys.path.insert(0, _LAYOUT_MAKER_DIR)


def _import_local(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if not spec or not spec.loader:
        raise ModuleNotFoundError(f"Could not load module from: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


try:
    from Helper.color_scheme import COLORS
except ModuleNotFoundError:
    _helper_dir = os.path.join(_LAYOUT_MAKER_DIR, "Helper")
    _m = _import_local("mini_autocad_color_scheme", os.path.join(_helper_dir, "color_scheme.py"))
    COLORS = getattr(_m, "COLORS", {})

try:
    from Helper.ctk_global import ctk
except ModuleNotFoundError:
    _helper_dir = os.path.join(_LAYOUT_MAKER_DIR, "Helper")
    _m = _import_local("mini_autocad_ctk_global", os.path.join(_helper_dir, "ctk_global.py"))
    ctk = getattr(_m, "ctk")

try:
    from Helper.showMessage import show_message
except ModuleNotFoundError:
    _helper_dir = os.path.join(_LAYOUT_MAKER_DIR, "Helper")
    _m = _import_local("mini_autocad_showMessage", os.path.join(_helper_dir, "showMessage.py"))
    show_message = getattr(_m, "show_message")

# Single source of truth for how each backend phase is shown (headline card + activity feed).
_PHASE_PRESENTATION = {
    "ready": ("●", "Ready for your brief", "#0F766E"),
    "preparing": ("◌", "Preparing context", "#D97706"),
    "generating": ("✦", "Designing with Gemini", "#7C3AED"),
    "parsing": ("◌", "Organizing the plan", "#2563EB"),
    "repairing_geometry": ("↻", "Aligning geometry", "#2563EB"),
    "validating_schema": ("✓", "Validating geometry", "#2563EB"),
    "validating_design": ("✓", "Checking your requirements", "#2563EB"),
    "repairing": ("↻", "Repairing validation issues", "#D97706"),
    "cancelling": ("◌", "Cancelling safely", "#D97706"),
    "cancelled": ("■", "Generation cancelled", "#64748B"),
    "timed_out": ("!", "Generation timed out", "#DC2626"),
    "complete": ("✓", "Validation passed", "#059669"),
    "applying": ("↓", "Applying to the canvas", "#2563EB"),
    "success": ("✓", "Layout ready", "#059669"),
    "error": ("!", "Generation needs attention", "#DC2626"),
}
_DEFAULT_PRESENTATION = ("◌", "Working", "#2563EB")

from layout_schema import new_project

from .service import GenerateLayoutService
from . import design_spec
from .ai_client import (
    generate_layout as ai_generate_layout,
    AIConfigError,
    AIGenerationError,
    AITimeoutError,
)


class GenerateLayoutTab:
    def __init__(self, *, model, tools, view, actions) -> None:
        self._model = model
        self._tools = tools
        self._view = view
        self._actions = actions

        default_on = bool(getattr(self._model, "auto_generate_layout_dimensions", True))
        setattr(self._model, "auto_generate_layout_dimensions", default_on)
        self._dims_var = tk.BooleanVar(value=default_on)
        self._compass_mode_var = tk.BooleanVar(value=False)

        # AI generation state
        self._ai_busy = False
        self._ai_previous_layout = None
        # Multi-floor: after a multi-storey generation the whole v2 project is loaded into the
        # serializer; these let the user switch which floor is drawn on the canvas.
        self._ai_floors_row = None
        self._ai_floor_buttons: dict[str, object] = {}
        self._ai_active_floor_id = None
        # Monotonic id stamped on each request; a worker result whose id no longer matches
        # (superseded by a newer request or a reset) is dropped and never applied.
        self._ai_generation_id = 0
        # Accepted canonical DesignSpec (Phase 1), stored beside the accepted native layout.
        self._ai_spec: design_spec.DesignSpec | None = None
        self._ai_messages: list[dict[str, str]] = []
        self._ai_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._ai_cancel_event: threading.Event | None = None
        self._ai_poll_id = None
        self._ai_resize_id = None
        self._ai_prompt = None
        self._ai_status_var = None
        self._ai_phase_title_var = None
        self._ai_phase_icon = None
        self._ai_progress_bar = None
        self._ai_generate_btn = None
        self._ai_cancel_btn = None
        self._ai_result_card = None
        self._ai_activity_log = None
        self._ai_activity_last = ""
        self._ai_result_title = None
        self._ai_result_meta = None
        self._ai_result_check = None
        self._ai_result_summary = None
        self._ai_result_details = None

    def build(self, parent) -> None:
        """Construct the premium UI for the Generate Layout tab."""
        # --- AI Layout Generator (primary feature) ---
        self._build_ai_section(parent)

        # --- Header Section ---
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", padx=12, pady=(15, 2))
        
        ctk.CTkLabel(
            header_frame,
            text="🏗️ Layout Builder",
            font=("Arial", 16, "bold"),
            text_color=COLORS.get("text_primary", "#0F172A"),
            anchor="w",
        ).pack(side="left")

        # Description
        ctk.CTkLabel(
            parent,
            text="Quickly create rectangular boundaries.",
            font=("Arial", 11),
            text_color=COLORS.get("text_secondary", "#475569"),
            wraplength=230,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=15, pady=(0, 10))

        # --- Main Input Card ---
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS.get("surface", "#FFFFFF"),
            border_color=COLORS.get("border", "#E2E8F0"),
            border_width=1,
            corner_radius=12
        )
        card.pack(fill="x", padx=10, pady=5)

        # Unit Selection Section
        unit_frame = ctk.CTkFrame(card, fg_color="transparent")
        unit_frame.pack(fill="x", padx=10, pady=(10, 6))
        
        ctk.CTkLabel(
            unit_frame,
            text="📏 Unit",
            font=("Arial", 11, "bold"),
            text_color=COLORS.get("text_primary", "#0F172A"),
        ).pack(side="left")

        available_units = list(getattr(self._model, "unit_scale", {"m": 1.0, "ft": 1.0}).keys())
        unit_menu = ctk.CTkOptionMenu(
            unit_frame,
            values=available_units,
            command=self._on_unit_change,
            width=80,
            height=26,
            corner_radius=6,
            font=("Arial", 11),
            fg_color=COLORS.get("primary_surface", "#153B3D"),
            button_color=COLORS.get("secondary", "#0F766E"),
            button_hover_color=COLORS.get("primary_hover", "#14B8A6"),
            text_color=COLORS.get("primary", "#2DD4BF"),
            dropdown_fg_color=COLORS.get("surface_dark", "#1F2937"),
            dropdown_text_color=COLORS.get("text_white", "#FFFFFF"),
            dropdown_hover_color=COLORS.get("secondary_hover", "#059669"),
            dynamic_resizing=False,
        )
        unit_menu.set(getattr(self._model, "unit", "m"))
        unit_menu.pack(side="right")

        # Mode Selection Switch
        mode_switch_frame = ctk.CTkFrame(card, fg_color="transparent")
        mode_switch_frame.pack(fill="x", padx=12, pady=(4, 6))
        
        mode_switch = ctk.CTkSwitch(
            mode_switch_frame,
            text="Non Rectangular/Square Layout",
            variable=self._compass_mode_var,
            command=self._on_toggle_mode,
            font=("Arial", 11, "bold"),
            fg_color=COLORS.get("border_strong", "#CBD5E1"),
            progress_color=COLORS.get("primary", "#4F46E5"),
            text_color=COLORS.get("text_primary", "#0F172A"),
        )
        mode_switch.pack(side="left")

        # Dimensions Section Header
        ctk.CTkLabel(
            card,
            text="📐 Dimensions",
            font=("Arial", 11, "bold"),
            text_color=COLORS.get("text_secondary", "#475569"),
            anchor="w"
        ).pack(fill="x", padx=12, pady=(4, 2))

        # --- Standard Mode Input Row (Length & Breadth) ---
        self._standard_inputs_row = ctk.CTkFrame(card, fg_color="transparent")
        self._standard_inputs_row.pack(fill="x", padx=12, pady=(0, 12))
        self._standard_inputs_row.columnconfigure(0, weight=1)
        self._standard_inputs_row.columnconfigure(1, weight=1)

        # Length Field
        len_col = ctk.CTkFrame(self._standard_inputs_row, fg_color="transparent")
        len_col.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        ctk.CTkLabel(len_col, text="Length", font=("Arial", 10), text_color=COLORS.get("text_secondary", "#475569")).pack(anchor="w")
        self._length_entry = ctk.CTkEntry(
            len_col,
            placeholder_text="0.0",
            height=34,
            border_color=COLORS.get("border_dark", "#374151"),
            fg_color="white",
            text_color="#0F172A",
            corner_radius=6
        )
        self._length_entry.pack(fill="x")

        # Breadth Field
        br_col = ctk.CTkFrame(self._standard_inputs_row, fg_color="transparent")
        br_col.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        ctk.CTkLabel(br_col, text="Breadth", font=("Arial", 10), text_color=COLORS.get("text_secondary", "#475569")).pack(anchor="w")
        self._breadth_entry = ctk.CTkEntry(
            br_col,
            placeholder_text="0.0",
            height=34,
            border_color=COLORS.get("border_dark", "#374151"),
            fg_color="white",
            text_color="#0F172A",
            corner_radius=6
        )
        self._breadth_entry.pack(fill="x")

        # --- Compass Mode Input Row (North, South, East, West) ---
        self._compass_inputs_row = ctk.CTkFrame(card, fg_color="transparent")
        self._compass_inputs_row.columnconfigure(0, weight=1)
        self._compass_inputs_row.columnconfigure(1, weight=1)

        # North Field
        n_col = ctk.CTkFrame(self._compass_inputs_row, fg_color="transparent")
        n_col.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 5))
        ctk.CTkLabel(n_col, text="North Wall", font=("Arial", 10), text_color=COLORS.get("text_secondary", "#475569")).pack(anchor="w")
        self._north_entry = ctk.CTkEntry(
            n_col,
            placeholder_text="0.0",
            height=34,
            border_color=COLORS.get("border_dark", "#374151"),
            fg_color="white",
            text_color="#0F172A",
            corner_radius=6
        )
        self._north_entry.pack(fill="x")

        # South Field
        s_col = ctk.CTkFrame(self._compass_inputs_row, fg_color="transparent")
        s_col.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 5))
        ctk.CTkLabel(s_col, text="South Wall", font=("Arial", 10), text_color=COLORS.get("text_secondary", "#475569")).pack(anchor="w")
        self._south_entry = ctk.CTkEntry(
            s_col,
            placeholder_text="0.0",
            height=34,
            border_color=COLORS.get("border_dark", "#374151"),
            fg_color="white",
            text_color="#0F172A",
            corner_radius=6
        )
        self._south_entry.pack(fill="x")

        # East Field
        e_col = ctk.CTkFrame(self._compass_inputs_row, fg_color="transparent")
        e_col.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkLabel(e_col, text="East Wall", font=("Arial", 10), text_color=COLORS.get("text_secondary", "#475569")).pack(anchor="w")
        self._east_entry = ctk.CTkEntry(
            e_col,
            placeholder_text="0.0",
            height=34,
            border_color=COLORS.get("border_dark", "#374151"),
            fg_color="white",
            text_color="#0F172A",
            corner_radius=6
        )
        self._east_entry.pack(fill="x")

        # West Field
        w_col = ctk.CTkFrame(self._compass_inputs_row, fg_color="transparent")
        w_col.grid(row=1, column=1, sticky="ew", padx=(5, 0))
        ctk.CTkLabel(w_col, text="West Wall", font=("Arial", 10), text_color=COLORS.get("text_secondary", "#475569")).pack(anchor="w")
        self._west_entry = ctk.CTkEntry(
            w_col,
            placeholder_text="0.0",
            height=34,
            border_color=COLORS.get("border_dark", "#374151"),
            fg_color="white",
            text_color="#0F172A",
            corner_radius=6
        )
        self._west_entry.pack(fill="x")

        # Compass Mode Info Label
        self._compass_note_label = ctk.CTkLabel(
            card,
            text="ℹ️ Note: North is on the Right side.",
            font=("Arial", 9, "italic"),
            text_color=COLORS.get("secondary", "#10B981"),
            anchor="w",
        )

        # Settings Section
        settings_frame = ctk.CTkFrame(card, fg_color="transparent")
        settings_frame.pack(fill="x", padx=12, pady=(0, 12))

        dims_switch = ctk.CTkSwitch(
            settings_frame,
            text="Show Measurements",
            variable=self._dims_var,
            command=self._on_toggle_dims,
            font=("Arial", 11),
            fg_color=COLORS.get("border_strong", "#CBD5E1"),
            progress_color=COLORS.get("primary", "#4F46E5"),
            text_color=COLORS.get("text_primary", "#0F172A"),
        )
        dims_switch.pack(side="left")

        # --- Action Buttons ---
        btn_container = ctk.CTkFrame(parent, fg_color="transparent")
        btn_container.pack(fill="x", padx=10, pady=(20, 10))

        def _parse_positive_float(raw: str, field: str) -> float:
            try:
                val = float((raw or "").strip())
            except ValueError as e:
                raise ValueError(f"{field} must be a valid number.") from e
            if val <= 0:
                raise ValueError(f"{field} must be greater than 0.")
            return val

        def on_generate() -> None:
            is_compass = bool(self._compass_mode_var.get())
            service = GenerateLayoutService(
                tools=self._tools,
                model=self._model,
                view=self._view,
                actions=self._actions,
            )

            if is_compass:
                def _parse_optional_float(raw: str) -> float:
                    try:
                        val = float((raw or "").strip())
                        if val <= 0:
                            return 0.0
                        return val
                    except ValueError:
                        return 0.0

                n_val = _parse_optional_float(self._north_entry.get())
                s_val = _parse_optional_float(self._south_entry.get())
                e_val = _parse_optional_float(self._east_entry.get())
                w_val = _parse_optional_float(self._west_entry.get())
                
                valid_count = sum(1 for v in (n_val, s_val, e_val, w_val) if v > 0)
                
                if valid_count < 3:
                    show_message("error", "Generate Layout", "Please enter at least 3 wall measurements.")
                    return
                
                # Auto-generate the 4th side if exactly 3 sides are entered
                if valid_count == 3:
                    if n_val <= 0:
                        n_val = s_val
                        try:
                            self._north_entry.delete(0, tk.END)
                            self._north_entry.insert(0, f"{n_val:.2f}")
                        except Exception:
                            pass
                    elif s_val <= 0:
                        s_val = n_val
                        try:
                            self._south_entry.delete(0, tk.END)
                            self._south_entry.insert(0, f"{s_val:.2f}")
                        except Exception:
                            pass
                    elif e_val <= 0:
                        e_val = w_val
                        try:
                            self._east_entry.delete(0, tk.END)
                            self._east_entry.insert(0, f"{e_val:.2f}")
                        except Exception:
                            pass
                    elif w_val <= 0:
                        w_val = e_val
                        try:
                            self._west_entry.delete(0, tk.END)
                            self._west_entry.insert(0, f"{w_val:.2f}")
                        except Exception:
                            pass

                try:
                    res = service.generate_compass_layout(
                        north=n_val,
                        south=s_val,
                        east=e_val,
                        west=w_val,
                        draw_dimensions=bool(self._dims_var.get()),
                    )
                    # Update input fields with actual physical side measurements!
                    if res and getattr(res, "actual_sides", None):
                        sides = res.actual_sides
                        try:
                            self._north_entry.delete(0, tk.END)
                            self._north_entry.insert(0, f"{sides['north']:.2f}")
                            self._south_entry.delete(0, tk.END)
                            self._south_entry.insert(0, f"{sides['south']:.2f}")
                            self._east_entry.delete(0, tk.END)
                            self._east_entry.insert(0, f"{sides['east']:.2f}")
                            self._west_entry.delete(0, tk.END)
                            self._west_entry.insert(0, f"{sides['west']:.2f}")
                        except Exception as ex:
                            print(f"[GenerateLayoutTab] Error writing back sides: {ex}")
                    else:
                        print("[GenerateLayoutTab] Warning: actual_sides is missing in layout result!")
                except Exception as e:
                    show_message("error", "Generate Layout", f"Failed to generate layout:\n{e}")
                    return
            else:
                try:
                    length = _parse_positive_float(self._length_entry.get(), "Length")
                    breadth = _parse_positive_float(self._breadth_entry.get(), "Breadth")
                except ValueError as e:
                    show_message("error", "Generate Layout", str(e))
                    return

                try:
                    service.generate_rectangle(
                        length=length,
                        breadth=breadth,
                        draw_dimensions=bool(self._dims_var.get()),
                    )
                except Exception as e:
                    show_message("error", "Generate Layout", f"Failed to generate layout:\n{e}")
                    return

            show_message("info", "Generate Layout", "Layout generated.")

        def on_clear() -> None:
            try:
                self._length_entry.delete(0, tk.END)
                self._breadth_entry.delete(0, tk.END)
                self._north_entry.delete(0, tk.END)
                self._south_entry.delete(0, tk.END)
                self._east_entry.delete(0, tk.END)
                self._west_entry.delete(0, tk.END)
            except Exception:
                pass

        # Generate Button - First Row
        generate_btn = ctk.CTkButton(
            btn_container,
            text="✨ Generate Layout",
            command=on_generate,
            fg_color=COLORS.get("primary_surface", "#153B3D"),
            hover_color=COLORS.get("sidebar_active", "#153B3D"),
            border_width=1,
            border_color=COLORS.get("secondary", "#0F766E"),
            height=36,
            corner_radius=8,
            text_color=COLORS.get("primary", "#2DD4BF"),
            font=("Arial", 13, "bold"),
        )
        generate_btn.pack(fill="x", pady=(0, 10))

        # Clear Button - Second Row
        clear_btn = ctk.CTkButton(
            btn_container,
            text="🧹 Clear Dimensions",
            command=on_clear,
            fg_color=COLORS.get("surface_muted", "#263449"),
            hover_color=COLORS.get("surface", "#1E293B"),
            border_width=1,
            border_color=COLORS.get("border", "#2A3A52"),
            height=34,
            corner_radius=8,
            text_color=COLORS.get("text_secondary", "#CBD5E1"),
            font=("Arial", 12, "bold"),
        )
        clear_btn.pack(fill="x")

        def _sync_unit_selection() -> None:
            """Keep the unit dropdown in sync with global model changes."""
            try:
                current_unit = getattr(self._model, "unit", "m")
                if unit_menu.get() != current_unit:
                    unit_menu.set(current_unit)
                parent.after(500, _sync_unit_selection)
            except Exception:
                pass

        _sync_unit_selection()

    # ------------------------------------------------------------------ AI section
    def _build_ai_section(self, parent) -> None:
        """Build a growing chat composer with observable generation progress."""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS.get("surface", "#FFFFFF"),
            border_color=COLORS.get("secondary", "#0F766E"),
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="x", padx=10, pady=(12, 4))

        ctk.CTkLabel(
            card,
            text="✨ AI Layout Generator",
            font=("Arial", 15, "bold"),
            text_color=COLORS.get("text_primary", "#0F172A"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            card,
            text="Describe a home, follow the live design checks, then refine it conversationally.",
            font=("Arial", 10),
            text_color=COLORS.get("text_secondary", "#475569"),
            wraplength=240,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

        # The surrounding toolbar already scrolls, so the conversation can grow naturally.
        self._ai_result_card = ctk.CTkFrame(card, fg_color="transparent")
        self._ai_result_card.pack(fill="x", padx=10)

        ctk.CTkLabel(
            card,
            text="YOUR REQUEST",
            font=("Arial", 9, "bold"),
            text_color=COLORS.get("text_secondary", "#64748B"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(4, 4))
        self._ai_prompt = ctk.CTkTextbox(
            card,
            height=84,
            wrap="word",
            font=("Arial", 11),
            border_width=1,
            border_color=COLORS.get("border", "#334155"),
            corner_radius=8,
        )
        self._ai_prompt.pack(fill="x", padx=12, pady=(0, 8))
        self._ai_prompt.insert(
            "1.0",
            "Design a north-facing 40x60 ft 3-bedroom Vastu home with a puja room, "
            "open kitchen in the southeast, and good ventilation.",
        )
        self._ai_prompt.bind("<KeyRelease>", self._schedule_ai_prompt_resize, add="+")
        self._ai_prompt.after_idle(self._resize_ai_prompt)
        self._ai_pending_prompt = ""

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 8))
        self._ai_generate_btn = ctk.CTkButton(
            btn_row,
            text="✨ Generate with AI",
            command=self._on_ai_generate,
            fg_color=COLORS.get("primary_surface", "#153B3D"),
            hover_color=COLORS.get("sidebar_active", "#153B3D"),
            border_width=1,
            border_color=COLORS.get("secondary", "#0F766E"),
            height=36,
            corner_radius=8,
            text_color=COLORS.get("primary", "#2DD4BF"),
            font=("Arial", 13, "bold"),
        )
        self._ai_generate_btn.pack(fill="x")
        self._ai_cancel_btn = ctk.CTkButton(
            btn_row,
            text="Cancel generation",
            command=self._on_ai_cancel,
            state="disabled",
            fg_color=COLORS.get("surface_muted", "#263449"),
            hover_color=COLORS.get("error", "#B91C1C"),
            border_width=1,
            border_color=COLORS.get("border", "#2A3A52"),
            height=30,
            corner_radius=8,
            text_color=COLORS.get("text_secondary", "#CBD5E1"),
            font=("Arial", 11, "bold"),
        )
        self._ai_cancel_btn.pack(fill="x", pady=(6, 0))
        ctk.CTkButton(
            btn_row,
            text="🧵 New design",
            command=self._on_ai_reset,
            fg_color=COLORS.get("surface_muted", "#263449"),
            hover_color=COLORS.get("surface", "#1E293B"),
            border_width=1,
            border_color=COLORS.get("border", "#2A3A52"),
            height=30,
            corner_radius=8,
            text_color=COLORS.get("text_secondary", "#CBD5E1"),
            font=("Arial", 11),
        ).pack(fill="x", pady=(6, 0))

        # One persistent activity card avoids layout jumps and reports only work the
        # provider/validator is actually performing.
        self._ai_result_title = ctk.CTkFrame(
            card,
            fg_color=COLORS.get("surface_muted", "#F1F5F9"),
            corner_radius=8,
        )
        self._ai_result_title.pack(fill="x", padx=12, pady=(2, 7))
        phase_header = ctk.CTkFrame(self._ai_result_title, fg_color="transparent")
        phase_header.pack(fill="x", padx=10, pady=(8, 1))
        self._ai_phase_icon = ctk.CTkLabel(
            phase_header,
            text="●",
            width=18,
            font=("Arial", 11, "bold"),
            text_color=COLORS.get("secondary", "#0F766E"),
        )
        self._ai_phase_icon.pack(side="left")
        self._ai_phase_title_var = tk.StringVar(value="Ready for your brief")
        ctk.CTkLabel(
            phase_header,
            textvariable=self._ai_phase_title_var,
            font=("Arial", 10, "bold"),
            text_color=COLORS.get("text_primary", "#0F172A"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        self._ai_phase_detail_var = tk.StringVar(
            value="Generation, validation, repair, and canvas application are shown here."
        )
        ctk.CTkLabel(
            self._ai_result_title,
            textvariable=self._ai_phase_detail_var,
            font=("Arial", 9),
            text_color=COLORS.get("text_secondary", "#475569"),
            wraplength=218,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 7))
        self._ai_progress_bar = ctk.CTkProgressBar(
            self._ai_result_title,
            height=3,
            corner_radius=2,
            progress_color=COLORS.get("primary", "#2DD4BF"),
            fg_color=COLORS.get("border", "#334155"),
        )
        self._ai_progress_bar.pack(fill="x", padx=10, pady=(0, 9))
        self._ai_progress_bar.set(0)

        self._ai_status_var = tk.StringVar(
            value="Tip: include plot size, facing direction, rooms, and priorities."
        )
        self._ai_result_meta = ctk.CTkLabel(
            card,
            textvariable=self._ai_status_var,
            font=("Arial", 9),
            text_color=COLORS.get("text_secondary", "#64748B"),
            wraplength=240,
            justify="left",
            anchor="w",
        )
        self._ai_result_meta.pack(fill="x", padx=12, pady=(0, 11))

        # Backend activity feed: a live, scrolling log of what the pipeline is doing
        # (planning rooms -> building the exact shell -> furnishing -> validating -> applying).
        ctk.CTkLabel(
            card,
            text="⚙ BACKEND ACTIVITY",
            font=("Arial", 9, "bold"),
            text_color=COLORS.get("text_secondary", "#64748B"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 2))
        self._ai_activity_log = ctk.CTkTextbox(
            card,
            height=150,
            wrap="word",
            font=("Consolas", 9),
            border_width=1,
            border_color=COLORS.get("border", "#334155"),
            fg_color=COLORS.get("surface_dark", "#0B1220"),
            text_color=COLORS.get("text_secondary", "#CBD5E1"),
            corner_radius=8,
        )
        self._ai_activity_log.pack(fill="x", padx=12, pady=(0, 10))
        self._ai_activity_log.insert("1.0", "Waiting for a design brief…\n")
        self._ai_activity_log.configure(state="disabled")

        # Floor switcher (shown only after a multi-floor generation). Each button activates a
        # floor in the serializer's project so it is drawn on the canvas.
        self._ai_floors_row = ctk.CTkFrame(card, fg_color="transparent")
        self._render_ai_messages()

    def _schedule_ai_prompt_resize(self, _event=None) -> None:
        """Coalesce key events so long prompts resize smoothly without flicker."""
        if self._ai_prompt is None:
            return
        if self._ai_resize_id is not None:
            try:
                self._ai_prompt.after_cancel(self._ai_resize_id)
            except Exception:
                pass
        self._ai_resize_id = self._ai_prompt.after_idle(self._resize_ai_prompt)

    def _resize_ai_prompt(self) -> None:
        """Grow with the prompt text, capped so the rest of the tab stays reachable."""
        self._ai_resize_id = None
        if self._ai_prompt is None:
            return
        text = self._ai_prompt.get("1.0", "end-1c")
        available_width = max(216, self._ai_prompt.winfo_width() - 24)
        characters_per_line = max(16, int(available_width / 7.2))
        display_lines = sum(
            max(1, (len(line) + characters_per_line - 1) // characters_per_line)
            for line in text.split("\n")
        )
        # ponytail: text-width estimation keeps typing responsive; 240 px is the
        # deliberate ceiling and the native textbox scrolls beyond it.
        self._ai_prompt.configure(height=min(240, max(84, 32 + display_lines * 19)))

    def _render_ai_messages(self) -> None:
        """Render accepted conversation turns as readable production-style bubbles."""
        if self._ai_result_card is None:
            return
        for child in self._ai_result_card.winfo_children():
            child.destroy()
        for message in self._ai_messages:
            is_user = message.get("role") == "user"
            bubble = ctk.CTkFrame(
                self._ai_result_card,
                fg_color=(
                    COLORS.get("primary_surface", "#153B3D")
                    if is_user else COLORS.get("surface_muted", "#F1F5F9")
                ),
                border_width=0 if is_user else 1,
                border_color=COLORS.get("border", "#334155"),
                corner_radius=9,
            )
            bubble.pack(fill="x", padx=((22, 0) if is_user else (0, 12)), pady=(0, 7))
            ctk.CTkLabel(
                bubble,
                text="YOU" if is_user else "✨ AI ARCHITECT",
                font=("Arial", 9, "bold"),
                text_color=(
                    COLORS.get("primary", "#2DD4BF")
                    if is_user else COLORS.get("secondary", "#0F766E")
                ),
                anchor="w",
            ).pack(fill="x", padx=10, pady=(7, 2))
            ctk.CTkLabel(
                bubble,
                text=str(message.get("content", "")).strip(),
                font=("Arial", 10),
                text_color=(
                    COLORS.get("text_white", "#FFFFFF")
                    if is_user else COLORS.get("text_primary", "#0F172A")
                ),
                wraplength=210,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=10, pady=(0, 9))

    def _set_ai_status(self, message: str) -> None:
        if self._ai_status_var is not None:
            self._ai_status_var.set(message)

    def _clear_ai_activity(self) -> None:
        """Reset the backend-activity feed for a new run."""
        self._ai_activity_last = ""
        log = self._ai_activity_log
        if log is None:
            return
        try:
            log.configure(state="normal")
            log.delete("1.0", "end")
            log.configure(state="disabled")
        except Exception:
            pass

    def _append_ai_activity(self, phase: str, message: str) -> None:
        """Append one backend step to the activity feed, collapsing repeats."""
        log = self._ai_activity_log
        if log is None or not message:
            return
        icon = _PHASE_PRESENTATION.get(phase, _DEFAULT_PRESENTATION)[0]
        line = f"{icon}  {message}"
        if line == self._ai_activity_last:
            return  # collapse consecutive duplicate steps so the feed stays readable
        self._ai_activity_last = line
        try:
            log.configure(state="normal")
            log.insert("end", line + "\n")
            log.see("end")
            log.configure(state="disabled")
        except Exception:
            pass

    def _set_ai_phase(self, phase: str, detail: str) -> None:
        icon, title, color = _PHASE_PRESENTATION.get(phase, _DEFAULT_PRESENTATION)
        if self._ai_phase_icon is not None:
            self._ai_phase_icon.configure(text=icon, text_color=color)
        if self._ai_phase_title_var is not None:
            self._ai_phase_title_var.set(title)
        if getattr(self, "_ai_phase_detail_var", None) is not None:
            self._ai_phase_detail_var.set(detail)

    def _set_ai_busy(self, busy: bool) -> None:
        self._ai_busy = busy
        if self._ai_generate_btn is not None:
            self._ai_generate_btn.configure(state="disabled" if busy else "normal")
            if busy:
                self._ai_generate_btn.configure(text="Working…")
            else:
                label = "✨ Refine layout" if self._ai_previous_layout is not None else "✨ Generate with AI"
                self._ai_generate_btn.configure(text=label)
        if self._ai_cancel_btn is not None:
            self._ai_cancel_btn.configure(state="normal" if busy else "disabled")
        if self._ai_prompt is not None:
            self._ai_prompt.configure(state="disabled" if busy else "normal")
        if self._ai_progress_bar is not None:
            if busy:
                self._ai_progress_bar.configure(mode="indeterminate")
                self._ai_progress_bar.start()
            else:
                self._ai_progress_bar.stop()

    def _restore_pending_prompt(self) -> None:
        if self._ai_prompt is None or not self._ai_pending_prompt:
            return
        self._ai_prompt.delete("1.0", "end")
        self._ai_prompt.insert("1.0", self._ai_pending_prompt)
        self._schedule_ai_prompt_resize()

    def _show_floor_switcher(self, floors: list, active_id) -> None:
        """Render one button per floor (or hide the row for a single-floor plan)."""
        row = self._ai_floors_row
        if row is None:
            return
        for child in row.winfo_children():
            child.destroy()
        self._ai_floor_buttons = {}
        if not floors or len(floors) < 2:
            row.pack_forget()
            return
        ctk.CTkLabel(
            row, text="🏢 FLOORS",
            font=("Arial", 9, "bold"),
            text_color=COLORS.get("text_secondary", "#64748B"),
            anchor="w",
        ).pack(fill="x", padx=2, pady=(0, 3))
        button_bar = ctk.CTkFrame(row, fg_color="transparent")
        button_bar.pack(fill="x")
        for floor in floors:
            fid, fname = floor.get("id"), floor.get("name") or "Floor"
            btn = ctk.CTkButton(
                button_bar,
                text=fname,
                command=lambda i=fid: self._on_switch_floor(i),
                height=28,
                corner_radius=6,
                font=("Arial", 10, "bold"),
            )
            btn.pack(side="left", padx=2, pady=2)
            self._ai_floor_buttons[fid] = btn
        row.pack(fill="x", padx=12, pady=(0, 10))
        self._highlight_active_floor(active_id)

    def _highlight_active_floor(self, active_id) -> None:
        self._ai_active_floor_id = active_id
        for fid, btn in self._ai_floor_buttons.items():
            if fid == active_id:
                btn.configure(fg_color=COLORS.get("secondary", "#0F766E"),
                              text_color=COLORS.get("text_white", "#FFFFFF"))
            else:
                btn.configure(fg_color=COLORS.get("surface_muted", "#263449"),
                              text_color=COLORS.get("text_secondary", "#CBD5E1"))

    def _on_switch_floor(self, floor_id) -> None:
        """Draw the chosen floor on the canvas via the serializer's native floor model."""
        if self._ai_busy or floor_id == self._ai_active_floor_id:
            return
        serializer = getattr(self._actions, "serializer", None)
        if serializer is None or not hasattr(serializer, "activate_floor"):
            return
        try:
            serializer.activate_floor(floor_id)
        except Exception as exc:  # noqa: BLE001 - report switch failures without crashing the tab
            show_message("error", "Floors", f"Could not switch floor: {exc}")
            return
        self._highlight_active_floor(floor_id)

    def _rollback_pending_turn(self) -> None:
        if self._ai_messages and self._ai_messages[-1].get("role") == "user":
            self._ai_messages.pop()
        self._render_ai_messages()
        self._restore_pending_prompt()

    def _on_ai_reset(self) -> None:
        if self._ai_busy:
            return

        # "New design" is a project boundary, not only a new AI conversation. Loading a fresh
        # native project clears every parked floor and notifies the long-lived 3D viewer before
        # another generated document can reuse entity IDs from the previous design.
        serializer = getattr(self._actions, "serializer", None)
        if serializer is None or not hasattr(serializer, "load_document"):
            show_message("error", "AI Layout Generator", "The layout serializer is unavailable; cannot start a new design.")
            return
        try:
            if not serializer.load_document(new_project(), confirm=True):
                return
        except Exception as exc:  # noqa: BLE001 - preserve the current project if reset fails
            show_message("error", "AI Layout Generator", f"Could not start a new design: {exc}")
            return

        self._ai_generation_id += 1  # invalidate any late result from a prior generation
        self._ai_spec = None
        self._ai_messages = []
        self._ai_previous_layout = None
        self._ai_pending_prompt = ""
        self._show_floor_switcher([], None)  # clear any multi-floor buttons
        if self._ai_prompt is not None:
            self._ai_prompt.delete("1.0", "end")
        self._render_ai_messages()
        self._resize_ai_prompt()
        self._set_ai_phase("ready", "Start by describing the plot, rooms, orientation, and priorities.")
        if self._ai_progress_bar is not None:
            self._ai_progress_bar.set(0)
        self._clear_ai_activity()
        self._set_ai_status("New design started. Your previous AI conversation has been cleared.")
        self._set_ai_busy(False)

    def _on_ai_generate(self) -> None:
        if self._ai_busy:
            return
        prompt = self._ai_prompt.get("1.0", "end").strip() if self._ai_prompt is not None else ""
        if not prompt:
            show_message("error", "AI Layout Generator", "Enter a description of the house first.")
            return

        serializer = getattr(self._actions, "serializer", None)
        if serializer is None or not hasattr(serializer, "load_document"):
            show_message("error", "AI Layout Generator", "The layout serializer is unavailable; cannot apply AI output.")
            return

        # A previous worker has terminated before busy is cleared, so anything left here is stale.
        while True:
            try:
                self._ai_queue.get_nowait()
            except queue.Empty:
                break

        self._ai_generation_id += 1
        gen = self._ai_generation_id
        self._ai_cancel_event = threading.Event()
        cancel_event = self._ai_cancel_event
        self._ai_pending_prompt = prompt
        self._ai_messages.append({"role": "user", "content": prompt})
        messages = list(self._ai_messages)
        previous = self._ai_previous_layout
        current_spec = self._ai_spec
        self._render_ai_messages()
        if self._ai_prompt is not None:
            self._ai_prompt.delete("1.0", "end")
            self._resize_ai_prompt()

        self._set_ai_busy(True)
        self._clear_ai_activity()
        self._set_ai_phase("preparing", "Preparing the bounded generation request.")
        self._append_ai_activity(
            "preparing",
            "Starting generation — the AI plans the rooms, deterministic code builds the exact "
            "shell, then the AI furnishes it.",
        )
        self._set_ai_status("Generation is time- and cost-bounded. You can cancel safely at any time.")

        def report_progress(phase: str, message: str) -> None:
            self._ai_queue.put(("progress", (gen, phase, message)))

        def worker() -> None:
            try:
                result = ai_generate_layout(
                    messages,
                    previous,
                    previous_spec=current_spec,
                    on_progress=report_progress,
                    cancel_event=cancel_event,
                )
                self._ai_queue.put(("cancelled", (gen, None)) if cancel_event.is_set() else ("ok", (gen, result)))
            except (AIConfigError, AIGenerationError) as exc:
                self._ai_queue.put(("cancelled", (gen, None)) if cancel_event.is_set() else ("err", (gen, exc)))
            except Exception as exc:  # noqa: BLE001 - report any unexpected failure to the UI
                self._ai_queue.put(("cancelled", (gen, None)) if cancel_event.is_set() else ("err", (gen, exc)))

        threading.Thread(target=worker, name="ai-layout", daemon=True).start()
        self._schedule_ai_poll()

    def _on_ai_cancel(self) -> None:
        if not self._ai_busy or self._ai_cancel_event is None:
            return
        self._ai_cancel_event.set()
        if self._ai_cancel_btn is not None:
            self._ai_cancel_btn.configure(state="disabled")
        self._set_ai_phase(
            "cancelling",
            "Stopping after the current provider request returns or reaches its timeout; no layout will be applied.",
        )
        self._set_ai_status("Cancellation requested. Your current canvas remains unchanged.")

    def _schedule_ai_poll(self) -> None:
        if self._ai_poll_id is not None:
            return
        root = getattr(self._view, "canvas", None)
        widget = root if root is not None else self._ai_prompt
        if widget is not None:
            self._ai_poll_id = widget.after(120, self._poll_ai_queue)

    def _poll_ai_queue(self) -> None:
        self._ai_poll_id = None
        progress_events: list[tuple[object, object]] = []
        terminal: tuple[str, object] | None = None
        while True:
            try:
                kind, payload = self._ai_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                if isinstance(payload, tuple) and len(payload) == 3:
                    event_gen, phase, message = payload
                    if event_gen == self._ai_generation_id:
                        progress_events.append((phase, message))
                elif isinstance(payload, tuple) and len(payload) == 2:
                    progress_events.append(payload)
            else:
                terminal = (kind, payload)

        # Stream every backend step into the activity feed; the last one drives the headline.
        # Once the user is cancelling we stop scrolling so the feed doesn't keep moving.
        cancelling = self._ai_cancel_event is not None and self._ai_cancel_event.is_set()
        if progress_events and not cancelling:
            for phase, message in progress_events:
                self._append_ai_activity(str(phase), str(message))
            phase, message = progress_events[-1]
            self._set_ai_phase(str(phase), str(message))

        if terminal is not None:
            # Terminal payloads are (generation_id, value). A mismatch means a stale worker
            # (superseded request or reset) finished late; drop it so it can never apply.
            t_kind, wrapped = terminal
            if isinstance(wrapped, tuple) and len(wrapped) == 2:
                result_gen, real_payload = wrapped
            else:  # defensive: unstamped payload from an unexpected producer
                result_gen, real_payload = self._ai_generation_id, wrapped
            terminal = (t_kind, real_payload) if result_gen == self._ai_generation_id else None

        if terminal is None:
            if self._ai_busy:
                self._schedule_ai_poll()
            return

        kind, payload = terminal
        cancelled = self._ai_cancel_event is not None and self._ai_cancel_event.is_set()
        if cancelled:
            kind = "cancelled"
        self._ai_cancel_event = None

        if kind == "cancelled":
            self._set_ai_busy(False)
            self._rollback_pending_turn()
            self._set_ai_phase("cancelled", "Generation stopped safely; no generated data was applied.")
            self._append_ai_activity("cancelled", "Cancelled — nothing was applied.")
            self._set_ai_status("Your request was restored so you can edit it or try again.")
            return

        if kind == "ok":
            result = payload  # type: ignore[assignment]
            layout = result["layout"]
            assistant_message = str(result.get("assistantMessage", "")).strip()
            calls = int(result.get("calls", result.get("attempts", 1)))
            elapsed = float(result.get("elapsed_seconds", 0.0))
            change_kind = str(result.get("change_kind", "structural"))

            # Answer/no-op chat turn: reply in the conversation and leave the canvas, the accepted
            # layout, and the stored spec exactly as they were.
            if change_kind == "answer" or layout is None:
                self._ai_messages.append(
                    {"role": "assistant", "content": assistant_message or "…"})
                self._ai_pending_prompt = ""
                self._render_ai_messages()
                self._set_ai_busy(False)
                if self._ai_progress_bar is not None:
                    self._ai_progress_bar.configure(mode="determinate")
                    self._ai_progress_bar.set(1)
                self._set_ai_phase("ready", "Answered your question; the layout is unchanged.")
                self._append_ai_activity("complete", "Answered without changing the canvas.")
                self._set_ai_status("Ask another question, request a change, or choose New design.")
                return

            # A multi-floor result carries a native v2 document (every floor). Loading it puts all
            # floors into the serializer's project and draws the ground floor; single-floor results
            # load their v1 layout exactly as before.
            version_2 = result.get("version_2") if isinstance(result, dict) else None
            apply_payload = version_2 if isinstance(version_2, dict) else layout
            self._set_ai_phase("applying", "Loading the validated layout through the native serializer.")
            # The AI apply is the user's explicit intent (they ran generation and accepted the
            # result), so we must NOT block on load_document's modal "Replace current layout?"
            # confirmation — that modal stalls the whole apply (the layout never commits) and was
            # why a generated multi-floor plan never reached the canvas/viewer. We preserve the
            # safety intent of confirm=True by writing a backup of the current plan first, then
            # apply with confirm=False so the commit is non-blocking.
            serializer = self._actions.serializer
            try:
                # Keep replacement non-modal, but never replace user work unless its backup is
                # durably written. Reuse the serializer's atomic writer so a failed write cannot
                # leave a partial file that looks recoverable.
                import datetime as _dt
                from layout_serializer import atomic_write_document
                backup_dir = getattr(serializer, "default_save_dir", _LAYOUT_MAKER_DIR)
                backup_path = os.path.join(
                    backup_dir, f"before_ai_apply_{_dt.datetime.now():%Y%m%d_%H%M%S}.json")
                atomic_write_document(serializer.serialize_layout(), backup_path)
                if self._ai_result_title is not None:
                    self._ai_result_title.update_idletasks()
                applied = serializer.load_document(apply_payload, confirm=False)
            except Exception as exc:  # noqa: BLE001 - surface apply/import failures
                self._set_ai_busy(False)
                self._rollback_pending_turn()
                self._set_ai_phase("error", f"The validated plan could not be applied: {exc}")
                self._set_ai_status("Nothing was replaced. Your request has been restored for retrying.")
                return
            if not applied:
                self._set_ai_busy(False)
                self._rollback_pending_turn()
                self._set_ai_phase("ready", "The generated plan was kept out because replacement was cancelled.")
                self._set_ai_status("Your request has been restored; the existing canvas is unchanged.")
                return

            self._ai_previous_layout = layout

            # Multi-storey (Scope A): every floor is now loaded into the serializer's project.
            # Show in-app Floor buttons so the user can switch which floor is drawn; a single-floor
            # result hides the switcher.
            if isinstance(version_2, dict):
                serializer = getattr(self._actions, "serializer", None)
                project_state = getattr(serializer, "project_state", None)
                try:
                    floors = project_state.floors if project_state is not None else version_2.get("floors", [])
                    active_id = (project_state.active_floor_id if project_state is not None
                                 else version_2.get("active_floor_id"))
                except Exception:  # noqa: BLE001 - fall back to the document's own floor list
                    floors, active_id = version_2.get("floors", []), version_2.get("active_floor_id")
                self._show_floor_switcher(floors, active_id)
                self._append_ai_activity(
                    "success", f"Loaded {len(floors)} floors — use the Floor buttons to switch.")
            else:
                self._show_floor_switcher([], None)

            # Store the accepted canonical intent beside the native layout. Multi mode
            # returns the direct spec; comb mode keeps its legacy program adapter.
            raw_spec = result.get("spec") if isinstance(result, dict) else None
            program = result.get("program") if isinstance(result, dict) else None
            try:
                if isinstance(raw_spec, dict):
                    self._ai_spec = design_spec.from_dict(raw_spec)
                elif isinstance(program, dict):
                    self._ai_spec = design_spec.from_program(program)
                if self._ai_spec is not None:
                    self._append_ai_activity("complete", f"Interpreted intent — {self._ai_spec.summary()}")
            except (TypeError, ValueError):
                self._ai_spec = None
            # Multi-planner telemetry (Phase 2-6/7): report the chosen topology, its score,
            # the diverse alternatives, and any disclosed feasibility assumptions/compromises.
            multi = result.get("multi") if isinstance(result, dict) else None
            if isinstance(multi, dict):
                try:
                    self._append_ai_activity(
                        "complete", f"Selected topology '{multi.get('selected_strategy')}'.")
                    for cand in (multi.get("candidates") or [])[:4]:
                        mark = "✓" if cand.get("valid") else "✗"
                        line = f"  {mark} {cand.get('strategy')}: score {cand.get('score', 0):.2f}"
                        if cand.get("compromises"):
                            line += f" — {cand['compromises'][0]}"
                        self._append_ai_activity("complete", line)
                    feas = multi.get("feasibility") or {}
                    for note in (feas.get("assumptions") or []) + (feas.get("warnings") or []):
                        self._append_ai_activity("complete", f"  note: {note}")
                except Exception:  # noqa: BLE001 - telemetry display must never break apply
                    pass
            self._ai_messages.append({"role": "assistant", "content": assistant_message})
            self._ai_pending_prompt = ""
            self._render_ai_messages()
            self._set_ai_busy(False)
            if self._ai_progress_bar is not None:
                self._ai_progress_bar.configure(mode="determinate")
                self._ai_progress_bar.set(1)
            rooms = len(layout.get("rooms", [])) if isinstance(layout, dict) else 0
            furniture = len(layout.get("furniture", [])) if isinstance(layout, dict) else 0
            self._set_ai_phase(
                "success",
                f"Applied {rooms} rooms and {furniture} furniture items after {calls} model call{'s' if calls != 1 else ''} in {elapsed:.1f}s.",
            )
            self._append_ai_activity(
                "success",
                f"Done — applied {rooms} rooms and {furniture} furniture items after "
                f"{calls} model call{'s' if calls != 1 else ''} in {elapsed:.1f}s.",
            )
            self._set_ai_status("Continue with a revision request, or choose New design to start over.")
            return

        self._set_ai_busy(False)
        self._rollback_pending_turn()
        exc = payload
        if isinstance(exc, AIGenerationError) and exc.details:
            details = "\n".join(f"• {item}" for item in exc.details[:3])
            message = f"{exc}\n{details}"
        else:
            message = f"Generation failed: {exc}"
        phase = "timed_out" if isinstance(exc, AITimeoutError) else "error"
        self._set_ai_phase(phase, message)
        self._append_ai_activity(phase, (message.splitlines() or ["Generation failed."])[0])
        self._set_ai_status("Nothing was applied. Your request was restored so you can edit and retry.")

    def _on_toggle_mode(self) -> None:
        """Handle toggling between Standard and Compass-aligned input modes."""
        if self._compass_mode_var.get():
            self._standard_inputs_row.pack_forget()
            self._compass_inputs_row.pack(fill="x", padx=12, pady=(0, 12))
            self._compass_note_label.pack(fill="x", padx=12, pady=(0, 8))
        else:
            self._compass_inputs_row.pack_forget()
            self._compass_note_label.pack_forget()
            self._standard_inputs_row.pack(fill="x", padx=12, pady=(0, 12))

    def _on_toggle_dims(self) -> None:
        """Toggle automatic dimension lines for generated layout."""
        setattr(self._model, "auto_generate_layout_dimensions", bool(self._dims_var.get()))

    def _on_unit_change(self, new_unit: str) -> None:
        """Handle unit change from the dropdown menu."""
        if hasattr(self._model, "set_unit"):
            self._model.set_unit(new_unit)
        else:
            # Fallback if set_unit is missing
            setattr(self._model, "unit", new_unit)
            unit_scale = getattr(self._model, "unit_scale", {})
            if new_unit in unit_scale:
                setattr(self._model, "unit_scale_factor", unit_scale[new_unit])

