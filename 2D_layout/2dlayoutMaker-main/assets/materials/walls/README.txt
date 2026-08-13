GLB Wall Finishes
=================

ZERO-CONFIG
-----------
Drop any .glb file into this folder (public/walls/) and restart the dev
server (or just save any file to trigger HMR). Every wall in the app
switches to the textures from that GLB automatically.

- Any filename works — no renaming required.
- If multiple .glb files are present, the first one (alphabetical) is used
  as the default wall finish.
- Remove the file and restart to go back to the built-in brick look.

How it works
------------
The Vite plugin (wallsManifestPlugin in vite.config.ts) scans this folder
on startup and whenever a .glb is added/removed, writing manifest.json here.
On first render the app fetches that manifest, picks the first GLB, extracts
its PBR texture maps (albedo, normal, roughness, metalness) and applies them
to every wall. Walls show the brick fallback while the file loads.

Requirements for the GLB
--------------------------
- Must contain at least one Mesh with a MeshStandardMaterial (standard PBR).
- Non-Draco compressed (add DRACOLoader to applyGlbTextures in
  src/domains/viewer/services/materials.ts if your file uses Draco).
- Polygon count doesn't matter — only the material textures are used.

ADDING NAMED PALETTE FINISHES (optional)
-----------------------------------------
To expose a GLB finish in the Paint tool so it can be applied per-wall:

  1. Add an entry to WALL_FINISHES in:
       src/domains/shared/materials/finishPalette.ts
     Example:
       { id: 'wall-my-finish', name: 'My Finish', category: 'wall',
         swatch: '#hex', color: '#hex', glbPath: '/walls/my-finish.glb',
         roughness: 0.8 }

  2. Drop my-finish.glb here.
