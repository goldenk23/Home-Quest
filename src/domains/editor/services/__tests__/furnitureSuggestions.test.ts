import { describe, it, expect } from 'vitest';
import { suggestFurniture } from '../furnitureSuggestions';

describe('suggestFurniture', () => {
  it('suggests kitchen items for a kitchen room type', () => {
    const items = suggestFurniture({ roomType: 'kitchen', label: 'Kitchen' });
    expect(items).toContain('stove');
    expect(items).toContain('fridge');
  });

  it('infers type from a Hindi label when roomType is custom ("rasoi" -> kitchen)', () => {
    const items = suggestFurniture({ roomType: 'custom', label: 'Rasoi' });
    expect(items).toContain('stove');
  });

  it('returns an empty list for a type with no suggestions', () => {
    expect(suggestFurniture({ roomType: 'garage', label: '' })).toEqual([]);
  });
});
