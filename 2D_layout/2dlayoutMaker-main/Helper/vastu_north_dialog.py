"""
Helper/vastu_north_dialog.py

Modal dialog to pick Vastu North direction. North is at the RIGHT (app convention).
- Dialog convention: 0° = North (right), 90° = West (top), 180° = South (left), 270° = East (bottom).
- Returned value (canvas): anti-clockwise from up; 270° = North (right).
"""

from __future__ import annotations

import platform
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
import math
from typing import Optional

from Helper.set_window_icon import set_window_icon

# Canvas uses anti-clockwise from up; 270 = right = North.
# Dialog uses 0 = North (right), 90 = West (up), 180 = South (left), 270 = East (down).
# Important: dialog degrees increase anti-clockwise on the dial, matching the app's anti-clockwise UX.
def _canvas_to_dialog(canvas_deg: float) -> float:
    # canvas: 0=up, 90=left, 180=down, 270=right
    # dialog: 0=right, 90=up, 180=left, 270=down
    return (float(canvas_deg) + 90.0) % 360.0

def _dialog_to_canvas(dialog_deg: float) -> float:
    return (float(dialog_deg) - 90.0) % 360.0


@dataclass(frozen=True)
class NorthAngleResult:
    """Angle in canvas convention: anti-clockwise from up; 270° = North (right)."""
    angle_deg_anticlockwise: float


class VastuNorthAngleDialog:
    def __init__(self, parent: tk.Misc, initial_angle: float = 270.0, title: str = "Vastu: Set North") -> None:
        # initial_angle in canvas convention (270 = North at right)
        self._parent = parent
        self._canvas_initial = float(initial_angle) % 360.0
        self._dialog_initial = _canvas_to_dialog(self._canvas_initial)
        self._title = title
        self._result: Optional[NorthAngleResult] = None

        self._win = tk.Toplevel(parent)
        self._win.title(self._title)
        self._win.resizable(False, False)

        try:
            set_window_icon(self._win)
        except Exception:
            pass

        self._win.transient(parent.winfo_toplevel())
        self._win.grab_set()
        self._win.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._win.bind("<Unmap>", self._on_unmap)

        self._angle_var = tk.DoubleVar(value=self._dialog_initial)
        # Dialer entry: used as offset (for arrow buttons) or exact degree (Enter).
        # Keep it blank by default (no "0.0" written).
        self._entry_var = tk.StringVar(value="")
        self._status_var = tk.StringVar(value="")

        self._build_ui()
        self._center_on_parent()
        self._redraw_compass()

    def _build_ui(self) -> None:
        pad = 16
        is_macos = platform.system() == "Darwin"
        row_offset = 0

        if is_macos:
            try:
                self._win.overrideredirect(True)
            except Exception:
                pass
            row_offset = 1

        root = ttk.Frame(self._win, padding=pad)
        root.grid(row=0, column=0, sticky="nsew")
        self._win.columnconfigure(0, weight=1)
        self._win.rowconfigure(0, weight=1)

        if is_macos:
            header = ttk.Frame(root)
            header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
            root.columnconfigure(0, weight=1)
            ttk.Label(header, text="Set North direction", font=("Segoe UI", 12, "bold")).pack(side="left")
            ttk.Button(header, text="✕", width=3, command=self._on_cancel).pack(side="right")

        if not is_macos:
            ttk.Label(root, text="Set North direction", font=("Segoe UI", 12, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w"
            )

        subtitle = ttk.Label(
            root,
            text="North = Right (0°)  •  West = Up (90°)  •  South = Left (180°)  •  East = Down (270°)",
        )
        subtitle.grid(row=1 + row_offset, column=0, columnspan=2, sticky="w", pady=(2, 10))

        # Compass dial (left) – North at right
        self._canvas_size = 280
        self._canvas = tk.Canvas(root, width=self._canvas_size, height=self._canvas_size, highlightthickness=0)
        self._canvas.grid(row=2 + row_offset, column=0, rowspan=5, padx=(0, 12), sticky="n")
        self._canvas.bind("<Button-1>", self._on_compass_pointer)
        self._canvas.bind("<B1-Motion>", self._on_compass_pointer)

        # Direction dialer (ported from Vastu app): arrow buttons + center angle input.
        dialer_panel = ttk.LabelFrame(root, text="Direction Dialer", padding=6)
        dialer_panel.grid(row=2 + row_offset, column=1, sticky="nw", pady=(0, 6))

        def create_compass_dialer(parent: ttk.LabelFrame) -> ttk.Frame:
            dialer_container = ttk.Frame(parent)
            dialer_container.pack(fill="both", expand=True, padx=5, pady=2)

            for i in range(3):
                dialer_container.grid_rowconfigure(i, weight=1, minsize=15)
                dialer_container.grid_columnconfigure(i, weight=1, minsize=25)

            direction_buttons = [
                ("W", "↑", (0, 1), lambda: self._apply_direction_with_offset("W")),
                ("S", "←", (1, 0), lambda: self._apply_direction_with_offset("S")),
                ("N", "→", (1, 2), lambda: self._apply_direction_with_offset("N")),
                ("E", "↓", (2, 1), lambda: self._apply_direction_with_offset("E")),
            ]

            for _dir_name, symbol, pos, cmd in direction_buttons:
                btn = ttk.Button(dialer_container, text=symbol, command=cmd, width=2)
                btn.grid(row=pos[0], column=pos[1], padx=1, pady=1, sticky="nsew")

            center_frame = ttk.Frame(dialer_container, relief="solid", borderwidth=1)
            center_frame.grid(row=1, column=1, padx=1, pady=1, sticky="nsew")

            inner_frame = ttk.Frame(center_frame, relief="groove", borderwidth=1)
            inner_frame.pack(fill="both", expand=True, padx=1, pady=1)

            input_container = ttk.Frame(inner_frame)
            input_container.pack(fill="both", expand=True, padx=1, pady=1)

            self.degree_entry = ttk.Entry(
                input_container,
                justify="center",
                textvariable=self._entry_var,
                width=8,
                font=("Helvetica", 12, "bold"),
            )
            self.degree_entry.pack(fill="x")
            self.degree_entry.bind("<Return>", lambda _e: self._set_exact_degree_from_entry())
            self.degree_entry.bind("<Escape>", lambda _e: self._on_cancel())
            self.degree_entry.bind("<FocusOut>", lambda _e: self._set_exact_degree_from_entry())

            ttk.Label(input_container, text="°", font=("Helvetica", 10, "bold"), foreground="#0066CC").pack()
            ttk.Label(input_container, text="Enter angle", font=("Helvetica", 6), foreground="#888888").pack()

            return dialer_container

        create_compass_dialer(dialer_panel)

        # Controls (right)
        controls = ttk.Frame(root)
        controls.grid(row=3 + row_offset, column=1, sticky="nsew")
        root.columnconfigure(1, weight=1)

        self._big_angle = ttk.Label(controls, text=self._format_deg(self._dialog_initial), font=("Segoe UI", 20, "bold"))
        self._big_angle.grid(row=1, column=0, sticky="w", pady=(8, 6))

        presets = ttk.LabelFrame(controls, text="Quick presets")
        presets.grid(row=2, column=0, sticky="ew")
        for i, (txt, v) in enumerate((("North (0°)", 0.0), ("West (90°)", 90.0), ("South (180°)", 180.0), ("East (270°)", 270.0))):
            ttk.Button(presets, text=txt, command=lambda vv=v: self._set_angle(vv)).grid(
                row=i // 2, column=i % 2, padx=6, pady=6, sticky="ew"
            )
        presets.columnconfigure(0, weight=1)
        presets.columnconfigure(1, weight=1)

        nudge = ttk.LabelFrame(controls, text="Nudge")
        nudge.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(nudge, text="⟲  -15°", command=lambda: self._nudge(-15.0)).grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        ttk.Button(nudge, text="⟳  +15°", command=lambda: self._nudge(+15.0)).grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        nudge.columnconfigure(0, weight=1)
        nudge.columnconfigure(1, weight=1)

        self._scale = tk.Scale(
            controls,
            from_=0,
            to=359,
            orient="horizontal",
            showvalue=False,
            length=280,
            command=lambda _v: self._sync_from_scale(),
        )
        self._scale.set(int(round(self._dialog_initial)) % 360)
        self._scale.grid(row=4 + row_offset, column=0, sticky="ew", pady=(10, 0))

        status = ttk.Label(root, textvariable=self._status_var, foreground="#b91c1c")
        status.grid(row=7 + row_offset, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Separator(root).grid(row=8 + row_offset, column=0, columnspan=2, sticky="ew", pady=(10, 8))

        btns = ttk.Frame(root)
        btns.grid(row=9 + row_offset, column=0, columnspan=2, sticky="ew")
        btns.columnconfigure(0, weight=1)
        ttk.Button(btns, text="Cancel", command=self._on_cancel).grid(row=0, column=1, sticky="e")
        ttk.Button(btns, text="OK", command=self._on_ok).grid(row=0, column=2, sticky="e", padx=(8, 0))

        try:
            if hasattr(self, "degree_entry"):
                self.degree_entry.focus_set()
        except Exception:
            pass

        try:
            self._win.update_idletasks()
            self._win.minsize(self._win.winfo_width(), self._win.winfo_height())
        except Exception:
            pass

    def _read_entry_degrees(self, empty_as_zero: bool = False) -> Optional[float]:
        """Read degrees from entry. empty_as_zero: blank => 0 (for arrow offsets)."""
        s = (self._entry_var.get() or "").strip()
        if not s:
            return 0.0 if empty_as_zero else None
        try:
            return float(s) % 360.0
        except Exception:
            self._status_var.set("Please enter a valid number (0–359).")
            return None

    def _apply_direction_with_offset(self, direction: str) -> None:
        """
        Vastu-app dialer logic:
        - Read entry as offset degrees (blank => 0)
        - Apply: base(direction) + offset
        - Clear entry afterwards
        Dialog convention: 0°=North (right), 90°=West (up), 180°=South (left), 270°=East (down).
        """
        base = {"N": 0.0, "W": 90.0, "S": 180.0, "E": 270.0}.get(str(direction).upper())
        if base is None:
            return
        offset = self._read_entry_degrees(empty_as_zero=True)
        if offset is None:
            return
        self._set_angle((base + float(offset)) % 360.0)
        try:
            self._entry_var.set("")
        except Exception:
            pass

    def _set_exact_degree_from_entry(self) -> None:
        """Set needle to exact degrees typed in the dialer entry (Enter key)."""
        v = self._read_entry_degrees()
        if v is None:
            return
        self._set_angle(float(v) % 360.0)

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

    def _set_angle(self, v: float) -> None:
        v = float(v) % 360.0
        self._angle_var.set(v)
        self._status_var.set("")
        try:
            self._big_angle.config(text=self._format_deg(v))
        except Exception:
            pass
        self._redraw_compass()
        try:
            self._scale.set(int(round(v)) % 360)
        except Exception:
            pass

    def _nudge(self, delta: float) -> None:
        self._set_angle(float(self._angle_var.get()) + float(delta))

    def _sync_from_scale(self) -> None:
        try:
            v = float(self._scale.get()) % 360.0
        except Exception:
            return
        self._angle_var.set(v)
        self._status_var.set("")
        try:
            self._big_angle.config(text=self._format_deg(v))
        except Exception:
            pass
        self._redraw_compass()

    def _on_ok(self) -> None:
        dialog_v = float(self._angle_var.get()) % 360.0
        canvas_v = _dialog_to_canvas(dialog_v)
        self._result = NorthAngleResult(angle_deg_anticlockwise=canvas_v)
        self._close()

    def _on_cancel(self) -> None:
        self._result = None
        self._close()

    def _on_unmap(self, _event) -> None:
        try:
            if str(self._win.state()) == "iconic":
                self._on_cancel()
        except Exception:
            self._on_cancel()

    def _close(self) -> None:
        try:
            self._win.grab_release()
        except Exception:
            pass
        try:
            self._win.destroy()
        except Exception:
            pass

    @staticmethod
    def _format_deg(v: float) -> str:
        return f"{float(v) % 360.0:.1f}°"

    def _on_compass_pointer(self, event: tk.Event) -> None:
        """Map click to dialog angle: right=0°, top=90°, left=180°, bottom=270°."""
        try:
            cx = self._canvas_size / 2
            cy = self._canvas_size / 2
            dx = float(event.x) - cx
            dy = float(event.y) - cy
            if (dx * dx + dy * dy) < 25.0:
                return
            # atan2(-dy, dx): right=0°, top=90°, left=180°, bottom=270°
            dialog_deg = math.degrees(math.atan2(-dy, dx)) % 360.0
            self._set_angle(float(dialog_deg))
        except Exception:
            return

    def _redraw_compass(self) -> None:
        if not hasattr(self, "_canvas"):
            return
        c = self._canvas
        c.delete("all")

        size = self._canvas_size
        cx = size / 2
        cy = size / 2
        margin = 28
        r = (size / 2) - margin

        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#9ca3af", width=2)

        # Ticks: dialog 0° at right, increasing anti-clockwise (90° at top).
        for deg in range(0, 360, 30):
            rad = math.radians(float(deg) % 360.0)
            vx = math.cos(rad)
            vy = -math.sin(rad)
            inner = r - (10 if deg % 90 == 0 else 6)
            c.create_line(
                cx + vx * inner, cy + vy * inner,
                cx + vx * r, cy + vy * r,
                fill="#6b7280", width=2 if deg % 90 == 0 else 1,
            )

        # Labels: 0° at right, 90° at top, 180° at left, 270° at bottom
        label_gap = 10
        c.create_text(cx + r + label_gap, cy, text="0°", fill="#111827", font=("Segoe UI", 9), anchor="w")
        c.create_text(cx, cy - r - label_gap, text="90°", fill="#111827", font=("Segoe UI", 9), anchor="s")
        c.create_text(cx - r - label_gap, cy, text="180°", fill="#111827", font=("Segoe UI", 9), anchor="e")
        c.create_text(cx, cy + r + label_gap, text="270°", fill="#111827", font=("Segoe UI", 9), anchor="n")

        # Arrow: dialog angle 0 = right, 90 = top, 180 = left, 270 = bottom
        dialog_deg = float(self._angle_var.get()) % 360.0
        rad = math.radians(dialog_deg)
        vx = math.cos(rad)
        vy = -math.sin(rad)
        x2 = cx + vx * (r - 16)
        y2 = cy + vy * (r - 16)
        c.create_line(cx, cy, x2, y2, fill="#dc2626", width=3, arrow=tk.LAST)
        c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#dc2626", outline="")

    def show(self) -> Optional[NorthAngleResult]:
        self._win.wait_window()
        return self._result
