# Home Quest — Architecture

Client-side only. No backend. Everything runs in the browser.
Diagram renders in GitHub / VS Code Mermaid preview — **click it to zoom & pan.**

```mermaid
flowchart TD
    User([User])

    %% ---------- INPUT ----------
    User --> Toolbar[Toolbar: pick tool]
    User --> Canvas2D
    User --> Canvas3D

    %% ---------- 2D EDITOR ----------
    subgraph EDITOR["2D Editor"]
        Canvas2D[EditorCanvas]
        Layers["Layers: Wall, Room, Furniture, Pillar,<br/>Beam, Deck, Railing, Road, Opening,<br/>Stair, Dimension, Grid, Compass"]
        Tools["Tools: useWallDrawing, useStairTool,<br/>useArrayTool, useRoadDrawing, paint"]
        Canvas2D --> Layers
        Canvas2D --> Tools
    end

    %% ---------- STORE ----------
    Store[("ZUSTAND STORE<br/>vertices · walls · rooms · furniture<br/>openings · pillars · beams · deckSlabs<br/>railings · roads · stairs<br/>+ floorsSlice (multi-storey)")]

    Toolbar -->|set active tool| Store
    Tools -->|addWall, addPillar,<br/>addFurniture, paint...| Store

    %% ---------- REACTIVE LOGIC ----------
    subgraph LOGIC["Reactive Hooks + Services"]
        Rooms[useRoomDetection<br/>→ roomDetection.ts]
        Vastu[useVastuAnalysis<br/>→ scoring.ts]
        Extrude[extrusion.ts + transform.ts]
    end

    Store -->|walls change| Rooms -->|write rooms| Store
    Store -->|rooms change| Vastu -->|write score| Store
    Store --> Extrude --> Canvas3D

    %% ---------- 3D VIEWER ----------
    subgraph VIEWER["3D Viewer (R3F)"]
        Canvas3D[ViewerCanvas]
        Meshes["Meshes: Wall, Floor, Stair, Pillar,<br/>Beam, Railing, Road, DeckSlab, FurnitureModel"]
        Canvas3D --> Meshes
    end

    %% ---------- OUTPUT PANELS ----------
    Store --> Canvas2D
    Store --> VastuPanel[VastuPanel: score + tips]

    %% ---------- MATERIALS ----------
    Mats["Materials / Paint<br/>finishPalette.ts · materials.ts"]
    Mats --> Meshes
    Mats --> Layers

    %% ---------- ASSETS ----------
    subgraph ASSETS["Assets (static files)"]
        Models["public/models/*.gltf<br/>(furniture)"]
        Walls["public/walls/*.gltf + manifest.json<br/>(wall styles)"]
    end
    Loader["useAssetLoader · useGlbWallDiscovery<br/>useGLTF · modelPrep.ts"]
    Models --> Loader
    Walls --> Loader
    Loader --> Meshes

    %% ---------- PERSISTENCE ----------
    Store <-->|auto save / load| IDB[("IndexedDB<br/>saved plan")]
    Store --> FileIO["fileIO.ts (import/export)<br/>imageExport.ts (PNG/PDF)"]
```

**Rule:** components never talk to each other directly. They all read/write the **Store**. Data flows one way: UI action → Store → logic reacts → Store → UI re-renders. Assets are static files under `public/`, loaded on demand into the 3D meshes. IndexedDB is the only persistence.
