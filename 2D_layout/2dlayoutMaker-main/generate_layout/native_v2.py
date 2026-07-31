"""Assemble a v2.0 multi-floor VastuCraft document from per-floor native v1 layouts.

Scope A (independent stacked floors): each floor embeds its own validated native v1 layout
as ``geometry.canvas``. The output is a native v2 document accepted by
``layout_schema.validate_v2`` and loaded directly through
``LayoutSerializer.load_document`` — every floor lands in ``project_state`` and the ground
floor is drawn; ``serializer.activate_floor(floor_id)`` switches which floor is on the
canvas. ``_canvas_from_geometry`` returns each floor's embedded ``canvas`` verbatim, so no
canonical geometry or cross-floor id namespacing is needed here. (The same document also
satisfies the web ``importVastu`` v2 importer, which regenerates ids on import.)

ponytail: vertical circulation is intentionally NOT modeled here — staircases are not aligned
across floors and no ``cross_floor_references`` are emitted (that is Scope B). Upgrade path:
have the planner reserve a shared stair cell and emit stair cross-floor references.
"""
from __future__ import annotations

from typing import Any

_DEFAULT_WALL_HEIGHT_CM = 280.0
_DEFAULT_FLOOR_NAMES = ("Ground Floor", "First Floor", "Second Floor", "Third Floor", "Fourth Floor")
# Mirrors layout_schema.GEOMETRY_COLLECTIONS so a stacked floor matches a natively-migrated one.
_GEOMETRY_COLLECTIONS = (
    "vertices", "walls", "rooms", "openings", "furniture", "shapes", "text",
    "pillars", "beams", "deck_slabs", "railings",
)


def default_floor_name(index: int) -> str:
    return _DEFAULT_FLOOR_NAMES[index] if index < len(_DEFAULT_FLOOR_NAMES) else f"Floor {index}"


def build_multi_floor_document(floors: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap ground-first per-floor native v1 layouts into a v2.0 document.

    ``floors`` is an ordered list of ``{"name": str, "layout": <native v1 dict>}`` with the
    ground floor first. Returns a document accepted by ``importVastu.assertV2Layout``:
    exactly one floor at elevation 0, unique floor ids/names/elevations, valid metadata,
    valid sun settings, and an empty cross-floor reference list.
    """
    if not floors:
        raise ValueError("at least one floor is required")

    ground_layout = floors[0].get("layout") or {}
    base_meta = dict(ground_layout.get("metadata") or {})
    if not base_meta:
        base_meta = {"unit": "ft", "unit_scale": 1, "grid_spacing": 20, "zoom_level": 1,
                     "wall_height_cm": _DEFAULT_WALL_HEIGHT_CM}
    wall_height = float(base_meta.get("wall_height_cm") or _DEFAULT_WALL_HEIGHT_CM) or _DEFAULT_WALL_HEIGHT_CM

    floor_entries: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for index, floor in enumerate(floors):
        layout = floor.get("layout")
        if not isinstance(layout, dict) or layout.get("version") != "1.0":
            raise ValueError(f"floor {index} must carry a native v1.0 layout as its canvas")
        # Names must be unique (case-insensitive) and trimmed; de-duplicate defensively.
        name = str(floor.get("name") or default_floor_name(index)).strip() or default_floor_name(index)
        base_name, suffix = name, 2
        while name.lower() in used_names:
            name = f"{base_name} ({suffix})"
            suffix += 1
        used_names.add(name.lower())
        # Match migrate_v1_to_v2 exactly: full empty canonical collections + the opaque v1
        # canvas (+ compass when present), so a stacked floor is byte-shape-identical to a
        # natively-migrated one and can't trip any code that assumes collection keys exist.
        geometry: dict[str, Any] = {name_: [] for name_ in _GEOMETRY_COLLECTIONS}
        geometry["canvas"] = layout
        if isinstance(layout.get("compass"), dict):
            geometry["compass"] = layout["compass"]
        floor_entries.append({
            "id": f"floor_{index}",
            "name": name,
            "elevation_cm": round(index * wall_height, 3),  # ground=0, strictly increasing, unique
            "geometry": geometry,
        })

    return {
        "version": "2.0",
        "metadata": base_meta,
        "active_floor_id": "floor_0",
        "floors": floor_entries,
        "sun_settings": {"time_hours": 12.0, "azimuth_deg": 180.0, "direction_override": False},
        "cross_floor_references": [],
    }


if __name__ == "__main__":
    # ponytail: offline structural self-check (no web validator available in Python). Locks the
    # v2.0 invariants importVastu.assertV2Layout enforces: one ground floor, unique ids/names/
    # elevations, an embedded v1.0 canvas per floor, active floor present.
    def _fake_v1(name: str) -> dict[str, Any]:
        return {"version": "1.0",
                "metadata": {"unit": "ft", "unit_scale": 1, "grid_spacing": 20, "zoom_level": 1,
                             "canvas_width": 800, "canvas_height": 1200, "wall_height_cm": 280},
                "rooms": [{"id": f"{name}_r0", "name": name}], "furniture": [], "shapes": [], "text": []}

    doc = build_multi_floor_document([
        {"name": "Ground Floor", "layout": _fake_v1("g")},
        {"name": "First Floor", "layout": _fake_v1("f1")},
        {"name": "First Floor", "layout": _fake_v1("f2")},  # duplicate name -> must be de-duped
    ])
    assert doc["version"] == "2.0"
    assert doc["active_floor_id"] == "floor_0"
    floors = doc["floors"]
    assert len(floors) == 3
    assert [f["id"] for f in floors] == ["floor_0", "floor_1", "floor_2"], "floor ids must be unique/ordered"
    elevations = [f["elevation_cm"] for f in floors]
    assert elevations[0] == 0 and len(set(elevations)) == 3, "one ground floor, unique elevations"
    assert sum(1 for e in elevations if e == 0) == 1, "exactly one floor at elevation 0"
    names = [f["name"].lower() for f in floors]
    assert len(set(names)) == 3, "floor names must be unique"
    assert all(f["geometry"]["canvas"]["version"] == "1.0" for f in floors), "each floor embeds a v1 canvas"
    assert doc["cross_floor_references"] == []

    try:
        build_multi_floor_document([{"name": "Bad", "layout": {"version": "2.0"}}])
    except ValueError:
        pass
    else:
        raise AssertionError("a non-v1 canvas must be rejected")

    # The document must satisfy the native schema that LayoutSerializer.load_document runs.
    # Best-effort: skip only if layout_schema is not importable in this run context.
    try:
        import layout_schema
    except ImportError:
        print("native_v2 multi-floor document self-check: OK (layout_schema not on path; skipped native validate)")
    else:
        layout_schema.validate_v2(doc)
        print("native_v2 multi-floor document self-check: OK (native validate_v2 passed)")
