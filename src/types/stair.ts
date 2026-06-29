// src/types/stair.ts

import type { EntityId } from './editor';
import type { Point2D } from './geometry';

/** A single straight run of steps between two consecutive path points. */
export interface StairFlight {
  readonly id: EntityId;
  /** Bottom-of-flight position in plan cm. */
  readonly startPoint: Point2D;
  /** Top-of-flight position in plan cm. */
  readonly endPoint: Point2D;
  readonly widthCm: number;
  readonly bottomElevationCm: number;
  readonly topElevationCm: number;
  readonly stepCount: number;
  readonly risePerStepCm: number;
  readonly goingPerStepCm: number;
}

/** A flat platform at a turn between two flights. */
export interface StairLanding {
  readonly id: EntityId;
  /** Centre of the landing in plan cm. */
  readonly center: Point2D;
  readonly widthCm: number;
  readonly depthCm: number;
  readonly elevationCm: number;
  /** Rotation of the landing in radians (aligns to the incoming segment). */
  readonly rotation: number;
}

/** A complete staircase entity connecting two storeys. Stored on the lower floor. */
export interface StairEntity {
  readonly id: EntityId;
  /** The floor where the bottom step sits. */
  readonly lowerFloorId: EntityId;
  /** The floor where the top step lands. */
  readonly upperFloorId: EntityId;
  /** The drawn path in plan cm: first point = bottom step, last = top step. */
  readonly pathPoints: Point2D[];
  /** Stair width in cm (60–500). */
  readonly widthCm: number;
  /** One flight per straight segment of the path. */
  readonly flights: StairFlight[];
  /** One landing at each intermediate turn point. */
  readonly landings: StairLanding[];
  /**
   * Precomputed plan-cm polygon tracing the stairwell void (the opening cut
   * through the lower floor's ceiling slab and the upper floor's floor finish).
   */
  readonly stairwellVoid: Point2D[];
}
