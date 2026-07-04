import { useCallback, useMemo } from 'react';
import { useAppStore } from '@/store';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import type { Point2D } from '@/types/geometry';
import { generateArrayPositions } from '../services/arrayPlacement';
import { computeBuildingBounds, type BuildingGeometry } from '../services/buildingClone';
import { computeComponentBounds, type ComponentCloneGeometry } from '../services/componentClone';

/** The building's plan-space reference point (its bounding-box center), or null when the
 *  plan is empty. Used as the array origin for building mode so the copies line up with the
 *  actual construction instead of the cursor. */
function buildingOrigin(g: BuildingGeometry): Point2D | null {
  return computeBuildingBounds(g)?.center ?? null;
}

/** The selected component's plan-space reference point (its bounding-box center), or null. */
function componentOrigin(componentId: string | null, g: ComponentCloneGeometry): Point2D | null {
  if (!componentId) return null;
  return computeComponentBounds(componentId, g)?.center ?? null;
}

/**
 * @param cursor Current mouse position in world space (used as the origin for cursor-anchored modes).
 * @param componentDragOffset World-space offset applied to the component-mode preview origin while
 *        the user drags the ghost array away from the source entity. Null = anchored on the source.
 */
export function useArrayTool(cursor: Point2D | null, componentDragOffset: Point2D | null = null) {
  const activeTool = useAppStore((s) => s.activeTool);
  const arrayConfig = useAppStore((s) => s.arrayConfig);
  const setArrayConfig = useAppStore((s) => s.setArrayConfig);
  const furniture = useAppStore((s) => s.furniture);
  const pillars = useAppStore((s) => s.pillars);
  // Building array previews from the building's own center, not the cursor.
  const vertices = useAppStore((s) => s.vertices);
  const deckSlabs = useAppStore((s) => s.deckSlabs);
  const beams = useAppStore((s) => s.beams);
  const railings = useAppStore((s) => s.railings);

  const walls = useAppStore((s) => s.walls);
  const roads = useAppStore((s) => s.roads);
  const openings = useAppStore((s) => s.openings);

  /** The world-space point the preview array starts from, per the active mode. */
  const previewOrigin = useMemo((): Point2D | null => {
    if (activeTool !== 'array' || !arrayConfig.entityType) return null;
    if (arrayConfig.entityType === 'building') {
      return buildingOrigin({ vertices, walls: {}, rooms: {}, openings: {}, pillars, beams, deckSlabs, railings, furniture } as BuildingGeometry);
    }
    if (arrayConfig.entityType === 'component') {
      const g: ComponentCloneGeometry = { vertices, walls, openings, pillars, beams, deckSlabs, railings, furniture, roads };
      const center = componentOrigin(arrayConfig.referenceId, g);
      if (!center) return null;
      return componentDragOffset
        ? { x: center.x + componentDragOffset.x, y: center.y + componentDragOffset.y }
        : center;
    }
    return cursor;
  }, [activeTool, arrayConfig, cursor, componentDragOffset, vertices, pillars, beams, deckSlabs, railings, furniture, walls, roads, openings]);

  const previewItems = useMemo(() => {
    if (activeTool !== 'array' || !arrayConfig.isPreviewing || !arrayConfig.entityType || !previewOrigin) return [];
    return generateArrayPositions(previewOrigin, arrayConfig);
  }, [activeTool, arrayConfig, previewOrigin]);

  const commitAt = useCallback((clickOrigin: Point2D): string[] => {
    const state = useAppStore.getState();
    const config = state.arrayConfig;
    if (state.activeTool !== 'array' || !config.entityType || !config.isPreviewing) return [];

    // Building mode arrays the existing construction from its own center; every other mode
    // places new items starting at the click point.
    const origin = config.entityType === 'building'
      ? buildingOrigin({
          vertices: state.vertices, walls: state.walls, rooms: state.rooms, openings: state.openings,
          pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
          railings: state.railings, furniture: state.furniture,
        })
      : clickOrigin;
    if (!origin) return [];

    const positions = generateArrayPositions(origin, config);
    const createdIds: string[] = [];

    state.recordHistory('Place Array', () => {
      if (config.entityType === 'furniture') {
        const catalogId = config.referenceId ?? state.furnitureCatalogId;
        const entry = getCatalogEntry(catalogId);
        for (const item of positions) {
          const id = state.addFurniture({
            position: item.position,
            rotation: config.angle,
            scale: 1,
            catalogId,
            roomId: null,
            bounds: { width: entry.bounds.width, depth: entry.bounds.depth },
          });
          if (id) createdIds.push(id);
        }
      } else if (config.entityType === 'pillar') {
        for (const item of positions) {
          const id = state.addPillar({
            position: item.position,
            width: 35,
            depth: 35,
            height: 300,
            elevationCm: 0,
            shape: 'rect',
            materialId: 'paint-white',
          });
          if (id) createdIds.push(id);
        }
      } else if (config.entityType === 'building') {
        // Index 0 is the existing building; only offsets 1..count-1 are cloned. Each offset
        // is the array vector times its index, measured from the building's own origin.
        const base = positions[0]?.position;
        if (base) {
          const offsets = positions.slice(1).map((p) => ({ x: p.position.x - base.x, y: p.position.y - base.y }));
          if (offsets.length > 0) createdIds.push(...state.duplicateBuilding(offsets));
        }
      } else if (config.entityType === 'component') {
        const componentId = config.referenceId;
        if (componentId) {
          // Offsets are measured from the SOURCE entity's own center so the clones land
          // exactly where the preview ghosts sit — even after the ghost array has been
          // dragged away from the source. A near-zero offset would clone the component
          // exactly on top of the original, so that slot is skipped (it's the original).
          const g: ComponentCloneGeometry = {
            vertices: state.vertices, walls: state.walls, openings: state.openings,
            pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
            railings: state.railings, furniture: state.furniture, roads: state.roads,
          };
          const center = componentOrigin(componentId, g);
          if (center) {
            const offsets = positions
              .map((p) => ({ x: p.position.x - center.x, y: p.position.y - center.y }))
              .filter((o) => Math.hypot(o.x, o.y) > 0.5);
            if (offsets.length > 0) createdIds.push(...state.duplicateComponent(componentId, offsets));
          }
        }
      }

      if (createdIds.length > 0) state.select(createdIds);
    });

    return createdIds;
  }, []);

  const cancel = useCallback(() => {
    setArrayConfig({ isPreviewing: false });
  }, [setArrayConfig]);

  /** Human-readable label for the current array source entity (component mode), or null. */
  const sourceLabel = useMemo(() => {
    if (arrayConfig.entityType !== 'component') return null;
    const id = arrayConfig.referenceId;
    if (!id) return null;
    if (furniture[id]) return getCatalogEntry(furniture[id].catalogId).label;
    if (pillars[id]) return 'Pillar';
    if (walls[id]) return 'Wall';
    if (beams[id]) return 'Beam';
    if (deckSlabs[id]) return 'Deck';
    if (railings[id]) return 'Railing';
    if (roads[id]) return 'Road';
    return null;
  }, [arrayConfig.entityType, arrayConfig.referenceId, furniture, pillars, walls, beams, deckSlabs, railings, roads]);

  return {
    previewItems,
    previewOrigin,
    commitAt,
    cancel,
    sourceLabel,
  };
}
