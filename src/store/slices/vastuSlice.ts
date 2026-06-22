import type { StateCreator } from 'zustand';
import type { AppStore } from '../index';
import type { Point2D } from '@/types/geometry';
import type { VastuScore } from '@/domains/vastu/services/scoring';

export interface VastuSlice {
  showVastuOverlay2D: boolean;
  showVastuOverlay3D: boolean;
  planBoundary: Point2D[] | null;
  vastuScore: VastuScore | null;

  toggleVastuOverlay2D: () => void;
  toggleVastuOverlay3D: () => void;
  setPlanBoundary: (boundary: Point2D[] | null) => void;
  setVastuScore: (score: VastuScore | null) => void;
}

export const createVastuSlice: StateCreator<
  AppStore,
  [['zustand/devtools', never], ['zustand/immer', never]],
  [],
  VastuSlice
> = (set) => ({
  showVastuOverlay2D: false,
  showVastuOverlay3D: false,
  planBoundary: null,
  vastuScore: null,

  toggleVastuOverlay2D: () => {
    set((state) => {
      state.showVastuOverlay2D = !state.showVastuOverlay2D;
    });
  },
  toggleVastuOverlay3D: () => {
    set((state) => {
      state.showVastuOverlay3D = !state.showVastuOverlay3D;
    });
  },
  setPlanBoundary: (boundary) => {
    set((state) => {
      state.planBoundary = boundary;
    });
  },
  setVastuScore: (score) => {
    set((state) => {
      state.vastuScore = score;
    });
  },
});
