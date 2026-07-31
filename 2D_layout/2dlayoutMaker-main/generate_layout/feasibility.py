"""Phase 2 feasibility analysis + Phase 11 buildable-envelope math.

Turns a canonical ``DesignSpec`` into a go/no-go decision *before* any planner runs, so an
impossible brief produces a clear report with actionable alternatives instead of a plan full
of 3-ft "bedrooms". Practical room standards apply whether or not the user says "realistic
dimensions"; the planners reuse the same standards so a room never lands below its minimum.

Everything here is pure and offline-testable: run ``python feasibility.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import design_spec
from .design_spec import DesignSpec

# Practical residential minimums in feet, keyed by the DesignSpec semantic room type.
# (min_w, min_h) is the smallest usable rectangle; target_area drives area allocation; a
# room whose type is missing falls back to _DEFAULT_STANDARD. needs_window means the type
# must own exterior frontage for light/ventilation.
@dataclass(frozen=True)
class RoomStandard:
    min_w_ft: float
    min_h_ft: float
    target_area_ft2: float
    max_aspect: float = 3.0
    needs_window: bool = True


_DEFAULT_STANDARD = RoomStandard(7.0, 7.0, 80.0, 3.0, True)
ROOM_STANDARDS: dict[str, RoomStandard] = {
    "bedroom": RoomStandard(9.0, 9.0, 130.0, 2.2, True),
    "bathroom": RoomStandard(5.0, 6.0, 40.0, 2.5, True),
    "kitchen": RoomStandard(7.0, 8.0, 90.0, 2.5, True),
    "dining": RoomStandard(8.0, 8.0, 110.0, 2.2, True),
    "living": RoomStandard(10.0, 10.0, 160.0, 2.2, True),
    "foyer": RoomStandard(5.0, 5.0, 40.0, 3.0, False),
    "corridor": RoomStandard(3.0, 3.0, 40.0, 8.0, False),
    "puja": RoomStandard(4.0, 4.0, 30.0, 2.0, False),
    "office": RoomStandard(8.0, 8.0, 90.0, 2.2, True),
    "utility": RoomStandard(5.0, 5.0, 40.0, 3.0, True),
    "storage": RoomStandard(4.0, 4.0, 24.0, 3.0, False),
    "garage": RoomStandard(10.0, 18.0, 200.0, 2.0, False),
    "balcony": RoomStandard(4.0, 4.0, 30.0, 4.0, True),
    "room": _DEFAULT_STANDARD,
}

# Fraction of buildable area reserved for circulation + wall thickness before rooms compete.
CIRCULATION_ALLOWANCE = 0.14
WALL_ALLOWANCE = 0.06


def standard_for(room: Any) -> RoomStandard:
    room_type = room.type if hasattr(room, "type") else str(room)
    base = ROOM_STANDARDS.get(room_type, _DEFAULT_STANDARD)
    if not hasattr(room, "type"):
        return base
    min_w = max(base.min_w_ft, float(getattr(room, "min_width_ft", None) or 0))
    min_h = max(base.min_h_ft, float(getattr(room, "min_depth_ft", None) or 0))
    requested_width = float(getattr(room, "target_width_ft", None) or 0)
    requested_depth = float(getattr(room, "target_depth_ft", None) or 0)
    target = max(
        base.target_area_ft2,
        float(getattr(room, "target_area_ft2", None) or 0),
        requested_width * (requested_depth or min_h),
        requested_depth * (requested_width or min_w),
        min_w * min_h,
    )
    return RoomStandard(min_w, min_h, target, base.max_aspect, base.needs_window)


@dataclass
class FeasibilityReport:
    feasible: bool
    hard_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    min_required_area_ft2: float = 0.0
    available_area_ft2: float = 0.0
    buildable_ft: tuple[float, float] = (0.0, 0.0)  # (width, depth) after setbacks
    alternatives: list[str] = field(default_factory=list)


def buildable_envelope(spec: DesignSpec) -> tuple[float, float]:
    """Plot minus setbacks (Phase 11). Returns (width_ft, depth_ft), never negative."""
    plot = spec.plot or {}
    width = float(plot.get("width_ft", 0) or 0)
    depth = float(plot.get("depth_ft", 0) or 0)
    setbacks = plot.get("setbacks_ft") if isinstance(plot.get("setbacks_ft"), dict) else None
    if setbacks is None and isinstance(spec.building, dict):
        setbacks = spec.building.get("setbacks_ft")
    if isinstance(setbacks, dict):
        width -= float(setbacks.get("left", 0) or 0) + float(setbacks.get("right", 0) or 0)
        depth -= float(setbacks.get("front", 0) or 0) + float(setbacks.get("rear", 0) or 0)
    return (max(0.0, width), max(0.0, depth))


def _habitable(rooms: list[Any]) -> list[Any]:
    return [r for r in rooms if r.type != "corridor"]


def analyze(spec: DesignSpec) -> FeasibilityReport:
    """Decide whether ``spec`` can be built on its buildable envelope."""
    report = FeasibilityReport(feasible=True)
    bw, bd = buildable_envelope(spec)
    report.buildable_ft = (round(bw, 1), round(bd, 1))
    report.available_area_ft2 = round(bw * bd, 1)

    rooms = _habitable(spec.rooms)
    if int(spec.building.get("floors", 1) or 1) != 1:
        report.feasible = False
        report.hard_failures.append("the current native-v1 bridge supports one floor only")
        report.alternatives.append("generate one floor now or plan multi-floor support as a separate schema project")
    if not rooms:
        report.feasible = False
        report.hard_failures.append("the brief contains no habitable rooms")
        return report

    # Required area = sum of each room's max(target, min-rectangle) plus circulation/walls.
    room_area = 0.0
    for room in rooms:
        std = standard_for(room)
        min_rect = std.min_w_ft * std.min_h_ft
        room_area += max(std.target_area_ft2, min_rect)
    overhead = 1.0 / (1.0 - CIRCULATION_ALLOWANCE - WALL_ALLOWANCE)
    report.min_required_area_ft2 = round(room_area * overhead, 1)

    if report.available_area_ft2 + 0.5 < report.min_required_area_ft2:
        report.feasible = False
        deficit = report.min_required_area_ft2 - report.available_area_ft2
        report.hard_failures.append(
            f"buildable area {report.available_area_ft2:g} ft² is below the "
            f"{report.min_required_area_ft2:g} ft² needed for {len(rooms)} rooms plus circulation"
        )
        extra_side = (deficit / max(bd, 1)) if bd else 0
        report.alternatives.append(
            f"enlarge the plot by about {extra_side:.0f} ft on one side, remove/merge the "
            f"{max(1, round(deficit / 130)):d} lowest-priority room(s), or reduce target sizes"
        )

    # Exterior frontage: rooms needing a window must fit along the buildable perimeter.
    perimeter = 2 * (bw + bd)
    window_rooms = [r for r in rooms if standard_for(r).needs_window or r.exterior_window]
    frontage_need = sum(min(standard_for(r).min_w_ft, standard_for(r).min_h_ft) for r in window_rooms)
    if frontage_need > perimeter + 0.5:
        report.feasible = False
        report.hard_failures.append(
            f"{len(window_rooms)} rooms need exterior windows but their frontage "
            f"({frontage_need:g} ft) exceeds the buildable perimeter ({perimeter:g} ft)"
        )
        report.alternatives.append("reduce window-requiring rooms, allow interior rooms, or enlarge the plot")

    # Hard zone capacity: several rooms may legally share a quadrant, but their practical
    # minimum rectangles cannot exceed that quadrant's available area.
    zone_area: dict[str, float] = {}
    for room in rooms:
        if room.zone and room.priority == "hard":
            std = standard_for(room)
            zone_area[room.zone] = zone_area.get(room.zone, 0.0) + std.min_w_ft * std.min_h_ft
    quadrant_area = report.available_area_ft2 / 4
    for zone, needed in zone_area.items():
        if needed > quadrant_area + 0.5:
            report.hard_failures.append(
                f"hard zone {zone} needs at least {needed:g} ft² but its quadrant has about {quadrant_area:g} ft²"
            )
            report.feasible = False

    # Impossible hard adjacency: a room hard-required adjacent to more neighbours than a
    # rectangle can physically touch usefully is flagged as a warning (planner still tries).
    hard_adj: dict[str, int] = {}
    for rel in spec.relationships:
        if rel.priority == "hard" and rel.kind in ("direct_door", "adjacent", "open_plan", "attached_to"):
            hard_adj[rel.a] = hard_adj.get(rel.a, 0) + 1
            hard_adj[rel.b] = hard_adj.get(rel.b, 0) + 1
    for room_id, count in hard_adj.items():
        if count > 4:
            report.warnings.append(
                f"{room_id} hard-requires {count} adjacencies; a rectangle has only 4 walls"
            )

    if not report.warnings and report.feasible:
        report.assumptions.append("applied practical residential room minimums and ~20% circulation/wall overhead")
    return report


if __name__ == "__main__":
    # ponytail: the runnable guard — a feasible brief passes; an over-stuffed one fails with
    # an actionable alternative rather than silently shrinking rooms.
    canonical = {
        "project_name": "Feasibility Self Check",
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
                {"name": "Kitchen", "zone": "SE", "window": True},
            ],
        },
    }
    spec = design_spec.from_program(canonical)
    report = analyze(spec)
    assert report.feasible, report.hard_failures
    assert report.buildable_ft == (60.0, 80.0), report.buildable_ft
    assert report.min_required_area_ft2 < report.available_area_ft2

    # Setbacks shrink the envelope (Phase 11).
    spec.building["setbacks_ft"] = {"front": 5, "rear": 5, "left": 3, "right": 3}
    assert buildable_envelope(spec) == (54.0, 70.0), buildable_envelope(spec)

    # Dense brief on a tiny plot: infeasible with an actionable alternative.
    tiny = design_spec.from_program({
        "plot": {"width_ft": 18, "height_ft": 18},
        "rows": {"top": [{"name": f"Bedroom {i}", "window": True} for i in range(6)]},
    })
    tiny_report = analyze(tiny)
    assert not tiny_report.feasible and tiny_report.alternatives, tiny_report

    # Hard zone capacity: practical minima must fit inside the requested quadrant.
    conflict = design_spec.from_program(canonical)
    conflict.plot["width_ft"], conflict.plot["depth_ft"] = 20, 20
    for r in conflict.rooms[:2]:
        r.zone, r.priority = "NE", "hard"
    conflict_report = analyze(conflict)
    assert not conflict_report.feasible and any("NE" in f for f in conflict_report.hard_failures)

    print("feasibility self-check passed:", report.buildable_ft, "->", report.min_required_area_ft2, "ft² needed")
