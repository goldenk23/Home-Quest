# Data model and persistence

This page explains how your project is represented inside the app, and how saving, loading, autosave, and recovery work. Plain language throughout — terms are defined at the bottom.

## The project, as a filing cabinet

A VastuCraft project is one document with a fixed shape (the **schema**). Think of it as a filing cabinet:

```text
Project (version "2.0")
├─ metadata                 → notes about the project itself
├─ active_floor_id          → which floor is on your screen right now
├─ floors[]                 → one folder per floor
│   ├─ id, name, elevation_cm
│   └─ geometry             → everything drawn on that floor:
│       ├─ vertices, walls, rooms, openings, furniture
│       ├─ shapes, text
│       └─ pillars, beams, deck_slabs, railings, stairs
├─ sun_settings             → time of day + sun direction, for shadows
└─ cross_floor_references[] → explicit links between things on different floors
```

The exact rules are written in code in `layout_schema.py` — that file **is** the contract; there is no separate specification document. The current format version is **2.0** ("v2").

## The rules every project must satisfy

Before any project is accepted — from disk, from the AI, or from an edit — it must pass these checks:

- **One ground floor.** Exactly one floor sits at elevation 0.
- **Sensible floors.** Floor names (ignoring case and surrounding spaces) and elevations are unique; elevations are never negative; the active floor must exist.
- **Unique IDs.** Every floor, wall, room, door, etc. has an ID, and no two things anywhere in the project share one.
- **References must resolve.** If a door says "I belong to wall X", wall X must exist on the same floor. Links *between* floors must be listed explicitly in `cross_floor_references`.
- **Stairs go up.** A staircase belongs to the lower floor and must target an existing higher floor.
- **Numbers must be real.** All geometry must be finite (no infinities or NaNs — impossible values computers can produce).
- **Sane sun.** Time of day is 0–24 hours; direction is 0–360 degrees.

If anything fails, the whole document is rejected — there is no such thing as a partially accepted project.

## How changes are made safely

`ProjectState` is the keeper of the official copy. Two habits make it safe:

- **It never hands out the original.** Anyone who asks for the project gets a copy, so nobody can accidentally (or maliciously) scribble on the real thing.
- **Changes are transactions.** To change something, the app edits a *draft copy*, runs the full rule check on the result, and only then swaps it in. Fail the check → the draft is thrown away and the old project stays.

Floors are managed by `FloorManager`: add, activate, rename, change elevation, duplicate, delete. Duplicating a floor remaps all internal references and intentionally leaves out roads, stairs, annotations, and text. You cannot delete the last floor, nor a floor that something on another floor still points to.

## Why two formats coexist (v1 and v2)

The drawing canvas is older than the strict format and works in its own style ("v1"). Instead of rewriting years of mature canvas behavior, the app keeps both:

- **v2 is the official contract** — used for saving, autosave, undo snapshots, AI output, and the 3D view.
- **v1 is kept for compatibility** — stored untouched inside each floor (`geometry.canvas`) so old files open perfectly and the canvas tools keep working exactly as they always have.

The serializer derives clean v2 geometry from the canvas while preserving the original v1 payload, so a save → load round-trip loses nothing. The AI's first-pass checker also works in v1 terms, since the AI produces single-floor canvas content.

> Do not "clean up" the embedded v1 data. Removing it is a migration project with tests, not a tidy-up.

## Saving and loading

- Files can be **JSON or YAML** (`.json`, `.yaml`, `.yml`).
- Every save is an **atomic write**: the app writes the full document to a temporary sibling file, forces it to disk, then instantly swaps it over the old file. At no moment can a crash leave a half-written project file.
- Loading validates the *entire* document before touching your screen. If rebuilding the canvas fails midway, the app restores your previous project and canvas — a bad file can never eat your current work.
- The undo history is cleared only *after* a load fully succeeds.
- **Save As** may write anywhere you choose.

## Autosave and recovery

Autosave runs by itself, with one behavior worth understanding:

- It uses a **2-second trailing debounce**: it waits until you *pause* editing for 2 seconds, then saves once. (Saving on every mouse movement would be wasteful; saving on a pause catches everything that matters.)
- It writes to `%LOCALAPPDATA%\VastuApp\saved_layouts\autosave.json`, and keeps up to **10 timestamped backups** in the `backups\` subfolder.
- When you close the app, a *pending* autosave timer is cancelled — it is not rushed. So if you edit and immediately slam the window shut, that last edit may exist only in your explicit **Save**.

**Recovery order** (after a crash): try your manually saved file first, then `autosave.json`, then the backups, newest first. Always *copy* a recovery file somewhere safe before opening or editing it.

> `%LOCALAPPDATA%\VastuApp` is real user data. Back it up before upgrades; never delete it during "cleanup".

## A note on AI-generated layouts

There is a storage helper that can write timestamped AI results under `%LOCALAPPDATA%\VastuApp\generated_layouts\`, but not every AI result is guaranteed to land there. Treat that folder as a convenience, not an archive: **explicitly save any AI plan you want to keep.**

## Words used on this page

| Term | Plain meaning |
|---|---|
| **Schema / v2** | The fixed shape and rules every project document must follow. Version 2.0 is current. |
| **Atomic write** | A save that either fully completes or leaves the old file untouched — never something in between. |
| **Transaction** | A change that is fully applied or fully discarded; no partial states. |
| **Defensive copy** | A hand-out copy of data, so the original can't be changed by the receiver. |
| **Debounce** | Waiting for a pause in activity before acting once. |
| **Reference** | A pointer from one thing to another ("this door belongs to wall 42"). |
| **fsync / flush** | Forcing data physically onto the disk instead of letting it linger in memory. |

**Next:** [AI layout generation](ai-layout-generation.md) or [Operations and troubleshooting](operations-and-troubleshooting.md).
