// src/domains/editor/hooks/useCollisions.ts

import { useMemo } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useAppStore } from '@/store';
import type { EntityId, FurnitureItem } from '@/types/editor';
import {
  SpatialHashGrid,
  furnitureToAABB,
  checkFurnitureCollisions,
} from '../services/collision';

/**
 * Returns the set of furniture ids that currently overlap at least one other piece.
 *
 * This is the live wiring for the Part 12 collision engine: it builds a spatial hash
 * grid from every placed item, runs broad-phase + SAT narrow-phase, and returns the ids
 * of everything involved in a collision so the 2D and 3D layers can highlight them red.
 *
 * The grid cell size (300cm) is comfortably larger than the biggest catalog item so
 * overlapping pieces always share a cell.
 */
export function useCollidingFurnitureIds(): Set<EntityId> {
  const furniture = useAppStore(useShallow((s) => Object.values(s.furniture)));

  return useMemo(() => {
    const grid = new SpatialHashGrid(300);
    const byId: Record<string, FurnitureItem> = {};
    for (const item of furniture) {
      byId[item.id] = item;
      grid.insert(item.id, furnitureToAABB(item));
    }

    const colliding = new Set<EntityId>();
    for (const item of furniture) {
      const hits = checkFurnitureCollisions(item, byId, [], {}, grid);
      if (hits.length > 0) {
        colliding.add(item.id);
        for (const id of hits) colliding.add(id);
      }
    }
    return colliding;
  }, [furniture]);
}
