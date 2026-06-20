import type { StateCreator } from 'zustand';
import type { AppStore } from '../index';
import type { EntityId, Vertex, Wall, Room, FurnitureItem } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { generateId } from '@/utils/id';
import type { SnapConfig } from '@/domains/editor/hooks/useSnapping';
import { castDraft } from 'immer';

export interface EditorSlice {
    // State
    vertices: Record<EntityId, Vertex>;
    walls: Record<EntityId, Wall>;
    rooms: Record<EntityId, Room>;
    furniture: Record<EntityId, FurnitureItem>;
    selectedIds: EntityId[];
    snapConfig: SnapConfig;
    currentMouseWorld: Point2D | null;

    // Actions
    addWall: (start: Point2D, end: Point2D, thickness?: number, height?: number) => EntityId;
    removeWall: (wallId: EntityId) => void;
    moveVertex: (vertexId: EntityId, newPosition: Point2D) => void;
    addFurniture: (item: Omit<FurnitureItem, 'id'>) => EntityId;
    removeFurniture: (id: EntityId) => void;
    moveFurniture: (id: EntityId, position: Point2D) => void;
    rotateFurniture: (id: EntityId, rotation: number) => void;
    setRooms: (rooms: Record<EntityId, Room>) => void;
    select: (ids: EntityId[]) => void;
    clearSelection: () => void;
    setSnapConfig: (config: Partial<SnapConfig>) => void;
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
    selectedIds: [],
    snapConfig: {
        gridSize: 10,
        snapRadius: 15,
        gridEnabled: true,
        endpointEnabled: true,
    },
    currentMouseWorld: null,
    addWall: (start, end, thickness = 20, height = 280) => {
        const wallId = generateId('wall');
        
        // Reject zero-length walls

        const dx = end.x - start.x;
        const dy = end.y - start.y;
        if(dx*dx + dy*dy <0.01) return ''; // Return empty string for zero-length wall

        set((state) => {
            const startVertexId = findOrCreateVertex(state, start);
            const endVertexId = findOrCreateVertex(state, end);

            if(startVertexId === endVertexId){
                return; // Don't create wall if both endpoints are the same vertex
            }

            state.walls[wallId] = {
                id: wallId,
                startVertexId,
                endVertexId,
                thickness,
                height,
                materialId: 'default-wall',
                isLoadBearing: false,
            };

            // Update vertex connectivity
            state.vertices[startVertexId].connectedWalls.push(wallId);
            state.vertices[endVertexId].connectedWalls.push(wallId);
        });
        return wallId;
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
            delete state.walls[wallId];
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

    setRooms: (rooms) => {
        set((state) => {
            state.rooms = castDraft(rooms);
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
});