// src/store/persistence/fileIO.ts

import { useAppStore } from '@/store';
import { type PersistedState, CURRENT_SCHEMA_VERSION, migrateState } from './migrations';
import { validateFloorPlanIntegrity } from './validation';

/** Downloads the current plan as a JSON file. */
export function exportFloorPlan(filename = 'floorplan.hq.json'): void {
  const state = useAppStore.getState();
  const exportData: PersistedState = {
    version: CURRENT_SCHEMA_VERSION,
    vertices: state.vertices,
    walls: state.walls,
    rooms: state.rooms,
    furniture: state.furniture,
    openings: state.openings,
    roads: state.roads,
    floors: state.floors,
    activeFloorId: state.activeFloorId,
    floorData: state.floorData,
    metadata: { name: filename.replace('.hq.json', ''), createdAt: new Date().toISOString(), lastModifiedAt: new Date().toISOString(), authorId: null },
    settings: { gridSize: 10, wallThickness: 20, wallHeight: 280, measurementUnit: 'cm' },
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** Reads, migrates, validates, then applies a plan file. Returns success + any error. */
export async function importFloorPlan(file: File): Promise<{ success: boolean; error?: string }> {
  try {
    const raw = JSON.parse(await file.text());
    const migrated = migrateState(raw);

    const validation = validateFloorPlanIntegrity(migrated);
    if (!validation.valid) return { success: false, error: validation.errors.join('; ') };

    useAppStore.setState({
      vertices: migrated.vertices,
      walls: migrated.walls,
      rooms: migrated.rooms,
      furniture: migrated.furniture,
      openings: migrated.openings ?? {},
      roads: migrated.roads ?? {},
      floors: migrated.floors,
      activeFloorId: migrated.activeFloorId,
      floorData: migrated.floorData ?? {},
    });
    useAppStore.getState().clearHistory(); // imported plan is a fresh baseline
    useAppStore.getState().requestFitView(); // center the imported plan in the editor

    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof SyntaxError ? 'Invalid JSON file' : (error as Error).message,
    };
  }
}
