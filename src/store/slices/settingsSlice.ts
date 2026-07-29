import type { StateCreator } from 'zustand';
import type { AppStore } from '../index';
import type { DisplayUnit } from '@/domains/editor/services/units';

export interface FeatureFlags {
  enableVastuOverlay: boolean;
  enableNewCamera: boolean;
  showDebugGrid: boolean;
  // Add new feature flags here as you build them
}

export interface SettingsSlice {
  featureFlags: FeatureFlags;
  devMode: boolean;
  activeView: 'app' | 'sandbox';
  /** User-chosen display unit. World geometry stays in cm; this only affects presentation. */
  displayUnit: DisplayUnit;

  // Actions
  toggleFeatureFlag: (flag: keyof FeatureFlags) => void;
  toggleDevMode: () => void;
  setActiveView: (view: 'app' | 'sandbox') => void;
  setDisplayUnit: (unit: DisplayUnit) => void;
}

const initialFeatureFlags: FeatureFlags = {
  enableVastuOverlay: false,
  enableNewCamera: false,
  showDebugGrid: true,
};

export const createSettingsSlice: StateCreator<
  AppStore,
  [['zustand/immer', never], ['zustand/devtools', never]],
  [],
  SettingsSlice
> = (set) => ({
  featureFlags: initialFeatureFlags,
  devMode: true, // Enabled by default in dev environment
  activeView: 'sandbox',
  displayUnit: 'm',

  toggleFeatureFlag: (flag) =>
    set((state) => {
      state.featureFlags[flag] = !state.featureFlags[flag];
    }),

  toggleDevMode: () =>
    set((state) => {
      state.devMode = !state.devMode;
    }),

  setActiveView: (view) =>
    set((state) => {
      state.activeView = view;
    }),

  setDisplayUnit: (unit) =>
    set((state) => {
      state.displayUnit = unit;
    }),
});
