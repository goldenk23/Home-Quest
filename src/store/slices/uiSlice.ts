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
import type { OpeningFamily } from '@/domains/shared/openings/openingCatalog';
import { defaultKindForFamily } from '@/domains/shared/openings/openingCatalog';

/** What the user is currently holding in their cursor (e.g. wall tool, select tool) */
export type Tool = 'select' | 'wall' | 'road' | 'furniture' | 'pan' | 'measure' | 'door' | 'window' | 'vent' | 'ac' | 'paint' | 'room';

/** The different side-menus the user can open and close */
export type PanelId = 'properties' | 'vastu' | 'catalog' | 'layers';

export interface UISlice {
  // Memory (What we remember)
  activeTool: Tool;
  panelVisibility: Record<PanelId, boolean>;
  isChainModeEnabled: boolean;
  /** Whether wall-length dimension labels are shown in the 2D editor. */
  showDimensions: boolean;
  /** The catalog id that the furniture tool will place on the next click. */
  furnitureCatalogId: string;
  /** Width (cm) applied to the next road segment drawn with the Road tool. */
  roadWidth: number;
  /** The finish id (wall paint or floor tile) the Paint tool applies on the next click. */
  paintFinishId: string;
  /** The selected opening kind id per family, used by the door/window/vent/ac tools. */
  selectedOpeningKinds: Record<OpeningFamily, string>;
  /**
   * Optional per-family size overrides applied when placing the next opening. Lets the user
   * dictate sill height (elevation), opening height, and width for windows/ventilation
   * instead of always using the kind's catalog defaults. Unset fields fall back to the kind.
   */
  openingSizeOverrides: Record<OpeningFamily, { width?: number; height?: number; elevation?: number }>;

  // Controls (How we change the memory)
  setActiveTool: (tool: Tool) => void;
  togglePanel: (panel: PanelId) => void;
  setPanelVisibility: (panel: PanelId, visible: boolean) => void;
  setChainMode: (enabled: boolean) => void;
  toggleDimensions: () => void;
  setFurnitureCatalogId: (catalogId: string) => void;
  /** Set the width (cm) used for newly drawn roads. */
  setRoadWidth: (width: number) => void;
  setPaintFinishId: (finishId: string) => void;
  /** Choose which opening kind a family's tool will place next. */
  setOpeningKind: (family: OpeningFamily, kindId: string) => void;
  /** Set/merge a size override (width/height/elevation in cm) for a family. */
  setOpeningSize: (family: OpeningFamily, patch: { width?: number; height?: number; elevation?: number }) => void;
  /** Clear all size overrides for a family (revert to the kind's catalog defaults). */
  resetOpeningSize: (family: OpeningFamily) => void;
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
  roadWidth: 300,
  showDimensions: true,
  paintFinishId: 'paint-white',
  selectedOpeningKinds: {
    door: defaultKindForFamily('door'),
    window: defaultKindForFamily('window'),
    vent: defaultKindForFamily('vent'),
    ac: defaultKindForFamily('ac'),
  },
  openingSizeOverrides: {
    door: {},
    window: {},
    vent: {},
    ac: {},
  },

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

  toggleDimensions: () => {
    set((state) => {
      state.showDimensions = !state.showDimensions;
    });
  },

  setFurnitureCatalogId: (catalogId) => {
    set((state) => {
      state.furnitureCatalogId = catalogId;    });
  },

  setRoadWidth: (width) => {
    set((state) => {
      state.roadWidth = Math.max(30, Math.min(2000, Math.round(width)));
    });
  },

  setPaintFinishId: (finishId) => {
    set((state) => {
      state.paintFinishId = finishId;
    });
  },

  setOpeningKind: (family, kindId) => {
    set((state) => {
      state.selectedOpeningKinds[family] = kindId;
    });
  },

  setOpeningSize: (family, patch) => {
    set((state) => {
      state.openingSizeOverrides[family] = { ...state.openingSizeOverrides[family], ...patch };
    });
  },

  resetOpeningSize: (family) => {
    set((state) => {
      state.openingSizeOverrides[family] = {};
    });
  },
});