# Home Quest — AI Floor Plan Generator: Full Chat Context

*Complete record of the multi-session debugging conversation. Use this as project memory for new chats.*

---

## Project Overview

Home Quest integrates:
- A Python/Tkinter 2D floor-plan editor (`2D_layout/2dlayoutMaker-main/`)
- A React/TypeScript 2D editor and React Three Fiber 3D renderer (web side)
- Gemini 3.1 Pro Preview (Vertex AI) for AI-driven floor-plan generation

The AI layout flow runs entirely within the Python editor. The web importer, 3D renderer, and `LayoutSerializer` are **never changed**; the only AI apply path is `LayoutSerializer.load_document(layout, confirm=True)`.

---

## Active Configuration

| Setting | Value |
|---|---|
| Model | `gemini-3.1-pro-preview` |
| Location | `global` |
| Thinking level | `HIGH` (Gemini 3 ThinkingLevel enum) |
| Max output tokens | 32,000 (cap 65,536) |
| Layout planner | `multi` (`AI_LAYOUT_PLANNER=multi` in `.env`) |
| Seed | `0` (`AI_LAYOUT_SEED=0`) |
| CP-SAT dependency | `ortools==9.11.4210` (installed in editor `.venv`) |

---

## Key Files Changed

| File | What changed |
|---|---|
| `generate_layout/ai_client.py` | Multi pipeline, thinking config, validation brief, token limits |
| `generate_layout/design_spec.py` | Alignment, coercions, plot extraction, trim rules |
| `generate_layout/native_builder.py` | North-up compass |
| `generate_layout/planners/constraint_solver.py` | **New** — CP-SAT solver |
| `generate_layout/planners/__init__.py` | Registers constraint_solver |
| `generate_layout/_multi_pipeline_check.py` | Extended regression suite |
| `requirements.txt` | Added `ortools==9.11.4210` |
| `.env` + `.env.example` | Model, location, token limits |

---

## Problems Found and Fixed (in order)

### P1: Comb layout for every prompt
**Root cause:** `multi` mode asked Gemini for a comb-specific room program and required a valid comb shell before flexible planning.
**Fix:** Multi mode builds a canonical `DesignSpec` directly, runs feasibility, then a registry of planners (subdivision, templates, CP-SAT, comb fallback).

### P2: "brief requests a foyer but the spec has none"
**Root cause:** `align_with_brief` re-read the brief with substring matching to require rooms. An exclusion list (`Do not add: foyer…`) was misread as a request list.
**Fix:** Removed the room-keyword requirement check entirely. Only bedroom count is enforced by keyword matching; all other requirements come from the DesignSpec.

### P3: Same error from a second module
**Root cause:** `ai_validator.validate_design` had the identical substring-matching logic.
**Fix:** Multi mode passes an empty brief to `validate_design` at all call sites (`validation_brief = "" if planner_mode == "multi" else design_brief`).

### P4: `furniture_requirements` must be an array / must contain at most 200 items
**Root cause:** Model returned furniture hints as an object (`{"room_living": ["sofa"]}`) or an oversized list. Parser hard-failed the structural spec.
**Fix:** Advisory fields are shape-tolerant. Object → coerced to list. Over-long → clamped. Non-array → empty. Structural fields remain strict.

### P5: `strategy_preferences` — `unknown strategy preferences: ['_','c','e',...]`
**Root cause:** Model returned `"open_living_core"` (string) instead of `["open_living_core"]` (list). Parser iterated the string character-by-character.
**Fix:** `_as_str_list()` wraps a bare string before filtering.

### P6: "Interpreted 10 spaces on 6×7 ft"
**Root cause:** `align_with_brief` grabbed the *first* `NxM` regex match; the model had set the plot to a room's size, and the first match was that small room.
**Fix:** `_extract_plot_dimensions()` prefers a pair whose context mentions `plot`/`lot`/`site`, else the largest-area pair.

### P7: 9-room hard brief — degenerate 16×37 bedrooms, wrong zones
**Root cause:** Guillotine subdivision and fixed templates cannot pack a brief with four fixed Vastu zones + attached bath + open kitchen + east entrance simultaneously.
**Fix:** Added CP-SAT `constraint_solver` planner. OR-Tools exact-cover tiling with hard zone, adjacency, and frontage constraints. Registered in the existing strategy registry.

### P8: Giant kitchen filling most of the plan
**Root cause:** Plot (3,952 ft²) much larger than rooms need (~2,000 ft²). Exact cover must fill it; surplus went into the kitchen. Hard area caps make the search too slow.
**Fix:** Two-phase solve — balanced attempt (2× fair-share area cap) then fast uncapped fallback. Deterministic-only budget (no wall-clock cap, which was cutting the search too early). 9-room balanced at 29%; 10-room on large plot may still be less balanced.

### P9: Common bathroom silently deleted
**Root cause:** `align_with_brief` defaulted bathrooms to max 1 when no explicit count phrase. A brief naming "master bathroom" and "common bathroom" (but not "2 bathrooms") lost the second.
**Fix:** Only an explicit count phrase enforces a maximum. Living/bathroom the user never mentioned stay capped at 1. A type the user mentioned without a number keeps the model's count.

### P10: 504 DEADLINE_EXCEEDED
**Root cause:** Gemini 3.1 Pro Preview with HIGH thinking on a large brief exceeded Vertex's deadline.
**Not a code bug.** Retrying usually works. `AI_LAYOUT_THINKING_LEVEL` env var can lower it if needed. Model and thinking level are not changed without user permission.

---

## Architecture

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
  - open_living_core / side_corridor / zoned_wings  (fixed templates)
  - recursive_subdivision                            (guillotine heuristic, 3 seeds)
  - constraint_solver                                (CP-SAT exact-cover, 2-phase)
  - comb                                             (legacy, unchanged fallback)
    ↓
validate_topology (hard gates before native build)
    ↓
native_builder (PlacedRoom → VastuCraft v1 JSON)
    ↓
validate_layout + validate_design (geometry + structural)
    ↓
score + rank + diversify
    ↓
Gemini furnishes the best candidate
    ↓
LayoutSerializer.load_document(confirm=True)
```

---

## Offline Regression Suite

Run with the editor's `.venv` interpreter:

```powershell
# Compile all changed modules
.\.venv\Scripts\python.exe -m py_compile generate_layout\design_spec.py generate_layout\ai_client.py generate_layout\planners\constraint_solver.py

# Module self-checks
.\.venv\Scripts\python.exe -m generate_layout.design_spec
.\.venv\Scripts\python.exe -m generate_layout.feasibility
.\.venv\Scripts\python.exe -m generate_layout.native_builder
.\.venv\Scripts\python.exe -m generate_layout.planners.constraint_solver
.\.venv\Scripts\python.exe -m generate_layout.planners.subdivision

# Full multi-pipeline integration check (~125s due to solver)
.\.venv\Scripts\python.exe -m generate_layout._multi_pipeline_check
```

The pipeline check covers: legacy comb rollback, multi-planner valid/diverse/deterministic candidates, exact 40×60 prompt regression, exclusion-list regression, and the hard 9-room end-to-end path.

---

## Known Limitations / Next Steps

1. **Large kitchen on oversized plots.** Exact cover surplus goes into one room when the balanced CP-SAT attempt times out (10 rooms on 52×76 ft). Fix: warm-start hint for the solver, or use a right-sized plot (e.g. 40×52 ft).
2. **Gemini 3.1 Pro is public preview.** Live behavior unmeasured; only offline pipeline validated. Restart + New Design needed before each live test.
3. **Phase 7 (candidate preview UI), Phase 9 (open boundary walls), Phase 10 (deterministic furniture)** — deferred.
4. **Hard `separate` relationships** not modeled in CP-SAT (rarely satisfiable in exact tiling).
5. **Non-rectangular rooms** not representable; all rooms are axis-aligned rectangles.

---

## Restart + Test Checklist

1. Close the editor window (all services tear down).
2. Run `run-home-quest.ps1`.
3. Click **New Design** (clears accumulated conversation).
4. Run your prompt.
5. Check BACKEND ACTIVITY for: correct plot dimensions, 10 spaces, `selected_strategy=constraint_solver`.
6. If a 504 occurs, retry once — it's a latency timeout, not a logic error.

---

## Invariants — Never Change Without Explicit Permission

- Model: `gemini-3.1-pro-preview`
- Thinking level: `HIGH`
- `LayoutSerializer.load_document(confirm=True)` is the only AI apply path
- `comb` remains an operational fallback
- Native VastuCraft v1 schema
- Web importer, 3D renderer, serializer paths
