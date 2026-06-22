// src/domains/vastu/services/zones.ts

import type { Point2D } from '@/types/geometry';

export type VastuDirection = 'N' | 'NE' | 'E' | 'SE' | 'S' | 'SW' | 'W' | 'NW';

export interface VastuZone {
  readonly direction: VastuDirection;
  readonly startAngle: number; // radians from +X (East), CCW
  readonly spanAngle: number;
  readonly element: 'fire' | 'water' | 'earth' | 'air' | 'space';
  readonly recommendedRooms: string[];
  readonly color: string;
}

/**
 * The eight 45° sectors. North = +Y (90°), East = +X (0°), angles increase CCW.
 * Each sector is centered on its compass direction (e.g. East spans 337.5°→22.5°).
 */
export const VASTU_ZONES_8: VastuZone[] = [
  { direction: 'E', startAngle: (15 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'air', recommendedRooms: ['living', 'study', 'entrance'], color: '#4CAF50' },
  { direction: 'NE', startAngle: Math.PI / 8, spanAngle: Math.PI / 4, element: 'water', recommendedRooms: ['puja', 'study', 'living'], color: '#2196F3' },
  { direction: 'N', startAngle: (3 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'water', recommendedRooms: ['living', 'entrance', 'study'], color: '#03A9F4' },
  { direction: 'NW', startAngle: (5 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'air', recommendedRooms: ['bedroom', 'storage', 'garage'], color: '#9C27B0' },
  { direction: 'W', startAngle: (7 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'space', recommendedRooms: ['dining', 'bedroom', 'study'], color: '#673AB7' },
  { direction: 'SW', startAngle: (9 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'earth', recommendedRooms: ['bedroom', 'storage'], color: '#795548' },
  { direction: 'S', startAngle: (11 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'fire', recommendedRooms: ['kitchen', 'dining'], color: '#F44336' },
  { direction: 'SE', startAngle: (13 * Math.PI) / 8, spanAngle: Math.PI / 4, element: 'fire', recommendedRooms: ['kitchen', 'bathroom'], color: '#FF5722' },
];

/** Maps an angle (degrees, 0=E, CCW) to one of the 8 directions. */
function degreesToDirection(degrees: number): VastuDirection {
  const d = ((degrees % 360) + 360) % 360;
  if (d >= 337.5 || d < 22.5) return 'E';
  if (d < 67.5) return 'NE';
  if (d < 112.5) return 'N';
  if (d < 157.5) return 'NW';
  if (d < 202.5) return 'W';
  if (d < 247.5) return 'SW';
  if (d < 292.5) return 'S';
  return 'SE';
}

/** The primary direction of a room, measured from the Brahmasthan to the room's centroid. */
export function getRoomDirection(roomPolygon: Point2D[], brahmasthan: Point2D): VastuDirection {
  const n = roomPolygon.length;
  const centroid = roomPolygon.reduce((acc, p) => ({ x: acc.x + p.x / n, y: acc.y + p.y / n }), { x: 0, y: 0 });
  const angle = Math.atan2(centroid.y - brahmasthan.y, centroid.x - brahmasthan.x);
  return degreesToDirection((angle * 180) / Math.PI);
}
