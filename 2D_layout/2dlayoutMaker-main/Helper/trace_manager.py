# Helper/trace_manager.py
import os
import sys
import importlib.util
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# Ensure local Helper imports work properly under collision-prone situations
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# Parent directory should be checked for packages if loaded as a helper
_PARENT_DIR = os.path.dirname(_THIS_DIR)

try:
    from Helper.ctk_global import ctk
except ModuleNotFoundError:
    try:
        from ctk_global import ctk
    except ModuleNotFoundError:
        _spec = importlib.util.spec_from_file_location("mini_autocad_ctk_global", os.path.join(_THIS_DIR, "ctk_global.py"))
        if _spec and _spec.loader:
            _module = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_module)
            ctk = getattr(_module, "ctk")
        else:
            ctk = None

try:
    from Helper.color_scheme import COLORS
except ModuleNotFoundError:
    try:
        from color_scheme import COLORS
    except ModuleNotFoundError:
        _spec = importlib.util.spec_from_file_location("mini_autocad_color_scheme", os.path.join(_THIS_DIR, "color_scheme.py"))
        if _spec and _spec.loader:
            _module = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_module)
            COLORS = getattr(_module, "COLORS", {})
        else:
            COLORS = {}


class TraceImageManager:
    """
    Manages layout image tracing:
    - Loads a background image with low opacity
    - Resizes/rescales the image on zoom changes
    - Allows manual template resizing/scaling (10% to 500%)
    - Allows manual opacity adjustment with dynamic feedback label
    - Allows panning/dragging when unlocked
    - Supports interactive scaling calibration based on drawn polygon segment lengths
    - Provides smooth, modular sidebar UI integration
    - Removes image completely upon request, leaving only drawn lines/polygons
    """
    def __init__(self, tools) -> None:
        self.tools = tools
        self.canvas = tools.canvas
        self.model = tools.model

        # State Variables
        self.original_image = None
        self.tk_image = None
        self.image_id = None
        self.image_path = None
        
        self.opacity = 0.35  # Default low opacity (adjustable by user)
        self.scale = 1.0     # Default trace image scale (adjustable by user)
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.locked = True   # Default locked position
        self.auto_calibrate = True  # Prompt for real-world distance calibration on drawn segment
        self.scale_calibrated = False # Flag indicating if the template has been calibrated once
        
        self.x = 0.0  # Center position in canvas coordinates
        self.y = 0.0
        
        # Dragging state
        self._dragging = False
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0
        
        # UI controls references
        self.remove_btn = None
        self.upload_btn = None
        self.opacity_slider = None
        self.opacity_value_lbl = None
        self.scale_slider = None
        self.scale_value_lbl = None
        self.lock_switch = None
        self.lock_var = None
        self.calibrate_switch = None
        self.calibrate_var = None
        self.instr_label = None

    def upload_image(self) -> bool:
        """Prompts the user to upload a layout image and places it at the viewport center."""
        path = filedialog.askopenfilename(
            title="Select Layout Image for Tracing",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"),
                ("All Files", "*.*")
            ],
            parent=self.tools.root
        )
        if not path:
            return False

        try:
            # Load and convert to RGBA
            img = Image.open(path)
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Limit max dimensions to maintain buttery-smooth performance
            max_dim = 1600
            if img.width > max_dim or img.height > max_dim:
                ratio = max_dim / max(img.width, img.height)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.BILINEAR)

            self.original_image = img
            self.image_path = path
            self.scale = 1.0  # Reset scale to default on new upload
            self.scale_x = 1.0
            self.scale_y = 1.0
            self.scale_calibrated = False  # Reset calibration state on new upload
            self.opacity = 0.35  # Reset opacity to default on new upload

            # Center position inside the current viewport
            width = max(1, self.canvas.winfo_width())
            height = max(1, self.canvas.winfo_height())
            self.x = float(self.canvas.canvasx(width / 2.0))
            self.y = float(self.canvas.canvasy(height / 2.0))

            # Render & Place
            self.render()
            self._setup_events()
            
            # Auto-update UI elements if they exist
            if self.remove_btn:
                self.remove_btn.configure(state="normal")
            if self.lock_var:
                self.lock_var.set(True)
                self.set_locked(True)
            if self.scale_slider:
                self.scale_slider.set(1.0)
            if self.scale_value_lbl:
                self.scale_value_lbl.configure(text="Image Size: 100%")
            if self.opacity_slider:
                self.opacity_slider.set(0.35)
            if self.opacity_value_lbl:
                self.opacity_value_lbl.configure(text="Tracing Opacity: 35%")
            if self.calibrate_var:
                self.calibrate_var.set(True)
                self.auto_calibrate = True
                
            return True
        except Exception as e:
            messagebox.showerror("Image Tracing", f"Failed to load tracing image:\n{e}", parent=self.tools.root)
            return False

    def remove_image(self) -> None:
        """Completely removes the trace image from the canvas."""
        if self.image_id:
            try:
                self.canvas.delete(self.image_id)
            except Exception:
                pass
        self.image_id = None
        self.original_image = None
        self.tk_image = None
        self.image_path = None
        self.scale = 1.0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.opacity = 0.35
        
        # Reset UI
        if self.remove_btn:
            self.remove_btn.configure(state="disabled")
        if self.scale_slider:
            self.scale_slider.set(1.0)
        if self.scale_value_lbl:
            self.scale_value_lbl.configure(text="Image Size: 100%")
        if self.opacity_slider:
            self.opacity_slider.set(0.35)
        if self.opacity_value_lbl:
            self.opacity_value_lbl.configure(text="Tracing Opacity: 35%")
        if self.calibrate_var:
            self.calibrate_var.set(True)
            self.auto_calibrate = True

    def set_opacity(self, opacity: float) -> None:
        """Sets the opacity of the tracing image and triggers a re-render."""
        self.opacity = max(0.01, min(1.0, opacity))
        if self.original_image:
            self.render()

    def set_scale(self, scale: float) -> None:
        """Sets the custom size scale factor and triggers a re-render."""
        self.scale = max(0.05, min(5.0, scale))
        self.scale_x = self.scale
        self.scale_y = self.scale
        if self.original_image:
            self.render()

    def set_locked(self, locked: bool) -> None:
        """Enables or disables manual dragging of the trace image."""
        self.locked = locked
        if not locked:
            # Indicate drag-and-drop capability
            self.canvas.config(cursor="hand2")
        else:
            self.canvas.config(cursor="arrow")

    def render(self) -> None:
        """Applies zoom level, custom scale factor, and opacity to the PIL image and updates canvas."""
        if not self.original_image:
            return

        zoom = self.model.zoom_level
        # Target size integrates both the canvas zoom and user scale factor
        w = max(1, int(self.original_image.width * self.scale_x * zoom))
        h = max(1, int(self.original_image.height * self.scale_y * zoom))

        # 1. Scale image
        resized = self.original_image.resize((w, h), Image.Resampling.BILINEAR)

        # 2. Apply opacity to alpha channel
        r, g, b, a = resized.split()
        a = a.point(lambda p: int(p * self.opacity))
        faded_img = Image.merge("RGBA", (r, g, b, a))

        # 3. Convert to ImageTk
        self.tk_image = ImageTk.PhotoImage(faded_img, master=self.canvas)

        # 4. Draw/update canvas image item
        if self.image_id and self.tools._item_exists(self.image_id):
            self.canvas.itemconfig(self.image_id, image=self.tk_image)
            self.canvas.coords(self.image_id, self.x, self.y)
        else:
            self.image_id = self.canvas.create_image(
                self.x, self.y,
                image=self.tk_image,
                anchor="center",
                tags=("trace_image",)
            )

        self.lower_to_back()

    def update_zoom(self) -> None:
        """Keeps trace image dimensions and position aligned after canvas zoom changes."""
        if self.original_image and self.image_id:
            # Sync position from scaled canvas coords
            coords = self.canvas.coords(self.image_id)
            if coords and len(coords) >= 2:
                self.x, self.y = coords[0], coords[1]
            self.render()

    def lower_to_back(self) -> None:
        """Pushes the tracing background beneath all polygons, furniture and lines."""
        if self.image_id:
            try:
                self.canvas.tag_lower(self.image_id)
                # Keep coordinates grid below the tracing image
                self.canvas.tag_lower("grid")
            except Exception:
                pass

    def _setup_events(self) -> None:
        """Binds canvas drag actions specifically to the trace image when unlocked."""
        self.canvas.tag_bind("trace_image", "<ButtonPress-1>", self._on_drag_start)
        self.canvas.tag_bind("trace_image", "<B1-Motion>", self._on_drag_motion)
        self.canvas.tag_bind("trace_image", "<ButtonRelease-1>", self._on_drag_end)

    def _on_drag_start(self, event) -> None:
        if self.locked or self.tools.canvas_frozen:
            return
        self.canvas.config(cursor="fleur")
        self._dragging = True
        self._drag_start_x = self.canvas.canvasx(event.x)
        self._drag_start_y = self.canvas.canvasy(event.y)

    def _on_drag_motion(self, event) -> None:
        if not self._dragging or self.locked or self.tools.canvas_frozen:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        dx = cx - self._drag_start_x
        dy = cy - self._drag_start_y
        
        self.x += dx
        self.y += dy
        self.canvas.move(self.image_id, dx, dy)
        
        self._drag_start_x = cx
        self._drag_start_y = cy

    def _on_drag_end(self, event) -> None:
        self._dragging = False
        if not self.locked:
            self.canvas.config(cursor="hand2")

    def build_ui(self, parent_frame) -> None:
        """Constructs a responsive, elegant CustomTkinter control panel inside the tab."""
        if not ctk:
            # Fallback to standard Tkinter in case ctk Global module isn't loaded
            lbl = tk.Label(parent_frame, text="CustomTkinter not found")
            lbl.pack()
            return

        # Main wrapper container
        container = ctk.CTkFrame(parent_frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Header Title
        ctk.CTkLabel(
            container,
            text="Image Tracing Panel",
            font=("Arial", 16, "bold"),
            text_color=COLORS.get("text_primary", "#0F172A")
        ).pack(pady=(10, 5))

        # Description
        ctk.CTkLabel(
            container,
            text="Upload an image layout as a background template. You can trace walls or polygons on top of it, then remove the image, leaving only your layout design.",
            font=("Arial", 11),
            text_color=COLORS.get("text_secondary", "#475569"),
            wraplength=220,
            justify="left"
        ).pack(fill="x", pady=(0, 15))

        # Upload Button
        self.upload_btn = ctk.CTkButton(
            container,
            text="🖼️ Upload Layout Image",
            command=self._on_upload_click,
            fg_color=COLORS.get("primary", "#4F46E5"),
            hover_color=COLORS.get("primary_hover", "#4338CA"),
            height=40,
            corner_radius=6,
            font=("Arial", 12, "bold"),
            text_color=COLORS.get("text_white", "#FFFFFF")
        )
        self.upload_btn.pack(fill="x", pady=6)

        # Opacity Slider Frame
        opacity_frame = ctk.CTkFrame(
            container,
            fg_color=COLORS.get("surface", "#1F2937"),
            border_color=COLORS.get("border", "#374151"),
            border_width=1
        )
        opacity_frame.pack(fill="x", pady=5, padx=2)

        self.opacity_value_lbl = ctk.CTkLabel(
            opacity_frame,
            text=f"Tracing Opacity: {int(self.opacity * 100)}%",
            font=("Arial", 11, "bold"),
            text_color=COLORS.get("text_primary", "#F3F4F6")
        )
        self.opacity_value_lbl.pack(anchor="w", padx=10, pady=(8, 2))

        # Opacity Slider
        self.opacity_slider = ctk.CTkSlider(
            opacity_frame,
            from_=0.05,
            to=0.95,
            number_of_steps=18,
            command=self._on_opacity_slide,
            fg_color=COLORS.get("border", "#374151"),
            progress_color=COLORS.get("secondary", "#10B981"),
            button_color=COLORS.get("primary", "#4F46E5"),
            button_hover_color=COLORS.get("primary_hover", "#4338CA")
        )
        self.opacity_slider.set(self.opacity)
        self.opacity_slider.pack(fill="x", padx=10, pady=(2, 6))

        # Scale/Resize Slider Frame
        scale_frame = ctk.CTkFrame(
            container,
            fg_color=COLORS.get("surface", "#1F2937"),
            border_color=COLORS.get("border", "#374151"),
            border_width=1
        )
        scale_frame.pack(fill="x", pady=5, padx=2)

        self.scale_value_lbl = ctk.CTkLabel(
            scale_frame,
            text=f"Image Size: {int(self.scale * 100)}%",
            font=("Arial", 11, "bold"),
            text_color=COLORS.get("text_primary", "#F3F4F6")
        )
        self.scale_value_lbl.pack(anchor="w", padx=10, pady=(8, 2))

        # Scale Slider (10% to 500% size)
        self.scale_slider = ctk.CTkSlider(
            scale_frame,
            from_=0.1,
            to=5.0,
            number_of_steps=98,
            command=self._on_scale_slide,
            fg_color=COLORS.get("border", "#374151"),
            progress_color=COLORS.get("secondary", "#10B981"),
            button_color=COLORS.get("primary", "#4F46E5"),
            button_hover_color=COLORS.get("primary_hover", "#4338CA")
        )
        self.scale_slider.set(self.scale)
        self.scale_slider.pack(fill="x", padx=10, pady=(2, 6))

        # Lock Position Switch
        self.lock_var = tk.BooleanVar(value=self.locked)
        self.lock_switch = ctk.CTkSwitch(
            container,
            text="🔒 Lock Image Position",
            variable=self.lock_var,
            command=self._on_lock_toggle,
            fg_color=(COLORS.get("border", "#D1D5DB"), COLORS.get("border_dark", "#374151")),
            progress_color=COLORS.get("secondary", "#10B981"),
            button_color=COLORS.get("error", "#EF4444"),
            button_hover_color=("#DC2626", "#DC2626"),
            text_color=(COLORS.get("text_primary", "#111827"), COLORS.get("text_white", "#FFFFFF"))
        )
        self.lock_switch.pack(pady=5, padx=10, fill="x")

        # Auto-Calibrate Switch
        self.calibrate_var = tk.BooleanVar(value=self.auto_calibrate)
        self.calibrate_switch = ctk.CTkSwitch(
            container,
            text="📐 Calibrate on Drawing",
            variable=self.calibrate_var,
            command=self._on_calibrate_toggle,
            fg_color=(COLORS.get("border", "#D1D5DB"), COLORS.get("border_dark", "#374151")),
            progress_color=COLORS.get("secondary", "#10B981"),
            button_color=COLORS.get("error", "#EF4444"),
            button_hover_color=("#DC2626", "#DC2626"),
            text_color=(COLORS.get("text_primary", "#111827"), COLORS.get("text_white", "#FFFFFF"))
        )
        self.calibrate_switch.pack(pady=5, padx=10, fill="x")

        # Position Instructions
        self.instr_label = ctk.CTkLabel(
            container,
            text="💡 Tip: With 'Calibrate on Drawing' checked, drawing your first polygon segment will prompt you for its real length to calibrate the background scale automatically.",
            font=("Arial", 10),
            text_color=COLORS.get("text_secondary", "#9CA3AF"),
            wraplength=220,
            justify="center"
        )
        self.instr_label.pack(fill="x", pady=(10, 10))

        # Remove/Clean Button
        self.remove_btn = ctk.CTkButton(
            container,
            text="🗑️ Remove Layout Image",
            command=self._on_remove_click,
            fg_color=COLORS.get("error", "#EF4444"),
            hover_color="#DC2626",
            height=36,
            corner_radius=6,
            font=("Arial", 11, "bold"),
            text_color=COLORS.get("text_white", "#FFFFFF"),
            state="normal" if self.original_image else "disabled"
        )
        self.remove_btn.pack(fill="x", pady=6)

    def _on_upload_click(self) -> None:
        if self.upload_image():
            if self.remove_btn:
                self.remove_btn.configure(state="normal")
            if self.lock_var:
                self.lock_var.set(True)
                self.set_locked(True)

    def _on_opacity_slide(self, val) -> None:
        opacity_val = float(val)
        self.set_opacity(opacity_val)
        if self.opacity_value_lbl:
            self.opacity_value_lbl.configure(text=f"Tracing Opacity: {int(opacity_val * 100)}%")

    def _on_scale_slide(self, val) -> None:
        scale_val = float(val)
        self.set_scale(scale_val)
        if self.scale_value_lbl:
            self.scale_value_lbl.configure(text=f"Image Size: {int(scale_val * 100)}%")

    def _on_lock_toggle(self) -> None:
        self.set_locked(bool(self.lock_var.get()))

    def _on_calibrate_toggle(self) -> None:
        self.auto_calibrate = bool(self.calibrate_var.get())
        if self.auto_calibrate:
            self.scale_calibrated = False

    def _on_remove_click(self) -> None:
        self.remove_image()
        if self.remove_btn:
            self.remove_btn.configure(state="disabled")
