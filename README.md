# VastuCraft

**Draw house floor plans on Windows — by hand or with AI — and see them in 3D.**

VastuCraft is a desktop app for designing home layouts. You can:

- **Draw plans yourself** — rooms, walls, doors, windows, furniture, stairs, and more, on as many floors as you need.
- **Ask AI to draft a plan** (optional) — type a plain-English wish list like *"3-bedroom house, kitchen in the south-east"*, and the app turns it into an editable floor plan.
- **Walk through it in 3D** — switch between a 2D plan view, a 3D view, or both side by side.
- **Check Vastu** — the app includes tools based on Vastu Shastra, a traditional Indian system for deciding where rooms should sit and face.

Everything runs on your own computer. There is no server to start, no website to open, and no account to create. The AI part is optional — the app works fully without it.

> [!NOTE]
> **The actual app lives in [`2D_layout/2dlayoutMaker-main/`](2D_layout/2dlayoutMaker-main/).** That is the folder you install from and run.

## Table of contents

- [How it works, in plain words](#how-it-works-in-plain-words)
- [Quick start](#quick-start)
- [Setting up AI (optional)](#setting-up-ai-optional)
- [Running the tests](#running-the-tests)
- [Where things live](#where-things-live)
- [Honest limitations](#honest-limitations)
- [Documentation](#documentation)

## How it works, in plain words

You do not need to read this section to use the app, but it explains the three ideas the whole project is built on.

### 1. One official copy of your plan

Inside the app there is exactly **one official version of your project**, kept in a strict, checked format (called the *schema* — think of it as a form with fixed fields that every room, wall, and door must fit into). Everything in the app — the drawing canvas, the save button, the autosave, the AI, and the 3D view — reads from and writes to that one official copy.

Why it matters: nothing can quietly disagree. The plan you draw is the plan that gets saved, and the plan that gets saved is the plan you see in 3D.

### 2. AI proposes, the app decides

When you ask AI to design a layout, the AI is **not allowed to draw directly**. It only describes what it thinks you want (a list of rooms, sizes, and positions). Then the app's own code:

1. draws the actual geometry,
2. fixes shapes that came out wrong,
3. checks the result against strict rules, and
4. only then shows it to you as a normal, editable plan.

Why it matters: AI can misunderstand or produce impossible geometry. Because the app checks everything before accepting it, a bad AI answer is rejected instead of corrupting your project.

### 3. Saving is careful

Saves are written so a crash can never leave you with a half-written, unreadable file. The app also autosaves for you in the background and keeps the last 10 backups on your computer.

Why it matters: your work is hard to lose. (Still, pressing **Save** after important work is the safest habit — see [Honest limitations](#honest-limitations).)

## Quick start

### You need

- **Windows**
- **Python 3.11 or newer** from [python.org](https://www.python.org/) (the standard installer — it already includes Tkinter, the piece Python uses to draw windows and buttons)
- **Microsoft Edge WebView2 Runtime** for the 3D view (most Windows 10/11 machines already have it)
- A **Google Cloud** project — *only if* you want the optional AI features

You do **not** need Node.js or any web server.

### Install

Open PowerShell in this folder and run:

```powershell
Set-Location ".\2D_layout\2dlayoutMaker-main"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location "..\.."
```

This creates a private Python environment for the app (a `.venv` folder) so its libraries never mix with the rest of your system.

### Run

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\2D_layout\run-2d-editor.ps1"
```

### Try these first

1. Draw a room, drag it, resize it, then undo and redo.
2. Save the project as a `.json` file, close it, and reopen it — it should look identical.
3. Switch to **3D View**, then **Split**. Your plan should appear in 3D.
4. Wait two seconds after an edit, then look in `%LOCALAPPDATA%\VastuApp\saved_layouts` — that is where the app quietly autosaves your work.

## Setting up AI (optional)

Skip this section if you only want to draw by hand — everything else works without it.

```powershell
Copy-Item ".env.example" ".env"
gcloud auth application-default login
```

Then open the new `.env` file and replace `your-google-cloud-project` with your real Google Cloud project name. The `gcloud` command signs your computer in so the app is allowed to call Google's AI on your behalf.

Settings you can change in `.env`:

| Setting | What it controls | Default |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Your Google Cloud project. **You must set this.** | *(none)* |
| `GOOGLE_CLOUD_LOCATION` | Which Google region serves the AI | `global` |
| `AI_LAYOUT_MODEL` | Which AI model is used | `gemini-3.1-pro-preview` |
| `AI_LAYOUT_MAX_TOKENS` | Maximum size of one AI answer | `32000` |
| `AI_LAYOUT_TIMEOUT_MS` | How long to wait for one AI reply (milliseconds) | `120000` |
| `AI_LAYOUT_OPERATION_TIMEOUT_MS` | How long a whole generation may take | `300000` |
| `AI_LAYOUT_PLANNER` | Which built-in layout planner draws the rooms (`comb` or `multi`) | `comb` |
| `AI_LAYOUT_SEED` | Starting value that makes results more repeatable | `0` |

> [!WARNING]
> Never share or commit your `.env` file or Google credentials. Real AI calls use your Google quota and can cost money.

## Running the tests

From `2D_layout\2dlayoutMaker-main`:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

All tests run offline — no Google account or internet needed. Details and the full release checklist: [docs/testing.md](docs/testing.md).

## Where things live

```text
Home Quest/
├─ README.md                      ← you are here
├─ .env.example                   ← template for AI settings (copy to .env)
├─ docs/                          ← all the guides (start with docs/README.md)
└─ 2D_layout/
   ├─ run-2d-editor.ps1           ← the launcher you run
   └─ 2dlayoutMaker-main/         ← the actual application
      ├─ app.pyw                  ← the program's starting point
      ├─ layout_schema.py         ← the strict "shape" every project must follow
      ├─ project_state.py         ← the keeper of the one official project copy
      ├─ layout_serializer.py     ← translates between the canvas and the official copy
      ├─ local_autosave.py        ← background autosave + rolling backups
      ├─ embedded_viewer.py       ← the built-in 3D window
      ├─ generate_layout/         ← everything AI-related
      ├─ tests/                   ← the offline test suite
      ├─ viewer_dist/             ← the ready-made 3D program (do not modify)
      └─ assets/                  ← 3D models, textures, symbols
```

Your personal data (autosaves, backups) lives outside this folder, under
`%LOCALAPPDATA%\VastuApp`. That is real user data — never delete it as "cleanup".

## Honest limitations

Every project has boundaries. These are VastuCraft's:

- **Windows only.** The launcher and the built-in 3D window use Windows-specific technology.
- **This is not an architect.** The app's checks and Vastu scoring are helpful heuristics, not building-code, structural, or legal certification. Have real designs reviewed by a licensed professional.
- **AI needs your own Google Cloud setup**, and its availability, speed, and cost are controlled by Google, not by this app.
- **AI-made multi-floor plans are stacked independently.** The app does not yet line up stairs between floors automatically — review and connect them yourself.
- **Autosave waits 2 seconds after your last edit.** If the app closes inside that window, the very last edit may only exist in your explicit save. Press **Save** after important work.
- **The 3D viewer ships as a finished, compiled bundle.** Its editable source code is not in this repository, so the 3D side can be used and packaged but not easily modified.

## Documentation

| Guide | Read it when… |
|---|---|
| [Documentation index](docs/README.md) | You want the recommended reading order. |
| [Getting started](docs/getting-started.md) | You are installing for the first time. |
| [Architecture](docs/architecture.md) | You want to understand how the app is built inside. |
| [Developer guide](docs/developer-guide.md) | You want to change the code safely. |
| [Data model and persistence](docs/data-model-and-persistence.md) | You want to know how projects are stored, saved, and recovered. |
| [AI layout generation](docs/ai-layout-generation.md) | You want to understand or configure the AI features. |
| [Embedded 3D viewer](docs/embedded-3d-viewer.md) | You want to understand the 3D view and its limits. |
| [Testing](docs/testing.md) | You want to run checks before a change or release. |
| [Operations and troubleshooting](docs/operations-and-troubleshooting.md) | Something broke, or you want to protect your data. |

---

**Project boundary:** VastuCraft is an engineering/portfolio project. Always review generated designs and save important work explicitly; do not use its output as a substitute for a licensed architect, structural engineer, or local authority approval.
