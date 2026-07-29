// src/domains/editor/services/furnitureSuggestions.ts

import type { RoomType } from '@/types/editor';

/**
 * Room-aware furniture suggestions. A plain static lookup keyed by room type, with a small
 * alias table so free-text labels (including common Hindi words like "rasoi"/"baithak") map to
 * a type. Catalog ids are the web ids from `useAssetLoader`'s FURNITURE_CATALOG.
 *
 * ponytail: intentional simplification — the Python editor uses TF-IDF; for this fixed, tiny
 * vocabulary a lookup table is equivalent and far cheaper. Upgrade path: swap `suggestFurniture`
 * for a scored matcher if the catalog/vocabulary grows large.
 */

/** Suggested catalog ids per room type (ordered by usefulness). */
const BY_ROOM_TYPE: Record<RoomType, string[]> = {
  bedroom: ['bed-queen', 'wardrobe', 'nightstand', 'desk'],
  living: ['sofa-3seat', 'armchair', 'coffee-table', 'tv-unit', 'rug'],
  kitchen: ['kitchen-counter', 'stove', 'fridge', 'vanity'],
  bathroom: ['toilet', 'bathtub', 'shower', 'vanity'],
  dining: ['dining-table', 'dining-chair', 'sideboard'],
  study: ['desk', 'chair-office', 'bookshelf'],
  puja: [],
  storage: ['wardrobe', 'sideboard'],
  garage: [],
  balcony: ['plant', 'shrub'],
  entrance: ['sideboard', 'plant'],
  corridor: [],
  custom: [],
};

/** Keyword/alias (English + Hindi) → room type, matched against a room's label tokens. */
const LABEL_ALIASES: Record<string, RoomType> = {
  rasoi: 'kitchen', kitchen: 'kitchen',
  baithak: 'living', living: 'living', hall: 'living', drawing: 'living', lounge: 'living',
  washroom: 'bathroom', bathroom: 'bathroom', toilet: 'bathroom', bath: 'bathroom',
  bedroom: 'bedroom', shayan: 'bedroom', master: 'bedroom',
  dining: 'dining', bhojan: 'dining',
  study: 'study', office: 'study',
  puja: 'puja', pooja: 'puja', mandir: 'puja',
  balcony: 'balcony',
  store: 'storage', storage: 'storage', bhandar: 'storage',
  garage: 'garage', parking: 'garage',
  entrance: 'entrance', foyer: 'entrance',
};

/**
 * Returns suggested catalog ids for a room. Uses the explicit `roomType`; when that is
 * 'custom', infers a type from label keywords (so "Rasoi"/"Baithak" still get sensible items).
 */
export function suggestFurniture(room: { roomType: RoomType; label: string }): string[] {
  let type: RoomType = room.roomType;
  if (type === 'custom' && room.label) {
    for (const token of room.label.toLowerCase().split(/[^a-z]+/)) {
      if (LABEL_ALIASES[token]) {
        type = LABEL_ALIASES[token];
        break;
      }
    }
  }
  return BY_ROOM_TYPE[type] ?? [];
}
