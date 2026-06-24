import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '@/store';

function reset() {
  useAppStore.setState({ vertices: {}, walls: {}, rooms: {}, furniture: {}, openings: {}, selectedIds: [] });
}

describe('paint actions (updateWall / updateRoom)', () => {
  beforeEach(reset);

  it('updateWall changes a wall materialId', () => {
    const { addWall, updateWall } = useAppStore.getState();
    const wallId = addWall({ x: 0, y: 0 }, { x: 400, y: 0 });
    expect(wallId).toBeTruthy();

    expect(useAppStore.getState().walls[wallId].materialId).toBe('default-wall');
    updateWall(wallId, { materialId: 'paint-sage' });
    expect(useAppStore.getState().walls[wallId].materialId).toBe('paint-sage');
  });

  it('updateRoom changes a room floorMaterialId', () => {
    // Build a closed room.
    const { addWall, setRooms, updateRoom } = useAppStore.getState();
    addWall({ x: 0, y: 0 }, { x: 400, y: 0 });
    addWall({ x: 400, y: 0 }, { x: 400, y: 400 });
    addWall({ x: 400, y: 400 }, { x: 0, y: 400 });
    addWall({ x: 0, y: 400 }, { x: 0, y: 0 });

    const roomId = 'room_test';
    setRooms({
      [roomId]: {
        id: roomId,
        boundaryVertexIds: Object.keys(useAppStore.getState().vertices),
        roomType: 'living',
        label: 'Living',
        floorMaterialId: 'default-floor',
      },
    });

    updateRoom(roomId, { floorMaterialId: 'floor-wood' });
    expect(useAppStore.getState().rooms[roomId].floorMaterialId).toBe('floor-wood');
    // Untouched fields survive.
    expect(useAppStore.getState().rooms[roomId].label).toBe('Living');
  });

  it('updateWall on a missing wall is a safe no-op', () => {
    expect(() => useAppStore.getState().updateWall('nope', { materialId: 'paint-white' })).not.toThrow();
  });
});
