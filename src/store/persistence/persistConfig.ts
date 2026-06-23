// src/store/persistence/persistConfig.ts

import type { StateStorage } from 'zustand/middleware';
import { get, set, del } from 'idb-keyval';

/**
 * IndexedDB-backed storage for Zustand's persist middleware. Chosen over localStorage:
 * no ~5MB cap, async (won't block the main thread), and works in workers.
 */
export const indexedDBStorage: StateStorage = {
  getItem: async (name) => {
    try {
      return (await get(name)) ?? null;
    } catch (error) {
      console.error('[Persistence] read failed:', error);
      return null;
    }
  },
  setItem: async (name, value) => {
    try {
      await set(name, value);
    } catch (error) {
      console.error('[Persistence] write failed:', error);
    }
  },
  removeItem: async (name) => {
    try {
      await del(name);
    } catch (error) {
      console.error('[Persistence] delete failed:', error);
    }
  },
};
