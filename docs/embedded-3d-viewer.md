# Embedded 3D viewer

This page explains how the 3D view works, what files it needs, and one important limitation: **the 3D program can be used and shipped, but not rebuilt or modified from this repository.**

## What the 3D view actually is

When you click **3D View** or **Split**, the app does not start any external program or website. Instead:

1. The app starts a tiny, private file server that only your own computer can reach (a *loopback* server on `127.0.0.1`, on a random free port). It serves the ready-made 3D program from the `viewer_dist/` folder, plus the models and textures from `assets/`.
2. The app opens a small built-in browser window (**WebView2** — a Microsoft Edge component that desktop apps can embed) pointed at that private server.
3. The 3D program loads, says "ready", and the app hands it your current project to draw.

Safety details, in plain terms:

- **Nothing is exposed to the network.** `127.0.0.1` means "this machine only."
- **The server is read-only.** It refuses anything except fetching files, and shows no directory listings.
- **The viewer can only look, not touch.** It receives a copy of your project; it cannot change it.
- Browser extras (DevTools, right-click menus) are disabled to keep the experience app-like.

The viewer starts **lazily** — it sleeps until you first open a 3D mode — and pauses when you return to **Plan**.

## How the app and the viewer talk

They exchange short JSON messages. Only five exist:

| From | Message | Meaning |
|---|---|---|
| Viewer → app | `ready` | "I've loaded — send me the current project." |
| Viewer → app | `refresh-request` | "Please send the current project again." |
| App → viewer | `load-layout` | "Here is the project." Carries a `requestId` that increases every time, so the viewer can ignore out-of-order deliveries. |
| App → viewer | `host-error` | "Something went wrong on the app's side." |
| App → viewer | `deactivate` | "We're back in Plan mode — pause rendering." |

The app keeps the newest project message and re-sends it whenever the viewer says `ready`. There is currently **no version negotiation** — both sides simply assume they speak the same protocol, which is true as long as neither side is changed alone.

## Files the viewer needs (do not reorganize)

- `2D_layout/2dlayoutMaker-main/viewer_dist/` — the 3D program itself. `index.html` inside it is the "is the viewer present?" check.
- `2D_layout/2dlayoutMaker-main/assets/` — models, textures, materials. 3D models find their textures by **relative paths**, so moving or renaming subfolders breaks them even if every file still exists.
- The hashed JS/CSS files inside `viewer_dist/assets/` — their names are part of how the program loads itself. Never rename or partially regenerate them.
- `finish_manifest.json` — a catalog of stable finish (material) identifiers kept for compatibility. Don't assume the running app reloads it dynamically without checking the code path first.

Three Python packages are pinned to exact versions because they form a tested combination:

```text
tkwebview2==3.5.0
pywebview==5.4
pythonnet==3.0.5
```

`embedded_viewer.py` checks these versions and refuses to run with a mismatched pair — that guard is there to fail loudly instead of mysteriously. Windows also needs the **Microsoft Edge WebView2 Evergreen Runtime** installed (most PCs have it).

## Release checks for the 3D view

Before shipping, confirm by hand (automated tests don't cover the browser lifecycle):

1. `viewer_dist/index.html`, the hashed bundle files, and the full `assets/` tree are present.
2. The pinned package versions install; WebView2 is detected.
3. **Plan → 3D View → Split → Plan** all work with a saved multi-floor project containing openings, furniture, finishes, and structures.
4. Editing the plan refreshes the 3D view.
5. The **Retry 3D Viewer** button recovers from a deliberately caused failure.

## Words used on this page

| Term | Plain meaning |
|---|---|
| **WebView2** | Microsoft's embeddable Edge browser for desktop apps. |
| **Loopback / 127.0.0.1** | A network address that only ever means "this same computer." |
| **Ephemeral port** | A random free port number picked at runtime, instead of a fixed one. |
| **Compiled/minified bundle** | Frontend code after a build step compresses it for shipping — functional but not meant to be edited by hand. |
| **Protocol** | The agreed list of messages two programs exchange. |
| **STA thread** | A specific Windows thread flavor that WebView2 requires for browser setup. Handled inside the app; you don't need to manage it. |

**Next:** [Testing](testing.md) for the full checklist, or [Operations and troubleshooting](operations-and-troubleshooting.md) if 3D fails.
