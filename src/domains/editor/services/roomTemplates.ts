// src/domains/editor/services/roomTemplates.ts

import { useAppStore } from '@/store';
import type { RoomType } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { generateId } from '@/utils/id';
import { CM_PER_UNIT } from './units';

const FT = CM_PER_UNIT.ft; // ft → cm

export interface RoomTemplate {
  id: string;
  label: string;
  roomType: RoomType;
  /** Rectangle size in cm. */
  width: number;
  height: number;
}

/** Common pre-sized rooms (dimensions in feet, converted to cm). */
export const ROOM_TEMPLATES: RoomTemplate[] = [
  { id: 'bedroom-12x10', label: 'Bedroom', roomType: 'bedroom', width: 12 * FT, height: 10 * FT },
  { id: 'master-14x12', label: 'Master Bedroom', roomType: 'bedroom', width: 14 * FT, height: 12 * FT },
  { id: 'kitchen-10x8', label: 'Kitchen', roomType: 'kitchen', width: 10 * FT, height: 8 * FT },
  { id: 'bathroom-8x6', label: 'Bathroom', roomType: 'bathroom', width: 8 * FT, height: 6 * FT },
  { id: 'living-16x12', label: 'Living Room', roomType: 'living', width: 16 * FT, height: 12 * FT },
  { id: 'dining-12x10', label: 'Dining', roomType: 'dining', width: 12 * FT, height: 10 * FT },
];

/**
 * Drop a pre-named, pre-sized rectangular room: build 4 walls around the rectangle (so room
 * detection + 2D→3D extrusion pick it up), then inject a room record with the template's
 * label/type. Because detection carries over label/type/floor by boundary key
 * (see useRoomDetection), the re-derived room keeps the name. All in ONE undo step.
 */
export function placeRoomTemplate(origin: Point2D, tpl: RoomTemplate): void {
  const corners: Point2D[] = [
    { x: origin.x, y: origin.y },
    { x: origin.x + tpl.width, y: origin.y },
    { x: origin.x + tpl.width, y: origin.y + tpl.height },
    { x: origin.x, y: origin.y + tpl.height },
  ];

  useAppStore.getState().recordHistory('Add Room Template', () => {
    const s = useAppStore.getState();
    for (let i = 0; i < 4; i++) s.addWall(corners[i], corners[(i + 1) % 4]);

    // Resolve the 4 corner vertices that addWall just created/reused.
    const verts = useAppStore.getState().vertices;
    const ids = corners
      .map((c) => Object.values(verts).find((v) => Math.hypot(v.position.x - c.x, v.position.y - c.y) < 0.5)?.id)
      .filter((id): id is string => Boolean(id));
    if (ids.length !== 4) return; // couldn't resolve — leave it as bare walls

    const roomId = generateId('room');
    const st = useAppStore.getState();
    st.setRooms({
      ...st.rooms,
      [roomId]: {
        id: roomId,
        boundaryVertexIds: ids,
        roomType: tpl.roomType,
        label: tpl.label,
        floorMaterialId: 'default-floor',
      },
    });
  });
}
