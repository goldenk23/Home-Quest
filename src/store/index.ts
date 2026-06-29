import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { devtools, persist, createJSONStorage } from 'zustand/middleware';
import { createEditorSlice } from './slices/editorSlice';
import type { EditorSlice } from './slices/editorSlice';
import { createViewerSlice } from './slices/viewerSlice';
import type { ViewerSlice } from './slices/viewerSlice';
import { createUISlice } from './slices/uiSlice';
import type { UISlice } from './slices/uiSlice';
import { createSettingsSlice } from './slices/settingsSlice';
import type { SettingsSlice } from './slices/settingsSlice';
import { createVastuSlice } from './slices/vastuSlice';
import type { VastuSlice } from './slices/vastuSlice';
import { createHistorySlice } from './slices/historySlice';
import type { HistorySlice } from './slices/historySlice';
import { createFloorsSlice } from './slices/floorsSlice';
import type { FloorsSlice } from './slices/floorsSlice';
import { indexedDBStorage } from './persistence/persistConfig';
import { migrateState, CURRENT_SCHEMA_VERSION } from './persistence/migrations';

export type AppStore = EditorSlice &
  ViewerSlice &
  UISlice &
  SettingsSlice &
  VastuSlice &
  HistorySlice &
  FloorsSlice;

export const useAppStore = create<AppStore>()(
  devtools(
    persist(
      immer((...args) => ({
        ...createEditorSlice(...args),
        ...createViewerSlice(...args),
        ...createUISlice(...args),
        ...createSettingsSlice(...args),
        ...createVastuSlice(...args),
        ...createHistorySlice(...args),
        ...createFloorsSlice(...args),
      })),
      {
        name: 'homequest-store',
        version: CURRENT_SCHEMA_VERSION,
        storage: createJSONStorage(() => indexedDBStorage),
        migrate: (persisted) => migrateState(persisted) as unknown as AppStore,
        // Persist floor-plan data only — UI/history are transient. The active floor lives in
        // the flat maps; the other storeys are parked in floorData.
        partialize: (state) => ({
          vertices: state.vertices,
          walls: state.walls,
          rooms: state.rooms,
          furniture: state.furniture,
          openings: state.openings,
          roads: state.roads,
          stairs: state.stairs,
          floors: state.floors,
          activeFloorId: state.activeFloorId,
          floorData: state.floorData,
        }),
        skipHydration: false,
      }
    ),
    { name: 'HomeQuest' }
  )
);
