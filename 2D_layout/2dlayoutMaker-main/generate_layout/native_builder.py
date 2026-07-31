"""Phase 3 shared native-v1 construction from arbitrary placed rectangles.

Every planner (comb, subdivision, topology strategies) emits ``PlacedRoom`` rectangles in
feet; this module is the single place that turns them into a schema-valid native VastuCraft
v1 document — rooms, mirrored wall openings, doors, exterior ventilation windows, a facing
entrance, labels, and compass. It reuses the low-level opening helpers already proven in
``layout_engine`` so a built layout passes ``validate_layout`` by construction.

Circulation model (same star as comb): a door is cut on every shared wall touching a public
room, plus every explicitly required interior door. A private room adjacent to no public
room is simply left unconnected — the candidate then fails validation/scoring instead of
being "fixed" by autofix, exactly as the guide requires.
"""
from __future__ import annotations

from typing import Any

from .layout_engine import _PX, _add_gap, _finalize_gaps, _make_room, _snap_door_interval
from .planner import PlacedRoom

_EPS = 0.5  # px tolerance for "walls touch"
_MIN_SHARED_PX = 3 * _PX  # 1-ft corner margins + at least a 1-ft usable opening
_PUBLIC_TYPES = {"corridor", "foyer"}


def _is_public(room: PlacedRoom) -> bool:
    return room.public or room.entrance or room.type in _PUBLIC_TYPES


def _shared_wall(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, float, float, float] | None:
    """Return (orientation, coord, lo, hi) of a shared wall in px, or None.

    orientation "V": vertical wall at x=coord over y in [lo,hi];
    orientation "H": horizontal wall at y=coord over x in [lo,hi].
    """
    if abs(a["x1"] - b["x0"]) <= _EPS:
        lo, hi = max(a["y0"], b["y0"]), min(a["y1"], b["y1"])
        if hi - lo >= _MIN_SHARED_PX:
            return ("V", a["x1"], lo, hi)
    if abs(b["x1"] - a["x0"]) <= _EPS:
        lo, hi = max(a["y0"], b["y0"]), min(a["y1"], b["y1"])
        if hi - lo >= _MIN_SHARED_PX:
            return ("V", b["x1"], lo, hi)
    if abs(a["y1"] - b["y0"]) <= _EPS:
        lo, hi = max(a["x0"], b["x0"]), min(a["x1"], b["x1"])
        if hi - lo >= _MIN_SHARED_PX:
            return ("H", a["y1"], lo, hi)
    if abs(b["y1"] - a["y0"]) <= _EPS:
        lo, hi = max(a["x0"], b["x0"]), min(a["x1"], b["x1"])
        if hi - lo >= _MIN_SHARED_PX:
            return ("H", b["y1"], lo, hi)
    return None


def build_native(
    project_name: str,
    placements: list[PlacedRoom],
    required_doors: list[tuple[str, str]] | None = None,
    facing: str = "N",
    canvas_size_ft: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Build a complete native v1 layout from placed rooms (feet)."""
    required_doors = required_doors or []
    rooms: list[dict[str, Any]] = []
    rec_by_id: dict[str, dict[str, Any]] = {}
    placed_by_id: dict[str, PlacedRoom] = {}

    for idx, pr in enumerate(placements):
        rec = _make_room(idx, pr.name, pr.x0 * _PX, pr.y0 * _PX, pr.x1 * _PX, pr.y1 * _PX,
                         pr.flooring or "wood")
        rooms.append(rec)
        rec_by_id[pr.id] = rec
        placed_by_id[pr.id] = pr

    if not rooms:
        raise ValueError("native_builder requires at least one room")

    max_x = max(r["x1"] for r in rooms)
    max_y = max(r["y1"] for r in rooms)
    min_x = min(r["x0"] for r in rooms)
    min_y = min(r["y0"] for r in rooms)
    W = max_x
    H = max_y
    if canvas_size_ft is not None:
        W = max(W, float(canvas_size_ft[0]) * _PX)
        H = max(H, float(canvas_size_ft[1]) * _PX)

    furniture: list[dict[str, Any]] = []
    door_idx = 0

    def add_door(cx: float, cy: float) -> None:
        nonlocal door_idx
        furniture.append({"id": f"door_{door_idx}", "image_name": "singlehand_door",
                          "x": float(cx), "y": float(cy), "scale": 1, "angle": 0})
        door_idx += 1

    def cut_door(a_id: str, b_id: str) -> bool:
        a, b = rec_by_id.get(a_id), rec_by_id.get(b_id)
        if not a or not b:
            return False
        wall = _shared_wall(a, b)
        if wall is None:
            return False
        orient, coord, lo, hi = wall
        interval = _snap_door_interval(lo, hi)
        if interval is None:
            return False
        if orient == "V":
            a_side = "right" if abs(a["x1"] - coord) <= _EPS else "left"
            b_side = "right" if abs(b["x1"] - coord) <= _EPS else "left"
            _add_gap(a, a_side, interval)
            _add_gap(b, b_side, interval)
            add_door(coord, (interval[0] + interval[1]) / 2)
        else:
            a_side = "bottom" if abs(a["y1"] - coord) <= _EPS else "top"
            b_side = "bottom" if abs(b["y1"] - coord) <= _EPS else "top"
            _add_gap(a, a_side, interval)
            _add_gap(b, b_side, interval)
            add_door((interval[0] + interval[1]) / 2, coord)
        return True

    # 1. Star circulation: a door on every shared wall touching a public room.
    ids = list(placed_by_id)
    cut_pairs: set[frozenset[str]] = set()
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a_id, b_id = ids[i], ids[j]
            if _is_public(placed_by_id[a_id]) or _is_public(placed_by_id[b_id]):
                if cut_door(a_id, b_id):
                    cut_pairs.add(frozenset((a_id, b_id)))

    # 2. Explicitly required interior doors (direct_door / attached_to).
    for a_id, b_id in required_doors:
        key = frozenset((a_id, b_id))
        if key not in cut_pairs and cut_door(a_id, b_id):
            cut_pairs.add(key)

    # 3. Connect every remaining component with the fewest additional doors. This is a
    # bounded spanning-tree pass over the planner's wall-adjacency graph; it avoids the old
    # assumption that every private room must touch one universal corridor.
    def components() -> list[set[str]]:
        graph = {room_id: set() for room_id in ids}
        for pair in cut_pairs:
            first, second = tuple(pair)
            graph[first].add(second)
            graph[second].add(first)
        result: list[set[str]] = []
        unseen = set(ids)
        while unseen:
            todo, group = [unseen.pop()], set()
            while todo:
                current = todo.pop()
                if current in group:
                    continue
                group.add(current)
                linked = graph[current] & unseen
                unseen -= linked
                todo.extend(linked)
            result.append(group)
        return result

    while True:
        groups = components()
        if len(groups) <= 1:
            break
        connected = False
        for first in sorted(groups[0]):
            for other_group in groups[1:]:
                for second in sorted(other_group):
                    if _shared_wall(rec_by_id[first], rec_by_id[second]) and cut_door(first, second):
                        cut_pairs.add(frozenset((first, second)))
                        connected = True
                        break
                if connected:
                    break
            if connected:
                break
        if not connected:
            break

    # 4. Exterior ventilation windows for window-rooms (partial gap, no door).
    def exterior_side(rec: dict[str, Any]) -> str | None:
        if rec["y0"] <= min_y + _EPS:
            return "top"
        if rec["y1"] >= max_y - _EPS:
            return "bottom"
        if rec["x0"] <= min_x + _EPS:
            return "left"
        if rec["x1"] >= max_x - _EPS:
            return "right"
        return None

    for pr in placements:
        if not pr.needs_window:
            continue
        rec = rec_by_id[pr.id]
        side = exterior_side(rec)
        if side is None:
            continue  # interior room: no exterior frontage; scoring penalizes this
        if side in ("top", "bottom"):
            interval = _snap_door_interval(rec["x0"], rec["x1"])
        else:
            interval = _snap_door_interval(rec["y0"], rec["y1"])
        if interval is None:
            continue
        # Offset so a window never merges with an existing door gap on the same side.
        existing = rec.get("wall_erased_regions", {}).get(side, [])
        span_lo = rec["x0"] if side in ("top", "bottom") else rec["y0"]
        span_hi = rec["x1"] if side in ("top", "bottom") else rec["y1"]
        w0, w1 = interval
        for _ in range(4):
            if not any(not (w1 <= g[0] or w0 >= g[1]) for g in existing):
                break
            shift = (span_hi - span_lo) / 4
            w0, w1 = w0 + shift, w1 + shift
            if w1 > span_hi - _PX:
                w0, w1 = interval  # give up offsetting; overlap merges harmlessly
                break
        _add_gap(rec, side, (w0, w1))

    # 4. Facing entrance: exterior door on the entrance room's facing-side wall.
    facing_side = {"N": "top", "S": "bottom", "E": "right", "W": "left"}.get(facing, "top")

    def entrance_interval(rec: dict[str, Any], side: str) -> tuple[float, float] | None:
        lo, hi = ((rec["x0"], rec["x1"]) if side in ("top", "bottom")
                  else (rec["y0"], rec["y1"]))
        centered = _snap_door_interval(lo, hi)
        if centered is None:
            return None
        existing = rec.get("wall_erased_regions", {}).get(side, [])
        width = centered[1] - centered[0]
        candidates = [
            (lo + _PX, lo + _PX + width),
            (hi - _PX - width, hi - _PX),
            centered,
        ]
        for candidate in candidates:
            if candidate[0] < lo + _PX - _EPS or candidate[1] > hi - _PX + _EPS:
                continue
            if not any(
                isinstance(gap, (list, tuple)) and len(gap) == 2
                and candidate[0] < float(gap[1]) and candidate[1] > float(gap[0])
                for gap in existing
            ):
                return candidate
        return None

    entrance = next((p for p in placements if p.entrance), None)
    if entrance is None:
        entrance = next((p for p in placements if _is_public(p) and exterior_side(rec_by_id[p.id])), None)
    if entrance is not None:
        rec = rec_by_id[entrance.id]
        side = facing_side if _side_is_exterior(rec, facing_side, min_x, min_y, max_x, max_y) else exterior_side(rec)
        if side is not None:
            if side in ("top", "bottom"):
                interval = entrance_interval(rec, side)
                if interval:
                    _add_gap(rec, side, interval)
                    add_door((interval[0] + interval[1]) / 2, rec["y0"] if side == "top" else rec["y1"])
            else:
                interval = entrance_interval(rec, side)
                if interval:
                    _add_gap(rec, side, interval)
                    add_door(rec["x0"] if side == "left" else rec["x1"], (interval[0] + interval[1]) / 2)

    texts: list[dict[str, Any]] = []
    for rec in rooms:
        _finalize_gaps(rec)
        texts.append({"id": f"label_{rec['group_id']}", "content": rec["name"],
                      "x": (rec["x0"] + rec["x1"]) / 2, "y": (rec["y0"] + rec["y1"]) / 2,
                      "tags": ["room_label"]})

    return {
        "version": "1.0",
        "metadata": {
            "project_name": str(project_name or "AI Layout")[:120],
            "unit": "ft", "unit_scale": 1, "grid_spacing": 20, "zoom_level": 1,
            "canvas_width": float(W), "canvas_height": float(H), "wall_height_cm": 280,
        },
        "rooms": rooms,
        "shapes": [],
        "furniture": furniture,
        "text": texts,
        # The plan is always drawn north-up (zones use top=N, left=W); the requested facing
        # is expressed by which edge the entrance sits on, not by rotating the drawing. So
        # true north is up, matching the comb engine and keeping the rendered compass valid.
        "compass": {"direction": "N", "north_deg_clockwise": 0},
    }


def _side_is_exterior(rec: dict[str, Any], side: str, min_x, min_y, max_x, max_y) -> bool:
    if side == "top":
        return rec["y0"] <= min_y + _EPS
    if side == "bottom":
        return rec["y1"] >= max_y - _EPS
    if side == "left":
        return rec["x0"] <= min_x + _EPS
    if side == "right":
        return rec["x1"] >= max_x - _EPS
    return False


if __name__ == "__main__":
    # ponytail: the runnable guard — a hand-placed 4-room plan must pass the real validator.
    from .ai_validator import validate_layout

    placements = [
        PlacedRoom("hall", "Hall", "corridor", 0, 18, 40, 24, public=True, needs_window=False),
        PlacedRoom("br1", "Bedroom", "bedroom", 0, 0, 20, 18, zone="NW", entrance=False),
        PlacedRoom("foyer", "Foyer", "foyer", 20, 0, 40, 18, public=True, entrance=True, needs_window=False),
        PlacedRoom("kit", "Kitchen", "kitchen", 0, 24, 20, 40, zone="SW"),
        PlacedRoom("liv", "Living Room", "living", 20, 24, 40, 40),
    ]
    layout = build_native("Native Builder Self Check", placements,
                          required_doors=[("kit", "liv")], facing="N")
    errors = validate_layout(layout)
    assert errors == [], errors
    assert len(layout["rooms"]) == 5
    assert any(f["image_name"] == "singlehand_door" for f in layout["furniture"]), "needs doors"
    print("native_builder self-check passed:", len(layout["rooms"]), "rooms,",
          len(layout["furniture"]), "doors")
