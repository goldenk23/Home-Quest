"""Pure geometry that mirrors ``src/domains/editor/services/structuralJoints.ts``.

Used by the tkinter parity toolbar so that a beam placed on two pillars seats on
their outer faces (instead of stopping at the post center), and so the joint
records the post↔beam link in v2 geometry.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence, Tuple

Point = Tuple[float, float]


class PillarFootprint:
    __slots__ = ("shape", "width", "depth")

    def __init__(self, shape: str, width: float, depth: float):
        self.shape = shape
        self.width = width
        self.depth = depth


def _reach_along(pillar: PillarFootprint, ux: float, uy: float) -> float:
    if pillar.shape == "round":
        return max(pillar.width, pillar.depth) / 2.0
    return abs(ux) * (pillar.width / 2.0) + abs(uy) * (pillar.depth / 2.0)


def extend_beam_ends_to_pillars(
    start: Point,
    end: Point,
    start_pillar: Optional[PillarFootprint],
    end_pillar: Optional[PillarFootprint],
) -> Tuple[Point, Point]:
    """Extend a beam's endpoints to the outer faces of the pillars it bears on.

    A beam whose endpoints sit on pillar centers is pushed outward so the beam
    fully spans and bears on each post instead of stopping at its center. Ends
    with no pillar are left unchanged. Direct port of the React helper.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return start, end
    ux = dx / length
    uy = dy / length

    if start_pillar is not None:
        reach = _reach_along(start_pillar, ux, uy)
        adj_start = (start[0] - ux * reach, start[1] - uy * reach)
    else:
        adj_start = start
    if end_pillar is not None:
        reach = _reach_along(end_pillar, ux, uy)
        adj_end = (end[0] + ux * reach, end[1] + uy * reach)
    else:
        adj_end = end
    return adj_start, adj_end


def pillar_at(pillar: Mapping, position: Point, tolerance: float) -> bool:
    """True when ``position`` is within ``tolerance`` of the pillar's center."""
    raw = pillar.get("position")
    if isinstance(raw, dict):
        cx, cy = float(raw.get("x", 0.0)), float(raw.get("y", 0.0))
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        cx, cy = float(raw[0]), float(raw[1])
    else:
        return False
    return math.hypot(cx - position[0], cy - position[1]) <= tolerance


def nearest_pillar(pillars, position: Point, tolerance: float) -> Optional[dict]:
    """Return the pillar closest to ``position`` within ``tolerance`` (or None)."""
    best = None
    best_dist = float("inf")
    for pillar in pillars or []:
        raw = pillar.get("position")
        if isinstance(raw, dict):
            cx, cy = float(raw.get("x", 0.0)), float(raw.get("y", 0.0))
        elif isinstance(raw, (list, tuple)) and len(raw) == 2:
            cx, cy = float(raw[0]), float(raw[1])
        else:
            continue
        d = math.hypot(cx - position[0], cy - position[1])
        if d <= tolerance and d < best_dist:
            best = pillar
            best_dist = d
    return best


def footprint_of(pillar: Mapping) -> PillarFootprint:
    return PillarFootprint(
        str(pillar.get("shape", "rect")),
        float(pillar.get("width_cm", 30) or 30),
        float(pillar.get("depth_cm", 30) or 30),
    )


def pillar_alignment_guide(pillars, position: Point, tolerance: float) -> dict:
    """Return the nearest same-column and same-row pillars, mirroring React guides."""
    column = row = None
    column_distance = row_distance = float("inf")
    px, py = position
    for pillar in pillars or []:
        raw = pillar.get("position")
        if isinstance(raw, dict):
            x, y = float(raw.get("x", 0.0)), float(raw.get("y", 0.0))
        elif isinstance(raw, (list, tuple)) and len(raw) == 2:
            x, y = float(raw[0]), float(raw[1])
        else:
            continue
        dx, dy = abs(x - px), abs(y - py)
        if dx <= tolerance and dy < column_distance:
            column_distance = dy
            column = {"pillar": pillar, "position": (x, y), "spacing": dy}
        if dy <= tolerance and dx < row_distance:
            row_distance = dx
            row = {"pillar": pillar, "position": (x, y), "spacing": dx}
    return {"column": column, "row": row}


def snap_deck_corner_outward(
    point: Point, centroid: Point, pillar: PillarFootprint,
) -> Point:
    """Push a center-snapped deck corner to the pillar's outward face."""
    ox, oy = point[0] - centroid[0], point[1] - centroid[1]
    if pillar.shape == "round":
        length = math.hypot(ox, oy) or 1.0
        radius = max(pillar.width, pillar.depth) / 2.0
        return point[0] + ox / length * radius, point[1] + oy / length * radius
    sx, sy = (1.0 if ox >= 0 else -1.0), (1.0 if oy >= 0 else -1.0)
    return point[0] + sx * pillar.width / 2.0, point[1] + sy * pillar.depth / 2.0


def expand_deck_to_pillars(
    points: Sequence[Point], pillars: Sequence[Optional[PillarFootprint]],
) -> list[Point]:
    """Wrap a convex deck around complete support footprints with short, clean corners."""
    if len(points) < 3 or len(points) != len(pillars):
        return [tuple(point) for point in points]
    turns = []
    for index, point in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        turn = ((point[0] - previous[0]) * (following[1] - point[1])
                - (point[1] - previous[1]) * (following[0] - point[0]))
        if abs(turn) > 1e-9:
            turns.append(turn > 0)
    if turns and not all(turn == turns[0] for turn in turns):
        # ponytail: preserve concave decks for now; use polygon union here if full
        # support-footprint wrapping is later required for concave deck outlines.
        centroid = (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
        return [
            snap_deck_corner_outward(tuple(point), centroid, pillar)
            if pillar is not None else tuple(point)
            for point, pillar in zip(points, pillars)
        ]

    candidates = []
    for point, pillar in zip(points, pillars):
        if pillar is None:
            candidates.append(tuple(point))
        elif pillar.shape == "round":
            radius = max(pillar.width, pillar.depth) / 2.0
            candidates.extend(
                (point[0] + math.cos(angle) * radius, point[1] + math.sin(angle) * radius)
                for angle in (index * math.pi / 4 for index in range(8))
            )
        else:
            half_width, half_depth = pillar.width / 2.0, pillar.depth / 2.0
            candidates.extend((
                (point[0] - half_width, point[1] - half_depth),
                (point[0] + half_width, point[1] - half_depth),
                (point[0] + half_width, point[1] + half_depth),
                (point[0] - half_width, point[1] + half_depth),
            ))

    ordered = sorted(set(candidates))
    if len(ordered) < 3:
        return ordered

    def cross(origin, first, second):
        return ((first[0] - origin[0]) * (second[1] - origin[1])
                - (first[1] - origin[1]) * (second[0] - origin[0]))

    lower = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]