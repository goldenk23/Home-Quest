# drawing_helpers.py
import math
import re
from config import UNIT_SCALE, GRID_SPACING


_FEET_IN_RE = re.compile(
    r"^\s*([0-9]*\.?[0-9]+)\s*(?:'|ft|feet|foot)\s*(?:([0-9]*\.?[0-9]+)\s*(?:\"|''|in|inch|inches)?)?\s*$"
)
_INCH_RE = re.compile(r'^\s*([0-9]*\.?[0-9]+)\s*(?:"|\'\'|in|inch|inches)\s*$')


def parse_length_input(text, unit="ft"):
    """Parse a length entry into the given unit.

    Accepts plain decimals ("5.17") and feet+inches formats such as
    "5 ft 2 in", "5' 2\"", "5'2". Bare "N in" / 'N"' values are treated as inches.
    Raises ValueError when the text cannot be understood.
    """
    s = str(text or "").strip().lower()
    if not s:
        raise ValueError("empty length")
    try:
        return float(s)
    except ValueError:
        pass

    m = _FEET_IN_RE.match(s)
    if m:
        total_ft = float(m.group(1)) + (float(m.group(2)) / 12.0 if m.group(2) else 0.0)
        if unit == "in":
            return total_ft * 12.0
        if unit == "m":
            return total_ft * 0.3048
        return total_ft  # default ft

    m = _INCH_RE.match(s)
    if m:
        inches = float(m.group(1))
        if unit == "in":
            return inches
        if unit == "m":
            return inches * 0.0254
        return inches / 12.0  # default ft

    raise ValueError(f"cannot parse length: {text!r}")


def format_length_normalized(value, unit="ft"):
    """Normalized display for a parsed length (feet+inches when unit is ft)."""
    if unit == "ft":
        feet = int(value)
        inches = round((value - feet) * 12.0, 2)
        if inches >= 12.0:
            feet += 1
            inches = 0.0
        return f"{feet}' {inches}\""
    return f"{value:.2f} {unit}"


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
