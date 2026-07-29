# drawing_helpers.py
import math
from config import UNIT_SCALE, GRID_SPACING

def get_distance_label(x0, y0, x1, y1, unit, zoom_level=1.0):
    dx = x1 - x0
    dy = y1 - y0
    pixel_length = math.hypot(dx, dy)

    # Correct pixel length by removing zoom effect
    adjusted_pixel_length = pixel_length / zoom_level

    # Convert to real-world units
    real_length = (adjusted_pixel_length / GRID_SPACING) * UNIT_SCALE[unit]

    # Choose unit suffix
    unit_suffix_map = {
        "m": "m",
        "ft": "ft",
        "in": "in",
        # "centimeters": "cm",
        # "millimeters": "mm"
    }
    suffix = unit_suffix_map.get(unit, unit)

    # Midpoint for label placement
    mid_x = (x0 + x1) / 2
    mid_y = (y0 + y1) / 2

    label_text = f"{real_length:.2f} {suffix}"
    return label_text, mid_x, mid_y


    # mid_x, mid_y = (x0 + x1) // 2, (y0 + y1) // 2
    # # label_text, mid_x, mid_y = get_distance_label(x0, y0, x1, y1, self.unit, self.zoom_level)
    # return f"{real_dist:.2f}", mid_x, mid_y
# def get_distance_label(x0, y0, x1, y1, unit, zoom_level=1.0):
#     dist = math.hypot(x1 - x0, y1 - y0)
#     real_dist = (dist / (GRID_SPACING * zoom_level)) * UNIT_SCALE[unit]
#     mid_x, mid_y = (x0 + x1) // 2, (y0 + y1) // 2
#     angle_rad = math.atan2(y1 - y0, x1 - x0)
#     angle_deg = math.degrees(angle_rad)
#     return f"{real_dist:.2f} {unit}", mid_x, mid_y, angle_deg
