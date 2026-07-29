from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import ttk
import importlib.util
import os
import sys


def _import_local_set_window_icon():
    """
    VastuApp may have a different top-level `Helper` already imported.
    Load MiniAutoCAD's `Helper/set_window_icon.py` via file path to avoid collisions.
    """
    helper_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(helper_dir, "set_window_icon.py")
    spec = importlib.util.spec_from_file_location("_mini_autocad_set_window_icon_ui_text_windows", path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Unable to load set_window_icon from '{path}'")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
    except Exception:
        pass
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return getattr(module, "set_window_icon")


set_window_icon = _import_local_set_window_icon()


class CTKTextTool:
    """
    CTK-based Text tool similar to CTK shapes
    - Opens a dialog with text input and formatting options
    - Live preview of the text with formatting
    - Text appears as movable overlay on canvas
    - Press Enter to commit, Esc to cancel
    - Right-click for edit/copy/delete options
    """

    def __init__(self, app):
        self.app = app
        # Active text overlay state
        self.active_text = None  # dict: {content, x, y, formatting, size}
        self.active_handles = []  # canvas ids for corner handles
        self.active_canvas_items = []  # text preview ids on canvas
        self.drag_state = None  # {mode: 'move'|'resize', handle_idx, start_pos}
        self.preview_dialog = None
        # Committed texts for re-edit/duplicate
        self.committed_texts = []  # list of dicts with text data

        # Handle visuals
        self.handle_radius = 5

        # Install global bindings
        self.install_global_bindings()

        # Load icon images (if needed)
        self.icon_files = {
            "bathroom": "assets/Images/bathroom.png",
            "toilet": "assets/Images/toilet.png",
            "chair": "assets/Images/chair.png",
            "table": "assets/Images/table.png"
        }
        from PIL import Image as PILImage
        self.icon_images = {}
        for key, path in self.icon_files.items():
            try:
                img = PILImage.open(path).resize((48, 48))
                # Store as PIL Image, not PhotoImage
                self.icon_images[key] = img
            except Exception as e:
                print(f"Could not load {key}: {e}")
                self.icon_images[key] = None

    def install_global_bindings(self):
        """Install global keyboard shortcuts"""
        try:
            # Right-click for context menu on canvas
            if hasattr(self.app, 'canvas'):
                # Match shape tools: standard right-click (Button-3) + Ctrl+Click
                self.app.canvas.bind("<Button-3>", self._on_canvas_right_click, add="+")
                self.app.canvas.bind("<Button-2>", self._on_canvas_right_click, add="+")
                self.app.canvas.bind("<Control-Button-1>", self._on_canvas_right_click, add="+")
        except Exception:
            pass

    # ---- Canvas/image coordinate mapping ----
    def image_to_canvas(self, x, y):
        img_w, img_h = self.app.image.size
        can_w, can_h = self.app.canvas.winfo_width(), self.app.canvas.winfo_height()
        scale = min(can_w / img_w, can_h / img_h, 1) * self.app.zoom_factor
        new_size = (int(img_w * scale), int(img_h * scale))
        pan_x, pan_y = getattr(self.app.zoom_flip_tools, "pan_offset", [0, 0])
        x_offset = (can_w - new_size[0]) // 2 + pan_x
        y_offset = (can_h - new_size[1]) // 2 + pan_y
        return (x * scale + x_offset, y * scale + y_offset)

    def canvas_to_image(self, x, y):
        img_w, img_h = self.app.image.size
        can_w, can_h = self.app.canvas.winfo_width(), self.app.canvas.winfo_height()
        scale = min(can_w / img_w, can_h / img_h, 1) * self.app.zoom_factor
        new_size = (int(img_w * scale), int(img_h * scale))
        pan_x, pan_y = getattr(self.app.zoom_flip_tools, "pan_offset", [0, 0])
        x_offset = (can_w - new_size[0]) // 2 + pan_x
        y_offset = (can_h - new_size[1]) // 2 + pan_y
        return ((x - x_offset) / scale, (y - y_offset) / scale)

    # ---- Public API: toolbar hook ----
    def open_text_dialog(self, initial_text_data=None):
        """Open the text input dialog with formatting options.

        If initial_text_data is provided, dialog works in *edit* mode and
        updates the existing text at the same position instead of creating
        a brand‑new centered text.
        """
        if getattr(self.app, "image", None) is None:
            messagebox.showinfo("Add Text", "Please open an image first.", parent=self.app.root)
            return

        # Close existing dialog if any
        try:
            if self.preview_dialog and self.preview_dialog.winfo_exists():
                self.preview_dialog.destroy()
        except Exception:
            pass

        dialog = tk.Toplevel(self.app.root)
        dialog.title("Add Text")
        dialog.grab_set()
        set_window_icon(dialog)
        self.preview_dialog = dialog

        # Size and center - smaller and better looking
        dialog.resizable(False, False)
        try:
            dw, dh = 550, 420
            dialog.geometry(f"{dw}x{dh}")
            dialog.update_idletasks()
            sw = dialog.winfo_screenwidth()
            sh = dialog.winfo_screenheight()
            x = (sw - dw) // 2
            y = (sh - dh) // 2
            dialog.geometry(f"{dw}x{dh}+{x}+{y}")
        except Exception:
            pass

        # Are we editing an existing committed text?
        is_edit = isinstance(initial_text_data, dict)

        # Variables
        text_var = tk.StringVar(value="")
        bold_var = tk.BooleanVar(value=False)
        italic_var = tk.BooleanVar(value=False)
        size_var = tk.IntVar(value=24)  # Font size in pixels (12-48)
        color_var = tk.StringVar(value=getattr(self.app, "brush_color", "#000000"))
        selected_icon_var = tk.StringVar(value="")  # Not used anymore, kept for compatibility
        text_box_var = tk.BooleanVar(value=False)  # Not used anymore, kept for compatibility

        # Layout - compact and better looking
        content = ttk.Frame(dialog, padding=15)
        content.pack(fill="both", expand=True)

        # Left: form (compact)
        form = ttk.Frame(content)
        form.pack(side="left", fill="y", padx=(0, 12))

        # Right: preview canvas (smaller)
        preview_panel = ttk.Frame(content)
        preview_panel.pack(side="left", fill="both", expand=True)
        preview_canvas = tk.Canvas(preview_panel, width=240, height=280, bg="#ffffff", 
                                  highlightthickness=1, relief=tk.SUNKEN, borderwidth=1)
        preview_canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # Live preview function (define before using)
        def update_preview():
            try:
                self._draw_text_preview(preview_canvas, text_entry.get("1.0", "end-1c"), 
                                       bold_var.get(), italic_var.get(), size_var.get(), 
                                       color_var.get(), selected_icon_var.get(), text_box_var.get())
            except Exception as e:
                print(f"Preview update error: {e}")
        
        # Bind resize events to update preview when window/canvas is resized
        def on_canvas_resize(event=None):
            try:
                update_preview()
            except Exception:
                pass
        
        def on_dialog_resize(event=None):
            try:
                dialog.update_idletasks()
                update_preview()
            except Exception:
                pass
        
        preview_canvas.bind("<Configure>", on_canvas_resize)
        dialog.bind("<Configure>", on_dialog_resize)

        # Title
        title_label = ttk.Label(form, text="Insert Text", font=("Arial", 13, "bold"))
        title_label.pack(anchor="w", pady=(0, 12))
        
        # Text input (compact)
        text_row = ttk.Frame(form)
        text_row.pack(fill="x", pady=(0, 8))
        ttk.Label(text_row, text="Text:", font=("Arial", 10)).pack(side="top", anchor="w")
        text_entry = tk.Text(text_row, width=28, height=4, font=("Arial", 10), wrap=tk.WORD)
        text_entry.pack(side="top", pady=(4, 0))
        text_entry.bind("<KeyRelease>", lambda e: update_preview())

        # Pre-fill dialog if editing existing text
        if is_edit:
            try:
                text_entry.insert("1.0", initial_text_data.get("content", ""))
                bold_var.set(bool(initial_text_data.get("bold", False)))
                italic_var.set(bool(initial_text_data.get("italic", False)))
                size_var.set(int(initial_text_data.get("size", 24)))
                color_var.set(initial_text_data.get("color", getattr(self.app, "brush_color", "#000000")))
            except Exception:
                # Fall back silently; user can still edit values
                pass

        # Formatting options (compact)
        format_label = ttk.Label(form, text="Formatting:", font=("Arial", 10))
        format_label.pack(anchor="w", pady=(8, 4))

        # Bold and Italic in one row
        format_row = ttk.Frame(form)
        format_row.pack(fill="x", pady=(0, 8))
        bold_cb = ttk.Checkbutton(format_row, text="Bold", variable=bold_var, command=update_preview)
        bold_cb.pack(side="left", padx=(0, 15))
        italic_cb = ttk.Checkbutton(format_row, text="Italic", variable=italic_var, command=update_preview)
        italic_cb.pack(side="left")

        # Size slider (compact)
        size_label_frame = ttk.Frame(form)
        size_label_frame.pack(fill="x", pady=(8, 4))
        ttk.Label(size_label_frame, text="Size:", font=("Arial", 10)).pack(side="left")
        size_value_label = ttk.Label(size_label_frame, text="24px", font=("Arial", 10))
        size_value_label.pack(side="right")
        
        def on_size_change(value):
            size_value_label.configure(text=f"{int(float(value))}px")
            size_var.set(int(float(value)))
            update_preview()
        
        size_slider = ttk.Scale(form, from_=12, to=72, 
                                variable=size_var, command=on_size_change, orient=tk.HORIZONTAL)
        size_slider.pack(fill="x", pady=(0, 8))

        # Color picker (compact)
        color_row = ttk.Frame(form)
        color_row.pack(fill="x", pady=(8, 12))
        ttk.Label(color_row, text="Color:", font=("Arial", 10)).pack(side="left")
        color_entry = ttk.Entry(color_row, textvariable=color_var, width=12, font=("Arial", 9))
        color_entry.pack(side="left", padx=(6, 4))

        def pick_color():
            from tkinter import colorchooser
            color = colorchooser.askcolor(title="Choose Text Color", parent=dialog)
            if color and color[1]:
                color_var.set(color[1])
                update_preview()

        ttk.Button(color_row, text="Pick", width=7, command=pick_color).pack(side="left")

        # Initial preview
        self._draw_text_preview(preview_canvas, "", False, False, "normal", color_var.get(), "", False)
        try:
            dialog.after(100, update_preview)
        except Exception:
            pass

        # Buttons (better styling)
        btns = ttk.Frame(dialog, padding=10)
        btns.pack(fill="x", pady=(0, 0))

        def on_create():
            content = text_entry.get("1.0", "end-1c").strip()
            if not content:
                messagebox.showwarning("Add Text", "Please enter some text.", parent=dialog)
                return
            
            # Create or update text overlay
            if is_edit:
                # Preserve original position when editing
                pos = (
                    float(initial_text_data.get("x", 0.0)),
                    float(initial_text_data.get("y", 0.0)),
                )
                self._create_text_overlay(
                    content=content,
                    bold=bold_var.get(),
                    italic=italic_var.get(),
                    size=size_var.get(),
                    color=color_var.get(),
                    icon="",
                    text_box=False,
                    position=pos,
                )
            else:
                # New text: center in layout / image
                self._create_text_overlay(
                    content=content,
                    bold=bold_var.get(),
                    italic=italic_var.get(),
                    size=size_var.get(),
                    color=color_var.get(),
                    icon="",
                    text_box=False,
                )
            dialog.destroy()

        # Create button
        create_btn = ttk.Button(btns, text="Insert", command=on_create, width=12)
        create_btn.pack(side="right", padx=(6, 0))
        
        # Cancel button
        cancel_btn = ttk.Button(btns, text="Cancel", command=dialog.destroy, width=12)
        cancel_btn.pack(side="right", padx=0)

    def _draw_text_preview(self, canvas, text, bold, italic, size, color, icon, text_box=False):
        """Draw live preview of text with formatting"""
        canvas.delete("all")
        
        # Update canvas to ensure accurate size measurements
        try:
            canvas.update_idletasks()
        except Exception:
            pass
        
        # Get canvas dimensions - use actual size
        try:
            w_cur = int(canvas.winfo_width())
            h_cur = int(canvas.winfo_height())
        except Exception:
            w_cur, h_cur = 0, 0
        
        # If canvas hasn't been rendered yet, use requested or configured size
        if w_cur <= 1 or h_cur <= 1:
            try:
                w_req = int(canvas.winfo_reqwidth())
                h_req = int(canvas.winfo_reqheight())
            except Exception:
                w_req, h_req = 0, 0
            try:
                w_attr = int(canvas.cget("width"))
                h_attr = int(canvas.cget("height"))
            except Exception:
                w_attr, h_attr = 380, 400
            w = max(w_req, w_attr, 380) if w_cur <= 1 else w_cur
            h = max(h_req, h_attr, 400) if h_cur <= 1 else h_cur
        else:
            w = w_cur
            h = h_cur
        
        cx, cy = w // 2, h // 2
        
        # Header
        canvas.create_text(cx, 20, text="Live Preview", fill="#34495e", font=("Helvetica", 12, "bold"))
        
        if not text.strip():
            canvas.create_text(cx, cy, text="Enter text to preview", fill="#95a5a6", 
                             font=("Helvetica", 11, "italic"))
            return
        
        # Determine font size - size is now an integer directly
        base_size = int(size) if isinstance(size, (int, float)) else 24
        
        font_style = []
        if bold:
            font_style.append("bold")
        if italic:
            font_style.append("italic")
        
        font_tuple = ("Helvetica", base_size, " ".join(font_style) if font_style else "normal")
        
        # Draw icon if selected
        y_offset = cy - 40
        if icon and icon in self.icon_images and self.icon_images[icon]:
            try:
                from PIL import ImageTk
                icon_img = self.icon_images[icon]
                icon_photo = ImageTk.PhotoImage(icon_img)
                # Store reference to prevent garbage collection
                canvas.icon_photo = icon_photo
                canvas.create_image(cx, y_offset, image=icon_photo)
                y_offset += 60
            except Exception as e:
                print(f"Error displaying icon: {e}")
        
        # Calculate text dimensions for box
        lines = text.split('\n')
        text_items = []
        max_width = 0
        
        # Measure text first
        try:
            import tkinter.font as tkfont
            font_obj = tkfont.Font(family="Helvetica", size=base_size, 
                                  weight="bold" if bold else "normal",
                                  slant="italic" if italic else "roman")
            for line in lines:
                line_width = font_obj.measure(line)
                max_width = max(max_width, line_width)
        except Exception:
            for line in lines:
                max_width = max(max_width, len(line) * base_size * 0.6)
        
        # Calculate total height
        total_height = len(lines) * (base_size + 4) - 4  # Remove extra spacing after last line
        
        # Draw box if enabled (draw first, behind text)
        if text_box and lines:
            padding = 10
            box_x0 = cx - max_width / 2 - padding
            box_y0 = y_offset - padding
            box_x1 = cx + max_width / 2 + padding
            box_y1 = y_offset + total_height + padding
            
            # White background with blue border
            canvas.create_rectangle(box_x0, box_y0, box_x1, box_y1, 
                                   fill="#ffffff", outline="#2980b9", width=2)
        
        # Draw text lines on top of box
        for i, line in enumerate(lines):
            y_pos = y_offset + i * (base_size + 4)
            canvas.create_text(cx, y_pos, text=line, 
                             fill=color, font=font_tuple)

    def _create_text_overlay(self, content, bold, italic, size, color, icon, text_box=False, position=None):
        """Create text as movable overlay.

        If position is provided (image‑space x,y), the new overlay will start
        exactly at that position; otherwise it is centered in layout/image.
        """
        # Center in layout or image, unless explicit position provided
        if position is not None:
            cx, cy = position
        else:
            img_w, img_h = self.app.image.size
            cx, cy = img_w // 2, img_h // 2
            if hasattr(self.app, "layout_rect") and self.app.layout_rect:
                x0, y0, x1, y1 = self.app.layout_rect
                cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        
        # Store text data
        self.active_text = {
            "content": content,
            "x": cx,
            "y": cy,
            "bold": bold,
            "italic": italic,
            "size": size,
            "color": color,
            "icon": icon,
            "text_box": text_box
        }
        
        self._set_active_text()

    def _set_active_text(self):
        """Set active text and bind controls"""
        if not self.active_text:
            return
        
        # Clear previous overlay
        self._clear_active_overlay()
        
        # Bind commit/cancel
        self.app.canvas.bind("<Double-Button-1>", self.commit_active_text)
        self.app.canvas.bind("<Return>", self.commit_active_text)
        try:
            self.app.root.bind("<Return>", self.commit_active_text)
        except Exception:
            pass
        self.app.canvas.bind("<Escape>", self.cancel_active_text)
        self.app.canvas.bind("<Button-1>", self._on_mouse_down)
        self.app.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.app.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        
        self._draw_active_overlay()
        
        # Focus canvas
        try:
            self.app.canvas.focus_set()
        except Exception:
            pass
        
        if hasattr(self.app, 'update_status'):
            self.app.update_status("Text overlay active. Drag to move. Press Enter to commit or Esc to cancel.")

    def _draw_active_overlay(self):
        """Draw text overlay on canvas with handles"""
        if not self.active_text:
            return
        
        # Clear previous items
        for cid in self.active_canvas_items:
            try:
                self.app.canvas.delete(cid)
            except Exception:
                pass
        self.active_canvas_items = []
        
        content = self.active_text["content"]
        x, y = self.active_text["x"], self.active_text["y"]
        bold = self.active_text["bold"]
        italic = self.active_text["italic"]
        size = self.active_text["size"]
        color = self.active_text["color"]
        icon = self.active_text["icon"]
        text_box = self.active_text.get("text_box", False)
        
        # Convert to canvas coords
        cx, cy = self.image_to_canvas(x, y)
        
        # Determine font size - size is now an integer directly
        base_size = int(size) if isinstance(size, (int, float)) else 24
        
        font_style = []
        if bold:
            font_style.append("bold")
        if italic:
            font_style.append("italic")
        
        font_tuple = ("Helvetica", base_size, " ".join(font_style) if font_style else "normal")
        
        # Draw icon if present
        y_offset = cy
        if icon and icon in self.icon_images and self.icon_images[icon]:
            try:
                from PIL import ImageTk
                icon_img = self.icon_images[icon]
                icon_photo = ImageTk.PhotoImage(icon_img)
                # Store reference
                if not hasattr(self, '_icon_photo_refs'):
                    self._icon_photo_refs = []
                self._icon_photo_refs.append(icon_photo)
                icon_id = self.app.canvas.create_image(cx, y_offset, image=icon_photo)
                self.active_canvas_items.append(icon_id)
                y_offset += 60
            except Exception as e:
                print(f"Error displaying icon: {e}")
        
        # Draw text lines
        lines = content.split('\n')
        text_ids = []
        text_positions = []
        max_width = 0
        
        for i, line in enumerate(lines):
            y_pos = y_offset + i * (base_size + 4)
            text_id = self.app.canvas.create_text(cx, y_pos, 
                                                  text=line, fill=color, font=font_tuple, 
                                                  tags="active_text")
            self.active_canvas_items.append(text_id)
            text_ids.append(text_id)
            text_positions.append((cx, y_pos, line))
            
            # Measure width
            try:
                bbox = self.app.canvas.bbox(text_id)
                if bbox:
                    width = bbox[2] - bbox[0]
                    max_width = max(max_width, width)
            except Exception:
                pass
        
        # Draw box if enabled
        if text_box and text_positions:
            padding = 10
            # Get overall bounding box
            bbox = self.app.canvas.bbox("active_text")
            if bbox:
                x0, y0, x1, y1 = bbox
                # Add padding
                x0 -= padding
                y0 -= padding
                x1 += padding
                y1 += padding
                
                # Draw white background with blue border (behind text)
                box_id = self.app.canvas.create_rectangle(x0, y0, x1, y1, 
                                                         fill="#ffffff", outline="#2980b9", 
                                                         width=2, tags="active_text_bg")
                self.active_canvas_items.insert(0, box_id)  # Insert at beginning
                # Lower box behind text
                self.app.canvas.tag_lower(box_id, "active_text")
        
        # Draw bounding box and handles
        if text_ids:
            # Get bounding box of all text items
            bbox = self.app.canvas.bbox("active_text")
            if bbox:
                x0, y0, x1, y1 = bbox
                # Expand bbox slightly
                padding = 10
                x0 -= padding
                y0 -= padding
                x1 += padding
                y1 += padding
                
                # Draw rectangle
                rect_id = self.app.canvas.create_rectangle(x0, y0, x1, y1, 
                                                          outline="#2980b9", width=2, 
                                                          dash=(4, 4), tags="active_text_box")
                self.active_canvas_items.append(rect_id)
                
                # Draw corner handles
                corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                self._draw_handles(corners)

    def _draw_handles(self, points):
        """Draw resize handles at given points"""
        for cid in self.active_handles:
            try:
                self.app.canvas.delete(cid)
            except Exception:
                pass
        self.active_handles = []
        
        r = self.handle_radius
        for px, py in points:
            handle = self.app.canvas.create_oval(px - r, py - r, px + r, py + r, 
                                                fill="#ffffff", outline="#2980b9", width=2)
            self.active_handles.append(handle)

    def _hit_handle(self, x, y):
        """Check if click is on a handle"""
        for i, handle_id in enumerate(self.active_handles):
            coords = self.app.canvas.coords(handle_id)
            if coords:
                x0, y0, x1, y1 = coords
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return i
        return None

    def _on_mouse_down(self, event):
        """Handle mouse down for moving text"""
        if not self.active_text:
            return
        
        # Check if clicked on text or box
        items = self.app.canvas.find_overlapping(event.x - 5, event.y - 5, event.x + 5, event.y + 5)
        if any(item in self.active_canvas_items or item in self.active_handles for item in items):
            self.drag_state = {
                "mode": "move",
                "start": (event.x, event.y),
                "start_text_pos": (self.active_text["x"], self.active_text["y"])
            }

    def _on_mouse_move(self, event):
        """Handle mouse move for dragging text"""
        if not self.drag_state or self.drag_state.get("mode") != "move":
            return
        
        # Calculate delta in image space
        sx, sy = self.drag_state["start"]
        dx_canvas = event.x - sx
        dy_canvas = event.y - sy
        
        # Convert delta to image space
        img_w, img_h = self.app.image.size
        can_w, can_h = self.app.canvas.winfo_width(), self.app.canvas.winfo_height()
        scale = min(can_w / img_w, can_h / img_h, 1) * self.app.zoom_factor
        dx_img = dx_canvas / scale
        dy_img = dy_canvas / scale
        
        # Update text position
        start_x, start_y = self.drag_state["start_text_pos"]
        self.active_text["x"] = start_x + dx_img
        self.active_text["y"] = start_y + dy_img
        
        self._refresh_overlay()

    def _on_mouse_up(self, event):
        """Handle mouse up"""
        self.drag_state = None

    def _refresh_overlay(self):
        """Refresh the overlay display"""
        self._draw_active_overlay()

    def cancel_active_text(self, event=None):
        """Cancel active text overlay"""
        self._clear_active_overlay()
        self.active_text = None
        if hasattr(self.app, 'update_status'):
            self.app.update_status("Text cancelled.")

    def commit_active_text(self, event=None):
        """Commit active text to drawing layer"""
        if not self.active_text:
            return
        
        try:
            self.app.push_undo()
        except Exception:
            pass
        
        # Ensure drawing layer exists
        if self.app.drawing_layer is None or self.app.drawing_layer.size != self.app.image.size:
            self.app.drawing_layer = Image.new("RGBA", self.app.image.size, (0, 0, 0, 0))
            self.app.drawing_draw = ImageDraw.Draw(self.app.drawing_layer)
        
        # Rasterize text to drawing layer
        self._rasterize_text(self.app.drawing_draw, self.active_text)
        
        # Add to committed list for re-editing
        self.committed_texts.append(self.active_text.copy())
        
        # Clear overlay
        self._clear_active_overlay()
        self.active_text = None
        
        # Rebuild and refresh
        self.app.prepare_image()
        
        if hasattr(self.app, 'update_status'):
            self.app.update_status("Text committed successfully!")

    def _rasterize_text(self, draw, text_data):
        """Rasterize text to the drawing layer"""
        # Ensure drawing layer exists
        if self.app.drawing_layer is None or self.app.drawing_layer.size != self.app.image.size:
            self.app.drawing_layer = Image.new("RGBA", self.app.image.size, (0, 0, 0, 0))
            self.app.drawing_draw = ImageDraw.Draw(self.app.drawing_layer)
        
        content = text_data["content"]
        x, y = text_data["x"], text_data["y"]
        bold = text_data["bold"]
        italic = text_data["italic"]
        size = text_data["size"]
        color = text_data["color"]
        icon = text_data["icon"]
        text_box = text_data.get("text_box", False)
        
        # Determine font size - size is now an integer directly
        base_size = int(size) if isinstance(size, (int, float)) else 24
        
        # Get font file - try multiple paths for macOS compatibility
        font = None
        font_paths = []
        
        # Build paths relative to the editLayout directory and root
        import os
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # editLayout dir
        root_dir = os.path.dirname(script_dir)  # Desktop-VASTUZone dir
        
        if bold and italic:
            font_paths = [
                os.path.join(script_dir, "DejaVuSans-BoldOblique.ttf"),
                os.path.join(root_dir, "DejaVuSans-BoldOblique.ttf"),
                "DejaVuSans-BoldOblique.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
            ]
        elif bold:
            font_paths = [
                os.path.join(script_dir, "DejaVuSans-Bold.ttf"),
                os.path.join(root_dir, "DejaVuSans-Bold.ttf"),
                "DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            ]
        elif italic:
            font_paths = [
                os.path.join(script_dir, "DejaVuSans-Oblique.ttf"),
                os.path.join(root_dir, "DejaVuSans-Oblique.ttf"),
                "DejaVuSans-Oblique.ttf",
                "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
            ]
        else:
            font_paths = [
                os.path.join(script_dir, "DejaVuSans.ttf"),
                os.path.join(root_dir, "DejaVuSans.ttf"),
                "DejaVuSans.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
        
        # Try each font path
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, base_size)
                print(f"Loaded font: {font_path}")
                break
            except Exception as e:
                continue
        
        # If all failed, use system default
        if font is None:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", base_size)
                print(f"Using Helvetica system font")
            except Exception:
                font = ImageFont.load_default()
                print(f"Warning: Could not load any TrueType font, using default font")
        
        # Draw icon if present
        y_cursor = y
        if icon and icon in self.icon_images and self.icon_images[icon]:
            try:
                icon_img = self.icon_images[icon]
                icon_x = int(x - icon_img.width // 2)
                icon_y = int(y_cursor - icon_img.height // 2)
                self.app.drawing_layer.paste(icon_img, (icon_x, icon_y), icon_img)
                y_cursor += 60
            except Exception as e:
                print(f"Error pasting icon: {e}")
        
        # Measure text dimensions
        lines = content.split('\n')
        max_width = 0
        total_height = 0
        line_info = []
        
        for line in lines:
            # Get text size
            try:
                bbox = font.getbbox(line)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except Exception:
                text_w = font.getlength(line)
                text_h = base_size
            
            max_width = max(max_width, text_w)
            line_info.append((line, text_w, text_h))
            total_height += base_size + 4
        
        # Draw box if enabled
        if text_box and lines:
            padding = 10
            box_x0 = int(x - max_width / 2 - padding)
            box_y0 = int(y_cursor - padding)
            box_x1 = int(x + max_width / 2 + padding)
            box_y1 = int(y_cursor + total_height + padding)
            
            # Draw white background
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill="#ffffff", outline=None)
            # Draw blue border
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=None, outline="#2980b9", width=2)
        
        # Draw text lines
        for line, text_w, text_h in line_info:
            # Center text
            text_x = x - text_w / 2
            
            # Draw with shadow for better readability
            shadow_offset = 1
            draw.text((text_x + shadow_offset, y_cursor + shadow_offset), line, 
                     fill="#00000040", font=font)
            
            # Draw main text
            draw.text((text_x, y_cursor), line, fill=color, font=font)
            
            # Simulate bold if needed and font doesn't support it natively
            # (This is a fallback for when proper bold fonts aren't available)
            if bold and "Helvetica" in str(font.path if hasattr(font, 'path') else ''):
                # Draw text again with slight offset for bold effect
                draw.text((text_x + 0.5, y_cursor), line, fill=color, font=font)
                draw.text((text_x, y_cursor + 0.5), line, fill=color, font=font)
            
            y_cursor += base_size + 4

    def _clear_active_overlay(self):
        """Clear active overlay from canvas"""
        for cid in self.active_canvas_items:
            try:
                self.app.canvas.delete(cid)
            except Exception:
                pass
        self.active_canvas_items = []
        
        for cid in self.active_handles:
            try:
                self.app.canvas.delete(cid)
            except Exception:
                pass
        self.active_handles = []
        
        # Unbind events
        try:
            self.app.canvas.unbind("<Double-Button-1>")
            self.app.canvas.unbind("<Return>")
            self.app.canvas.unbind("<Escape>")
            self.app.canvas.unbind("<Button-1>")
            self.app.canvas.unbind("<B1-Motion>")
            self.app.canvas.unbind("<ButtonRelease-1>")
        except Exception:
            pass

    # ===== Context menu support =====
    def _on_canvas_right_click(self, event):
        """Handle right-click for text selection"""
        if not self.app.image:
            return
        
        # Check if clicked on committed text
        cx, cy = event.x, event.y
        hit_idx = self._hit_test_committed(cx, cy)
        
        if hit_idx is not None:
            menu = tk.Menu(self.app.canvas, tearoff=0)
            menu.add_command(label="Edit Text", command=lambda: self._edit_selected_text(hit_idx))
            menu.add_command(label="Duplicate Text", command=lambda: self._duplicate_selected_text(hit_idx))
            menu.add_command(label="Delete Text", command=lambda: self._delete_selected_text(hit_idx))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

    def _hit_test_committed(self, cx, cy):
        """Check if canvas point hits a committed text"""
        # Convert to image coords
        ix, iy = self.canvas_to_image(cx, cy)
        
        # Check each committed text (in reverse order, newest first)
        for idx in range(len(self.committed_texts) - 1, -1, -1):
            text_data = self.committed_texts[idx]
            tx, ty = text_data["x"], text_data["y"]
            
            # Rough hit test (within 50px radius)
            if abs(ix - tx) < 50 and abs(iy - ty) < 50:
                return idx
        
        return None

    def _edit_selected_text(self, idx):
        """Edit a committed text via the full text dialog.

        The existing text is removed from the drawing layer and opened
        in the dialog; after editing, it will be re‑committed at the
        same position.
        """
        if 0 <= idx < len(self.committed_texts):
            text_data = self.committed_texts[idx].copy()
            try:
                self.app.push_undo()
            except Exception:
                pass

            # Remove this text from committed list and from drawing layer
            self.committed_texts.pop(idx)
            self._rebuild_drawing_layer()

            # Open dialog pre‑filled with this text's properties
            self.open_text_dialog(initial_text_data=text_data)

    def _duplicate_selected_text(self, idx):
        """Duplicate a committed text"""
        if 0 <= idx < len(self.committed_texts):
            text_data = self.committed_texts[idx].copy()
            # Offset position slightly
            text_data["x"] += 20
            text_data["y"] += 20
            
            try:
                self.app.push_undo()
            except Exception:
                pass
            
            # Add as new committed text
            self.committed_texts.append(text_data)
            self._rebuild_drawing_layer()
            self.app.prepare_image()

    def _delete_selected_text(self, idx):
        """Delete a committed text"""
        if 0 <= idx < len(self.committed_texts):
            try:
                self.app.push_undo()
            except Exception:
                pass
            
            self.committed_texts.pop(idx)
            self._rebuild_drawing_layer()
            self.app.prepare_image()

    def _rebuild_drawing_layer(self):
        """Rebuild drawing layer with all committed texts.

        Important: preserve any committed shapes/overlays (grid, compass, etc.)
        and then draw text on top, instead of leaving old text pixels behind.
        """
        # First, ask shapes tool to rebuild its committed content if available
        try:
            shapes_tools = getattr(self.app, "shapes_tools", None)
            if shapes_tools is not None and hasattr(shapes_tools, "_redraw_all_committed_shapes"):
                # This will create a fresh transparent drawing_layer, redraw shapes,
                # and re-apply compass overlays based on _last_compass_* helpers.
                shapes_tools._redraw_all_committed_shapes()
            else:
                # Fallback: start from a clean transparent layer
                self.app.drawing_layer = Image.new("RGBA", self.app.image.size, (0, 0, 0, 0))
                self.app.drawing_draw = ImageDraw.Draw(self.app.drawing_layer)
        except Exception:
            # If anything goes wrong, still ensure we have a valid empty layer
            try:
                self.app.drawing_layer = Image.new("RGBA", self.app.image.size, (0, 0, 0, 0))
                self.app.drawing_draw = ImageDraw.Draw(self.app.drawing_layer)
            except Exception:
                return

        # Re-rasterize all committed texts on top of shapes/overlays
        for text_data in self.committed_texts:
            self._rasterize_text(self.app.drawing_draw, text_data)

    def _clear_canvas_bindings(self):
        """Clear canvas bindings"""
        try:
            self.app.canvas.unbind("<Button-1>")
            self.app.canvas.unbind("<B1-Motion>")
            self.app.canvas.unbind("<ButtonRelease-1>")
        except Exception:
            pass
