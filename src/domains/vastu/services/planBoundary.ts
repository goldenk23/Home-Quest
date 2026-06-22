// src/domains/vastu/services/planBoundary.ts

import type { EntityId, Vertex, Wall } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { computeSignedArea } from '@/domains/editor/services/roomDetection';

interface DirectedEdge {
  fromVertexId: EntityId;
  toVertexId: EntityId;
}

/**
 * Derives the plan's outer boundary polygon (cm) from the wall graph, or null if there
 * isn't a closed loop yet. Returns the loop with the greatest enclosed area — the outline
 * that wraps every room.
 */
export function computePlanBoundary(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): Point2D[] | null {
  const edges: DirectedEdge[] = [];
  for (const wall of Object.values(walls)) {
    edges.push({ fromVertexId: wall.startVertexId, toVertexId: wall.endVertexId });
    edges.push({ fromVertexId: wall.endVertexId, toVertexId: wall.startVertexId });
  }

  const visited = new Set<string>();
  let best: Point2D[] | null = null;
  let bestArea = 0;

  for (const start of edges) {
    if (visited.has(`${start.fromVertexId}->${start.toVertexId}`)) continue;
    const cycle = traceCycle(start, vertices, edges);
    if (!cycle) continue;

    for (let i = 0; i < cycle.length; i++) {
      visited.add(`${cycle[i]}->${cycle[(i + 1) % cycle.length]}`);
    }

    const polygon = cycle.map((id) => vertices[id].position);
    const area = Math.abs(computeSignedArea(polygon));
    if (area > bestArea) {
      bestArea = area;
      best = polygon;
    }
  }

  return best;
}

/** Smallest-left-turn face tracer (identical rule to room detection). */
function traceCycle(
  startEdge: DirectedEdge,
  vertices: Record<EntityId, Vertex>,
  allEdges: DirectedEdge[]
): EntityId[] | null {
  const MAX = 200;
  const cycle: EntityId[] = [startEdge.fromVertexId];
  let from = startEdge.fromVertexId;
  let to = startEdge.toVertexId;

  for (let step = 0; step < MAX; step++) {
    if (to === startEdge.fromVertexId) return cycle.length >= 3 ? cycle : null;
    cycle.push(to);

    const incoming = Math.atan2(
      vertices[from].position.y - vertices[to].position.y,
      vertices[from].position.x - vertices[to].position.x
    );
    const outgoing = allEdges.filter((e) => e.fromVertexId === to && e.toVertexId !== from);
    if (outgoing.length === 0) return null;

    let bestEdge: DirectedEdge | null = null;
    let bestAngle = Infinity;
    for (const e of outgoing) {
      const out = Math.atan2(
        vertices[e.toVertexId].position.y - vertices[to].position.y,
        vertices[e.toVertexId].position.x - vertices[to].position.x
      );
      let rel = out - incoming;
      while (rel <= 0) rel += Math.PI * 2;
      while (rel > Math.PI * 2) rel -= Math.PI * 2;
      if (rel < bestAngle) {
        bestAngle = rel;
        bestEdge = e;
      }
    }
    if (!bestEdge) return null;
    from = to;
    to = bestEdge.toVertexId;
  }
  return null;
}
