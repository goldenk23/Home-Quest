"""Pure, transactional project and floor lifecycle state."""
from __future__ import annotations

from copy import deepcopy
import uuid
from typing import Any, Callable

from layout_schema import empty_geometry, new_project, validate_document, validate_v2

_EXCLUDED_DUPLICATE_COLLECTIONS = frozenset({"roads", "stairs", "annotations", "text"})
_ENTITY_REFERENCE_KEYS = frozenset({
    "start_vertex_id", "end_vertex_id", "boundary_vertex_ids", "opening_ids",
    "wall_id", "wall_ids", "room_id", "host_id", "deck_slab_id", "post_ids",
    "beam_ids",
})


class ProjectState:
    """Owns a validated v2 snapshot; callers only receive defensive copies."""

    def __init__(self, document: dict[str, Any] | None = None):
        self._document = validate_document(document if document is not None else new_project())
        self.floor_manager = FloorManager(self)

    @property
    def document(self) -> dict[str, Any]:
        return deepcopy(self._document)

    @property
    def floors(self) -> list[dict[str, Any]]:
        return deepcopy(self._document["floors"])

    @property
    def active_floor_id(self) -> str:
        return self._document["active_floor_id"]

    @property
    def active_floor(self) -> dict[str, Any]:
        floor = next(f for f in self._document["floors"] if f["id"] == self.active_floor_id)
        return deepcopy(floor)

    @property
    def sun_settings(self) -> dict[str, Any]:
        return deepcopy(self._document["sun_settings"])

    @property
    def cross_floor_references(self) -> list[dict[str, Any]]:
        return deepcopy(self._document["cross_floor_references"])

    def snapshot(self) -> dict[str, Any]:
        return self.document

    def replace(self, document: dict[str, Any]) -> None:
        candidate = validate_document(document)
        self._document = candidate

    def replace_active_geometry(self, geometry: dict[str, Any]) -> dict[str, Any]:
        """Atomically replace only the active floor geometry."""
        if not isinstance(geometry, dict):
            raise TypeError("geometry must be an object")

        def mutation(document: dict[str, Any]) -> dict[str, Any]:
            floor = next(f for f in document["floors"] if f["id"] == document["active_floor_id"])
            floor["geometry"] = deepcopy(geometry)
            return floor["geometry"]

        return self._transact(mutation)

    def replace_sun_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Atomically replace project-level sun settings."""
        if not isinstance(settings, dict):
            raise TypeError("sun settings must be an object")

        def mutation(document: dict[str, Any]) -> dict[str, Any]:
            document["sun_settings"] = deepcopy(settings)
            return document["sun_settings"]

        return self._transact(mutation)

    def _transact(self, mutation: Callable[[dict[str, Any]], Any]) -> Any:
        candidate = deepcopy(self._document)
        result = mutation(candidate)
        validate_v2(candidate)
        self._document = candidate
        return deepcopy(result)


class FloorManager:
    """Applies floor operations to a ProjectState using validate-before-commit copies."""

    def __init__(self, state: ProjectState):
        if not isinstance(state, ProjectState):
            raise TypeError("state must be a ProjectState")
        self._state = state

    @staticmethod
    def _find(document: dict[str, Any], floor_id: str) -> tuple[int, dict[str, Any]]:
        for index, floor in enumerate(document["floors"]):
            if floor["id"] == floor_id:
                return index, floor
        raise ValueError(f"floor_id: unknown floor {floor_id!r}")

    @staticmethod
    def _name(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("name: must be a non-empty string")
        return value.strip()

    @staticmethod
    def _next_elevation(document: dict[str, Any]) -> float:
        return max(float(floor["elevation_cm"]) for floor in document["floors"]) + 300.0

    @staticmethod
    def _fresh(prefix: str, used: set[str]) -> str:
        while True:
            value = f"{prefix}-{uuid.uuid4()}"
            if value not in used:
                used.add(value)
                return value

    @staticmethod
    def _all_ids(document: dict[str, Any]) -> set[str]:
        ids = {floor["id"] for floor in document["floors"]}
        ids.update(ref["id"] for ref in document["cross_floor_references"])
        for floor in document["floors"]:
            for values in floor["geometry"].values():
                if isinstance(values, list):
                    ids.update(entity["id"] for entity in values if isinstance(entity, dict) and "id" in entity)
        return ids

    def add(self, name: str = "New Floor", elevation_cm: float | None = None,
            geometry: dict[str, Any] | None = None, floor_id: str | None = None) -> dict[str, Any]:
        clean_name = self._name(name)

        def mutation(document: dict[str, Any]) -> dict[str, Any]:
            used = self._all_ids(document)
            if floor_id is None:
                new_id = self._fresh("floor", used)
            else:
                new_id = floor_id
                if not isinstance(new_id, str) or not new_id.strip() or new_id in used:
                    raise ValueError("floor_id: must be a non-empty unique string")
            floor = {
                "id": new_id,
                "name": clean_name,
                "elevation_cm": self._next_elevation(document) if elevation_cm is None else elevation_cm,
                "geometry": deepcopy(geometry) if geometry is not None else empty_geometry(),
            }
            document["floors"].append(floor)
            document["active_floor_id"] = new_id
            return floor

        return self._state._transact(mutation)

    def activate(self, floor_id: str) -> dict[str, Any]:
        def mutation(document: dict[str, Any]) -> dict[str, Any]:
            _, floor = self._find(document, floor_id)
            document["active_floor_id"] = floor_id
            return floor

        return self._state._transact(mutation)

    def rename(self, floor_id: str, name: str) -> dict[str, Any]:
        clean_name = self._name(name)

        def mutation(document: dict[str, Any]) -> dict[str, Any]:
            _, floor = self._find(document, floor_id)
            floor["name"] = clean_name
            return floor

        return self._state._transact(mutation)

    def set_elevation(self, floor_id: str, elevation_cm: float) -> dict[str, Any]:
        def mutation(document: dict[str, Any]) -> dict[str, Any]:
            _, floor = self._find(document, floor_id)
            if float(floor["elevation_cm"]) == 0 and elevation_cm != 0:
                raise ValueError("elevation_cm: ground floor elevation is read-only")
            floor["elevation_cm"] = elevation_cm
            return floor

        return self._state._transact(mutation)

    @staticmethod
    def _unique_copy_name(document: dict[str, Any], source_name: str) -> str:
        names = {floor["name"].casefold() for floor in document["floors"]}
        base = f"{source_name} Copy"
        if base.casefold() not in names:
            return base
        suffix = 2
        while f"{base} {suffix}".casefold() in names:
            suffix += 1
        return f"{base} {suffix}"

    @classmethod
    def _remap_values(cls, value: Any, id_map: dict[str, str], key: str | None = None) -> Any:
        if isinstance(value, dict):
            return {child_key: cls._remap_values(child, id_map, child_key) for child_key, child in value.items()}
        if isinstance(value, list):
            return [cls._remap_values(child, id_map, key) for child in value]
        if isinstance(value, tuple):
            return tuple(cls._remap_values(child, id_map, key) for child in value)
        if isinstance(value, str) and (key == "id" or key in _ENTITY_REFERENCE_KEYS):
            return id_map.get(value, value)
        return value

    def duplicate(self, floor_id: str | None = None, name: str | None = None,
                  elevation_cm: float | None = None) -> dict[str, Any]:
        source_id = floor_id or self._state.active_floor_id

        def mutation(document: dict[str, Any]) -> dict[str, Any]:
            _, source = self._find(document, source_id)
            used = self._all_ids(document)
            new_floor_id = self._fresh("floor", used)
            copied_geometry = {
                key: deepcopy(value) for key, value in source["geometry"].items()
                if key not in _EXCLUDED_DUPLICATE_COLLECTIONS
            }
            # The parked v1 canvas mirrors annotations separately from canonical geometry.
            canvas = copied_geometry.get("canvas")
            if isinstance(canvas, dict):
                canvas["text"] = []
            id_map: dict[str, str] = {}
            for collection, values in copied_geometry.items():
                if not isinstance(values, list):
                    continue
                for entity in values:
                    if isinstance(entity, dict) and isinstance(entity.get("id"), str):
                        prefix = f"{new_floor_id}:{collection.rstrip('s') or 'entity'}"
                        id_map[entity["id"]] = self._fresh(prefix, used)
            copied_geometry = self._remap_values(copied_geometry, id_map)
            floor = {
                "id": new_floor_id,
                "name": self._name(name) if name is not None else self._unique_copy_name(document, source["name"]),
                "elevation_cm": self._next_elevation(document) if elevation_cm is None else elevation_cm,
                "geometry": copied_geometry,
            }
            document["floors"].append(floor)
            document["active_floor_id"] = new_floor_id
            return floor

        return self._state._transact(mutation)

    def delete(self, floor_id: str) -> dict[str, Any]:
        def mutation(document: dict[str, Any]) -> dict[str, Any]:
            if len(document["floors"]) == 1:
                raise ValueError("floors: cannot delete the final floor")
            _, floor = self._find(document, floor_id)
            blocking = [
                (index, reference)
                for index, reference in enumerate(document["cross_floor_references"])
                if reference["target_floor_id"] == floor_id
            ]
            if blocking:
                details = ", ".join(
                    f"{reference['id']} (cross_floor_references[{index}])"
                    for index, reference in blocking
                )
                raise ValueError(
                    f"inbound references block deletion of {floor_id!r}: {details}"
                )
            document["cross_floor_references"] = [
                reference for reference in document["cross_floor_references"]
                if reference["source_floor_id"] != floor_id
            ]
            document["floors"] = [item for item in document["floors"] if item["id"] != floor_id]
            if document["active_floor_id"] == floor_id:
                deleted_elevation = float(floor["elevation_cm"])
                document["active_floor_id"] = min(
                    document["floors"],
                    key=lambda item: (abs(float(item["elevation_cm"]) - deleted_elevation),
                                      float(item["elevation_cm"])),
                )["id"]
            return floor

        return self._state._transact(mutation)
