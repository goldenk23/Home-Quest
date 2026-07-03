// src/store/persistence/migrations.ts

import type { EntityId, Vertex, Wall, Room, FurnitureItem, Floor, FloorGeometry, Pillar, Beam, DeckSlab, Railing } from '@/types';

/** Bump this whenever the persisted shape changes. */
export const CURRENT_SCHEMA_VERSION = 8;

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
export interface PersistedStateV5 extends Omit<PersistedStateV4, 'version'> {
  version: 5;
  pillars: Record<EntityId, Pillar>;
}
export interface PersistedStateV6 extends Omit<PersistedStateV5, 'version'> {
  version: 6;
  beams: Record<EntityId, Beam>;
}
export interface PersistedStateV7 extends Omit<PersistedStateV6, 'version'> {
  version: 7;
  deckSlabs: Record<EntityId, DeckSlab>;
}
export interface PersistedStateV8 extends Omit<PersistedStateV7, 'version'> {
  version: 8;
  railings: Record<EntityId, Railing>;
}
export type PersistedState = PersistedStateV8;

/** Upgrades any older persisted blob to the current shape. Each step is idempotent. */
export function migrateState(state: any): PersistedState {
  let current = state;
  if (!current.version || current.version < 2) current = migrateV1ToV2(current);
  if (current.version < 3) current = migrateV2ToV3(current);
  if (current.version < 4) current = migrateV3ToV4(current);
  if (current.version < 5) current = migrateV4ToV5(current);
  if (current.version < 6) current = migrateV5ToV6(current);
  if (current.version < 7) current = migrateV6ToV7(current);
  if (current.version < 8) current = migrateV7ToV8(current);
  return current as PersistedState;
}

/** v8: introduce safety railings/parapets. */
function migrateV7ToV8(state: PersistedStateV7): PersistedStateV8 {
  const floorData: Record<EntityId, FloorGeometry> = {};
  for (const [id, geo] of Object.entries(state.floorData ?? {})) {
    floorData[id] = { ...geo, railings: (geo as Partial<FloorGeometry>).railings ?? {} };
  }
  return {
    ...state,
    version: 8,
    railings: (state as unknown as { railings?: Record<EntityId, Railing> }).railings ?? {},
    floorData,
  };
}

/** v7: introduce custom deck/corridor/balcony slab polygons. */
function migrateV6ToV7(state: PersistedStateV6): PersistedStateV7 {
  const floorData: Record<EntityId, FloorGeometry> = {};
  for (const [id, geo] of Object.entries(state.floorData ?? {})) {
    floorData[id] = { ...geo, deckSlabs: (geo as Partial<FloorGeometry>).deckSlabs ?? {} };
  }
  return {
    ...state,
    version: 7,
    deckSlabs: (state as unknown as { deckSlabs?: Record<EntityId, DeckSlab> }).deckSlabs ?? {},
    floorData,
  };
}

/** v6: introduce standalone horizontal structural beams. */
function migrateV5ToV6(state: PersistedStateV5): PersistedStateV6 {
  const floorData: Record<EntityId, FloorGeometry> = {};
  for (const [id, geo] of Object.entries(state.floorData ?? {})) {
    floorData[id] = { ...geo, beams: (geo as Partial<FloorGeometry>).beams ?? {} };
  }
  return {
    ...state,
    version: 6,
    beams: (state as unknown as { beams?: Record<EntityId, Beam> }).beams ?? {},
    floorData,
  };
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

/** v5: introduce standalone structural pillars/columns. */
function migrateV4ToV5(state: PersistedStateV4): PersistedStateV5 {
  const floorData: Record<EntityId, FloorGeometry> = {};
  for (const [id, geo] of Object.entries(state.floorData ?? {})) {
    floorData[id] = { ...geo, pillars: (geo as Partial<FloorGeometry>).pillars ?? {} };
  }
  return {
    ...state,
    version: 5,
    pillars: (state as unknown as { pillars?: Record<EntityId, Pillar> }).pillars ?? {},
    floorData,
  };
}
