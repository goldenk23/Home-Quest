// src/store/persistence/migrations.ts

import type { EntityId, Vertex, Wall, Room, FurnitureItem } from '@/types';

/** Bump this whenever the persisted shape changes. */
export const CURRENT_SCHEMA_VERSION = 3;

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
export type PersistedState = PersistedStateV3;

/** Upgrades any older persisted blob to the current shape. Each step is idempotent. */
export function migrateState(state: any): PersistedState {
  let current = state;
  if (!current.version || current.version < 2) current = migrateV1ToV2(current);
  if (current.version < 3) current = migrateV2ToV3(current);
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
