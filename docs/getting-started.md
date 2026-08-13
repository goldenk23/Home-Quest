# Getting started

This page takes you from a fresh download to a running app. Each step says what to type **and why**, so you can follow along even if some terms are new to you.

## 1. What you need first

| Requirement | Why | Do I already have it? |
|---|---|---|
| **Windows** | The launcher and the 3D window use Windows-only technology. | You're on it or you're not. |
| **Python 3.11+** from [python.org](https://www.python.org/) | The app is written in Python. | Run `python --version` in PowerShell to check. |
| **Tkinter** | The part of Python that draws windows and buttons. It comes with the standard python.org installer — there is nothing extra to install. | Comes with Python above. |
| **Microsoft Edge WebView2 Runtime** | A small Microsoft browser component the app borrows to display 3D. | Most Windows 10/11 PCs already have it. If 3D fails later, install "WebView2 Evergreen Runtime" from Microsoft's site. |
| **Google Cloud account + `gcloud` CLI** | Only for the optional AI features. | Only needed for section 3. |

You do **not** need Node.js, and you must not start any web server — the app is fully self-contained.

## 2. Install the app

Open PowerShell in the repository root (the `Home Quest` folder) and run:

```powershell
Set-Location ".\2D_layout\2dlayoutMaker-main"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location "..\.."
```

What this does, line by line:

1. Moves into the application folder.
2. Creates a **virtual environment** — a private copy of Python inside a `.venv` folder, so this app's libraries never clash with anything else on your PC.
3. Updates `pip`, Python's package installer.
4. Installs the exact library versions listed in `requirements.txt`.
5. Returns to where you started.

The `.venv` folder is ignored by Git, so it will never be committed.

## 3. Turn on AI (optional — skip if unsure)

The app works completely without this step. Only the "generate a plan from a description" feature needs it.

```powershell
Copy-Item ".env.example" ".env"
gcloud auth application-default login
```

- The first command makes your own private copy of the settings template.
- The second opens a Google sign-in that lets the app call Google's AI **as you** (this is called *Application Default Credentials*, or ADC — Google's way of proving "this computer is allowed to use my account").

Now edit the new `.env` file and replace `your-google-cloud-project` with your real project name.

Rules that keep you safe:

- **Never commit or share `.env`.** It points at your billing account.
- Real AI calls use your Google quota and can cost money.
- Without working credentials, only AI generation fails — drawing, saving, and 3D all still work.

## 4. Launch the app

From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\2D_layout\run-2d-editor.ps1"
```

The launcher finds the private `.venv` Python, starts the app from the correct folder, and passes back the app's exit code. (The same command is saved in `2D_layout/01_run.txt` for easy copying.)

Always start the app this way — launching `app.pyw` directly can pick the wrong Python or the wrong working folder.

## 5. Check that everything works

Five minutes now saves confusion later:

1. The editor opens with a canvas, toolbar, and sidebar.
2. Draw a room, move it, resize it. Undo and redo work. Shapes snap neatly to the grid.
3. Save a small `.json` project, reopen it, and confirm it looks identical.
4. Open **3D View**, then **Split** — both must show your current plan.
5. Close and reopen the app, then look inside `%LOCALAPPDATA%\VastuApp\saved_layouts` — you should see autosave data.
6. If you set up AI: generate a small single-floor plan and inspect it **before** saving it.

## 6. Folders worth knowing

| What | Where |
|---|---|
| The application | `2D_layout/2dlayoutMaker-main/` |
| The ready-made 3D program | `2D_layout/2dlayoutMaker-main/viewer_dist/` |
| Models, textures, symbols | `2D_layout/2dlayoutMaker-main/assets/` |
| Your autosaves | `%LOCALAPPDATA%\VastuApp\saved_layouts\autosave.json` |
| Your rolling backups | `%LOCALAPPDATA%\VastuApp\saved_layouts\backups\` |
| AI-generated layout storage | `%LOCALAPPDATA%\VastuApp\generated_layouts\` |
| Crash log (when running from source) | `2D_layout/2dlayoutMaker-main/crash.log` |

> `%LOCALAPPDATA%` is a standard Windows folder for app data. Paste it into File Explorer's address bar and Windows takes you there. Everything under `VastuApp` is **your data** — back it up, never delete it as cleanup.

**Next:** read [Architecture](architecture.md) to see how the app works inside, or [Testing](testing.md) to run the checks.
