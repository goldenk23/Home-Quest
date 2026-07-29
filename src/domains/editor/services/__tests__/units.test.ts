import { describe, it, expect } from 'vitest';
import { toCm, fromCm, formatLength, formatArea } from '../units';

describe('units conversion', () => {
  it('round-trips cm <-> unit for every unit', () => {
    for (const unit of ['cm', 'm', 'ft', 'in'] as const) {
      expect(toCm(fromCm(1234, unit), unit)).toBeCloseTo(1234, 6);
    }
  });

  it('100 cm equals 1 m equals ~3.281 ft', () => {
    expect(fromCm(100, 'm')).toBeCloseTo(1, 6);
    expect(fromCm(100, 'ft')).toBeCloseTo(3.281, 3);
    expect(fromCm(100, 'in')).toBeCloseTo(39.3701, 3);
  });
});

describe('formatLength', () => {
  it('rounds cm to whole cm', () => {
    expect(formatLength(349.6, 'cm')).toBe('350 cm');
  });
  it('formats metres/feet with 2 decimals by default', () => {
    expect(formatLength(350, 'm')).toBe('3.50 m');
    expect(formatLength(304.8, 'ft')).toBe('10.00 ft');
  });
});

describe('formatArea', () => {
  it('reports m² for metric units', () => {
    expect(formatArea(10000, 'm')).toBe('1.00 m²'); // 100cm x 100cm
  });
  it('reports ft² for imperial units', () => {
    expect(formatArea(929.0304, 'ft')).toBe('1.00 ft²');
  });
});
