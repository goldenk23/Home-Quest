"""
Helper/room_style_dialog.py

Room creation UI:
- Filled (optional custom color)
- Transparent (no fill)
- Walls only (0.2 ft) with hollow interior

We use a custom Toplevel so we can apply the app icon via `set_window_icon()`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, colorchooser
from dataclasses import dataclass
from typing import Optional

from Helper.set_window_icon import set_window_icon


@dataclass(frozen=True)
class RoomStyleResult:
    fill_mode: str  # "filled" | "transparent" | "walls_only"
    fill_color: Optional[str]  # hex like "#RRGGBB" or None


class RoomStyleDialog:
    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str = "Room Style",
        default_fill_color: str = "#d0f0c0",
        initial_mode: str = "filled",
    ) -> None:
        self._parent = parent
        self._title = title
        self._result: Optional[RoomStyleResult] = None

        self._mode_var = tk.StringVar(value=initial_mode if initial_mode in ("filled", "transparent", "walls_only") else "filled")
        self._color_var = tk.StringVar(value=str(default_fill_color or "#d0f0c0"))

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
        self._win.bind("<Escape>", lambda _e: self._on_cancel())
        self._win.bind("<Return>", lambda _e: self._on_ok())
        self._win.bind("<Unmap>", self._on_unmap)

        self._build_ui()
        self._center_on_parent()
        self._sync_enabled_state()

    def show(self) -> Optional[RoomStyleResult]:
        try:
            self._win.wait_window()
        except Exception:
            pass
        return self._result

    def _build_ui(self) -> None:
        pad = 14
        root = ttk.Frame(self._win, padding=pad)
        root.grid(row=0, column=0, sticky="nsew")

        title = ttk.Label(root, text="Create room with…", font=("Segoe UI", 12, "bold"))
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(root, text="Choose how the room should look on the canvas.")
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 10))

        opts = ttk.LabelFrame(root, text="Style")
        opts.grid(row=2, column=0, sticky="ew")

        def rb(text: str, value: str, row: int) -> None:
            ttk.Radiobutton(
                opts,
                text=text,
                value=value,
                variable=self._mode_var,
                command=self._sync_enabled_state,
            ).grid(row=row, column=0, sticky="w", padx=10, pady=6)

        rb("Filled (with color)", "filled", 0)
        rb("Transparent (only outline)", "transparent", 1)
        rb("Walls only (0.2 ft thick, hollow inside)", "walls_only", 2)

        color_row = ttk.Frame(root)
        color_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        color_row.columnconfigure(1, weight=1)

        ttk.Label(color_row, text="Fill color:").grid(row=0, column=0, sticky="w")

        self._color_swatch = tk.Canvas(color_row, width=26, height=18, highlightthickness=1, highlightbackground="#999999")
        self._color_swatch.grid(row=0, column=1, sticky="w", padx=(8, 8))

        self._color_text = ttk.Label(color_row, textvariable=self._color_var)
        self._color_text.grid(row=0, column=2, sticky="w")

        self._pick_btn = ttk.Button(color_row, text="Choose…", command=self._pick_color)
        self._pick_btn.grid(row=0, column=3, sticky="e", padx=(10, 0))

        ttk.Separator(root).grid(row=4, column=0, sticky="ew", pady=(12, 10))

        btns = ttk.Frame(root)
        btns.grid(row=5, column=0, sticky="ew")
        btns.columnconfigure(0, weight=1)
        ttk.Button(btns, text="Cancel", command=self._on_cancel).grid(row=0, column=1, sticky="e")
        ttk.Button(btns, text="OK", command=self._on_ok).grid(row=0, column=2, sticky="e", padx=(8, 0))

        try:
            self._pick_btn.focus_set()
        except Exception:
            pass

        try:
            self._win.update_idletasks()
            self._win.minsize(self._win.winfo_width(), self._win.winfo_height())
        except Exception:
            pass

        self._redraw_swatch()

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

    def _pick_color(self) -> None:
        try:
            chosen = colorchooser.askcolor(
                title="Choose fill color",
                parent=self._win,
                initialcolor=self._color_var.get() or None,
            )
        except Exception:
            chosen = None
        if chosen and chosen[1]:
            self._color_var.set(chosen[1])
            self._redraw_swatch()

    def _redraw_swatch(self) -> None:
        try:
            self._color_swatch.delete("all")
            self._color_swatch.create_rectangle(
                0,
                0,
                26,
                18,
                outline="",
                fill=self._color_var.get() or "#d0f0c0",
            )
        except Exception:
            pass

    def _sync_enabled_state(self) -> None:
        mode = self._mode_var.get()
        enabled = mode == "filled"
        try:
            self._pick_btn.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            pass
        try:
            self._color_swatch.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            pass
        try:
            self._color_text.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            pass

    def _on_unmap(self, _event) -> None:
        """
        Handle cases where the dialog window is minimized.
        When minimized, immediately cancel/close the dialog so the main canvas
        is not left in a confusing blank/blocked state.
        """
        try:
            if str(self._win.state()) == "iconic":
                self._on_cancel()
        except Exception:
            self._on_cancel()

    def _on_ok(self) -> None:
        mode = self._mode_var.get()
        if mode not in ("filled", "transparent", "walls_only"):
            mode = "filled"
        color: Optional[str] = self._color_var.get() if mode == "filled" else None
        self._result = RoomStyleResult(fill_mode=mode, fill_color=color or None)
        try:
            self._win.destroy()
        except Exception:
            pass

    def _on_cancel(self) -> None:
        self._result = None
        try:
            self._win.destroy()
        except Exception:
            pass

