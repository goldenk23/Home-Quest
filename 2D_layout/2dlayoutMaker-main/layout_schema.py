"""Native layout v2 construction, v1 migration, and trust-boundary validation."""
from __future__ import annotations

from copy import deepcopy
import math
import uuid
from typing import Any, Iterable

VERSION = "2.0"
GEOMETRY_COLLECTIONS = (
    "vertices", "walls", "rooms", "openings", "furniture", "shapes", "text",
    "pillars", "beams", "deck_slabs", "railings",
)
DEFAULT_SUN_SETTINGS = {
    "time_hours": 12.0,
    "azimuth_deg": 120.0,
    "direction_override": False,
}
_REFERENCE_KEYS = {
    "start_vertex_id", "end_vertex_id", "boundary_vertex_ids", "opening_ids",
    "wall_id", "wall_ids", "room_id", "host_id", "deck_slab_id", "post_ids",
}


def _fail(path: str, message: str) -> None:
    raise ValueError(f"{path}: {message}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    return value


def _text(value: Any, path: str, *, trimmed: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "must be a non-empty string")
    if trimmed and value != value.strip():
        _fail(path, "must be trimmed")
    return value


def _number(value: Any, path: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail(path, "must be a finite number")
    result = float(value)
    if positive and result <= 0:
        _fail(path, "must be greater than zero")
    return result


def empty_geometry() -> dict[str, list[Any]]:
    return {name: [] for name in GEOMETRY_COLLECTIONS}


def new_project() -> dict[str, Any]:
    floor_id = f"floor-{uuid.uuid4()}"
    return {
        "version": VERSION,
        "metadata": {},
        "active_floor_id": floor_id,
        "floors": [{"id": floor_id, "name": "Ground Floor", "elevation_cm": 0, "geometry": empty_geometry()}],
        "sun_settings": deepcopy(DEFAULT_SUN_SETTINGS),
        "cross_floor_references": [],
    }


def _fresh_id(used: set[str], prefix: str = "entity") -> str:
    while True:
        candidate = f"{prefix}-{uuid.uuid4()}"
        if candidate not in used:
            used.add(candidate)
            return candidate


def _validate_v1_canvas(source: dict[str, Any]) -> None:
    _mapping(source.get("metadata", {}), "metadata")
    for collection in ("rooms", "furniture", "windows", "shapes", "text"):
        if collection in source:
            values = _array(source[collection], collection)
            for index, value in enumerate(values):
                _mapping(value, f"{collection}[{index}]")
    for index, room in enumerate(source.get("rooms", [])):
        base = f"rooms[{index}]"
        if not (("x0" in room or "x" in room) and ("y0" in room or "y" in room)
                and ("x1" in room or "width" in room) and ("y1" in room or "height" in room)):
            _fail(base, "must contain rectangle geometry")
        for field in ("x0", "y0", "x1", "y1", "x", "y", "width", "height"):
            if field in room:
                _number(room[field], f"{base}.{field}")
    for index, shape in enumerate(source.get("shapes", [])):
        base = f"shapes[{index}]"
        if shape.get("type") not in ("line", "rectangle", "oval", "polygon", "text"):
            _fail(f"{base}.type", "is unsupported")
        points = _array(shape.get("points"), f"{base}.points")
        for point_index, point in enumerate(points):
            _point(point, f"{base}.points[{point_index}]")
    for index, furniture in enumerate(source.get("furniture", [])):
        _number(furniture.get("x"), f"furniture[{index}].x")
        _number(furniture.get("y"), f"furniture[{index}].y")
    for index, text in enumerate(source.get("text", [])):
        if "content" not in text:
            _fail(f"text[{index}].content", "is required")


def migrate_v1_to_v2(document: dict[str, Any]) -> dict[str, Any]:
    """Return a v2 project while preserving the exact v1 canvas payload."""
    source = _mapping(document, "$")
    version = source.get("version", "1.0")
    if not isinstance(version, str) or version.split(".", 1)[0] != "1":
        _fail("version", "expected a 1.x document")
    _validate_v1_canvas(source)

    # geometry.canvas is intentionally opaque to the web importer. Keeping one
    # exact copy lets Tkinter round-trip every legacy field without weakening
    # the canonical v2 collections derived on the next serialization.
    geometry: dict[str, Any] = empty_geometry()
    geometry["canvas"] = deepcopy(source)
    if "compass" in source:
        geometry["compass"] = deepcopy(source["compass"])

    floor_id = f"floor-{uuid.uuid4()}"
    migrated = {
        "version": VERSION,
        "metadata": deepcopy(source.get("metadata", {})),
        "active_floor_id": floor_id,
        "floors": [{
            "id": floor_id,
            "name": "Ground Floor",
            "elevation_cm": 0,
            "geometry": geometry,
        }],
        "sun_settings": deepcopy(DEFAULT_SUN_SETTINGS),
        "cross_floor_references": [],
    }
    validate_v2(migrated)
    return migrated


def _point(value: Any, path: str) -> tuple[float, float]:
    if isinstance(value, dict):
        return _number(value.get("x"), f"{path}.x"), _number(value.get("y"), f"{path}.y")
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return _number(value[0], f"{path}[0]"), _number(value[1], f"{path}[1]")
    _fail(path, "must be an {x, y} object or two-number array")


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]) -> bool:
    eps = 1e-9
    return (min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps and
            min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps)


def _segments_intersect(a: tuple[float, float], b: tuple[float, float],
                        c: tuple[float, float], d: tuple[float, float]) -> bool:
    eps = 1e-9
    o1, o2, o3, o4 = (_orientation(a, b, c), _orientation(a, b, d),
                      _orientation(c, d, a), _orientation(c, d, b))
    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and \
       ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)):
        return True
    return ((abs(o1) <= eps and _on_segment(a, b, c)) or
            (abs(o2) <= eps and _on_segment(a, b, d)) or
            (abs(o3) <= eps and _on_segment(c, d, a)) or
            (abs(o4) <= eps and _on_segment(c, d, b)))


def _validate_polygon(raw: Any, path: str) -> None:
    values = _array(raw, path)
    points = [_point(value, f"{path}[{index}]") for index, value in enumerate(values)]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3 or len(set(points)) < 3:
        _fail(path, "must contain at least three distinct points")
    area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))
    if abs(area2) <= 1e-9:
        _fail(path, "must have non-zero area")
    # ponytail: O(n^2) is appropriate for interactive deck polygons; use a sweep-line only for large imports.
    count = len(points)
    for first in range(count):
        a, b = points[first], points[(first + 1) % count]
        if a == b:
            _fail(f"{path}[{first}]", "edge must have non-zero length")
        for second in range(first + 1, count):
            if second == first or second == (first + 1) % count or first == (second + 1) % count:
                continue
            c, d = points[second], points[(second + 1) % count]
            if _segments_intersect(a, b, c, d):
                _fail(path, f"self-intersection between edges {first} and {second}")


def _validate_structures(geometry: dict[str, Any], path: str) -> None:
    for index, pillar in enumerate(geometry.get("pillars", [])):
        base = f"{path}.pillars[{index}]"
        item = _mapping(pillar, base)
        for field in ("width_cm", "depth_cm", "height_cm"):
            _number(item.get(field), f"{base}.{field}", positive=True)
        if "elevation_cm" in item:
            _number(item["elevation_cm"], f"{base}.elevation_cm")
        if "position" in item:
            _point(item["position"], f"{base}.position")
    for index, beam in enumerate(geometry.get("beams", [])):
        base = f"{path}.beams[{index}]"
        item = _mapping(beam, base)
        for field in ("width_cm", "depth_cm"):
            _number(item.get(field), f"{base}.{field}", positive=True)
        start, end = _point(item.get("start"), f"{base}.start"), _point(item.get("end"), f"{base}.end")
        if math.hypot(end[0] - start[0], end[1] - start[1]) <= 1e-9:
            _fail(f"{base}.end", "must differ from start")
        if "elevation_cm" in item:
            _number(item["elevation_cm"], f"{base}.elevation_cm")
    for index, deck in enumerate(geometry.get("deck_slabs", [])):
        base = f"{path}.deck_slabs[{index}]"
        item = _mapping(deck, base)
        _number(item.get("thickness_cm"), f"{base}.thickness_cm", positive=True)
        if "elevation_cm" in item:
            _number(item["elevation_cm"], f"{base}.elevation_cm")
        _validate_polygon(item.get("polygon"), f"{base}.polygon")


def _iter_references(entity: dict[str, Any], base: str) -> Iterable[tuple[str, str]]:
    for key in _REFERENCE_KEYS:
        if key not in entity:
            continue
        value = entity[key]
        if key.endswith("_ids"):
            for index, reference in enumerate(_array(value, f"{base}.{key}")):
                yield _text(reference, f"{base}.{key}[{index}]"), f"{base}.{key}[{index}]"
        elif value is not None:
            yield _text(value, f"{base}.{key}"), f"{base}.{key}"


def validate_v2(document: dict[str, Any]) -> dict[str, Any]:
    """Validate a native v2 document without mutating it; return the same object."""
    root = _mapping(document, "$")
    if root.get("version") != VERSION:
        _fail("version", f"must equal {VERSION!r}")
    _mapping(root.get("metadata", {}), "metadata")
    floors = _array(root.get("floors"), "floors")
    if not floors:
        _fail("floors", "must contain at least one floor")

    floor_ids: set[str] = set()
    floor_names: set[str] = set()
    elevations: set[float] = set()
    entity_owner: dict[str, str] = {}
    entities: list[tuple[dict[str, Any], str, str]] = []
    ground_count = 0
    for floor_index, raw_floor in enumerate(floors):
        base = f"floors[{floor_index}]"
        floor = _mapping(raw_floor, base)
        floor_id = _text(floor.get("id"), f"{base}.id")
        if floor_id in floor_ids:
            _fail(f"{base}.id", "must be unique")
        floor_ids.add(floor_id)
        name = _text(floor.get("name"), f"{base}.name", trimmed=True)
        if name.casefold() in floor_names:
            _fail(f"{base}.name", "must be unique")
        floor_names.add(name.casefold())
        elevation = _number(floor.get("elevation_cm"), f"{base}.elevation_cm")
        if elevation < 0:
            _fail(f"{base}.elevation_cm", "must be zero or positive")
        if elevation in elevations:
            _fail(f"{base}.elevation_cm", "must be unique")
        elevations.add(elevation)
        ground_count += elevation == 0
        geometry = _mapping(floor.get("geometry"), f"{base}.geometry")
        if "canvas" in geometry:
            _mapping(geometry["canvas"], f"{base}.geometry.canvas")
        for collection in GEOMETRY_COLLECTIONS:
            if collection in geometry:
                _array(geometry[collection], f"{base}.geometry.{collection}")
        for collection, values in geometry.items():
            if not isinstance(values, list):
                continue  # compass and future scalar geometry metadata round-trip untouched
            for entity_index, raw_entity in enumerate(values):
                entity_path = f"{base}.geometry.{collection}[{entity_index}]"
                entity = _mapping(raw_entity, entity_path)
                entity_id = _text(entity.get("id"), f"{entity_path}.id")
                if entity_id in floor_ids or entity_id in entity_owner:
                    _fail(f"{entity_path}.id", "must be globally unique")
                entity_owner[entity_id] = floor_id
                entities.append((entity, entity_path, floor_id))
                if collection == "vertices":
                    _point(entity.get("position", {"x": entity.get("x"), "y": entity.get("y")}), f"{entity_path}.position")
                elif collection == "walls":
                    _number(entity.get("thickness_cm"), f"{entity_path}.thickness_cm", positive=True)
                    _number(entity.get("height_cm"), f"{entity_path}.height_cm", positive=True)
                    _text(entity.get("material_id"), f"{entity_path}.material_id")
                    _array(entity.get("opening_ids"), f"{entity_path}.opening_ids")
                elif collection == "rooms":
                    boundary = _array(entity.get("boundary_vertex_ids"), f"{entity_path}.boundary_vertex_ids")
                    if len(boundary) < 3:
                        _fail(f"{entity_path}.boundary_vertex_ids", "must contain at least three vertices")
        _validate_structures(geometry, f"{base}.geometry")
    if ground_count != 1:
        _fail("floors", "must contain exactly one floor at elevation 0")
    active_floor_id = _text(root.get("active_floor_id"), "active_floor_id")
    if active_floor_id not in floor_ids:
        _fail("active_floor_id", "must reference an existing floor")

    for entity, path, owner in entities:
        for reference, reference_path in _iter_references(entity, path):
            if reference not in entity_owner:
                _fail(reference_path, "must reference an existing entity")
            if entity_owner[reference] != owner:
                _fail(reference_path, "cannot reference an entity on another floor")

    sun = _mapping(root.get("sun_settings"), "sun_settings")
    time_hours = _number(sun.get("time_hours"), "sun_settings.time_hours")
    if not 0 <= time_hours <= 24:
        _fail("sun_settings.time_hours", "must be in [0, 24]")
    azimuth = _number(sun.get("azimuth_deg"), "sun_settings.azimuth_deg")
    if not 0 <= azimuth < 360:
        _fail("sun_settings.azimuth_deg", "must be in [0, 360)")
    if type(sun.get("direction_override")) is not bool:
        _fail("sun_settings.direction_override", "must be a boolean")

    cross_refs = _array(root.get("cross_floor_references"), "cross_floor_references")
    reference_ids: set[str] = set(floor_ids) | set(entity_owner)
    for index, raw_reference in enumerate(cross_refs):
        base = f"cross_floor_references[{index}]"
        reference = _mapping(raw_reference, base)
        reference_id = _text(reference.get("id"), f"{base}.id")
        _text(reference.get("type"), f"{base}.type")
        if reference_id in reference_ids:
            _fail(f"{base}.id", "must be globally unique")
        reference_ids.add(reference_id)
        source_floor = _text(reference.get("source_floor_id"), f"{base}.source_floor_id")
        target_floor = _text(reference.get("target_floor_id"), f"{base}.target_floor_id")
        if source_floor not in floor_ids:
            _fail(f"{base}.source_floor_id", "must reference an existing floor")
        if target_floor not in floor_ids:
            _fail(f"{base}.target_floor_id", "must reference an existing floor")
        if source_floor == target_floor:
            _fail(f"{base}.target_floor_id", "must reference a different floor")
        source_entity = _text(reference.get("source_entity_id"), f"{base}.source_entity_id")
        target_entity = _text(reference.get("target_entity_id"), f"{base}.target_entity_id")
        if entity_owner.get(source_entity) != source_floor:
            _fail(f"{base}.source_entity_id", "must resolve on source_floor_id")
        if entity_owner.get(target_entity) != target_floor:
            _fail(f"{base}.target_entity_id", "must resolve on target_floor_id")
    return document


def validate_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return an independent validated v2 document, migrating supported v1 input."""
    source = _mapping(document, "$")
    version = source.get("version", "1.0")
    if version == VERSION:
        candidate = deepcopy(source)
        validate_v2(candidate)
        return candidate
    if isinstance(version, str) and version.split(".", 1)[0] == "1":
        return migrate_v1_to_v2(source)
    _fail("version", "unsupported native layout version")


migrate_document = validate_document
