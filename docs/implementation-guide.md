# Production-Grade AI Floor-Plan Implementation Guide

**Workspace:** `c:\Users\golde\Desktop\Projects\Home Quest`  
**Primary scope:** `2D_layout/2dlayoutMaker-main/generate_layout/`  
**Status:** Implementation specification; no production changes are implied by this document  
**Audience:** Any AI agent or developer continuing the Tkinter AI layout feature

## 1. Mission

Upgrade the conversational floor-plan generator so different prompts produce meaningfully different, usable plans that satisfy explicit user intent, while preserving the working native serializer, validation, rollback, Tk canvas, autosave, and existing Home Quest 2D/3D rendering pipeline.

The current generator is strong at producing valid geometry but weak at producing design variety. The fix is not to let Gemini emit unrestricted coordinates again. Keep deterministic geometry, but replace the single fixed topology with a canonical design specification, feasibility checks, multiple deterministic planning strategies, candidate scoring, and specification-based refinement.

## 2. Non-negotiable compatibility rules

1. Keep Python native VastuCraft JSON as the Tk generator's output contract.
2. Keep `LayoutSerializer.load_document(layout, confirm=True)` as the only AI apply path.
3. Keep validation before state replacement and serializer rollback on materialization failure.
4. Do not create another serializer, renderer, or intermediate `.hq.json` conversion.
5. Continue using the existing Zustand/entity/`SceneContent`/`FloorScene` pipeline for web 3D.
6. Preserve cancellation semantics: cancelled, timed-out, invalid, or declined results never change the canvas.
7. Preserve existing manual rectangle/compass generation in `generate_layout/service.py`.
8. Preserve native v1 coordinate rules: feet, 20 px/ft, top-left origin, and Y increasing downward.
9. Unknown furniture must be rejected or reported, never silently substituted.
10. Treat model output, previous layouts, and user text as untrusted input.
11. Never weaken `validate_layout`, `validate_design`, or `validate_document` to make a candidate pass.
12. Introduce changes behind a planner feature flag until the new path proves stable.

## 3. Current system baseline

```text
GenerateLayoutTab._on_ai_generate()
  -> worker thread
  -> ai_client.generate_layout()
  -> Gemini room program
  -> layout_engine.build_layout()
  -> Gemini furniture
  -> geometry_autofix.autofix_layout()
  -> validate_layout() + validate_design()
  -> Tk queue / UI thread
  -> LayoutSerializer.load_document(confirm=True)
  -> existing canvas + project state + 3D refresh
```

### 3.1 Current responsibilities

- `generate_layout/tab.py`: prompt UI, accepted conversation turns, worker lifecycle, cancellation, progress queue, activity feed, apply result.
- `generate_layout/ai_client.py`: Vertex configuration, prompt orchestration, bounded calls/time, parsing, initial generation, refinement, final gate.
- `generate_layout/layout_engine.py`: one deterministic two-row central-hallway “comb” topology.
- `generate_layout/ai_validator.py`: untrusted native schema and brief/design validation.
- `generate_layout/geometry_autofix.py`: fail-open mechanical repairs followed by fail-closed validation.
- `layout_serializer.py`: native/project validation, confirmation, backup, replacement, materialization, rollback, history reset, mutation notification.
- `FurnitureHelper/furniture_sizes.py`: physical furniture dimensions.
- `Helper/vastu_layout_generator.py`: existing placement knowledge that must be inspected before adding furniture logic.
- `generate_layout/service.py`: separate manual rectangle/compass builder; not the AI orchestrator.
- `generate_layout/storage.py`: not part of the accepted AI apply path.

### 3.2 Confirmed root causes of generic output

1. `build_layout()` always uses one full-width hallway with one north row and one south row.
2. Gemini controls room names/order and approximate width, not topology or geometry.
3. The room program lacks target depth/area, privacy, open-plan, setbacks, circulation style, hard/soft priorities, and ownership of attached spaces.
4. Zones and adjacency are encoded indirectly through row order and exact room-name pairs instead of solved by the engine.
5. `_column_widths_ft()` silently shrinks rooms to remain in bounds, potentially creating valid but unusable dimensions.
6. Initial generation is deterministic, but refinement returns to full-document coordinate rewriting.
7. Refinement validates a concatenation of all user messages, so superseded requirements can remain active.
8. `architecture_rules.md` requires a complete layout envelope while program/furniture stages require incompatible envelopes.
9. Autofix converts full-wall erased regions into partial openings with piers, limiting genuine open-plan output.
10. Furniture inventory and coordinates remain model-controlled and can be generic or impractical.

## 4. Target architecture

```text
User conversation
  -> requirement compiler
  -> canonical DesignSpec
  -> clarification/assumption report when needed
  -> feasibility analyzer
  -> topology candidate generators
  -> deterministic geometry packers
  -> opening/circulation planner
  -> deterministic furniture planner
  -> strict validation
  -> quality scoring and diversity filtering
  -> candidate preview/selection
  -> existing LayoutSerializer.load_document()
```

The LLM should interpret language, update structured intent, propose high-level alternatives, and summarize tradeoffs. Deterministic code should own feasibility, topology realization, dimensions, coordinates, openings, clearances, validation, and ranking metrics.

## 5. Canonical contracts

### 5.1 `DesignSpec`

Create a JSON-serializable internal contract with stable semantic IDs. It is not a replacement for native v1 and must never be passed to `LayoutSerializer` or the web importer.

Minimum fields:

```json
{
  "version": "1.0",
  "project_name": "North-facing family home",
  "plot": {
    "width_ft": 40,
    "depth_ft": 60,
    "facing": "N",
    "setbacks_ft": {"front": 0, "rear": 0, "left": 0, "right": 0}
  },
  "building": {
    "floors": 1,
    "footprint": "rectangular",
    "strategy_preferences": ["open_living_core", "zoned_wings"],
    "circulation_preference": "minimal_corridor",
    "privacy_priority": "high"
  },
  "rooms": [],
  "relationships": [],
  "furniture_requirements": [],
  "assumptions": [],
  "locked_constraints": []
}
```

Each room must include a stable `id`, semantic `type`, optional `role`, count, minimum/target/maximum dimensions or area, exterior-window requirement, zone preference, priority, flooring preference, and accessibility needs.

Each relationship must use room IDs and one of: `direct_door`, `adjacent`, `near`, `separate`, `open_plan`, `access_through_public`, or `attached_to`. Every relationship must carry `hard` or `preferred` priority.

### 5.2 Candidate contracts

Define internal, typed records:

- `FeasibilityReport`: feasible flag, hard failures, warnings, assumptions, minimum required area, available buildable area, alternatives.
- `TopologyCandidate`: strategy ID, room adjacency graph, zone/cell assignment, deterministic seed, explanation.
- `LayoutCandidate`: native v1 layout, originating spec/strategy, hard errors, score breakdown, compromises, metrics.
- `RequirementResult`: requirement ID, source text, interpreted constraint, status, evidence, compromise.

Use dataclasses or `TypedDict`; do not introduce a dependency solely for these records.

## 6. Implementation phases

Every phase must be independently releasable. Do not begin the next phase until the current phase's acceptance checks pass. Keep the old comb planner available as a fallback throughout the migration.

### Phase 0 — Freeze the baseline and add rollout controls

**Goal:** Make improvements measurable and reversible before changing behavior.

Tasks:

1. Record several real prompts that currently produce generic layouts, including expected rooms, zones, adjacencies, and qualitative differences.
2. Preserve the current `build_layout(program)` behavior as the named `comb` strategy; avoid changing its output while extracting an interface.
3. Add an environment/config switch such as `AI_LAYOUT_PLANNER=comb|multi`, defaulting to `comb` initially.
4. Add a deterministic seed to planner context; identical spec + strategy + seed must be reproducible.
5. Add a generation ID propagated through worker progress/results so stale results cannot apply after reset or a newer request.
6. Capture baseline call count, latency, validation failures, room dimensions, corridor ratio, and user-visible output for the fixed prompt set.
7. Do not log raw prompts or native documents unless explicit local debug mode is enabled.

Likely files:

- `generate_layout/ai_client.py`
- `generate_layout/layout_engine.py`
- `generate_layout/tab.py`
- `.env.example`

Acceptance:

- `comb` mode produces the previous output for the canonical self-check.
- Old cancellation/apply/rollback behavior is unchanged.
- Unknown planner mode fails clearly or falls back explicitly; it never silently selects an arbitrary path.

Rollback: set `AI_LAYOUT_PLANNER=comb`.

### Phase 1 — Split prompt contracts and compile a canonical `DesignSpec`

**Goal:** Remove contradictory model instructions and make current user intent explicit.

Tasks:

1. Split `architecture_rules.md` into shared safety/domain rules and stage-specific output contracts.
2. Keep the complete native-layout contract only for legacy full-document refinement while it remains in use.
3. Create a strict design-spec instruction/schema for initial extraction.
4. Create a separate furniture-inventory instruction; it must not inherit “return complete layout” language.
5. Parse model output with an explicit response schema if supported by pinned `google-genai`; otherwise validate the decoded object manually.
6. Add `design_spec.py` containing normalization, validation, stable ID generation, defaults, and bounded field lengths/counts.
7. Store the accepted current `DesignSpec` in `GenerateLayoutTab` beside the accepted native layout.
8. On refinement, ask Gemini to update the current spec or emit semantic operations, not concatenate all historical user requirements.
9. Maintain a requirement traceability list linking user statements to canonical constraints.
10. Present interpreted assumptions in the result; never silently omit a room or relationship.

New/changed files:

- New: `generate_layout/design_spec.py`
- New: stage-specific prompt files under `generate_layout/prompts/`, or clearly separated constants if fewer files remain simpler
- Changed: `generate_layout/ai_client.py`, `generate_layout/tab.py`

Acceptance:

- Contradictory envelope instructions are gone.
- “Four bedrooms” followed by “remove one bedroom” yields a current spec with three bedrooms.
- Duplicate display names do not break relationships because references use stable IDs.
- Invalid or oversized model output is rejected before planning.

### Phase 2 — Add feasibility and practical room standards

**Goal:** Refuse or negotiate impossible briefs instead of silently creating unusable rooms.

Tasks:

1. Add `feasibility.py` with room-type minimum dimensions, minimum area, aspect-ratio limits, circulation allowance, wall allowance, setbacks, and exterior-frontage requirements.
2. Apply practical defaults regardless of whether the user says “realistic dimensions.”
3. Distinguish minimum, target, and maximum dimensions.
4. Calculate buildable envelope separately from plot dimensions.
5. Detect impossible room counts, impossible hard adjacencies, insufficient exterior frontage, and conflicting hard zones.
6. Return actionable alternatives: enlarge plot, remove/merge rooms, relax a preference, reduce targets, or add a floor when supported.
7. Change `_column_widths_ft()` behavior in the new planner only: never shrink below practical room minima.
8. Keep old comb behavior unchanged behind the fallback flag until migration is complete.

New/changed files:

- New: `generate_layout/feasibility.py`
- Changed: `generate_layout/design_spec.py`, `generate_layout/ai_client.py`, `generate_layout/tab.py`

Acceptance:

- Dense briefs fail with a clear feasibility report instead of producing 3-ft bedrooms.
- Feasible briefs identify buildable width/depth after setbacks.
- Hard and preferred conflicts are reported separately.

### Phase 3 — Introduce a planner interface without changing output

**Goal:** Decouple orchestration from the current engine.

Tasks:

1. Define a minimal planner protocol accepting `DesignSpec`, strategy ID, and seed, returning topology/layout candidates.
2. Wrap the existing engine as `CombPlanner` rather than rewriting it.
3. Add a strategy registry; avoid a deep class hierarchy.
4. Make `ai_client.py` call the registry instead of importing one global `build_layout()` implementation.
5. Keep native-layout construction helpers shared: room records, IDs, flooring, gap finalization, compass, labels, and metadata.
6. Ensure every planner result passes the existing validators before it can be scored or displayed.

Suggested structure:

```text
generate_layout/
  planner.py
  planners/
    comb.py
  native_builder.py
```

Only create this structure if it reduces duplication; keeping two small modules is preferable to boilerplate.

Acceptance:

- Comb output remains equivalent for the same normalized input.
- Planner selection is explicit and logged in progress events.
- No changes to serializer or web importer are required.

### Phase 4 — Add recursive subdivision as the first flexible planner

**Goal:** Produce visibly different, usable room proportions with the smallest new geometry algorithm.

Tasks:

1. Implement deterministic recursive rectangular subdivision (“guillotine” slicing) of the buildable envelope.
2. Group rooms before slicing: public, private, service/wet, and circulation.
3. Allocate target areas, then choose horizontal/vertical cuts based on envelope aspect ratio and group adjacency.
4. Respect hard zone constraints while assigning groups and rooms to rectangles.
5. Enforce target/minimum dimensions and aspect ratios during search, not after layout creation.
6. Preserve a connected public circulation graph.
7. Add a bounded search limit and deterministic tie-breaking; never allow unbounded recursion.
8. Convert the winning rectangles through shared native-v1 builders.
9. Leave unresolved candidates invalid rather than invoking autofix as a design solver.

Acceptance:

- The planner passes native and structure validation for the canonical briefs.
- At least three materially different prompt types produce visibly different partitions.
- No room falls below its hard minimum or outside the buildable envelope.
- Same spec/seed produces identical output.

### Phase 5 — Add topology diversity and constraint solving

**Goal:** Support prompt-dependent circulation and room grouping rather than one universal plan.

Implement incrementally, not all at once:

1. `open_living_core`: living/dining circulation core with private/service rooms around it.
2. `side_corridor`: suitable for narrow plots.
3. `zoned_wings`: separate public and bedroom wings.
4. `split_bedroom`: master suite separated from secondary bedrooms.
5. `central_service_core`: wet/service rooms clustered internally, habitable rooms at exterior.
6. `courtyard`: only when footprint/site requirements permit it.
7. Optional later strategies: double-loaded corridor, L-shaped circulation, grid-cell planner.

Use the already-installed `python-constraint` where it helps with discrete assignments:

- room-to-zone/cell assignment
- required adjacency
- required separation
- exterior frontage
- public access
- attached-space ownership

Use bounded deterministic search for geometric optimization. Do not add OR-Tools or another heavy dependency until a measured limitation proves necessary.

Acceptance:

- Strategy choice is based on `DesignSpec`, not random model prose.
- Every hard relationship is either satisfied or the candidate is rejected.
- Candidate topology graphs are connected from a real exterior entrance.
- Different strategies produce meaningful structural diversity, not cosmetic coordinate shifts.

### Phase 6 — Generate, score, and de-duplicate multiple candidates

**Goal:** Select designs by quality, not merely by absence of validation errors.

Tasks:

1. Generate a bounded candidate set across compatible strategies and seeds.
2. Run `validate_layout()` and relevant `validate_design()` phases first; invalid candidates cannot be scored as acceptable.
3. Add `scoring.py` with a transparent score breakdown.
4. Score target-size accuracy, adjacency, circulation efficiency, exterior light/ventilation, privacy, Vastu preferences, furniture usability, and compactness.
5. Penalize corridor percentage, long travel paths, extreme aspect ratios, unusable residual strips, door conflicts, fragmented plumbing, and public/private conflicts.
6. Hard requirements are gates, not weighted score items.
7. Add topology/geometry fingerprints to remove near-duplicate candidates.
8. Keep the best few diverse candidates, not the top few copies of one strategy.
9. Return a requirement matrix and compromises for each candidate.

Recommended default weighting after hard gates:

- target dimensions: 20%
- requested adjacency: 20%
- circulation: 15%
- daylight/ventilation: 15%
- privacy: 10%
- Vastu preferences: 10%
- furniture usability: 5%
- compactness/waste: 5%

Acceptance:

- Scores include evidence and are reproducible.
- A lower-scoring candidate cannot win because of list ordering.
- At least two returned candidates differ in topology or meaningful room arrangement.

### Phase 7 — Add candidate preview and user-controlled acceptance

**Goal:** Stop treating one generated guess as the only possible answer.

Tasks:

1. Extend the Tk result area to present candidate summaries and selection controls without applying them immediately.
2. Show strategy, room schedule, key dimensions, score breakdown, requirement status, warnings, and compromises.
3. Provide actions such as “Use this plan,” “Try another topology,” “Larger rooms,” “Less corridor,” “More open,” and “More privacy.”
4. Apply only the selected candidate through the unchanged serializer path.
5. Keep current confirmation/backup behavior.
6. Make candidate state generation-scoped and discard it on reset/new design.
7. Preserve accessibility: keyboard focus, readable labels, and no color-only status.

Acceptance:

- Previewing candidates never mutates project/canvas state.
- Declining selection leaves the current canvas untouched.
- Applying a candidate still validates and rolls back through `LayoutSerializer`.

### Phase 8 — Replace coordinate-rewriting refinement

**Goal:** Make conversational changes predictable and preserve accepted intent.

Tasks:

1. Replace transcript concatenation with current `DesignSpec` + latest user request.
2. Ask Gemini for either a complete updated spec or bounded semantic operations.
3. Supported operations should include add/remove room, change count, set/clear zone, resize target, set relationship, set strategy preference, set furniture requirement, and lock/unlock constraint.
4. Validate operations and apply them to a copy of the current spec.
5. Offer two modes:
   - **Preserve layout:** local optimizer may change only affected rooms/relationships.
   - **Re-plan layout:** generate new candidates from the updated spec.
6. Preserve stable room IDs and locked constraints.
7. Keep the legacy full-document refinement behind a temporary fallback flag until spec refinement passes real QA.
8. Remove the legacy path only after migration evidence is recorded.

Acceptance:

- Superseded requirements no longer remain active.
- “Remove one bedroom” changes the canonical count and validation target.
- Locked rooms/constraints remain unchanged.
- Failed refinement leaves both accepted layout and spec unchanged.

### Phase 9 — Improve openings, doors, windows, and open-plan semantics

**Goal:** Make circulation and openness functional rather than uniformly centered.

Tasks:

1. Separate internal semantic opening types even if native v1 still serializes them as gaps plus door furniture.
2. Support `door`, `window`, `wide_opening`, and `full_open_plan_boundary` internally.
3. Preserve intentional full-wall erased regions; do not pull them into piers merely for generic corner clearance.
4. Apply corner clearance to doors where appropriate, not to intentional wall removal.
5. Choose door width, wall orientation, angle, hinge/swing preference, and placement based on circulation and furniture clearance.
6. Detect door-door, door-wall, and door-furniture conflicts.
7. Keep mirrored shared-wall openings exact.
8. Maintain native v1 compatibility until both Python and web importers support richer semantic openings.

Changed files may include:

- `generate_layout/native_builder.py`
- `generate_layout/geometry_autofix.py`
- `generate_layout/ai_validator.py`
- later, only if intentionally versioned: serializer/importer opening contracts

Acceptance:

- Open-plan requests visibly remove intended boundaries.
- Door records remain near matching partial gaps.
- Existing native-v1 files still deserialize and import.

### Phase 10 — Make furniture inventory model-assisted and placement deterministic

**Goal:** Improve usability and eliminate unsupported/generic furniture placement.

Tasks:

1. Inspect and reuse `Helper/vastu_layout_generator.py` and current furniture helpers before adding algorithms.
2. Let Gemini select semantic inventory/style intent, not final coordinates.
3. Place assets deterministically using room role, wall anchors, openings, windows, circulation paths, and physical footprints.
4. Add room-role templates for bedrooms, kitchens, living areas, dining, bathrooms, offices, and storage.
5. Enforce bed access, wardrobe clearance, dining clearance, kitchen work zones, stove/sink separation, and unobstructed doors.
6. Use bounded search/backtracking when several placements are possible.
7. Produce fewer valid items rather than overlapping or unsupported items; report unmet optional inventory.
8. Create one asset catalog as the source of truth for canonical name, aliases, filename/path, physical dimensions, supported room roles, and web mapping.
9. Generate validator/prompt allowlists from that catalog where practical.
10. Keep missing/unknown assets explicit; never substitute a sofa or another unrelated object.

Acceptance:

- Every emitted asset resolves to an actual image and mapping or is rejected before apply.
- Furniture footprints are inside rooms and preserve circulation.
- Same room/spec/seed yields reproducible placement.

### Phase 11 — Site planning and advanced scope

**Goal:** Model the difference between plot, buildable envelope, and building.

Tasks:

1. Apply front/rear/side setbacks to create the buildable envelope.
2. Support an actual footprint smaller than the plot.
3. Model optional garden, courtyard, parking, and entry path only with importer-safe entities.
4. Add site-facing versus entrance-facing semantics.
5. Do not fabricate stairs, pillars, beams, roads, decks, or railings through native v1.
6. Treat multi-floor generation as a separate future schema/integration project; the current Python bridge imports one floor.
7. Introduce native v2 only when source semantics and both import/export paths are designed and tested.

Acceptance:

- Plot dimensions remain metadata/canvas authority.
- Building geometry respects setbacks.
- Unsupported structural requests produce clear scope guidance rather than fake geometry.

### Phase 12 — Production reliability, security, and observability

**Goal:** Make failures diagnosable without exposing user data or weakening safety.

Tasks:

1. Remove the hard-coded cloud project fallback; require environment/application configuration.
2. Add a provider readiness check for SDK, ADC, project, location, and model before starting expensive work.
3. Record model/version, planner strategy, candidate count, call count, phase latency, validation categories, selected score, apply result, cancellation, and timeout.
4. Use local structured logs with redaction; raw prompts/layouts require explicit debug opt-in.
5. Distinguish provider failure, parse failure, infeasible brief, no valid candidate, user cancellation, timeout, and serializer failure in UI messaging.
6. Preserve strict call budgets and operation deadlines.
7. Retry only bounded, recognized transient provider failures.
8. Close clients and ignore late worker events after app shutdown.
9. Keep output complexity/entity limits and repair-payload limits.
10. Add generation IDs and exact active-request matching before applying results.

Acceptance:

- Production configuration has no repository-specific cloud project default.
- Every failed generation has a categorized reason without leaking secrets.
- Late, stale, or cancelled results cannot apply.

## 7. Verification strategy

Do not rely only on model calls. Most planner work must be testable offline.

### 7.1 Golden brief suite

Maintain representative briefs for:

- compact 2BHK
- narrow north-facing plot
- open-plan three-bedroom home
- high-privacy four-bedroom home
- courtyard preference
- split-bedroom plan
- senior/accessibility preference
- dense infeasible brief
- conflicting hard constraints
- refinement removing a room
- refinement preserving locked rooms
- unsupported multi-floor/structural request

For each brief, store expected requirements and invariants, not one exact coordinate snapshot unless reproducibility is the behavior under test.

### 7.2 Required checks per phase

1. Native schema validation returns no errors for accepted candidates.
2. Design validation returns no hard requirement errors.
3. Every room is in bounds, non-overlapping, and practically usable.
4. Circulation reaches every occupied room from a real entrance.
5. Required adjacencies have mirrored gaps and actual doors/open boundaries.
6. Required habitable/wet spaces have exterior ventilation when feasible.
7. Furniture resolves, fits, and does not block required paths.
8. Serializer apply succeeds and rollback restores prior state on an injected materialization failure.
9. Python native save/reload round-trip preserves semantics.
10. Web import and existing 2D/3D renderer still consume the native result.

### 7.3 Commands

From `2D_layout/2dlayoutMaker-main`:

```powershell
.\.venv\Scripts\python.exe -B generate_layout\layout_engine.py
.\.venv\Scripts\python.exe -B generate_layout\geometry_autofix.py
.\.venv\Scripts\python.exe -B generate_layout\ai_validator.py
```

Use an in-memory syntax compile or `py_compile` for changed Python modules. Run focused unit/self-checks before any live Vertex call. Do not invoke `_ai_smoke_tmp.py` unless credentials, billing, and a real provider test are explicitly intended.

For integration changes at repository root:

```powershell
npm run test:run
npm run build
npx eslint <changed-files>
```

The worktree contains substantial unrelated changes. Never reset, clean, or revert them.

## 8. Quality and acceptance metrics

A production candidate is acceptable only if:

- 100% of hard requirements are satisfied.
- Every compromise is disclosed.
- No room violates practical hard minimums.
- No required item is silently omitted.
- The result passes native, design, and serializer validation.
- Candidate alternatives are materially diverse when more than one is shown.
- The selected plan is applied only after user choice/confirmation.

Track improvement over the baseline:

- hard-requirement satisfaction rate
- infeasible-request detection accuracy
- accepted-first-generation rate
- regenerate/refine rate
- candidate diversity rate
- missing-asset rate
- validation-repair attempts
- provider calls and latency
- apply/rollback failures

## 9. Safe migration order

Implement in this order:

1. Baseline + feature flag.
2. Stage-specific prompts.
3. Canonical `DesignSpec` and requirement traceability.
4. Feasibility and practical minimums.
5. Planner interface wrapping the unchanged comb engine.
6. Recursive subdivision planner.
7. Candidate scoring and diversity filtering.
8. Candidate preview/selection.
9. Spec-based refinement.
10. Opening/door improvements.
11. Deterministic furniture and unified asset catalog.
12. Additional strategies, site planning, and production telemetry.

Do not implement all strategies in one change. One strategy, one offline check, and one guarded rollout at a time.

## 10. Instructions for an implementing AI

Before editing:

1. Read this guide and `docs/2d-3d-integration-handoff.md`.
2. Inspect current Git status/diff and preserve unrelated work.
3. Read the complete active flow in `tab.py`, `ai_client.py`, `layout_engine.py`, `ai_validator.py`, `geometry_autofix.py`, and `layout_serializer.py`.
4. Inspect every caller before changing a shared function.
5. Inspect `Helper/vastu_layout_generator.py`, furniture dimensions, asset files, and web asset mapping before adding parallel logic.
6. State the current phase and its exact acceptance criteria.
7. Implement only that phase's smallest coherent slice.

While editing:

1. Reuse existing validators, serializers, entity models, assets, and dependencies.
2. Keep model responses bounded and validate every trust boundary.
3. Keep Tk calls on the UI thread.
4. Keep provider work off the UI thread.
5. Preserve exact cancel/timeout/no-apply semantics.
6. Never “fix” a failing candidate by weakening validation.
7. Never silently drop requirements to obtain a valid plan.
8. Report infeasibility and alternatives explicitly.
9. Add one focused runnable check for each non-trivial new planner behavior.
10. Update only the live-session section of the handoff when substantive state changes.

After editing:

1. Run the smallest relevant offline checks.
2. Run diagnostics/syntax validation for every changed file.
3. Run targeted integration tests if the native contract or web importer changed.
4. Report what passed, what was not run, and why.
5. Record feature-flag/fallback behavior.
6. Do not claim visual quality without live Tk inspection.

## 11. Explicit anti-goals

Do not:

- return unrestricted full coordinates to Gemini for initial generation
- increase call budgets as the primary quality fix
- create another 3D renderer or converter
- pass `.hq.json` through the Python importer
- replace the working serializer apply transaction
- make autofix responsible for architectural decisions
- silently shrink rooms below usable minimums
- use display names as relationship identities
- keep concatenated historical prompts as current truth
- introduce native v2 before both producer and consumers are ready
- add a large solver dependency before measuring the installed constraint library
- expose secrets, ADC data, raw prompts, or layouts in production telemetry

## 12. Definition of done for the overall program

The improvement program is complete when:

1. Distinct prompts select or generate meaningfully different topologies.
2. The user can inspect multiple valid candidates and choose one.
3. The system explains assumptions, satisfied requirements, and compromises.
4. Impossible briefs produce actionable alternatives, not unusable rooms.
5. Refinements update canonical intent and preserve locked requirements.
6. Doors, windows, open-plan boundaries, and furniture are functionally placed.
7. Every accepted candidate passes the existing fail-closed validation/application pipeline.
8. Old native files, manual tools, autosave, rollback, and existing 2D/3D rendering still work.
9. The old comb planner remains an operational fallback until production evidence supports removal.
10. Golden briefs, offline planner checks, live Tk QA, and web import/3D smoke checks are green.

## 13. Immediate next implementation task

Begin with **Phase 0 and Phase 1 only**:

1. Preserve the current engine as explicit `comb` behavior behind `AI_LAYOUT_PLANNER`.
2. Create the canonical `DesignSpec` contract and validator.
3. Split the conflicting program, furniture, and full-layout prompt contracts.
4. Store current accepted spec in the Tk conversation state.
5. Add offline checks proving superseded requirements and stable room IDs work.

Do not add a second geometry strategy until these foundations are validated. Without canonical intent and feasibility, additional planners only produce more varieties of misunderstood requests.
