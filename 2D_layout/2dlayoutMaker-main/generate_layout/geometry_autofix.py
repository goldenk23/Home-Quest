"""Deterministic geometry auto-fix for AI-authored native VastuCraft v1 layouts.

This is a *linter/formatter* for the model's own design, not a generator. The LLM
decides the rooms, zones, openings, doors, and furniture; this pass repairs only the
mechanical consistency that language models reliably fumble:

1. Mirror every interior wall opening onto the adjoining room (the #1 failure class:
   "opening on X shared wall must be mirrored on Y").
2. Snap each door to the exact centre of the nearest wall gap so door/gap-proximity
   checks pass and circulation is counted.
3. Clamp each furniture item fully inside its room with the validator's inset so
   "footprint is not fully inside one room" stops firing on near-misses.
4. Separate overlapping rooms with the smallest single-boundary cut that makes the pair
   disjoint (the container or later room yields) - the room-level analogue of furniture
   separation. Shrinking one room can never create a new overlap; anything that would
   require slicing a room to ribbons is left for the strict validator to report back.

Design intent stays the model's; only coordinates are nudged into consistency. The
matching tolerances and the 20 px = 1 ft contract mirror `ai_validator` exactly so a
repaired layout passes by construction. Anything that cannot be fixed mechanically
(a missing room, an oversized item, furniture-on-furniture overlaps) is left for the
strict validator to report back into the LLM repair loop.
"""
from __future__ import annotations

import math
import re
from typing import Any

try:
    from .ai_validator import is_allowed_furniture_overlap
except ImportError:  # Direct `python generate_layout\\geometry_autofix.py` self-check.
    from ai_validator import is_allowed_furniture_overlap

# Same tolerances the validator uses, kept in one place so the two files agree.
_POSITION_TOL = 1.0          # two walls are "the same wall" within 1 px
_MIRROR_MIN_OVERLAP = 20.0   # validator requires >= 20 px shared opening to pair rooms
_FURNITURE_INSET = 4.0       # validator wants the footprint inside the room by 4 px
_PX_PER_FT = 20.0

try:  # Runtime furniture footprints; identical source the validator reads.
    from FurnitureHelper.furniture_sizes import STANDARD_FURNITURE_SIZES
    _SIZES = {re.sub(r"[^a-z0-9]", "", k.lower()): v for k, v in STANDARD_FURNITURE_SIZES.items()}
except Exception:  # noqa: BLE001 - autofix must never crash generation
    _SIZES = {}


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _rect(room: dict[str, Any]) -> tuple[float, float, float, float] | None:
    if not isinstance(room, dict) or not all(_num(room.get(k)) for k in ("x0", "y0", "x1", "y1")):
        return None
    x0, y0, x1, y1 = float(room["x0"]), float(room["y0"]), float(room["x1"]), float(room["y1"])
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def _merge_intervals(intervals: list[list[float]], lo: float, hi: float) -> list[list[float]]:
    """Clamp to [lo, hi], drop empties, sort, and merge overlapping/touching intervals."""
    cleaned = []
    for interval in intervals:
        if isinstance(interval, list) and len(interval) == 2 and _num(interval[0]) and _num(interval[1]):
            start, end = max(lo, min(interval)), min(hi, max(interval))
            if end - start > 0.01:
                cleaned.append([start, end])
    cleaned.sort()
    merged: list[list[float]] = []
    for start, end in cleaned:
        if merged and start <= merged[-1][1] + 0.01:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _repair_degenerate_rooms(rooms: list[dict[str, Any]]) -> None:
    """Rebuild a zero/negative-size room from its own width/height fields.

    Models occasionally emit x1<=x0 or y1<=y0 while still stating the intended size in
    `width`/`height`/`width_real`. We trust that stated intent, fix the far corner, and
    resync all derived fields so the validator's `width == x1-x0` checks stay consistent.
    """
    for room in rooms:
        if not isinstance(room, dict) or not all(_num(room.get(k)) for k in ("x0", "y0", "x1", "y1")):
            continue
        x0, y0, x1, y1 = float(room["x0"]), float(room["y0"]), float(room["x1"]), float(room["y1"])
        if x1 <= x0:
            span = room["width"] if _num(room.get("width")) and room["width"] > 0 else (
                room["width_real"] * _PX_PER_FT if _num(room.get("width_real")) and room["width_real"] > 0 else 0)
            if span <= 0:
                continue
            x1 = x0 + span
        if y1 <= y0:
            span = room["height"] if _num(room.get("height")) and room["height"] > 0 else (
                room["height_real"] * _PX_PER_FT if _num(room.get("height_real")) and room["height_real"] > 0 else 0)
            if span <= 0:
                continue
            y1 = y0 + span
        room["x1"], room["y1"] = x1, y1
        if "width" in room:
            room["width"] = x1 - x0
        if "height" in room:
            room["height"] = y1 - y0
        if "width_real" in room:
            room["width_real"] = (x1 - x0) / _PX_PER_FT
        if "height_real" in room:
            room["height_real"] = (y1 - y0) / _PX_PER_FT


def _mirror_side(neighbour: tuple[float, float, float, float], horizontal: bool, position: float) -> str | None:
    """Which wall of `neighbour` coincides with a gap at `position`, or None."""
    nx0, ny0, nx1, ny1 = neighbour
    if horizontal:
        if abs(position - ny0) <= _POSITION_TOL:
            return "top"
        if abs(position - ny1) <= _POSITION_TOL:
            return "bottom"
    else:
        if abs(position - nx0) <= _POSITION_TOL:
            return "left"
        if abs(position - nx1) <= _POSITION_TOL:
            return "right"
    return None


_COMPASS_SIDES = {"north": "top", "south": "bottom", "east": "right", "west": "left",
                  "n": "top", "s": "bottom", "e": "right", "w": "left"}


def _normalize_erased_keys(rooms: list[dict[str, Any]], layout: dict[str, Any]) -> None:
    """Rename compass-keyed wall sides (west/south/...) to native top/right/bottom/left.

    The model sometimes labels walls by compass direction; on a north-up plan the mapping
    is unambiguous. Only remaps list-valued entries when the compass is missing or already
    north-up; anything else is left for the strict validator to report back to the model.
    """
    compass = layout.get("compass") if isinstance(layout.get("compass"), dict) else {}
    if compass.get("direction") not in (None, "N") or compass.get("north_deg_clockwise") not in (None, 0, 0.0):
        return
    for room in rooms:
        erased = room.get("wall_erased_regions") if isinstance(room, dict) else None
        if not isinstance(erased, dict):
            continue
        for key in list(erased.keys()):
            side = _COMPASS_SIDES.get(str(key).lower())
            intervals = erased[key]
            if side is None or not isinstance(intervals, list):
                continue
            existing = erased.get(side)
            erased[side] = (existing if isinstance(existing, list) else []) + intervals
            del erased[key]


def _normalize_erased_intervals(rooms: list[dict[str, Any]]) -> None:
    """Clamp every wall opening to its wall bounds, drop empties, sort, and merge.

    Fixes the "interval endpoint outside [min,max]" and "overlaps or is unsorted"
    classes the model produces when it lets an opening run past a room corner.
    """
    for room in rooms:
        rect = _rect(room)
        erased = room.get("wall_erased_regions") if isinstance(room, dict) else None
        if rect is None or not isinstance(erased, dict):
            continue
        x0, y0, x1, y1 = rect
        for side in ("top", "right", "bottom", "left"):
            intervals = erased.get(side)
            if not isinstance(intervals, list):
                continue
            lo, hi = (x0, x1) if side in ("top", "bottom") else (y0, y1)
            erased[side] = _merge_intervals(intervals, lo, hi)


_CORNER_MARGIN = 20.0  # keep openings >= 1 ft from a room corner (door-swing clearance)


def _nudge_corner_openings(rooms: list[dict[str, Any]]) -> None:
    """Slide any opening that sits within 1 ft of a corner back toward the wall centre."""
    for room in rooms:
        rect = _rect(room)
        erased = room.get("wall_erased_regions") if isinstance(room, dict) else None
        if rect is None or not isinstance(erased, dict):
            continue
        x0, y0, x1, y1 = rect
        for side in ("top", "right", "bottom", "left"):
            intervals = erased.get(side)
            if not isinstance(intervals, list):
                continue
            lo, hi = (x0, x1) if side in ("top", "bottom") else (y0, y1)
            if hi - lo < 2 * _CORNER_MARGIN + 1:
                continue  # wall too short to hold any corner-safe opening; leave for the model
            fixed: list[list[float]] = []
            for interval in intervals:
                if not (isinstance(interval, list) and len(interval) == 2 and _num(interval[0]) and _num(interval[1])):
                    continue
                s, e = float(min(interval)), float(max(interval))
                if s <= lo and e >= hi:
                    # A fully erased wall still violates the corner-clearance rule, so pull
                    # both ends in to 1 ft piers; the opening stays wide and mirrored.
                    fixed.append([lo + _CORNER_MARGIN, hi - _CORNER_MARGIN])
                    continue
                length = min(e - s, hi - lo - 2 * _CORNER_MARGIN)
                s = max(lo + _CORNER_MARGIN, min(s, hi - _CORNER_MARGIN - length))
                fixed.append([s, s + length])
            erased[side] = _merge_intervals(fixed, lo, hi)


def _mirror_openings(rooms: list[dict[str, Any]]) -> None:
    """For every interior gap, guarantee the adjoining room carries the matching gap."""
    rects = [_rect(room) for room in rooms]
    # Snapshot source intervals first so we mirror originals, not our own additions.
    source: list[tuple[int, str, float, float, float, bool]] = []
    for i, room in enumerate(rooms):
        rect = rects[i]
        erased = room.get("wall_erased_regions") if isinstance(room, dict) else None
        if rect is None or not isinstance(erased, dict):
            continue
        x0, y0, x1, y1 = rect
        for side, intervals in erased.items():
            if side not in ("top", "right", "bottom", "left") or not isinstance(intervals, list):
                continue
            horizontal = side in ("top", "bottom")
            position = y0 if side == "top" else y1 if side == "bottom" else x0 if side == "left" else x1
            for interval in intervals:
                if isinstance(interval, list) and len(interval) == 2 and _num(interval[0]) and _num(interval[1]):
                    source.append((i, side, float(min(interval)), float(max(interval)), position, horizontal))

    for i, _side, start, end, position, horizontal in source:
        for j, neighbour in enumerate(rects):
            if j == i or neighbour is None:
                continue
            mside = _mirror_side(neighbour, horizontal, position)
            if mside is None:
                continue
            nx0, ny0, nx1, ny1 = neighbour
            span_lo, span_hi = (nx0, nx1) if horizontal else (ny0, ny1)
            overlap_lo, overlap_hi = max(start, span_lo), min(end, span_hi)
            if overlap_hi - overlap_lo < _MIRROR_MIN_OVERLAP:
                continue  # not a real shared opening; leave it as an exterior gap
            erased = rooms[j].setdefault("wall_erased_regions", {})
            if not isinstance(erased, dict):
                rooms[j]["wall_erased_regions"] = erased = {}
            existing = erased.get(mside) if isinstance(erased.get(mside), list) else []
            already = any(
                isinstance(iv, list) and len(iv) == 2 and _num(iv[0]) and _num(iv[1])
                and min(max(iv), overlap_hi) - max(min(iv), overlap_lo) >= _MIRROR_MIN_OVERLAP
                for iv in existing
            )
            if not already:
                existing = existing + [[overlap_lo, overlap_hi]]
            erased[mside] = _merge_intervals(existing, span_lo, span_hi)


def _resolve_room_overlaps(rooms: list[dict[str, Any]]) -> None:
    """Separate overlapping rooms with the smallest single-boundary cut.

    The model owns every room's position and size; an overlap is never intentional, so
    the draftsman moves ONE boundary of ONE room by the smallest amount that makes the
    pair disjoint. The container yields in a containment (the model's usual failure is
    nesting a bath/utility at another room's corner); otherwise the later room yields.
    A cut that would leave a sliver, fail to separate, or clip a third room is rejected;
    unresolved pairs are left for the validator to report back to the model.
    """
    rects = [_rect(room) for room in rooms]

    def overlap_area(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
        return (max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
                * max(0.0, min(a[3], b[3]) - max(a[1], b[1])))

    def apply_cut(index: int, field: str, value: float) -> None:
        room = rooms[index]
        room[field] = value
        x0, y0, x1, y1 = float(room["x0"]), float(room["y0"]), float(room["x1"]), float(room["y1"])
        if "width" in room:
            room["width"] = x1 - x0
        if "height" in room:
            room["height"] = y1 - y0
        if "width_real" in room:
            room["width_real"] = (x1 - x0) / _PX_PER_FT
        if "height_real" in room:
            room["height_real"] = (y1 - y0) / _PX_PER_FT
        rects[index] = (x0, y0, x1, y1)

    skipped: set[tuple[int, int]] = set()
    while True:
        pair = None
        for i in range(len(rooms)):
            if rects[i] is None:
                continue
            for j in range(i + 1, len(rooms)):
                if rects[j] is None or (i, j) in skipped:
                    continue
                area = overlap_area(rects[i], rects[j])
                smaller = min((rects[i][2] - rects[i][0]) * (rects[i][3] - rects[i][1]),
                              (rects[j][2] - rects[j][0]) * (rects[j][3] - rects[j][1]))
                if area > max(4.0, smaller * 0.02):
                    pair = (i, j)
                    break
            if pair:
                break
        if pair is None:
            return
        i, j = pair
        a, b = rects[i], rects[j]
        a_inside_b = a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]
        b_inside_a = b[0] >= a[0] and b[1] >= a[1] and b[2] <= a[2] and b[3] <= a[3]
        order = (j, i) if a_inside_b else (i, j) if b_inside_a else (j, i)
        resolved = False
        for yielder, other in ((order[0], order[1]), (order[1], order[0])):
            y, o = rects[yielder], rects[other]
            candidates = [
                ("x0", o[2], (o[2] - y[0]) * (y[3] - y[1])),
                ("x1", o[0], (y[2] - o[0]) * (y[3] - y[1])),
                ("y0", o[3], (y[2] - y[0]) * (o[3] - y[1])),
                ("y1", o[1], (y[2] - y[0]) * (y[3] - o[1])),
            ]
            legal: list[tuple[float, str, float]] = []
            for field, value, lost in candidates:
                nx0, ny0, nx1, ny1 = y
                if field == "x0":
                    nx0 = value
                elif field == "x1":
                    nx1 = value
                elif field == "y0":
                    ny0 = value
                else:
                    ny1 = value
                if nx1 - nx0 < 40 or ny1 - ny0 < 40:
                    continue  # never slice a room below 2 ft; the model must re-tile instead
                new_rect = (nx0, ny0, nx1, ny1)
                if overlap_area(new_rect, o) > 0:
                    continue  # cut fails to separate the pair
                if any(k != yielder and k != other and rects[k] is not None
                       and overlap_area(new_rect, rects[k]) > 0 for k in range(len(rooms))):
                    continue  # cut would push the room into a third room
                legal.append((lost, field, value))
            if legal:
                legal.sort()
                _, field, value = legal[0]
                apply_cut(yielder, field, value)
                resolved = True
                break
        if not resolved:
            skipped.add(pair)  # leave this pair for the validator; keep resolving others


def _gap_segments(rooms: list[dict[str, Any]]) -> list[tuple[float, float, float, float]]:
    """All partial wall-gap segments as (x0, y0, x1, y1), for door snapping."""
    segments: list[tuple[float, float, float, float]] = []
    for room in rooms:
        rect = _rect(room)
        erased = room.get("wall_erased_regions") if isinstance(room, dict) else None
        if rect is None or not isinstance(erased, dict):
            continue
        x0, y0, x1, y1 = rect
        for side, intervals in erased.items():
            if side not in ("top", "right", "bottom", "left") or not isinstance(intervals, list):
                continue
            span_lo, span_hi = (x0, x1) if side in ("top", "bottom") else (y0, y1)
            for interval in intervals:
                if not (isinstance(interval, list) and len(interval) == 2 and _num(interval[0]) and _num(interval[1])):
                    continue
                s, e = float(min(interval)), float(max(interval))
                if s <= span_lo and e >= span_hi:
                    continue  # full-wall opening; validator only treats partial gaps as doorways
                if side == "top":
                    segments.append((s, y0, e, y0))
                elif side == "bottom":
                    segments.append((s, y1, e, y1))
                elif side == "left":
                    segments.append((x0, s, x0, e))
                else:
                    segments.append((x1, s, x1, e))
    return segments


def _segment_distance(px: float, py: float, seg: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = seg
    dx, dy = x1 - x0, y1 - y0
    denom = dx * dx + dy * dy or 1.0
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / denom))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def _snap_doors(furniture: list[dict[str, Any]], segments: list[tuple[float, float, float, float]]) -> None:
    if not segments:
        return
    for item in furniture:
        if not isinstance(item, dict) or "door" not in str(item.get("image_name", "")).lower():
            continue
        if not _num(item.get("x")) or not _num(item.get("y")):
            continue
        nearest = min(segments, key=lambda seg: _segment_distance(item["x"], item["y"], seg))
        item["x"] = (nearest[0] + nearest[2]) / 2
        item["y"] = (nearest[1] + nearest[3]) / 2


def _footprint(item: dict[str, Any]) -> tuple[float, float]:
    key = re.sub(r"[^a-z0-9]", "", str(item.get("image_name", "")).lower())
    width_ft, height_ft = _SIZES.get(key, (3.0, 3.0))
    scale = float(item["scale"]) if _num(item.get("scale")) else 1.0
    angle = math.radians(float(item["angle"]) if _num(item.get("angle")) else 0.0)
    w, h = width_ft * _PX_PER_FT * scale, height_ft * _PX_PER_FT * scale
    return (abs(w * math.cos(angle)) + abs(h * math.sin(angle)),
            abs(w * math.sin(angle)) + abs(h * math.cos(angle)))


def _clamp_furniture(furniture: list[dict[str, Any]], rooms: list[dict[str, Any]]) -> None:
    rects = [r for r in (_rect(room) for room in rooms) if r is not None]
    for item in furniture:
        if not isinstance(item, dict) or "door" in str(item.get("image_name", "")).lower():
            continue
        if not _num(item.get("x")) or not _num(item.get("y")):
            continue
        cx, cy = float(item["x"]), float(item["y"])
        home = next((r for r in rects if r[0] < cx < r[2] and r[1] < cy < r[3]), None)
        if home is None:  # centre outside any room; snap to the nearest room centre
            home = min(rects, key=lambda r: math.hypot(cx - (r[0] + r[2]) / 2, cy - (r[1] + r[3]) / 2), default=None)
        if home is None:
            continue
        bw, bh = _footprint(item)
        lo_x, hi_x = home[0] + _FURNITURE_INSET + bw / 2, home[2] - _FURNITURE_INSET - bw / 2
        lo_y, hi_y = home[1] + _FURNITURE_INSET + bh / 2, home[3] - _FURNITURE_INSET - bh / 2
        if lo_x <= hi_x:  # item fits horizontally; clamp it inside
            item["x"] = max(lo_x, min(hi_x, cx))
        if lo_y <= hi_y:  # item fits vertically; clamp it inside
            item["y"] = max(lo_y, min(hi_y, cy))


def _separate_furniture(furniture: list[dict[str, Any]], rooms: list[dict[str, Any]]) -> None:
    """Push overlapping items in the same room apart along their least-penetration axis.

    Standard collision separation: minimal movement that preserves the model's chosen
    positions, unlike a full re-layout. Bounded passes; anything still crowded (a room
    too small for its furniture) is left for the validator to report back.
    """
    rects = [r for r in (_rect(room) for room in rooms) if r is not None]
    if not rects:
        return
    # Group items with their footprint into the room that contains their centre.
    groups: dict[tuple, list[dict[str, Any]]] = {}
    meta: dict[int, tuple[float, float]] = {}
    for item in furniture:
        if not isinstance(item, dict) or "door" in str(item.get("image_name", "")).lower():
            continue
        if not _num(item.get("x")) or not _num(item.get("y")):
            continue
        cx, cy = float(item["x"]), float(item["y"])
        home = next((r for r in rects if r[0] < cx < r[2] and r[1] < cy < r[3]), None)
        if home is None:
            continue
        groups.setdefault(home, []).append(item)
        meta[id(item)] = _footprint(item)

    for home, items in groups.items():
        if len(items) < 2:
            continue
        rx0, ry0, rx1, ry1 = home
        for _ in range(12):
            moved = False
            for a in range(len(items)):
                for b in range(a + 1, len(items)):
                    ia, ib = items[a], items[b]
                    aw, ah = meta[id(ia)]
                    bw, bh = meta[id(ib)]
                    dx = ib["x"] - ia["x"]
                    dy = ib["y"] - ia["y"]
                    px = (aw + bw) / 2 - abs(dx)  # x-overlap of the two footprints
                    py = (ah + bh) / 2 - abs(dy)  # y-overlap
                    if px <= 2 or py <= 2:
                        continue  # not overlapping (validator tolerates <= 4 px area)
                    if is_allowed_furniture_overlap(
                        ia.get("image_name"), ib.get("image_name"), px * py, aw * ah, bw * bh
                    ):
                        continue  # surface-mounted or incidental touch; keep as designed
                    if px < py:  # least penetration on x; split the push between both
                        shift = (px / 2 + 1) * (1 if dx >= 0 else -1)
                        ia["x"] = max(rx0 + aw / 2 + _FURNITURE_INSET, min(rx1 - aw / 2 - _FURNITURE_INSET, ia["x"] - shift))
                        ib["x"] = max(rx0 + bw / 2 + _FURNITURE_INSET, min(rx1 - bw / 2 - _FURNITURE_INSET, ib["x"] + shift))
                    else:
                        shift = (py / 2 + 1) * (1 if dy >= 0 else -1)
                        ia["y"] = max(ry0 + ah / 2 + _FURNITURE_INSET, min(ry1 - ah / 2 - _FURNITURE_INSET, ia["y"] - shift))
                        ib["y"] = max(ry0 + bh / 2 + _FURNITURE_INSET, min(ry1 - bh / 2 - _FURNITURE_INSET, ib["y"] + shift))
                    moved = True
            if not moved:
                break


def autofix_layout(layout: Any) -> Any:
    """Repair mechanical geometry in place and return the same object. Never raises."""
    try:
        if not isinstance(layout, dict):
            return layout
        rooms = [r for r in layout.get("rooms", []) if isinstance(r, dict)]
        furniture = [f for f in layout.get("furniture", []) if isinstance(f, dict)]
        if rooms:
            _repair_degenerate_rooms(rooms)
            _normalize_erased_keys(rooms, layout)
            _resolve_room_overlaps(rooms)
            _normalize_erased_intervals(rooms)
            _nudge_corner_openings(rooms)
            _mirror_openings(rooms)
            if furniture:
                _snap_doors(furniture, _gap_segments(rooms))
                _clamp_furniture(furniture, rooms)
                _separate_furniture(furniture, rooms)
                _clamp_furniture(furniture, rooms)  # re-seat anything the push nudged toward a wall
    except Exception:  # noqa: BLE001 - a repair bug must not break generation
        pass
    return layout


if __name__ == "__main__":
    # ponytail: assert-based self-check — the one runnable guard for the auto-fix.
    # Two rooms share a vertical wall at x=400; only the left room cut the opening.
    layout = {
        "rooms": [
            {"id": "a", "x0": 0, "y0": 0, "x1": 400, "y1": 300,
             "wall_erased_regions": {"right": [[120, 180]]}},
            {"id": "b", "x0": 400, "y0": 0, "x1": 800, "y1": 300, "wall_erased_regions": {}},
        ],
        "furniture": [
            {"id": "d", "image_name": "singlehand_door", "x": 380, "y": 150},   # off the gap
            {"id": "bed", "image_name": "double_bed", "x": 395, "y": 150},        # spilling past the wall
        ],
    }
    autofix_layout(layout)

    mirrored = layout["rooms"][1]["wall_erased_regions"].get("left")
    assert mirrored and abs(mirrored[0][0] - 120) < 1 and abs(mirrored[0][1] - 180) < 1, mirrored

    door = next(f for f in layout["furniture"] if f["id"] == "d")
    assert abs(door["x"] - 400) < 1 and abs(door["y"] - 150) < 1, (door["x"], door["y"])

    bed = next(f for f in layout["furniture"] if f["id"] == "bed")
    assert bed["x"] + _footprint(bed)[0] / 2 <= 400 - _FURNITURE_INSET + 0.01, bed["x"]

    # Degenerate rectangle rebuilt from its stated width/height, derived fields resynced.
    degenerate = {"rooms": [{"id": "z", "x0": 100, "y0": 100, "x1": 100, "y1": 340,
                             "width": 300, "height": 240, "width_real": 15, "height_real": 12}]}
    autofix_layout(degenerate)
    fixed = degenerate["rooms"][0]
    assert fixed["x1"] == 400 and fixed["width"] == 300 and fixed["width_real"] == 15, fixed

    # Two stacked wardrobes in one big room get separated with minimal movement.
    crowded = {"rooms": [{"id": "big", "x0": 0, "y0": 0, "x1": 600, "y1": 600}],
               "furniture": [{"id": "w1", "image_name": "wardrobe", "x": 300, "y": 300},
                             {"id": "w2", "image_name": "wardrobe", "x": 305, "y": 305}]}
    autofix_layout(crowded)
    w1, w2 = crowded["furniture"]
    fw, fh = _footprint(w1)
    px = (fw + fw) / 2 - abs(w2["x"] - w1["x"])
    py = (fh + fh) / 2 - abs(w2["y"] - w1["y"])
    assert px <= 2 or py <= 2, (px, py, w1, w2)

    # Appliances mounted on a surface (platform/counter/table/desk) keep their overlap;
    # the draftsman must not pull them apart, whatever the specific asset names are.
    mounted = {"rooms": [{"id": "kitchen", "x0": 0, "y0": 0, "x1": 600, "y1": 600}],
               "furniture": [
                   {"id": "platform", "image_name": "kitchen_platform", "x": 300, "y": 300},
                   {"id": "stove", "image_name": "stove", "x": 240, "y": 300},
                   {"id": "sink", "image_name": "sink", "x": 300, "y": 300},
                   {"id": "fridge", "image_name": "fridge", "x": 360, "y": 300},
               ]}
    before = [(item["x"], item["y"]) for item in mounted["furniture"]]
    autofix_layout(mounted)
    assert [(item["x"], item["y"]) for item in mounted["furniture"]] == before, mounted

    # An opening running past the room corner is clamped back onto the wall bounds
    # and slid at least 1 ft (20 px) clear of the corner.
    out_of_bounds = {"rooms": [{"id": "o", "x0": 0, "y0": 1100, "x1": 200, "y1": 1300,
                                "wall_erased_regions": {"right": [[1150, 1360]]}}]}
    autofix_layout(out_of_bounds)
    clamped = out_of_bounds["rooms"][0]["wall_erased_regions"]["right"]
    assert clamped and clamped[0][1] <= 1300 - _CORNER_MARGIN + 0.01, clamped

    # An opening jammed into the corner is slid inward to keep its 1 ft margin.
    corner = {"rooms": [{"id": "c", "x0": 0, "y0": 0, "x1": 400, "y1": 200,
                         "wall_erased_regions": {"top": [[2, 62]]}}]}
    autofix_layout(corner)
    top = corner["rooms"][0]["wall_erased_regions"]["top"]
    assert top and top[0][0] >= _CORNER_MARGIN - 0.01, top

    # A fully erased wall is pulled in to 1 ft piers so the corner-clearance rule passes.
    open_wall = {"rooms": [{"id": "w", "x0": 0, "y0": 0, "x1": 400, "y1": 300,
                            "wall_erased_regions": {"top": [[0, 400]]}}]}
    autofix_layout(open_wall)
    piered = open_wall["rooms"][0]["wall_erased_regions"]["top"]
    assert piered and piered[0] == [20.0, 380.0], piered

    # A room nested inside another (the model's classic bath-in-bedroom mistake) is freed
    # by cutting the container's boundary with the smallest area loss; the nested room
    # keeps its exact rect and the container's derived fields resync.
    nested = {"rooms": [
        {"id": "bath", "x0": 420, "y0": 700, "x1": 620, "y1": 820,
         "width": 200, "height": 120, "width_real": 10, "height_real": 6},
        {"id": "corr", "x0": 420, "y0": 700, "x1": 620, "y1": 1180,
         "width": 200, "height": 480, "width_real": 10, "height_real": 24},
    ]}
    autofix_layout(nested)
    bath_r, corr_r = nested["rooms"]
    assert bath_r["x0"] == 420 and bath_r["y1"] == 820, bath_r
    assert corr_r["y0"] == 820 and corr_r["height_real"] == 18, corr_r

    # An edge-band overlap makes the later room yield by the minimal cut.
    band = {"rooms": [
        {"id": "r1", "x0": 0, "y0": 0, "x1": 400, "y1": 300},
        {"id": "r2", "x0": 380, "y0": 0, "x1": 800, "y1": 300},
    ]}
    autofix_layout(band)
    r1, r2 = band["rooms"]
    remaining = max(0, min(r1["x1"], r2["x1"]) - max(r1["x0"], r2["x0"])) * max(
        0, min(r1["y1"], r2["y1"]) - max(r1["y0"], r2["y0"]))
    assert remaining <= 4 and r2["x0"] == 400, (r1, r2)

    # Compass-keyed wall sides are renamed to native sides on a north-up plan.
    compass_keyed = {"rooms": [{"id": "k", "x0": 0, "y0": 0, "x1": 400, "y1": 300,
                                "wall_erased_regions": {"west": [[120, 180]], "south": [[100, 160]]}}]}
    autofix_layout(compass_keyed)
    sides = compass_keyed["rooms"][0]["wall_erased_regions"]
    assert "west" not in sides and "south" not in sides, sides
    assert sides.get("left") == [[120.0, 180.0]] and sides.get("bottom") == [[100.0, 160.0]], sides

    # Idempotence: a second pass must not duplicate or grow the mirrored interval.
    before = [list(i) for i in layout["rooms"][1]["wall_erased_regions"]["left"]]
    autofix_layout(layout)
    assert layout["rooms"][1]["wall_erased_regions"]["left"] == before, "autofix must be idempotent"

    print("geometry_autofix self-check passed")
