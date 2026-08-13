# Testing and release validation

This page covers how to check that the app works: the automated tests you can run offline, what they do **not** cover, and the manual checklist to walk through before calling anything "released".

## The automated checks (run these first)

All of these run **offline** — no Google account, no internet, no cost.

From `2D_layout\2dlayoutMaker-main` in PowerShell:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Runs the whole test suite. This checks the important safety machinery: the strict project format, floor operations, save/load rollback, atomic saves, autosave, undo/redo snapshots, snapping, room detection, and door/window cut-outs.

```powershell
.\.venv\Scripts\python.exe -m py_compile app.pyw embedded_viewer.py layout_serializer.py generate_layout\service.py generate_layout\ai_client.py
```

Confirms the most critical files have no syntax errors (Python can parse them).

```powershell
.\.venv\Scripts\python.exe generate_layout\geometry_autofix.py
.\.venv\Scripts\python.exe generate_layout\ai_validator.py
```

Runs the AI geometry-fixer and validator's own built-in self-checks.

Then, from the repository root, a quick hygiene check that no broken whitespace or unintended files sneak into Git:

```powershell
git diff --check
git status --short
```

> **Why no live AI test?** Real AI calls need network, credentials, quota, and money, and they depend on a model Google can change at any time. Test AI only in an approved Google Cloud test project, by hand.

## What each test file covers

| Test file | What it proves |
|---|---|
| `tests/test_parity_foundation.py` | Old files migrate correctly; the strict format rejects bad projects; floors/references/stairs behave; saves are atomic; failed loads roll back; autosave and undo snapshots work. |
| `tests/test_mixed_tool_snapping.py` | The Room and Draw tools coexist; snapping works in both directions; guides appear and disappear correctly; overlapping is prevented. |
| `tests/test_room_drag_group.py` | Room detection finds closed loops; dividers split rooms; dragging connected rooms and walls works with snapping. |
| `tests/test_wall_openings.py` | Doors/windows attach to the nearest wall, drag correctly, and show distinct symbols. |

> **Heads-up about skips:** tests that need a real screen quietly *skip* themselves when run on a machine without a display. A green run with skips may not have tested the interactive parts at all — always read the skip lines in the output.

## The manual release checklist

Automated tests can't open windows and look at them. Before any release, do this by hand:

1. **Launch** only through `2D_layout/run-2d-editor.ps1`; confirm the app starts and closes cleanly.
2. **Draw:** create rooms with both the Room and Draw tools; divide a closed loop; name rooms; drag them.
3. **Edit:** check snapping, guides, doors/windows, furniture, flooring, dimensions, zoom, and undo/redo.
4. **Floors:** create, duplicate, rename, change elevation, switch, and delete floors; add pillars/beams/stairs; adjust the sun.
5. **Save/load:** save as JSON and as YAML; reload both; confirm parked floors, undo behavior, and that the plan looks identical.
6. **Autosave:** edit something, wait more than two seconds, and confirm a valid autosave plus rolling backup exists under `%LOCALAPPDATA%\VastuApp`.
7. **3D:** walk **Plan → 3D View → Split → Plan**; confirm geometry, edits, floors, furniture, and finishes all show up and refresh.
8. **AI (if in scope):** generate a small single-floor plan; refine it; cancel one request mid-flight; try a multi-floor brief and remember stairs between floors are not auto-aligned.
9. **Hygiene:** confirm no secrets or user data are staged in Git, and that `viewer_dist/` and `assets/` are complete in the release.

## Known gaps (what nobody checks automatically)

There are no automated tests for: app startup/shutdown, the autosave final-close window, backup cleanup, AI threading in the UI tab, live AI calls, AI timeout/cancel/repair behavior, generated-layout storage, installer behavior, the WebView2 browser lifecycle, viewer message compatibility, or reproducible viewer builds.

If you change code in one of those areas, **you are the test suite** — validate it manually, and if you add non-trivial logic, add the smallest possible regression test with it.
