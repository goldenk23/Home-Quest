// src/domains/editor/services/marqueeSelect.ts

import type { Point2D } from '@/types/geometry';
import type { EntityId, Vertex, Wall, FurnitureItem, Pillar, Beam, Road, DeckSlab, Railing } from '@/types/editor';

/** Axis-aligned world-space rectangle (cm). */
export interface WorldRect {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/** Build a normalized rect from two corner points (any order). */
export function normalizeRect(a: Point2D, b: Point2D): WorldRect {
  return {
    minX: Math.min(a.x, b.x),
    maxX: Math.max(a.x, b.x),
    minY: Math.min(a.y, b.y),
    maxY: Math.max(a.y, b.y),
  };
}

export function pointInRect(p: Point2D, r: WorldRect): boolean {
  return p.x >= r.minX && p.x <= r.maxX && p.y >= r.minY && p.y <= r.maxY;
}

/** A segment "hits" the rect when either endpoint or its midpoint falls inside. */
function segmentInRect(a: Point2D, b: Point2D, r: WorldRect): boolean {
  return (
    pointInRect(a, r) ||
    pointInRect(b, r) ||
    pointInRect({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, r)
  );
}

export interface MarqueeGeometry {
  vertices: Record<EntityId, Vertex>;
  walls: Record<EntityId, Wall>;
  furniture: Record<EntityId, FurnitureItem>;
  pillars: Record<EntityId, Pillar>;
  beams: Record<EntityId, Beam>;
  roads: Record<EntityId, Road>;
  deckSlabs: Record<EntityId, DeckSlab>;
  railings: Record<EntityId, Railing>;
}

/**
 * Ids of every deletable entity whose geometry intersects `rect`. Walls/roads/beams/railings
 * count if an endpoint or midpoint is inside; furniture/pillars if their center is inside;
 * deck slabs if any polygon vertex is inside. Openings are omitted (they belong to walls and
 * are removed with them). ponytail: midpoint test is a cheap approximation of true
 * segment-rect clipping — good enough for a marquee erase; upgrade to a clip test if needed.
 */
export function collectEntitiesInRect(g: MarqueeGeometry, rect: WorldRect): EntityId[] {
  const ids: EntityId[] = [];

  for (const f of Object.values(g.furniture)) {
    if (pointInRect(f.position, rect)) ids.push(f.id);
  }
  for (const p of Object.values(g.pillars)) {
    if (pointInRect(p.position, rect)) ids.push(p.id);
  }
  for (const w of Object.values(g.walls)) {
    const a = g.vertices[w.startVertexId]?.position;
    const b = g.vertices[w.endVertexId]?.position;
    if (a && b && segmentInRect(a, b, rect)) ids.push(w.id);
  }
  for (const r of Object.values(g.roads)) {
    if (segmentInRect(r.start, r.end, rect)) ids.push(r.id);
  }
  for (const beam of Object.values(g.beams)) {
    if (segmentInRect(beam.start, beam.end, rect)) ids.push(beam.id);
  }
  for (const rail of Object.values(g.railings)) {
    if (segmentInRect(rail.start, rail.end, rect)) ids.push(rail.id);
  }
  for (const d of Object.values(g.deckSlabs)) {
    if (d.polygon.some((pt) => pointInRect(pt, rect))) ids.push(d.id);
  }

  return ids;
}
