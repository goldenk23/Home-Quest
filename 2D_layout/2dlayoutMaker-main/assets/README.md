# Application assets

All reusable visual assets are centralized here:

- `furniture-2d/`: viewer-ready 2D furniture; `editor/` preserves the original Tkinter images.
- `models-3d/`: glTF/GLB furniture, geometry binaries, and model textures.
- `flooring/`: viewer-ready flooring; `editor/` preserves the original editor files.
- `materials/walls/`: wall/floor material packages and their manifest.
- `materials/grass/`: ground PBR textures.
- `materials/asphalt/`: road PBR textures.
- `branding/`: application/viewer icons; `editor/` preserves the original branding files.

Do not flatten model or wall package subdirectories: their `.gltf` files use relative paths to adjacent `.bin` and texture files. The compiled viewer still requests legacy URLs such as `/models/` and `/walls/`; `embedded_viewer.py` safely maps those URLs to this tree.