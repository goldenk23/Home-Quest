from PIL import Image, ImageTk


class RoomEntity:
    def __init__(
        self,
        canvas,
        model,
        name,
        width_m,
        height_m,
        group_id,
        fill_mode: str = "filled",
        fill_color: "str | None" = None,
        wall_thickness_ft: float = 0.2,
    ):
        self.canvas = canvas
        self.model = model
        self.name = name
        self.group_tag = f"room_group_{group_id}"
        self.unit_scale = model.unit_scale[model.unit]
        self.grid_spacing = model.grid_spacing
        self.zoom_level = model.zoom_level
        self.wlabel = width_m
        self.hlabel = height_m
        self.width_px = width_m / self.unit_scale * self.grid_spacing * self.zoom_level
        self.height_px = height_m / self.unit_scale * self.grid_spacing * self.zoom_level
        self.x0 = 100 + group_id * 20
        self.y0 = 100 + group_id * 20
        self.x1 = self.x0 + self.width_px
        self.y1 = self.y0 + self.height_px
        self.canvas.tag_bind(self.group_tag, "<Double-Button-1>", self.on_double_click)

        # Room appearance options
        self.fill_mode = fill_mode  # "filled", "transparent", or "walls_only"
        self.wall_thickness_ft = wall_thickness_ft

        # Base fill color; can be overridden by explicit fill_color
        base_fill = "#d0f0c0"  # default
        if "shaft" in name.lower():
            base_fill = "#808080"
        elif "cupboard" in name.lower():
            base_fill = "#663300"

        self.fill_color = fill_color or base_fill

        self.create()

    def _wall_thickness_pixels(self) -> float:
        """
        Convert the desired wall thickness (in feet) into canvas pixels,
        respecting the current drawing unit, grid spacing, and zoom.
        """
        ft = float(self.wall_thickness_ft)
        unit = getattr(self.model, "unit", "feet")

        # Convert 0.2 ft into the active unit
        if unit in ("meters", "m"):
            thickness_in_unit = ft * 0.3048  # 1 ft = 0.3048 m
        elif unit in ("inches", "in"):
            thickness_in_unit = ft * 12.0  # 1 ft = 12 in
        elif unit in ("yards", "yd", "yards"):
            thickness_in_unit = ft / 3.0  # 1 yd = 3 ft
        else:  # "feet", "ft" or any unknown unit falls back to feet
            thickness_in_unit = ft

        return thickness_in_unit / self.unit_scale * self.grid_spacing * self.model.zoom_level

    def _rgb_from_tk_color(self, color: str):
        """
        Resolve any Tk color (hex/name/system) into an (r,g,b) tuple in 0-255.
        Returns None if it can't be resolved.
        """
        if not color:
            return None
        try:
            r16, g16, b16 = self.canvas.winfo_rgb(color)
            # winfo_rgb returns 0..65535; map to 0..255
            return (int(r16 / 257), int(g16 / 257), int(b16 / 257))
        except Exception:
            return None

    @staticmethod
    def _relative_luminance(rgb):
        # Simple (fast) perceived luminance approximation.
        r, g, b = rgb
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0

    def _pick_contrast_text_fill(self, background_color: str) -> str:
        """
        Pick a readable label color for the given background.
        This avoids macOS dark-mode/system default text color surprises.
        """
        rgb = self._rgb_from_tk_color(background_color)
        if not rgb:
            return "black"
        lum = self._relative_luminance(rgb)
        return "#111111" if lum >= 0.55 else "#f7f7f7"

    def _label_fill_color(self) -> str:
        # Prefer room fill for filled rooms; otherwise use canvas bg.
        bg = ""
        try:
            if self.fill_mode == "filled" and self.fill_color:
                bg = self.fill_color
            else:
                bg = str(self.canvas.cget("bg") or "")
        except Exception:
            bg = ""
        return self._pick_contrast_text_fill(bg)

    def create(self):
        self.items = []

        # --- Draw base geometry depending on fill mode ---
        if self.fill_mode == "transparent":
            # Only border, no interior fill
            self.rect_id = self.canvas.create_rectangle(
                self.x0,
                self.y0,
                self.x1,
                self.y1,
                fill="",
                outline="black",
                tags=("room", self.group_tag),
            )
            self.items.append(self.rect_id)
        elif self.fill_mode == "walls_only":
            # Draw four thin rectangles (top / bottom / left / right) as walls,
            # leaving the interior completely empty so grid/background is visible.
            t = self._wall_thickness_pixels()

            top_id = self.canvas.create_rectangle(
                self.x0,
                self.y0,
                self.x1,
                self.y0 + t,
                fill="black",
                outline="black",
                tags=("room", self.group_tag),
            )
            bottom_id = self.canvas.create_rectangle(
                self.x0,
                self.y1 - t,
                self.x1,
                self.y1,
                fill="black",
                outline="black",
                tags=("room", self.group_tag),
            )
            left_id = self.canvas.create_rectangle(
                self.x0,
                self.y0 + t,
                self.x0 + t,
                self.y1 - t,
                fill="black",
                outline="black",
                tags=("room", self.group_tag),
            )
            right_id = self.canvas.create_rectangle(
                self.x1 - t,
                self.y0 + t,
                self.x1,
                self.y1 - t,
                fill="black",
                outline="black",
                tags=("room", self.group_tag),
            )

            # Invisible hit-rectangle covering full room area for selection / double-click.
            self.rect_id = self.canvas.create_rectangle(
                self.x0,
                self.y0,
                self.x1,
                self.y1,
                fill="",
                outline="",
                tags=("room", self.group_tag),
            )

            # Store wall IDs for easy access
            self.top_wall_id = top_id
            self.bottom_wall_id = bottom_id
            self.left_wall_id = left_id
            self.right_wall_id = right_id

            self.items.extend([top_id, bottom_id, left_id, right_id, self.rect_id])
        else:
            # Default: filled rectangle
            self.rect_id = self.canvas.create_rectangle(
                self.x0,
                self.y0,
                self.x1,
                self.y1,
                fill=self.fill_color,
                outline="black",
                tags=("room", self.group_tag),
            )
            self.items.append(self.rect_id)

        # --- Decorations and labels ---
        if "shaft" in self.name.lower():
            line1 = self.canvas.create_line(
                self.x0,
                self.y0,
                self.x1,
                self.y1,
                fill="black",
                tags=(self.group_tag,),
            )
            line2 = self.canvas.create_line(
                self.x0,
                self.y1,
                self.x1,
                self.y0,
                fill="black",
                tags=(self.group_tag,),
            )
            self.items.extend([line1, line2])
        else:
            # Friendly unit label
            unit_display = {
                "meters": "m",
                "m": "m",
                "feet": "ft",
                "ft": "ft",
                "inches": "in",
                "in": "in",
                "yards": "yd",
                "yd": "yd",
            }

            unit_label = unit_display.get(self.model.unit, self.model.unit)
            text = f"{self.name}\n{round(self.wlabel, 1)}×{round(self.hlabel, 1)} {unit_label}"
            self.label_id = self.canvas.create_text(
                (self.x0 + self.x1) / 2,
                (self.y0 + self.y1) / 2,
                text=text,
                fill=self._label_fill_color(),
                font=("Helvetica", 10),
                justify="center",
                tags=(self.group_tag, "room_label"),
            )
            self.items.append(self.label_id)
            try:
                # Ensure label is visible above room geometry & images.
                self.canvas.tag_raise(self.label_id)
            except Exception:
                pass

        # ✅ Add both to group tag
        self.canvas.addtag_withtag(self.group_tag, self.rect_id)
        if hasattr(self, "label_id"):
            self.canvas.addtag_withtag(self.group_tag, self.label_id)

        # Ensure foreground elements (furniture, lines, measurements, text) stay on top
        if hasattr(self.model, "tools") and self.model.tools:
            if hasattr(self.model.tools, "restore_foreground_z_order"):
                self.model.tools.restore_foreground_z_order()

    # def on_click(self, event):
    #     if hasattr(self.model, "handle_room_click"):
    #         self.model.handle_room_click(self.name)
    def on_double_click(self, event):
        # Pull the live coords of the room rectangle from the canvas
        try:
            x0, y0, x1, y1 = self.canvas.coords(self.rect_id)
        except Exception:
            return

        # Check if click is inside this (moved) rectangle
        if x0 <= event.x <= x1 and y0 <= event.y <= y1:
            if hasattr(self.model, "handle_room_double_click"):
                self.model.handle_room_double_click(
                    self.name,
                    (x0, y0, x1, y1),
                    self.canvas,
                    self.wlabel,
                    self.hlabel,
                )

    def destroy(self):
        """Delete all items belonging to this room from the canvas."""
        if hasattr(self, "items"):
            for item in self.items:
                try:
                    self.canvas.delete(item)
                except Exception:
                    pass
            self.items = []

    def sync_to_canvas(self):
        """Update internal x0, y0 from the current canvas position of the primary rectangle."""
        try:
            coords = self.canvas.coords(self.rect_id)
            if coords and len(coords) >= 4:
                self.x0, self.y0 = coords[0], coords[1]
                self.x1, self.y1 = coords[2], coords[3]
        except Exception:
            pass