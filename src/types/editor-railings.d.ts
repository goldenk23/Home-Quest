import type { Point2D } from './geometry';
import type { EntityId } from './editor';

declare module './editor' {
  /** A safety railing/parapet for balconies, decks, stairs, or elevated areas. */
  export interface Railing {
    readonly id: EntityId;
    start: Point2D;
    end: Point2D;
    height: number;
    elevationCm: number;
    style: 'open' | 'solid';
    materialId: string;
  }

  export interface FloorPlan {
    readonly railings: Record<EntityId, Railing>;
  }

  export interface FloorGeometry {
    railings: Record<EntityId, Railing>;
  }
}

declare module '@/types/editor' {
  /** A safety railing/parapet for balconies, decks, stairs, or elevated areas. */
  export interface Railing {
    readonly id: EntityId;
    start: Point2D;
    end: Point2D;
    height: number;
    elevationCm: number;
    style: 'open' | 'solid';
    materialId: string;
  }

  export interface FloorPlan {
    readonly railings: Record<EntityId, Railing>;
  }

  export interface FloorGeometry {
    railings: Record<EntityId, Railing>;
  }
}