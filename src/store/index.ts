import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { devtools } from 'zustand/middleware';
import { createEditorSlice } from './slices/editorSlice';
import type { EditorSlice } from './slices/editorSlice';
import { createViewerSlice } from './slices/viewerSlice';
import type { ViewerSlice } from './slices/viewerSlice';
// import { VastuSlice, createVastuSlice } from './slices/vastuSlice';
import { createUISlice } from './slices/uiSlice';
import type { UISlice } from './slices/uiSlice';
// import { HistorySlice, createHistorySlice } from './slices/historySlice';

export type AppStore = EditorSlice & ViewerSlice & UISlice;// & VastuSlice &  & HistorySlice;

export const useAppStore = create<AppStore>()(
  devtools(
    immer((...args) => ({
      ...createEditorSlice(...args),
      ...createViewerSlice(...args),
      // ...createVastuSlice(...args),
      ...createUISlice(...args),
      // ...createHistorySlice(...args),
    })),
    { name: 'HomeQuest' }
  )
);