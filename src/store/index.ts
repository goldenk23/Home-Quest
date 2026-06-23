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
import { indexedDBStorage } from './persistence/persistConfig';
import { migrateState, CURRENT_SCHEMA_VERSION } from './persistence/migrations';

export type AppStore = EditorSlice &
  ViewerSlice &
  UISlice &
  SettingsSlice &
  VastuSlice &
  HistorySlice;

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
      })),
      {
        name: 'homequest-store',
        version: CURRENT_SCHEMA_VERSION,
        storage: createJSONStorage(() => indexedDBStorage),
        migrate: (persisted) => migrateState(persisted) as unknown as AppStore,
        // Persist floor-plan data only — UI/history are transient.
        partialize: (state) => ({
          vertices: state.vertices,
          walls: state.walls,
          rooms: state.rooms,
          furniture: state.furniture,
          openings: state.openings,
        }),
        skipHydration: false,
      }
    ),
    { name: 'HomeQuest' }
  )
);
