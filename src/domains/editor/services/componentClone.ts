import type { Point2D } from '@/types/geometry';
import type {
  Beam,
  DeckSlab,
  EntityId,
  FurnitureItem,
  Opening,
  Pillar,
  Railing,
  Road,
  Vertex,
  Wall,
} from '@/types/editor';

export type CloneableComponentKind = 'furniture' | 'pillar' | 'wall' | 'beam' | 'deck' | 'railing' | 'road';

export interface ComponentCloneGeometry {
  vertices: Record<EntityId, Vertex>;
  walls: Record<EntityId, Wall>;
  openings: Record<EntityId, Opening>;
  pillars: Record<EntityId, Pillar>;
  beams: Record<EntityId, Beam>;
  deckSlabs: Record<EntityId, DeckSlab>;
  railings: Record<EntityId, Railing>;
  furniture: Record<EntityId, FurnitureItem>;
  roads: Record<EntityId, Road>;
}

export interface ComponentCloneResult extends ComponentCloneGeometry {
  createdIds: EntityId[];
}

export interface ComponentBounds {
  min: Point2D;
  max: Point2D;
  center: Point2D;
  kind: CloneableComponentKind;
}

const shift = (p: Point2D, o: Point2D): Point2D => ({ x: p.x + o.x, y: p.y + o.y });

function emptyClone(): ComponentCloneResult {
  return {
    vertices: {},
    walls: {},
    openings: {},
    pillars: {},
    beams: {},
    deckSlabs: {},
    railings: {},
    furniture: {},
    roads: {},
    createdIds: [],
  };
}

function boundsFromPoints(points: Point2D[], kind: CloneableComponentKind): ComponentBounds | null {
  if (points.length === 0) return null;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  if (!Number.isFinite(minX)) return null;
  return {
    min: { x: minX, y: minY },
    max: { x: maxX, y: maxY },
    center: { x: (minX + maxX) / 2, y: (minY + maxY) / 2 },
    kind,
  };
}

export function resolveCloneableComponentKind(id: EntityId, g: ComponentCloneGeometry): CloneableComponentKind | null {
  if (g.furniture[id]) return 'furniture';
  if (g.pillars[id]) return 'pillar';
  if (g.walls[id]) return 'wall';
  if (g.beams[id]) return 'beam';
  if (g.deckSlabs[id]) return 'deck';
  if (g.railings[id]) return 'railing';
  if (g.roads[id]) return 'road';
  return null;
}

/** Axis-aligned plan bounds for a single cloneable component. */
export function computeComponentBounds(id: EntityId, g: ComponentCloneGeometry): ComponentBounds | null {
  const furniture = g.furniture[id];
  if (furniture) {
    const halfW = (furniture.bounds.width * furniture.scale) / 2;
    const halfD = (furniture.bounds.depth * furniture.scale) / 2;
    return boundsFromPoints([
      { x: furniture.position.x - halfW, y: furniture.position.y - halfD },
      { x: furniture.position.x + halfW, y: furniture.position.y + halfD },
    ], 'furniture');
  }

  const pillar = g.pillars[id];
  if (pillar) {
    const halfW = pillar.width / 2;
    const halfD = pillar.depth / 2;
    return boundsFromPoints([
      { x: pillar.position.x - halfW, y: pillar.position.y - halfD },
      { x: pillar.position.x + halfW, y: pillar.position.y + halfD },
    ], 'pillar');
  }

  const wall = g.walls[id];
  if (wall) {
    const s = g.vertices[wall.startVertexId]?.position;
    const e = g.vertices[wall.endVertexId]?.position;
    return s && e ? boundsFromPoints([s, e], 'wall') : null;
  }

  const beam = g.beams[id];
  if (beam) return boundsFromPoints([beam.start, beam.end], 'beam');

  const slab = g.deckSlabs[id];
  if (slab) return boundsFromPoints(slab.polygon, 'deck');

  const railing = g.railings[id];
  if (railing) return boundsFromPoints([railing.start, railing.end], 'railing');

  const road = g.roads[id];
  if (road) return boundsFromPoints([road.start, road.end], 'road');

  return null;
}

/**
 * Clone one selected component by `offset`. Wall clones include fresh endpoint vertices and
 * their wall openings, so the copy is independent and can be dragged without moving the
 * original wall graph.
 */
export function cloneComponent(
  src: ComponentCloneGeometry,
  id: EntityId,
  offset: Point2D,
  genId: (prefix: string) => EntityId,
): ComponentCloneResult | null {
  const out = emptyClone();

  const furniture = src.furniture[id];
  if (furniture) {
    const nid = genId('furniture');
    out.furniture[nid] = { ...furniture, id: nid, position: shift(furniture.position, offset), roomId: null };
    out.createdIds.push(nid);
    return out;
  }

  const pillar = src.pillars[id];
  if (pillar) {
    const nid = genId('pillar');
    out.pillars[nid] = { ...pillar, id: nid, position: shift(pillar.position, offset) };
    out.createdIds.push(nid);
    return out;
  }

  const wall = src.walls[id];
  if (wall) {
    const start = src.vertices[wall.startVertexId];
    const end = src.vertices[wall.endVertexId];
    if (!start || !end) return null;
    const newWallId = genId('wall');
    const newStartId = genId('vertex');
    const newEndId = genId('vertex');
    const openingMap = new Map<EntityId, EntityId>();
    for (const openingId of wall.openingIds) {
      if (src.openings[openingId]) openingMap.set(openingId, genId('opening'));
    }

    out.vertices[newStartId] = { id: newStartId, position: shift(start.position, offset), connectedWalls: [newWallId] };
    out.vertices[newEndId] = { id: newEndId, position: shift(end.position, offset), connectedWalls: [newWallId] };
    out.walls[newWallId] = {
      ...wall,
      id: newWallId,
      startVertexId: newStartId,
      endVertexId: newEndId,
      openingIds: [...openingMap.values()],
    };
    for (const [oldOpeningId, newOpeningId] of openingMap.entries()) {
      const opening = src.openings[oldOpeningId];
      out.openings[newOpeningId] = { ...opening, id: newOpeningId, wallId: newWallId };
    }
    out.createdIds.push(newWallId);
    return out;
  }

  const beam = src.beams[id];
  if (beam) {
    const nid = genId('beam');
    out.beams[nid] = { ...beam, id: nid, start: shift(beam.start, offset), end: shift(beam.end, offset) };
    out.createdIds.push(nid);
    return out;
  }

  const slab = src.deckSlabs[id];
  if (slab) {
    const nid = genId('deck-slab');
    out.deckSlabs[nid] = { ...slab, id: nid, polygon: slab.polygon.map((pt) => shift(pt, offset)) };
    out.createdIds.push(nid);
    return out;
  }

  const railing = src.railings[id];
  if (railing) {
    const nid = genId('railing');
    out.railings[nid] = { ...railing, id: nid, start: shift(railing.start, offset), end: shift(railing.end, offset) };
    out.createdIds.push(nid);
    return out;
  }

  const road = src.roads[id];
  if (road) {
    const nid = genId('road');
    out.roads[nid] = { ...road, id: nid, start: shift(road.start, offset), end: shift(road.end, offset) };
    out.createdIds.push(nid);
    return out;
  }

  return null;
}