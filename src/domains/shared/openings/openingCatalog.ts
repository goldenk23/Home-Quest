// src/domains/shared/openings/openingCatalog.ts
//
// Single source of truth for every KIND of wall opening the user can place: doors (incl.
// the main gate), the different window types, the ventilation variants, and wall-mounted
// ACs. Deliberately framework-free (no THREE, no React) so the editor (tools, 2D layer),
// the store (presets), and the viewer (3D meshes) can all share one vocabulary.
//
// Each kind maps to a base behaviour `type` (stored on `Opening.type`) that decides how it
// interacts with the wall geometry:
//   - 'door'   → cut as a floor-to-head notch (you can walk through it)
//   - 'window' → punched as a hole at an elevation
//   - 'vent'   → punched as a small high hole
//   - 'ac'     → NOT cut at all; mounted on the wall surface
// The `kind` id is stored alongside on `Opening.kind` and drives the detailed look.

import type { OpeningType } from '@/types/editor';

/** A family groups the kinds a single placement tool offers. Matches the tool name. */
export type OpeningFamily = 'door' | 'window' | 'vent' | 'ac';

/** Window glazing layout, used by the 3D renderer. */
export interface WindowStyle {
  /** Number of glass panes. */
  readonly panels: number;
  /** Whether panes are split left↔right (horizontal) or stacked (vertical). */
  readonly orientation: 'horizontal' | 'vertical';
}

export interface OpeningKind {
  /** Stable id — also stored on `Opening.kind`. */
  readonly id: string;
  /** Which tool/family offers this kind. */
  readonly family: OpeningFamily;
  /** Base behaviour written to `Opening.type` (controls the wall cut). */
  readonly type: OpeningType;
  /** Human label shown in the picker. */
  readonly label: string;
  /** Small emoji for the picker button. */
  readonly icon: string;
  /** Default size + elevation presets in centimeters. */
  readonly width: number;
  readonly height: number;
  readonly elevation: number;
  /** 2D editor fill/swatch colour. */
  readonly color: string;
  /** Window-only: glazing layout. */
  readonly window?: WindowStyle;
  /** Vent-only: how it renders in 3D. */
  readonly vent?: 'louvre' | 'exhaust';
  /** Door-only: 'open' = empty doorway, 'gate' = framed gate panel, 'shutter' = roller/sectional garage shutter. */
  readonly door?: 'open' | 'gate' | 'shutter';
}

export const OPENING_KINDS: readonly OpeningKind[] = [
  // ---- Doors --------------------------------------------------------------
  { id: 'door-standard', family: 'door', type: 'door', label: 'Door', icon: '🚪', width: 90, height: 210, elevation: 0, color: '#ca8a04', door: 'open' },
  { id: 'door-room-blue', family: 'door', type: 'door', label: 'Room Door (Blue)', icon: '🚪', width: 90, height: 210, elevation: 0, color: '#2563eb', door: 'open' },
  { id: 'door-double', family: 'door', type: 'door', label: 'Double Door', icon: '🚪', width: 150, height: 215, elevation: 0, color: '#ca8a04', door: 'open' },
  { id: 'door-main-gate', family: 'door', type: 'door', label: 'Main Gate', icon: '🏛️', width: 160, height: 240, elevation: 0, color: '#92400e', door: 'gate' },
  { id: 'garage-shutter', family: 'door', type: 'door', label: 'Garage Shutter', icon: '🚧', width: 260, height: 220, elevation: 0, color: '#64748b', door: 'shutter' },

  // ---- Windows ------------------------------------------------------------
  { id: 'window-standard', family: 'window', type: 'window', label: 'Standard', icon: '🪟', width: 120, height: 120, elevation: 90, color: '#93c5fd', window: { panels: 2, orientation: 'horizontal' } },
  { id: 'window-large', family: 'window', type: 'window', label: 'Picture (Large)', icon: '🪟', width: 220, height: 150, elevation: 75, color: '#93c5fd', window: { panels: 1, orientation: 'horizontal' } },
  { id: 'window-sliding', family: 'window', type: 'window', label: 'Sliding', icon: '🪟', width: 180, height: 130, elevation: 85, color: '#93c5fd', window: { panels: 3, orientation: 'horizontal' } },
  { id: 'window-slit', family: 'window', type: 'window', label: 'Slit (Narrow)', icon: '🪟', width: 50, height: 140, elevation: 90, color: '#93c5fd', window: { panels: 1, orientation: 'vertical' } },
  { id: 'window-clerestory', family: 'window', type: 'window', label: 'Clerestory (High)', icon: '🪟', width: 150, height: 50, elevation: 200, color: '#93c5fd', window: { panels: 3, orientation: 'horizontal' } },

  // ---- Ventilation --------------------------------------------------------
  { id: 'vent-normal', family: 'vent', type: 'vent', label: 'Normal', icon: '💨', width: 60, height: 30, elevation: 220, color: '#5eead4', vent: 'louvre' },
  { id: 'vent-kitchen', family: 'vent', type: 'vent', label: 'Kitchen', icon: '🍳', width: 75, height: 55, elevation: 190, color: '#fcd34d', vent: 'louvre' },
  { id: 'vent-washroom', family: 'vent', type: 'vent', label: 'Washroom', icon: '🚿', width: 45, height: 40, elevation: 200, color: '#7dd3fc', vent: 'louvre' },
  { id: 'vent-exhaust', family: 'vent', type: 'vent', label: 'Exhaust Fan', icon: '🌀', width: 35, height: 35, elevation: 210, color: '#cbd5e1', vent: 'exhaust' },

  // ---- Air conditioner (wall-mounted, no cut) -----------------------------
  { id: 'ac-split', family: 'ac', type: 'ac', label: 'Split AC', icon: '❄️', width: 90, height: 30, elevation: 205, color: '#f1f5f9' },
];

const KIND_INDEX: ReadonlyMap<string, OpeningKind> = new Map(OPENING_KINDS.map((k) => [k.id, k]));

/** Lookup a kind by id; null when unknown. */
export function getOpeningKind(id: string | undefined): OpeningKind | null {
  return id ? KIND_INDEX.get(id) ?? null : null;
}

/** All kinds offered by a family, in catalog order. */
export function kindsForFamily(family: OpeningFamily): OpeningKind[] {
  return OPENING_KINDS.filter((k) => k.family === family);
}

/** The default (first) kind id for a family. */
export function defaultKindForFamily(family: OpeningFamily): string {
  return kindsForFamily(family)[0]?.id ?? 'door-standard';
}

/**
 * Resolve the kind for an opening that may predate the kinds system (no `kind` stored):
 * fall back to the first kind whose base `type` matches, so old plans still render sanely.
 */
export function resolveKind(kindId: string | undefined, type: OpeningType): OpeningKind {
  const direct = getOpeningKind(kindId);
  if (direct) return direct;
  return OPENING_KINDS.find((k) => k.type === type) ?? OPENING_KINDS[0];
}
