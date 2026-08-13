# VastuCraft desktop application

This folder **is** the app — the Python/Tkinter floor-plan editor you install and run.

New here? Read the [project overview](../../README.md) first, then the [guides in docs/](../../docs/README.md). This page only keeps the commands and facts that are specific to this folder.

## What you need

- Windows with **Python 3.11+** (the standard python.org installer, which already includes Tkinter)
- **Microsoft Edge WebView2 Runtime** for the 3D view (most Windows PCs already have it)
- Google Cloud sign-in (`gcloud`) — only if you want the optional AI features

## Install

From this folder, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This creates a private Python environment (`.venv`) and installs the exact libraries the app needs. For AI: copy the repository-root `.env.example` to `.env`, set your Google Cloud project in it, and run `gcloud auth application-default login`. Never commit or overwrite the real `.env`.

## Run

Always use the launcher from the repository root — it guarantees the right Python and the right working folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\2D_layout\run-2d-editor.ps1"
```

Two folders here are **runtime material — hands off**:

- `viewer_dist/` — the ready-made, compiled 3D program. Its editable source is not in this repository, so treat it as sealed.
- `assets/` — all 3D models, textures, materials, and symbols. Their folder structure is load-bearing: models find their textures by relative paths.

No Node.js, no web server — the app serves everything locally by itself.

## Check your changes

From this folder:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m py_compile app.pyw embedded_viewer.py layout_serializer.py generate_layout\service.py generate_layout\ai_client.py
.\.venv\Scripts\python.exe generate_layout\geometry_autofix.py
.\.venv\Scripts\python.exe generate_layout\ai_validator.py
```

All offline — no Google account needed. Note that tests needing a real screen quietly skip on display-less machines, so read the skip lines. Before a release, also walk the manual **Plan → 3D View → Split** checklist in [docs/testing.md](../../docs/testing.md). Real AI calls are deliberately excluded from the suite (they need network, credentials, and money).

## Your data

Autosaves and rolling backups live under `%LOCALAPPDATA%\VastuApp\saved_layouts`; AI-generated layouts under `%LOCALAPPDATA%\VastuApp\generated_layouts`. That is **your data, not app code** — back it up, never delete it as cleanup. Details: [Data model and persistence](../../docs/data-model-and-persistence.md) and [Operations](../../docs/operations-and-troubleshooting.md).
