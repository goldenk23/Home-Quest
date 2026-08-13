# Architecture

This page explains how VastuCraft is built on the inside — what the parts are, who is in charge of what, and how your edits travel through the app. No background knowledge is assumed; unusual terms are explained as they appear.

## The one-sentence version

VastuCraft is a single Windows program: a 2D drawing canvas, a strictly-checked project record, an optional AI helper, and a built-in 3D window — all kept in sync through one official copy of your plan.

## The cast of characters

Think of the app as a small design office with clearly separated jobs:

| Who | Real name in code | Their job |
|---|---|---|
| **The drawing board** | `view.py`, `model.py`, `controller.py`, `tools.py` | What you see and touch. Shows the plan, handles mouse clicks, drawing, moving, snapping. |
| **The historian** | `action.py` (`ActionManager`) | Remembers every change so undo/redo works, and rings a bell ("something changed!") that other parts listen to. |
| **The official record book** | `project_state.py` (`ProjectState`) + `layout_schema.py` | Holds the one official version of your project, in a strict format, and refuses anything invalid. |
| **The translator** | `layout_serializer.py` (`LayoutSerializer`) | Converts between the drawing board's working style and the record book's strict format, in both directions. Also handles save/load. |
| **The cautious assistant** | `local_autosave.py` (`LocalAutosave`) | Whenever the bell rings, waits a moment, then safely photocopies the record book to disk. |
| **The AI desk** | `generate_layout/` | Turns your plain-English wishes into a plan — but only through the official channels. |
| **The 3D showroom** | `embedded_viewer.py` + `viewer_dist/` | A small built-in browser window that draws your plan in 3D. |

The key idea: **the drawing board and the record book are deliberately different.** The board is optimized for fast, interactive editing. The book is optimized for safety and long-term storage. The translator keeps them equal, so neither side has to care how the other works.

## How an edit travels through the app

Here is exactly what happens when you drag a wall:

```text
You drag a wall
   │
   ▼
1. Drawing board updates the picture and tells the historian:
   "record this as ONE undoable action"
   │
   ▼
2. Historian stores it and rings the bell
   │
   ├──────────────► 3. Assistant starts a 2-second timer;
   │                    when it fires, asks the translator for the
   │                    official copy and saves it to disk
   │
   └──────────────► 4. If 3D is open, the showroom asks the
                        translator for the official copy and redraws
```

Two consequences worth remembering:

- **Undo works on real actions** ("move wall"), not on tiny internal steps — because the historian records one entry per logical action.
- **Autosave and 3D never read the drawing board directly.** They always go through the translator, so they only ever see valid, checked data.

## How loading a file works (and why it can't half-fail)

Opening a project file is treated like a bank transaction — it either fully succeeds or leaves everything untouched:

1. Read the file and check it against the strict format. Anything wrong → stop, nothing changes.
2. Take a snapshot of the current project, canvas, and history.
3. Swap in the new project and rebuild the canvas from it.
4. If rebuilding throws an error → put the old snapshot back. You keep your previous work.
5. Only when everything succeeded: clear the undo history (old undo steps refer to the old project).

## How AI generation fits in

The AI follows the same rules as everything else — it never gets a shortcut to your project:

```text
Your description
   │
   ▼
1. AI reads it and answers with a WISH LIST
   (rooms, sizes, relationships — no final geometry)
   │
   ▼
2. The app's own planner draws the actual rectangles
   │
   ▼
3. A fixer repairs broken shapes
   │
   ▼
4. A strict checker rejects anything invalid
   │      (if the problem list is small, the AI gets
   │       a limited chance to fix it and we retry)
   ▼
5. A valid plan is handed to the translator,
   which places it on the drawing board like any other edit
```

Also important: the AI runs on a **background worker** (a separate lane of work) so the app never freezes while waiting for Google. The worker is not allowed to touch the screen directly — it posts its result to the main part of the app, which applies it. Each request carries an increasing ID number, so a late answer from an old, cancelled request is recognized as stale and thrown away.

Full detail: [AI layout generation](ai-layout-generation.md).

## Startup and shutdown

1. `app.pyw` (the starting point) builds all the parts above and connects them. The 3D showroom is created but stays asleep until you first open **3D View** or **Split**.
2. While you work, everything happens on the app's single **UI thread** — the one lane of work allowed to touch the screen.
3. When you close the app, scheduled work is cancelled and the browser is disposed of. One deliberate gap: if the autosave assistant's 2-second timer is still counting down at that moment, it is cancelled rather than rushed — so the very last edit can be missing from autosave. **Explicit Save is the strongest guarantee.**

## The rules the design follows

- **Windows is the target.** The launcher and the embedded 3D window rely on Windows-specific pieces (WebView2, PowerShell).
- **Two formats coexist on purpose.** The record book's strict format ("v2") is the official contract, but each floor also keeps the drawing board's original working data ("v1") so older files and mature tools keep working. Removing that compatibility layer would be a real migration project, not a cleanup.
- **The 3D showroom is read-only and local.** Its files are served inside your own computer only (nothing is exposed to the network), and it cannot modify your project — it only displays it.
- **The AI is never trusted.** Its answers are treated as suggestions until the app's own checks pass.
- **No construction guarantee.** Geometry checks and Vastu scoring are heuristics — useful guidance, not professional certification.

## Words used on this page

| Term | Plain meaning |
|---|---|
| **Schema** | A strict form that data must fit into — fixed fields, types, and rules. |
| **Canonical / official copy** | The single version of the project every part of the app agrees to use. |
| **Serializer** | Code that converts data between two formats (here: canvas ⇄ official project). |
| **Transaction** | A set of changes treated as one unit: fully applied, or not at all. |
| **UI thread** | The single lane of work allowed to touch windows, buttons, and the canvas. |
| **Debounce** | "Wait until activity pauses, then act once" — autosave waits 2 seconds after your last edit instead of saving on every mouse movement. |
| **WebView2** | A Microsoft component that lets a desktop app embed a small Edge browser window. VastuCraft uses it for 3D. |
| **Loopback / 127.0.0.1** | An address that means "this computer only" — the 3D files never leave your machine. |

**Next:** [Developer guide](developer-guide.md) for where each behavior lives in the code, or [Data model and persistence](data-model-and-persistence.md) for the storage details.
