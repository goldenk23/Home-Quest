import { create } from 'zustand';
import type { SettingsSlice } from './slices/settingsSlice';
import { createSettingsSlice } from './slices/settingsSlice';

// Combine all slice types into a single AppState
export type AppState = SettingsSlice; // Add other slices here (e.g. & EditorSlice)

export const useAppStore = create<AppState>()((...a) => ({
  ...createSettingsSlice(...a),
  // Add other slice creators here
}));
