"""Phase 3 planner contracts and strategy registry.

Decouples orchestration (ai_client) from the concrete geometry engine. A *strategy* takes a
canonical ``DesignSpec`` + a deterministic seed and returns ``PlacedRoom`` rectangles (in
feet); ``native_builder`` turns any placement into a validated native v1 layout, and
``scoring`` ranks the results. The old comb engine is registered here as one strategy, not
rewritten, so it stays an operational fallback throughout the migration.

Pure data + a dict registry; no heavy class hierarchy. Offline-testable via the planners.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .design_spec import DesignSpec


@dataclass
class PlacedRoom:
    """A room positioned on the buildable envelope, in FEET (native builder scales to px)."""
    id: str
    name: str
    type: str
    x0: float
    y0: float
    x1: float
    y1: float
    zone: str | None = None
    needs_window: bool = True
    public: bool = False
    entrance: bool = False
    flooring: str = "wood"

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class PlannerContext:
    spec: "DesignSpec"
    seed: int = 0
    facing: str = "N"


@dataclass
class TopologyCandidate:
    strategy_id: str
    placements: list[PlacedRoom]
    seed: int
    explanation: str = ""


@dataclass
class LayoutCandidate:
    strategy_id: str
    seed: int
    layout: dict[str, Any]
    hard_errors: list[str] = field(default_factory=list)
    score: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    compromises: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    explanation: str = ""

    @property
    def valid(self) -> bool:
        return not self.hard_errors


# ------------------------------------------------------------------ strategy registry
# strategy_id -> callable(PlannerContext) -> TopologyCandidate | None. A strategy returns
# None when it does not apply to the given spec (e.g. courtyard on a tiny plot).
Strategy = Callable[[PlannerContext], "TopologyCandidate | None"]
_REGISTRY: dict[str, Strategy] = {}


def register(strategy_id: str) -> Callable[[Strategy], Strategy]:
    def deco(fn: Strategy) -> Strategy:
        _REGISTRY[strategy_id] = fn
        return fn
    return deco


def strategies() -> dict[str, Strategy]:
    return dict(_REGISTRY)


def run_strategy(strategy_id: str, ctx: PlannerContext) -> "TopologyCandidate | None":
    fn = _REGISTRY.get(strategy_id)
    return fn(ctx) if fn else None


def _touching(a: PlacedRoom, b: PlacedRoom, eps: float = 1e-6) -> bool:
    vertical = (abs(a.x1 - b.x0) <= eps or abs(b.x1 - a.x0) <= eps) and min(a.y1, b.y1) - max(a.y0, b.y0) >= 3.0
    horizontal = (abs(a.y1 - b.y0) <= eps or abs(b.y1 - a.y0) <= eps) and min(a.x1, b.x1) - max(a.x0, b.x0) >= 3.0
    return vertical or horizontal


def validate_topology(candidate: TopologyCandidate, spec: "DesignSpec") -> tuple[list[str], list[dict[str, str]]]:
    """Gate hard DesignSpec requirements before native building or weighted scoring."""
    from .feasibility import buildable_envelope, standard_for

    errors: list[str] = []
    evidence: list[dict[str, str]] = []
    width, depth = buildable_envelope(spec)
    placed = {room.id: room for room in candidate.placements if room.type != "corridor"}
    expected = {room.id: room for room in spec.rooms if room.type != "corridor"}
    if set(placed) != set(expected):
        missing = sorted(set(expected) - set(placed))
        extra = sorted(set(placed) - set(expected))
        errors.append(f"room identity mismatch (missing={missing}, extra={extra})")

    footprint = candidate.placements
    min_x = min((room.x0 for room in footprint), default=0.0)
    min_y = min((room.y0 for room in footprint), default=0.0)
    max_x = max((room.x1 for room in footprint), default=width)
    max_y = max((room.y1 for room in footprint), default=depth)
    mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2

    for room_id, room in placed.items():
        source = expected.get(room_id)
        if source is None:
            continue
        std = standard_for(source)
        ok = room.width + 1e-6 >= std.min_w_ft and room.height + 1e-6 >= std.min_h_ft
        aspect = max(room.width / max(room.height, 1e-6), room.height / max(room.width, 1e-6))
        ok = ok and aspect <= std.max_aspect + 1e-6
        if source.max_width_ft is not None:
            ok = ok and room.width <= source.max_width_ft + 1e-6
        if source.max_depth_ft is not None:
            ok = ok and room.height <= source.max_depth_ft + 1e-6
        if source.min_area_ft2 is not None:
            ok = ok and room.area + 1e-6 >= source.min_area_ft2
        if source.max_area_ft2 is not None:
            ok = ok and room.area <= source.max_area_ft2 + 1e-6
        if not ok:
            errors.append(
                f"{room_id} is {room.width:.1f}x{room.height:.1f} ft; minimum is "
                f"{std.min_w_ft:g}x{std.min_h_ft:g} ft with aspect <= {std.max_aspect:g}"
            )
        if room.x0 < -1e-6 or room.y0 < -1e-6 or room.x1 > width + 1e-6 or room.y1 > depth + 1e-6:
            errors.append(f"{room_id} lies outside the {width:g}x{depth:g} ft buildable envelope")
        evidence.append({"requirement": f"usable_dimensions:{room_id}", "status": "satisfied" if ok else "failed",
                         "evidence": f"{room.width:.1f}x{room.height:.1f} ft"})
        if source.zone and source.priority == "hard":
            zone_ok = (("W" in source.zone) == (room.cx < mid_x)
                       and ("N" in source.zone) == (room.cy < mid_y))
            if not zone_ok:
                errors.append(f"{room_id} is outside hard-required zone {source.zone}")
            evidence.append({"requirement": f"zone:{room_id}", "status": "satisfied" if zone_ok else "failed",
                             "evidence": source.zone})
        if source.exterior_window and source.priority == "hard":
            exterior = (abs(room.x0 - min_x) <= 1e-6 or abs(room.y0 - min_y) <= 1e-6
                        or abs(room.x1 - max_x) <= 1e-6 or abs(room.y1 - max_y) <= 1e-6)
            if not exterior:
                errors.append(f"{room_id} hard-requires exterior frontage")
            evidence.append({"requirement": f"exterior_window:{room_id}",
                             "status": "satisfied" if exterior else "failed",
                             "evidence": "touches exterior" if exterior else "interior room"})

    all_rooms = candidate.placements
    for index, first in enumerate(all_rooms):
        for second in all_rooms[index + 1:]:
            if min(first.x1, second.x1) - max(first.x0, second.x0) > 1e-6 and min(first.y1, second.y1) - max(first.y0, second.y0) > 1e-6:
                errors.append(f"{first.id} overlaps {second.id}")

    for rel in spec.relationships:
        if rel.priority != "hard":
            continue
        first, second = placed.get(rel.a), placed.get(rel.b)
        touching = bool(first and second and _touching(first, second))
        if rel.kind in {"direct_door", "adjacent", "open_plan", "attached_to"}:
            ok = touching
        elif rel.kind == "separate":
            ok = bool(first and second and not touching)
        elif rel.kind == "near":
            ok = bool(first and second and abs(first.cx - second.cx) + abs(first.cy - second.cy) <= 30.0)
        else:
            ok = bool(first and second)
        if not ok:
            errors.append(f"hard relationship {rel.id} ({rel.kind}) is not satisfied")
        evidence.append({"requirement": rel.id, "status": "satisfied" if ok else "failed",
                         "evidence": f"{rel.a} {rel.kind} {rel.b}"})

    # Guillotine/template partitions form a wall-adjacency graph. Require every occupied
    # room to be reachable from a real exterior entrance before native doors are cut.
    graph = {room.id: set() for room in all_rooms}
    for index, first in enumerate(all_rooms):
        for second in all_rooms[index + 1:]:
            if _touching(first, second):
                graph[first.id].add(second.id)
                graph[second.id].add(first.id)
    entrance = next((room for room in all_rooms if room.entrance), None)
    facing = str(spec.plot.get("facing") or "N")
    on_facing_edge = bool(entrance and (
        (facing == "N" and abs(entrance.y0 - min_y) <= 1e-6)
        or (facing == "S" and abs(entrance.y1 - max_y) <= 1e-6)
        or (facing == "W" and abs(entrance.x0 - min_x) <= 1e-6)
        or (facing == "E" and abs(entrance.x1 - max_x) <= 1e-6)
    ))
    if entrance is None:
        errors.append("candidate has no exterior entrance room")
    elif not on_facing_edge:
        errors.append(f"entrance room {entrance.id} does not touch the {facing} facing edge")
    else:
        seen, stack = set(), [entrance.id]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(graph.get(current, set()) - seen)
        unreachable = sorted(set(graph) - seen)
        if unreachable:
            errors.append(f"rooms are not reachable from the entrance: {unreachable}")
    evidence.append({"requirement": "entrance_connectivity", "status": "satisfied" if entrance and not errors else "failed",
                     "evidence": entrance.id if entrance else "missing entrance"})
    return errors, evidence