# Project Plan: 3D Architectural Visualization & Vastu Engine

## 🎯 Objective
To build an interactive, web-based architectural visualization application that enables users to design 2D floor plans, instantly generate navigable 3D models, and perform real-time spatial analysis by calculating and projecting directional energy zones (Vastu Shastra) onto the 3D geometry.

---

## 🛠 Tech Stack

This stack is optimized for high-performance browser rendering and clean state synchronization.

### Core Frameworks & State
* **Language:** TypeScript (Ensures strict typing for spatial coordinates and object properties).
* **Core Logic & UI:** React.
* **State Management:** Zustand (Lightweight and fast; critical for high-frequency state updates like dragging objects).
* **Build Environment:** Vite.

### 3D Rendering & Mathematics
* **3D Engine:** Three.js via React Three Fiber (R3F) (Allows declarative 3D scene building using React components).
* **Model Loading:** `@react-three/drei` (Specifically `useGLTF` for importing `.gltf`/`.glb` 3D furniture files).

### UI Components & Styling
* **CSS Framework:** Tailwind CSS.
* **Component Library:** Radix UI (For building accessible sidebars, configuration menus, and control panels).

---

## 🚀 Implementation Phases

### Phase 1: Architecture & State Foundation
1.  Initialize the project repository using Vite, React, and TypeScript.
2.  Define the Zustand store schema. The global state must handle:
    * `viewMode`: `"2D" | "3D"`
    * `walls`: Array of objects containing start and end coordinates `[(x1, y1), (x2, y2)]`.
    * `furniture`: Array of objects containing `id`, `type`, `position (x, y, z)`, `rotation`, and `scale`.
    * `vastuOverlay`: Boolean (visible/hidden).

### Phase 2: The 2D Floor Plan Editor
1.  Build a 2D interactive grid using HTML `<canvas>` or standard React SVG components.
2.  Implement a wall-drawing tool that allows users to click and drag to plot lines.
3.  Implement a drag-and-drop system to place 2D bounding boxes (representing furniture) onto the grid.
4.  Bind all spatial coordinate changes to the Zustand store for real-time synchronization.

### Phase 3: The 3D Engine & Transformation
1.  Set up the 3D `<Canvas>` environment using React Three Fiber.
2.  Map the 2D coordinates to 3D space: A 2D point `(x, y)` translates to a 3D vector `(x, 0, z)` where the 2D y-axis becomes the horizontal z-axis in Three.js, and the Three.js y-axis represents vertical height.
3.  Write an extrusion algorithm that reads the `walls` array and generates 3D `BoxGeometry` meshes to represent physical walls.
4.  Implement `OrbitControls` (from `@react-three/drei`) to allow camera panning, zooming, and rotation around the 3D scene.

### Phase 4: Spatial Mathematics & Vastu Overlay
1.  **Centroid Calculation:** Write an algorithm to calculate the geometric center (Brahmasthan) of the bounded floor plan area.
2.  **Radial Projection:** Divide the 360-degree space surrounding the centroid into standard directional zones (e.g., North spans from 337.5° to 22.5°).
3.  **Visual Overlay:** Render semi-transparent, colored 3D planes or volumetric geometric cones over the 3D model, originating from the centroid and mapped to the calculated angles. 
4.  Bind opacity and toggle controls to the UI sidebar.

### Phase 5: Advanced Mechanics & Polish
1.  **Collision Detection:** Implement Axis-Aligned Bounding Box (AABB) logic to prevent users from dragging furniture meshes through wall meshes.
2.  **First-Person Walkthrough:** Add a camera controller mapped to WASD keys for virtual exploration.
3.  **Deployment:** Configure CI/CD and host the final build on platforms like Vercel or Netlify.

---

## 🏆 Reference Platforms & Industry Competitors

To build a high-performance application, study the engineering and UX of these top-tier WebGL and architectural platforms.

### 1. Coohom
* **Website:** [coohom.com](https://www.coohom.com/)
* **What to Study:** This is the direct competitor shown in your video. Study their **lighting algorithms** and **Vastu template integration**. Notice how seamlessly their state management handles the transition between the 2D blueprint and the fully lit 3D render without crashing the browser.

### 2. Homestyler
* **Website:** [homestyler.com](https://www.homestyler.com/)
* **What to Study:** Backed by Alibaba, Homestyler has one of the best browser-based 3D engines in the world. Study their **drag-and-drop mechanics** for furniture and how they handle **AABB collision detection** (preventing a sofa from going through a wall) in real-time.

### 3. Floorplanner
* **Website:** [floorplanner.com](https://www.floorplanner.com/)
* **What to Study:** The industry standard for lightweight, lightning-fast execution. Study their **2D drawing tools**. Notice the "snapping" feature—when you draw a wall, it automatically snaps to 90-degree angles or connects cleanly to adjacent walls. This is a crucial algorithm for your Phase 2.

### 4. Foyr Neo
* **Website:** [foyr.com](https://foyr.com/)
* **What to Study:** Known for an incredibly intuitive user interface. Study their **UI/UX layout**—specifically, how their sidebars and property panels are organized using React/CSS. It is a great reference for how to structure your Tailwind and Radix UI components.

### 5. VastuAgent AI & AppliedVastu
* **Websites:** [vastuagent.ai](https://vastuagent.ai/) | [appliedvastu.com](https://www.appliedvastu.com/)
* **What to Study:** While their 3D tech isn't as advanced as the others, they are hyper-specialized in Vastu. Study their **radial projection mathematics**—how they calculate the *Brahmasthan* (center) of irregular floor plans and accurately overlay the 16 Vastu zones (Maha Vastu) onto the grid.