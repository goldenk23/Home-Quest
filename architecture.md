# Home Quest — Architecture Diagram

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI Framework** | React 18 + TypeScript | Component-based UI |
| **Build Tool** | Vite 5 | Dev server, HMR, bundling |
| **3D Rendering** | Three.js + React Three Fiber + Drei | WebGL 3D visualization |
| **State Management** | Zustand + Immer | Reactive store with immutable updates |
| **Styling** | Tailwind CSS | Utility-first CSS |
| **UI Primitives** | Radix UI | Accessible headless components |
| **2D Editor** | SVG (native React JSX) | Floor plan drawing canvas |
| **Persistence** | IndexedDB (idb-keyval) | Client-side storage |
| **Testing** | Vitest + Testing Library | Unit/integration tests |
| **Monitoring** | Sentry | Error tracking & performance |
| **Deployment** | Vercel | Static hosting + CDN |
| **ID Generation** | nanoid | Unique entity IDs |
| **Assets** | GLTF/GLB + KTX2 + Draco | 3D models & compressed textures |

---

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              APPLICATION SHELL                               │
│                         (App.tsx + Error Boundaries)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐   │
│  │   2D EDITOR      │  │   3D VIEWER      │  │   VASTU ENGINE          │   │
│  │   Domain         │  │   Domain         │  │   Domain                │   │
│  │                  │  │                  │  │                         │   │
│  │  • SVG Canvas    │  │  • R3F Canvas    │  │  • Brahmasthan Calc     │   │
│  │  • Pan/Zoom      │  │  • Wall Meshes   │  │  • Zone Projection      │   │
│  │  • Wall Drawing  │  │  • Floor Meshes  │  │  • Scoring Engine       │   │
│  │  • Snapping      │  │  • Furniture     │  │  • 2D/3D Overlays       │   │
│  │  • Room Detect   │  │  • Lighting      │  │  • Recommendations      │   │
│  │  • Collision     │  │  • Camera (Orbit │  │                         │   │
│  │  • Selection     │  │    + First Person)│  │                         │   │
│  └────────┬─────────┘  └────────┬─────────┘  └────────────┬────────────┘   │
│           │                     │                          │                │
├───────────┴─────────────────────┴──────────────────────────┴────────────────┤
│                          ZUSTAND STORE (Single Source of Truth)              │
│                                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────┐ ┌────────┐ ┌───────────┐  │
│  │ editorSlice │ │ viewerSlice │ │ vastuSlice │ │uiSlice │ │historySlice│  │
│  │             │ │             │ │            │ │        │ │           │  │
│  │ vertices{}  │ │ cameraMode  │ │ scores{}   │ │ tool   │ │ undo stack│  │
│  │ walls{}     │ │ renderQual  │ │ recs[]     │ │ panels │ │ redo stack│  │
│  │ rooms{}     │ │ overlays    │ │ activeZone │ │ select │ │ commands  │  │
│  │ furniture{} │ │             │ │            │ │        │ │           │  │
│  └─────────────┘ └─────────────┘ └────────────┘ └────────┘ └───────────┘  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                         DOMAIN SERVICES (Pure Functions)                     │
│                                                                             │
│  ┌────────────────────┐  ┌─────────────────────┐  ┌──────────────────────┐ │
│  │ Geometry Services   │  │ Transform Services  │  │ Analysis Services    │ │
│  │                    │  │                     │  │                      │ │
│  │ • screenToWorld    │  │ • planTo3D          │  │ • calculateBrahma.   │ │
│  │ • wallQuad         │  │ • threeDToPlan      │  │ • getZoneForPoint    │ │
│  │ • snapToGrid       │  │ • polygonToShape    │  │ • computeVastuScore  │ │
│  │ • findIntersect.   │  │ • createWallGeo     │  │ • getRoomDirection   │ │
│  │ • detectRooms      │  │ • getMaterial       │  │ • isAngleInSector    │ │
│  │ • obbIntersects    │  │                     │  │                      │ │
│  │ • spatialHash      │  │                     │  │                      │ │
│  └────────────────────┘  └─────────────────────┘  └──────────────────────┘ │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                         INFRASTRUCTURE LAYER                                │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │ Persistence  │  │ Error System │  │ Event Bus   │  │ Monitoring     │  │
│  │              │  │              │  │             │  │                │  │
│  │ • IndexedDB  │  │ • AppError   │  │ • pub/sub   │  │ • Sentry       │  │
│  │ • Migrations │  │ • Boundaries │  │ • cross-    │  │ • Performance  │  │
│  │ • Export/    │  │ • Fallback   │  │   domain    │  │   marks        │  │
│  │   Import     │  │   UIs        │  │   comms     │  │                │  │
│  │ • Validation │  │ • Safe ops   │  │             │  │                │  │
│  └──────────────┘  └──────────────┘  └─────────────┘  └────────────────┘  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                         ASSET PIPELINE                                       │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  GLTF/GLB Models → Draco Compression → CDN (Vercel Edge)            │   │
│  │  Textures → KTX2/Basis → GPU-native decompression                   │   │
│  │  HDRI Environment Maps → Preloaded via Drei <Preload>               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
User Input (mouse/touch/keyboard)
        │
        ▼
┌─────────────────────────────┐
│  Event Processing Layer     │
│  (useDrawing, useSnapping,  │
│   usePanZoom, useTouch)     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Zustand Store Actions      │
│  (addWall, moveVertex,      │
│   addFurniture, etc.)       │
└──────────────┬──────────────┘
               │
       ┌───────┼───────┬──────────────┐
       │       │       │              │
       ▼       ▼       ▼              ▼
┌──────────┐ ┌─────┐ ┌──────────┐ ┌──────────────┐
│2D Render │ │ 3D  │ │  Vastu   │ │   History    │
│(SVG re-  │ │Trans│ │  Engine  │ │  (Command    │
│ render)  │ │form │ │(recompute│ │   Stack)     │
└──────────┘ │  +  │ │ zones &  │ └──────────────┘
             │Extru│ │ scores)  │
             │sion │ └─────┬────┘
             └──┬──┘       │
                │          │
                ▼          ▼
         ┌───────────┐ ┌──────────┐
         │  R3F      │ │ Overlay  │
         │  Scene    │ │ Renders  │
         │ (meshes,  │ │ (2D SVG  │
         │  lights,  │ │  sectors │
         │  camera)  │ │  + 3D    │
         └───────────┘ │  zones)  │
                       └──────────┘
```

---

## Coordinate Systems

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│   SCREEN SPACE          WORLD 2D             WORLD 3D          │
│   (Pixels)              (Centimeters)        (Meters)          │
│                                                                │
│   Origin: top-left      Origin: center       Origin: ground    │
│   Y: ↓ (down)          Y: ↑ (up)           Y: ↑ (up)         │
│                                              Z: → (depth, -Y2D)│
│                                                                │
│        screenToWorld()          planTo3D()                      │
│   Screen ──────────────▶ 2D ──────────────▶ 3D                │
│          ◀──────────────    ◀──────────────                    │
│        worldToScreen()        threeDToPlan()                   │
│                                                                │
│   Key transforms:                                              │
│   • Y-flip between screen and world 2D                        │
│   • cm → meters (÷100)                                         │
│   • 2D Y → 3D -Z (right-hand coordinate preservation)         │
│   • Height → 3D Y axis                                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Domain Boundaries & Communication

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌──────────────┐          STORE           ┌──────────────┐    │
│  │              │◀──── (selectors) ────────▶│              │    │
│  │   EDITOR     │                           │   VIEWER     │    │
│  │   DOMAIN     │──── vertices/walls ──────▶│   DOMAIN     │    │
│  │              │     rooms/furniture        │              │    │
│  └──────┬───────┘                           └──────────────┘    │
│         │                                          ▲            │
│         │ rooms + polygons                         │            │
│         ▼                                          │            │
│  ┌──────────────┐                                  │            │
│  │              │───── overlay geometry ────────────┘            │
│  │   VASTU      │                                               │
│  │   DOMAIN     │                                               │
│  │              │                                               │
│  └──────────────┘                                               │
│                                                                 │
│  RULE: Domains never import components from each other.         │
│  Communication ONLY via:                                        │
│    1. Zustand store (selectors)                                 │
│    2. Service function calls (pure functions)                   │
│    3. Event bus (fire-and-forget notifications)                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
src/
├── app/                          # Application shell
│   ├── App.tsx                   # Root layout + error boundaries
│   ├── main.tsx                  # Vite entry point
│   ├── providers.tsx             # Context providers
│   ├── monitoring.ts             # Sentry init
│   ├── ResponsiveLayout.tsx      # Breakpoint-aware layout
│   ├── ErrorBoundary.tsx         # React error boundary
│   ├── fallbacks/                # Fallback UIs per domain
│   └── hooks/
│       ├── useKeyboardShortcuts.ts
│       ├── useResponsiveLayout.ts
│       └── useAccessibilityPreferences.ts
│
├── domains/
│   ├── editor/                   # 2D floor plan editing
│   │   ├── components/           # SVG layers (Grid, Wall, Room, Furniture, Selection)
│   │   ├── hooks/                # useDrawing, useSnapping, usePan, useTouch, useSelection
│   │   ├── services/             # geometry, roomDetection, wallOps, collision
│   │   └── constants.ts
│   │
│   ├── viewer/                   # 3D visualization
│   │   ├── components/           # R3F meshes (Wall, Floor, Furniture, Camera, Overlay)
│   │   ├── hooks/                # useOrbitCamera, useFirstPerson, useAssetLoader
│   │   ├── services/             # extrusion, transform, materials
│   │   └── constants.ts
│   │
│   ├── vastu/                    # Vastu Shastra analysis
│   │   ├── components/           # VastuPanel, VastuOverlay2D, ScoreCard
│   │   ├── services/             # brahmasthan, zones, scoring, vectors
│   │   └── constants.ts
│   │
│   └── shared/                   # Cross-domain UI
│       ├── components/           # Toolbar, PropertyPanel, StatusBar, Loading, Empty
│       └── ui/                   # Radix-based primitives (Button, Dialog, Select, etc.)
│
├── store/                        # Zustand state management
│   ├── index.ts                  # Store composition (immer + devtools + persist)
│   ├── slices/                   # editorSlice, viewerSlice, vastuSlice, uiSlice, historySlice
│   ├── selectors/                # Memoized selectors per domain
│   ├── history/                  # Command-based undo/redo system
│   ├── persistence/              # IndexedDB adapter, migrations, validation, fileIO
│   └── guards/                   # Input validation & graph integrity checks
│
├── types/                        # TypeScript interfaces
│   ├── geometry.ts               # Point2D, Point3D, ScreenPoint, ViewTransform, AABB, OBB
│   ├── editor.ts                 # Vertex, Wall, Room, FurnitureItem, FloorPlan
│   ├── viewer.ts                 # Camera, Material configs
│   └── vastu.ts                  # Zone, Direction, Score
│
├── utils/                        # Shared utilities
│   ├── math.ts                   # Vector ops, pointInPolygon, clamp
│   ├── id.ts                     # nanoid wrapper
│   ├── errors.ts                 # Typed error classes
│   ├── eventBus.ts               # Cross-domain pub/sub
│   ├── env.ts                    # Environment config
│   └── constants.ts
│
├── test/
│   └── setup.ts                  # Vitest global setup + mocks
│
└── assets/
    ├── models/                   # GLTF/GLB furniture
    ├── textures/                 # KTX2 wall/floor textures
    └── icons/                    # 2D furniture SVG icons
```

---

## Rendering Architecture

```
┌─────────────────────── 2D EDITOR (SVG) ───────────────────────┐
│                                                                │
│  <svg>                                                         │
│    <g transform="translate(offX, offY) scale(s)">  ← Pan/Zoom │
│      ├── GridLayer        (SVG <pattern> + <rect>)             │
│      ├── RoomLayer        (filled <polygon> per room)          │
│      ├── WallLayer        (thick <line> per wall)              │
│      ├── FurnitureLayer   (positioned <image> icons)           │
│      ├── SelectionLayer   (highlight <rect> overlays)          │
│      ├── VastuOverlay2D   (arc <path> sectors)                 │
│      └── DrawingPreview   (rubber-band <line>)                 │
│    </g>                                                        │
│  </svg>                                                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌─────────────────────── 3D VIEWER (R3F) ───────────────────────┐
│                                                                │
│  <Canvas shadows dpr={[1,2]}>                                  │
│    <Suspense>                                                  │
│      ├── SceneEnvironment (HDRI + directional + hemisphere)    │
│      ├── CameraController (Orbit or FirstPerson)               │
│      ├── Ground Plane     (MeshStandardMaterial)               │
│      ├── FloorMesh[]      (ShapeGeometry per room)             │
│      ├── WallMesh[]       (Custom BufferGeometry per wall)     │
│      ├── FurnitureModel[] (GLTF clones with LOD)              │
│      ├── VastuOverlay3D   (Transparent triangle fans)          │
│      └── ContactShadows                                        │
│    </Suspense>                                                 │
│  </Canvas>                                                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## State Management Pattern

```
┌─────────────────────────────────────────────────┐
│              Zustand Store                       │
│                                                 │
│  create()(                                      │
│    devtools(                                    │
│      persist(                                   │
│        immer(                                   │
│          ...editorSlice   ← walls, vertices     │
│          ...viewerSlice   ← camera, render      │
│          ...vastuSlice    ← scores, zones       │
│          ...uiSlice       ← tool, panels        │
│          ...historySlice  ← undo/redo           │
│        )                                        │
│      , { storage: IndexedDB, migrate })         │
│    , { name: 'HomeQuest' })                     │
│  )                                              │
│                                                 │
│  Access patterns:                               │
│  • Surgical selectors (shallow equality)        │
│  • Transient subscribe (bypass React for 60fps) │
│  • getState() for event handlers                │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Performance Strategy

| Technique | Where | Impact |
|-----------|-------|--------|
| Surgical Zustand selectors | All components | Prevents cascade re-renders |
| `shallow` equality | Array/object selectors | Stops reference-change triggers |
| Transient `subscribe` | Mouse tracking during draw | Bypasses React at 60fps |
| `React.memo` | Leaf components (WallMesh, etc.) | Skips unchanged props |
| `useMemo` on geometry | WallMesh, FloorMesh | Avoids GPU buffer recreation |
| Material cache | getMaterial() | Single GPU upload per type |
| Instanced meshes | Repeated furniture | O(1) draw calls |
| Geometry batching | Static wall groups | Merged into single mesh |
| LOD (Detailed) | Furniture at distance | Simplified geo far away |
| `dpr={[1,2]}` | R3F Canvas | Caps pixel ratio for perf |
| Frustum culling | Three.js automatic | Skips off-screen meshes |
| Code splitting | `React.lazy` per domain | Smaller initial bundle |
| Draco + KTX2 | Asset pipeline | 80-90% smaller models |

---

## Deployment Architecture

```
┌──────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Developer  │      │     Vercel       │      │    Client    │
│              │      │                  │      │   Browser    │
│  git push    │─────▶│  Build (Vite)    │      │              │
│              │      │  ├── HTML/JS/CSS │─────▶│  React App   │
│              │      │  ├── chunks:     │      │  Three.js    │
│              │      │  │   vendor-react│      │  WebGL       │
│              │      │  │   vendor-three│      │              │
│              │      │  │   vendor-r3f  │      │  IndexedDB   │
│              │      │  │   vendor-ui   │      │  (persist)   │
│              │      │  └── assets/     │      │              │
│              │      │      models/ CDN │      │              │
│              │      │      textures/   │      │              │
│              │      │                  │      │              │
│              │      │  Edge Network    │      │              │
│              │      │  (immutable      │      │              │
│              │      │   asset caching) │      │              │
└──────────────┘      └──────────────────┘      └──────────────┘
```

---

## Key Algorithms

| Algorithm | Domain | Complexity | Purpose |
|-----------|--------|-----------|---------|
| Minimal Cycle Detection (left-turn rule) | Editor | O(E × max_degree) | Room detection from wall graph |
| Separating Axis Theorem (SAT) | Editor | O(1) per pair | OBB collision detection |
| Spatial Hash Grid | Editor | O(1) insert/query | Broad-phase collision culling |
| Shoelace Formula | Editor/Vastu | O(n) | Polygon area + winding direction |
| Parametric Line Intersection | Editor | O(n) per new wall | Wall split detection |
| Polygon Centroid (area-weighted) | Vastu | O(n) | Brahmasthan calculation |
| Angular Zone Classification | Vastu | O(zones) | Direction assignment |
| Ray Casting | Utils | O(n) | Point-in-polygon test |
| Wall Extrusion (custom BufferGeometry) | Viewer | O(1) per wall | 2D→3D mesh generation |
