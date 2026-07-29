# import tkinter as tk
# from tkinter import ttk
# from PIL import Image, ImageTk
# import os

# HANDLE_SIZE = 8

# def find_image_path(name):
#     """Find the path for the furniture image, supporting .png and .jpeg."""
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     for ext in ('png', 'jpeg', 'jpg'):
#         path = os.path.join(base_dir, "Images", f"{name}.{ext}")
#         if os.path.exists(path):
#             return path
#     return None

# class Furniture:
#     def __init__(self, canvas, image_path, x, y, select_callback,scale,angle,get_freeze_state):
#         self.image_path = image_path
#         self.canvas = canvas
#         self.original_image = Image.open(image_path).convert("RGBA")
#         self.angle = angle
#         self.scale = scale
#         self.update_image()
#         self.image_id = self.canvas.create_image(x, y, image=self.tk_image, anchor="center",tags=("furniture",))
#         self.select_callback = select_callback
#         self.canvas.tag_bind(self.image_id, "<ButtonPress-1>", self._on_left_click)
#         self.canvas.tag_bind(self.image_id, "<B1-Motion>", self.drag)
#         self.canvas.tag_bind(self.image_id, "<Double-Button-1>", self.rotate)
#         # self.canvas.tag_bind(self.image_id, "<Button-1>", self.on_click)
#         self.last_mouse = (x, y)
#         self.handles = []
#         self.handle_dragging = False
#         self.handle_index = None
#         self.get_freeze_state = get_freeze_state  # function to query freeze state

#     def update_image(self):
#         rotated = self.original_image.rotate(self.angle, expand=True)
#         size = (int(rotated.width * self.scale), int(rotated.height * self.scale))
#         resized = rotated.resize(size)
#         self.tk_image = ImageTk.PhotoImage(resized)
#         self.current_size = size

#     def start_drag(self, event):
#         if self.get_freeze_state(): return
#         self.last_mouse = (event.x, event.y)
#         self.select_callback(self)

#     def drag(self, event):
#         if self.get_freeze_state(): return
#         dx = event.x - self.last_mouse[0]
#         dy = event.y - self.last_mouse[1]
#         self.canvas.move(self.image_id, dx, dy)
#         self.last_mouse = (event.x, event.y)
#         self.update_handles_position()

#     def rotate(self, event=None):
#         if self.get_freeze_state(): return
#         self.angle = (self.angle + 15) % 360
#         self.update_image()
#         self.canvas.itemconfig(self.image_id, image=self.tk_image)
#         self.update_handles_position()

#     def resize(self, factor):
#         if self.get_freeze_state(): return
#         self.scale *= factor
#         self.update_image()
#         self.canvas.itemconfig(self.image_id, image=self.tk_image)
#         self.update_handles_position()

#     def get_position(self):
#         coords = self.canvas.coords(self.image_id)
#         if coords and len(coords) >= 2:
#             return coords[0], coords[1]
#         return 0, 0

#     def set_position(self, x, y):
#         self.canvas.coords(self.image_id, x, y)
#         self.update_handles_position()

#     def on_click(self, event):
#         if self.get_freeze_state(): return
#         self.select_callback(self)

#     def draw_handles(self):
#         self.delete_handles()
#         x, y = self.get_position()
#         w, h = self.current_size
#         half_w, half_h = w / 2, h / 2
#         positions = [
#             (x - half_w, y - half_h), (x + half_w, y - half_h),
#             (x + half_w, y + half_h), (x - half_w, y + half_h)
#         ]
#         for i, (hx, hy) in enumerate(positions):
#             handle = self.canvas.create_rectangle(
#                 hx - HANDLE_SIZE//2, hy - HANDLE_SIZE//2,
#                 hx + HANDLE_SIZE//2, hy + HANDLE_SIZE//2,
#                 fill="blue", outline="black",
#                 tags=("handle", f"handle_{id(self)}_{i}")
#             )
#             self.handles.append(handle)
#             self.canvas.tag_bind(handle, "<ButtonPress-1>", lambda e, idx=i: self.start_handle_drag(e, idx))
#             self.canvas.tag_bind(handle, "<B1-Motion>", self.handle_drag)
#             self.canvas.tag_bind(handle, "<ButtonRelease-1>", self.end_handle_drag)




#     def delete_handles(self):
#         for h in self.handles:
#             self.canvas.delete(h)
#         self.handles.clear()

#     def update_handles_position(self):
#         if not self.handles:
#             return
#         x, y = self.get_position()
#         w, h = self.current_size
#         half_w, half_h = w / 2, h / 2
#         positions = [
#             (x - half_w, y - half_h), (x + half_w, y - half_h),
#             (x + half_w, y + half_h), (x - half_w, y + half_h)
#         ]
#         for i, (hx, hy) in enumerate(positions):
#             self.canvas.coords(self.handles[i],
#                 hx - HANDLE_SIZE//2, hy - HANDLE_SIZE//2,
#                 hx + HANDLE_SIZE//2, hy + HANDLE_SIZE//2)

#     def start_handle_drag(self, event, handle_index):
#         if self.get_freeze_state(): return
#         self.handle_dragging = True
#         self.handle_index = handle_index
#         self.last_mouse = (event.x, event.y)

#     def handle_drag(self, event):
#         if self.get_freeze_state(): return
#         if not self.handle_dragging:
#             return
#         x, y = self.get_position()
#         dx = event.x - self.last_mouse[0]
#         dy = event.y - self.last_mouse[1]
#         w, h = self.current_size
#         base_img = self.original_image.rotate(self.angle, expand=True)
#         scale_x = (w + dx * 2) / base_img.width if self.handle_index in [1, 2] else (w - dx * 2) / base_img.width
#         scale_y = (h + dy * 2) / base_img.height if self.handle_index in [2, 3] else (h - dy * 2) / base_img.height
#         self.scale = max(0.05, (scale_x + scale_y) / 2)
#         self.update_image()
#         self.canvas.itemconfig(self.image_id, image=self.tk_image)
#         self.set_position(x + dx / 2, y + dy / 2)
#         self.last_mouse = (event.x, event.y)

#     def end_handle_drag(self, event):
#         self.handle_dragging = False
#         self.handle_index = None

#     def delete(self):
#         self.delete_handles()
#         self.canvas.delete(self.image_id)

#     def apply_global_zoom(self, zoom_level):
#         self.scale = zoom_level
#         self.update_image()
#         self.canvas.itemconfig(self.image_id, image=self.tk_image)
#         self.update_handles_position()
        
#     def flip_horizontal(self):
#         # Flip the original image left-right and update
#         self.original_image = self.original_image.transpose(Image.FLIP_LEFT_RIGHT)
#         self.update_image()
#         self.canvas.itemconfig(self.image_id, image=self.tk_image)
#         self.update_handles_position()

#     def flip_vertical(self):
#         # Flip the original image top-bottom and update
#         self.original_image = self.original_image.transpose(Image.FLIP_TOP_BOTTOM)
#         self.update_image()
#         self.canvas.itemconfig(self.image_id, image=self.tk_image)
#         self.update_handles_position()


# class furniture_data:
#     STANDARD_FURNITURE_SIZES = {
#     "double_bed": (6, 5),     # feet (length, width)
#     "single_bed": (6.5, 3),
#     "wardrobe":   (2, 6),
#     "desk":       (4, 2),
#     "sofa":       (6, 3),
#     "tv":         (4, 1),
#     "coffee_table": (3, 2),
#     "fridge":     (2.5, 2.5),
#     "cabinet":    (2, 1.5),
#     "bathtub":    (5.5, 2.5),
#     "shower":     (3, 3),
# }
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os

# Import furniture sizes from FurnitureHelper
from FurnitureHelper import STANDARD_FURNITURE_SIZES

def find_image_path(name: str) -> str | None:
    """
    Find the path for the furniture image in a case‑insensitive, cross‑platform way.

    We scan the Images folder and match the filename (without extension) ignoring case,
    so items like "wardrobe" will correctly find "Wardrobe.png" on macOS/Linux too.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(base_dir, "Images")

    if not os.path.isdir(images_dir):
        return None

    target = (name or "").strip().lower()
    if not target:
        return None

    for filename in os.listdir(images_dir):
        stem, ext = os.path.splitext(filename)
        if ext.lower() in (".png", ".jpeg", ".jpg") and stem.lower() == target:
            return os.path.join(images_dir, filename)

    return None

def remove_padding(image):
    """Remove transparent/white padding from image, return cropped image."""
    # Convert to RGBA if not already
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # Get bounding box of non-transparent pixels
    bbox = image.getbbox()
    
    if bbox:
        # Crop to bounding box (removes padding)
        cropped = image.crop(bbox)
        return cropped
    else:
        # If no bounding box found, return original
        return image

class Furniture:
    def __init__(
        self,
        canvas,
        image_path,
        x,
        y,
        select_callback,
        scale,
        angle,
        get_freeze_state,
        edit_callback=None,
        duplicate_callback=None,
        delete_callback=None,
        target_size=None,  # For square furniture: (width, height) in pixels
    ):
        self.image_path = image_path
        self.canvas = canvas
        # Load image and remove padding/transparency to get exact furniture content
        loaded_image = Image.open(image_path).convert("RGBA")
        self.original_image = remove_padding(loaded_image)
        self.angle = float(angle) % 360
        self.initial_angle = self.angle
        self.scale = scale
        self.target_size = target_size  # Store target size for square furniture
        # Store real size in feet for zoom recalculation (will be set after placement)
        self.real_size_ft = None  # (width_ft, height_ft)
        self.model_ref = None  # Reference to model for zoom calculations
        self.update_image()
        self.image_id = self.canvas.create_image(x, y, image=self.tk_image, anchor="center",tags=("furniture",))
        self.select_callback = select_callback
        self.edit_callback = edit_callback
        self.duplicate_callback = duplicate_callback
        self.delete_callback = delete_callback
        self._ctx_menu = None
        self.highlight_id = None
        self.is_selected = False

        # Lock/commit state (handled by tools/controller)
        self.committed = False
        self.committed_group_tag = None
        self.editing = True  # initially editable when placed

        self.canvas.tag_bind(self.image_id, "<ButtonPress-1>", self._on_left_click)
        self.canvas.tag_bind(self.image_id, "<B1-Motion>", self.drag)
        # Rotation is explicit only; double-click overlaps normal select/drag gestures.
        # Right-click (and common mac alternative) to enter edit mode (detach from group)
        self.canvas.tag_bind(self.image_id, "<Button-3>", self._on_right_click)
        self.canvas.tag_bind(self.image_id, "<Button-2>", self._on_right_click)
        self.canvas.tag_bind(self.image_id, "<Control-Button-1>", self._on_right_click)
        self.last_mouse = (x, y)
        self.drag_start_image_pos = (x, y)  # Initialize drag start position
        self.get_freeze_state = get_freeze_state  # function to query freeze state

    def update_image(self):
        # Optimization: Use Bilinear for much faster interactive scaling than Lanczos
        # and remove debug prints that slow down the main loop.
        
        if self.target_size:
            base_w = int(self.target_size[0])
            base_h = int(self.target_size[1])

            # Special handling for 90/270 degree rotations
            a = int(self.angle) % 360
            if a in (90, 270):
                # For 90/270: resize to original dimensions, rotate with expand=True (full image),
                # then crop/pad to swapped dimensions (base_h x base_w)
                base = self.original_image.resize((base_w, base_h), Image.Resampling.BILINEAR)
                rotated = base.rotate(self.angle, expand=True)
                
                # After rotation, we need swapped dimensions (base_h x base_w)
                final_w, final_h = base_h, base_w
                
                # Crop or pad rotated image to exact swapped dimensions
                if rotated.width != final_w or rotated.height != final_h:
                    # Calculate crop box to center the image
                    left = max(0, (rotated.width - final_w) // 2)
                    top = max(0, (rotated.height - final_h) // 2)
                    right = min(rotated.width, left + final_w)
                    bottom = min(rotated.height, top + final_h)
                    
                    if right > left and bottom > top:
                        rotated = rotated.crop((left, top, right, bottom))
                    
                    # If cropped image is smaller than target, pad it
                    if rotated.width < final_w or rotated.height < final_h:
                        padded = Image.new('RGBA', (final_w, final_h), (0, 0, 0, 0))
                        paste_x = (final_w - rotated.width) // 2
                        paste_y = (final_h - rotated.height) // 2
                        padded.paste(rotated, (paste_x, paste_y), rotated if rotated.mode == 'RGBA' else None)
                        rotated = padded
                
                self.tk_image = ImageTk.PhotoImage(rotated)
                self.current_size = (final_w, final_h)
                return
            
            # For all other angles: resize first, then rotate (no dimension swap)
            base = self.original_image.resize((base_w, base_h), Image.Resampling.BILINEAR)
            rotated = base.rotate(self.angle, expand=True)
            self.tk_image = ImageTk.PhotoImage(rotated)
            self.current_size = (base_w, base_h)
            return

        # Fallback: scale-based sizing (legacy)
        rotated = self.original_image.rotate(self.angle, expand=True)
        size = (int(rotated.width * self.scale), int(rotated.height * self.scale))
        resized = rotated.resize(size, Image.Resampling.BILINEAR)
        self.tk_image = ImageTk.PhotoImage(resized)
        self.current_size = size


    def _on_left_click(self, event):
        """Handle left-click: select furniture first, then allow dragging."""
        if self.get_freeze_state():
            return
        # Select furniture on left-click
        if callable(self.select_callback):
            try:
                self.select_callback(self)
            except Exception:
                pass
        # Then start drag
        self.start_drag(event)

    def start_drag(self, event):
        if self.get_freeze_state(): return
        # If furniture is committed to a group, don't handle drag here - let group drag handle it
        if getattr(self, "committed", False) and not getattr(self, "editing", False):
            return
        # Get current image position (center point)
        coords = self.canvas.coords(self.image_id)
        if coords and len(coords) >= 2:
            img_x, img_y = coords[0], coords[1]
        else:
            img_x, img_y = event.x, event.y
        # Calculate offset from click point to image center
        # This offset will be maintained during drag so image follows cursor
        self.drag_offset_x = event.x - img_x
        self.drag_offset_y = event.y - img_y
        self.last_mouse = (event.x, event.y)

    def drag(self, event):
        if self.get_freeze_state(): return
        # If furniture is committed to a group, don't handle drag here - let group drag handle it
        if getattr(self, "committed", False) and not getattr(self, "editing", False):
            return
        # Calculate new image position: cursor position minus the offset
        # This keeps the image at the same relative position to cursor
        new_x = event.x - self.drag_offset_x
        new_y = event.y - self.drag_offset_y
        # Get current position
        coords = self.canvas.coords(self.image_id)
        if coords and len(coords) >= 2:
            current_x, current_y = coords[0], coords[1]
            # Move by the difference
            dx = new_x - current_x
            dy = new_y - current_y
            self.canvas.move(self.image_id, dx, dy)
            self.draw_highlight()
        self.last_mouse = (event.x, event.y)

    def set_rotation(self, angle):
        """Rotate around the fixed canvas center and refresh selection overlays."""
        if self.get_freeze_state():
            return False
        center = self.get_position()
        self.angle = float(angle) % 360
        self.update_image()
        self.canvas.itemconfig(self.image_id, image=self.tk_image)
        self.canvas.coords(self.image_id, *center)
        if self.is_selected:
            if getattr(self, "committed", False) and not getattr(self, "editing", False):
                self.delete_handles()
            else:
                self.draw_handles()
            self.draw_highlight()
        return True

    def rotate(self, degrees=15):
        """Rotate by signed Pillow degrees: positive is anti-clockwise."""
        return self.set_rotation(self.angle + float(degrees))

    def resize(self, factor):
        """Resize proportionally while keeping real-world dimensions in sync."""
        if self.get_freeze_state() or factor <= 0:
            return
        if self.target_size:
            self.target_size = (
                max(8, int(self.target_size[0] * factor)),
                max(8, int(self.target_size[1] * factor)),
            )
        else:
            self.scale = max(0.05, self.scale * factor)
        if self.real_size_ft:
            self.real_size_ft = (
                max(0.1, self.real_size_ft[0] * factor),
                max(0.1, self.real_size_ft[1] * factor),
            )
        self.update_image()
        self.canvas.itemconfig(self.image_id, image=self.tk_image)
        self.draw_handles()
        self.draw_highlight()

    def set_exact_size(self, width_ft, depth_ft):
        """Set exact unrotated dimensions in feet."""
        width_ft, depth_ft = float(width_ft), float(depth_ft)
        if width_ft <= 0 or depth_ft <= 0:
            raise ValueError("Furniture dimensions must be positive")
        self.real_size_ft = (width_ft, depth_ft)
        if self.model_ref:
            unit_factor = self.model_ref.unit_scale.get("ft", 1.0)
            pixels_per_foot = self.model_ref.grid_spacing * self.model_ref.zoom_level / unit_factor
            self.target_size = (max(8, int(width_ft * pixels_per_foot)), max(8, int(depth_ft * pixels_per_foot)))
        self.update_image()
        self.canvas.itemconfig(self.image_id, image=self.tk_image)
        self.draw_handles()
        self.draw_highlight()

    def get_position(self):
        coords = self.canvas.coords(self.image_id)
        if coords and len(coords) >= 2:
            return coords[0], coords[1]
        return 0, 0

    def set_position(self, x, y):
        self.canvas.coords(self.image_id, x, y)

    def on_click(self, event):
        if self.get_freeze_state(): return
        self.select_callback(self)

    def draw_highlight(self):
        """Show a bright boundary around this item while it is selected."""
        if not self.is_selected:
            self.delete_highlight()
            return
        bbox = self.canvas.bbox(self.image_id)
        if not bbox:
            return
        tags = tuple(
            ["furniture_selection_highlight"]
            + [
                tag for tag in self.canvas.gettags(self.image_id)
                if tag.startswith("room_group_") or tag.startswith("polygon_group_")
            ]
        )
        if self.highlight_id and self.canvas.type(self.highlight_id) == "rectangle":
            self.canvas.coords(self.highlight_id, bbox[0] - 3, bbox[1] - 3, bbox[2] + 3, bbox[3] + 3)
            self.canvas.itemconfig(self.highlight_id, tags=tags)
        else:
            self.highlight_id = self.canvas.create_rectangle(
                bbox[0] - 3, bbox[1] - 3, bbox[2] + 3, bbox[3] + 3,
                fill="", outline="#FACC15", width=3, tags=tags,
            )
        self.canvas.tag_raise(self.highlight_id)
        self.canvas.tag_raise(self.image_id)
        for handle in getattr(self, "handle_ids", []):
            self.canvas.tag_raise(handle)

    def delete_highlight(self):
        if self.highlight_id:
            try:
                self.canvas.delete(self.highlight_id)
            except Exception:
                pass
        self.highlight_id = None

    def draw_handles(self):
        """Draw four proportional resize handles around an editable item."""
        if getattr(self, "committed", False) and not getattr(self, "editing", False):
            self.delete_handles()
            return
        bbox = self.canvas.bbox(self.image_id)
        if not bbox:
            return
        positions = ((bbox[0], bbox[1]), (bbox[2], bbox[1]), (bbox[0], bbox[3]), (bbox[2], bbox[3]))
        existing = getattr(self, "handle_ids", [])
        if len(existing) == 4 and all(self.canvas.type(handle) == "rectangle" for handle in existing):
            for handle, (x, y) in zip(existing, positions):
                self.canvas.coords(handle, x - 4, y - 4, x + 4, y + 4)
                self.canvas.tag_raise(handle)
            return
        self.delete_handles()
        self.handle_ids = []
        for x, y in positions:
            handle = self.canvas.create_rectangle(
                x - 4, y - 4, x + 4, y + 4,
                fill="white", outline="#2563EB", width=2,
                tags=("furniture_resize_handle",),
            )
            self.canvas.tag_bind(handle, "<ButtonPress-1>", self._start_handle_resize)
            self.canvas.tag_bind(handle, "<B1-Motion>", self._drag_handle_resize)
            self.handle_ids.append(handle)

    def _start_handle_resize(self, event):
        bbox = self.canvas.bbox(self.image_id)
        if not bbox:
            return
        self._resize_start_distance = max(
            abs(self.canvas.canvasx(event.x) - (bbox[0] + bbox[2]) / 2),
            abs(self.canvas.canvasy(event.y) - (bbox[1] + bbox[3]) / 2),
            1.0,
        )
        self._resize_start_target = self.target_size
        self._resize_start_scale = self.scale
        self._resize_start_real = self.real_size_ft

    def _drag_handle_resize(self, event):
        bbox = self.canvas.bbox(self.image_id)
        if not bbox or not getattr(self, "_resize_start_distance", None):
            return
        distance = max(
            abs(self.canvas.canvasx(event.x) - (bbox[0] + bbox[2]) / 2),
            abs(self.canvas.canvasy(event.y) - (bbox[1] + bbox[3]) / 2),
            1.0,
        )
        factor = max(0.05, distance / self._resize_start_distance)
        if self._resize_start_target:
            self.target_size = (
                max(8, int(self._resize_start_target[0] * factor)),
                max(8, int(self._resize_start_target[1] * factor)),
            )
        else:
            self.scale = max(0.05, self._resize_start_scale * factor)
        if self._resize_start_real:
            self.real_size_ft = (
                max(0.1, self._resize_start_real[0] * factor),
                max(0.1, self._resize_start_real[1] * factor),
            )
        self.update_image()
        self.canvas.itemconfig(self.image_id, image=self.tk_image)
        self.draw_handles()
        self.draw_highlight()

    def delete_handles(self):
        for handle in getattr(self, "handle_ids", []):
            try:
                self.canvas.delete(handle)
            except Exception:
                pass
        self.handle_ids = []

    def _on_right_click(self, event):
        """Show a context menu: Edit / Duplicate / Delete."""
        try:
            items = self.canvas.find_overlapping(event.x - 5, event.y - 5, event.x + 5, event.y + 5)
            for item in reversed(items):
                if self.canvas.type(item) == "text":
                    tags = self.canvas.gettags(item)
                    if "user_text" in tags:
                        return
        except Exception:
            pass

        try:
            self.select_callback(self)
        except Exception:
            pass

        self._show_context_menu(event)
        return "break"

    def _show_context_menu(self, event) -> None:
        try:
            root = self.canvas.winfo_toplevel()
        except Exception:
            root = None

        if self._ctx_menu is None:
            m = tk.Menu(root, tearoff=0)
            m.add_command(label="Edit", command=self._menu_edit)
            m.add_command(label="Duplicate", command=self._menu_duplicate)
            m.add_separator()
            m.add_command(label="Delete", command=self._menu_delete)
            self._ctx_menu = m

        try:
            self._ctx_menu.tk_popup(int(event.x_root), int(event.y_root))
        finally:
            try:
                self._ctx_menu.grab_release()
            except Exception:
                pass

    def _menu_edit(self) -> None:
        """Enter edit mode to allow drag and drop, then re-commit with Enter key."""
        if callable(getattr(self, "edit_callback", None)):
            try:
                self.edit_callback(self)
            except Exception:
                pass

    def _menu_duplicate(self) -> None:
        if callable(getattr(self, "duplicate_callback", None)):
            try:
                self.duplicate_callback(self)
            except Exception:
                pass

    def _menu_delete(self) -> None:
        if callable(getattr(self, "delete_callback", None)):
            try:
                self.delete_callback(self)
            except Exception:
                pass

    def delete(self):
        self.delete_handles()
        self.delete_highlight()
        self.canvas.delete(self.image_id)

    def apply_global_zoom(self, zoom_level, model=None):
        """Update furniture size when zoom changes."""
        # If we have real size in feet, recalculate target_size based on new zoom
        if self.real_size_ft and model:
            base_unit_factor = model.unit_scale.get("ft", model.unit_scale.get(model.unit, 1.0))
            pixels_per_foot = (model.grid_spacing * zoom_level) / base_unit_factor
            new_target_w = int(self.real_size_ft[0] * pixels_per_foot)
            new_target_h = int(self.real_size_ft[1] * pixels_per_foot)
            self.target_size = (new_target_w, new_target_h)
            self.model_ref = model
        
        self.scale = zoom_level
        self.update_image()
        self.canvas.itemconfig(self.image_id, image=self.tk_image)
        self.draw_highlight()
        
    def flip_horizontal(self):
        # Flip the original image left-right and update
        self.original_image = self.original_image.transpose(Image.FLIP_LEFT_RIGHT)
        self.update_image()
        self.canvas.itemconfig(self.image_id, image=self.tk_image)
        self.draw_highlight()

    def flip_vertical(self):
        # Flip the original image top-bottom and update
        self.original_image = self.original_image.transpose(Image.FLIP_TOP_BOTTOM)
        self.update_image()
        self.canvas.itemconfig(self.image_id, image=self.tk_image)
        self.draw_highlight()


# Keep furniture_data class for backward compatibility, but use constants from FurnitureHelper
class _ReloadingDict(dict):
    """Dictionary that reloads from FurnitureHelper module on each access."""
    def __init__(self):
        super().__init__()
        self._reload()
    
    def _reload(self):
        """Reload STANDARD_FURNITURE_SIZES from FurnitureHelper."""
        import importlib
        try:
            from FurnitureHelper import furniture_sizes
            importlib.reload(furniture_sizes)
            self.clear()
            self.update(furniture_sizes.STANDARD_FURNITURE_SIZES)
        except Exception:
            # Fallback to original import if reload fails
            if not self:
                self.update(STANDARD_FURNITURE_SIZES)
    
    def get(self, key, default=None):
        """Override get to reload before lookup."""
        self._reload()
        return super().get(key, default)
    
    def __getitem__(self, key):
        """Override __getitem__ to reload before lookup."""
        self._reload()
        return super().__getitem__(key)
    
    def __contains__(self, key):
        """Override __contains__ to reload before check."""
        self._reload()
        return super().__contains__(key)

class furniture_data:
    """
    Wrapper class for furniture size data.
    STANDARD_FURNITURE_SIZES automatically reloads from FurnitureHelper
    so changes to furniture_sizes.py are reflected without restarting.
    """
    pass

# Set STANDARD_FURNITURE_SIZES as a reloading dictionary
furniture_data.STANDARD_FURNITURE_SIZES = _ReloadingDict()
