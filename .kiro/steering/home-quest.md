# Home Quest project context

Home Quest integrates a Python/Tkinter 2D floor-plan editor with an existing React/TypeScript 2D editor and React Three Fiber 3D renderer.

## Integration flow

1. The Python editor saves native VastuCraft JSON (`version: "1.0"`) through `2D_layout/2dlayoutMaker-main/layout_serializer.py`.
2. The web UI imports that native file from `src/app/SandboxView.tsx`.
3. `src/store/persistence/importVastu.ts` validates and converts it into Home Quest entities measured in centimeters.
4. Zustand stores the converted active-floor geometry.
5. The existing `SceneContent`/`FloorScene` pipeline renders the same entities in 3D. Do not create a second renderer or an intermediate `.hq.json` converter.

## Important conventions

- Python coordinates are canvas pixels with Y down; Home Quest uses centimeters with plan Y up.
- Conversion includes `unit`, `unit_scale`, `grid_spacing`, and `zoom_level`, then normalizes the canvas offset.
- Python native JSON and Home Quest `.hq.json` are different formats. Never pass an `.hq.json` file to the Python-layout importer.
- Unknown furniture is skipped and reported; never silently substitute another object.
- Import validation must finish before replacing store state. Existing plans are backed up and require confirmation.
- Keep changes minimal and reuse the existing entity/store/rendering architecture.

## Key commands (Windows)

- Web tests: `npm run test:run`
- Production build: `npm run build`
- Targeted lint: `npx eslint <files>`
- Python syntax: `python -m py_compile layout_serializer.py generate_layout\service.py`
- Launch Python editor: see `2D_layout/01_run.txt`.

Before continuing integration work, read `docs/2d-3d-integration-handoff.md` and inspect the current Git diff. The worktree contains substantial uncommitted user work; do not revert unrelated files.


## Automatically loaded handoff

The detailed implementation handoff below is project memory for new chats. Treat code and Git diff as authoritative if it becomes stale.

#[[file:../../docs/2d-3d-integration-handoff.md]]