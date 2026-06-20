/**
 *  Selector for editor state management with Memoization
 */
import { useAppStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';// it prevents unnecessary re-renders by doing a shallow comparison of the
 import type {Point2D} from '@/types/geometry';


/**
 * We are creating a helper called useWallSegments. Its only job is to gather all the walls so the 2D screen can draw them. It calls the global memory (useAppStore) and asks to look at everything currently remembered (state).
 */
export function useWallSegments() {
    return useAppStore(useShallow((state)=> {
        return Object.values(state.walls).map((wall) => ({
            id: wall.id,
            start: state.vertices[wall.startVertexId]?.position ?? {x:0,y:0},
            end: state.vertices[wall.endVertexId]?.position ?? {x:0,y:0},
            thickness: wall.thickness,
        }));
    }));
}

/**
 * Helper specifically for the "magnetic snapping" feature.
 * When you are drawing a new wall, your mouse magnetically snaps to an existing corner.
 * This asks the memory to go through every single corner in the house and hands back 
 * a simple list of their x and y coordinates. 
 * We use the `useShallow` performance trick so it doesn't recalculate this unless a corner actually moved!
 */
export function useEndpoints(): Point2D[] {
    return useAppStore(useShallow((state) => 
        Object.values(state.vertices).map((v) => v.position)
    ));
}

/**
 * Acts as a translator between the 2D drawing board and the 3D viewer.
 * The 3D viewer needs to know how to build the house, but it doesn't care about the UI or tools.
 * It creates a custom package containing only what is physically necessary:
 * - Walls: Needs the start/end coordinates, plus height and material (like brick) to paint them.
 * - Rooms: Needs the coordinates forming the floor shape, and the floor material (like wood or carpet).
 * 
 * We use the `useShallow` trick so the 3D viewer doesn't rebuild the entire model unless the physical shape actually changed.
 */
export function useGeometryForViewer() {
  return useAppStore(useShallow(
    (state) => ({
      walls: Object.values(state.walls).map((w) => ({
        id: w.id,
        start: state.vertices[w.startVertexId]?.position,
        end: state.vertices[w.endVertexId]?.position,
        thickness: w.thickness,
        height: w.height,
        materialId: w.materialId,
      })),
      rooms: Object.values(state.rooms).map((r) => ({
        id: r.id,
        polygon: r.boundaryVertexIds.map(
          (vid) => state.vertices[vid]?.position ?? { x: 0, y: 0 }
        ),
        floorMaterialId: r.floorMaterialId,
      })),
    })
  ));
}