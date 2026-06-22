# 🏡 Home Quest: Features Overview

Welcome to the **Home Quest** feature guide! This document breaks down everything our smart home design application can do. We've organized these features into three main "Installments" — from drawing a basic blueprint to walking through your home in 3D. 

---

## 📐 1. The 2D Editor (Your Digital Drafting Board)
*This is where you design your floor plan from a top-down, "bird's-eye" perspective.*

### **Infinite Design Canvas**
Think of this as a massive, endless piece of digital graph paper. You can drag the screen to pan around and use your mouse wheel to zoom in and out, allowing you to design anything from a tiny cabin to a sprawling mansion.

### **Smart Wall Drawing**
Click and drag to lay down solid walls. You can draw a single wall segment or enable "Chain Mode" to continuously click and draw connected walls, making it incredibly fast to sketch out a room. 

### **Magnetic Snapping**
Drawing perfectly straight lines and exact corners by hand is hard. Our snapping system acts like a magnet—as your cursor gets close to a grid line or the end of another wall, it "snaps" perfectly into place so your walls always align tightly.

### **Automatic Room Detection**
The moment you draw a completely closed loop of walls, the system instantly recognizes it and creates a "Room." It automatically fills the room with a floor and calculates the exact area (in m²), shown right on the room.

### **Interior Design & Furniture**
Pick a piece of furniture (sofa, dining table, queen bed, office chair, toilet, kitchen counter) from the catalog and click to drop it into your plan. With the Select tool you can drag pieces around, rotate them (the `R` key or the rotate buttons, in 15° steps), and delete them. Each piece carries real-world dimensions used for both display and collision.

### **Editor Power Tools**
The drafting board includes pro touches: hold `Shift` while drawing to snap to clean angles (and it auto-snaps to 90°/45° lines), a live readout shows the wall's length and angle as you draw, wall corners are automatically mitered so junctions look clean, and `Esc`/right-click cancels an in-progress wall.

---

## 🕶️ 2. The 3D Viewer (Your Virtual Tour)
*This brings your flat blueprint to life in an interactive 3D world.*

### **Instant 3D Magic**
There is no "Render" or "Load" button. The absolute second you draw a wall or place a bed in the 2D editor, it instantly pops up as a physical, 3D object in the viewer right next to it. 

### **Solid Walls & Floors**
The system takes your flat 2D lines and automatically "pulls" them up to create solid 3D walls with real thickness and height. When a room is detected, it automatically lays down a solid 3D floor.

### **Realistic Lighting & Shadows**
To make the house feel real, the 3D viewer simulates sunlight. Walls and furniture cast accurate shadows on the floor, giving you a true sense of depth and space.

### **3D Furniture Models**
Those simple 2D icons you placed in the editor? The 3D viewer translates them into dimension-accurate, volumetric 3D objects sitting inside your virtual rooms, each sized and colored to its catalog entry.

---

## 🧠 3. Advanced Interactions & Smart Analysis
*This makes your home "smart" by adding physics, video-game cameras, and architectural rules.*

### **Smart Furniture Collision**
In the real world, you can't stack two sofas in the same spot. Our collision engine (a spatial hash for broad-phase plus the Separating Axis Theorem for precise oriented-box checks) continuously detects when furniture pieces overlap and flags every offending piece in **red** — in both the 2D editor and the 3D viewer — so you can immediately see and fix layout conflicts. *(Furniture-vs-wall collision is planned for a later installment; today the engine handles furniture-vs-furniture.)*

### **Dual Camera System**
You have two completely different ways to explore your creation:
- **Orbit Mode (Helicopter View):** Spin your camera smoothly around the outside of the house to inspect the overall structure. It's smart enough to stop you from accidentally zooming underneath the ground.
- **First-Person Mode (Walkthrough View):** Drop down to human eye-level. Just like a video game, you can use your keyboard (`W`, `A`, `S`, `D`) and mouse to walk through the hallways and look around your rooms.

### **The Vastu Shastra Engine**
Vastu is the traditional Indian system of architecture based on directional alignments and energy flow. Our engine calculates exactly how your house aligns with these ancient rules.
- **The Brahmasthan:** The engine uses complex math to find the exact, true center of your entire home.
- **Automated Scoring:** It checks what type of room is in what zone (e.g., checking if the kitchen is correctly placed in the South-East "Fire" zone) and gives you a score and recommendations to improve the layout. The results appear in a live **Vastu panel** — an overall score, a per-room breakdown, and prioritized recommendations (each marked with an icon and label, never color alone). Assign room types in the Rooms panel to drive the analysis.

### **Vastu Visual Overlays**
Instead of just giving you numbers, the system visually projects the Vastu compass directly onto your house! 
- **In 2D:** You'll see beautiful, color-coded pie slices radiating from the center of your blueprint.
- **In 3D:** You'll see transparent, glowing colored zones floating just above the floor, letting you physically walk through the different energy zones.

### **Developer Sandbox**
The app opens straight into an **Interactive Playground** — a single screen with the 2D editor and live 3D viewer side by side. A toolbar lets you switch tools (Select / Draw Wall / Furniture), pick furniture from the catalog, toggle the Vastu 2D/3D overlays, switch camera modes, assign room types, and rotate/delete the current selection. A one-click **Load Sample House** instantly populates a two-room plan so you can exercise every feature immediately, and a **Clear All** resets the canvas. A built-in "How to test" guide and an isolated snapping visualizer round it out. (You can switch back to the placeholder app shell anytime from the Dev Tools panel in the bottom-right.)
