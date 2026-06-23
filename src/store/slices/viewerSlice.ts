/**
 * ============================================================================
 * PURPOSE: 3D Viewer Settings & Camera State
 * ============================================================================
 * 
 * WHY IT EXISTS:
 * While the 2D editor handles the architectural data (walls, rooms), this file 
 * strictly manages HOW you view that data in the 3D world. It remembers your 
 * camera settings and visual preferences.
 * 
 * WHAT IT DOES:
 * 1. Camera: Remembers if you are flying around (orbit) or walking (first-person).
 * 2. Visuals: Keeps track of graphics quality and debug views (like wireframes).
 * 3. Focus: Remembers the exact center of the house so the camera knows what to orbit around.
 * 
 * MENTAL MODEL:
 * ┌─────────────────────────────────────────────────────────┐
 * │                     3D Viewport                         │
 * │                                                         │
 * │    [👁️ Camera: Orbit]            [⚙️ Quality: High]    │
 * │                                                         │
 * │              ┌───────────────────────┐                  │
 * │              │           X           │                  │
 * │              │     (House Center)    │                  │
 * │              └───────────────────────┘                  │
 * │                                                         │
 * │    [🕸️ Wireframe: OFF]                                  │
 * └─────────────────────────────────────────────────────────┘
 */
import type { StateCreator } from 'zustand';
import type { AppStore } from '..';
import type { Point3D } from '@/types/geometry';

/** How the user is looking at the 3D scene (orbiting from outside vs walking inside) */
export type CameraMode = 'orbit' | 'firstPerson';

/** How pretty the graphics look (lower it if the computer is lagging) */
export type RenderQuality = 'low' | 'medium' | 'high';

export interface ViewerSlice {
  // Memory (What we remember)
  cameraMode: CameraMode;
  renderQuality: RenderQuality;
  showWireframe: boolean;
  /**
   * The exact middle point of the house in the 3D world.
   * We remember this so the camera knows what to spin around!
   */
  planCentroid3D: Point3D | null;

  // Controls (How we change the memory)
  setCameraMode: (mode: CameraMode) => void;
  setRenderQuality: (quality: RenderQuality) => void;
  toggleWireframe: () => void;
  setPlanCentroid3D: (centroid: Point3D | null) => void;
  resetCameraTick: number;
  triggerCameraReset: () => void;
}

export const createViewerSlice: StateCreator<
  AppStore,
  [['zustand/devtools', never], ['zustand/immer', never]],
  [],
  ViewerSlice
> = (set) => ({
  cameraMode: 'orbit',
  renderQuality: 'high',
  showWireframe: false,
  planCentroid3D: null,
  resetCameraTick: 0,

  setCameraMode: (mode) => {
    set((state) => {
      state.cameraMode = mode;
    });
  },

  setRenderQuality: (quality) => {
    set((state) => {
      state.renderQuality = quality;
    });
  },

  toggleWireframe: () => {
    set((state) => {
      state.showWireframe = !state.showWireframe;
    });
  },

  setPlanCentroid3D: (centroid) => {
    set((state) => {
      state.planCentroid3D = centroid;
    });
  },

  triggerCameraReset: () => {
    set((state) => {
      state.resetCameraTick += 1;
    });
  },
});