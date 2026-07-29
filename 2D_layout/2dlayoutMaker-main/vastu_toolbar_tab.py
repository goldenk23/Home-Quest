# vastu_toolbar_tab.py
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


class VastuPolygonMeasurementsToggleController:
    """
    Under the Vastu Polygon tool, show a toggle that controls whether measurement/dimension
    lines are drawn when a Vastu polygon is completed.
    """

    def __init__(self, parent, model) -> None:
        self._parent = parent
        self._model = model

        default_on = bool(getattr(model, "auto_vastu_polygon_dimensions", True))
        try:
            setattr(model, "auto_vastu_polygon_dimensions", default_on)
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
            text_color=(COLORS["text_primary"], COLORS["text_primary"]),
        )

        # Start disabled until Vastu polygon tool is selected
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
            self._model.auto_vastu_polygon_dimensions = bool(self._var.get())
        except Exception:
            pass

    def _sync_once(self) -> None:
        try:
            enabled = bool(self._model.get("vastu_polygon_mode"))
        except Exception:
            enabled = False

        try:
            target_state = "normal" if enabled else "disabled"
            if self._switch.cget("state") != target_state:
                self._switch.configure(state=target_state)
        except Exception:
            pass

        try:
            current = bool(getattr(self._model, "auto_vastu_polygon_dimensions", True))
            if bool(self._var.get()) != current:
                self._var.set(current)
        except Exception:
            pass

        try:
            self._parent.after(max(1000, self._interval_ms), self._sync_once)
        except Exception:
            pass


class VastuZonesDropdownStateController:
    """
    Controls the Vastu 'Zones' dropdown:
    - Disabled until at least one Vastu polygon exists on canvas
    - Disabled while user is drawing a Vastu polygon
    - Enabled as READONLY after polygon is created
    - Syncs displayed value with model so Undo/Redo keeps dropdown consistent.
    """

    def __init__(self, parent, tools, model, dropdown, value_var=None, label_by_count=None) -> None:
        self._parent = parent
        self._tools = tools
        self._model = model
        self._dropdown = dropdown
        self._value_var = value_var
        self._label_by_count = label_by_count or {}
        try:
            self._dropdown.configure(state="disabled")
        except Exception:
            pass

    def start_sync(self, interval_ms: int = 500) -> None:
        self._interval_ms = max(200, int(interval_ms))
        self._sync_once()

    def _has_vastu_polygon(self) -> bool:
        try:
            canvas = getattr(self._tools, "canvas", None)
            if canvas is None:
                return False
            return bool(canvas.find_withtag("vastu_polygon"))
        except Exception:
            return False

    def _sync_once(self) -> None:
        try:
            drawing = bool(self._model.get("vastu_polygon_mode"))
        except Exception:
            drawing = False

        enabled = (self._has_vastu_polygon() and not drawing)
        try:
            target_state = "readonly" if enabled else "disabled"
            if self._dropdown.cget("state") != target_state:
                self._dropdown.configure(state=target_state)
        except Exception:
            pass

        if self._value_var is not None and self._label_by_count:
            try:
                current_count = int(self._model.get("vastu_zone_count") or 8)
            except Exception:
                current_count = 8
            desired = self._label_by_count.get(current_count)
            if desired and str(self._value_var.get()) != str(desired):
                try:
                    self._value_var.set(str(desired))
                except Exception:
                    pass

        try:
            self._parent.after(self._interval_ms, self._sync_once)
        except Exception:
            pass


class Vastu32ChakraDropdownStateController:
    """
    Controls the Vastu '32 Zones Chakra' dropdown:
    - Enabled ONLY when:
      - at least one Vastu polygon exists on canvas
      - user is NOT currently drawing a Vastu polygon
      - selected zone count is 32
    """

    def __init__(self, parent, tools, model, dropdown) -> None:
        self._parent = parent
        self._tools = tools
        self._model = model
        self._dropdown = dropdown
        try:
            self._dropdown.configure(state="disabled")
        except Exception:
            pass

    def start_sync(self, interval_ms: int = 500) -> None:
        self._interval_ms = max(200, int(interval_ms))
        self._sync_once()

    def _has_vastu_polygon(self) -> bool:
        try:
            canvas = getattr(self._tools, "canvas", None)
            if canvas is None:
                return False
            return bool(canvas.find_withtag("vastu_polygon"))
        except Exception:
            return False

    def _sync_once(self) -> None:
        try:
            drawing = bool(self._model.get("vastu_polygon_mode"))
        except Exception:
            drawing = False
        try:
            zone_count = int(self._model.get("vastu_zone_count") or 8)
        except Exception:
            zone_count = 8

        enabled = (self._has_vastu_polygon() and (not drawing) and zone_count == 32)
        try:
            target_state = "readonly" if enabled else "disabled"
            if self._dropdown.cget("state") != target_state:
                self._dropdown.configure(state=target_state)
        except Exception:
            pass

        try:
            self._parent.after(max(1000, self._interval_ms), self._sync_once)
        except Exception:
            pass


class VastuToolbarTab:
    """Class representing the Vastu Tools sidebar tab."""

    def __init__(self, root, tools) -> None:
        self.root = root
        self.tools = tools

    def build(self, vaastu_body) -> None:
        # 1. Info Help Card
        help_card = ctk.CTkFrame(
            vaastu_body,
            fg_color=(COLORS.get("primary_light", "#6366F1"), "#312E81"),
            corner_radius=8,
            border_width=1,
            border_color=COLORS.get("primary", "#4F46E5"),
        )
        help_card.pack(fill="x", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(
            help_card,
            text="🧭 Vastu Analyst / वास्तु चक्र साधन",
            font=("Segoe UI", 12, "bold"),
            text_color="#FFFFFF",
            anchor="w",
            wraplength=180
        ).pack(fill="x", padx=10, pady=(6, 2))
        
        ctk.CTkLabel(
            help_card,
            text="• Click 'Create Vastu Polygon' and draw boundary.\n• Select 8, 16, or 32 zones to see directions.\n• Move whole boundary or individual slices to align.",
            font=("Segoe UI", 10),
            text_color="#E2E8F0",
            justify="left",
            anchor="w",
            wraplength=180
        ).pack(fill="x", padx=10, pady=(0, 6))

        # 2. Header
        ctk.CTkLabel(
            vaastu_body,
            text="Vastu Tools",
            font=("Segoe UI", 16, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(0, 5))
        
        ctk.CTkLabel(
            vaastu_body,
            text="Create Vastu-compliant layouts and structures.",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            wraplength=180,
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=8, pady=(0, 10))
        
        # Vastu tools section
        vastu_frame = ctk.CTkFrame(
            vaastu_body,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1
        )
        vastu_frame.pack(fill="x", padx=10, pady=5)

        try:
            move_mode_var = tk.StringVar(value="whole")

            def _apply_vastu_move_mode() -> None:
                mode = str(move_mode_var.get() or "whole")
                try:
                    self.tools.model.set("vastu_move_slices_only", mode == "slices")
                except Exception:
                    pass

            mode_frame = ctk.CTkFrame(
                vaastu_body,
                fg_color=COLORS["surface"],
                border_color=COLORS["border"],
                border_width=1,
            )
            mode_frame.pack(fill="x", padx=10, pady=(0, 5))

            ctk.CTkLabel(
                mode_frame,
                text="Move Mode",
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS["text_primary"],
            ).pack(anchor="w", padx=8, pady=(8, 4))

            mv_whole_rb = ctk.CTkRadioButton(
                mode_frame,
                text="Move Whole Vastu",
                variable=move_mode_var,
                value="whole",
                command=_apply_vastu_move_mode,
                text_color=COLORS["text_primary"],
            )
            mv_whole_rb.pack(anchor="w", padx=8, pady=2)
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(mv_whole_rb, "Drag vastu polygon to move all slices together.")

            mv_slices_rb = ctk.CTkRadioButton(
                mode_frame,
                text="Move Slices Only",
                variable=move_mode_var,
                value="slices",
                command=_apply_vastu_move_mode,
                text_color=COLORS["text_primary"],
            )
            mv_slices_rb.pack(anchor="w", padx=8, pady=(2, 8))
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(mv_slices_rb, "Drag vertices to move individual vastu slices.")

            _apply_vastu_move_mode()
        except Exception:
            pass

        try:
            reset_slices_btn = ctk.CTkButton(
                vaastu_body,
                text="Reset Slices",
                command=getattr(self.tools, "reset_vastu_slices", lambda: None),
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                height=32,
                corner_radius=6,
                text_color=COLORS["text_white"],
            )
            reset_slices_btn.pack(fill="x", padx=10, pady=(0, 8))
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(reset_slices_btn, "Reset vastu boundary modifications back to standard shapes.")
        except Exception:
            pass

        try:
            from vastu_polygon.constants import ZONE_COUNT_CHOICES, DEFAULT_ZONE_COUNT
            zone_count_var = tk.StringVar(value="8 zone")
            current = getattr(self.tools.model, "state_flags", {}).get("vastu_zone_count", DEFAULT_ZONE_COUNT)
            for label, count in ZONE_COUNT_CHOICES:
                if count == current:
                    zone_count_var.set(label)
                    break

            def _on_zone_count_change(choice: str) -> None:
                for label, count in ZONE_COUNT_CHOICES:
                    if label == choice:
                        try:
                            old_count = int(self.tools.model.get("vastu_zone_count") or 8)
                            old_draw = str(self.tools.model.get("vastu_polygon_draw_type") or "slices")
                            self.tools.model.set("vastu_zone_count", count)
                            if getattr(self.tools, "refresh_vastu_zones_to_current_count", None):
                                self.tools.refresh_vastu_zones_to_current_count(
                                    vastu_model_before={"vastu_zone_count": old_count, "vastu_polygon_draw_type": old_draw}
                                )
                        except Exception:
                            pass
                        break

            ctk.CTkLabel(
                vastu_frame,
                text="Zones",
                font=("Segoe UI", 11, "bold"),
                text_color=COLORS["text_primary"],
            ).pack(anchor="w", padx=8, pady=(6, 2))
            
            zone_dropdown = ctk.CTkComboBox(
                vastu_frame,
                values=[label for label, _ in ZONE_COUNT_CHOICES],
                variable=zone_count_var,
                command=_on_zone_count_change,
                width=120,
                height=28,
                state="disabled",
            )
            zone_dropdown.pack(fill="x", padx=8, pady=(0, 4))
            _on_zone_count_change(zone_count_var.get())
            label_by_count = {count: label for label, count in ZONE_COUNT_CHOICES}
            VastuZonesDropdownStateController(
                vastu_frame, self.tools, self.tools.model, zone_dropdown,
                value_var=zone_count_var,
                label_by_count=label_by_count,
            ).start_sync(interval_ms=150)
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(zone_dropdown, "Select divisions (8, 16, 32 zones) for Vastu Analysis.")
        except Exception:
            pass

        # 32-zone chakra mode selector (Moderne vastu vs Vedic)
        try:
            chakra_choices = ["Moderne vastu", "Vedic"]
            current_mode = str(self.tools.model.get("vastu_32_chakra_mode"))
            if current_mode not in chakra_choices:
                current_mode = "Vedic"
            chakra_var = tk.StringVar(value=current_mode)

            def _on_chakra_mode_change(choice: str) -> None:
                self.tools.model.set("vastu_32_chakra_mode", str(choice))
                try:
                    if getattr(self.tools, "refresh_vastu_zones_to_current_count", None):
                        self.tools.refresh_vastu_zones_to_current_count()
                except Exception:
                    pass

            ctk.CTkLabel(
                vastu_frame,
                text="32 Zones Chakra",
                font=("Segoe UI", 11, "bold"),
                text_color=COLORS["text_primary"],
            ).pack(anchor="w", padx=8, pady=(6, 2))
            
            chakra_dropdown = ctk.CTkComboBox(
                vastu_frame,
                values=chakra_choices,
                variable=chakra_var,
                command=_on_chakra_mode_change,
                width=120,
                height=28,
                state="disabled",
            )
            chakra_dropdown.pack(fill="x", padx=8, pady=(0, 4))
            _on_chakra_mode_change(chakra_var.get())
            Vastu32ChakraDropdownStateController(vastu_frame, self.tools, self.tools.model, chakra_dropdown).start_sync(interval_ms=150)
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(chakra_dropdown, "Select layout style for 32 zones (Vedic or Modern Vastu).")
        except Exception:
            pass

        try:
            polygon_type_var = tk.StringVar(value=str(self.tools.model.get("vastu_polygon_draw_type")))

            def _apply_vastu_polygon_type() -> None:
                mode = str(polygon_type_var.get())
                try:
                    old_count = int(self.tools.model.get("vastu_zone_count") or 8)
                    old_draw = str(self.tools.model.get("vastu_polygon_draw_type") or "slices")
                    self.tools.model.set("vastu_polygon_draw_type", mode)
                    if getattr(self.tools, "refresh_vastu_zones_to_current_count", None):
                        self.tools.refresh_vastu_zones_to_current_count(
                            vastu_model_before={"vastu_zone_count": old_count, "vastu_polygon_draw_type": old_draw}
                        )
                except Exception:
                    pass

            ctk.CTkLabel(
                vastu_frame,
                text="Vastu Polygon Type",
                font=("Segoe UI", 11, "bold"),
                text_color=COLORS["text_primary"],
            ).pack(anchor="w", padx=8, pady=(6, 2))

            sliced_rb = ctk.CTkRadioButton(
                vastu_frame,
                text="Sliced (Zones)",
                variable=polygon_type_var,
                value="slices",
                command=_apply_vastu_polygon_type,
                text_color=COLORS["text_primary"],
            )
            sliced_rb.pack(anchor="w", padx=8, pady=2)
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(sliced_rb, "Draw Vastu overlay divided into pie segments.")

            filled_rb = ctk.CTkRadioButton(
                vastu_frame,
                text="Filled",
                variable=polygon_type_var,
                value="slices_clean",
                command=_apply_vastu_polygon_type,
                text_color=COLORS["text_primary"],
            )
            filled_rb.pack(anchor="w", padx=8, pady=2)
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(filled_rb, "Draw Vastu overlay filled with translucent colors.")

            normal_rb = ctk.CTkRadioButton(
                vastu_frame,
                text="Normal (Outline only)",
                variable=polygon_type_var,
                value="normal",
                command=_apply_vastu_polygon_type,
                text_color=COLORS["text_primary"],
            )
            normal_rb.pack(anchor="w", padx=8, pady=(2, 6))
            if hasattr(self.tools, "create_tooltip"):
                self.tools.create_tooltip(normal_rb, "Draw Vastu overlay outline only, with no interior slices.")

            _apply_vastu_polygon_type()
        except Exception:
            pass

        # Toggle: draw measurement (dimension) lines on Vastu polygon completion
        try:
            vastu_dims_toggle = VastuPolygonMeasurementsToggleController(vastu_frame, self.tools.model)
            vastu_dims_toggle.pack(pady=(0, 6), padx=24, fill="x")
            vastu_dims_toggle.start_sync(interval_ms=150)
        except Exception:
            pass

        vastu_polygon_btn = ctk.CTkButton(
            vastu_frame,
            text="🧭 Create Vastu Polygon",
            command=self.tools.start_vastu_polygon,
            fg_color=COLORS["warning"],
            hover_color="#D97706",
            height=40,
            corner_radius=6,
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["text_white"]
        )
        vastu_polygon_btn.pack(fill="x", padx=8, pady=8)
        if hasattr(self.tools, "create_tooltip"):
            self.tools.create_tooltip(vastu_polygon_btn, "Start drawing a closed Vastu boundary on canvas.")
