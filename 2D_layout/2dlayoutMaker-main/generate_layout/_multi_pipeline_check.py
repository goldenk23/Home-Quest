"""Offline integration check for the Phase 2-6 multi-strategy pipeline (no Vertex call).

Checks the legacy comb rollback, flexible candidate validation/ranking/determinism, and the
exact default-prompt regression where an over-expanded model spec must be aligned before
planning. Run: python -m generate_layout._multi_pipeline_check
"""
from __future__ import annotations

from .ai_client import _run_multi_planner
from .ai_validator import validate_layout
from .design_spec import align_with_brief, from_dict
from .layout_engine import build_layout

_PROGRAM = {
    "project_name": "Multi Pipeline Check",
    "plot": {"width_ft": 60, "height_ft": 80},
    "rows": {
        "top": [
            {"name": "Guest Bedroom", "zone": "NW", "window": True, "min_ft": 12},
            {"name": "Foyer", "public": True, "entrance": True, "min_ft": 8},
            {"name": "Living Room", "window": True, "min_ft": 14},
            {"name": "Home Office", "window": True, "min_ft": 10},
        ],
        "bottom": [
            {"name": "Master Bedroom", "zone": "SW", "window": True, "min_ft": 12},
            {"name": "Second Bedroom", "window": True, "min_ft": 11},
            {"name": "Dining Room", "window": True, "min_ft": 10},
            {"name": "Kitchen", "window": True, "min_ft": 10},
        ],
    },
    "doors": [["Dining Room", "Kitchen"], ["Living Room", "Dining Room"]],
}

BRIEF = "north-facing 60 ft x 80 ft family home with bedrooms, living, dining, kitchen, office"
_EXACT_PROMPT = (
    "Design a north-facing 40x60 ft 3-bedroom Vastu home with a puja room, "
    "open kitchen in the southeast, and good ventilation."
)
# Deliberately reproduces the bad model behavior reported from the UI: ten spaces,
# invented setbacks/floors, optional rooms, and the entrance assigned to a disposable foyer.
_OVER_EXPANDED_SPEC = {
    "version": "1.0",
    "project_name": "Over-expanded exact prompt",
    "plot": {
        "width_ft": 40,
        "depth_ft": 60,
        "facing": "N",
        "setbacks_ft": {"front": 15, "rear": 15, "left": 5, "right": 5},
    },
    "building": {"floors": 2, "footprint": "rectangular"},
    "rooms": [
        {"id": "master", "name": "Master Bedroom", "type": "bedroom", "exterior_window": True},
        {"id": "bedroom_2", "name": "Bedroom 2", "type": "bedroom", "exterior_window": True},
        {"id": "bedroom_3", "name": "Bedroom 3", "type": "bedroom", "exterior_window": True},
        {"id": "bathroom_1", "name": "Bathroom 1", "type": "bathroom", "exterior_window": True},
        {"id": "living", "name": "Living Room", "type": "living", "public": True,
         "exterior_window": True},
        {"id": "kitchen", "name": "Kitchen", "type": "kitchen", "zone": "NW",
         "exterior_window": True},
        {"id": "puja", "name": "Puja Room", "type": "puja", "zone": "SW"},
        {"id": "dining", "name": "Dining Room", "type": "dining"},
        {"id": "foyer", "name": "Foyer", "type": "foyer", "public": True, "entrance": True},
        {"id": "bathroom_2", "name": "Bathroom 2", "type": "bathroom"},
    ],
    "relationships": [
        {"a": "foyer", "b": "living", "kind": "direct_door", "priority": "hard"},
        {"a": "living", "b": "dining", "kind": "open_plan", "priority": "preferred"},
        {"a": "dining", "b": "kitchen", "kind": "adjacent", "priority": "preferred"},
        {"a": "master", "b": "bathroom_2", "kind": "attached_to", "priority": "preferred"},
    ],
}


def main() -> None:
    comb_shell = build_layout(_PROGRAM)
    assert validate_layout(comb_shell) == [], "legacy comb rollback must remain valid"

    report, candidates, ranked = _run_multi_planner(_PROGRAM, BRIEF, seed=7)
    assert report.feasible, report.hard_failures

    valid = [c for c in candidates if c.valid]
    assert len(valid) >= 2, f"expected multiple valid candidates, got {[c.strategy_id for c in candidates]}"
    for c in valid:
        assert validate_layout(c.layout) == [], (c.strategy_id, "invalid geometry slipped through")
    assert len(ranked) >= 2, "multi mode must return at least two diverse candidates"
    assert len({candidate.fingerprint for candidate in ranked}) == len(ranked)
    assert ranked[0].score == max(c.score for c in valid), "ranking must pick the top score"

    # Determinism: same inputs -> same selected strategy, seed, score, and geometry.
    _, _, ranked2 = _run_multi_planner(_PROGRAM, BRIEF, seed=7)
    assert (ranked2[0].strategy_id, ranked2[0].seed, ranked2[0].fingerprint) == (
        ranked[0].strategy_id, ranked[0].seed, ranked[0].fingerprint)
    assert abs(ranked2[0].score - ranked[0].score) < 1e-9

    # Exact UI prompt: prompt truth must correct model overreach before geometry generation.
    exact_spec = from_dict(_OVER_EXPANDED_SPEC)
    notes, errors = align_with_brief(exact_spec, _EXACT_PROMPT, initial=True)
    assert errors == [], errors
    assert (exact_spec.plot["width_ft"], exact_spec.plot["depth_ft"]) == (40, 60)
    assert set(exact_spec.plot["setbacks_ft"].values()) == {0.0}
    assert exact_spec.building["floors"] == 1
    assert [room.name for room in exact_spec.rooms] == [
        "Master Bedroom", "Bedroom 2", "Bedroom 3", "Bathroom 1",
        "Living Room", "Kitchen", "Puja Room",
    ]
    assert len(exact_spec.rooms_of_type("bedroom")) == 3
    kitchen, puja = exact_spec.rooms_of_type("kitchen")[0], exact_spec.rooms_of_type("puja")[0]
    living = exact_spec.rooms_of_type("living")[0]
    assert (kitchen.zone, kitchen.priority) == ("SE", "hard")
    assert (puja.zone, puja.priority) == ("NE", "hard")
    assert [room.id for room in exact_spec.rooms if room.entrance] == [living.id]
    assert any(
        rel.kind == "open_plan" and rel.priority == "hard"
        and {rel.a, rel.b} == {living.id, kitchen.id}
        for rel in exact_spec.relationships
    )
    assert any("ignored AI-invented setbacks" in note for note in notes)
    assert any("Dining Room" in note and "Foyer" in note and "Bathroom 2" in note for note in notes)

    exact_report, exact_candidates, exact_ranked = _run_multi_planner(exact_spec, _EXACT_PROMPT, seed=7)
    assert exact_report.feasible, exact_report.hard_failures
    open_core = next(
        candidate for candidate in exact_candidates
        if candidate.strategy_id == "open_living_core" and candidate.valid
    )
    # The winner must be a valid, clean strategy; the CP-SAT solver may legitimately
    # outrank the open-core template, so accept either while still proving the open-core
    # candidate itself remains valid and corridor-free below.
    assert exact_ranked[0].strategy_id in {"open_living_core", "constraint_solver"}, [
        (candidate.strategy_id, candidate.score) for candidate in exact_ranked
    ]
    assert validate_layout(open_core.layout) == []
    assert not any(
        token in room["name"].lower()
        for room in open_core.layout["rooms"] for token in ("corridor", "hallway")
    )

    # The north entrance and living-room ventilation window must remain separate gaps.
    native_living = next(room for room in open_core.layout["rooms"] if room["name"] == "Living Room")
    top_gaps = native_living.get("wall_erased_regions", {}).get("top", [])
    entrance_doors = [
        item for item in open_core.layout["furniture"]
        if item.get("image_name") == "singlehand_door"
        and abs(float(item["y"]) - float(native_living["y0"])) < 1e-6
        and native_living["x0"] <= float(item["x"]) <= native_living["x1"]
    ]
    assert len(top_gaps) >= 2 and entrance_doors, (top_gaps, entrance_doors)
    assert any(lo <= entrance_doors[0]["x"] <= hi for lo, hi in top_gaps)

    _, _, exact_ranked2 = _run_multi_planner(exact_spec, _EXACT_PROMPT, seed=7)
    assert exact_ranked2[0].fingerprint == exact_ranked[0].fingerprint

    # Regression: a multi-line "do not add" exclusion list must never be misread as a room
    # requirement. This previously failed at the validate_design gate with "design brief
    # requires a foyer/dining/utility". Multi mode validates against the structured spec, not
    # the raw brief, so an exclusion-heavy brief still yields a valid, selected layout.
    exclusion_brief = _EXACT_PROMPT + (
        "\nDo not add\nDining room\nFoyer\nUtility room\nStorage room\nOffice\nBalcony\nGarage"
    )
    excl_report, excl_candidates, excl_ranked = _run_multi_planner(exact_spec, exclusion_brief, seed=7)
    assert excl_report.feasible and excl_ranked, excl_report.hard_failures
    assert excl_ranked[0].valid, [(c.strategy_id, c.hard_errors[:2]) for c in excl_candidates]

    print("multi pipeline check passed:")
    print("  feasible:", report.feasible, "buildable", report.buildable_ft)
    for c in sorted(candidates, key=lambda c: c.score, reverse=True):
        flag = "OK " if c.valid else "XX "
        print(f"  {flag}{c.strategy_id:18s} score={c.score:.3f} {c.breakdown}")
    print("  selected:", ranked[0].strategy_id)
    print("  exact prompt:", exact_ranked[0].strategy_id, "score", exact_ranked[0].score)


if __name__ == "__main__":
    main()
