import type { StateCreator } from 'zustand';
import type { AppStore } from '../index';
import type { Point2D } from '@/types/geometry';
import type { VastuScore } from '@/domains/vastu/services/scoring';

export type VastuZoneCount = 8 | 16 | 32;
export type VastuChakraMode = 'vedic' | 'modern';

export interface VastuSlice {
  showVastuOverlay2D: boolean;
  showVastuOverlay3D: boolean;
  planBoundary: Point2D[] | null;
  vastuScore: VastuScore | null;
  /** Number of sectors in the authoring chakra grid. */
  vastuZoneCount: VastuZoneCount;
  /** North offset in degrees (clockwise from world +Y). Rotates the whole grid/compass. */
  vastuNorthDeg: number;
  /** Label scheme: traditional Vedic names vs modern compass names. */
  vastuChakraMode: VastuChakraMode;
  /** Whether the sector division lines are drawn over the plan boundary. */
  showVastuDivisionLines: boolean;

  toggleVastuOverlay2D: () => void;
  toggleVastuOverlay3D: () => void;
  setPlanBoundary: (boundary: Point2D[] | null) => void;
  setVastuScore: (score: VastuScore | null) => void;
  setVastuZoneCount: (count: VastuZoneCount) => void;
  setVastuNorthDeg: (deg: number) => void;
  setVastuChakraMode: (mode: VastuChakraMode) => void;
  toggleVastuDivisionLines: () => void;
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
  vastuZoneCount: 8,
  vastuNorthDeg: 0,
  vastuChakraMode: 'vedic',
  showVastuDivisionLines: true,

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
  setVastuZoneCount: (count) => {
    set((state) => {
      state.vastuZoneCount = count;
    });
  },
  setVastuNorthDeg: (deg) => {
    set((state) => {
      state.vastuNorthDeg = ((deg % 360) + 360) % 360;
    });
  },
  setVastuChakraMode: (mode) => {
    set((state) => {
      state.vastuChakraMode = mode;
    });
  },
  toggleVastuDivisionLines: () => {
    set((state) => {
      state.showVastuDivisionLines = !state.showVastuDivisionLines;
    });
  },
});
