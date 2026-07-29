from config import UNIT_SCALE, DEFAULT_UNIT, GRID_SPACING
from furniture_suggestor import FurnitureSuggester, FurnitureSuggestionPopup

class CanvasModel:
    def __init__(self):
        self.zoom_level = 1.0
        self.zoom_step = 0.1
        self.grid_spacing = GRID_SPACING
        self.unit = "m"
        self.unit_scale = {"m": 1.0, "cm": 100, "ft": 3.281}
        
        self.line_color = "#E2E8F0"
        self.line_style = "solid"
        self.line_arrow = "none"
        self.fill_color = ""
        self.selected_item = None
        self.selected_image_item = None
        self.group_id_counter = 0

        # Polygon: auto-measurement lines (dimensioning) toggle
        # Default ON; toolbar can toggle this when polygon tool is active.
        self.auto_polygon_dimensions = True

        # Vastu Polygon: auto-measurement lines (dimensioning) toggle
        # Default ON; Vastu tab can toggle this when Vastu polygon tool is active.
        self.auto_vastu_polygon_dimensions = True

        # Generate Layout: auto-measurement lines (dimensioning) toggle
        # Default ON; Generate Layout tab can toggle this.
        self.auto_generate_layout_dimensions = True

        self.unit = DEFAULT_UNIT  # from config.py
        self.unit_scale = UNIT_SCALE
        self.unit_scale_factor = UNIT_SCALE[self.unit]  # Currently active unit
        self.suggester = FurnitureSuggester()
        self.tools = None 
        self.state_flags = { ... }  # unchanged

        self.state_flags = {
            "drawing_enabled": False,
            "polygon_mode": False,
            # Optional grid snapping for polygon/Vastu polygon drawing.
            # Default True to preserve existing snapping behavior.
            "grid_snap_enabled": True,
            "fill_mode_enabled": False,
            "eraser_mode": False,
            "multi_eraser_mode": False,
            "text_insertion_mode": False,
            "furniture_mode": False,
            "measure_mode": False,
            "paste_ready": False,
            "vastu_polygon_mode": False,
            "vastu_move_slices_only": False,
            # "slices": draw Vastu partitions (zones + division lines); "normal": outline only
            "vastu_polygon_draw_type": "slices",
            "vastu_zone_count": 8,
            # For 32-zone Vastu polygon only: choose label/angle scheme.
            # Values: "Moderne vastu" | "Vedic"
            "vastu_32_chakra_mode": "Vedic",
            "polygon_transparent": False,
        }

    def toggle(self, key):
        self.state_flags[key] = not self.state_flags[key]

    def set(self, key, value):
        self.state_flags[key] = value

    def get(self, key):
        if key == "vastu_zone_count":
            val = self.state_flags.get(key, 8)
            return val if isinstance(val, int) and val in (8, 16, 32) else 8
        if key == "vastu_32_chakra_mode":
            val = self.state_flags.get(key, "Vedic")
            val = str(val)
            return val if val in ("Moderne vastu", "Vedic") else "Vedic"
        return self.state_flags.get(key, False)
    def set_unit(self, new_unit):
        if new_unit in self.unit_scale:
            self.unit = new_unit
            self.unit_scale_factor = self.unit_scale[new_unit]
    

    def handle_room_double_click(self, room_name, bbox, canvas, real_width, real_height):
        from functools import partial
        """
        Display a popup listing furniture suggestions for a room.
        UI layout and styling is delegated to `FurnitureSuggestionPopup` so that
        Mac and Windows share the same look.
        """
        suggestions = self.suggester.suggest(room_name)
        if not suggestions:
            return

        x0, y0, x1, y1 = bbox

        # Compute default placement positions inside the room for each suggestion.
        n = len(suggestions)
        cols = min(3, n)
        rows = (n + cols - 1) // cols

        room_width_px = abs(x1 - x0)
        room_height_px = abs(y1 - y0)

        x_spacing = room_width_px / (cols + 1)
        y_spacing = room_height_px / (rows + 1)

        button_specs = []
        for idx, item in enumerate(suggestions):
            row = idx // cols
            col = idx % cols

            place_x = x0 + x_spacing * (col + 1)
            place_y = y0 + y_spacing * (row + 1)

            display_name = item.replace("_", " ").title()

            callback = partial(
                self.place_furniture_in_room,
                item,
                canvas,
                place_x,
                place_y,
                bbox,
                real_width,
                real_height,
            )
            button_specs.append((display_name, callback))

        try:
            parent = canvas.winfo_toplevel()
        except Exception:
            parent = canvas

        popup = FurnitureSuggestionPopup(
            parent=parent,
            title=f"Furniture for {room_name}",
            buttons=button_specs,
            # Keep popup compact on all platforms by limiting columns.
            columns=min(2, cols),
        )
        popup.show()

    def place_furniture_in_room(self, item_name, canvas, cx, cy, room_bbox, real_width, real_height):
        if self.tools:
            furniture_item = self.tools.insert_furniture_scaled(
                item_name, cx, cy, room_bbox, real_width, real_height
            )
            # select newly placed furniture for rotation
            if furniture_item:
                self.tools.selected_image_item = furniture_item
