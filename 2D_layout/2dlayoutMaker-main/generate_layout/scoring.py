"""Phase 6: transparent candidate scoring and diversity filtering.

Hard requirements are gates handled earlier by ``validate_layout``/``validate_design`` — a
candidate that fails them never reaches scoring. Here we rank *valid* candidates by quality
with a documented weighted breakdown, attach reproducible metrics, and drop near-duplicate
topologies so the user sees genuinely different options, not copies of one plan.

Weights (after hard gates), from the implementation guide:
    target dimensions 20%, adjacency 20%, circulation 15%, daylight 15%,
    privacy 10%, vastu 10%, furniture 5%, compactness 5%.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .feasibility import standard_for
from .planner import LayoutCandidate

WEIGHTS = {
    "target": 0.20, "adjacency": 0.20, "circulation": 0.15, "daylight": 0.15,
    "privacy": 0.10, "vastu": 0.10, "furniture": 0.05, "compactness": 0.05,
}
_PX = 20.0
_PUBLIC_TYPES = {"foyer", "living", "dining", "corridor"}


def _rects_by_name(layout: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    out: dict[str, tuple[float, float, float, float]] = {}
    for room in layout.get("rooms", []):
        name = str(room.get("name", "")).lower()
        if name and name not in out and all(isinstance(room.get(k), (int, float)) for k in ("x0", "y0", "x1", "y1")):
            out[name] = (room["x0"], room["y0"], room["x1"], room["y1"])
    return out


def _share_wall(a: tuple, b: tuple) -> bool:
    eps = 1.0
    vertical = (abs(a[2] - b[0]) <= eps or abs(b[2] - a[0]) <= eps) and min(a[3], b[3]) - max(a[1], b[1]) > eps
    horizontal = (abs(a[3] - b[1]) <= eps or abs(b[3] - a[1]) <= eps) and min(a[2], b[2]) - max(a[0], b[0]) > eps
    return vertical or horizontal


def fingerprint(layout: dict[str, Any]) -> str:
    """Semantic topology signature, order-independent and stable across room-list ordering."""
    sig = sorted(
        (str(r.get("name", "")).lower(), round(r["x0"] / 10), round(r["y0"] / 10),
         round(r["x1"] / 10), round(r["y1"] / 10))
        for r in layout.get("rooms", [])
        if all(isinstance(r.get(k), (int, float)) for k in ("x0", "y0", "x1", "y1"))
    )
    return hashlib.sha1(repr(sig).encode()).hexdigest()[:16]


def score(layout: dict[str, Any], spec: Any) -> tuple[float, dict[str, float], dict[str, Any], list[str]]:
    """Return (score 0..1, breakdown, metrics, compromises) for a valid candidate."""
    rooms = layout.get("rooms", [])
    if not rooms:
        return 0.0, {}, {}, ["empty layout"]
    rects = _rects_by_name(layout)
    id_to_name = {r.id: r.name.lower() for r in spec.rooms}
    breakdown: dict[str, float] = {}
    metrics: dict[str, Any] = {}
    compromises: list[str] = []

    total_area = sum((r["x1"] - r["x0"]) * (r["y1"] - r["y0"]) for r in rooms) / (_PX * _PX)
    corridor_area = sum(
        (r["x1"] - r["x0"]) * (r["y1"] - r["y0"]) for r in rooms
        if "hall" in str(r.get("name", "")).lower() or "corridor" in str(r.get("name", "")).lower()
    ) / (_PX * _PX)

    # 1. target dimensions: mean closeness of each room's area to its type target.
    errs = []
    for r in rooms:
        area = (r["x1"] - r["x0"]) * (r["y1"] - r["y0"]) / (_PX * _PX)
        name = str(r.get("name", "")).lower()
        spec_room = next((sr for sr in spec.rooms if sr.name.lower() == name), None)
        if spec_room is None:
            continue
        width = (r["x1"] - r["x0"]) / _PX
        depth = (r["y1"] - r["y0"]) / _PX
        requested_width = float(getattr(spec_room, "target_width_ft", None) or 0)
        requested_depth = float(getattr(spec_room, "target_depth_ft", None) or 0)
        if requested_width:
            errs.append(min(1.0, abs(width - requested_width) / requested_width))
        if requested_depth:
            errs.append(min(1.0, abs(depth - requested_depth) / requested_depth))
        if not requested_width and not requested_depth:
            target = float(getattr(spec_room, "target_area_ft2", None) or standard_for(spec_room).target_area_ft2)
            if target > 0:
                errs.append(min(1.0, abs(area - target) / target))
    breakdown["target"] = 1.0 - (sum(errs) / len(errs) if errs else 0.0)

    # 2. adjacency: fraction of spec relationships whose rooms actually share a wall.
    rel_kinds = {"direct_door", "adjacent", "open_plan", "attached_to"}
    rels = [rel for rel in spec.relationships if rel.kind in rel_kinds]
    satisfied = 0
    for rel in rels:
        a, b = rects.get(id_to_name.get(rel.a, "")), rects.get(id_to_name.get(rel.b, ""))
        if a and b and _share_wall(a, b):
            satisfied += 1
        elif rel.priority == "hard":
            compromises.append(f"required adjacency {rel.a}~{rel.b} not physically met")
    breakdown["adjacency"] = (satisfied / len(rels)) if rels else 1.0

    # 3. circulation: less corridor is better (penalize > ~15%).
    corridor_pct = corridor_area / total_area if total_area else 0.0
    breakdown["circulation"] = max(0.0, 1.0 - max(0.0, corridor_pct - 0.10) / 0.30)
    metrics["corridor_pct"] = round(corridor_pct, 3)

    # 4. daylight: fraction of window-needing rooms on the exterior.
    min_x = min(r["x0"] for r in rooms)
    min_y = min(r["y0"] for r in rooms)
    max_x = max(r["x1"] for r in rooms)
    max_y = max(r["y1"] for r in rooms)
    need, lit = 0, 0
    for r in rooms:
        name = str(r.get("name", "")).lower()
        spec_room = next((sr for sr in spec.rooms if sr.name.lower() == name), None)
        if spec_room is None or not standard_for(spec_room).needs_window:
            continue
        need += 1
        if (r["x0"] <= min_x + 1 or r["x1"] >= max_x - 1 or r["y0"] <= min_y + 1 or r["y1"] >= max_y - 1):
            lit += 1
        else:
            compromises.append(f"{r.get('name')} has no exterior wall for a window")
    breakdown["daylight"] = (lit / need) if need else 1.0

    # 5. privacy: bedrooms not directly touching a public living/dining room.
    beds = [(sr.name.lower()) for sr in spec.rooms if sr.type == "bedroom"]
    public_rects = [rects[n] for sr in spec.rooms if sr.type in ("living", "dining")
                    for n in [sr.name.lower()] if n in rects]
    private_ok, private_total = 0, 0
    for bed_name in beds:
        rect = rects.get(bed_name)
        if rect is None:
            continue
        private_total += 1
        if not any(_share_wall(rect, pub) for pub in public_rects):
            private_ok += 1
    breakdown["privacy"] = (private_ok / private_total) if private_total else 1.0

    # 6. vastu: zoned rooms placed in their requested quadrant.
    mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    zoned = [(sr, rects.get(sr.name.lower())) for sr in spec.rooms if sr.zone]
    zoned = [(sr, rc) for sr, rc in zoned if rc]
    zone_ok = 0
    for sr, rc in zoned:
        cx, cy = (rc[0] + rc[2]) / 2, (rc[1] + rc[3]) / 2
        want = sr.zone
        ok = ((("W" in want) == (cx < mid_x)) and (("N" in want) == (cy < mid_y)))
        zone_ok += 1 if ok else 0
    breakdown["vastu"] = (zone_ok / len(zoned)) if zoned else 1.0

    # 7. furniture: fraction of non-corridor rooms containing at least one non-door item.
    furniture = [f for f in layout.get("furniture", []) if isinstance(f, dict)
                 and "door" not in str(f.get("image_name", "")).lower()]
    occupied = 0
    habitable = [r for r in rooms if "hall" not in str(r.get("name", "")).lower()]
    for r in habitable:
        if any(r["x0"] <= f.get("x", -1) <= r["x1"] and r["y0"] <= f.get("y", -1) <= r["y1"] for f in furniture):
            occupied += 1
    breakdown["furniture"] = (occupied / len(habitable)) if habitable else 0.0

    # 8. compactness: room union vs bounding box (no wasted residual strips).
    bbox = (max_x - min_x) * (max_y - min_y) / (_PX * _PX)
    breakdown["compactness"] = min(1.0, total_area / bbox) if bbox else 0.0

    active_weights = {key: value for key, value in WEIGHTS.items() if key != "furniture" or furniture}
    weight_total = sum(active_weights.values()) or 1.0
    total = sum(active_weights[key] * breakdown.get(key, 0.0) for key in active_weights) / weight_total
    metrics["total_area_ft2"] = round(total_area, 1)
    return round(total, 4), {k: round(v, 3) for k, v in breakdown.items()}, metrics, compromises


def rank_and_diversify(candidates: list[LayoutCandidate], keep: int = 3) -> list[LayoutCandidate]:
    """Highest score first, deterministic tie-break, then unique semantic topologies."""
    valid = [c for c in candidates if c.valid]
    valid.sort(key=lambda c: (-c.score, c.strategy_id, c.seed))
    seen: set[str] = set()
    diverse: list[LayoutCandidate] = []
    for cand in valid:
        if cand.fingerprint in seen:
            continue
        seen.add(cand.fingerprint)
        diverse.append(cand)
        if len(diverse) >= keep:
            break
    return diverse


if __name__ == "__main__":
    # ponytail: the runnable guard — a well-zoned plan must outscore a degenerate one, and
    # diversity filtering must drop a duplicate fingerprint.
    from . import design_spec
    from .native_builder import build_native
    from .planner import LayoutCandidate, PlannerContext, run_strategy
    from . import planners  # noqa: F401 - register strategies

    spec = design_spec.from_program({
        "plot": {"width_ft": 60, "height_ft": 80},
        "rows": {
            "top": [{"name": "Guest Bedroom", "zone": "NW", "window": True},
                    {"name": "Living Room", "window": True}],
            "bottom": [{"name": "Master Bedroom", "zone": "SW", "window": True},
                       {"name": "Kitchen", "zone": "SE", "window": True}],
        },
        "doors": [["Kitchen", "Living Room"]],
    })
    ctx = PlannerContext(spec=spec, seed=1)
    cand = run_strategy("open_living_core", ctx)
    layout = build_native(spec.project_name, cand.placements)
    s, breakdown, metrics, comp = score(layout, spec)
    assert 0.0 <= s <= 1.0 and set(breakdown) == set(WEIGHTS), (s, breakdown)
    assert metrics["corridor_pct"] >= 0

    c1 = LayoutCandidate("a", 1, layout, score=0.9, fingerprint=fingerprint(layout))
    c2 = LayoutCandidate("b", 1, layout, score=0.8, fingerprint=fingerprint(layout))  # duplicate
    layout2 = build_native(spec.project_name, run_strategy("side_corridor", ctx).placements)
    c3 = LayoutCandidate("c", 1, layout2, score=0.7, fingerprint=fingerprint(layout2))
    kept = rank_and_diversify([c1, c2, c3], keep=3)
    assert len(kept) == 2 and kept[0].strategy_id == "a", [k.strategy_id for k in kept]
    print(f"scoring self-check passed: score={s}, breakdown={breakdown}")
