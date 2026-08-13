# VastuCraft documentation

These guides explain the VastuCraft desktop app — what it does, how it is built, and how to work on it safely. They are written so that no prior knowledge of the project (or of the technical terms) is needed; every unusual term is explained where it first appears.

## Which guide should I read?

**If you just want to install and use the app:**
1. [Getting started](getting-started.md)
2. [Operations and troubleshooting](operations-and-troubleshooting.md) — only when something goes wrong

**If you want to understand how the app works inside:**
1. [Architecture](architecture.md) — the big picture
2. [Data model and persistence](data-model-and-persistence.md) — how projects are stored and saved
3. [AI layout generation](ai-layout-generation.md) — how the optional AI drafting works
4. [Embedded 3D viewer](embedded-3d-viewer.md) — how the 3D view works

**If you want to change the code:**
1. [Developer guide](developer-guide.md) — the rules and the code map
2. [Testing](testing.md) — how to check your change

## The guides in reading order

1. [Getting started](getting-started.md) — install, launch, and check that everything works.
2. [Architecture](architecture.md) — the parts of the app and how they talk to each other.
3. [Developer guide](developer-guide.md) — where each behavior lives in the code, and the rules you must not break.
4. [Data model and persistence](data-model-and-persistence.md) — the project file format, saving, autosave, and recovery.
5. [AI layout generation](ai-layout-generation.md) — the AI pipeline, its settings, limits, and costs.
6. [Embedded 3D viewer](embedded-3d-viewer.md) — the built-in 3D window, its assets, and why it cannot be rebuilt here.
7. [Testing](testing.md) — automated checks, what they do not cover, and the manual release checklist.
8. [Operations and troubleshooting](operations-and-troubleshooting.md) — protecting your data and fixing common problems.

## Where the real answers live

When documentation and code ever disagree, the code wins:

- The running app: `2D_layout/2dlayoutMaker-main/`
- The strict project format: `layout_schema.py` (inside that folder)
- Python libraries needed: `requirements.txt`
- AI settings template: `.env.example` (repository root)
- The launcher: `2D_layout/run-2d-editor.ps1`
- The ready-made 3D program: `2D_layout/2dlayoutMaker-main/viewer_dist/`
- Models, textures, and symbols: `2D_layout/2dlayoutMaker-main/assets/`

Two things must never be committed to Git or copied into docs: your real `.env` file, and anything under `%LOCALAPPDATA%\VastuApp` (that folder is the user's saved work, not app code).

## The preserved prompt collection

[`prompt.txt`](prompt.txt) is a kept-as-is collection of example house descriptions used to try out the AI generator. Some examples contradict each other on purpose. Treat them as test inputs, never as design requirements or as proof of architectural, structural, legal, or Vastu correctness.

## A note on names

The project has been called several things over its life — Home Quest, VastuCraft, VastuCraft Pro, MiniAutoCAD, VastuApp — and old names still appear in some code and window titles. These docs use **VastuCraft** everywhere. One name is frozen on purpose: the data folder `%LOCALAPPDATA%\VastuApp` stays as it is, because renaming it would orphan existing users' saved work.
