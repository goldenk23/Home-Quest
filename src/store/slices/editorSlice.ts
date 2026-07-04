import type { StateCreator } from 'zustand';
import type { AppStore } from '../index';
import type { EntityId, Vertex, Wall, Room, FurnitureItem, Road, Pillar, Beam, DeckSlab, Railing } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { generateId } from '@/utils/id';
import type { SnapConfig } from '@/domains/editor/hooks/useSnapping';
import { castDraft } from 'immer';
import { validateAddWall } from '@/store/guards/storeGuards';
import type { StairEntity } from '@/types/stair';
import { cloneGeometry, type BuildingGeometry } from '@/domains/editor/services/buildingClone';
import { cloneComponent, type ComponentCloneGeometry } from '@/domains/editor/services/componentClone';

export interface EditorSlice {
    // State
    vertices: Record<EntityId, Vertex>;
    walls: Record<EntityId, Wall>;
    rooms: Record<EntityId, Room>;
    furniture: Record<EntityId, FurnitureItem>;
    openings: Record<EntityId, import('@/types/editor').Opening>;
    roads: Record<EntityId, Road>;
    stairs: Record<EntityId, StairEntity>;
    pillars: Record<EntityId, Pillar>;
    beams: Record<EntityId, Beam>;
    deckSlabs: Record<EntityId, DeckSlab>;
    railings: Record<EntityId, Railing>;
    selectedIds: EntityId[];
    snapConfig: SnapConfig;
    currentMouseWorld: Point2D | null;

    // Actions
    addWall: (start: Point2D, end: Point2D, thickness?: number, height?: number) => EntityId;
    removeWall: (wallId: EntityId) => void;
    /** Patch a wall's mutable attributes (paint, per-face finish, or geometry like height/thickness). Mirrors updateRoom. */
    updateWall: (id: EntityId, patch: Partial<Pick<Wall, 'materialId' | 'materialSideA' | 'materialSideB' | 'height' | 'thickness' | 'isLoadBearing'>>) => void;
    moveVertex: (vertexId: EntityId, newPosition: Point2D) => void;
    addFurniture: (item: Omit<FurnitureItem, 'id'>) => EntityId;
    removeFurniture: (id: EntityId) => void;
    moveFurniture: (id: EntityId, position: Point2D) => void;
    rotateFurniture: (id: EntityId, rotation: number) => void;
    scaleFurniture: (id: EntityId, scale: number) => void;

    addOpening: (opening: Omit<import('@/types/editor').Opening, 'id'>) => EntityId;
    removeOpening: (id: EntityId) => void;

    /** Add a road segment (standalone; not part of the wall/vertex graph). */
    addRoad: (start: Point2D, end: Point2D, width?: number) => EntityId;
    removeRoad: (id: EntityId) => void;
    moveRoad: (id: EntityId, delta: Point2D) => void;

    /** Place a computed StairEntity (from stairBuilder) on the active floor. */
    addStair: (stair: StairEntity) => void;
    removeStair: (id: EntityId) => void;

    addPillar: (pillar: Omit<Pillar, 'id'>) => EntityId;
    updatePillar: (id: EntityId, patch: Partial<Omit<Pillar, 'id'>>) => void;
    removePillar: (id: EntityId) => void;
    movePillar: (id: EntityId, position: Point2D) => void;
    addBeam: (beam: Omit<Beam, 'id'>) => EntityId;
    updateBeam: (id: EntityId, patch: Partial<Omit<Beam, 'id'>>) => void;
    removeBeam: (id: EntityId) => void;
    moveBeam: (id: EntityId, delta: Point2D) => void;
    addDeckSlab: (slab: Omit<DeckSlab, 'id'>) => EntityId;
    updateDeckSlab: (id: EntityId, patch: Partial<Omit<DeckSlab, 'id'>>) => void;
    removeDeckSlab: (id: EntityId) => void;
    moveDeckSlab: (id: EntityId, delta: Point2D) => void;
    addRailing: (railing: Omit<Railing, 'id'>) => EntityId;
    updateRailing: (id: EntityId, patch: Partial<Omit<Railing, 'id'>>) => void;
    removeRailing: (id: EntityId) => void;
    moveRailing: (id: EntityId, delta: Point2D) => void;

    /** Clone the whole building (walls, rooms, openings, pillars, beams, decks, railings,
     *  furniture) once per offset vector, appending each copy to the current floor. Used by
     *  the Array tool's "building" mode to duplicate a constructed unit. Returns new ids. */
    duplicateBuilding: (offsets: Point2D[]) => EntityId[];
    /** Clone a selected component once per offset vector. Returns the top-level cloned ids. */
    duplicateComponent: (componentId: EntityId, offsets: Point2D[]) => EntityId[];

    setRooms: (rooms: Record<EntityId, Room>) => void;
    updateRoom: (id: EntityId, patch: Partial<Pick<Room, 'roomType' | 'label' | 'floorMaterialId'>>) => void;
    select: (ids: EntityId[]) => void;
    clearSelection: () => void;
    setSnapConfig: (config: Partial<SnapConfig>) => void;
    scalePlan: (factor: number) => void;
    clearAll: () => void;
}


/**
 * Helper: find existing vertex at a given position (within a small tolerance) or create a new one.
 * 
 */

function findOrCreateVertex(state: any, position: Point2D): EntityId {
    const tolerance = 0.1; // 10 cm tolerance for snapping to existing vertices

    for(const [id, vertex] of Object.entries(state.vertices)) {
        const v = vertex as Vertex;
        const dx = v.position.x - position.x;
        const dy = v.position.y - position.y;
        if(dx*dx + dy*dy < tolerance * tolerance) {
            return id; // Found existing vertex
        }
    }
    // If no existing vertex is found, create a new one
    const vertexId = generateId('vertex');
    state.vertices[vertexId] = {
        id: vertexId,
        position,
        connectedWalls: []
    };
    return vertexId;
};

export const createEditorSlice: StateCreator<
    AppStore,
    [['zustand/immer', never], ['zustand/devtools', never]],
    [],
    EditorSlice
> = (set, _get) => ({
    vertices: {},
    walls: {},
    rooms: {},
    furniture: {},
    openings: {},
    roads: {},
    stairs: {},
    pillars: {},
    beams: {},
    deckSlabs: {},
    railings: {},
    selectedIds: [],
    snapConfig: {
        gridSize: 10,
        snapRadius: 15,
        gridEnabled: true,
        endpointEnabled: true,
    },
    currentMouseWorld: null,
    addWall: (start, end, thickness = 20, height = 280) => {
        // Pre-flight validation: rejects non-finite, zero-length, or absurd walls.
        const validation = validateAddWall(start, end, thickness, height);
        if (!validation.valid) {
            console.warn(`[Store] addWall rejected: ${validation.error}`);
            return '';
        }

        const wallId = generateId('wall');
        let wallCreated = false;

        set((state) => {
            const startVertexId = findOrCreateVertex(state, start);
            const endVertexId = findOrCreateVertex(state, end);

            if(startVertexId === endVertexId){
                return; // Don't create wall if both endpoints are the same vertex
            }

            // No duplicate wall between the same two vertices (either direction).
            const dup = Object.values(state.walls).find(
                (w) =>
                    (w.startVertexId === startVertexId && w.endVertexId === endVertexId) ||
                    (w.startVertexId === endVertexId && w.endVertexId === startVertexId)
            );
            if (dup) return;

            state.walls[wallId] = {
                id: wallId,
                startVertexId,
                endVertexId,
                thickness,
                height,
                materialId: 'default-wall',
                isLoadBearing: false,
                openingIds: [],
            };

            // Update vertex connectivity
            state.vertices[startVertexId].connectedWalls.push(wallId);
            state.vertices[endVertexId].connectedWalls.push(wallId);
            wallCreated = true;
        });
        return wallCreated ? wallId : '';
    },
    removeWall: (wallId) => {
        set((state) => {
            const wall = state.walls[wallId];
            if(!wall) return;

            // Remove from vertex connectivity
            const startVertex = state.vertices[wall.startVertexId];
            const endVertex = state.vertices[wall.endVertexId];

            if(startVertex){
                startVertex.connectedWalls = startVertex.connectedWalls.filter((id) => id !== wallId);
                // remove vertex it has no more connected walls 
                if(startVertex.connectedWalls.length ===0){
                    delete state.vertices[wall.startVertexId];
                }
            }

            if(endVertex){
                endVertex.connectedWalls = endVertex.connectedWalls.filter((id) => id !== wallId);
                // remove vertex it has no more connected walls
                if(endVertex.connectedWalls.length ===0){
                    delete state.vertices[wall.endVertexId];
                }
            }
            
            // Remove associated openings
            if (wall.openingIds) {
                wall.openingIds.forEach(openingId => {
                    delete state.openings[openingId];
                });
            }

            delete state.walls[wallId];
        });
    },
    updateWall: (id, patch) => {
        set((state) => {
            const wall = state.walls[id];
            if (wall) {
                Object.assign(wall, patch);
            }
        });
    },

    moveVertex: (vertexId, newPosition) => {
        set((state) => {
            const vertex = state.vertices[vertexId];
            if(vertex){
                vertex.position = newPosition;
            }
        });
    },

    addFurniture: (item) => {
        const furnitureId = generateId('furniture');
        set((state) => {
            state.furniture[furnitureId] = {
                ...item,
                id: furnitureId
            };
        });
        return furnitureId;
    },

    removeFurniture: (id) => {
        set((state) => {
            delete state.furniture[id];
        });
    },


    moveFurniture: (id, newPosition) => {
        set((state) => {
            const furniture = state.furniture[id];
            if(furniture){
                furniture.position = newPosition;
            }
        });
    },

    rotateFurniture: (id, rotation) => {
        set((state) => {
            const furniture = state.furniture[id];
            if(furniture){
                furniture.rotation = rotation;
            }
        });
    },

    scaleFurniture: (id, scale) => {
        set((state) => {
            const furniture = state.furniture[id];
            if(furniture){
                // constrain scale to reasonable limits
                furniture.scale = Math.max(0.1, Math.min(scale, 10));
            }
        });
    },

    addOpening: (opening) => {
        const openingId = generateId('opening');
        set((state) => {
            const wall = state.walls[opening.wallId];
            if (wall) {
                state.openings[openingId] = { ...opening, id: openingId };
                wall.openingIds = wall.openingIds || [];
                wall.openingIds.push(openingId);
            }
        });
        return openingId;
    },

    removeOpening: (id) => {
        set((state) => {
            const opening = state.openings[id];
            if (opening) {
                const wall = state.walls[opening.wallId];
                if (wall && wall.openingIds) {
                    wall.openingIds = wall.openingIds.filter(oid => oid !== id);
                }
                delete state.openings[id];
            }
        });
    },

    addRoad: (start, end, width = 300) => {
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        // Ignore zero/sub-cm roads (squared length < 1 cm²).
        if (!Number.isFinite(dx) || !Number.isFinite(dy) || dx * dx + dy * dy < 1) return '';
        const roadId = generateId('road');
        set((state) => {
            state.roads[roadId] = { id: roadId, start, end, width };
        });
        return roadId;
    },

    removeRoad: (id) => {
        set((state) => {
            delete state.roads[id];
        });
    },

    moveRoad: (id, delta) => {
        set((state) => {
            const road = state.roads[id];
            if (road) {
                road.start = { x: road.start.x + delta.x, y: road.start.y + delta.y };
                road.end = { x: road.end.x + delta.x, y: road.end.y + delta.y };
            }
        });
    },

    addStair: (stair) => {
        set((state) => {
            state.stairs[stair.id] = castDraft(stair);
        });
    },

    removeStair: (id) => {
        set((state) => {
            delete state.stairs[id];
        });
    },

    addPillar: (pillar) => {
        const pillarId = generateId('pillar');
        set((state) => {
            state.pillars[pillarId] = { ...pillar, id: pillarId };
        });
        return pillarId;
    },

    updatePillar: (id, patch) => {
        set((state) => {
            const pillar = state.pillars[id];
            if (pillar) Object.assign(pillar, patch);
        });
    },

    removePillar: (id) => {
        set((state) => {
            delete state.pillars[id];
        });
    },

    movePillar: (id, position) => {
        set((state) => {
            const pillar = state.pillars[id];
            if (pillar) pillar.position = position;
        });
    },

    addBeam: (beam) => {
        const beamId = generateId('beam');
        set((state) => { state.beams[beamId] = { ...beam, id: beamId }; });
        return beamId;
    },
    updateBeam: (id, patch) => {
        set((state) => { const beam = state.beams[id]; if (beam) Object.assign(beam, patch); });
    },
    removeBeam: (id) => {
        set((state) => { delete state.beams[id]; });
    },
    moveBeam: (id, delta) => {
        set((state) => {
            const beam = state.beams[id];
            if (beam) {
                beam.start = { x: beam.start.x + delta.x, y: beam.start.y + delta.y };
                beam.end = { x: beam.end.x + delta.x, y: beam.end.y + delta.y };
            }
        });
    },

    addDeckSlab: (slab) => {
        const slabId = generateId('deck-slab');
        set((state) => { state.deckSlabs[slabId] = { ...slab, id: slabId }; });
        return slabId;
    },
    updateDeckSlab: (id, patch) => {
        set((state) => { const slab = state.deckSlabs[id]; if (slab) Object.assign(slab, patch); });
    },
    removeDeckSlab: (id) => {
        set((state) => { delete state.deckSlabs[id]; });
    },
    moveDeckSlab: (id, delta) => {
        set((state) => {
            const slab = state.deckSlabs[id];
            if (slab) slab.polygon = slab.polygon.map((p) => ({ x: p.x + delta.x, y: p.y + delta.y }));
        });
    },

    duplicateBuilding: (offsets) => {
        const created: EntityId[] = [];
        set((state) => {
            const src: BuildingGeometry = {
                vertices: state.vertices, walls: state.walls, rooms: state.rooms,
                openings: state.openings, pillars: state.pillars, beams: state.beams,
                deckSlabs: state.deckSlabs, railings: state.railings, furniture: state.furniture,
            };
            for (const offset of offsets) {
                const clone = cloneGeometry(src, offset, generateId);
                Object.assign(state.vertices, castDraft(clone.vertices));
                Object.assign(state.walls, castDraft(clone.walls));
                Object.assign(state.rooms, castDraft(clone.rooms));
                Object.assign(state.openings, castDraft(clone.openings));
                Object.assign(state.pillars, castDraft(clone.pillars));
                Object.assign(state.beams, castDraft(clone.beams));
                Object.assign(state.deckSlabs, castDraft(clone.deckSlabs));
                Object.assign(state.railings, castDraft(clone.railings));
                Object.assign(state.furniture, castDraft(clone.furniture));
                created.push(...Object.keys(clone.pillars), ...Object.keys(clone.walls));
            }
        });
        return created;
    },

    duplicateComponent: (componentId, offsets) => {
        const created: EntityId[] = [];
        set((state) => {
            const src: ComponentCloneGeometry = {
                vertices: state.vertices, walls: state.walls, openings: state.openings,
                pillars: state.pillars, beams: state.beams, deckSlabs: state.deckSlabs,
                railings: state.railings, furniture: state.furniture, roads: state.roads,
            };
            for (const offset of offsets) {
                const clone = cloneComponent(src, componentId, offset, generateId);
                if (!clone) continue;
                Object.assign(state.vertices, castDraft(clone.vertices));
                Object.assign(state.walls, castDraft(clone.walls));
                Object.assign(state.openings, castDraft(clone.openings));
                Object.assign(state.pillars, castDraft(clone.pillars));
                Object.assign(state.beams, castDraft(clone.beams));
                Object.assign(state.deckSlabs, castDraft(clone.deckSlabs));
                Object.assign(state.railings, castDraft(clone.railings));
                Object.assign(state.furniture, castDraft(clone.furniture));
                Object.assign(state.roads, castDraft(clone.roads));
                created.push(...clone.createdIds);
            }
        });
        return created;
    },

    addRailing: (railing) => {
        const railingId = generateId('railing');
        set((state) => { state.railings[railingId] = { ...railing, id: railingId }; });
        return railingId;
    },
    updateRailing: (id, patch) => {
        set((state) => { const railing = state.railings[id]; if (railing) Object.assign(railing, patch); });
    },
    removeRailing: (id) => {
        set((state) => { delete state.railings[id]; });
    },
    moveRailing: (id, delta) => {
        set((state) => {
            const railing = state.railings[id];
            if (railing) {
                railing.start = { x: railing.start.x + delta.x, y: railing.start.y + delta.y };
                railing.end = { x: railing.end.x + delta.x, y: railing.end.y + delta.y };
            }
        });
    },

    setRooms: (rooms) => {
        set((state) => {
            state.rooms = castDraft(rooms);
        });
    },
    updateRoom: (id, patch) => {
        set((state) => {
            const room = state.rooms[id];
            if (room) {
                Object.assign(room, patch);
            }
        });
    },
    select: (ids) => {
        set((state) => {
            state.selectedIds = ids;
        });
    },
    clearSelection: () => {
        set((state) => {
            state.selectedIds = [];
        });
    },
    setSnapConfig: (config) => {
        set((state) => {
        Object.assign(state.snapConfig, config);
        });
    },
    /**
     * Uniformly scales the whole floor plan about its geometric centre: every wall
     * vertex and furniture position is moved toward/away from the centre by `factor`, and
     * each opening's along-wall offset scales with it so doors/windows stay proportional.
     * Real-world SIZES (wall thickness/height, furniture footprints, opening widths) are
     * left unchanged, so scaling up makes rooms genuinely more spacious rather than just
     * zooming. factor > 1 enlarges, < 1 shrinks.
     */
    scalePlan: (factor) => {
        if (!(factor > 0) || factor === 1) return;
        set((state) => {
            const verts = Object.values(state.vertices);
            const furn = Object.values(state.furniture);

            // Centre on the walls (fall back to furniture, then origin).
            let cx = 0, cy = 0, n = 0;
            for (const v of verts) { cx += v.position.x; cy += v.position.y; n++; }
            if (n === 0) for (const f of furn) { cx += f.position.x; cy += f.position.y; n++; }
            if (n === 0) return;
            cx /= n; cy /= n;

            for (const v of verts) {
                v.position = { x: cx + (v.position.x - cx) * factor, y: cy + (v.position.y - cy) * factor };
            }
            for (const f of furn) {
                f.position = { x: cx + (f.position.x - cx) * factor, y: cy + (f.position.y - cy) * factor };
            }
            for (const o of Object.values(state.openings)) {
                o.offsetCm = o.offsetCm * factor;
            }
            // Scale road endpoints about the same centre so paving moves with the plan.
            for (const r of Object.values(state.roads)) {
                r.start = { x: cx + (r.start.x - cx) * factor, y: cy + (r.start.y - cy) * factor };
                r.end = { x: cx + (r.end.x - cx) * factor, y: cy + (r.end.y - cy) * factor };
            }
            for (const p of Object.values(state.pillars)) {
                p.position = { x: cx + (p.position.x - cx) * factor, y: cy + (p.position.y - cy) * factor };
            }
            for (const b of Object.values(state.beams)) {
                b.start = { x: cx + (b.start.x - cx) * factor, y: cy + (b.start.y - cy) * factor };
                b.end = { x: cx + (b.end.x - cx) * factor, y: cy + (b.end.y - cy) * factor };
            }
            for (const s of Object.values(state.deckSlabs)) {
                s.polygon = s.polygon.map((p) => ({ x: cx + (p.x - cx) * factor, y: cy + (p.y - cy) * factor }));
            }
            for (const r of Object.values(state.railings)) {
                r.start = { x: cx + (r.start.x - cx) * factor, y: cy + (r.start.y - cy) * factor };
                r.end = { x: cx + (r.end.x - cx) * factor, y: cy + (r.end.y - cy) * factor };
            }
        });
    },
    clearAll: () => {
        set((state) => {
            state.vertices = {};
            state.walls = {};
            state.rooms = {};
            state.furniture = {};
            state.openings = {};
            state.roads = {};
            state.stairs = {};
            state.pillars = {};
            state.beams = {};
            state.deckSlabs = {};
            state.railings = {};
            state.selectedIds = [];
        });
    },
});