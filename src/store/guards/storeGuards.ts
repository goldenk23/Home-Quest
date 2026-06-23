// src/store/guards/storeGuards.ts

import type { Point2D, EntityId } from '@/types';
import type { Wall, Vertex } from '@/types/editor';

/** Pre-flight check for addWall: rejects non-finite, zero-length, or absurd walls. */
export function validateAddWall(
  start: Point2D,
  end: Point2D,
  thickness: number,
  height: number
): { valid: boolean; error?: string } {
  if (!Number.isFinite(start.x) || !Number.isFinite(start.y)) return { valid: false, error: 'Start point has non-finite coordinates' };
  if (!Number.isFinite(end.x) || !Number.isFinite(end.y)) return { valid: false, error: 'End point has non-finite coordinates' };
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (dx * dx + dy * dy < 0.01) return { valid: false, error: 'Wall has zero length' };
  if (thickness <= 0 || thickness > 200) return { valid: false, error: `Invalid wall thickness: ${thickness}` };
  if (height <= 0 || height > 2000) return { valid: false, error: `Invalid wall height: ${height}` };
  return { valid: true };
}

/** Checks referential + bidirectional integrity of the wall graph. */
export function validateGraphIntegrity(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): { valid: boolean; issues: string[] } {
  const issues: string[] = [];

  for (const [wallId, wall] of Object.entries(walls)) {
    if (!vertices[wall.startVertexId]) issues.push(`Wall ${wallId}: dangling start vertex ref ${wall.startVertexId}`);
    if (!vertices[wall.endVertexId]) issues.push(`Wall ${wallId}: dangling end vertex ref ${wall.endVertexId}`);
  }
  for (const [vertexId, vertex] of Object.entries(vertices)) {
    for (const wallId of vertex.connectedWalls) {
      if (!walls[wallId]) issues.push(`Vertex ${vertexId}: dangling wall ref ${wallId}`);
    }
  }
  for (const [wallId, wall] of Object.entries(walls)) {
    const sv = vertices[wall.startVertexId];
    if (sv && !sv.connectedWalls.includes(wallId)) issues.push(`Wall ${wallId}: start vertex doesn't reference this wall`);
    const ev = vertices[wall.endVertexId];
    if (ev && !ev.connectedWalls.includes(wallId)) issues.push(`Wall ${wallId}: end vertex doesn't reference this wall`);
  }

  return { valid: issues.length === 0, issues };
}

/** Best-effort recovery: drops dangling walls, prunes bad refs, removes orphan vertices. */
export function repairGraphIntegrity(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): { verticesRemoved: number; wallsRemoved: number; refsFixed: number } {
  let verticesRemoved = 0;
  let wallsRemoved = 0;
  let refsFixed = 0;

  for (const [wallId, wall] of Object.entries(walls)) {
    if (!vertices[wall.startVertexId] || !vertices[wall.endVertexId]) {
      delete walls[wallId];
      wallsRemoved++;
    }
  }
  for (const vertex of Object.values(vertices)) {
    const valid = vertex.connectedWalls.filter((wid) => walls[wid]);
    if (valid.length !== vertex.connectedWalls.length) {
      refsFixed += vertex.connectedWalls.length - valid.length;
      vertex.connectedWalls = valid;
    }
  }
  for (const [vertexId, vertex] of Object.entries(vertices)) {
    if (vertex.connectedWalls.length === 0) {
      delete vertices[vertexId];
      verticesRemoved++;
    }
  }

  return { verticesRemoved, wallsRemoved, refsFixed };
}
