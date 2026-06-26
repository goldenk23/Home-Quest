// src/store/persistence/migrations.ts

import type { EntityId, Vertex, Wall, Room, FurnitureItem, Floor, FloorGeometry } from '@/types';

/** Bump this whenever the persisted shape changes. */
export const CURRENT_SCHEMA_VERSION = 4;

export interface PersistedStateV1 {
  version: 1;
  vertices: Record<EntityId, Vertex>;
  walls: Record<EntityId, Wall>;
  rooms: Record<EntityId, Room>;
}
export interface PersistedStateV2 extends Omit<PersistedStateV1, 'version'> {
  version: 2;
  furniture: Record<EntityId, FurnitureItem>;
}
export interface PersistedStateV3 extends Omit<PersistedStateV2, 'version'> {
  version: 3;
  metadata: { name: string; createdAt: string; lastModifiedAt: string; authorId: string | null };
  settings: { gridSize: number; wallThickness: number; wallHeight: number; measurementUnit: 'cm' | 'ft' | 'in' };
}
export interface PersistedStateV4 extends Omit<PersistedStateV3, 'version'> {
  version: 4;
  openings: Record<EntityId, import('@/types/editor').Opening>;
  roads: Record<EntityId, import('@/types/editor').Road>;
  /** Multi-storey: the active floor lives in the flat maps; others are parked here. */
  floors: Floor[];
  activeFloorId: EntityId;
  floorData: Record<EntityId, FloorGeometry>;
}
export type PersistedState = PersistedStateV4;

/** Upgrades any older persisted blob to the current shape. Each step is idempotent. */
export function migrateState(state: any): PersistedState {
  let current = state;
  if (!current.version || current.version < 2) current = migrateV1ToV2(current);
  if (current.version < 3) current = migrateV2ToV3(current);
  if (current.version < 4) current = migrateV3ToV4(current);
  return current as PersistedState;
}

function migrateV1ToV2(state: PersistedStateV1): PersistedStateV2 {
  return { ...state, version: 2, furniture: {} };
}

function migrateV2ToV3(state: PersistedStateV2): PersistedStateV3 {
  return {
    ...state,
    version: 3,
    metadata: { name: 'Untitled Floor Plan', createdAt: new Date().toISOString(), lastModifiedAt: new Date().toISOString(), authorId: null },
    settings: { gridSize: 10, wallThickness: 20, wallHeight: 280, measurementUnit: 'cm' },
  };
}

/** v4: introduce storeys. The existing single plan becomes the ground floor. */
function migrateV3ToV4(state: PersistedStateV3): PersistedStateV4 {
  const groundId = `floor-${Date.now()}-ground`;
  const anyState = state as any;
  return {
    ...state,
    version: 4,
    openings: anyState.openings ?? {},
    roads: anyState.roads ?? {},
    floors: [{ id: groundId, name: 'Ground Floor', elevationCm: 0 }],
    activeFloorId: groundId,
    floorData: {},
  };
}
