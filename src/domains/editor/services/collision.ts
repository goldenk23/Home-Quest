// src/domains/editor/services/collision.ts

import type { Point2D, AABB, OBB } from '@/types/geometry';
import type { FurnitureItem, Wall, Vertex } from '@/types/editor';

/** Broad-phase test: two AABBs overlap only if they overlap on BOTH axes. O(1). */
export function aabbOverlaps(a: AABB, b: AABB): boolean {
  return a.min.x <= b.max.x && a.max.x >= b.min.x && a.min.y <= b.max.y && a.max.y >= b.min.y;
}

/** Tightest axis-aligned box around a (possibly rotated) furniture item. */
export function furnitureToAABB(item: FurnitureItem): AABB {
  const hw = item.bounds.width / 2;
  const hd = item.bounds.depth / 2;
  const cos = Math.abs(Math.cos(item.rotation));
  const sin = Math.abs(Math.sin(item.rotation));
  const ex = hw * cos + hd * sin; // rotated extent on X
  const ey = hw * sin + hd * cos; // rotated extent on Y
  return {
    min: { x: item.position.x - ex, y: item.position.y - ey },
    max: { x: item.position.x + ex, y: item.position.y + ey },
  };
}

/**
 * Narrow-phase test: do two oriented boxes overlap?
 * Separating Axis Theorem — if we can find ANY axis where the boxes' shadows don't
 * overlap, they're apart. For two OBBs there are 4 candidate axes (2 per box).
 */
export function obbIntersects(a: OBB, b: OBB): boolean {
  const cornersA = getOBBCorners(a);
  const cornersB = getOBBCorners(b);
  const axes = [...getOBBAxes(a), ...getOBBAxes(b)];
  for (const axis of axes) {
    const projA = projectOntoAxis(cornersA, axis);
    const projB = projectOntoAxis(cornersB, axis);
    if (projA.max < projB.min || projB.max < projA.min) return false; // gap found ⇒ apart
  }
  return true;
}

function getOBBCorners(obb: OBB): Point2D[] {
  const cos = Math.cos(obb.rotation);
  const sin = Math.sin(obb.rotation);
  const local = [
    { x: -obb.halfExtents.x, y: -obb.halfExtents.y },
    { x: obb.halfExtents.x, y: -obb.halfExtents.y },
    { x: obb.halfExtents.x, y: obb.halfExtents.y },
    { x: -obb.halfExtents.x, y: obb.halfExtents.y },
  ];
  return local.map((lc) => ({
    x: obb.center.x + lc.x * cos - lc.y * sin,
    y: obb.center.y + lc.x * sin + lc.y * cos,
  }));
}

function getOBBAxes(obb: OBB): Point2D[] {
  const cos = Math.cos(obb.rotation);
  const sin = Math.sin(obb.rotation);
  return [
    { x: cos, y: sin },
    { x: -sin, y: cos },
  ];
}

function projectOntoAxis(points: Point2D[], axis: Point2D): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const p of points) {
    const proj = p.x * axis.x + p.y * axis.y;
    if (proj < min) min = proj;
    if (proj > max) max = proj;
  }
  return { min, max };
}

/**
 * Spatial hash grid for the broad phase. The world is chopped into square cells; only
 * items sharing a cell are ever narrow-phase tested. Keep cellSize >= the largest item so
 * overlapping items always share a cell.
 */
export class SpatialHashGrid {
  private cells = new Map<string, Set<string>>();
  private entityCells = new Map<string, string[]>();
  private cellSize: number;

  constructor(cellSize = 100) {
    this.cellSize = cellSize; // 100cm = 1m cells
  }

  insert(entityId: string, aabb: AABB): void {
    const keys: string[] = [];
    const minCx = Math.floor(aabb.min.x / this.cellSize);
    const maxCx = Math.floor(aabb.max.x / this.cellSize);
    const minCy = Math.floor(aabb.min.y / this.cellSize);
    const maxCy = Math.floor(aabb.max.y / this.cellSize);
    for (let cx = minCx; cx <= maxCx; cx++) {
      for (let cy = minCy; cy <= maxCy; cy++) {
        const key = `${cx},${cy}`;
        keys.push(key);
        if (!this.cells.has(key)) this.cells.set(key, new Set());
        this.cells.get(key)!.add(entityId);
      }
    }
    this.entityCells.set(entityId, keys);
  }

  remove(entityId: string): void {
    const keys = this.entityCells.get(entityId);
    if (!keys) return;
    for (const key of keys) this.cells.get(key)?.delete(entityId);
    this.entityCells.delete(entityId);
  }

  query(aabb: AABB): Set<string> {
    const result = new Set<string>();
    const minCx = Math.floor(aabb.min.x / this.cellSize);
    const maxCx = Math.floor(aabb.max.x / this.cellSize);
    const minCy = Math.floor(aabb.min.y / this.cellSize);
    const maxCy = Math.floor(aabb.max.y / this.cellSize);
    for (let cx = minCx; cx <= maxCx; cx++) {
      for (let cy = minCy; cy <= maxCy; cy++) {
        const cell = this.cells.get(`${cx},${cy}`);
        if (cell) for (const id of cell) result.add(id);
      }
    }
    return result;
  }

  clear(): void {
    this.cells.clear();
    this.entityCells.clear();
  }
}

/**
 * Returns the ids of furniture that the given item overlaps.
 * (`walls`/`vertices` are part of the signature for the wall-aware extension in Part 27;
 * furniture-vs-furniture is handled here.)
 */
export function checkFurnitureCollisions(
  item: FurnitureItem,
  allFurniture: Record<string, FurnitureItem>,
  _walls: Wall[],
  _vertices: Record<string, Vertex>,
  spatialGrid: SpatialHashGrid
): string[] {
  const collisions: string[] = [];
  const itemAABB = furnitureToAABB(item);
  const itemOBB: OBB = {
    center: item.position,
    halfExtents: { x: item.bounds.width / 2, y: item.bounds.depth / 2 },
    rotation: item.rotation,
  };

  for (const candidateId of spatialGrid.query(itemAABB)) {
    if (candidateId === item.id) continue;
    const other = allFurniture[candidateId];
    if (!other) continue;
    const otherOBB: OBB = {
      center: other.position,
      halfExtents: { x: other.bounds.width / 2, y: other.bounds.depth / 2 },
      rotation: other.rotation,
    };
    if (obbIntersects(itemOBB, otherOBB)) collisions.push(candidateId);
  }
  return collisions;
}
