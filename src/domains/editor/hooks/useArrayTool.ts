import { useCallback, useMemo } from 'react';
import { useAppStore } from '@/store';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';
import type { Point2D } from '@/types/geometry';
import { generateArrayPositions } from '../services/arrayPlacement';

export function useArrayTool(cursor: Point2D | null) {
  const activeTool = useAppStore((s) => s.activeTool);
  const arrayConfig = useAppStore((s) => s.arrayConfig);
  const setArrayConfig = useAppStore((s) => s.setArrayConfig);
  const selectedIds = useAppStore((s) => s.selectedIds);
  const furniture = useAppStore((s) => s.furniture);
  const pillars = useAppStore((s) => s.pillars);

  const previewItems = useMemo(() => {
    if (activeTool !== 'array' || !arrayConfig.isPreviewing || !arrayConfig.entityType || !cursor) return [];
    return generateArrayPositions(cursor, arrayConfig);
  }, [activeTool, arrayConfig, cursor]);

  const commitAt = useCallback((origin: Point2D): string[] => {
    const state = useAppStore.getState();
    const config = state.arrayConfig;
    if (state.activeTool !== 'array' || !config.entityType || !config.isPreviewing) return [];

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
