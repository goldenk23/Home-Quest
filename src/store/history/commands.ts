// src/store/history/commands.ts

import type { Point2D, EntityId } from '@/types';
import type { Wall, Vertex, FurnitureItem, Room } from '@/types/editor';

/** A reversible operation. Carries enough data to go both directions. */
export interface Command {
  readonly type: string;
  readonly label: string; // shown in the UI ("Undo Add Wall")
  readonly timestamp: number;
  execute(): void;
  undo(): void;
}

export interface AddWallCommand extends Command {
  type: 'ADD_WALL';
  wallId: EntityId;
  startVertexId: EntityId;
  endVertexId: EntityId;
  wall: Wall;
  startVertex: Vertex;
  endVertex: Vertex;
  createdVertexIds: EntityId[];
}

export interface RemoveWallCommand extends Command {
  type: 'REMOVE_WALL';
  wall: Wall;
  startVertex: Vertex;
  endVertex: Vertex;
  affectedRooms: Room[];
}

export interface MoveVertexCommand extends Command {
  type: 'MOVE_VERTEX';
  vertexId: EntityId;
  oldPosition: Point2D;
  newPosition: Point2D;
}

export interface AddFurnitureCommand extends Command {
  type: 'ADD_FURNITURE';
  item: FurnitureItem;
}

export interface RemoveFurnitureCommand extends Command {
  type: 'REMOVE_FURNITURE';
  item: FurnitureItem;
}

export interface MoveFurnitureCommand extends Command {
  type: 'MOVE_FURNITURE';
  itemId: EntityId;
  oldPosition: Point2D;
  newPosition: Point2D;
}

export interface RotateFurnitureCommand extends Command {
  type: 'ROTATE_FURNITURE';
  itemId: EntityId;
  oldRotation: number;
  newRotation: number;
}

export interface SetRoomTypeCommand extends Command {
  type: 'SET_ROOM_TYPE';
  roomId: EntityId;
  oldType: string;
  newType: string;
}

export interface BatchCommand extends Command {
  type: 'BATCH';
  commands: Command[];
}
