// src/store/persistence/validation.ts

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/** Validates a parsed floor-plan object. Errors block import; warnings don't. */
export function validateFloorPlanIntegrity(data: any): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!data.vertices || typeof data.vertices !== 'object') errors.push('Missing or invalid vertices field');
  if (!data.walls || typeof data.walls !== 'object') errors.push('Missing or invalid walls field');
  if (!data.rooms || typeof data.rooms !== 'object') errors.push('Missing or invalid rooms field');
  if (!data.furniture || typeof data.furniture !== 'object') errors.push('Missing or invalid furniture field');
  if (data.pillars && typeof data.pillars !== 'object') errors.push('Invalid pillars field');
  if (data.beams && typeof data.beams !== 'object') errors.push('Invalid beams field');
  if (data.deckSlabs && typeof data.deckSlabs !== 'object') errors.push('Invalid deckSlabs field');
  if (data.railings && typeof data.railings !== 'object') errors.push('Invalid railings field');
  if (errors.length > 0) return { valid: false, errors, warnings };

  for (const [id, vertex] of Object.entries(data.vertices as Record<string, any>)) {
    const pos = vertex.position;
    if (!pos || typeof pos.x !== 'number' || typeof pos.y !== 'number') errors.push(`Vertex ${id}: invalid position`);
    else if (!Number.isFinite(pos.x) || !Number.isFinite(pos.y)) errors.push(`Vertex ${id}: non-finite coordinates`);
  }

  for (const [id, wall] of Object.entries(data.walls as Record<string, any>)) {
    if (!data.vertices[wall.startVertexId]) errors.push(`Wall ${id}: references non-existent start vertex ${wall.startVertexId}`);
    if (!data.vertices[wall.endVertexId]) errors.push(`Wall ${id}: references non-existent end vertex ${wall.endVertexId}`);
    if (wall.thickness <= 0 || wall.thickness > 200) warnings.push(`Wall ${id}: unusual thickness ${wall.thickness}cm`);
    if (wall.height <= 0 || wall.height > 2000) warnings.push(`Wall ${id}: unusual height ${wall.height}cm`);
  }

  for (const [id, room] of Object.entries(data.rooms as Record<string, any>)) {
    if (!Array.isArray(room.boundaryVertexIds)) {
      errors.push(`Room ${id}: boundaryVertexIds is not an array`);
      continue;
    }
    for (const vid of room.boundaryVertexIds) {
      if (!data.vertices[vid]) errors.push(`Room ${id}: references non-existent vertex ${vid}`);
    }
    if (room.boundaryVertexIds.length < 3) errors.push(`Room ${id}: fewer than 3 boundary vertices`);
  }

  for (const [id, item] of Object.entries(data.furniture as Record<string, any>)) {
    if (!item.position || typeof item.position.x !== 'number') errors.push(`Furniture ${id}: invalid position`);
    if (item.roomId && !data.rooms[item.roomId]) warnings.push(`Furniture ${id}: references non-existent room ${item.roomId}`);
  }

  for (const [id, pillar] of Object.entries((data.pillars ?? {}) as Record<string, any>)) {
    const pos = pillar.position;
    if (!pos || typeof pos.x !== 'number' || typeof pos.y !== 'number') errors.push(`Pillar ${id}: invalid position`);
    if (pillar.width <= 0 || pillar.depth <= 0) errors.push(`Pillar ${id}: invalid footprint`);
    if (pillar.height <= 0 || pillar.height > 3000) warnings.push(`Pillar ${id}: unusual height ${pillar.height}cm`);
  }

  for (const [id, beam] of Object.entries((data.beams ?? {}) as Record<string, any>)) {
    if (!beam.start || typeof beam.start.x !== 'number' || !beam.end || typeof beam.end.x !== 'number') errors.push(`Beam ${id}: invalid endpoints`);
    if (beam.width <= 0 || beam.depth <= 0) errors.push(`Beam ${id}: invalid profile`);
  }

  for (const [id, slab] of Object.entries((data.deckSlabs ?? {}) as Record<string, any>)) {
    if (!Array.isArray(slab.polygon) || slab.polygon.length < 3) errors.push(`Deck slab ${id}: invalid polygon`);
    if (slab.thicknessCm <= 0) errors.push(`Deck slab ${id}: invalid thickness`);
  }

  for (const [id, railing] of Object.entries((data.railings ?? {}) as Record<string, any>)) {
    if (!railing.start || typeof railing.start.x !== 'number' || !railing.end || typeof railing.end.x !== 'number') errors.push(`Railing ${id}: invalid endpoints`);
    if (railing.height <= 0 || railing.height > 300) warnings.push(`Railing ${id}: unusual height ${railing.height}cm`);
    if (railing.style && railing.style !== 'open' && railing.style !== 'solid') errors.push(`Railing ${id}: invalid style`);
  }

  for (const [id, vertex] of Object.entries(data.vertices as Record<string, any>)) {
    const connected = (vertex.connectedWalls || []).filter((wid: string) => data.walls[wid]);
    if (connected.length === 0) warnings.push(`Vertex ${id}: orphan (connected to no valid walls)`);
  }

  return { valid: errors.length === 0, errors, warnings };
}
