// src/domains/editor/services/wallOps.ts

import type { Point2D } from '@/types/geometry';
import type { EntityId, Wall, Vertex } from '@/types/editor';
import { useAppStore } from '@/store';
import { generateId } from '@/utils/id';
import { produce } from 'immer';

export interface WallIntersection {
  wallId: EntityId;
  point: Point2D;
  /** Parameter along the NEW wall (0..1), used to order splits start→end. */
  t: number;
}

/**
 * Finds where a proposed segment (newStart → newEnd) crosses existing wall centerlines.
 *
 * Uses the standard parametric segment‑intersection test. For segments A(P1→P2) and
 * B(P3→P4): solve for t (along A) and u (along B). A real crossing exists only when both
 * t and u are strictly inside (0,1) — we exclude the exact endpoints so shared corners
 * aren't mistaken for crossings.
 */
export function findWallIntersections(
  newStart: Point2D,
  newEnd: Point2D,
  walls: Record<EntityId, Wall>,
  vertices: Record<EntityId, Vertex>
): WallIntersection[] {
  const results: WallIntersection[] = [];

  const d1x = newEnd.x - newStart.x;
  const d1y = newEnd.y - newStart.y;

  for (const wall of Object.values(walls)) {
    const sv = vertices[wall.startVertexId];
    const ev = vertices[wall.endVertexId];
    if (!sv || !ev) continue;

    const p3 = sv.position;
    const p4 = ev.position;
    const d2x = p4.x - p3.x;
    const d2y = p4.y - p3.y;

    // 2D cross product of the two directions. ~0 ⇒ parallel ⇒ no single crossing.
    const cross = d1x * d2y - d1y * d2x;
    if (Math.abs(cross) < 1e-10) continue;

    const dx = p3.x - newStart.x;
    const dy = p3.y - newStart.y;
    const t = (dx * d2y - dy * d2x) / cross; // along the new wall
    const u = (dx * d1y - dy * d1x) / cross; // along the existing wall

    const EPS = 1e-6;
    if (t > EPS && t < 1 - EPS && u > EPS && u < 1 - EPS) {
      results.push({
        wallId: wall.id,
        point: { x: newStart.x + t * d1x, y: newStart.y + t * d1y },
        t,
      });
    }
  }

  // Process splits in order along the new wall so topology stays consistent.
  return results.sort((a, b) => a.t - b.t);
}

/**
 * Splits an existing wall at `point`, atomically.
 *
 * Topology change: one wall A→B becomes A→V and V→B, where V is a brand‑new vertex at
 * `point`. The shared vertex V is what lets a later wall connect cleanly, which is the
 * prerequisite for room detection.
 *
 * Everything happens inside a SINGLE setState() so no subscriber ever sees a wall that
 * points at a vertex that doesn't exist yet.
 *
 * @returns the new vertex id, or '' if the wall was not found.
 */
export function splitWallAtPoint(wallId: EntityId, point: Point2D): EntityId {
  const newVertexId = generateId('vertex');
  let ok = false;

  useAppStore.setState(produce((draft: any) => {
    const original = draft.walls[wallId];
    if (!original) return; // nothing to split

    const originalEndVertexId = original.endVertexId;

    // 1. Create the junction vertex.
    draft.vertices[newVertexId] = {
      id: newVertexId,
      position: point,
      connectedWalls: [],
    };

    // 2. Shorten the original wall so it now ends at the junction.
    original.endVertexId = newVertexId;

    // 3. Create the second half, inheriting thickness/height/material from the original.
    const newWallId = generateId('wall');
    draft.walls[newWallId] = {
      ...original,
      id: newWallId,
      startVertexId: newVertexId,
      endVertexId: originalEndVertexId,
    };

    // 4. Fix up connectivity so the graph stays correct.
    draft.vertices[newVertexId].connectedWalls = [wallId, newWallId];
    const endVertex = draft.vertices[originalEndVertexId];
    if (endVertex) {
      const idx = endVertex.connectedWalls.indexOf(wallId);
      if (idx !== -1) endVertex.connectedWalls[idx] = newWallId;
    }

    ok = true;
  }));

  return ok ? newVertexId : '';
}

/**
 * Returns the angles (radians) of every wall meeting at a vertex, sorted ascending.
 * Used later for mitered corner rendering. Pure — safe to call anywhere.
 */
export function computeCornerAngles(
  vertexId: EntityId,
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): number[] {
  const vertex = vertices[vertexId];
  if (!vertex || vertex.connectedWalls.length < 2) return [];

  return vertex.connectedWalls
    .map((wallId) => {
      const wall = walls[wallId];
      const otherId = wall.startVertexId === vertexId ? wall.endVertexId : wall.startVertexId;
      const other = vertices[otherId];
      if (!other) return 0;
      return Math.atan2(other.position.y - vertex.position.y, other.position.x - vertex.position.x);
    })
    .sort((a, b) => a - b);
}

export interface MiterOffsets {
    startLeft: number;
    startRight: number;
    endLeft: number;
    endRight: number;
}

/**
 * Computes exactly how much each corner of a wall needs to extend or retract
 * to seamlessly meet its neighboring walls without gaps or overlapping blockiness.
 */
export function computeMiterOffsets(
    wallId: EntityId,
    walls: Record<EntityId, Wall>,
    vertices: Record<EntityId, Vertex>
): MiterOffsets {
    const wall = walls[wallId];
    if (!wall) return { startLeft: 0, startRight: 0, endLeft: 0, endRight: 0 };

    const startV = vertices[wall.startVertexId];
    const endV = vertices[wall.endVertexId];
    if (!startV || !endV) return { startLeft: 0, startRight: 0, endLeft: 0, endRight: 0 };

    const dx = endV.position.x - startV.position.x;
    const dy = endV.position.y - startV.position.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len === 0) return { startLeft: 0, startRight: 0, endLeft: 0, endRight: 0 };

    const vStart = { x: dx / len, y: dy / len };
    const vEnd = { x: -dx / len, y: -dy / len };

    const maxOffset = wall.thickness * 2; // Safety limit for extremely sharp angles

    function getVertexOffsets(vertex: Vertex, v: Point2D) {
        if (vertex.connectedWalls.length <= 1) return { left: 0, right: 0 };

        const neighbors = vertex.connectedWalls
            .filter(id => id !== wallId)
            .map(id => {
                const w = walls[id];
                if (!w) return null;
                const otherVId = w.startVertexId === vertex.id ? w.endVertexId : w.startVertexId;
                const otherV = vertices[otherVId];
                if (!otherV) return null;
                const ddx = otherV.position.x - vertex.position.x;
                const ddy = otherV.position.y - vertex.position.y;
                const l = Math.sqrt(ddx*ddx + ddy*ddy);
                if (l === 0) return null;
                return {
                    id: w.id,
                    dir: { x: ddx/l, y: ddy/l },
                    thickness: w.thickness,
                    angle: Math.atan2(ddy, ddx)
                };
            })
            .filter(n => n !== null);

        if (neighbors.length === 0) return { left: 0, right: 0 };

        const vAngle = Math.atan2(v.y, v.x);
        const all = [...neighbors, { id: wallId, dir: v, thickness: wall.thickness, angle: vAngle }];
        
        // Sort counter-clockwise
        all.sort((a, b) => a.angle - b.angle);

        const myIdx = all.findIndex(x => x.id === wallId);
        const n = all.length;
        const leftNeighbor = all[(myIdx + 1) % n];
        const rightNeighbor = all[(myIdx - 1 + n) % n];

        let sLeft = 0;
        let sRight = 0;
        const tv = wall.thickness;

        const uL = leftNeighbor.dir;
        const tL = leftNeighbor.thickness;
        const crossL = v.x * uL.y - v.y * uL.x;
        const dotL = v.x * uL.x + v.y * uL.y;
        if (Math.abs(crossL) > 1e-4) {
            sLeft = ((tv / 2) * dotL - (tL / 2)) / crossL;
        }

        const uR = rightNeighbor.dir;
        const tR = rightNeighbor.thickness;
        const crossR = v.x * uR.y - v.y * uR.x;
        const dotR = v.x * uR.x + v.y * uR.y;
        if (Math.abs(crossR) > 1e-4) {
            sRight = -((tv / 2) * dotR + (tR / 2)) / crossR;
        }

        sLeft = Math.max(-maxOffset, Math.min(maxOffset, sLeft));
        sRight = Math.max(-maxOffset, Math.min(maxOffset, sRight));

        return { left: sLeft, right: sRight };
    }

    const startOffsets = getVertexOffsets(startV, vStart);
    const endOffsets = getVertexOffsets(endV, vEnd);

    return {
        startLeft: startOffsets.left,
        startRight: startOffsets.right,
        endLeft: endOffsets.left, // Left corner at the end corresponds to the Right side of the wall
        endRight: endOffsets.right,
    };
}
