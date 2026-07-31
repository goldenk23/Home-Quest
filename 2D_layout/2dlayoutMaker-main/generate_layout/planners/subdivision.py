"""Deterministic bounded guillotine subdivision planner (Phase 4)."""
from __future__ import annotations

import itertools
import math

from ..feasibility import buildable_envelope, standard_for
from ..planner import PlacedRoom, PlannerContext, TopologyCandidate, register

_SERVICE = {"bathroom", "kitchen", "utility", "storage", "garage"}
_PUBLIC = {"foyer", "living", "dining"}
_FLOOR = {"kitchen": "tile", "bathroom": "tile", "utility": "tile", "puja": "marble"}


def _target(room: object) -> float:
    std = standard_for(room)
    return max(std.target_area_ft2, std.min_w_ft * std.min_h_ft)


def _group(room: object) -> int:
    if room.type in _PUBLIC or getattr(room, "public", False) or getattr(room, "entrance", False):
        return 0
    if room.type in _SERVICE:
        return 1
    return 2


def _order(room: object) -> tuple[int, int, str]:
    zone = {"NW": 0, "NE": 1, "SW": 2, "SE": 3}.get(getattr(room, "zone", None), 4)
    return (_group(room), zone, room.id)


def _fits(room: object, width: float, depth: float) -> bool:
    std = standard_for(room)
    aspect = max(width / max(depth, 1e-9), depth / max(width, 1e-9))
    return width + 1e-6 >= std.min_w_ft and depth + 1e-6 >= std.min_h_ft and aspect <= std.max_aspect + 1e-6


def _placed(room: object, rect: tuple[float, float, float, float]) -> PlacedRoom:
    x0, y0, x1, y1 = rect
    std = standard_for(room)
    return PlacedRoom(
        room.id, room.name, room.type, x0, y0, x1, y1, zone=room.zone,
        needs_window=std.needs_window or room.exterior_window,
        public=room.public or room.type in _PUBLIC, entrance=room.entrance,
        flooring=room.flooring or _FLOOR.get(room.type, "wood"),
    )


def _hard_relationship_misses(placements: list[PlacedRoom], ctx: PlannerContext) -> int:
    from ..planner import _touching
    by_id = {room.id: room for room in placements}
    misses = 0
    for rel in ctx.spec.relationships:
        if rel.priority != "hard":
            continue
        if rel.a not in by_id or rel.b not in by_id:
            continue
        touching = _touching(by_id[rel.a], by_id[rel.b])
        if rel.kind in {"direct_door", "adjacent", "open_plan", "attached_to"} and not touching:
            misses += 1
        elif rel.kind == "separate" and touching:
            misses += 1
    return misses


def _optimize_relationship_assignments(
    placements: list[PlacedRoom], ctx: PlannerContext
) -> list[PlacedRoom]:
    """Reassign related room identities to existing leaves using bounded stdlib search."""
    graph = {room.id: set() for room in ctx.spec.rooms}
    for rel in ctx.spec.relationships:
        if rel.priority == "hard" and rel.kind in {"direct_door", "adjacent", "open_plan", "attached_to"}:
            if rel.a in graph and rel.b in graph:
                graph[rel.a].add(rel.b)
                graph[rel.b].add(rel.a)
    by_spec = {room.id: room for room in ctx.spec.rooms}
    result = list(placements)
    unseen = {room_id for room_id, links in graph.items() if links}
    while unseen:
        root = unseen.pop()
        component, todo = {root}, [root]
        while todo:
            current = todo.pop()
            linked = graph[current] & unseen
            unseen -= linked
            component |= linked
            todo.extend(linked)
        # ponytail: factorial search is capped at six related rooms (720 assignments).
        if len(component) > 6:
            continue
        slot_indexes = [index for index, placed in enumerate(result) if placed.id in component]
        if len(slot_indexes) != len(component):
            continue
        sources = [by_spec[room_id] for room_id in sorted(component)]
        best = result
        best_key = (_hard_relationship_misses(result, ctx), _structure_misses(result, ctx))
        for assignment in itertools.permutations(sources):
            candidate = list(result)
            valid = True
            for index, source in zip(slot_indexes, assignment):
                slot = result[index]
                if not _fits(source, slot.width, slot.height):
                    valid = False
                    break
                candidate[index] = _placed(source, (slot.x0, slot.y0, slot.x1, slot.y1))
            if not valid:
                continue
            key = (_hard_relationship_misses(candidate, ctx), _structure_misses(candidate, ctx))
            if key < best_key:
                best, best_key = candidate, key
                if key == (0, 0):
                    break
        result = best
    return result


def _optimize_all_assignments(placements: list[PlacedRoom], ctx: PlannerContext) -> list[PlacedRoom]:
    """Small-spec discrete assignment pass for zones, entrance, and hard adjacency."""
    sources = [room for room in ctx.spec.rooms if room.type != "corridor"]
    if sources:
        shift = ctx.seed % len(sources)
        sources = sources[shift:] + sources[:shift]
    if len(sources) != len(placements) or len(sources) > 9 or not ctx.spec.relationships:
        return placements
    best = placements
    best_key = (_hard_relationship_misses(best, ctx), _structure_misses(best, ctx))
    # ponytail: <=9 rooms bounds this at 362,880 stdlib permutations; use the installed
    # constraint solver only when the golden corpus needs larger discrete assignments.
    for assignment in itertools.permutations(sources):
        candidate: list[PlacedRoom] = []
        for source, slot in zip(assignment, placements):
            if not _fits(source, slot.width, slot.height):
                break
            candidate.append(_placed(source, (slot.x0, slot.y0, slot.x1, slot.y1)))
        if len(candidate) != len(placements):
            continue
        key = (_hard_relationship_misses(candidate, ctx), _structure_misses(candidate, ctx))
        candidate_ids = [room.id for room in candidate]
        best_ids = [room.id for room in best]
        if key < best_key or (key == best_key and candidate_ids != best_ids):
            best, best_key = candidate, key
            if key == (0, 0):
                break
    return best


def _partition(
    rooms: list[object], rect: tuple[float, float, float, float], budget: list[int],
    ctx: PlannerContext | None = None,
) -> tuple[list[PlacedRoom], float] | None:
    budget[0] -= 1
    if budget[0] < 0:
        return None
    x0, y0, x1, y1 = rect
    width, depth = x1 - x0, y1 - y0
    if len(rooms) == 1:
        if not _fits(rooms[0], width, depth):
            return None
        target = _target(rooms[0])
        error = abs(width * depth - target) / target
        return [_placed(rooms[0], rect)], error

    total = sum(_target(room) for room in rooms)
    running = 0.0
    split_candidates: list[int] = []
    for index, room in enumerate(rooms[:-1], 1):
        running += _target(room)
        split_candidates.append(index)
    # ponytail: explore every cut position but cap the whole recursion at 512 nodes; upgrade
    # to beam search only if the offline corpus proves this bounded search insufficient.
    split_candidates.sort(key=lambda index: abs(sum(_target(r) for r in rooms[:index]) - total / 2))
    orientations = ("vertical", "horizontal") if width >= depth else ("horizontal", "vertical")
    best: tuple[list[PlacedRoom], float] | None = None
    best_key: tuple[int, float] | None = None
    for index in split_candidates:
        left, right = rooms[:index], rooms[index:]
        ratio = sum(_target(room) for room in left) / total
        for orientation in orientations:
            if orientation == "vertical":
                cut = x0 + width * ratio
                first_rect, second_rect = (x0, y0, cut, y1), (cut, y0, x1, y1)
            else:
                cut = y0 + depth * ratio
                first_rect, second_rect = (x0, y0, x1, cut), (x0, cut, x1, y1)
            first = _partition(left, first_rect, budget, ctx)
            if first is None:
                continue
            second = _partition(right, second_rect, budget, ctx)
            if second is None:
                continue
            candidate = (first[0] + second[0], first[1] + second[1])
            key = (_hard_relationship_misses(candidate[0], ctx), candidate[1]) if ctx else (0, candidate[1])
            if best is None or best_key is None or key < best_key:
                best, best_key = candidate, key
    return best


def _footprints(ctx: PlannerContext, rooms: list[object]) -> list[tuple[float, float]]:
    width, depth = buildable_envelope(ctx.spec)
    target_area = sum(_target(room) for room in rooms) * 1.08
    ratio = width / max(depth, 1e-9)
    target_w = min(width, math.sqrt(target_area * ratio))
    target_d = min(depth, target_area / max(target_w, 1e-9))
    if target_d >= depth:
        target_d = depth
        target_w = min(width, target_area / max(target_d, 1e-9))
    footprints = [(target_w, target_d)]
    middle = [
        (min(width, width * 0.55), min(depth, depth * 0.55)),
        (min(width, width * 0.65), min(depth, depth * 0.60)),
        (min(width, width * 0.60), min(depth, depth * 0.65)),
        (min(width, width * 0.75), min(depth, depth * 0.75)),
        (min(width, width * 0.88), min(depth, depth * 0.68)),
        (min(width, width * 0.68), min(depth, depth * 0.88)),
    ]
    shift = ctx.seed % len(middle)
    for footprint in middle[shift:] + middle[:shift] + [(width, depth)]:
        if all(abs(footprint[0] - seen[0]) > 0.1 or abs(footprint[1] - seen[1]) > 0.1 for seen in footprints):
            footprints.append(footprint)
    return footprints


def _relationship_order(ctx: PlannerContext) -> list[object]:
    rooms = [room for room in ctx.spec.rooms if room.type != "corridor"]
    by_id = {room.id: room for room in rooms}
    graph = {room.id: set() for room in rooms}
    for rel in ctx.spec.relationships:
        if rel.priority == "hard" and rel.kind in {"direct_door", "adjacent", "open_plan", "attached_to"}:
            if rel.a in graph and rel.b in graph:
                graph[rel.a].add(rel.b)
                graph[rel.b].add(rel.a)
    ordered: list[object] = []
    unseen = set(by_id)
    while unseen:
        component_start = min(unseen, key=lambda room_id: (_group(by_id[room_id]), _order(by_id[room_id])))
        component = set()
        todo = [component_start]
        while todo:
            current = todo.pop()
            if current in component:
                continue
            component.add(current)
            todo.extend(graph[current] - component)
        start = min(component, key=lambda room_id: (-len(graph[room_id]), _order(by_id[room_id])))
        queue, emitted = [start], set()
        while queue:
            current = queue.pop(0)
            if current in emitted:
                continue
            emitted.add(current)
            ordered.append(by_id[current])
            queue.extend(sorted(graph[current] - emitted, key=lambda room_id: _order(by_id[room_id])))
        for room_id in sorted(component - emitted, key=lambda value: _order(by_id[value])):
            ordered.append(by_id[room_id])
        unseen -= component
    return ordered


def _structure_misses(placements: list[PlacedRoom], ctx: PlannerContext) -> int:
    max_x = max(room.x1 for room in placements)
    max_y = max(room.y1 for room in placements)
    mid_x, mid_y = max_x / 2, max_y / 2
    facing = str(ctx.spec.plot.get("facing") or "N")
    misses = 0
    for room in placements:
        lowered = room.name.lower()
        wanted = room.zone
        if wanted is None:
            if room.type == "kitchen":
                wanted = "SE"
            elif room.type == "puja":
                wanted = "NE"
            elif "master bedroom" in lowered:
                wanted = "SW"
            elif "guest bedroom" in lowered:
                wanted = "NW"
        if wanted:
            west = room.cx < mid_x
            north = room.cy < mid_y
            misses += int(("W" in wanted) != west or ("N" in wanted) != north)
        if room.entrance:
            on_edge = (
                (facing == "N" and room.y0 <= 1e-6)
                or (facing == "S" and room.y1 >= max_y - 1e-6)
                or (facing == "W" and room.x0 <= 1e-6)
                or (facing == "E" and room.x1 >= max_x - 1e-6)
            )
            misses += 10 * int(not on_edge)
    return misses


@register("recursive_subdivision")
def recursive_subdivision(ctx: PlannerContext) -> TopologyCandidate | None:
    base = sorted((room for room in ctx.spec.rooms if room.type != "corridor"), key=_order)
    related = _relationship_order(ctx)
    if not base:
        return None
    orders: list[list[object]] = []
    for source in (related, list(reversed(related)), base, list(reversed(base))):
        for offset in range(len(source)):
            order = source[offset:] + source[:offset]
            if [room.id for room in order] not in [[room.id for room in seen] for seen in orders]:
                orders.append(order)
    if orders:
        shift = ctx.seed % len(orders)
        orders = orders[shift:] + orders[:shift]
    best: tuple[int, float, list[PlacedRoom]] | None = None
    for rooms in orders:
        for width, depth in _footprints(ctx, rooms):
            result = _partition(rooms, (0.0, 0.0, width, depth), [512], ctx)
            if result is None:
                continue
            placements = _optimize_relationship_assignments(result[0], ctx)
            by_id = {room.id: room for room in placements}
            misses = 0
            from ..planner import _touching
            for rel in ctx.spec.relationships:
                if rel.priority == "hard" and rel.kind in {"direct_door", "adjacent", "open_plan", "attached_to"}:
                    if rel.a not in by_id or rel.b not in by_id or not _touching(by_id[rel.a], by_id[rel.b]):
                        misses += 1
            structure_misses = _structure_misses(placements, ctx)
            quality = (misses + structure_misses, result[1], placements)
            if best is None or quality[:2] < best[:2]:
                best = quality
            if quality[0] == 0:
                break
        if best is not None and best[0] == 0:
            break
    if best is None:
        return None
    placements = _optimize_all_assignments(best[2], ctx)
    if not any(room.entrance for room in placements):
        facing = str(ctx.spec.plot.get("facing") or "N")
        max_x = max(room.x1 for room in placements)
        max_y = max(room.y1 for room in placements)
        edge = [room for room in placements if (
            (facing == "N" and abs(room.y0) < 1e-6)
            or (facing == "S" and abs(room.y1 - max_y) < 1e-6)
            or (facing == "W" and abs(room.x0) < 1e-6)
            or (facing == "E" and abs(room.x1 - max_x) < 1e-6)
        )]
        preferred = [room for room in edge if room.public]
        if edge:
            (preferred or edge)[0].entrance = True
    return TopologyCandidate(
        "recursive_subdivision", placements, ctx.seed,
        "bounded guillotine subdivision grouped by public, service, and private use",
    )


if __name__ == "__main__":
    from .. import design_spec
    from ..planner import validate_topology

    spec = design_spec.from_dict({
        "version": "1.0", "project_name": "Subdivision Check",
        "plot": {"width_ft": 40, "depth_ft": 55, "facing": "N"},
        "building": {"strategy_preferences": ["recursive_subdivision"]},
        "rooms": [
            {"id": "foyer", "name": "Foyer", "type": "foyer", "public": True, "entrance": True},
            {"id": "living", "name": "Living", "type": "living", "public": True},
            {"id": "kitchen", "name": "Kitchen", "type": "kitchen"},
            {"id": "bed_1", "name": "Bedroom 1", "type": "bedroom"},
            {"id": "bed_2", "name": "Bedroom 2", "type": "bedroom"},
            {"id": "bath", "name": "Bathroom", "type": "bathroom"},
        ], "relationships": [],
    })
    candidate = recursive_subdivision(PlannerContext(spec, seed=7))
    assert candidate is not None
    errors, _ = validate_topology(candidate, spec)
    assert not errors, errors
    again = recursive_subdivision(PlannerContext(spec, seed=7))
    assert [(p.id, p.x0, p.y0, p.x1, p.y1) for p in candidate.placements] == [
        (p.id, p.x0, p.y0, p.x1, p.y1) for p in again.placements
    ]
    print("subdivision self-check passed:", len(candidate.placements), "rooms")