import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '@/store';
import { detectRooms } from '../roomDetection';
import { splitWallsAtPoint } from '../wallOps';

function reset() {
  useAppStore.setState({ vertices: {}, walls: {}, rooms: {}, furniture: {}, selectedIds: [] });
}

function roomCount() {
  const { vertices, walls } = useAppStore.getState();
  return detectRooms(vertices, walls).length;
}

describe('room split / merge', () => {
  beforeEach(reset);

  it('square = 1 room', () => {
    const { addWall } = useAppStore.getState();
    addWall({ x: 0, y: 0 }, { x: 400, y: 0 });
    addWall({ x: 400, y: 0 }, { x: 400, y: 400 });
    addWall({ x: 400, y: 400 }, { x: 0, y: 400 });
    addWall({ x: 0, y: 400 }, { x: 0, y: 0 });
    expect(roomCount()).toBe(1);
  });

  it('divider through square => 2 rooms', () => {
    const { addWall } = useAppStore.getState();
    addWall({ x: 0, y: 0 }, { x: 400, y: 0 });
    addWall({ x: 400, y: 0 }, { x: 400, y: 400 });
    addWall({ x: 400, y: 400 }, { x: 0, y: 400 });
    addWall({ x: 0, y: 400 }, { x: 0, y: 0 });
    expect(roomCount()).toBe(1);

    splitWallsAtPoint({ x: 200, y: 0 });
    splitWallsAtPoint({ x: 200, y: 400 });
    useAppStore.getState().addWall({ x: 200, y: 0 }, { x: 200, y: 400 });
    expect(roomCount()).toBe(2);
  });

  it('adjacent room sharing a full edge => 2 rooms', () => {
    const { addWall } = useAppStore.getState();
    addWall({ x: 0, y: 0 }, { x: 400, y: 0 });
    addWall({ x: 400, y: 0 }, { x: 400, y: 400 });
    addWall({ x: 400, y: 400 }, { x: 0, y: 400 });
    addWall({ x: 0, y: 400 }, { x: 0, y: 0 });
    // Room 2 to the right, reusing the shared edge (400,0)-(400,400)
    useAppStore.getState().addWall({ x: 400, y: 0 }, { x: 800, y: 0 });
    useAppStore.getState().addWall({ x: 800, y: 0 }, { x: 800, y: 400 });
    useAppStore.getState().addWall({ x: 800, y: 400 }, { x: 400, y: 400 });
    expect(roomCount()).toBe(2);
  });

  it('adjacent room attaching to the MIDDLE of a wall (T-junctions) => 2 rooms', () => {
    const { addWall } = useAppStore.getState();
    addWall({ x: 0, y: 0 }, { x: 600, y: 0 });
    addWall({ x: 600, y: 0 }, { x: 600, y: 600 });
    addWall({ x: 600, y: 600 }, { x: 0, y: 600 });
    addWall({ x: 0, y: 600 }, { x: 0, y: 0 });
    // Small room attaching to the middle of the right wall (y 200..400)
    splitWallsAtPoint({ x: 600, y: 200 });
    splitWallsAtPoint({ x: 600, y: 400 });
    useAppStore.getState().addWall({ x: 600, y: 200 }, { x: 900, y: 200 });
    useAppStore.getState().addWall({ x: 900, y: 200 }, { x: 900, y: 400 });
    useAppStore.getState().addWall({ x: 900, y: 400 }, { x: 600, y: 400 });
    expect(roomCount()).toBe(2);
  });
});
