// src/domains/editor/services/buildingClone.ts
//
// Pure helpers for the "array a whole building unit" feature: deep-clone every entity that
// makes up the building (the wall/vertex graph, rooms, openings, pillars, beams, decks,
// railings, furniture), remapping all cross-references onto fresh ids and offsetting every
// position by a vector. Pure (no store/THREE) so it's testable and reusable by the store
// action that appends the clones.

import type { Point2D } from '@/types/geometry';
import type {
  EntityId, Vertex, Wall, Room, Opening, Pillar, Beam, DeckSlab, Railing, FurnitureItem,
} from '@/types/editor';

export interface BuildingGeometry {
  vertices: Record<EntityId, Vertex>;
  walls: Record<EntityId, Wall>;
  rooms: Record<EntityId, Room>;
  openings: Record<EntityId, Opening>;
  pillars: Record<EntityId, Pillar>;
  beams: Record<EntityId, Beam>;
  deckSlabs: Record<EntityId, DeckSlab>;
  railings: Record<EntityId, Railing>;
  furniture: Record<EntityId, FurnitureItem>;
}

const shift = (p: Point2D, o: Point2D): Point2D => ({ x: p.x + o.x, y: p.y + o.y });

/** Axis-aligned plan bounds of everything in the building, or null when it's empty. */
export function computeBuildingBounds(g: BuildingGeometry): { min: Point2D; max: Point2D; center: Point2D } | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const acc = (p: Point2D) => {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  };
  for (const v of Object.values(g.vertices)) acc(v.position);
  for (const p of Object.values(g.pillars)) acc(p.position);
  for (const b of Object.values(g.beams)) { acc(b.start); acc(b.end); }
  for (const r of Object.values(g.railings)) { acc(r.start); acc(r.end); }
  for (const d of Object.values(g.deckSlabs)) for (const pt of d.polygon) acc(pt);
  for (const f of Object.values(g.furniture)) acc(f.position);

  if (!Number.isFinite(minX)) return null;
  return { min: { x: minX, y: minY }, max: { x: maxX, y: maxY }, center: { x: (minX + maxX) / 2, y: (minY + maxY) / 2 } };
}

/**
 * Clone every building entity, offset by `offset`, with brand-new ids. `genId(prefix)`
 * supplies unique ids (pass the app's generateId). Cross-references (wall→vertices,
 * opening→wall, room→vertices, furniture→room, vertex→walls) are all remapped onto the new
 * ids so the copy is a fully independent, self-consistent building.
 */
export function cloneGeometry(
  src: BuildingGeometry,
  offset: Point2D,
  genId: (prefix: string) => EntityId,
): BuildingGeometry {
  // 1. Build old→new id maps first so references can be remapped in any order.
  const vMap = new Map<EntityId, EntityId>();
  const wMap = new Map<EntityId, EntityId>();
  const oMap = new Map<EntityId, EntityId>();
  const rMap = new Map<EntityId, EntityId>();
  for (const id of Object.keys(src.vertices)) vMap.set(id, genId('vertex'));
  for (const id of Object.keys(src.walls)) wMap.set(id, genId('wall'));
  for (const id of Object.keys(src.openings)) oMap.set(id, genId('opening'));
  for (const id of Object.keys(src.rooms)) rMap.set(id, genId('room'));

  const out: BuildingGeometry = {
    vertices: {}, walls: {}, rooms: {}, openings: {},
    pillars: {}, beams: {}, deckSlabs: {}, railings: {}, furniture: {},
  };

  for (const [id, v] of Object.entries(src.vertices)) {
    const nid = vMap.get(id)!;
    out.vertices[nid] = {
      id: nid,
      position: shift(v.position, offset),
      connectedWalls: v.connectedWalls.map((w) => wMap.get(w)).filter((x): x is EntityId => !!x),
    };
  }

  for (const [id, w] of Object.entries(src.walls)) {
    const nid = wMap.get(id)!;
    out.walls[nid] = {
      ...w,
      id: nid,
      startVertexId: vMap.get(w.startVertexId) ?? w.startVertexId,
      endVertexId: vMap.get(w.endVertexId) ?? w.endVertexId,
      openingIds: w.openingIds.map((o) => oMap.get(o)).filter((x): x is EntityId => !!x),
    };
  }

  for (const [id, o] of Object.entries(src.openings)) {
    const nid = oMap.get(id)!;
    out.openings[nid] = { ...o, id: nid, wallId: wMap.get(o.wallId) ?? o.wallId };
  }

  for (const [id, r] of Object.entries(src.rooms)) {
    const nid = rMap.get(id)!;
    out.rooms[nid] = {
      ...r,
      id: nid,
      boundaryVertexIds: r.boundaryVertexIds.map((v) => vMap.get(v) ?? v),
    };
  }

  for (const p of Object.values(src.pillars)) {
    const nid = genId('pillar');
    out.pillars[nid] = { ...p, id: nid, position: shift(p.position, offset) };
  }
  for (const b of Object.values(src.beams)) {
    const nid = genId('beam');
    out.beams[nid] = { ...b, id: nid, start: shift(b.start, offset), end: shift(b.end, offset) };
  }
  for (const d of Object.values(src.deckSlabs)) {
    const nid = genId('deck-slab');
    out.deckSlabs[nid] = { ...d, id: nid, polygon: d.polygon.map((pt) => shift(pt, offset)) };
  }
  for (const rl of Object.values(src.railings)) {
    const nid = genId('railing');
    out.railings[nid] = { ...rl, id: nid, start: shift(rl.start, offset), end: shift(rl.end, offset) };
  }
  for (const f of Object.values(src.furniture)) {
    const nid = genId('furniture');
    out.furniture[nid] = { ...f, id: nid, position: shift(f.position, offset), roomId: f.roomId ? (rMap.get(f.roomId) ?? null) : null };
  }

  return out;
}
