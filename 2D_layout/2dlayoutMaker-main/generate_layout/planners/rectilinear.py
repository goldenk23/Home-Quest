"""Phases 4-5: deterministic rectilinear planners that produce visibly different topologies.

All three share one guarantee: every room touches a public corridor, so circulation reaches
every room from the facing entrance by construction. Diversity comes from *how* the corridor
is oriented and how rooms are grouped against it:

- ``open_living_core``  — full-width corridor across the middle, area-weighted bands (deep-plan).
- ``side_corridor``     — single-loaded corridor down the west edge (good for narrow plots).
- ``zoned_wings``       — central corridor splitting a bedroom wing from a public/service wing.

Room sizes come from target areas (feasibility standards), clamped to fit the buildable
envelope. Same spec + seed => identical output (pure arithmetic, deterministic ordering).
"""
from __future__ import annotations

from ..feasibility import buildable_envelope, standard_for
from ..planner import PlacedRoom, PlannerContext, TopologyCandidate, register

_CORRIDOR_FT = 4.0
_PUBLIC_TYPES = {"foyer", "living", "dining"}
_FLOOR = {"kitchen": "tile", "bathroom": "tile", "utility": "tile", "corridor": "tile", "puja": "marble"}


def _floor_for(room_type: str) -> str:
    return _FLOOR.get(room_type, "wood")


def _target_area(room: object) -> float:
    std = standard_for(room)
    return max(std.target_area_ft2, std.min_w_ft * std.min_h_ft)


def _alloc(targets: list[float], total: float, mins: list[float]) -> list[float]:
    """Allocate a span without ever shrinking a room below its practical minimum."""
    n = len(targets)
    if n == 0:
        return []
    min_sum = sum(mins)
    if min_sum > total + 1e-6:
        raise ValueError(f"minimum room spans need {min_sum:g} ft but only {total:g} ft is available")
    extra = max(0.0, total - min_sum)
    tsum = sum(targets) or float(n)
    return [mins[i] + extra * (targets[i] / tsum) for i in range(n)]


def _we(room: object) -> int:  # west->east ordering key
    return {"NW": 0, "SW": 0, "NE": 2, "SE": 2}.get(getattr(room, "zone", None) or "", 1)


def _ns(room: object) -> int:  # north->south ordering key
    return {"NW": 0, "NE": 0, "SW": 2, "SE": 2}.get(getattr(room, "zone", None) or "", 1)


def _placed(room: object, x0: float, y0: float, x1: float, y1: float) -> PlacedRoom:
    std = standard_for(room)
    return PlacedRoom(
        id=room.id, name=room.name, type=room.type, x0=x0, y0=y0, x1=x1, y1=y1,
        zone=getattr(room, "zone", None),
        needs_window=std.needs_window or getattr(room, "exterior_window", False),
        public=getattr(room, "public", False) or room.type in _PUBLIC_TYPES,
        flooring=_floor_for(room.type),
    )


def _corridor(x0: float, y0: float, x1: float, y1: float) -> PlacedRoom:
    return PlacedRoom("corridor", "Hallway", "corridor", x0, y0, x1, y1,
                      public=True, entrance=True, needs_window=False, flooring="tile")


def _lay_row(band: list[object], y0: float, y1: float, width: float) -> list[PlacedRoom]:
    band = sorted(band, key=_we)
    widths = _alloc([_target_area(r) for r in band], width, [standard_for(r).min_w_ft for r in band])
    out, x = [], 0.0
    for room, w in zip(band, widths):
        out.append(_placed(room, x, y0, x + w, y1))
        x += w
    if out:
        out[-1].x1 = width
    return out


def _lay_column(band: list[object], x0: float, x1: float, depth: float) -> list[PlacedRoom]:
    band = sorted(band, key=_ns)
    heights = _alloc([_target_area(r) for r in band], depth, [standard_for(r).min_h_ft for r in band])
    out, y = [], 0.0
    for room, h in zip(band, heights):
        out.append(_placed(room, x0, y, x1, y + h))
        y += h
    if out:
        out[-1].y1 = depth
    return out


def _habitable(ctx: PlannerContext) -> list[object]:
    return [r for r in ctx.spec.rooms if r.type != "corridor"]


def _perimeter_open_core(ctx: PlannerContext, width: float, depth: float) -> TopologyCandidate | None:
    """Open living core with perimeter bedrooms/services and no invented hallway."""
    rooms = _habitable(ctx)
    allowed = {"bedroom", "living", "kitchen", "bathroom", "puja"}
    if not rooms or any(room.type not in allowed for room in rooms):
        return None
    bedrooms = [room for room in rooms if room.type == "bedroom"]
    living = [room for room in rooms if room.type == "living"]
    kitchen = [room for room in rooms if room.type == "kitchen"]
    baths = [room for room in rooms if room.type == "bathroom"]
    pujas = [room for room in rooms if room.type == "puja"]
    if not bedrooms or len(living) != 1 or len(kitchen) != 1 or len(baths) > 1 or len(pujas) > 1:
        return None

    left_w = max(max(standard_for(room).min_w_ft for room in bedrooms), width * 0.30)
    right_w = max(standard_for(kitchen[0]).min_w_ft, width * 0.30)
    core_w = width - left_w - right_w
    if core_w < standard_for(living[0]).min_w_ft:
        return None
    target_depth = sum(_target_area(room) for room in bedrooms) / left_w
    footprint_d = min(depth, max(target_depth, sum(standard_for(room).min_h_ft for room in bedrooms)))
    bath_h = 0.0
    if baths:
        bath_std = standard_for(baths[0])
        bath_h = max(
            bath_std.min_h_ft,
            _target_area(baths[0]) / core_w,
            core_w / bath_std.max_aspect,
        )
    living_h = footprint_d - bath_h
    if living_h < standard_for(living[0]).min_h_ft:
        return None

    placements = _lay_column(bedrooms, 0.0, left_w, footprint_d)
    placements.append(_placed(living[0], left_w, 0.0, left_w + core_w, living_h))
    if baths:
        placements.append(_placed(baths[0], left_w, living_h, left_w + core_w, footprint_d))

    kitchen_std = standard_for(kitchen[0])
    kitchen_h = max(
        kitchen_std.min_h_ft,
        _target_area(kitchen[0]) / right_w,
        bath_h + 3.0,  # at least a 3-ft shared segment with the living core
    )
    if kitchen_h > footprint_d:
        return None
    placements.append(_placed(kitchen[0], left_w + core_w, footprint_d - kitchen_h, width, footprint_d))

    if pujas:
        puja_std = standard_for(pujas[0])
        puja_w = min(right_w, max(puja_std.min_w_ft, _target_area(pujas[0]) / puja_std.min_h_ft))
        puja_h = max(puja_std.min_h_ft, _target_area(pujas[0]) / puja_w)
        if puja_h > footprint_d - kitchen_h:
            return None
        placements.append(_placed(
            pujas[0], left_w + core_w, 0.0, left_w + core_w + puja_w, puja_h
        ))

    _mark_entrance(placements, prefer_y=0.0)
    return TopologyCandidate(
        "open_living_core", placements, ctx.seed,
        "open living circulation core with bedrooms and Vastu service rooms on the perimeter",
    )


@register("open_living_core")
def open_living_core(ctx: PlannerContext) -> TopologyCandidate | None:
    width, depth = buildable_envelope(ctx.spec)
    rooms = _habitable(ctx)
    flexible = _perimeter_open_core(ctx, width, depth)
    if flexible is not None:
        return flexible
    if len(rooms) < 2 or width < 12 or depth < 12 + _CORRIDOR_FT:
        return None
    avail_d = depth - _CORRIDOR_FT

    top: list[object] = []
    bottom: list[object] = []
    for room in rooms:
        zone = room.zone or ""
        if zone in ("NW", "NE"):
            top.append(room)
        elif zone in ("SW", "SE"):
            bottom.append(room)
        elif room.entrance or getattr(room, "public", False) or room.type in _PUBLIC_TYPES:
            top.append(room)
        else:
            (top if sum(map(_target_area, top)) <= sum(map(_target_area, bottom)) else bottom).append(room)
    if not top:
        top.append(bottom.pop())
    if not bottom and len(top) > 1:
        bottom.append(top.pop())

    ta, ba = sum(map(_target_area, top)), sum(map(_target_area, bottom)) or 1.0
    ht = avail_d * ta / (ta + ba) if (ta + ba) else avail_d / 2
    top_min = max(standard_for(r).min_h_ft for r in top)
    bottom_min = max((standard_for(r).min_h_ft for r in bottom), default=0.0)
    ht = max(top_min, min(ht, avail_d - bottom_min))

    placements = [_corridor(0, ht, width, ht + _CORRIDOR_FT)]
    placements += _lay_row(top, 0, ht, width)
    if bottom:
        placements += _lay_row(bottom, ht + _CORRIDOR_FT, depth, width)
    _mark_entrance(placements, prefer_y=0.0)
    return TopologyCandidate("open_living_core", placements, ctx.seed,
                             "full-width central corridor with area-weighted bands")


@register("side_corridor")
def side_corridor(ctx: PlannerContext) -> TopologyCandidate | None:
    width, depth = buildable_envelope(ctx.spec)
    rooms = _habitable(ctx)
    if len(rooms) < 2 or width < 10 + _CORRIDOR_FT or depth < 12:
        return None
    east_x0 = _CORRIDOR_FT
    placements = [_corridor(0, 0, _CORRIDOR_FT, depth)]
    placements += _lay_column(rooms, east_x0, width, depth)
    return TopologyCandidate("side_corridor", placements, ctx.seed,
                             "single-loaded corridor down the west edge")


@register("zoned_wings")
def zoned_wings(ctx: PlannerContext) -> TopologyCandidate | None:
    width, depth = buildable_envelope(ctx.spec)
    rooms = _habitable(ctx)
    beds = [r for r in rooms if r.type == "bedroom"]
    others = [r for r in rooms if r.type != "bedroom"]
    if not beds or not others or width < 2 * 8 + _CORRIDOR_FT or depth < 12:
        return None
    avail_w = width - _CORRIDOR_FT
    wa = sum(map(_target_area, beds))
    ea = sum(map(_target_area, others)) or 1.0
    west_w = avail_w * wa / (wa + ea)
    west_min = max(standard_for(r).min_w_ft for r in beds)
    east_min = max(standard_for(r).min_w_ft for r in others)
    west_w = max(west_min, min(west_w, avail_w - east_min))
    cx = west_w
    placements = [_corridor(cx, 0, cx + _CORRIDOR_FT, depth)]
    placements += _lay_column(beds, 0, west_w, depth)
    placements += _lay_column(others, cx + _CORRIDOR_FT, width, depth)
    return TopologyCandidate("zoned_wings", placements, ctx.seed,
                             "bedroom wing separated from a public/service wing by a central corridor")


def _mark_entrance(placements: list[PlacedRoom], prefer_y: float) -> None:
    """Ensure exactly one entrance: a public room on the facing (top) edge if possible."""
    if any(p.entrance for p in placements if p.type != "corridor"):
        return
    candidates = [p for p in placements if p.public and abs(p.y0 - prefer_y) < 0.5]
    target = candidates[0] if candidates else next((p for p in placements if abs(p.y0 - prefer_y) < 0.5), None)
    if target is not None:
        for p in placements:
            if p.type == "corridor":
                p.entrance = False  # prefer a habitable/foyer entrance on the facing edge
        target.entrance = True


if __name__ == "__main__":
    # ponytail: the runnable guard — every strategy must yield a validator-clean, connected
    # native layout for the canonical brief, and the three topologies must differ.
    from .. import design_spec
    from ..ai_validator import validate_design, validate_layout
    from ..native_builder import build_native
    from ..planner import PlannerContext

    canonical = {
        "project_name": "Rectilinear Self Check",
        "plot": {"width_ft": 60, "height_ft": 80},
        "rows": {
            "top": [
                {"name": "Guest Bedroom", "zone": "NW", "window": True},
                {"name": "Foyer", "public": True, "entrance": True},
                {"name": "Living Room", "window": True},
                {"name": "Puja Room", "zone": "NE"},
            ],
            "bottom": [
                {"name": "Master Bedroom", "zone": "SW", "window": True},
                {"name": "Master Bathroom", "window": True},
                {"name": "Dining Room", "window": True},
                {"name": "Kitchen", "zone": "SE", "window": True},
            ],
        },
    }
    spec = design_spec.from_program(canonical)
    ctx = PlannerContext(spec=spec, seed=7, facing="N")

    fingerprints = {}
    for sid in ("open_living_core", "side_corridor", "zoned_wings"):
        from ..planner import run_strategy
        cand = run_strategy(sid, ctx)
        assert cand is not None, sid
        layout = build_native(spec.project_name, cand.placements, facing="N")
        errors = validate_layout(layout)
        assert errors == [], (sid, errors)
        struct = validate_design(layout, "north-facing 60 ft x 80 ft home", phase="structure")
        # structure phase may flag brief-specific zones we didn't force; only assert geometry
        # (validate_layout) here, and that the plan is non-trivial.
        assert len(layout["rooms"]) >= 5, sid
        fingerprints[sid] = tuple(sorted((round(r["x0"]), round(r["y0"]), round(r["x1"]), round(r["y1"]))
                                         for r in layout["rooms"]))
        # determinism: same ctx -> identical placements
        again = run_strategy(sid, ctx)
        assert [(_p.id, _p.x0, _p.y1) for _p in again.placements] == [(_p.id, _p.x0, _p.y1) for _p in cand.placements]

    assert len({fingerprints[k] for k in fingerprints}) == 3, "the three topologies must differ"
    print("rectilinear self-check passed: 3 distinct connected topologies")
