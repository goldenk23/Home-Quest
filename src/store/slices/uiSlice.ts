/**
 * ============================================================================
 * PURPOSE: Global UI State Management
 * ============================================================================
 * 
 * WHY IT EXISTS:
 * While `editorSlice.ts` holds the actual floor plan data (walls, furniture), 
 * this file strictly holds the TRANSIENT user interface state. This is the 
 * state that changes as you click around, but doesn't get saved to the database.
 * 
 * WHAT IT DOES:
 * 1. Active Tool: Remembers what you are currently holding/doing (e.g., drawing a 'wall' vs 'selecting').
 * 2. Panel Visibility: Remembers which floating side-menus are opened or closed.
 * 
 * MENTAL MODEL:
 * ┌─────────────────┬──────────────────────────────────┬─────────────────┐
 * │ Toolbar (Tools) │                                  │ Panels (Right)  │
 * │  [x] Select     │          Main Viewport           │  [+] Properties │
 * │  [ ] Wall       │      (Data from editorSlice)     │  [-] Vastu      │
 * │  [ ] Furniture  │                                  │  [+] Catalog    │
 * └─────────────────┴──────────────────────────────────┴─────────────────┘
 */
import type { StateCreator } from 'zustand';
import type  { AppStore } from '..';

/** What the user is currently holding in their cursor (e.g. wall tool, select tool) */
export type Tool = 'select' | 'wall' | 'furniture' | 'pan' | 'measure';

/** The different side-menus the user can open and close */
export type PanelId = 'properties' | 'vastu' | 'catalog' | 'layers';

export interface UISlice {
  // Memory (What we remember)
  activeTool: Tool;
  panelVisibility: Record<PanelId, boolean>;
  isChainModeEnabled: boolean;
  /** The catalog id that the furniture tool will place on the next click. */
  furnitureCatalogId: string;

  // Controls (How we change the memory)
  setActiveTool: (tool: Tool) => void;
  togglePanel: (panel: PanelId) => void;
  setPanelVisibility: (panel: PanelId, visible: boolean) => void;
  setChainMode: (enabled: boolean) => void;
  setFurnitureCatalogId: (catalogId: string) => void;
}

export const createUISlice: StateCreator<
  AppStore,
  [['zustand/devtools', never], ['zustand/immer', never]],
  [],
  UISlice
> = (set) => ({
  activeTool: 'select',
  panelVisibility: {
    properties: true,
    vastu: false,
    catalog: false,
    layers: false,
  },
  isChainModeEnabled: false,
  furnitureCatalogId: 'sofa-3seat',

  setActiveTool: (tool) => {
    set((state) => {
      state.activeTool = tool;
    });
  },

  togglePanel: (panel) => {
    set((state) => {
      state.panelVisibility[panel] = !state.panelVisibility[panel];
    });
  },

  setPanelVisibility: (panel, visible) => {
    set((state) => {
      state.panelVisibility[panel] = visible;
    });
  },

  setChainMode: (enabled) => {
    set((state) => {
      state.isChainModeEnabled = enabled;
    });
  },

  setFurnitureCatalogId: (catalogId) => {
    set((state) => {
      state.furnitureCatalogId = catalogId;
    });
  },
});