import { useCallback, useMemo } from 'react';
import { useAppStore } from '@/store';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import type { Point2D } from '@/types/geometry';
import { generateArrayPositions } from '../services/arrayPlacement';
import { computeBuildingBounds, type BuildingGeometry } from '../services/buildingClone';

/** The building's plan-space reference point (its bounding-box center), or null when the
 *  plan is empty. Used as the array origin for building mode so the copies line up with the
 *  actual construction instead of the cursor. */
function buildingOrigin(g: BuildingGeometry): Point2D | null {
  return computeBuildingBounds(g)?.center ?? null;
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

  const previewItems = useMemo(() => {
    if (activeTool !== 'array' || !arrayConfig.isPreviewing || !arrayConfig.entityType) return [];
    if (arrayConfig.entityType === 'building') {
      const origin = buildingOrigin({ vertices, walls: {}, rooms: {}, openings: {}, pillars, beams, deckSlabs, railings, furniture } as BuildingGeometry);
      if (!origin) return [];
      return generateArrayPositions(origin, arrayConfig);
    }
    if (!cursor) return [];
    return generateArrayPositions(cursor, arrayConfig);
  }, [activeTool, arrayConfig, cursor, vertices, pillars, beams, deckSlabs, railings, furniture]);

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
    return null;
  }, [furniture, pillars, selectedIds]);

  return {
    previewItems,
    commitAt,
    cancel,
    selectedReferenceLabel,
  };
}
