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

from .service import GenerateLayoutService
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
            fg_color=COLORS.get("surface", "#F9FAFB"),
            text_color=COLORS.get("text_primary", "#111827"),
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
            fg_color=COLORS.get("surface", "#F9FAFB"),
            text_color=COLORS.get("text_primary", "#111827"),
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
            fg_color=COLORS.get("surface", "#F9FAFB"),
            text_color=COLORS.get("text_primary", "#111827"),
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
            fg_color=COLORS.get("surface", "#F9FAFB"),
            text_color=COLORS.get("text_primary", "#111827"),
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
            fg_color=COLORS.get("surface", "#F9FAFB"),
            text_color=COLORS.get("text_primary", "#111827"),
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
            fg_color=COLORS.get("surface", "#F9FAFB"),
            text_color=COLORS.get("text_primary", "#111827"),
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

    def _rollback_pending_turn(self) -> None:
        if self._ai_messages and self._ai_messages[-1].get("role") == "user":
            self._ai_messages.pop()
        self._render_ai_messages()
        self._restore_pending_prompt()

    def _on_ai_reset(self) -> None:
        if self._ai_busy:
            return
        self._ai_messages = []
        self._ai_previous_layout = None
        self._ai_pending_prompt = ""
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

        self._ai_cancel_event = threading.Event()
        cancel_event = self._ai_cancel_event
        self._ai_pending_prompt = prompt
        self._ai_messages.append({"role": "user", "content": prompt})
        messages = list(self._ai_messages)
        previous = self._ai_previous_layout
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
            self._ai_queue.put(("progress", (phase, message)))

        def worker() -> None:
            try:
                result = ai_generate_layout(
                    messages,
                    previous,
                    on_progress=report_progress,
                    cancel_event=cancel_event,
                )
                self._ai_queue.put(("cancelled", None) if cancel_event.is_set() else ("ok", result))
            except (AIConfigError, AIGenerationError) as exc:
                self._ai_queue.put(("cancelled", None) if cancel_event.is_set() else ("err", exc))
            except Exception as exc:  # noqa: BLE001 - report any unexpected failure to the UI
                self._ai_queue.put(("cancelled", None) if cancel_event.is_set() else ("err", exc))

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
                progress_events.append(payload)  # type: ignore[arg-type]
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
            self._set_ai_phase("applying", "Loading the validated layout through the native serializer.")
            try:
                if self._ai_result_title is not None:
                    self._ai_result_title.update_idletasks()
                applied = self._actions.serializer.load_document(layout, confirm=True)
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

