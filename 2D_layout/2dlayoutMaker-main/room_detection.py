"""Planar-graph face extraction for the tkinter 2D editor.

Direct 1:1 port of ``src/domains/editor/services/roomDetection.ts`` from the React
Home Quest layout maker. Builds both directed edges for every wall, traces the
smallest counter-clockwise cycle from each unused edge, and emits interior faces
(positive signed area) as rooms. The lone exterior face (negative area) is
dropped. ``structural_joints`` mirrors ``structuralJoints.ts`` so beam endpoints
snap to the outer faces of the pillars they bear on.
"""
from __future__ import annotations

import math
import uuid
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

Point = Tuple[float, float]
VertexMap = Mapping[str, Mapping[str, object]]
WallMap = Mapping[str, Mapping[str, object]]


MAX_CYCLE_LENGTH = 100
DEGENERATE_AREA_EPS = 1.0  # < 1 cm² treated as degenerate (matches React < 1)


def _fresh_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _point(position: object) -> Point:
    """Coerce a stored position (list/tuple of two numbers or {x,y}) into a tuple."""
    if isinstance(position, dict):
        return float(position["x"]), float(position["y"])
    if isinstance(position, (list, tuple)) and len(position) == 2:
        return float(position[0]), float(position[1])
    raise ValueError(f"vertex position is not a 2D point: {position!r}")


def detect_rooms(vertices: VertexMap, walls: WallMap) -> List[dict]:
    """Find every enclosed room (minimal interior loop) of the wall graph.

    Each wall becomes two directed edges (one per direction). Starting from each
    unused directed edge we trace a loop using the "smallest counter-clockwise
    turn" rule, the standard face-extraction walk for planar graphs. Interior
    loops come out wound CCW (positive signed area); the lone exterior loop is
    CW (negative) and discarded.
    """
    rooms: List[dict] = []
    visited_edges: set = set()

    directed_edges: List[dict] = []
    edges_by_from: Dict[str, List[dict]] = {}

    def push_edge(edge: dict) -> None:
        directed_edges.append(edge)
        edges_by_from.setdefault(edge["from_vertex_id"], []).append(edge)

    for wall in walls.values():
        wall_id = wall["id"]
        start_id = wall["start_vertex_id"]
        end_id = wall["end_vertex_id"]
        push_edge({"wall_id": wall_id, "from_vertex_id": start_id, "to_vertex_id": end_id})
        push_edge({"wall_id": wall_id, "from_vertex_id": end_id, "to_vertex_id": start_id})

    for start_edge in directed_edges:
        key = f"{start_edge['from_vertex_id']}->{start_edge['to_vertex_id']}"
        if key in visited_edges:
            continue
        cycle = _trace_cycle(start_edge, vertices, edges_by_from)
        if cycle is None:
            continue
        for i in range(len(cycle)):
            from_id = cycle[i]
            to_id = cycle[(i + 1) % len(cycle)]
            visited_edges.add(f"{from_id}->{to_id}")
        polygon: List[Point] = []
        ok = True
        for vid in cycle:
            v = vertices.get(vid)
            if v is None:
                ok = False
                break
            try:
                polygon.append(_point(v.get("position")))
            except Exception:
                ok = False
                break
        if not ok or len(polygon) < 3:
            continue
        if compute_signed_area(polygon) > 0:
            rooms.append({
                "id": _fresh_id("room"),
                "boundary_vertex_ids": list(cycle),
                "room_type": "custom",
                "label": f"Room {len(rooms) + 1}",
                "floor_material_id": "default-floor",
            })
    return rooms


def _trace_cycle(start_edge, vertices: VertexMap, edges_by_from) -> Optional[List[str]]:
    """Trace one loop by always picking the largest CCW relative turn at each vertex."""
    cycle: List[str] = [start_edge["from_vertex_id"]]
    current_from = start_edge["from_vertex_id"]
    current_to = start_edge["to_vertex_id"]

    for _step in range(MAX_CYCLE_LENGTH):
        if current_to == start_edge["from_vertex_id"]:
            return cycle if len(cycle) >= 3 else None
        cycle.append(current_to)

        from_v = vertices.get(current_from)
        to_v = vertices.get(current_to)
        if from_v is None or to_v is None:
            return None
        try:
            from_pt = _point(from_v.get("position"))
            to_pt = _point(to_v.get("position"))
        except Exception:
            return None

        incoming_angle = math.atan2(from_pt[1] - to_pt[1], from_pt[0] - to_pt[0])

        candidates = edges_by_from.get(current_to) or []
        outgoing = [e for e in candidates if e["to_vertex_id"] != current_from]
        if not outgoing:
            return None

        best_edge: Optional[dict] = None
        best_angle = float("-inf")
        for edge in outgoing:
            dest_v = vertices.get(edge["to_vertex_id"])
            if dest_v is None:
                continue
            try:
                dest_pt = _point(dest_v.get("position"))
            except Exception:
                continue
            out_angle = math.atan2(dest_pt[1] - to_pt[1], dest_pt[0] - to_pt[0])
            rel = out_angle - incoming_angle
            while rel <= 0:
                rel += 2 * math.pi
            while rel > 2 * math.pi:
                rel -= 2 * math.pi
            if rel > best_angle:
                best_angle = rel
                best_edge = edge
        if best_edge is None:
            return None

        current_from = current_to
        current_to = best_edge["to_vertex_id"]
    return None


def compute_signed_area(polygon: Sequence[Point]) -> float:
    """Signed polygon area via the shoelace formula; >0 ⇒ CCW."""
    area = 0.0
    n = len(polygon)
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1] - polygon[j][0] * polygon[i][1]
    return area / 2.0


def validate_room_polygon(vertex_ids: Sequence[str], vertices: VertexMap) -> bool:
    """Validate a candidate room polygon: ≥3 vertices, non-degenerate, non-self-intersecting."""
    if len(vertex_ids) < 3:
        return False
    polygon: List[Point] = []
    for vid in vertex_ids:
        v = vertices.get(vid)
        if v is None:
            return False
        try:
            polygon.append(_point(v.get("position")))
        except Exception:
            return False
    if len(polygon) < 3:
        return False
    if abs(compute_signed_area(polygon)) < DEGENERATE_AREA_EPS:
        return False
    return not _has_self_intersection(polygon)


def _has_self_intersection(polygon: Sequence[Point]) -> bool:
    n = len(polygon)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _segments_intersect(polygon[i], polygon[(i + 1) % n], polygon[j], polygon[(j + 1) % n]):
                return True
    return False


def _segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    d1x, d1y = a2[0] - a1[0], a2[1] - a1[1]
    d2x, d2y = b2[0] - b1[0], b2[1] - b1[1]
    cross = d1x * d2y - d1y * d2x
    if abs(cross) < 1e-10:
        return False
    dx, dy = b1[0] - a1[0], b1[1] - a1[1]
    t = (dx * d2y - dy * d2x) / cross
    u = (dx * d1y - dy * d1x) / cross
    eps = 1e-6
    return eps < t < 1 - eps and eps < u < 1 - eps


def merge_vertices_by_position(vertices: Iterable[Mapping[str, object]], tolerance: float = 1.0) -> Tuple[Dict[str, dict], Dict[str, str]]:
    """Collapse vertices whose positions are within ``tolerance`` into one canonical vertex.

    Returns ``(merged_vertices, alias_map)`` where ``alias_map`` maps the
    original id → canonical merged id. Walls should update their
    ``start_vertex_id``/``end_vertex_id`` through ``alias_map``.
    """
    merged: Dict[str, dict] = {}
    alias: Dict[str, str] = {}
    buckets: List[Tuple[Point, str]] = []

    for vertex in vertices:
        if not isinstance(vertex, Mapping):
            continue
        original_id = vertex.get("id")
        if not original_id:
            continue
        try:
            point = _point(vertex.get("position"))
        except Exception:
            continue
        canonical_id: Optional[str] = None
        for known_point, known_id in buckets:
            if math.hypot(point[0] - known_point[0], point[1] - known_point[1]) <= tolerance:
                canonical_id = known_id
                break
        if canonical_id is None:
            canonical_id = str(original_id)
            merged[canonical_id] = {
                "id": canonical_id,
                "position": [point[0], point[1]],
                "source_canvas_id": vertex.get("source_canvas_id"),
            }
            buckets.append((point, canonical_id))
        alias[str(original_id)] = canonical_id
    return merged, alias


def _segment_crossing(a1: Point, a2: Point, b1: Point, b2: Point) -> Optional[Point]:
    """Return the proper crossing point of two segments, or None.

    Endpoint touches are excluded: those are already graph vertices and are handled by
    ``split_walls_at_vertices``.
    """
    d1x, d1y = a2[0] - a1[0], a2[1] - a1[1]
    d2x, d2y = b2[0] - b1[0], b2[1] - b1[1]
    cross = d1x * d2y - d1y * d2x
    if abs(cross) < 1e-10:
        return None
    dx, dy = b1[0] - a1[0], b1[1] - a1[1]
    t = (dx * d2y - dy * d2x) / cross
    u = (dx * d1y - dy * d1x) / cross
    eps = 1e-6
    if not (eps < t < 1 - eps and eps < u < 1 - eps):
        return None
    return a1[0] + t * d1x, a1[1] + t * d1y


def planarize(
    vertices: Mapping[str, Mapping[str, object]],
    walls: Iterable[Mapping[str, object]],
    tolerance: float = 1.0,
) -> Tuple[Dict[str, dict], List[dict]]:
    """Make the wall graph planar: add vertices where walls cross, then split walls.

    Two divider lines crossing inside a room only produce four faces if the crossing
    point is a real graph vertex; otherwise the face walk cannot turn there and emits
    one self-touching polygon.

    ponytail: O(n²) pairwise segment test. Fine for hand-drawn plans (tens of walls);
    if a generated plan ever pushes this into thousands of walls, replace the pair loop
    with a sweep line or a grid index over segment bounding boxes.
    """
    result_vertices: Dict[str, dict] = {
        str(vid): dict(vertex) for vid, vertex in vertices.items()
    }
    points: Dict[str, Point] = {}
    for vid, vertex in result_vertices.items():
        try:
            points[vid] = _point(vertex.get("position"))
        except Exception:
            continue

    def find_or_create(point: Point) -> str:
        for vid, known in points.items():
            if math.hypot(point[0] - known[0], point[1] - known[1]) <= tolerance:
                return vid
        new_id = _fresh_id("vertex-crossing")
        result_vertices[new_id] = {
            "id": new_id,
            "position": [point[0], point[1]],
            # A crossing is derived geometry, not a canvas item; keep it self-referential
            # so persisted vertices never carry a null source.
            "source_canvas_id": new_id,
        }
        points[new_id] = point
        return new_id

    wall_list = [dict(wall) for wall in walls]
    for index, wall in enumerate(wall_list):
        a1 = points.get(wall.get("start_vertex_id"))
        a2 = points.get(wall.get("end_vertex_id"))
        if a1 is None or a2 is None:
            continue
        for other in wall_list[index + 1:]:
            b1 = points.get(other.get("start_vertex_id"))
            b2 = points.get(other.get("end_vertex_id"))
            if b1 is None or b2 is None:
                continue
            crossing = _segment_crossing(a1, a2, b1, b2)
            if crossing is not None:
                find_or_create(crossing)

    return result_vertices, split_walls_at_vertices(result_vertices, wall_list, tolerance)


def split_walls_at_vertices(
    vertices: Mapping[str, Mapping[str, object]],
    walls: Iterable[Mapping[str, object]],
    tolerance: float = 1.0,
) -> List[dict]:
    """Split walls at vertices lying on their interior (T-junction splitting).

    ``detect_rooms`` can only turn at graph vertices. A divider line drawn across a
    room lands in the *middle* of the enclosing walls, so without breaking those
    walls at the junction the graph still has a single face and the room is never
    split in two. Sub-walls inherit the parent's ``source_canvas_id`` so callers can
    still map them back to the originating canvas item.
    """
    points: Dict[str, Point] = {}
    for vid, vertex in vertices.items():
        try:
            points[vid] = _point(vertex.get("position"))
        except Exception:
            continue

    result: List[dict] = []
    for wall in walls:
        start_id = wall.get("start_vertex_id")
        end_id = wall.get("end_vertex_id")
        a, b = points.get(start_id), points.get(end_id)
        if a is None or b is None:
            result.append(dict(wall))
            continue
        dx, dy = b[0] - a[0], b[1] - a[1]
        length_squared = dx * dx + dy * dy
        if length_squared <= tolerance * tolerance:
            result.append(dict(wall))
            continue

        hits: List[Tuple[float, str]] = []
        for vid, point in points.items():
            if vid == start_id or vid == end_id:
                continue
            t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_squared
            if t <= 0.0 or t >= 1.0:
                continue
            proj_x, proj_y = a[0] + t * dx, a[1] + t * dy
            if math.hypot(point[0] - proj_x, point[1] - proj_y) <= tolerance:
                hits.append((t, vid))
        if not hits:
            result.append(dict(wall))
            continue

        hits.sort(key=lambda item: item[0])
        chain: List[str] = [start_id]
        for _t, vid in hits:
            if vid != chain[-1]:
                chain.append(vid)
        chain.append(end_id)
        for index in range(len(chain) - 1):
            clone = dict(wall)
            clone["id"] = f"{wall.get('id')}-s{index}"
            clone["start_vertex_id"] = chain[index]
            clone["end_vertex_id"] = chain[index + 1]
            result.append(clone)
    return result


def dedupe_walls(walls: Iterable[Mapping[str, object]], alias: Mapping[str, str]) -> List[dict]:
    """Drop walls that collapse to the same undirected pair of vertices (and any zero-length walls).

    One wall per edge is required: ``detect_rooms`` marks visited edges by direction, so
    coincident duplicates (the Line tool's closing polygon, or two rooms patched along a
    shared edge) can swallow a face and make rooms stop being detected. Deciding which
    room *owns* a shared canvas line is handled later, when the drag group is built.
    """
    seen: set = set()
    result: List[dict] = []
    for wall in walls:
        if not isinstance(wall, Mapping):
            continue
        start = alias.get(wall.get("start_vertex_id"), wall.get("start_vertex_id"))
        end = alias.get(wall.get("end_vertex_id"), wall.get("end_vertex_id"))
        if not start or not end or start == end:
            continue
        edge_key = frozenset((start, end))
        if edge_key in seen:
            continue
        seen.add(edge_key)
        clone = dict(wall)
        clone["start_vertex_id"] = start
        clone["end_vertex_id"] = end
        result.append(clone)
    return result