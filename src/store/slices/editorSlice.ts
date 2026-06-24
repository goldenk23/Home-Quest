import type { StateCreator } from 'zustand';
import type { AppStore } from '../index';
import type { EntityId, Vertex, Wall, Room, FurnitureItem, Road } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { generateId } from '@/utils/id';
import type { SnapConfig } from '@/domains/editor/hooks/useSnapping';
import { castDraft } from 'immer';
import { validateAddWall } from '@/store/guards/storeGuards';

export interface EditorSlice {
    // State
    vertices: Record<EntityId, Vertex>;
    walls: Record<EntityId, Wall>;
    rooms: Record<EntityId, Room>;
    furniture: Record<EntityId, FurnitureItem>;
    openings: Record<EntityId, import('@/types/editor').Opening>;
    roads: Record<EntityId, Road>;
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
            state.selectedIds = [];
        });
    },
});