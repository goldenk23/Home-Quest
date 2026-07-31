"""Deterministic native-VastuCraft-v1 room-shell engine.

The LLM is bad at exact coordinate arithmetic across dozens of coupled constraints,
so it only produces a compact *room program* (which rooms, their zone, which row they
sit in, which need windows, and the required interior doors). This module turns that
program into a complete, schema-valid room shell — rooms, mirrored wall openings, doors,
ventilation windows, a north entrance, labels, and compass — whose geometry satisfies
`ai_validator.validate_layout` and `validate_design(phase="structure")` BY CONSTRUCTION.

Layout scheme (a "comb"): one full-width public hallway across the vertical middle, a
row of rooms above it (touching the north edge) and a row below (touching the south
edge). Every room shares a wall with the hallway, so circulation is a star through public
space with no pass-through; every perimeter room owns exterior frontage for a window; and
left/right + top/bottom column placement lands each zoned room in its quadrant.

ponytail: full-depth rooms off a single central hallway are valid but visually deep;
the upgrade path is recursive slicing per row. Correctness (passing the validator) is the
goal here, not architectural elegance.
"""
from __future__ import annotations

from typing import Any

_PX = 20  # canvas pixels per foot (native v1 contract)
_HALL_FT = 4  # public hallway width in feet
_DOOR_FT = 3  # opening width for doors/windows
_MARGIN_FT = 1  # keep every opening >= 1 ft from a wall corner


def _snap_door_interval(lo: float, hi: float) -> tuple[float, float] | None:
    """A centered opening within [lo, hi], >= 1 ft from each end, or None if too short."""
    usable = (hi - _MARGIN_FT * _PX) - (lo + _MARGIN_FT * _PX)
    if usable <= 0:
        return None
    width = min(_DOOR_FT * _PX, usable)
    center = (lo + hi) / 2
    start = center - width / 2
    start = max(lo + _MARGIN_FT * _PX, min(start, hi - _MARGIN_FT * _PX - width))
    return (start, start + width)


def _add_gap(room: dict[str, Any], side: str, interval: tuple[float, float]) -> None:
    erased = room.setdefault("wall_erased_regions", {})
    erased.setdefault(side, []).append([float(interval[0]), float(interval[1])])


def _finalize_gaps(room: dict[str, Any]) -> None:
    """Sort and merge each wall's intervals so they pass the strict interval checks."""
    erased = room.get("wall_erased_regions")
    if not isinstance(erased, dict):
        return
    for side, intervals in list(erased.items()):
        cleaned = sorted([iv[0], iv[1]] for iv in intervals if iv[1] > iv[0])
        merged: list[list[float]] = []
        for start, end in cleaned:
            if merged and start <= merged[-1][1] + 0.01:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        erased[side] = merged


def _make_room(idx: int, name: str, x0: float, y0: float, x1: float, y1: float,
               flooring: str = "wood") -> dict[str, Any]:
    return {
        "id": f"room_{idx}",
        "name": name,
        "group_tag": f"room_group_{idx}",
        "group_id": idx,
        "x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1),
        "width": float(x1 - x0), "height": float(y1 - y0),
        "width_real": (x1 - x0) / _PX, "height_real": (y1 - y0) / _PX,
        "fill_mode": "walls_only",
        "fill_color": "#F1F5F9", "outline_color": "#334155",
        "wall_thickness_ft": 0.5,
        "flooring": {"has_flooring": True, "flooring_type": flooring},
    }


def _column_widths_ft(specs: list[dict[str, Any]], total_ft: int) -> list[int]:
    """Pack rooms into exactly `total_ft`, shrinking to fit so nothing runs off the plot.

    Every room keeps at least a 3 ft wall (enough to cut a real door), rooms get their
    requested min_ft when there is room, and the widths always sum to exactly total_ft so
    the row tiles the footprint edge-to-edge without going out of bounds.
    """
    n = len(specs)
    if n == 0:
        return []
    floor_ft = 3 if n * 3 <= total_ft else max(1, total_ft // n)
    widths = [max(floor_ft, int(spec.get("min_ft", 8))) for spec in specs]
    # If the requested minimums overflow the plot, trim the widest rooms down to the floor.
    while sum(widths) > total_ft:
        i = max(range(n), key=lambda k: widths[k])
        if widths[i] <= floor_ft:
            break  # everything already at the floor; nothing left to trim
        widths[i] -= 1
    # Hand out any remaining feet round-robin so the row fills the footprint exactly.
    leftover = total_ft - sum(widths)
    i = 0
    while leftover > 0:
        widths[i % n] += 1
        leftover -= 1
        i += 1
    return widths


# Rollout flag values for AI_LAYOUT_PLANNER. Both modes build the initial shell with the
# deterministic comb engine; "multi" additionally runs the feasibility/candidate/scoring
# pipeline in ai_client to explore and select diverse topologies. An unknown mode fails
# loudly rather than silently picking an arbitrary planner.
_PLANNER_MODES = ("comb", "multi")


def get_planner(mode: str):
    """Resolve the stage-1 shell builder by rollout flag; raise clearly on an unknown mode.

    Both "comb" and "multi" return the comb ``build_layout`` for the initial shell — "multi"
    layers additional strategies on top downstream (see ``ai_client._run_multi_planner``).
    """
    mode = (mode or "comb").strip().lower()
    if mode not in _PLANNER_MODES:
        raise ValueError(
            f"Unknown AI_LAYOUT_PLANNER={mode!r}; expected 'comb' (default) or 'multi'."
        )
    return build_layout


def build_layout(program: dict[str, Any]) -> dict[str, Any]:
    """Turn a room program into a complete, valid native v1 room shell.

    Deterministic: identical program input yields identical output, so a planner seed is
    unnecessary for this strategy (reserved in the flag/config for future randomized ones).
    """
    plot = program.get("plot", {})
    width_ft = int(round(float(plot.get("width_ft", 40))))
    height_ft = int(round(float(plot.get("height_ft", 40))))
    W, H = width_ft * _PX, height_ft * _PX

    top_specs = list(program.get("rows", {}).get("top", []))
    bottom_specs = list(program.get("rows", {}).get("bottom", []))

    top_h_ft = (height_ft - _HALL_FT) // 2
    bottom_h_ft = height_ft - _HALL_FT - top_h_ft
    hall_y0 = top_h_ft * _PX
    hall_y1 = hall_y0 + _HALL_FT * _PX

    rooms: list[dict[str, Any]] = []
    by_name: dict[str, dict[str, Any]] = {}
    idx = 0

    def lay_row(specs: list[dict[str, Any]], y0: float, y1: float) -> None:
        nonlocal idx
        specs = [s for s in specs if isinstance(s, dict) and s.get("name")]
        widths = _column_widths_ft(specs, width_ft)
        cursor_ft = 0
        for spec, w_ft in zip(specs, widths):
            x0 = cursor_ft * _PX
            x1 = (cursor_ft + w_ft) * _PX
            room = _make_room(idx, str(spec["name"]), x0, y0, x1, y1,
                              spec.get("flooring", "wood"))
            room["_spec"] = spec
            rooms.append(room)
            by_name[spec["name"]] = room
            idx += 1
            cursor_ft += w_ft

    lay_row(top_specs, 0, hall_y0)
    lay_row(bottom_specs, hall_y1, H)

    hall = _make_room(idx, program.get("corridor_name", "Central Hallway"),
                      0, hall_y0, W, hall_y1, "tile")
    hall["_spec"] = {"name": hall["name"], "public": True}
    rooms.append(hall)
    by_name[hall["name"]] = hall
    idx += 1

    furniture: list[dict[str, Any]] = []
    texts: list[dict[str, Any]] = []
    door_idx = 0

    def add_door(cx: float, cy: float) -> None:
        nonlocal door_idx
        furniture.append({"id": f"door_{door_idx}", "image_name": "singlehand_door",
                          "x": float(cx), "y": float(cy), "scale": 1, "angle": 0})
        door_idx += 1

    # Every room shares the hallway wall: cut a mirrored gap + door so circulation is a
    # star through public space (no pass-through).
    for room in rooms:
        if room is hall:
            continue
        interval = _snap_door_interval(room["x0"], room["x1"])
        if interval is None:
            continue
        top_row = room["y1"] <= hall_y0 + 0.5
        room_side = "bottom" if top_row else "top"
        hall_side = "top" if top_row else "bottom"
        _add_gap(room, room_side, interval)
        _add_gap(hall, hall_side, interval)
        add_door((interval[0] + interval[1]) / 2, hall_y0 if top_row else hall_y1)

    # Ventilation windows on each window-room's exterior edge (no door => a window).
    for room in rooms:
        if room is hall or not room.get("_spec", {}).get("window"):
            continue
        interval = _snap_door_interval(room["x0"], room["x1"])
        if interval is None:
            continue
        top_row = room["y1"] <= hall_y0 + 0.5
        # Offset the window from the hallway door so the two intervals never merge.
        shift = min(room["x1"] - _MARGIN_FT * _PX - interval[1],
                    max(0.0, (room["x1"] - room["x0"]) / 4))
        win = (interval[0] + shift, interval[1] + shift)
        if win[1] > room["x1"] - _MARGIN_FT * _PX:
            win = interval
        _add_gap(room, "top" if top_row else "bottom", (win[0], win[1]))

    # Main entrance: an exterior door on the north (top) wall of the entrance room.
    entrance = next((r for r in rooms if r.get("_spec", {}).get("entrance")), None)
    if entrance is not None:
        interval = _snap_door_interval(entrance["x0"], entrance["x1"])
        if interval is not None:
            _add_gap(entrance, "top", interval)
            add_door((interval[0] + interval[1]) / 2, 0.0)

    # Required interior doors between horizontally adjacent rooms (dining<->kitchen, etc.).
    for a_name, b_name in program.get("doors", []):
        a, b = by_name.get(a_name), by_name.get(b_name)
        if not a or not b:
            continue
        # Shared vertical wall at a common x with overlapping y-range.
        shared_x = None
        if abs(a["x1"] - b["x0"]) <= 0.5:
            shared_x = a["x1"]
        elif abs(b["x1"] - a["x0"]) <= 0.5:
            shared_x = b["x1"]
        if shared_x is None:
            continue
        lo, hi = max(a["y0"], b["y0"]), min(a["y1"], b["y1"])
        interval = _snap_door_interval(lo, hi)
        if interval is None:
            continue
        a_side = "right" if abs(a["x1"] - shared_x) <= 0.5 else "left"
        b_side = "right" if abs(b["x1"] - shared_x) <= 0.5 else "left"
        _add_gap(a, a_side, interval)
        _add_gap(b, b_side, interval)
        add_door(shared_x, (interval[0] + interval[1]) / 2)

    for room in rooms:
        _finalize_gaps(room)
        room.pop("_spec", None)
        texts.append({"id": f"label_{room['group_id']}", "content": room["name"],
                      "x": (room["x0"] + room["x1"]) / 2, "y": (room["y0"] + room["y1"]) / 2,
                      "tags": ["room_label"]})

    return {
        "version": "1.0",
        "metadata": {
            "project_name": str(program.get("project_name", "AI Layout"))[:120],
            "unit": "ft", "unit_scale": 1, "grid_spacing": 20, "zoom_level": 1,
            "canvas_width": float(W), "canvas_height": float(H), "wall_height_cm": 280,
        },
        "rooms": rooms,
        "shapes": [],
        "furniture": furniture,
        "text": texts,
        "compass": {"direction": "N", "north_deg_clockwise": 0},
    }


def _canonical_program() -> dict[str, Any]:
    """The recurring failing case: a north-facing zoned family home."""
    return {
        "project_name": "Engine Self Check",
        "plot": {"width_ft": 60, "height_ft": 80},
        "rows": {
            "top": [
                {"name": "Guest Bedroom", "zone": "NW", "window": True, "min_ft": 12},
                {"name": "Foyer", "public": True, "entrance": True, "min_ft": 8},
                {"name": "Formal Living Room", "window": True, "min_ft": 12},
                {"name": "Home Office", "window": True, "min_ft": 10},
                {"name": "Puja Room", "zone": "NE", "min_ft": 8},
            ],
            "bottom": [
                {"name": "Master Bedroom", "zone": "SW", "window": True, "min_ft": 12},
                {"name": "Master Bathroom", "window": True, "min_ft": 6},
                {"name": "Family Lounge", "window": True, "min_ft": 12},
                {"name": "Dining Room", "window": True, "min_ft": 10},
                {"name": "Kitchen", "zone": "SE", "window": True, "min_ft": 10},
            ],
        },
        "doors": [
            ["Master Bedroom", "Master Bathroom"],
            ["Family Lounge", "Dining Room"],
            ["Dining Room", "Kitchen"],
        ],
    }


if __name__ == "__main__":
    # ponytail: the one runnable guard — the engine's output must pass the real validator.
    from ai_validator import validate_design, validate_layout

    layout = build_layout(_canonical_program())
    native = validate_layout(layout)
    assert native == [], native

    brief = ("north-facing 60 ft x 80 ft vastu home with a master bedroom in the south-west, "
             "kitchen in the south-east, puja room in the north-east, guest bedroom in the "
             "north-west, a foyer, a formal living room, a family lounge, a dining room "
             "directly connected to the kitchen and family lounge, a home office, good "
             "ventilation, and an attached bathroom for the master bedroom")
    rooms_errors = validate_design(layout, brief, phase="rooms")
    assert rooms_errors == [], rooms_errors
    structure_errors = validate_design(layout, brief, phase="structure")
    assert structure_errors == [], structure_errors

    # Capacity regression: a row stuffed with more rooms than its min_ft can fit must still
    # pack within the plot (no out-of-bounds x1) rather than overflow the footprint.
    packed = build_layout({
        "plot": {"width_ft": 60, "height_ft": 80},
        "rows": {
            "top": [{"name": f"T{i}", "window": True, "min_ft": 12} for i in range(7)],
            "bottom": [{"name": f"B{i}", "window": True, "min_ft": 12} for i in range(8)],
        },
    })
    w = packed["metadata"]["canvas_width"]
    assert max(r["x1"] for r in packed["rooms"]) <= w, "rows must stay within the plot"
    assert validate_layout(packed) == [], validate_layout(packed)

    print("layout_engine self-check passed:",
          len(layout["rooms"]), "rooms,", len(layout["furniture"]), "doors")
