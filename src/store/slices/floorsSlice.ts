// src/store/slices/floorsSlice.ts
//
// Multi-storey support. The design keeps the editor simple: the global store
// (vertices/walls/rooms/furniture/openings/roads) ALWAYS holds exactly the *active* floor's
// geometry — so every 2D editor component, snapping, room detection, drawing and undo/redo
// keep working unchanged, operating on one floor at a time. The OTHER floors are "parked" as
// serialized geometry in `floorData`. Switching floors swaps the working set with a parked
// one. The 3D viewer reads the active floor live and the parked floors from `floorData`, and
// stacks them by each floor's `elevationCm`.

import type { StateCreator } from 'zustand';
import { castDraft } from 'immer';
import type { AppStore } from '../index';
import type { EntityId, Floor, FloorGeometry } from '@/types/editor';
import { generateId } from '@/utils/id';

/** Floor-to-floor height in cm used when stacking a new storey (wall height + slab). */
export const STORY_HEIGHT_CM = 300;

/** An empty floor's geometry. */
export function emptyFloorGeometry(): FloorGeometry {
  return { vertices: {}, walls: {}, rooms: {}, furniture: {}, openings: {}, roads: {}, stairs: {}, pillars: {}, beams: {}, deckSlabs: {} };
}

/** Pull the active floor's geometry out of the live working set. */
function readWorkingGeometry(state: AppStore): FloorGeometry {
  return {
    vertices: state.vertices,
    walls: state.walls,
    rooms: state.rooms,
    furniture: state.furniture,
    openings: state.openings,
    roads: state.roads,
    stairs: state.stairs,
    pillars: state.pillars,
    beams: state.beams,
    deckSlabs: state.deckSlabs,
  };
}

export interface FloorsSlice {
  /** Ordered list of storeys, ground floor first. */
  floors: Floor[];
  /** The storey currently loaded into the working set (vertices/walls/…). */
  activeFloorId: EntityId;
  /** Serialized geometry for every NON-active floor (the active floor lives in the working set). */
  floorData: Record<EntityId, FloorGeometry>;

  /** Add a new empty storey on top, switch to it, and return its id. */
  addFloor: (name?: string) => EntityId;
  /** Remove a storey (never the last one). If it's active, switches to a neighbour first. */
  removeFloor: (id: EntityId) => void;
  /** Park the current floor and load `id` into the working set. */
  setActiveFloor: (id: EntityId) => void;
  /** Rename a storey. */
  renameFloor: (id: EntityId, name: string) => void;
  /** Reset to a single empty ground floor (used by Clear All / sample load). */
  resetFloors: () => void;
}

export const createFloorsSlice: StateCreator<
  AppStore,
  [['zustand/immer', never], ['zustand/devtools', never]],
  [],
  FloorsSlice
> = (set, get) => {
  const groundId = generateId('floor');
  return {
    floors: [{ id: groundId, name: 'Ground Floor', elevationCm: 0 }],
    activeFloorId: groundId,
    floorData: {},

    addFloor: (name) => {
      const id = generateId('floor');
      const state = get();
      const topElevation = state.floors.reduce((max, f) => Math.max(max, f.elevationCm), 0);
      const floorName = name ?? `Floor ${state.floors.length}`;
      // Park the current floor, then start the new one empty as the working set.
      const parked = readWorkingGeometry(state);
      const empty = emptyFloorGeometry();
      set((s) => {
        s.floorData[s.activeFloorId] = castDraft(parked);
        s.floors.push({ id, name: floorName, elevationCm: topElevation + STORY_HEIGHT_CM });
        s.vertices = castDraft(empty.vertices);
        s.walls = castDraft(empty.walls);
        s.rooms = castDraft(empty.rooms);
        s.furniture = castDraft(empty.furniture);
        s.openings = castDraft(empty.openings);
        s.roads = castDraft(empty.roads);
        s.stairs = castDraft(empty.stairs);
        s.pillars = castDraft(empty.pillars);
        s.beams = castDraft(empty.beams);
        s.deckSlabs = castDraft(empty.deckSlabs);
        delete s.floorData[id];
        s.activeFloorId = id;
        s.selectedIds = [];
      });
      get().clearHistory();
      return id;
    },

    removeFloor: (id) => {
      const state = get();
      if (state.floors.length <= 1) return; // keep at least one storey
      const removingActive = state.activeFloorId === id;
      // Decide which floor becomes active if we're deleting the active one.
      const idx = state.floors.findIndex((f) => f.id === id);
      if (idx === -1) return;
      const fallback = state.floors[idx === 0 ? 1 : idx - 1];

      if (removingActive) {
        const incoming = state.floorData[fallback.id] ?? emptyFloorGeometry();
        set((s) => {
          s.vertices = castDraft(incoming.vertices);
          s.walls = castDraft(incoming.walls);
          s.rooms = castDraft(incoming.rooms);
          s.furniture = castDraft(incoming.furniture);
          s.openings = castDraft(incoming.openings);
          s.roads = castDraft(incoming.roads);
          s.stairs = castDraft(incoming.stairs ?? {});
          s.pillars = castDraft(incoming.pillars ?? {});
          s.beams = castDraft(incoming.beams ?? {});
          s.deckSlabs = castDraft(incoming.deckSlabs ?? {});
          delete s.floorData[fallback.id];
          delete s.floorData[id];
          s.activeFloorId = fallback.id;
          s.floors = s.floors.filter((f) => f.id !== id);
          s.selectedIds = [];
        });
        get().clearHistory();
      } else {
        set((s) => {
          delete s.floorData[id];
          s.floors = s.floors.filter((f) => f.id !== id);
        });
      }
    },

    setActiveFloor: (id) => {
      const state = get();
      if (state.activeFloorId === id) return;
      if (!state.floors.some((f) => f.id === id)) return;
      const parked = readWorkingGeometry(state);
      const incoming = state.floorData[id] ?? emptyFloorGeometry();
      set((s) => {
        s.floorData[s.activeFloorId] = castDraft(parked);
        s.vertices = castDraft(incoming.vertices);
        s.walls = castDraft(incoming.walls);
        s.rooms = castDraft(incoming.rooms);
        s.furniture = castDraft(incoming.furniture);
        s.openings = castDraft(incoming.openings);
        s.roads = castDraft(incoming.roads);
        s.stairs = castDraft(incoming.stairs ?? {});
        s.pillars = castDraft(incoming.pillars ?? {});
        s.beams = castDraft(incoming.beams ?? {});
        s.deckSlabs = castDraft(incoming.deckSlabs ?? {});
        delete s.floorData[id];
        s.activeFloorId = id;
        s.selectedIds = [];
      });
      // Undo history is per-floor; mixing floors in one stack would restore the wrong floor.
      get().clearHistory();
    },

    renameFloor: (id, name) => {
      set((s) => {
        const floor = s.floors.find((f) => f.id === id);
        if (floor) floor.name = name;
      });
    },

    resetFloors: () => {
      const id = generateId('floor');
      set((s) => {
        s.floors = [{ id, name: 'Ground Floor', elevationCm: 0 }];
        s.activeFloorId = id;
        s.floorData = {};
      });
    },
  };
};
