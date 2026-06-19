import type { StateCreator } from 'zustand';

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
  
  // Actions
  toggleFeatureFlag: (flag: keyof FeatureFlags) => void;
  toggleDevMode: () => void;
  setActiveView: (view: 'app' | 'sandbox') => void;
}

const initialFeatureFlags: FeatureFlags = {
  enableVastuOverlay: false,
  enableNewCamera: false,
  showDebugGrid: true,
};

export const createSettingsSlice: StateCreator<SettingsSlice> = (set) => ({
  featureFlags: initialFeatureFlags,
  devMode: true, // Enabled by default in dev environment
  activeView: 'app',
  
  toggleFeatureFlag: (flag) => 
    set((state) => ({
      featureFlags: {
        ...state.featureFlags,
        [flag]: !state.featureFlags[flag],
      },
    })),
    
  toggleDevMode: () => 
    set((state) => ({ devMode: !state.devMode })),
    
  setActiveView: (view) => 
    set({ activeView: view }),
});
