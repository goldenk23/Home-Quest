# Home Quest — AI Floor Plan Generator: Debugging Story

*A technical narrative of building a reliable AI-driven floor plan generator from scratch, suitable for interviews.*

---

## The Project

Home Quest integrates a Python/Tkinter 2D floor-plan editor with a React/Three.js 3D renderer. The challenge: let users describe a home in natural language and have the system generate a geometrically valid, Vastu-compliant, architecturally sensible floor plan — rooms, doors, windows, circulation, furniture — applied directly to the canvas.

The stack: Gemini 3.1 Pro (Vertex AI) for language interpretation, deterministic Python for geometry, OR-Tools CP-SAT for constraint solving, and a strict validator before anything touches the canvas.

---

## Phase 1: The Wrong Architecture

The original approach asked Gemini to return a complete `rows.top`/`rows.bottom` room program and then build geometry from it. Gemini was doing layout arithmetic — zone placement, dimension math, circulation — which it's not reliable at.

**Symptom:** Every prompt returned a comb-style layout regardless of brief.

**Root cause:** Architecture trusted the model for decisions deterministic code should own.

**Fix:** Split responsibilities cleanly.

> *"Gemini interprets language. Deterministic code owns geometry."*

Gemini now produces a structured `DesignSpec` (rooms, zones, relationships, priorities). Deterministic planners, a feasibility gate, a CP-SAT solver, and a strict validator own everything from placement to doors.

---

## Phase 2: The Trust Boundary Problem

Once we had a structured spec, a new class of bugs appeared: the deterministic layer was re-reading the user's natural-language brief with Python substring matching to second-guess what the model had produced.

**Three concrete failures from this one mistake:**

### 2a. "brief requests a foyer but the spec has none"

The prompt said: *"Do not add: foyer, utility room, balcony…"*

The validator saw `"foyer"` in the brief, required a foyer room, and rejected every valid layout. The exclusion list was being read as a request list.

**Fix:** Removed the room-keyword requirement check entirely. The model interprets prose; the deterministic layer enforces only reliably-extractable facts (plot dimensions, bedroom count, facing, zero-setback default).

### 2b. Same logic in a second module

Fixed it in `align_with_brief`. Tested. Worked. Shipped. Next run: `"design brief requires a foyer/dining/utility"` — same error, different file.

`ai_validator.validate_design` had the identical substring-matching logic, called from three separate points in the pipeline.

**Fix:** In multi mode, pass an empty brief to `validate_design`. Requirements are enforced structurally by `DesignSpec` + `validate_topology`. Comb mode (no structured spec) unchanged.

**Lesson:** Fixing one instance of a fragile pattern without auditing for duplicates is incomplete. Grep for the pattern, not just the symptom.

### 2c. The exclusion list as a "do not add" list

Even after fixing validators, `align_with_brief`'s initial pruning used `_positive_clauses()` to strip negated clauses — but a multi-line list like:
```
Do not add
Foyer
Utility room
Office
```
…produced one clause per line, each containing a room name with no negation cue. So "Foyer" passed as a positive request.

**Fix:** Removed the per-room requirement check entirely. `_positive_clauses` now only drives best-effort pruning of model-invented rooms, never hard validation.

---

## Phase 3: Model Output Shape Mismatches

Gemini 3 returns structured JSON, but not always in the schema shape the parser expects.

**Three failures, same class:**

| Field | What the parser expected | What the model returned | Error |
|---|---|---|---|
| `furniture_requirements` | Array of `{room_id, items}` | Object `{"room_living": ["sofa"]}` | "must be an array" |
| `furniture_requirements` | Array | Array with 250 items | "must contain at most 200 items" |
| `strategy_preferences` | `["open_living_core"]` | `"open_living_core"` (bare string) | "unknown strategy preferences: `['_','c','e','g','i','l','n','o','p','r','v']`" |

The last one is my favourite: the parser iterated the string character-by-character, so every letter of `open_living_core` became an "unknown strategy."

**Fix (general):** Advisory fields (`furniture_requirements`, `strategy_preferences`, `assumptions`, `traceability`) are now shape-tolerant. A bare string → wrapped in a list. An object → coerced to `[{room_id, items}]`. Over-long arrays → clamped. Non-array scalars → ignored (empty). Structural fields (rooms, plot, relationships) remain strict.

**Pattern:** Advisory fields that feed a later stage do not need to fail the structural spec. Strict validation belongs at the semantically critical fields.

---

## Phase 4: The Plot vs Room Dimension Collision

**Observed:** "Interpreted 10 spaces on **6×7 ft**" — the puja room's size, not the 52×76 ft plot.

**Root cause:** `align_with_brief` extracted plot dimensions by grabbing the *first* `N×M` regex match in the full brief. A brief with 10 rooms lists 10 dimension pairs; if the model had mis-set the plot to a room's size, the first-match extraction latched onto a small room before reaching the corrected plot statement.

**Fix:** `_extract_plot_dimensions()` collects all pairs, prefers any pair whose surrounding text names the plot (`plot`/`lot`/`site`/`parcel`/`land`), else picks the largest-area pair. A plot is always larger than any single room.

**Guard:**
```python
assert _extract_plot_dimensions(
    "52 ft × 76 ft rectangular plot. puja 6×7 ft."
) == (52, 76)
```

---

## Phase 5: The CP-SAT Solver

**Problem:** The heuristic planners (guillotine subdivision, fixed templates) can only produce "sliceable" plans. A hard brief — 9 rooms with four fixed Vastu zones, an attached master bathroom, an open kitchen, east entrance, privacy constraints — exceeded what any heuristic could pack. Every candidate failed validation with degenerate aspect ratios and wrong zones.

**Solution:** Add a CP-SAT exact-cover planner as a new strategy in the existing registry.

The solver models rooms as integer rectangles on a 1-ft grid and enforces:
- Non-overlap + exact cover (gap-free, connected tiling)
- Per-room minimum size and maximum aspect ratio
- Hard Vastu zone quadrants (N=top, W=left)
- Hard exterior-window rooms on the perimeter
- Entrance on the facing edge
- Hard adjacency (attached/open-plan/adjacent) as a ≥3 ft shared wall

It's registered in `planners/__init__.py` and participates in the existing scoring/ranking/fallback pipeline. Comb, subdivision, and templates are unchanged.

**Result:** On the hard 9-room east-facing brief, every heuristic strategy failed. The CP-SAT solver produced a validator-clean, natively-built, scored (0.876), deterministic, selected layout.

---

## Phase 6: The Oversized-Plot Balance Problem

With exact cover, the total room area must equal the plot area. A 52×76 ft plot for 10 rooms that need ~2,000 ft² has ~2,000 ft² of surplus that must go *somewhere*.

**Symptom:** The kitchen occupied most of the plan.

**First attempt:** Hard maximum area caps per room type (kitchen ≤ 220 ft², bathroom ≤ 120 ft²). Result: CP-SAT's search became too slow, timed out, returned nothing. Failure.

**Second attempt:** Exclude the living room from the deviation objective, letting it absorb the surplus. Result: Search couldn't find a feasible point at all. Failure.

**Third attempt:** Two-phase solve — balanced attempt (2× fair-share area cap) first, then fast uncapped fallback. Combined with removing wall-clock limits (which were cutting the search before the deterministic budget could find a solution). Result: 9-room case solves balanced (biggest room 29%). 10-room case exceeds the balanced budget and falls back to the uncapped solve, where the kitchen can still be large.

**Honest status:** The root cause is an oversized plot (52×76 for ~2,000 ft² of rooms). Matching the plot to the rooms (e.g. 40×52 ft) gives a well-proportioned layout. The warm-start hint for harder cases is the correct next step.

---

## Key Patterns

**1. The model interprets; deterministic code enforces.**
Never ask the model to produce geometry or re-derive semantic requirements from text it already interpreted. Natural language is the model's domain. Constraint satisfaction is the solver's domain.

**2. Trust boundaries must be explicit.**
Advisory fields (furniture hints, strategy preferences, assumptions) cannot be allowed to abort a structurally valid spec. Only structurally critical fields (rooms, plot, relationships) deserve hard rejection.

**3. Grep for the pattern, not just the instance.**
Every case of "the same logic was in a second module" was preventable by searching for the pattern after fixing the first instance.

**4. Validate with intentionally bad inputs.**
The regression that caught the string-strategy-preference bug was:
```python
spec = from_dict({"building": {"strategy_preferences": "open_living_core"}, ...})
assert spec.building["strategy_preferences"] == ["open_living_core"]
```
Not a unit test of a function — a minimal runnable guard that fails exactly when the bug regresses.

**5. A valid layout that exists beats any timeout.**
Hard area caps made the solver provably correct but practically useless (timeouts → failures). The two-phase design (balanced attempt, fast fallback) means the system never fails when a valid layout exists — it may be less proportioned, but it's applied.

---

## Architecture Summary (current)

```
User prompt
    ↓
Gemini 3.1 Pro Preview (language interpretation only)
    ↓
align_with_brief (deterministic: plot size, bedroom count, zones, setbacks)
    ↓
DesignSpec (stable IDs, relationships, hard constraints)
    ↓
Feasibility check (area, frontage, zones)
    ↓
Strategy registry:
  - open_living_core / side_corridor / zoned_wings (fixed templates)
  - recursive_subdivision (guillotine heuristic, 3 seeds)
  - constraint_solver (CP-SAT exact-cover, 2-phase)
  - comb (legacy, unchanged fallback)
    ↓
validate_topology (hard gates before native build)
    ↓
native_builder (rooms → VastuCraft v1 JSON: walls, doors, windows, compass)
    ↓
validate_layout + validate_design (geometry + structural only)
    ↓
score + rank + diversify
    ↓
Gemini furnishes the best candidate
    ↓
LayoutSerializer.load_document(confirm=True) — only apply path
```

---

## Numbers

| Metric | Value |
|---|---|
| Hard 9-room brief: heuristics | All fail |
| Hard 9-room brief: CP-SAT | Score 0.876, valid, selected |
| Exact 40×60 prompt: balanced plan | `open_living_core`, score 0.817 |
| Model | Gemini 3.1 Pro Preview, HIGH thinking |
| Max output tokens | 32,000 (65,536 cap) |
| CP-SAT dependency | `ortools==9.11.4210` |
| Offline regression suite | `_multi_pipeline_check.py` + per-module self-checks |
