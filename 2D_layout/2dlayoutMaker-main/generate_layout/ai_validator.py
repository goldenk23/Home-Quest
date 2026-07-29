"""Strict native VastuCraft v1 validation for AI-generated layouts.

Ported from the tested Node validator so the editor enforces the same quality bar
(canvas bounds, room overlap, wall-gap intervals, door/gap proximity, and the exact
furniture/flooring allowlists) before a layout is applied to the canvas.
"""
from __future__ import annotations

import math
import re
from typing import Any

MAX_COORD = 10_000
MAX_ENTITIES = 1_000
MAX_POINTS = 4_000
SIDES = {"top", "right", "bottom", "left"}
SHAPES = {"line", "polygon"}
FLOORING = {"wood", "Wood", "marble", "Marble", "tile", "Tile", "garden", "grass", "Garden"}
FURNITURE = {
    "double_bed", "circular_bed", "bed_with_side_table", "single_bed",
    "sofa", "Sofa_Set_with_Centre_Table", "sofa_set_with_centre_table", "single_sofa",
    "Chair", "chair", "coffee_table", "dining_table_4_seat", "dining_table_6_seat",
    "dining_table_8_seat", "Table_Chair_Set", "table_chair_set", "Study_Table_Chair",
    "study_table_chair", "desk", "wardrobe", "Wardrobe", "Standing_Cabinet",
    "standing_cabinet", "tv", "TV", "fridge", "Fridge", "stove", "sink",
    "kitchen_platform", "kitchen_platform_2", "kitchen_platform_3", "kitchen_platform_4",
    "Toilet", "toilet", "Bath Tub", "bathtub", "Bath_Tub", "shower", "Wash_Basin",
    "Wash_basin", "wash_basin", "singlehand_door", "doublehand_door",
}
COMPASS_DIRECTIONS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
# Furniture whose job is to be a surface other items rest on or tuck under: kitchen
# counters, dining/coffee tables, desks. Detected by catalog name so the rule applies
# to every brief, not one prompt's assets. New surface assets inherit it for free.
_SURFACE_HINTS = ("platform", "table", "desk", "counter")
# Fraction of the smaller footprint two solid items may overlap before it is a collision.
_FURNITURE_TOUCH_FRACTION = 0.15


def _asset_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _is_surface_asset(value: Any) -> bool:
    key = _asset_key(value)
    return any(hint in key for hint in _SURFACE_HINTS)


def is_allowed_furniture_overlap(
    first: Any, second: Any, overlap_area: float, first_area: float, second_area: float
) -> bool:
    """Whether two same-room furniture footprints may legitimately share space.

    A general design rule, not a per-asset list: any item may rest on or tuck under a
    surface (counter, table, desk), and two non-surface items may touch slightly. Only a
    substantial overlap between two solid items is a real collision to report/repair.
    """
    if _is_surface_asset(first) or _is_surface_asset(second):
        return True
    smaller = min(first_area, second_area)
    return overlap_area <= max(4.0, _FURNITURE_TOUCH_FRACTION * smaller)


def _is_object(value: Any) -> bool:
    return isinstance(value, dict)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _finite(value, path, errors, min_v=-MAX_COORD, max_v=MAX_COORD) -> bool:
    if not _is_number(value) or value < min_v or value > max_v:
        errors.append(f"{path} must be a finite number from {min_v} to {max_v}")
        return False
    return True


def _string(value, path, errors, max_len=200) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > max_len:
        errors.append(f"{path} must be a non-empty string of at most {max_len} characters")
        return False
    return True


def _collection(value, path, errors, max_len):
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    if len(value) > max_len:
        errors.append(f"{path} has more than {max_len} items")
    return value


def _bounded_tree(root, errors) -> None:
    counter = {"nodes": 0}

    def visit(value, path, depth):
        counter["nodes"] += 1
        if counter["nodes"] > 15_000:
            errors.append("layout is too complex")
            return
        if depth > 10:
            errors.append(f"{path} is nested too deeply")
            return
        if isinstance(value, str) and len(value) > 2_000:
            errors.append(f"{path} exceeds 2000 characters")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value) or abs(value) > 1_000_000:
                errors.append(f"{path} is not a bounded finite number")
        if isinstance(value, list):
            if len(value) > 4_000:
                errors.append(f"{path} array is too large")
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]", depth + 1)
        elif isinstance(value, dict):
            if len(value) > 100:
                errors.append(f"{path} has too many fields")
            for key, item in value.items():
                if len(str(key)) > 64:
                    errors.append(f"{path} has an overlong field name")
                visit(item, f"{path}.{key}", depth + 1)

    visit(root, "layout", 0)


def _validate_flooring(value, path, errors) -> None:
    if not _is_object(value) or not isinstance(value.get("has_flooring"), bool):
        errors.append(f"{path} must contain boolean has_flooring")
        return
    if value.get("has_flooring") and value.get("flooring_type") not in FLOORING:
        errors.append(f"{path}.flooring_type is unsupported")
    image_path = value.get("image_path")
    if image_path is not None and (not isinstance(image_path, str) or len(image_path) > 300):
        errors.append(f"{path}.image_path is invalid")


def _point(value, path, errors, width, height) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        errors.append(f"{path} must be [x, y]")
        return False
    return _finite(value[0], f"{path}[0]", errors, 0, width) and _finite(value[1], f"{path}[1]", errors, 0, height)


def _distance_to_segment(px, py, x0, y0, x1, y1) -> float:
    dx = x1 - x0
    dy = y1 - y0
    denom = dx * dx + dy * dy or 1
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / denom))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def validate_layout(layout: Any) -> list[str]:
    """Return a de-duplicated list of validation errors; empty means the layout is valid."""
    errors: list[str] = []
    if not _is_object(layout):
        return ["layout must be a JSON object"]
    _bounded_tree(layout, errors)
    if layout.get("version") != "1.0":
        errors.append('version must be "1.0"')
    metadata = layout.get("metadata") if _is_object(layout.get("metadata")) else None
    if metadata is None:
        errors.append("metadata must be an object")
    width = metadata.get("canvas_width") if metadata else None
    height = metadata.get("canvas_height") if metadata else None
    if metadata is not None:
        _string(metadata.get("project_name"), "metadata.project_name", errors, 120)
        description = metadata.get("description")
        if description is not None and (not isinstance(description, str) or len(description) > 500):
            errors.append("metadata.description is invalid")
        if metadata.get("unit") != "ft":
            errors.append('metadata.unit must be "ft"')
        if metadata.get("unit_scale") != 1:
            errors.append("metadata.unit_scale must be 1")
        if metadata.get("grid_spacing") != 20:
            errors.append("metadata.grid_spacing must be 20 (20 canvas pixels = 1 ft)")
        if metadata.get("zoom_level") != 1:
            errors.append("metadata.zoom_level must be 1")
        _finite(width, "metadata.canvas_width", errors, 100, 5_000)
        _finite(height, "metadata.canvas_height", errors, 100, 5_000)
        _finite(metadata.get("wall_height_cm"), "metadata.wall_height_cm", errors, 100, 1_000)

    rooms = _collection(layout.get("rooms"), "rooms", errors, 100)
    furniture = _collection(layout.get("furniture"), "furniture", errors, 500)
    shapes = _collection(layout.get("shapes"), "shapes", errors, 200)
    texts = _collection(layout.get("text"), "text", errors, 200)
    if len(rooms) + len(furniture) + len(shapes) + len(texts) > MAX_ENTITIES:
        errors.append(f"layout exceeds {MAX_ENTITIES} entities")
    if not _is_number(width) or not _is_number(height):
        return list(dict.fromkeys(errors))[:40]

    ids: set[str] = set()
    room_tags: set[str] = set()
    polygon_tags: set[str] = set()
    gaps: list[tuple[float, float, float, float]] = []

    def add_id(item, path) -> None:
        if not _is_object(item):
            errors.append(f"{path} must be an object")
            return
        if _string(item.get("id"), f"{path}.id", errors, 100):
            if item["id"] in ids:
                errors.append(f"{path}.id must be unique")
            ids.add(item["id"])

    import re
    for index, room in enumerate(rooms):
        path = f"rooms[{index}]"
        add_id(room, path)
        if not _is_object(room):
            continue
        _string(room.get("name"), f"{path}.name", errors, 120)
        if _string(room.get("group_tag"), f"{path}.group_tag", errors, 100):
            if not re.fullmatch(r"room_group_[A-Za-z0-9_-]+", room["group_tag"]):
                errors.append(f"{path}.group_tag must start with room_group_")
            if room["group_tag"] in room_tags:
                errors.append(f"{path}.group_tag must be unique")
            room_tags.add(room["group_tag"])
        valid_rect = (
            _finite(room.get("x0"), f"{path}.x0", errors, 0, width)
            & _finite(room.get("y0"), f"{path}.y0", errors, 0, height)
            & _finite(room.get("x1"), f"{path}.x1", errors, 0, width)
            & _finite(room.get("y1"), f"{path}.y1", errors, 0, height)
        )
        if valid_rect and (room["x1"] <= room["x0"] or room["y1"] <= room["y0"]):
            errors.append(f"{path} must be a positive nonzero rectangle")
        if room.get("width") is not None and abs(room["width"] - (room["x1"] - room["x0"])) > 0.01:
            errors.append(f"{path}.width must equal x1 - x0")
        if room.get("height") is not None and abs(room["height"] - (room["y1"] - room["y0"])) > 0.01:
            errors.append(f"{path}.height must equal y1 - y0")
        if room.get("width_real") is not None and abs(room["width_real"] - (room["x1"] - room["x0"]) / 20) > 0.01:
            errors.append(f"{path}.width_real must use 20 px per ft")
        if room.get("height_real") is not None and abs(room["height_real"] - (room["y1"] - room["y0"]) / 20) > 0.01:
            errors.append(f"{path}.height_real must use 20 px per ft")
        if room.get("fill_mode") not in ("filled", "walls_only"):
            errors.append(f"{path}.fill_mode must be filled or walls_only")
        if room.get("wall_thickness_ft") is not None:
            _finite(room.get("wall_thickness_ft"), f"{path}.wall_thickness_ft", errors, 0.05, 3)
        _validate_flooring(room.get("flooring"), f"{path}.flooring", errors)

        erased = room.get("wall_erased_regions")
        if erased is not None:
            if not _is_object(erased):
                errors.append(f"{path}.wall_erased_regions must be an object")
            else:
                for side, intervals in erased.items():
                    if side not in SIDES:
                        errors.append(f"{path}.wall_erased_regions.{side} is not a valid side")
                        continue
                    if not isinstance(intervals, list) or len(intervals) > 12:
                        errors.append(f"{path}.wall_erased_regions.{side} must be an array of at most 12 intervals")
                        continue
                    horizontal = side in ("top", "bottom")
                    min_v = room.get("x0") if horizontal else room.get("y0")
                    max_v = room.get("x1") if horizontal else room.get("y1")
                    if not (_is_number(min_v) and _is_number(max_v)):
                        continue
                    prior = min_v
                    for gap_index, interval in enumerate(intervals):
                        gap_path = f"{path}.wall_erased_regions.{side}[{gap_index}]"
                        if not isinstance(interval, list) or len(interval) != 2:
                            errors.append(f"{gap_path} must be [start, end]")
                            continue
                        if not _finite(interval[0], f"{gap_path}[0]", errors, min_v, max_v) or not _finite(interval[1], f"{gap_path}[1]", errors, min_v, max_v):
                            continue
                        if interval[1] <= interval[0]:
                            errors.append(f"{gap_path} must have positive length")
                        if interval[0] < prior:
                            errors.append(f"{gap_path} overlaps or is unsorted")
                        prior = interval[1]
                        if horizontal:
                            edge_y = room["y0"] if side == "top" else room["y1"]
                            segment = (interval[0], edge_y, interval[1], edge_y)
                        else:
                            edge_x = room["x0"] if side == "left" else room["x1"]
                            segment = (edge_x, interval[0], edge_x, interval[1])
                        if interval[0] > min_v or interval[1] < max_v:
                            gaps.append(segment)

    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = rooms[i], rooms[j]
            if not _is_object(a) or not _is_object(b):
                continue
            if not all(_is_number(a.get(k)) and _is_number(b.get(k)) for k in ("x0", "y0", "x1", "y1")):
                continue
            overlap = max(0, min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])) * max(0, min(a["y1"], b["y1"]) - max(a["y0"], b["y0"]))
            smaller = min((a["x1"] - a["x0"]) * (a["y1"] - a["y0"]), (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]))
            if overlap > max(4, smaller * 0.02):
                name_a = a.get("name") if isinstance(a.get("name"), str) else a.get("id")
                name_b = b.get("name") if isinstance(b.get("name"), str) else b.get("id")
                errors.append(
                    f"rooms[{i}] ({name_a} {a['x0']},{a['y0']} -> {a['x1']},{a['y1']}) and "
                    f"rooms[{j}] ({name_b} {b['x0']},{b['y0']} -> {b['x1']},{b['y1']}) substantially overlap"
                )

    point_count = 0
    for index, shape in enumerate(shapes):
        path = f"shapes[{index}]"
        add_id(shape, path)
        if not _is_object(shape):
            continue
        if shape.get("type") not in SHAPES:
            errors.append(f"{path}.type must be line or polygon")
        points = _collection(shape.get("points"), f"{path}.points", errors, 64)
        point_count += len(points)
        valid_points = [_point(p, f"{path}.points[{pi}]", errors, width, height) for pi, p in enumerate(points)]
        if shape.get("type") == "line" and len(points) != 2:
            errors.append(f"{path}.line must have exactly 2 points")
        if shape.get("type") == "line" and len(points) == 2 and all(valid_points) and points[0][0] == points[1][0] and points[0][1] == points[1][1]:
            errors.append(f"{path}.line must have nonzero length")
        if shape.get("type") == "polygon":
            if len(points) < 3:
                errors.append(f"{path}.polygon must have at least 3 points")
            if len(points) >= 3 and all(valid_points):
                area2 = sum(
                    points[k][0] * points[(k + 1) % len(points)][1] - points[(k + 1) % len(points)][0] * points[k][1]
                    for k in range(len(points))
                )
                if abs(area2) < 2:
                    errors.append(f"{path}.polygon must have nonzero area")
            tags = shape.get("tags") if isinstance(shape.get("tags"), list) else []
            group = next((t for t in tags if isinstance(t, str) and t.startswith("polygon_group_")), None)
            if not group:
                errors.append(f"{path}.polygon requires a polygon_group_ tag")
            elif group in polygon_tags:
                errors.append(f"{path} polygon group tag must be unique")
            else:
                polygon_tags.add(group)
            _validate_flooring(shape.get("flooring"), f"{path}.flooring", errors)
        tags = shape.get("tags")
        if not isinstance(tags, list) or len(tags) > 20 or any(not isinstance(t, str) or len(t) > 100 for t in tags):
            errors.append(f"{path}.tags is invalid")
        if shape.get("width") is not None:
            _finite(shape.get("width"), f"{path}.width", errors, 0.1, 50)
    if point_count > MAX_POINTS:
        errors.append(f"shapes exceed {MAX_POINTS} points")
    if len(rooms) == 0 and not any(_is_object(s) and s.get("type") == "polygon" for s in shapes):
        errors.append("layout must contain at least one room")

    for index, item in enumerate(furniture):
        path = f"furniture[{index}]"
        add_id(item, path)
        if not _is_object(item):
            continue
        if item.get("image_name") not in FURNITURE:
            errors.append(f"{path}.image_name is unsupported")
        _finite(item.get("x"), f"{path}.x", errors, 0, width)
        _finite(item.get("y"), f"{path}.y", errors, 0, height)
        if item.get("scale") is not None:
            _finite(item.get("scale"), f"{path}.scale", errors, 0.1, 10)
        if item.get("angle") is not None:
            _finite(item.get("angle"), f"{path}.angle", errors, -3_600, 3_600)
        if "door" in str(item.get("image_name", "")).lower() and _is_number(item.get("x")) and _is_number(item.get("y")):
            near_gap = any(_distance_to_segment(item["x"], item["y"], *seg) <= 45 for seg in gaps)
            if not near_gap:
                errors.append(f"{path} door must be within 45 canvas pixels of a partial wall gap")

    for index, item in enumerate(texts):
        path = f"text[{index}]"
        add_id(item, path)
        if not _is_object(item):
            continue
        _string(item.get("content"), f"{path}.content", errors, 500)
        _finite(item.get("x"), f"{path}.x", errors, 0, width)
        _finite(item.get("y"), f"{path}.y", errors, 0, height)
        font = item.get("font")
        if font is not None and (not isinstance(font, str) or len(font) > 100):
            errors.append(f"{path}.font is invalid")
        tags = item.get("tags")
        if tags is not None and (not isinstance(tags, list) or len(tags) > 20 or any(not isinstance(t, str) or len(t) > 100 for t in tags)):
            errors.append(f"{path}.tags must be an array of at most 20 strings, for example [\"user_text\"], or be omitted")

    compass = layout.get("compass")
    if compass is not None:
        if not _is_object(compass):
            errors.append("compass must be an object")
        else:
            if compass.get("direction") is not None and compass.get("direction") not in COMPASS_DIRECTIONS:
                errors.append("compass.direction is invalid")
            if compass.get("north_deg_clockwise") is not None:
                _finite(compass.get("north_deg_clockwise"), "compass.north_deg_clockwise", errors, 0, 359.999999)
            if compass.get("direction") is None and compass.get("north_deg_clockwise") is None:
                errors.append("compass requires direction or north_deg_clockwise")

    return list(dict.fromkeys(errors))[:40]


def _rect_union_area(rects: list[tuple[float, float, float, float]]) -> float:
    """Exact union area for the small axis-aligned room set."""
    xs = sorted({x for rect in rects for x in (rect[0], rect[2])})
    area = 0.0
    for left, right in zip(xs, xs[1:]):
        if right <= left:
            continue
        spans = sorted((y0, y1) for x0, y0, x1, y1 in rects if x0 < right and x1 > left)
        covered = 0.0
        end = -math.inf
        for start, stop in spans:
            if stop <= end:
                continue
            covered += stop - max(start, end)
            end = stop
        area += (right - left) * covered
    return area


def _requested_count(brief: str, noun: str) -> int | None:
    import re

    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    match = re.search(rf"\b(\d+|{'|'.join(words)})\s+{noun}s?\b", brief)
    if not match:
        return None
    return int(match.group(1)) if match.group(1).isdigit() else words[match.group(1)]


def validate_design(layout: Any, design_brief: str, phase: str = "full") -> list[str]:
    """Validate architectural invariants and explicit requirements omitted by v1 schema checks.

    phase="rooms" reports only room-rectangle concerns (canvas, tiling, zones, room
    presence, exterior-wall placement, dimensions), so the first pipeline stage is
    judged before any openings exist. phase="structure" adds opening/door/circulation/
    ventilation concerns on top (the full shell) for the second stage. phase="furniture"
    reports only furniture inventory/containment/overlap concerns, so the furnishing
    stage is judged on furniture alone. phase="full" (default, also "all") checks
    everything and stays the final merged gate.
    """
    if not _is_object(layout) or not isinstance(design_brief, str):
        return []
    scopes = {
        "rooms": {"rooms"},
        "structure": {"rooms", "openings"},
        "furniture": {"furniture"},
        "full": {"rooms", "openings", "furniture"},
        "all": {"rooms", "openings", "furniture"},
    }.get(phase)
    if scopes is None:
        scopes = {"rooms", "openings", "furniture"}
    check_rooms = "rooms" in scopes
    check_openings = "openings" in scopes
    check_furniture = "furniture" in scopes
    brief = re.sub(r"\s+", " ", design_brief.lower().replace("×", "x"))
    rooms = layout.get("rooms")
    metadata = layout.get("metadata")
    furniture = layout.get("furniture")
    if not isinstance(rooms, list) or not isinstance(metadata, dict) or not isinstance(furniture, list):
        return []  # Native validation reports the structural errors first.

    room_data: list[dict[str, Any]] = []
    for index, room in enumerate(rooms):
        if not isinstance(room, dict) or not all(_is_number(room.get(k)) for k in ("x0", "y0", "x1", "y1")):
            continue
        if room["x1"] <= room["x0"] or room["y1"] <= room["y0"]:
            continue
        room_data.append({"index": index, "name": str(room.get("name", "")).lower(), "room": room,
                          "rect": (float(room["x0"]), float(room["y0"]), float(room["x1"]), float(room["y1"]))})
    if not room_data:
        return []

    errors: list[str] = []
    plot = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?\s*x\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')\b", brief)
    if plot:
        expected_width, expected_height = float(plot.group(1)) * 20, float(plot.group(2)) * 20
        if not _is_number(metadata.get("canvas_width")) or abs(metadata["canvas_width"] - expected_width) > 0.5:
            errors.append(f"requested plot requires metadata.canvas_width={expected_width:g} (20 px/ft)")
        if not _is_number(metadata.get("canvas_height")) or abs(metadata["canvas_height"] - expected_height) > 0.5:
            errors.append(f"requested plot requires metadata.canvas_height={expected_height:g} (20 px/ft)")

    rects = [entry["rect"] for entry in room_data]
    min_x = min(r[0] for r in rects)
    min_y = min(r[1] for r in rects)
    max_x = max(r[2] for r in rects)
    max_y = max(r[3] for r in rects)
    mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    envelope_area = (max_x - min_x) * (max_y - min_y)
    if "rectangular" in brief and envelope_area and _rect_union_area(rects) / envelope_area < 0.98:
        errors.append("requested rectangular building has internal voids; rooms/corridors must tile one rectangular footprint")

    for i, first in enumerate(room_data):
        a = first["rect"]
        for second in room_data[i + 1:]:
            b = second["rect"]
            overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            if check_rooms and overlap > 1:
                errors.append(f"{first['room'].get('name', 'room')} overlaps {second['room'].get('name', 'room')}")

    aliases = {
        "foyer": ("foyer", "entrance lobby"),
        "formal living": ("formal living",),
        "family lounge": ("family lounge", "family room"),
        "kitchen": ("kitchen",),
        "dining": ("dining",),
        "puja": ("puja", "pooja", "prayer"),
        "home office": ("office", "study room"),
        "powder room": ("powder",),
        "store room": ("store room", "storeroom"),
    }
    for phrase, names in aliases.items():
        if phrase in brief and not any(any(name in entry["name"] for name in names) for entry in room_data):
            errors.append(f"design brief requires a {phrase}")
    if ("utility" in brief or "laundry" in brief) and not any(
        "utility" in entry["name"] or "laundry" in entry["name"] for entry in room_data
    ):
        errors.append("design brief requires a utility/laundry space")

    bedroom_count = _requested_count(brief, "bedroom")
    actual_bedrooms = [entry for entry in room_data if "bedroom" in entry["name"]]
    if bedroom_count is not None and len(actual_bedrooms) < bedroom_count:
        errors.append(f"design brief requires {bedroom_count} bedrooms; layout has {len(actual_bedrooms)}")

    def find_room(*needles: str) -> dict[str, Any] | None:
        return next((entry for entry in room_data if any(needle in entry["name"] for needle in needles)), None)

    def center(entry: dict[str, Any]) -> tuple[float, float]:
        x0, y0, x1, y1 = entry["rect"]
        return (x0 + x1) / 2, (y0 + y1) / 2

    zone_checks = [
        ("master bedroom", ("master bedroom",), lambda x, y: x < mid_x and y > mid_y, "south-west"),
        ("kitchen", ("kitchen",), lambda x, y: x > mid_x and y > mid_y, "south-east"),
        ("puja", ("puja", "pooja", "prayer"), lambda x, y: x > mid_x and y < mid_y, "north-east"),
        ("guest bedroom", ("guest bedroom",), lambda x, y: x < mid_x and y < mid_y, "north-west"),
    ]
    for phrase, names, predicate, wanted in zone_checks:
        if phrase in brief:
            entry = find_room(*names)
            if entry and not predicate(*center(entry)):
                errors.append(f"{entry['room'].get('name', phrase)} must be in the requested {wanted} zone")
    if "parents" in brief:
        entry = find_room("parent")
        if entry and center(entry)[0] >= mid_x:
            errors.append("parents' bedroom must be in the requested west half")
    if "formal living" in brief:
        entry = find_room("formal living")
        if entry and center(entry)[1] >= mid_y:
            errors.append("formal living room must be in the requested north half")

    # Rooms-stage feasibility guarantees: a window-requiring room placed fully inside the
    # footprint could never get its ventilation window later, and a pass-through-restricted
    # room walled only by other restricted rooms could never join public circulation. Catch
    # both before any openings exist so the openings stage always inherits a workable shell.
    if check_rooms and "ventilat" in brief:
        for entry in room_data:
            if any(word in entry["name"] for word in ("bedroom", "living", "lounge", "kitchen", "office", "bath")):
                x0, y0, x1, y1 = entry["rect"]
                if x0 > min_x + 1 and y0 > min_y + 1 and x1 < max_x - 1 and y1 < max_y - 1:
                    errors.append(
                        f"{entry['room'].get('name', 'room')} must touch the building exterior so it "
                        "can take a ventilation window"
                    )
    if check_rooms and "without passing through another bedroom" in brief:
        restricted_words = ("bedroom", "bath", "powder", "kitchen")

        def shares_wall(first: dict[str, Any], second: dict[str, Any]) -> bool:
            a, b = first["rect"], second["rect"]
            vertical = abs(a[2] - b[0]) <= 1 or abs(b[2] - a[0]) <= 1
            horizontal = abs(a[3] - b[1]) <= 1 or abs(b[3] - a[1]) <= 1
            return (vertical and min(a[3], b[3]) - max(a[1], b[1]) > 1) or (
                horizontal and min(a[2], b[2]) - max(a[0], b[0]) > 1
            )

        for entry in room_data:
            if not any(word in entry["name"] for word in restricted_words):
                continue
            if not any(
                other is not entry
                and not any(word in other["name"] for word in restricted_words)
                and shares_wall(entry, other)
                for other in room_data
            ):
                errors.append(
                    f"{entry['room'].get('name', 'room')} must share a wall with a corridor, foyer, "
                    "or other public room so it can be reached without pass-through"
                )

    # Every door the openings stage will be asked for needs a shared wall to cut through;
    # verify the required adjacencies while moving rooms is still allowed.
    if check_rooms and room_data:
        def rect_shares_wall(first: dict[str, Any], second: dict[str, Any]) -> bool:
            a, b = first["rect"], second["rect"]
            vertical = abs(a[2] - b[0]) <= 1 or abs(b[2] - a[0]) <= 1
            horizontal = abs(a[3] - b[1]) <= 1 or abs(b[3] - a[1]) <= 1
            return (vertical and min(a[3], b[3]) - max(a[1], b[1]) > 1) or (
                horizontal and min(a[2], b[2]) - max(a[0], b[0]) > 1
            )

        dining, kitchen = find_room("dining"), find_room("kitchen")
        lounge = find_room("family lounge", "family room")
        if "directly connected" in brief:
            if dining and kitchen and not rect_shares_wall(dining, kitchen):
                errors.append("dining room must share a wall with the kitchen so they can have a direct door")
            if dining and lounge and not rect_shares_wall(dining, lounge):
                errors.append("dining room must share a wall with the family lounge so they can have a direct door")
        utility = find_room("utility", "laundry")
        if ("attached utility" in brief or "attached utility/laundry" in brief) and utility and kitchen \
                and not rect_shares_wall(utility, kitchen):
            errors.append("utility/laundry must share a wall with the kitchen so they can have a direct door")
        foyer = find_room("foyer", "entrance lobby")
        if "opening into a foyer" in brief and foyer is not None:
            fx0, fy0, fx1, fy1 = foyer["rect"]
            if fx0 > min_x + 1 and fy0 > min_y + 1 and fx1 < max_x - 1 and fy1 < max_y - 1:
                errors.append("the foyer must touch the building exterior so the main entrance can open into it")
            if ("north-facing" in brief or "north facing" in brief) and fy0 > min_y + 1:
                errors.append("the foyer must touch the north edge of the footprint for a north-facing entrance")
        baths = [entry for entry in room_data if "bath" in entry["name"] and "powder" not in entry["name"]]
        for needles, trigger in ((("master bedroom",), "master bedroom" in brief), (("parent",), "parent" in brief)):
            bedroom = find_room(*needles)
            if trigger and bedroom is not None and not any(rect_shares_wall(bedroom, bath) for bath in baths):
                errors.append(f"{bedroom['room'].get('name', 'bedroom')} must share a wall with its attached bathroom")
        attached_count = _requested_count(brief, "attached bathroom")
        if attached_count:
            adjacent = sum(
                1 for bath in baths
                if any("bedroom" in entry["name"] and rect_shares_wall(bath, entry) for entry in room_data)
            )
            if adjacent < attached_count:
                errors.append(
                    f"design brief requires {attached_count} bathrooms sharing a wall with a bedroom; "
                    f"layout has {adjacent}"
                )

    # Convert all room wall gaps to collinear segments and require mirrored shared-wall cuts.
    gaps: list[dict[str, Any]] = []
    for room_index, entry in enumerate(room_data):
        x0, y0, x1, y1 = entry["rect"]
        erased = entry["room"].get("wall_erased_regions")
        if not isinstance(erased, dict):
            continue
        for side, intervals in erased.items():
            if not isinstance(intervals, list):
                continue
            horizontal = side in ("top", "bottom")
            position = y0 if side == "top" else y1 if side == "bottom" else x0 if side == "left" else x1
            for interval in intervals:
                if isinstance(interval, list) and len(interval) == 2 and all(_is_number(v) for v in interval):
                    gaps.append({"room": room_index, "side": side, "horizontal": horizontal, "position": position,
                                 "start": float(interval[0]), "end": float(interval[1]), "external": True})

    adjacency: list[set[int]] = [set() for _ in room_data]

    def gap_overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
        if a["horizontal"] != b["horizontal"] or abs(a["position"] - b["position"]) > 1:
            return 0
        return max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))

    for gap in gaps:
        source = room_data[gap["room"]]["rect"]
        for other_index, other in enumerate(room_data):
            if other_index == gap["room"]:
                continue
            target = other["rect"]
            on_shared_wall = (
                gap["horizontal"] and (abs(gap["position"] - target[1]) <= 1 or abs(gap["position"] - target[3]) <= 1)
                and max(gap["start"], target[0]) < min(gap["end"], target[2])
            ) or (
                not gap["horizontal"] and (abs(gap["position"] - target[0]) <= 1 or abs(gap["position"] - target[2]) <= 1)
                and max(gap["start"], target[1]) < min(gap["end"], target[3])
            )
            if not on_shared_wall:
                continue
            gap["external"] = False
            counterpart = next((candidate for candidate in gaps if candidate["room"] == other_index and gap_overlap(gap, candidate) >= 20), None)
            if counterpart:
                adjacency[gap["room"]].add(other_index)
                adjacency[other_index].add(gap["room"])
            elif check_openings:
                errors.append(
                    f"opening on {room_data[gap['room']]['room'].get('name', 'room')} shared wall must be mirrored on "
                    f"{other['room'].get('name', 'adjoining room')}"
                )

    doors = [item for item in furniture if isinstance(item, dict) and "door" in str(item.get("image_name", "")).lower()]
    exterior_roots: set[int] = set()
    north_entrance = False
    door_gaps: set[int] = set()
    for door in doors:
        if not _is_number(door.get("x")) or not _is_number(door.get("y")):
            continue
        matched = []
        for gap_index, gap in enumerate(gaps):
            x0, y0, x1, y1 = ((gap["start"], gap["position"], gap["end"], gap["position"])
                              if gap["horizontal"] else (gap["position"], gap["start"], gap["position"], gap["end"]))
            if _distance_to_segment(door["x"], door["y"], x0, y0, x1, y1) <= 30:
                matched.append(gap)
                door_gaps.add(gap_index)
        for gap in matched:
            if gap["external"]:
                exterior_roots.add(gap["room"])
                if gap["side"] == "top" and abs(gap["position"] - min_y) <= 1:
                    north_entrance = True

    if not check_openings:
        pass  # Rooms/furniture stages trust the openings stage to prove circulation.
    elif not exterior_roots:
        errors.append("layout requires a real exterior entrance door on an exterior wall gap")
    else:
        reachable = set(exterior_roots)
        pending = list(exterior_roots)
        while pending:
            current = pending.pop()
            for neighbor in adjacency[current] - reachable:
                reachable.add(neighbor)
                pending.append(neighbor)
        inaccessible = [room_data[i]["room"].get("name", f"room {i}") for i in range(len(room_data)) if i not in reachable]
        if inaccessible:
            errors.append("rooms inaccessible from the exterior entrance: " + ", ".join(map(str, inaccessible[:8])))

    if check_openings and ("north-facing" in brief or "north facing" in brief):
        compass = layout.get("compass") if isinstance(layout.get("compass"), dict) else {}
        if compass.get("direction") != "N" or compass.get("north_deg_clockwise") not in (0, 0.0):
            errors.append("north-facing design requires compass direction N and north_deg_clockwise 0")
        if not north_entrance:
            errors.append("north-facing design requires the main exterior entrance on the north/top wall")

    attached_required = _requested_count(brief, "attached bathroom")
    if check_openings and attached_required:
        attached = 0
        for bath_index, entry in enumerate(room_data):
            if "bath" in entry["name"] and "powder" not in entry["name"]:
                if any("bedroom" in room_data[neighbor]["name"] for neighbor in adjacency[bath_index]):
                    attached += 1
        if attached < attached_required:
            errors.append(f"design brief requires {attached_required} bathrooms directly attached to bedrooms; layout has {attached}")

    if check_openings and "ventilat" in brief:
        for room_index, entry in enumerate(room_data):
            if any(word in entry["name"] for word in ("bedroom", "living", "lounge", "kitchen", "office", "bath")):
                if not any(gap["room"] == room_index and gap["external"] and index not in door_gaps for index, gap in enumerate(gaps)):
                    errors.append(f"{entry['room'].get('name', 'room')} requires an exterior ventilation window")

    if check_rooms and ("corridor" in brief and "4 ft" in brief or "passage" in brief and "4 ft" in brief):
        for entry in room_data:
            if "corridor" in entry["name"] or "passage" in entry["name"]:
                x0, y0, x1, y1 = entry["rect"]
                if min(x1 - x0, y1 - y0) < 80:
                    errors.append(f"{entry['room'].get('name', 'corridor')} must be at least 4 ft wide")

    # Use the editor's runtime dimensions, not model-supplied target_size, for physical collisions.
    try:
        from FurnitureHelper.furniture_sizes import STANDARD_FURNITURE_SIZES
        sizes = {re.sub(r"[^a-z0-9]", "", key.lower()): value for key, value in STANDARD_FURNITURE_SIZES.items()}
    except ImportError:
        sizes = {}
    placed: list[tuple[int, str, str, tuple[float, float, float, float]]] = []
    for item in furniture:
        if not isinstance(item, dict) or "door" in str(item.get("image_name", "")).lower():
            continue
        if not _is_number(item.get("x")) or not _is_number(item.get("y")):
            continue
        key = _asset_key(item.get("image_name"))
        width_ft, height_ft = sizes.get(key, (3.0, 3.0))
        scale = float(item.get("scale", 1)) if _is_number(item.get("scale", 1)) else 1.0
        angle = math.radians(float(item.get("angle", 0)) if _is_number(item.get("angle", 0)) else 0)
        width, height = width_ft * 20 * scale, height_ft * 20 * scale
        box_width = abs(width * math.cos(angle)) + abs(height * math.sin(angle))
        box_height = abs(width * math.sin(angle)) + abs(height * math.cos(angle))
        box = (item["x"] - box_width / 2, item["y"] - box_height / 2,
               item["x"] + box_width / 2, item["y"] + box_height / 2)
        containing = next((i for i, entry in enumerate(room_data) if
                           box[0] >= entry["rect"][0] + 4 and box[1] >= entry["rect"][1] + 4
                           and box[2] <= entry["rect"][2] - 4 and box[3] <= entry["rect"][3] - 4), None)
        if containing is None:
            if check_furniture:
                errors.append(f"furniture {item.get('id', item.get('image_name', 'item'))} footprint is not fully inside one room")
            continue
        placed.append((containing, str(item.get("id", item.get("image_name", "item"))), key, box))

    for i, (room_index, first_id, first_key, first) in enumerate(check_furniture and placed or []):
        first_area = (first[2] - first[0]) * (first[3] - first[1])
        for other_room, second_id, second_key, second in placed[i + 1:]:
            if room_index != other_room:
                continue
            overlap = max(0, min(first[2], second[2]) - max(first[0], second[0])) * max(0, min(first[3], second[3]) - max(first[1], second[1]))
            if overlap <= 4:
                continue
            second_area = (second[2] - second[0]) * (second[3] - second[1])
            if is_allowed_furniture_overlap(first_key, second_key, overlap, first_area, second_area):
                continue
            errors.append(f"furniture {first_id} overlaps furniture {second_id}")

    if check_furniture and ("brahmasthan" in brief or "exact center" in brief):
        center_box = (mid_x - (max_x - min_x) * 0.05, mid_y - (max_y - min_y) * 0.05,
                      mid_x + (max_x - min_x) * 0.05, mid_y + (max_y - min_y) * 0.05)
        if any(max(0, min(box[2], center_box[2]) - max(box[0], center_box[0]))
               * max(0, min(box[3], center_box[3]) - max(box[1], center_box[1])) > 0
               for _, _, _, box in placed):
            errors.append("the requested exact Brahmasthan/center must remain free of furniture")

    if check_rooms and "toilet" in brief and "north-east" in brief:
        for entry in room_data:
            x, y = center(entry)
            if ("bath" in entry["name"] or "powder" in entry["name"] or "toilet" in entry["name"]) and x > mid_x and y < mid_y:
                errors.append(f"{entry['room'].get('name', 'toilet room')} cannot be in the requested toilet-free north-east zone")

    # Explicit role checks close the main acceptance gap: a valid native document is not
    # a valid design when requested rooms or their contents were silently omitted.
    roles = {
        "master bedroom": find_room("master bedroom"),
        "parents' bedroom": find_room("parent"),
        "children's bedroom": find_room("children", "child bedroom", "kids bedroom"),
        "guest bedroom": find_room("guest bedroom"),
        "foyer": find_room("foyer", "entrance lobby"),
        "formal living room": find_room("formal living"),
        "family lounge": find_room("family lounge", "family room"),
        "kitchen": find_room("kitchen"),
        "dining room": find_room("dining"),
        "home office": find_room("office", "study room"),
        "utility/laundry": find_room("utility", "laundry"),
    }
    role_triggers = {
        "master bedroom": "master bedroom" in brief,
        "parents' bedroom": "parent" in brief,
        "children's bedroom": "children" in brief or "child bedroom" in brief,
        "guest bedroom": "guest bedroom" in brief,
    }
    for role, required in role_triggers.items():
        if check_rooms and required and roles[role] is None:
            errors.append(f"design brief requires a distinct {role}")

    # A shared gap is traversable only when the same cut exists on both room walls and
    # a real door is placed on it. The earlier adjacency graph deliberately remains useful
    # for generic opening checks; this stricter graph is used for circulation and attachment.
    door_adjacency: list[set[int]] = [set() for _ in room_data]
    for gap_index in door_gaps:
        if gap_index >= len(gaps) or gaps[gap_index]["external"]:
            continue
        gap = gaps[gap_index]
        for other_index, candidate in enumerate(gaps):
            if candidate["room"] == gap["room"] or gap_overlap(gap, candidate) < 20:
                continue
            if other_index not in door_gaps:
                continue
            door_adjacency[gap["room"]].add(candidate["room"])
            door_adjacency[candidate["room"]].add(gap["room"])

    def room_index(entry: dict[str, Any] | None) -> int | None:
        return room_data.index(entry) if entry is not None else None

    def require_connection(first_role: str, second_role: str, requirement: str) -> None:
        first, second = room_index(roles[first_role]), room_index(roles[second_role])
        if first is not None and second is not None and second not in door_adjacency[first]:
            errors.append(requirement)

    if check_openings:
        if "directly connected" in brief:
            require_connection("dining room", "kitchen", "dining room must have a direct door to the kitchen")
            require_connection("dining room", "family lounge", "dining room must have a direct door to the family lounge")
        if ("attached utility" in brief or "attached utility/laundry" in brief) and roles["utility/laundry"]:
            require_connection("utility/laundry", "kitchen", "utility/laundry must have a direct door to the kitchen")
        if "opening into a foyer" in brief and roles["foyer"] is not None:
            foyer_index = room_index(roles["foyer"])
            if foyer_index not in exterior_roots:
                errors.append("the main exterior entrance door must open into the foyer")

    strict_attached = 0
    bath_indices = [i for i, entry in enumerate(room_data)
                    if "bath" in entry["name"] and "powder" not in entry["name"]]
    bedroom_indices = [i for i, entry in enumerate(room_data)
                       if "bedroom" in entry["name"] or any(room_index(roles[key]) == i for key in role_triggers)]
    for bath_index in bath_indices:
        if any(bedroom in door_adjacency[bath_index] for bedroom in bedroom_indices):
            strict_attached += 1
    if check_openings and attached_required and strict_attached < attached_required:
        errors.append(
            f"design brief requires {attached_required} attached bathrooms with real bedroom doors; "
            f"layout has {strict_attached}"
        )
    for role in ("master bedroom", "parents' bedroom"):
        index = room_index(roles[role])
        if check_openings and role_triggers[role] and index is not None and not any(
            bath in door_adjacency[index] for bath in bath_indices
        ):
            errors.append(f"{role} requires its own directly attached bathroom")

    if check_openings and "without passing through another bedroom" in brief and exterior_roots:
        restricted = set(bedroom_indices + bath_indices)
        restricted.update(i for i, entry in enumerate(room_data)
                          if "powder" in entry["name"] or "kitchen" in entry["name"])
        inaccessible: list[str] = []
        for target in range(len(room_data)):
            reached = set(exterior_roots)
            pending = list(exterior_roots)
            while pending and target not in reached:
                current = pending.pop()
                for neighbor in door_adjacency[current] - reached:
                    if neighbor in restricted and neighbor != target:
                        continue
                    reached.add(neighbor)
                    pending.append(neighbor)
            if target not in reached:
                inaccessible.append(str(room_data[target]["room"].get("name", f"room {target}")))
        if inaccessible:
            errors.append(
                "clear circulation without bedroom/bathroom/kitchen pass-through is missing for: "
                + ", ".join(inaccessible[:8])
            )

    # Assign each supported asset to its containing room. Physical footprint containment
    # and collision checks above remain authoritative; this map checks intended-room semantics.
    room_assets: list[list[tuple[str, dict[str, Any]]]] = [[] for _ in room_data]
    for item in check_furniture and furniture or []:
        if not isinstance(item, dict) or "door" in str(item.get("image_name", "")).lower():
            continue
        if not _is_number(item.get("x")) or not _is_number(item.get("y")):
            continue
        for index, entry in enumerate(room_data):
            x0, y0, x1, y1 = entry["rect"]
            if x0 < item["x"] < x1 and y0 < item["y"] < y1:
                asset = re.sub(r"[^a-z0-9]", "", str(item.get("image_name", "")).lower())
                room_assets[index].append((asset, item))
                break

    def require_assets(role: str, requirements: list[tuple[str, set[str], int]]) -> None:
        index = room_index(roles[role])
        if index is None:
            return
        assets = [asset for asset, _ in room_assets[index]]
        for label, allowed, count in requirements:
            actual = sum(asset in allowed for asset in assets)
            if actual < count:
                errors.append(f"{role} requires {count} {label}; found {actual}")

    beds = {"doublebed", "bedwithsidetable", "circularbed"}
    wardrobes = {"wardrobe"}
    desks = {"desk", "studytablechair", "tablechairset"}
    sofas = {"sofa", "sofasetwithcentretable", "singlesofa"}
    storage = {"standingcabinet", "wardrobe"}
    if check_furniture and role_triggers["master bedroom"]:
        require_assets("master bedroom", [("king/double bed with side tables", {"bedwithsidetable"}, 1),
                                            ("wardrobe", wardrobes, 1)])
    if check_furniture and role_triggers["parents' bedroom"]:
        require_assets("parents' bedroom", [("queen/double bed", beds, 1), ("wardrobe", wardrobes, 1)])
    if check_furniture and role_triggers["guest bedroom"]:
        require_assets("guest bedroom", [("queen/double bed", beds, 1), ("wardrobe", wardrobes, 1)])
    if check_furniture and role_triggers["children's bedroom"]:
        require_assets("children's bedroom", [("single beds", {"singlebed"}, 2),
                                                ("study desks", desks, 2), ("wardrobe", wardrobes, 1)])
    if check_furniture and "sofa arrangement" in brief:
        require_assets("formal living room", [("sofa arrangement", sofas, 1),
                                                ("coffee table", {"coffeetable"}, 1), ("TV unit", {"tv"}, 1)])
    if check_furniture and "family lounge separately" in brief:
        require_assets("family lounge", [("separate sofa arrangement", sofas, 1)])
    if check_furniture and "dining room for eight" in brief:
        require_assets("dining room", [("eight-seat dining table", {"diningtable8seat"}, 1)])
    if check_furniture and "office for two" in brief:
        require_assets("home office", [("work desks", desks, 2), ("storage unit", storage, 1)])
    if check_furniture and "counters" in brief and "refrigerator" in brief and "stove" in brief and "sink" in brief:
        require_assets("kitchen", [("counter/platform", {"kitchenplatform", "kitchenplatform2",
                                                           "kitchenplatform3", "kitchenplatform4"}, 1),
                                    ("refrigerator", {"fridge"}, 1), ("stove", {"stove"}, 1),
                                    ("sink", {"sink", "washbasin"}, 1), ("pantry cabinet", storage, 1)])

    kitchen_index = room_index(roles["kitchen"])
    if check_furniture and "stove and sink separated" in brief and kitchen_index is not None:
        stove_items = [item for asset, item in room_assets[kitchen_index] if asset == "stove"]
        sink_items = [item for asset, item in room_assets[kitchen_index] if asset in {"sink", "washbasin"}]
        if stove_items and sink_items and min(
            math.hypot(stove["x"] - sink["x"], stove["y"] - sink["y"])
            for stove in stove_items for sink in sink_items
        ) < 40:
            errors.append("kitchen stove and sink must be separated by at least 2 ft")

    if check_furniture and "linen storage" in brief:
        has_linen_room = find_room("linen") is not None
        has_linen_cabinet = any(
            asset in storage and room_index(roles["kitchen"]) != index
            for index, assets in enumerate(room_assets) for asset, _ in assets
        )
        if not has_linen_room and not has_linen_cabinet:
            errors.append("design brief requires linen storage outside the kitchen")

    if check_openings and ("room labels" in brief or "concise room labels" in brief):
        labels = layout.get("text") if isinstance(layout.get("text"), list) else []
        for entry in room_data:
            x0, y0, x1, y1 = entry["rect"]
            if not any(isinstance(label, dict) and isinstance(label.get("content"), str)
                       and _is_number(label.get("x")) and _is_number(label.get("y"))
                       and x0 <= label["x"] <= x1 and y0 <= label["y"] <= y1 for label in labels):
                errors.append(f"{entry['room'].get('name', 'room')} requires a concise label inside the room")

    if check_rooms and ("supported flooring" in brief or "suitable supported flooring" in brief):
        for entry in room_data:
            flooring = entry["room"].get("flooring")
            if not isinstance(flooring, dict) or flooring.get("has_flooring") is not True:
                errors.append(f"{entry['room'].get('name', 'room')} requires supported flooring")

    if check_rooms and ("realistic dimensions" in brief or "narrow, unusable" in brief):
        for entry in room_data:
            width_ft = (entry["rect"][2] - entry["rect"][0]) / 20
            height_ft = (entry["rect"][3] - entry["rect"][1]) / 20
            area = width_ft * height_ft
            name = entry["name"]
            if "bedroom" in name and (min(width_ft, height_ft) < 9 or area < 100):
                errors.append(f"{entry['room'].get('name', 'bedroom')} has unusable bedroom dimensions")
            elif any(word in name for word in ("living", "lounge", "dining", "kitchen")) and (
                min(width_ft, height_ft) < 8 or area < 80
            ):
                errors.append(f"{entry['room'].get('name', 'room')} has unusable room dimensions")
            elif ("bath" in name or "powder" in name) and (min(width_ft, height_ft) < 4 or area < 20):
                errors.append(f"{entry['room'].get('name', 'bathroom')} has unusable bathroom dimensions")

    if check_openings and "openings at room corners" in brief:
        for index, gap in enumerate(gaps):
            entry = room_data[gap["room"]]
            x0, y0, x1, y1 = entry["rect"]
            side_min, side_max = (x0, x1) if gap["horizontal"] else (y0, y1)
            if gap["start"] - side_min < 20 or side_max - gap["end"] < 20:
                errors.append(f"opening on {entry['room'].get('name', 'room')} must stay at least 1 ft from corners")

    if check_rooms and "exact center" in brief:
        for entry in room_data:
            if any(word in entry["name"] for word in ("bath", "powder", "toilet")):
                x0, y0, x1, y1 = entry["rect"]
                if x0 <= mid_x <= x1 and y0 <= mid_y <= y1:
                    errors.append(f"{entry['room'].get('name', 'toilet room')} cannot occupy the exact center")

    if check_openings and "multiple exterior windows" in brief:
        windows = [index for index, gap in enumerate(gaps) if gap["external"] and index not in door_gaps]
        if len(windows) < 2:
            errors.append("design brief requires multiple exterior windows")

    return list(dict.fromkeys(errors))[:40]


if __name__ == "__main__":
    # ponytail: assert-based self-check — the one runnable guard for this validator.
    good = {
        "version": "1.0",
        "metadata": {"project_name": "Self Check", "unit": "ft", "unit_scale": 1, "grid_spacing": 20,
                     "zoom_level": 1, "canvas_width": 600, "canvas_height": 500, "wall_height_cm": 280},
        "rooms": [{"id": "r0", "name": "Living", "group_tag": "room_group_0", "group_id": 0,
                   "x0": 100, "y0": 100, "x1": 500, "y1": 400, "width": 400, "height": 300,
                   "width_real": 20, "height_real": 15, "fill_mode": "walls_only",
                   "fill_color": "#eee", "outline_color": "#334155", "wall_thickness_ft": 0.5,
                   "flooring": {"has_flooring": True, "flooring_type": "wood"}}],
        "shapes": [], "furniture": [], "text": [],
        "compass": {"direction": "N", "north_deg_clockwise": 0},
    }
    assert validate_layout(good) == [], validate_layout(good)

    overlap = {**good, "rooms": [good["rooms"][0],
               {**good["rooms"][0], "id": "r1", "group_tag": "room_group_1", "group_id": 1}]}
    assert any("overlap" in e for e in validate_layout(overlap)), "overlap must be detected"

    bad_unit = {**good, "metadata": {**good["metadata"], "grid_spacing": 35}}
    assert any("grid_spacing" in e for e in validate_layout(bad_unit)), "grid must be 20"

    orphan_door = {**good, "furniture": [{"id": "d0", "image_name": "singlehand_door", "x": 300, "y": 250}]}
    assert any("door" in e for e in validate_layout(orphan_door)), "orphan door must be rejected"

    good_design = {
        **good,
        "rooms": [{**good["rooms"][0], "x0": 0, "y0": 0, "x1": 600, "y1": 500,
                   "width": 600, "height": 500, "width_real": 30, "height_real": 25,
                   "wall_erased_regions": {"top": [[270, 330]]}}],
        "furniture": [{"id": "entrance", "image_name": "singlehand_door", "x": 300, "y": 0}],
    }
    assert validate_layout(good_design) == [], validate_layout(good_design)
    assert validate_design(good_design, "rectangular 30 ft x 25 ft home") == [], validate_design(
        good_design, "rectangular 30 ft x 25 ft home")

    wrong_plot = validate_design(good_design, "60 ft x 80 ft rectangular home")
    assert any("canvas_width" in error for error in wrong_plot), "requested plot size must be enforced"

    colliding = {**good_design, "furniture": good_design["furniture"] + [
        {"id": "chair-a", "image_name": "chair", "x": 200, "y": 200},
        {"id": "chair-b", "image_name": "chair", "x": 200, "y": 200},
    ]}
    assert any("overlaps furniture" in error for error in validate_design(colliding, "rectangular home")), \
        "furniture footprint collisions must be rejected"

    mounted_kitchen = {**good_design, "furniture": good_design["furniture"] + [
        {"id": "platform", "image_name": "kitchen_platform", "x": 300, "y": 250},
        {"id": "stove", "image_name": "stove", "x": 240, "y": 250},
        {"id": "sink", "image_name": "sink", "x": 300, "y": 250},
        {"id": "fridge", "image_name": "fridge", "x": 360, "y": 250},
    ]}
    mounted_errors = validate_design(mounted_kitchen, "rectangular home", phase="furniture")
    assert not any("overlaps furniture" in error for error in mounted_errors), mounted_errors
    # General rule: any item may sit on a surface (counter/table/desk), whatever its name.
    assert is_allowed_furniture_overlap("kitchen_platform", "fridge", 3600, 12800, 3600)
    assert is_allowed_furniture_overlap("dining_table_8_seat", "chair", 1600, 9600, 1600)
    assert is_allowed_furniture_overlap("desk", "chair", 1600, 5000, 1600)
    # Two solid items substantially overlapping is still a real collision.
    assert not is_allowed_furniture_overlap("double_bed", "wardrobe", 4800, 14400, 4800)
    assert not is_allowed_furniture_overlap("stove", "sink", 1600, 3600, 1600)

    # Two-pass scoping: the structure phase must stay silent about furniture, the
    # furniture phase must stay silent about the shell, and "full" covers both.
    phased = {**good_design,
              "rooms": [{**good_design["rooms"][0], "name": "Master Bedroom",
                         "wall_erased_regions": {"top": [[0, 60]]}}],
              "furniture": [{"id": "entrance", "image_name": "singlehand_door", "x": 30, "y": 0}]}
    phase_brief = ("rectangular 30 ft x 25 ft home with a master bedroom with a king bed "
                   "with side tables and a wardrobe; realistic dimensions; openings at room corners")
    structure_errors = validate_design(phased, phase_brief, phase="structure")
    furniture_errors = validate_design(phased, phase_brief, phase="furniture")
    full_errors = validate_design(phased, phase_brief, phase="full")
    assert not any("requires 1" in error for error in structure_errors), structure_errors
    assert any("must stay at least 1 ft from corners" in error for error in structure_errors), structure_errors
    assert any("master bedroom requires 1 king/double bed" in error for error in furniture_errors), furniture_errors
    assert not any("corners" in error for error in furniture_errors), furniture_errors
    assert any("requires 1" in error for error in full_errors) and any("corners" in error for error in full_errors)
    assert validate_design(colliding, "rectangular home", phase="structure") == []

    # Rooms-stage scoping: opening concerns stay silent, room concerns fire, and an
    # interior bathroom is flagged before the openings stage could inherit it.
    rooms_errors = validate_design(phased, phase_brief, phase="rooms")
    assert not any("corners" in error or "requires 1" in error for error in rooms_errors), rooms_errors
    interior = {**good, "rooms": [
        {**good["rooms"][0], "id": "hall", "name": "Hall", "group_tag": "room_group_0",
         "x0": 0, "y0": 0, "x1": 600, "y1": 500, "width": 600, "height": 500,
         "width_real": 30, "height_real": 25},
        {**good["rooms"][0], "id": "bath", "name": "Common Bathroom", "group_tag": "room_group_1",
         "x0": 200, "y0": 200, "x1": 300, "y1": 300, "width": 100, "height": 100,
         "width_real": 5, "height_real": 5},
    ]}
    autofix_free = validate_design(interior, "well ventilated 30 ft x 25 ft rectangular home", phase="rooms")
    assert any("must touch the building exterior" in error for error in autofix_free), autofix_free

    print("ai_validator self-check passed")
