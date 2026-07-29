# Helper/zoom_helper.py
"""
Class-based zoom controller helper for MiniAutoCAD 2D Layout Maker.
Provides Zoom In and Zoom Out widgets with professional styling and tooltips.
"""

import tkinter as tk
from typing import Any

from Helper.ctk_global import ctk
from Helper.color_scheme import COLORS

class CanvasZoomController:
    """
    Controls zooming the canvas using GUI buttons.
    Uses class-based architecture and is cross-platform compatible.
    """
    def __init__(self, parent: Any, view: Any, tools: Any) -> None:
        self._parent = parent
        self._view = view
        self._tools = tools

        # Container frame for horizontal alignment of zoom buttons
        self._frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._frame.columnconfigure(0, weight=1)
        self._frame.columnconfigure(1, weight=1)

        # Zoom In Button
        self._zoom_in_btn = ctk.CTkButton(
            self._frame,
            text="🔍 Zoom In",
            command=self._zoom_in,
            fg_color=COLORS.get("primary", "#4F46E5"),
            hover_color=COLORS.get("primary_hover", "#4338CA"),
            height=32,
            corner_radius=6,
            text_color=COLORS.get("text_white", "#FFFFFF")
        )
        self._zoom_in_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        
        # Zoom Out Button
        self._zoom_out_btn = ctk.CTkButton(
            self._frame,
            text="🔍 Zoom Out",
            command=self._zoom_out,
            fg_color=COLORS.get("secondary", "#10B981"),
            hover_color=COLORS.get("secondary_hover", "#059669"),
            height=32,
            corner_radius=6,
            text_color=COLORS.get("text_white", "#FFFFFF")
        )
        self._zoom_out_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self._reset_btn = ctk.CTkButton(
            self._frame, text="Reset View", command=self._view.reset_view,
            fg_color=COLORS.get("surface", "#374151"), height=30, corner_radius=6,
        )
        self._reset_btn.grid(row=1, column=0, padx=(0, 4), pady=(6, 0), sticky="ew")
        self._fit_btn = ctk.CTkButton(
            self._frame, text="Fit Design", command=self._view.fit_design,
            fg_color=COLORS.get("accent", "#7C3AED"), height=30, corner_radius=6,
        )
        self._fit_btn.grid(row=1, column=1, padx=(4, 0), pady=(6, 0), sticky="ew")

        # Set up tooltips if available
        if hasattr(self._tools, "create_tooltip"):
            try:
                self._tools.create_tooltip(self._zoom_in_btn, "Zoom in on the drawing canvas.")
                self._tools.create_tooltip(self._zoom_out_btn, "Zoom out on the drawing canvas.")
            except Exception:
                pass

    def pack(self, **kwargs: Any) -> None:
        """Packs the zoom container frame into the parent layout."""
        self._frame.pack(**kwargs)

    def _zoom_in(self) -> None:
        """Applies zoom-in factor to the canvas view."""
        try:
            self._view.apply_zoom(1.1)
        except Exception:
            pass

    def _zoom_out(self) -> None:
        """Applies zoom-out factor to the canvas view."""
        try:
            self._view.apply_zoom(0.9)
        except Exception:
            pass
