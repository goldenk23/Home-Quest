// src/domains/editor/services/roomDetection.ts

import type { EntityId, Vertex, Wall, Room } from '@/types/editor';
import type { Point2D } from '@/types/geometry';
import { generateId } from '@/utils/id';

interface DirectedEdge {
  wallId: EntityId;
  fromVertexId: EntityId;
  toVertexId: EntityId;
}

/**
 * Finds all rooms (minimal enclosed loops) in the wall graph.
 *
 * Every wall becomes two directed edges (one per direction). Starting from each unused
 * directed edge we trace a loop using the "smallest counter‑clockwise turn" rule, which
 * is the standard way to extract faces from a planar graph. Interior loops come out
 * wound counter‑clockwise (positive signed area); the lone exterior loop is clockwise
 * (negative) and is discarded.
 */
export function detectRooms(
  vertices: Record<EntityId, Vertex>,
  walls: Record<EntityId, Wall>
): Room[] {
  const rooms: Room[] = [];
  const visitedEdges = new Set<string>();

  // Build both directed edges for every wall.
  const directedEdges: DirectedEdge[] = [];
  for (const wall of Object.values(walls)) {
    directedEdges.push({ wallId: wall.id, fromVertexId: wall.startVertexId, toVertexId: wall.endVertexId });
    directedEdges.push({ wallId: wall.id, fromVertexId: wall.endVertexId, toVertexId: wall.startVertexId });
  }

  for (const startEdge of directedEdges) {
    const key = `${startEdge.fromVertexId}->${startEdge.toVertexId}`;
    if (visitedEdges.has(key)) continue;

    const cycle = traceCycle(startEdge, vertices, directedEdges);
    if (!cycle) continue;

    // Mark every directed edge of this loop as used so we don't trace it again.
    for (let i = 0; i < cycle.length; i++) {
      const from = cycle[i];
      const to = cycle[(i + 1) % cycle.length];
      visitedEdges.add(`${from}->${to}`);
    }

    // Positive area ⇒ interior face ⇒ a real room. Negative ⇒ exterior boundary ⇒ skip.
    const polygon = cycle.map((vid) => vertices[vid].position);
    if (computeSignedArea(polygon) > 0) {
      rooms.push({
        id: generateId('room'),
        boundaryVertexIds: cycle,
        roomType: 'custom',
        label: `Room ${rooms.length + 1}`,
        floorMaterialId: 'default-floor',
      });
    }
  }

  return rooms;
}

/**
 * Traces one loop by always taking the smallest CCW turn at each vertex.
 * Returns the ordered vertex IDs of the loop, or null if it dead‑ends or runs too long
 * (the length cap guards against infinite loops on malformed graphs).
 */
function traceCycle(
  startEdge: DirectedEdge,
  vertices: Record<EntityId, Vertex>,
  allEdges: DirectedEdge[]
): EntityId[] | null {
  const MAX_CYCLE_LENGTH = 100;
  const cycle: EntityId[] = [startEdge.fromVertexId];

  let currentFrom = startEdge.fromVertexId;
  let currentTo = startEdge.toVertexId;

  for (let step = 0; step < MAX_CYCLE_LENGTH; step++) {
    // Closed the loop back to the start?
    if (currentTo === startEdge.fromVertexId) {
      return cycle.length >= 3 ? cycle : null;
    }
    cycle.push(currentTo);

    // Direction we arrived from, measured at the current vertex.
    const incomingAngle = Math.atan2(
      vertices[currentFrom].position.y - vertices[currentTo].position.y,
      vertices[currentFrom].position.x - vertices[currentTo].position.x
    );

    // All ways out of currentTo except straight back where we came from.
    const outgoing = allEdges.filter((e) => e.fromVertexId === currentTo && e.toVertexId !== currentFrom);
    if (outgoing.length === 0) return null; // dead end

    // Pick the outgoing edge with the smallest counter‑clockwise turn.
    let bestEdge: DirectedEdge | null = null;
    let bestAngle = Infinity;
    for (const edge of outgoing) {
      const outAngle = Math.atan2(
        vertices[edge.toVertexId].position.y - vertices[currentTo].position.y,
        vertices[edge.toVertexId].position.x - vertices[currentTo].position.x
      );
      let rel = outAngle - incomingAngle;
      while (rel <= 0) rel += Math.PI * 2; // normalize into (0, 2π]
      while (rel > Math.PI * 2) rel -= Math.PI * 2;
      if (rel < bestAngle) {
        bestAngle = rel;
        bestEdge = edge;
      }
    }
    if (!bestEdge) return null;

    currentFrom = currentTo;
    currentTo = bestEdge.toVertexId;
  }

  return null; // exceeded the safety cap
}

/**
 * Signed polygon area via the shoelace formula.
 * Positive ⇒ counter‑clockwise winding, negative ⇒ clockwise.
 */
export function computeSignedArea(polygon: Point2D[]): number {
  let area = 0;
  const n = polygon.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += polygon[i].x * polygon[j].y - polygon[j].x * polygon[i].y;
  }
  return area / 2;
}

/** Validates a candidate room polygon: ≥3 vertices, non‑degenerate, non‑self‑intersecting. */
export function validateRoomPolygon(vertexIds: EntityId[], vertices: Record<EntityId, Vertex>): boolean {
  if (vertexIds.length < 3) return false;
  const polygon = vertexIds.map((id) => vertices[id]?.position).filter((p): p is Point2D => Boolean(p));
  if (polygon.length < 3) return false;
  if (Math.abs(computeSignedArea(polygon)) < 1) return false; // < 1 cm² is degenerate
  return !hasSelfIntersection(polygon);
}

function hasSelfIntersection(polygon: Point2D[]): boolean {
  const n = polygon.length;
  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue; // adjacent edges legitimately share a vertex
      if (segmentsIntersect(polygon[i], polygon[(i + 1) % n], polygon[j], polygon[(j + 1) % n])) {
        return true;
      }
    }
  }
  return false;
}

function segmentsIntersect(a1: Point2D, a2: Point2D, b1: Point2D, b2: Point2D): boolean {
  const d1x = a2.x - a1.x, d1y = a2.y - a1.y;
  const d2x = b2.x - b1.x, d2y = b2.y - b1.y;
  const cross = d1x * d2y - d1y * d2x;
  if (Math.abs(cross) < 1e-10) return false;
  const dx = b1.x - a1.x, dy = b1.y - a1.y;
  const t = (dx * d2y - dy * d2x) / cross;
  const u = (dx * d1y - dy * d1x) / cross;
  const EPS = 1e-6;
  return t > EPS && t < 1 - EPS && u > EPS && u < 1 - EPS;
}
