# Operations and troubleshooting

This page is for when something goes wrong — or when you want to make sure nothing *can* go wrong with your saved work. Start with the first section; it is the one that protects your data.

## 1. Protect your data first

Your saved work does **not** live in the project folder. It lives here:

```text
%LOCALAPPDATA%\VastuApp\
├─ saved_layouts\
│  ├─ autosave.json        ← the latest autosave
│  └─ backups\             ← up to 10 older, timestamped copies
└─ generated_layouts\      ← timestamped AI-generated layouts
```

(Paste `%LOCALAPPDATA%` into File Explorer's address bar to get there.)

Rules that keep you safe:

- **Before upgrades or deep debugging, copy that whole folder somewhere safe.** It is irreplaceable user data, not disposable cache. Never delete it during "cleanup".
- Files you saved yourself with **Save As** live wherever you put them — back those up separately.
- Autosave fires **2 seconds after you stop editing**. After an important edit, either pause a moment or just press **Save** — an explicit save is always the strongest guarantee.

**If you need to recover work after a crash, try in this order:**

1. Your last manually saved file.
2. `saved_layouts\autosave.json`
3. Files in `saved_layouts\backups\`, newest first.

And always **copy** a recovery file to a safe place *before* opening or editing it, so a failed attempt can't damage your last copy.

## 2. The app won't start

Work down this list:

1. Launch from the repository root with `2D_layout/run-2d-editor.ps1` and read the error it prints — it usually names the problem.
2. Confirm both of these exist: `2D_layout\2dlayoutMaker-main\.venv\Scripts\python.exe` and `2D_layout\2dlayoutMaker-main\app.pyw`. If the first is missing, redo the install steps in [Getting started](getting-started.md).
3. Reinstall the libraries with the app's own Python:
   ```powershell
   .\2D_layout\2dlayoutMaker-main\.venv\Scripts\python.exe -m pip install -r .\2D_layout\2dlayoutMaker-main\requirements.txt
   ```
4. Run the automated checks in [Testing](testing.md).
5. Open `2D_layout\2dlayoutMaker-main\crash.log` — if the app died during startup, the Python error is usually in there.

(One quirk: the crash log is written next to the source code. If the app were run from a read-only location, writing the log could silently fail — the app swallows that logging error on purpose so it never hides the real startup error.)

## 3. 3D View or Split doesn't work

Try these in order:

- **Check the files exist:** `viewer_dist\index.html`, the hashed files in `viewer_dist\assets\`, and the full `assets\` tree inside `2D_layout\2dlayoutMaker-main\`. Do not substitute any other `dist/` folder, and do not start a Node server — the app doesn't use one.
- **Install or repair the Microsoft Edge WebView2 Evergreen Runtime** (from Microsoft's website).
- **Reinstall the exact pinned viewer packages** from `requirements.txt` (see the command in section 2). The app checks these versions on purpose — do not remove that version guard to "fix" a mismatch; upgrade the packages and the viewer together instead.
- Click **Retry 3D Viewer** after fixing the cause.
- If the 3D window's render process died: switch back to **Plan**, open 3D again, and check `crash.log`.
- If 3D opens but shows an old version of your plan: make any small edit (or reopen the 3D view) to trigger a refresh — the viewer can also ask for fresh data itself.

## 4. AI generation fails

1. Confirm the repository-root `.env` has your real project, location, and a supported model — and that you never shared or committed it.
2. Re-run `gcloud auth application-default login` for the Windows user you're logged in as.
3. In Google Cloud, check: Vertex AI API enabled, your permissions (IAM), billing active, quota available, and the model available in your chosen location.
4. Check `.env` spelling: planner must be exactly `comb` or `multi`; timeouts within their allowed ranges (see [AI layout generation](ai-layout-generation.md)).
5. Simplify the brief: remove contradictions, state plot dimensions/facing/floor count/rooms clearly.
6. Read the validation messages the app shows and fix what they point at. Never bypass the checkers to force a plan through.

Remember: even cancelled or timed-out requests may have consumed some quota on Google's side, and the default model is a preview that Google can change. A real AI smoke test costs a (small) amount of money — use an approved test project.

## 5. Saving or loading fails

- Only `.json`, `.yaml`, and `.yml` files are supported.
- **Keep the failing file** — don't overwrite it. The validation error names the exact path to the problem inside the file (e.g., which floor, which wall). Fix the file or migrate it properly; do not weaken `layout_schema.py` to make the error go away.
- Loading is transactional: a failed load should leave your previous project, canvas, and undo history untouched. If you ever see a failed load *damage* the current project, preserve `crash.log` and the file involved — that's a data-loss defect, treat it seriously.

## 6. Repository and release hygiene

- Never stage in Git: `.env`, `.venv`, `crash.log`, `__pycache__`, or anything from `%LOCALAPPDATA%\VastuApp`.
- Always preserve: `docs/prompt.txt`, the complete `viewer_dist/` folder, and the complete `assets/` tree.
- Do not resurrect the old removed React/Node development setup as an app dependency.
- Before committing: `git status --short` and `git diff --check` — stage only what you meant to change.
- Cut releases from a clean checkout and walk the manual checklist in [Testing](testing.md).

---

Background reading: [Architecture](architecture.md) for how the parts fit together, [Data model and persistence](data-model-and-persistence.md) for exactly how saving and recovery behave.
