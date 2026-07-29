import copy
import json
import os
import tempfile
import unittest

from action import ActionManager
from layout_schema import empty_geometry, migrate_v1_to_v2, new_project, validate_document, validate_v2
from layout_serializer import LayoutSerializer, atomic_write_document
from local_autosave import LocalAutosave
from project_state import FloorManager, ProjectState


def entity(entity_id, **values):
    return {"id": entity_id, "position": [0, 0], **values}


def project_with_geometry(**collections):
    document = new_project()
    document["floors"][0]["geometry"].update(collections)
    return document


class SchemaTests(unittest.TestCase):
    def test_v1_migration_preserves_collections_on_one_floor(self):
        v1 = {
            "version": "1.0",
            "metadata": {"unit": "feet", "zoom_level": 2},
            "rooms": [{"name": "Kitchen", "x0": 0, "y0": 0, "x1": 100, "y1": 80}],
            "windows": [{"x": 2, "y": 3}],
            "text": [{"content": "North"}],
            "compass": {"north_deg_clockwise": 45},
        }
        migrated = migrate_v1_to_v2(v1)
        self.assertEqual("2.0", migrated["version"])
        self.assertEqual(1, len(migrated["floors"]))
        geometry = migrated["floors"][0]["geometry"]
        self.assertEqual(v1, geometry["canvas"])
        for collection in ("rooms", "windows", "text"):
            self.assertEqual([], geometry.get(collection, []))
        self.assertEqual(v1["compass"], geometry["compass"])
        self.assertEqual(v1["metadata"], migrated["metadata"])
        v1["rooms"][0]["name"] = "Changed"
        self.assertEqual("Kitchen", geometry["canvas"]["rooms"][0]["name"])

    def test_validate_document_returns_independent_copy(self):
        original = new_project()
        validated = validate_document(original)
        validated["metadata"]["changed"] = True
        self.assertNotIn("changed", original["metadata"])

    def test_path_errors_for_ids_sun_and_dimensions(self):
        cases = []
        duplicate = project_with_geometry(vertices=[entity("same"), entity("same")])
        cases.append((duplicate, "floors[0].geometry.vertices[1].id"))
        sun = new_project()
        sun["sun_settings"]["time_hours"] = 25
        cases.append((sun, "sun_settings.time_hours"))
        pillar = project_with_geometry(pillars=[entity("p", width_cm=0, depth_cm=10, height_cm=20)])
        cases.append((pillar, "floors[0].geometry.pillars[0].width_cm"))
        for document, expected_path in cases:
            with self.subTest(expected_path=expected_path), self.assertRaisesRegex(ValueError, expected_path.replace("[", r"\[").replace("]", r"\]")):
                validate_v2(document)

    def test_beam_and_deck_geometry(self):
        beam = project_with_geometry(beams=[entity(
            "beam", start=[0, 0], end=[0, 0], width_cm=10, depth_cm=20
        )])
        with self.assertRaisesRegex(ValueError, r"beams\[0\]\.end"):
            validate_v2(beam)
        deck = project_with_geometry(deck_slabs=[entity(
            "deck", thickness_cm=15, polygon=[[0, 0], [2, 2], [0, 2], [2, 0]]
        )])
        with self.assertRaisesRegex(ValueError, r"deck_slabs\[0\]\.polygon"):
            validate_v2(deck)

    def test_intra_and_cross_floor_references_resolve(self):
        document = project_with_geometry(
            vertices=[entity("v1"), entity("v2")],
            walls=[entity(
                "wall", start_vertex_id="v1", end_vertex_id="missing",
                thickness_cm=15, height_cm=280, material_id="default-wall", opening_ids=[],
            )],
        )
        with self.assertRaisesRegex(ValueError, r"walls\[0\]\.end_vertex_id"):
            validate_v2(document)

        state = ProjectState(project_with_geometry(vertices=[entity("ground-entity")]))
        upper = state.floor_manager.add("Upper", 300, {**project_with_geometry()["floors"][0]["geometry"], "vertices": [entity("upper-entity")]})
        candidate = state.document
        candidate["cross_floor_references"] = [{
            "id": "cross-1", "type": "alignment",
            "source_floor_id": candidate["floors"][0]["id"],
            "source_entity_id": "ground-entity",
            "target_floor_id": upper["id"],
            "target_entity_id": "upper-entity",
        }]
        validate_v2(candidate)


class ProjectStateTests(unittest.TestCase):
    def test_add_activate_rename_and_elevation(self):
        state = ProjectState()
        manager = FloorManager(state)
        upper = manager.add(" Upper ", 300)
        self.assertEqual("Upper", upper["name"])
        manager.activate(upper["id"])
        self.assertEqual(upper["id"], state.active_floor_id)
        manager.rename(upper["id"], "First Floor")
        manager.set_elevation(upper["id"], 350)
        self.assertEqual("First Floor", state.active_floor["name"])
        self.assertEqual(350, state.active_floor["elevation_cm"])

    def test_duplicate_remaps_ids_and_excludes_categories(self):
        document = project_with_geometry(
            vertices=[entity("v1", label="v1"), entity("v2")],
            walls=[entity(
                "w1", start_vertex_id="v1", end_vertex_id="v2",
                thickness_cm=15, height_cm=280, material_id="default-wall", opening_ids=[],
            )],
            roads=[entity("road-1")],
            stairs=[entity("stair-1")],
            annotations=[entity("legacy-annotation-1")],
            text=[entity("text-1", content="Do not duplicate")],
            canvas={
                "version": "1.0", "metadata": {}, "rooms": [], "furniture": [],
                "windows": [], "shapes": [],
                "text": [entity("canvas-text-1", content="Do not duplicate")],
            },
        )
        state = ProjectState(document)
        duplicate = state.floor_manager.duplicate(elevation_cm=300)
        self.assertFalse({"roads", "stairs", "annotations", "text"} & duplicate["geometry"].keys())
        self.assertEqual([], duplicate["geometry"]["canvas"]["text"])
        source_ids = {
            "v1", "v2", "w1", "road-1", "stair-1", "legacy-annotation-1",
            "text-1", "canvas-text-1",
        }
        duplicate_ids = {
            item["id"] for values in duplicate["geometry"].values() if isinstance(values, list)
            for item in values
        }
        self.assertTrue(source_ids.isdisjoint(duplicate_ids))
        self.assertTrue(all(item_id.startswith(f"{duplicate['id']}:") for item_id in duplicate_ids))
        wall = duplicate["geometry"]["walls"][0]
        vertex_ids = {item["id"] for item in duplicate["geometry"]["vertices"]}
        self.assertIn(wall["start_vertex_id"], vertex_ids)
        self.assertIn(wall["end_vertex_id"], vertex_ids)
        self.assertEqual("v1", duplicate["geometry"]["vertices"][0]["label"])
        self.assertEqual([], state.cross_floor_references)

    def test_failed_mutations_are_atomic(self):
        state = ProjectState()
        before = state.snapshot()
        with self.assertRaises(ValueError):
            state.floor_manager.add("Ground Again", 0)
        self.assertEqual(before, state.snapshot())
        with self.assertRaises(ValueError):
            state.floor_manager.rename(state.active_floor_id, "  ")
        self.assertEqual(before, state.snapshot())

    def test_delete_is_blocked_by_inbound_reference(self):
        state = ProjectState(project_with_geometry(vertices=[entity("source")]))
        target = state.floor_manager.add(
            "Upper", 300,
            {**project_with_geometry()["floors"][0]["geometry"], "vertices": [entity("target")]},
        )
        document = state.document
        document["cross_floor_references"] = [{
            "id": "xref", "type": "alignment",
            "source_floor_id": document["floors"][0]["id"], "source_entity_id": "source",
            "target_floor_id": target["id"], "target_entity_id": "target",
        }, {
            "id": "xref-2", "type": "alignment",
            "source_floor_id": document["floors"][0]["id"], "source_entity_id": "source",
            "target_floor_id": target["id"], "target_entity_id": "target",
        }]
        state.replace(document)
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "xref.*xref-2"):
            state.floor_manager.delete(target["id"])
        self.assertEqual(before, state.snapshot())

    def test_atomic_active_geometry_and_sun_replacement(self):
        state = ProjectState()
        geometry = empty_geometry()
        geometry["canvas"] = {"version": "1.0", "metadata": {}, "rooms": [], "furniture": [], "shapes": [], "text": []}
        state.replace_active_geometry(geometry)
        self.assertEqual(geometry, state.active_floor["geometry"])
        before = state.snapshot()
        with self.assertRaises(ValueError):
            state.replace_sun_settings({"time_hours": 30, "azimuth_deg": 0, "direction_override": False})
        self.assertEqual(before, state.snapshot())

    def test_add_duplicate_activate_and_delete_by_elevation(self):
        state = ProjectState()
        ground_id = state.active_floor_id
        upper = state.floor_manager.add("Upper", 300)
        self.assertEqual(upper["id"], state.active_floor_id)
        top = state.floor_manager.duplicate(upper["id"], elevation_cm=900)
        self.assertEqual(top["id"], state.active_floor_id)
        middle = state.floor_manager.add("Middle", 600)
        state.floor_manager.activate(middle["id"])
        state.floor_manager.delete(middle["id"])
        self.assertEqual(upper["id"], state.active_floor_id)
        self.assertNotEqual(ground_id, state.active_floor_id)

    def test_delete_final_floor_is_atomic(self):
        state = ProjectState()
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "final floor"):
            state.floor_manager.delete(state.active_floor_id)
        self.assertEqual(before, state.snapshot())

    def test_floor_ids_cannot_collide_with_entity_ids(self):
        document = new_project()
        document["floors"][0]["geometry"]["vertices"] = [
            entity(document["floors"][0]["id"])
        ]
        with self.assertRaisesRegex(ValueError, "globally unique"):
            validate_v2(document)


class SerializerParityTests(unittest.TestCase):
    def test_canvas_derives_stable_ts_canonical_geometry_and_preserves_structures(self):
        serializer = LayoutSerializer.__new__(LayoutSerializer)
        canvas = {
            "version": "1.0",
            "metadata": {"wall_height_cm": 280},
            "rooms": [{
                "id": "kitchen", "name": "Kitchen", "x0": 0, "y0": 0, "x1": 100, "y1": 80,
                "wall_thickness_ft": .5, "flooring": {"flooring_type": "wood"},
            }],
            "furniture": [], "windows": [], "text": [],
            "shapes": [
                {"id": "patio", "type": "polygon", "points": [[120, 0], [180, 0], [150, 50]], "width": 2,
                 "flooring": {"flooring_type": "tile"}},
                {"id": "divider", "type": "line", "points": [[0, 100], [100, 100]], "width": 4},
            ],
        }
        existing = empty_geometry()
        existing["pillars"] = [{
            "id": "pillar-existing", "position": [10, 10], "width_cm": 20,
            "depth_cm": 20, "height_cm": 280, "elevation_cm": 0,
        }]
        first = serializer._derive_canvas_geometry("floor-ground", canvas, existing)
        second = serializer._derive_canvas_geometry("floor-ground", canvas, first)
        self.assertEqual(first, second)
        self.assertEqual(canvas, first["canvas"])
        self.assertEqual(existing["pillars"], first["pillars"])
        self.assertEqual(2, len(first["rooms"]))
        self.assertEqual(8, len(first["walls"]))
        self.assertEqual(9, len(first["vertices"]))
        ids = [item["id"] for key in ("vertices", "walls", "rooms") for item in first[key]]
        self.assertTrue(all(item_id.startswith("floor-ground:canvas:") for item_id in ids))
        self.assertEqual(len(ids), len(set(ids)))
        room = first["rooms"][0]
        self.assertEqual(4, len(room["boundary_vertex_ids"]))
        self.assertEqual("floor-wood", room["floor_material_id"])
        document = new_project()
        document["floors"][0]["id"] = "floor-ground"
        document["active_floor_id"] = "floor-ground"
        document["floors"][0]["geometry"] = first
        validate_v2(document)

    def test_atomic_json_and_yaml_writer(self):
        document = new_project()
        with tempfile.TemporaryDirectory() as directory:
            json_path = os.path.join(directory, "project.json")
            yaml_path = os.path.join(directory, "project.yaml")
            atomic_write_document(document, json_path)
            atomic_write_document(document, yaml_path)
            with open(json_path, encoding="utf-8") as stream:
                self.assertEqual(document, json.load(stream))
            self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(directory)))

    def test_load_failure_restores_project_canvas_and_history(self):
        serializer = LayoutSerializer.__new__(LayoutSerializer)
        serializer.project_state = ProjectState()
        before = serializer.project_state.snapshot()
        old_canvas = {"version": "1.0", "metadata": {}, "rooms": [], "furniture": [], "windows": [], "shapes": [], "text": []}
        serializer._serialize_canvas_v1 = lambda: copy.deepcopy(old_canvas)
        restored = []
        serializer.deserialize_layout = lambda payload: restored.append(copy.deepcopy(payload))
        serializer._materialize_active_floor = lambda: (_ for _ in ()).throw(RuntimeError("canvas failed"))
        serializer.actions = ActionManager()
        serializer.actions.undo_stack.append({"type": "sentinel"})
        candidate = new_project()
        candidate["metadata"]["candidate"] = True
        with self.assertRaisesRegex(RuntimeError, "canvas failed"):
            serializer.load_document(candidate, confirm=False)
        self.assertEqual(before, serializer.project_state.snapshot())
        self.assertEqual([old_canvas], restored)
        self.assertEqual([{"type": "sentinel"}], serializer.actions.undo_stack)

    def test_successful_load_clears_history_after_materialization(self):
        serializer = LayoutSerializer.__new__(LayoutSerializer)
        serializer.project_state = ProjectState()
        serializer._serialize_canvas_v1 = lambda: {
            "version": "1.0", "metadata": {}, "rooms": [], "furniture": [],
            "windows": [], "shapes": [], "text": [],
        }
        materialized = []
        serializer._materialize_active_floor = lambda: materialized.append(True)
        serializer.actions = ActionManager()
        serializer.actions.undo_stack.append({"type": "sentinel"})
        notifications = []
        serializer.actions.post_mutation_callback = lambda: notifications.append(True)
        candidate = new_project()
        self.assertTrue(serializer.load_document(candidate, confirm=False))
        self.assertEqual([True], materialized)
        self.assertEqual([], serializer.actions.undo_stack)
        self.assertEqual([], serializer.actions.redo_stack)
        self.assertEqual([True], notifications)

    def test_local_autosave_uses_native_serializer(self):
        class FakeSerializer:
            def serialize_layout(self):
                return new_project()
            def export_to_dict(self):
                raise AssertionError("legacy export must not be used")
        class FakeRoot:
            pass
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "autosave.json")
            saver = LocalAutosave(FakeRoot(), FakeSerializer(), ActionManager(), path)
            saver.save_now()
            with open(path, encoding="utf-8") as stream:
                self.assertEqual("2.0", json.load(stream)["version"])


class ActionSnapshotTests(unittest.TestCase):
    def test_snapshot_undo_redo_notifies_once_without_recursive_logging(self):
        actions = ActionManager()
        applied = []
        notifications = []

        class FakeSerializer:
            def apply_project_snapshot(self, document):
                applied.append(document["value"])
                actions.log({"type": "recursive"})

        actions.serializer = FakeSerializer()
        actions.post_mutation_callback = lambda: notifications.append("changed")
        actions.log({"type": "project_snapshot", "before": {"value": 1}, "after": {"value": 2}})
        actions.undo(object())
        actions.redo(object())
        self.assertEqual([1, 2], applied)
        self.assertEqual(3, len(notifications))
        self.assertEqual(1, len(actions.undo_stack))
        self.assertEqual([], actions.redo_stack)


if __name__ == "__main__":
    unittest.main()
