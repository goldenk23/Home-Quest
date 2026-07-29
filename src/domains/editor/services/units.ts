// src/domains/editor/services/units.ts

/**
 * Unit system for the 2D editor. World geometry is ALWAYS stored in centimeters (see the
 * architecture invariants). These helpers convert to/from a user-chosen display unit and
 * format lengths/areas for the UI (dimensions, grid labels, HUD, property panels).
 *
 * Port of the Python editor's `unit_scale` / `set_unit` concept, but the store stays cm-only —
 * only the presentation layer is unit-aware.
 */

export type DisplayUnit = 'cm' | 'm' | 'ft' | 'in';

/** Centimeters per one unit. Multiply a value-in-unit by this to get cm. */
export const CM_PER_UNIT: Record<DisplayUnit, number> = {
  cm: 1,
  m: 100,
  ft: 30.48,
  in: 2.54,
};

/** Convert a value expressed in `unit` into centimeters (for typed numeric input). */
export function toCm(value: number, unit: DisplayUnit): number {
  return value * CM_PER_UNIT[unit];
}

/** Convert a centimeter value into `unit` (raw number, no formatting). */
export function fromCm(cm: number, unit: DisplayUnit): number {
  return cm / CM_PER_UNIT[unit];
}

/**
 * Format a centimeter length as a display string in the active unit.
 * cm is rounded to whole cm; other units use `digits` decimals.
 */
export function formatLength(cm: number, unit: DisplayUnit, digits = 2): string {
  switch (unit) {
    case 'cm':
      return `${Math.round(cm)} cm`;
    case 'm':
      return `${fromCm(cm, 'm').toFixed(digits)} m`;
    case 'ft':
      return `${fromCm(cm, 'ft').toFixed(digits)} ft`;
    case 'in':
      return `${fromCm(cm, 'in').toFixed(digits)} in`;
  }
}

/**
 * Format an area given in square centimeters. Metric units read as m², imperial as ft²,
 * mirroring the Python editor's area readout.
 */
export function formatArea(cm2: number, unit: DisplayUnit, digits = 2): string {
  if (unit === 'ft' || unit === 'in') {
    const ft2 = cm2 / (CM_PER_UNIT.ft * CM_PER_UNIT.ft); // 929.0304 cm² per ft²
    return `${ft2.toFixed(digits)} ft²`;
  }
  const m2 = cm2 / (CM_PER_UNIT.m * CM_PER_UNIT.m); // 10000 cm² per m²
  return `${m2.toFixed(digits)} m²`;
}
