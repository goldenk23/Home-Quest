import { useCallback, useMemo, useRef, useState } from 'react';
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

  // Drag-to-position state. While dragging, `dragOrigin` overrides the array's reference
  // point (cursor for furniture/pillar, entity center for building/component) so the whole
  // preview translates with the mouse. State drives re-renders; the ref mirrors it so the
  // canvas mouse handlers (which run outside React's render cycle) always see fresh values.
  const [dragOrigin, setDragOrigin] = useState<Point2D | null>(null);
  const dragOriginRef = useRef<Point2D | null>(null);
  // Cursor→origin offset captured on pickup, so the preview doesn't jump to the cursor.
  const dragOffsetRef = useRef<Point2D>({ x: 0, y: 0 });

  const previewItems = useMemo(() => {
    if (activeTool !== 'array' || !arrayConfig.isPreviewing || !arrayConfig.entityType) return [];
    // A drag in progress overrides every mode's origin — the array follows the drag.
    if (dragOrigin) return generateArrayPositions(dragOrigin, arrayConfig);
    if (arrayConfig.entityType === 'building') {
      const origin = buildingOrigin({ vertices, walls: {}, rooms: {}, openings: {}, pillars, beams, deckSlabs, railings, furniture } as BuildingGeometry);
      if (!origin) return [];
      return generateArrayPositions(origin, arrayConfig);
    }
    if (arrayConfig.entityType === 'component') {
      const componentId = arrayConfig.referenceId;
      const g: ComponentCloneGeometry = { vertices, walls, openings, pillars, beams, deckSlabs, railings, furniture, roads };
      const origin = componentOrigin(componentId, g);
      if (!origin) return [];
      return generateArrayPositions(origin, arrayConfig);
    }
    if (!cursor) return [];
    return generateArrayPositions(cursor, arrayConfig);
  }, [activeTool, arrayConfig, cursor, dragOrigin, vertices, pillars, beams, deckSlabs, railings, furniture, walls, roads, openings]);

  /**
   * Commits the array. `clickOrigin` is the plain-click position (legacy flow);
   * `draggedOrigin` — when provided — is the drag-adjusted, snapped origin and takes priority.
   *
   * For building/component modes the clone offsets are measured from the entity's OWN
   * bounding-box center (not from positions[0]) so that when the origin has been dragged
   * away from the entity, every clone lands exactly where its preview ghost was drawn.
   * With an undragged origin (origin === center) this reduces to the previous behavior.
   */
  const commitAt = useCallback((clickOrigin: Point2D, draggedOrigin: Point2D | null = null): string[] => {
    const state = useAppStore.getState();
    const config = state.arrayConfig;
    if (state.activeTool !== 'array' || !config.entityType || !config.isPreviewing) return [];

    const entityCenter = config.entityType === 'building'
      ? buildingOrigin({
          vertices: state.vertices, walls: state.walls, rooms: state.rooms, openings: state.openings,
          pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
          railings: state.railings, furniture: state.furniture,
        })
      : config.entityType === 'component'
        ? componentOrigin(config.referenceId, {
            vertices: state.vertices, walls: state.walls, openings: state.openings,
            pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
            railings: state.railings, furniture: state.furniture, roads: state.roads,
          })
        : null;

    // Building/component arrays anchor on the entity's own center unless dragged; every
    // other mode places new items starting at the (possibly dragged) click point.
    const origin = config.entityType === 'building' || config.entityType === 'component'
      ? (draggedOrigin ?? entityCenter)
      : (draggedOrigin ?? clickOrigin);
    if (!origin) return [];

    const positions = generateArrayPositions(origin, config);
    const createdIds: string[] = [];

    // recordHistory is the transaction boundary: the drag itself never mutates the store
    // (it only moves the preview), so the whole placement is a single undoable step.
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
        // Index 0 is the existing building; only offsets 1..count-1 are cloned. Offsets are
        // measured from the building's own center so a dragged origin repositions the set.
        if (entityCenter) {
          const offsets = positions.slice(1).map((p) => ({ x: p.position.x - entityCenter.x, y: p.position.y - entityCenter.y }));
          if (offsets.length > 0) createdIds.push(...state.duplicateBuilding(offsets));
        }
      } else if (config.entityType === 'component') {
        const componentId = config.referenceId;
        if (componentId && entityCenter) {
          const offsets = positions.slice(1).map((p) => ({ x: p.position.x - entityCenter.x, y: p.position.y - entityCenter.y }));
          if (offsets.length > 0) createdIds.push(...state.duplicateComponent(componentId, offsets));
        }
      }

      if (createdIds.length > 0) state.select(createdIds);
    });

    return createdIds;
  }, []);

  /**
   * Picks up the array preview at its current origin (cursor position for furniture/pillar,
   * entity bounding-box center for building/component). Records the cursor→origin offset so
   * the preview doesn't jump. Returns false when the tool isn't in a previewable state.
   */
  const beginDrag = useCallback((grabCursor: Point2D): boolean => {
    const state = useAppStore.getState();
    const config = state.arrayConfig;
    if (state.activeTool !== 'array' || !config.entityType || !config.isPreviewing) return false;

    let origin: Point2D | null = grabCursor;
    if (config.entityType === 'building') {
      origin = buildingOrigin({
        vertices: state.vertices, walls: state.walls, rooms: state.rooms, openings: state.openings,
        pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
        railings: state.railings, furniture: state.furniture,
      });
    } else if (config.entityType === 'component') {
      origin = componentOrigin(config.referenceId, {
        vertices: state.vertices, walls: state.walls, openings: state.openings,
        pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
        railings: state.railings, furniture: state.furniture, roads: state.roads,
      });
    }
    if (!origin) return false;

    dragOffsetRef.current = { x: origin.x - grabCursor.x, y: origin.y - grabCursor.y };
    dragOriginRef.current = origin;
    setDragOrigin(origin);
    return true;
  }, []);

  /**
   * Translates the array origin to follow the cursor (raw world coords + pickup offset).
   * The caller supplies `snapOrigin` (e.g. the useSnapping pipeline) so snapping applies to
   * the ORIGIN itself, not the cursor. Returns true when the origin actually moved.
   */
  const updateDrag = useCallback((rawCursor: Point2D, snapOrigin?: (p: Point2D) => Point2D): boolean => {
    const prev = dragOriginRef.current;
    if (!prev) return false;
    const raw = { x: rawCursor.x + dragOffsetRef.current.x, y: rawCursor.y + dragOffsetRef.current.y };
    const next = snapOrigin ? snapOrigin(raw) : raw;
    if (next.x === prev.x && next.y === prev.y) return false;
    dragOriginRef.current = next;
    setDragOrigin(next);
    return true;
  }, []);

  /**
   * Ends the drag. With `commit` true the array is placed at the final snapped origin using
   * the same commit logic as click-to-place; with false the drag is dropped (e.g. the
   * mouseup was really just a click, or the cursor left the canvas).
   */
  const endDrag = useCallback((commit: boolean): string[] => {
    const origin = dragOriginRef.current;
    dragOriginRef.current = null;
    setDragOrigin(null);
    if (!commit || !origin) return [];
    return commitAt(origin, origin);
  }, [commitAt]);

  const cancel = useCallback(() => {
    dragOriginRef.current = null;
    setDragOrigin(null);
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
    beginDrag,
    updateDrag,
    endDrag,
    isDragging: dragOrigin !== null,
  };
}
