import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { devtools } from 'zustand/middleware';
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

export type AppStore = EditorSlice & ViewerSlice & UISlice & SettingsSlice & VastuSlice;

export const useAppStore = create<AppStore>()(
  devtools(
    immer((...args) => ({
      ...createEditorSlice(...args),
      ...createViewerSlice(...args),
      ...createUISlice(...args),
      ...createSettingsSlice(...args),
      ...createVastuSlice(...args),
    })),
    { name: 'HomeQuest' }
  )
);