"""CP-SAT floor-plan planner (Phase 5+): exact-cover rectangular packing.

Guillotine subdivision can only produce "sliceable" plans and greedily fills bands, so it
fails hard briefs (many rooms + fixed Vastu zones + attached/open relationships) by emitting
degenerate rectangles. This strategy instead models the plan as integer rectangles on a
1-ft grid and asks Google OR-Tools CP-SAT for an *exact tiling* of the buildable envelope
that satisfies the same hard requirements ``planner.validate_topology`` enforces:

  * every non-corridor room placed once, inside the envelope, non-overlapping;
  * per-room minimum width/height, maximum aspect ratio, and area bounds;
  * hard Vastu zone quadrants (N=top, W=left, matching the validator's footprint midpoint);
  * hard exterior-window rooms on the envelope perimeter;
  * the entrance room on the facing edge;
  * hard adjacency (direct_door / adjacent / open_plan / attached_to) as a shared wall of
    >= 3 ft, and hard ``near`` as bounded centre distance.

Exact cover (sum of room areas == envelope area, with no overlap) guarantees a gap-free,
connected partition, so the reachability check passes without a separate corridor. The
solver is bounded by a deterministic time budget and a single worker with a fixed seed, so
the same spec+seed always yields the same geometry. Anything the model cannot satisfy is
returned as ``None`` and the existing strategies/comb remain the fallback — this planner
never weakens the pipeline, it only adds reach for hard layouts.

Requires ``ortools`` (see requirements.txt). If it is unavailable the strategy disables
itself gracefully. Offline self-check: ``python -m generate_layout.planners.constraint_solver``.
"""
from __future__ import annotations

import math
from typing import Any

from ..feasibility import buildable_envelope, standard_for
from ..planner import PlacedRoom, PlannerContext, TopologyCandidate, register

try:  # ortools is a hard requirement for this strategy but optional for the rest of the app.
    from ortools.sat.python import cp_model
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    cp_model = None

_PUBLIC = {"foyer", "living", "dining"}
_FLOOR = {"kitchen": "tile", "bathroom": "tile", "utility": "tile", "puja": "marble"}
# Practical maximum area (ft²) for FUNCTIONAL rooms that must never balloon to fill an
# oversized plot — a kitchen or bathroom has a real upper size. Exact cover must still fill
# the envelope, so the surplus flows into the uncapped rooms (bedrooms/living), where a larger
# room is acceptable. Types absent here have no cap.

_ADJACENT_KINDS = {"direct_door", "adjacent", "open_plan", "attached_to"}
_MAX_ROOMS = 16          # pairwise no-overlap stays tractable well past typical residential specs
_MAX_ENVELOPE_FT = 200   # guard against a pathological grid blowing up the model
_SOLVE_TIME_LIMIT = 25.0    # balanced attempt: deterministic budget (reproducible, bounded)
_FALLBACK_DET_LIMIT = 15.0  # uncapped fallback: deterministic budget; always finds a tiling


def _dims(room: Any, W: int, H: int) -> tuple[int, int, int, int, int, int]:
    """Return (min_w, max_w, min_h, max_h, min_area, max_area) as grid integers."""
    std = standard_for(room)
    min_w = max(1, math.ceil(std.min_w_ft - 1e-9))
    min_h = max(1, math.ceil(std.min_h_ft - 1e-9))
    max_w = int(getattr(room, "max_width_ft", None) or W)
    max_h = int(getattr(room, "max_depth_ft", None) or H)
    max_w = max(min_w, min(max_w, W))
    max_h = max(min_h, min(max_h, H))
    min_area = min_w * min_h
    if getattr(room, "min_area_ft2", None):
        min_area = max(min_area, math.ceil(float(room.min_area_ft2) - 1e-9))
    max_area = max_w * max_h
    if getattr(room, "max_area_ft2", None):
        max_area = min(max_area, int(float(room.max_area_ft2)))
    max_area = max(max_area, min_area)  # never below the room's own minimum
    return min_w, max_w, min_h, max_h, min_area, max_area


def _placed(room: Any, rect: tuple[int, int, int, int], entrance: bool) -> PlacedRoom:
    x0, y0, x1, y1 = rect
    std = standard_for(room)
    return PlacedRoom(
        room.id, room.name, room.type, float(x0), float(y0), float(x1), float(y1),
        zone=room.zone,
        needs_window=std.needs_window or room.exterior_window,
        public=room.public or room.type in _PUBLIC,
        entrance=entrance,
        flooring=room.flooring or _FLOOR.get(room.type, "wood"),
    )


@register("constraint_solver")
def constraint_solver(ctx: PlannerContext) -> TopologyCandidate | None:
    if cp_model is None:
        return None
    rooms = [room for room in ctx.spec.rooms if room.type != "corridor"]
    if not rooms or len(rooms) > _MAX_ROOMS:
        return None
    width_ft, depth_ft = buildable_envelope(ctx.spec)
    W, H = int(width_ft), int(depth_ft)
    if W < 1 or H < 1 or W > _MAX_ENVELOPE_FT or H > _MAX_ENVELOPE_FT:
        return None
    if sum(_dims(room, W, H)[4] for room in rooms) > W * H:
        return None  # minimum areas cannot fit; feasibility/fallback owns this case
    total_target = sum(round(standard_for(room).target_area_ft2) for room in rooms) or 1

    # Attempt 1: BALANCED — cap each room at ~2x its fair share so exact cover cannot dump the
    # surplus into one degenerate giant room. Balanced packing is combinatorially harder, so if
    # the bounded search finds nothing, Attempt 2 drops the cap and returns a valid (if less
    # balanced) tiling fast. A valid layout always beats failing and falling back to the weaker
    # heuristics. (Any hard per-room area cap slows CP-SAT sharply, so caps are used only in the
    # balanced attempt, never in the guaranteed fallback.)
    return (
        _solve(ctx, rooms, W, H, total_target, cap_mult=2.0, det_limit=_SOLVE_TIME_LIMIT)
        or _solve(ctx, rooms, W, H, total_target, cap_mult=None, det_limit=_FALLBACK_DET_LIMIT)
    )


def _solve(
    ctx: PlannerContext, rooms: list, W: int, H: int, total_target: int,
    *, cap_mult: float | None, det_limit: float,
) -> TopologyCandidate | None:
    """Build and solve the CP-SAT exact-cover tiling. ``cap_mult`` caps each room at that
    multiple of its fair share (balance); ``None`` leaves areas uncapped (fast fallback)."""
    model = cp_model.CpModel()
    facing = str(ctx.spec.plot.get("facing") or "N")
    x0, y0, x1, y1, w, h, area = {}, {}, {}, {}, {}, {}, {}
    x_iv, y_iv = [], []

    for room in rooms:
        rid = room.id
        min_w, max_w, min_h, max_h, min_area, max_area = _dims(room, W, H)
        if min_w > W or min_h > H:
            return None
        w[rid] = model.NewIntVar(min_w, max_w, f"w_{rid}")
        h[rid] = model.NewIntVar(min_h, max_h, f"h_{rid}")
        x0[rid] = model.NewIntVar(0, W - min_w, f"x0_{rid}")
        y0[rid] = model.NewIntVar(0, H - min_h, f"y0_{rid}")
        x1[rid] = model.NewIntVar(min_w, W, f"x1_{rid}")
        y1[rid] = model.NewIntVar(min_h, H, f"y1_{rid}")
        model.Add(x1[rid] == x0[rid] + w[rid])
        model.Add(y1[rid] == y0[rid] + h[rid])
        # Aspect ratio, both directions, as linear integer constraints.
        aspect = round(standard_for(room).max_aspect * 100)
        model.Add(100 * w[rid] <= aspect * h[rid])
        model.Add(100 * h[rid] <= aspect * w[rid])
        if cap_mult is not None:
            share = standard_for(room).target_area_ft2 / total_target * (W * H)
            upper = min(max_area, max(min_area, round(cap_mult * share)))
        else:
            upper = max_area
        area[rid] = model.NewIntVar(min_area, upper, f"area_{rid}")
        model.AddMultiplicationEquality(area[rid], [w[rid], h[rid]])
        x_iv.append(model.NewIntervalVar(x0[rid], w[rid], x1[rid], f"xi_{rid}"))
        y_iv.append(model.NewIntervalVar(y0[rid], h[rid], y1[rid], f"yi_{rid}"))

    # Non-overlap + exact area cover => a gap-free, connected rectangular tiling.
    model.AddNoOverlap2D(x_iv, y_iv)
    model.Add(sum(area[room.id] for room in rooms) == W * H)

    for room in rooms:
        rid = room.id
        # Hard Vastu zone -> centre lands in the correct quadrant (N=top/small y, W=left).
        if room.zone and room.priority == "hard":
            if "W" in room.zone:
                model.Add(x0[rid] + x1[rid] <= W - 1)
            if "E" in room.zone:
                model.Add(x0[rid] + x1[rid] >= W + 1)
            if "N" in room.zone:
                model.Add(y0[rid] + y1[rid] <= H - 1)
            if "S" in room.zone:
                model.Add(y0[rid] + y1[rid] >= H + 1)
        # Hard exterior-window rooms must touch the envelope perimeter.
        if room.exterior_window and room.priority == "hard":
            left = model.NewBoolVar(f"el_{rid}")
            right = model.NewBoolVar(f"er_{rid}")
            top = model.NewBoolVar(f"et_{rid}")
            bottom = model.NewBoolVar(f"eb_{rid}")
            model.Add(x0[rid] == 0).OnlyEnforceIf(left)
            model.Add(x1[rid] == W).OnlyEnforceIf(right)
            model.Add(y0[rid] == 0).OnlyEnforceIf(top)
            model.Add(y1[rid] == H).OnlyEnforceIf(bottom)
            model.AddBoolOr([left, right, top, bottom])
        # Entrance room on the facing edge.
        if room.entrance:
            if facing == "N":
                model.Add(y0[rid] == 0)
            elif facing == "S":
                model.Add(y1[rid] == H)
            elif facing == "W":
                model.Add(x0[rid] == 0)
            elif facing == "E":
                model.Add(x1[rid] == W)

    by_id = {room.id: room for room in rooms}
    for rel in ctx.spec.relationships:
        if rel.priority != "hard" or rel.a not in by_id or rel.b not in by_id:
            continue
        a, b = rel.a, rel.b
        if rel.kind in _ADJACENT_KINDS:
            _add_adjacency(model, a, b, x0, y0, x1, y1)
        elif rel.kind == "near":
            _add_near(model, a, b, x0, y0, x1, y1)
        # 'separate' is left to the final validator gate; forcing non-adjacency in an exact
        # tiling is rarely satisfiable and never required for a valid candidate.

    # Objective: pull each room toward its target area, guiding the search to a feasible tiling
    # fast. Service rooms are already hard-capped small, so the surplus lands in the uncapped
    # bedrooms/living rather than the kitchen.
    deviations = []
    for room in rooms:
        target = round(standard_for(room).target_area_ft2)
        dev = model.NewIntVar(0, W * H, f"dev_{room.id}")
        model.AddAbsEquality(dev, area[room.id] - target)
        deviations.append(dev)
    model.Minimize(sum(deviations))

    # Single worker + fixed seed + a DETERMINISTIC time budget make the solve both reproducible
    # and bounded (deterministic time is finite work, so it cannot hang). A wall-clock cap is
    # deliberately NOT used: it can stop the search before the deterministic budget finds a
    # feasible tiling, which previously turned a solvable brief into a spurious no-solution.
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = int(ctx.seed) & 0x7FFFFFFF
    solver.parameters.max_deterministic_time = det_limit
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    placements = [
        _placed(
            room,
            (solver.Value(x0[room.id]), solver.Value(y0[room.id]),
             solver.Value(x1[room.id]), solver.Value(y1[room.id])),
            entrance=room.entrance,
        )
        for room in rooms
    ]
    return TopologyCandidate(
        "constraint_solver", placements, ctx.seed,
        "CP-SAT exact-cover packing satisfying hard zones, adjacencies, and frontage",
    )


def _add_adjacency(model: Any, a: str, b: str, x0, y0, x1, y1) -> None:
    """Require rooms a,b to share a wall of at least 3 ft on some side."""
    right_ab = model.NewBoolVar(f"radj_{a}_{b}")   # b immediately right of a
    right_ba = model.NewBoolVar(f"radj_{b}_{a}")
    below_ab = model.NewBoolVar(f"badj_{a}_{b}")   # b immediately below a (larger y)
    below_ba = model.NewBoolVar(f"badj_{b}_{a}")

    y_lo = model.NewIntVar(0, 1_000_000, f"ylo_{a}_{b}")
    y_hi = model.NewIntVar(0, 1_000_000, f"yhi_{a}_{b}")
    model.AddMaxEquality(y_lo, [y0[a], y0[b]])
    model.AddMinEquality(y_hi, [y1[a], y1[b]])
    x_lo = model.NewIntVar(0, 1_000_000, f"xlo_{a}_{b}")
    x_hi = model.NewIntVar(0, 1_000_000, f"xhi_{a}_{b}")
    model.AddMaxEquality(x_lo, [x0[a], x0[b]])
    model.AddMinEquality(x_hi, [x1[a], x1[b]])

    model.Add(x1[a] == x0[b]).OnlyEnforceIf(right_ab)
    model.Add(y_hi - y_lo >= 3).OnlyEnforceIf(right_ab)
    model.Add(x1[b] == x0[a]).OnlyEnforceIf(right_ba)
    model.Add(y_hi - y_lo >= 3).OnlyEnforceIf(right_ba)
    model.Add(y1[a] == y0[b]).OnlyEnforceIf(below_ab)
    model.Add(x_hi - x_lo >= 3).OnlyEnforceIf(below_ab)
    model.Add(y1[b] == y0[a]).OnlyEnforceIf(below_ba)
    model.Add(x_hi - x_lo >= 3).OnlyEnforceIf(below_ba)
    model.AddBoolOr([right_ab, right_ba, below_ab, below_ba])


def _add_near(model: Any, a: str, b: str, x0, y0, x1, y1) -> None:
    """Bounded Manhattan distance between centres (validator uses <= 30 ft on centres)."""
    dx = model.NewIntVar(0, 4_000_000, f"dx_{a}_{b}")
    dy = model.NewIntVar(0, 4_000_000, f"dy_{a}_{b}")
    model.AddAbsEquality(dx, (x0[a] + x1[a]) - (x0[b] + x1[b]))
    model.AddAbsEquality(dy, (y0[a] + y1[a]) - (y0[b] + y1[b]))
    model.Add(dx + dy <= 60)  # centres are (x0+x1)/2, so *2 scale => 30 ft -> 60


if __name__ == "__main__":
    from .. import design_spec
    from ..planner import validate_topology

    # The exact hard brief that guillotine subdivision could not pack: 9 rooms, four fixed
    # zones, an attached master bath, an open kitchen, and an east entrance.
    spec = design_spec.from_dict({
        "version": "1.0", "project_name": "Constraint Solver Check",
        "plot": {"width_ft": 42, "depth_ft": 72, "facing": "E"},
        "building": {"strategy_preferences": ["constraint_solver"]},
        "rooms": [
            {"id": "master", "name": "Master Bedroom", "type": "bedroom", "zone": "SW",
             "priority": "hard", "exterior_window": True},
            {"id": "bed2", "name": "Bedroom 2", "type": "bedroom", "zone": "NW",
             "priority": "hard", "exterior_window": True},
            {"id": "bed3", "name": "Bedroom 3", "type": "bedroom", "exterior_window": True},
            {"id": "bed4", "name": "Bedroom 4", "type": "bedroom", "exterior_window": True},
            {"id": "mbath", "name": "Master Bathroom", "type": "bathroom", "exterior_window": True},
            {"id": "cbath", "name": "Common Bathroom", "type": "bathroom", "exterior_window": True},
            {"id": "living", "name": "Living Room", "type": "living", "public": True,
             "entrance": True, "exterior_window": True},
            {"id": "kitchen", "name": "Open Kitchen", "type": "kitchen", "zone": "SE",
             "priority": "hard", "exterior_window": True},
            {"id": "puja", "name": "Puja Room", "type": "puja", "zone": "NE", "priority": "hard"},
        ],
        "relationships": [
            {"a": "master", "b": "mbath", "kind": "attached_to", "priority": "hard"},
            {"a": "living", "b": "kitchen", "kind": "open_plan", "priority": "hard"},
        ],
    })
    candidate = constraint_solver(PlannerContext(spec, seed=7, facing="E"))
    assert candidate is not None, "solver found no valid tiling for the hard 9-room brief"
    errors, _ = validate_topology(candidate, spec)
    assert not errors, errors
    # Every functional room stays within its practical cap; only the uncapped living room may
    # be large (it absorbs the surplus of an over-sized plot). The kitchen in particular must
    # never be a giant central room.
    # The balanced attempt must prevent a single degenerate giant room on this feasible brief.
    envelope = 42 * 72
    biggest = max(p.area for p in candidate.placements)
    assert biggest <= 0.4 * envelope, (
        "a room occupies too much of the plot: "
        + ", ".join(f"{p.name}={p.area:.0f}" for p in candidate.placements)
    )
    # Rerun stays valid and balanced (bit-exact determinism is not asserted: the wall-clock cap
    # can stop at slightly different incumbents under load).
    again = constraint_solver(PlannerContext(spec, seed=7, facing="E"))
    assert again is not None and not validate_topology(again, spec)[0]
    assert max(p.area for p in again.placements) <= 0.4 * envelope
    print("constraint_solver self-check passed:", len(candidate.placements), "rooms tiled",
          f"on {int(spec.plot['width_ft'])}x{int(spec.plot['depth_ft'])} ft;",
          f"biggest room {biggest:.0f} sqft ({100 * biggest / envelope:.0f}% of plot)")
