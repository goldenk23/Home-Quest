import { useCallback, useEffect, useMemo } from 'react';
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

export function useArrayTool(cursor: Point2D | null) {
  const activeTool = useAppStore((s) => s.activeTool);
  const arrayConfig = useAppStore((s) => s.arrayConfig);
  const setArrayConfig = useAppStore((s) => s.setArrayConfig);
  const selectedIds = useAppStore((s) => s.selectedIds);
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

  // If the replication source is deleted while the tool is active, clear the source
  // (keep the chosen entity type so the user can pick another).
  useEffect(() => {
    if (activeTool !== 'array' || !arrayConfig.referenceId) return;
    const g: ComponentCloneGeometry = { vertices, walls, openings, pillars, beams, deckSlabs, railings, furniture, roads };
    if (!computeComponentBounds(arrayConfig.referenceId, g)) {
      setArrayConfig({ referenceId: null });
    }
  }, [activeTool, arrayConfig.referenceId, vertices, walls, openings, pillars, beams, deckSlabs, railings, furniture, roads, setArrayConfig]);

  const previewItems = useMemo(() => {
    if (activeTool !== 'array' || !arrayConfig.isPreviewing || !arrayConfig.entityType) return [];
    if (arrayConfig.entityType === 'building') {
      // Original + `count` replicas, anchored at the building's own center.
      const origin = buildingOrigin({ vertices, walls: {}, rooms: {}, openings: {}, pillars, beams, deckSlabs, railings, furniture } as BuildingGeometry);
      if (!origin) return [];
      return generateArrayPositions(origin, { ...arrayConfig, count: arrayConfig.count + 1 });
    }
    // Pillar/furniture: no preview until a source is picked; then the replicas follow the cursor.
    if (!arrayConfig.referenceId || !cursor) return [];
    return generateArrayPositions(cursor, arrayConfig);
  }, [activeTool, arrayConfig, cursor, vertices, pillars, beams, deckSlabs, railings, furniture, walls, roads, openings]);

  const commitAt = useCallback((clickOrigin: Point2D): string[] => {
    const state = useAppStore.getState();
    const config = state.arrayConfig;
    if (state.activeTool !== 'array' || !config.entityType || !config.isPreviewing) return [];

    const createdIds: string[] = [];

    state.recordHistory('Place Array', () => {
      if (config.entityType === 'building') {
        // The building is arrayed from its own center: `count` replicas at offsets 1..count
        // along the array vector.
        const origin = buildingOrigin({
          vertices: state.vertices, walls: state.walls, rooms: state.rooms, openings: state.openings,
          pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
          railings: state.railings, furniture: state.furniture,
        });
        if (!origin) return;
        const positions = generateArrayPositions(origin, { ...config, count: config.count + 1 });
        const base = positions[0]?.position;
        if (base) {
          const offsets = positions.slice(1).map((p) => ({ x: p.position.x - base.x, y: p.position.y - base.y }));
          if (offsets.length > 0) createdIds.push(...state.duplicateBuilding(offsets));
        }
      } else {
        // Pillar/furniture: clone the picked source at the click point. Every generated
        // position is a replica, so count=1 places exactly one copy at the cursor.
        const componentId = config.referenceId;
        if (!componentId) return;
        const g: ComponentCloneGeometry = {
          vertices: state.vertices, walls: state.walls, openings: state.openings,
          pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
          railings: state.railings, furniture: state.furniture, roads: state.roads,
        };
        const sourceCenter = componentOrigin(componentId, g);
        if (!sourceCenter) return;
        const positions = generateArrayPositions(clickOrigin, config);
        const offsets = positions.map((p) => ({ x: p.position.x - sourceCenter.x, y: p.position.y - sourceCenter.y }));
        if (offsets.length > 0) createdIds.push(...state.duplicateComponent(componentId, offsets));
      }

      if (createdIds.length > 0) state.select(createdIds);
    });

    return createdIds;
  }, []);

  const cancel = useCallback(() => {
    setArrayConfig({ isPreviewing: false });
  }, [setArrayConfig]);

  const selectedReferenceLabel = useMemo(() => {
    const id = selectedIds[0];
    if (id && furniture[id]) return getCatalogEntry(furniture[id].catalogId).label;
    if (id && pillars[id]) return 'Selected pillar';
    if (id && walls[id]) return 'Selected wall';
    if (id && beams[id]) return 'Selected beam';
    if (id && deckSlabs[id]) return 'Selected deck';
    if (id && railings[id]) return 'Selected railing';
    if (id && roads[id]) return 'Selected road';
    return null;
  }, [furniture, pillars, selectedIds, walls, beams, deckSlabs, railings, roads]);

  return {
    previewItems,
    commitAt,
    cancel,
    selectedReferenceLabel,
  };
}
