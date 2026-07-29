import { expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { convertVastuLayout } from '../importVastu';
import { validateFloorPlanIntegrity } from '../validation';
import { createWallGeometry } from '@/domains/viewer/services/extrusion';

it('imports and extrudes the detailed reference house', () => {
  const layout = JSON.parse(readFileSync('2D_layout/2dlayoutMaker-main/single_storey_vastu_reference.json', 'utf8'));
  const { geometry, report } = convertVastuLayout(layout);
  console.info('reference-house import report', report);
  expect(report.rooms).toBe(11);
  expect(report.furniture).toBe(40);
  expect(report.unmapped).toEqual([]);
  expect(report.residuals).toEqual([]);
  expect(validateFloorPlanIntegrity(geometry).errors).toEqual([]);
  for (const wall of Object.values(geometry.walls)) {
    const a = geometry.vertices[wall.startVertexId].position;
    const b = geometry.vertices[wall.endVertexId].position;
    const openings = wall.openingIds.map((id) => geometry.openings[id]);
    const positions = createWallGeometry(a, b, wall.thickness, wall.height, undefined, openings).getAttribute('position');
    expect(positions.count).toBeGreaterThan(0);
    expect(Array.from(positions.array).every(Number.isFinite)).toBe(true);
  }
});

it('imports and extrudes the 60x60 ground-floor compatibility house', () => {
  const layout = JSON.parse(readFileSync('2D_layout/2dlayoutMaker-main/ground_floor_60x60_reference.json', 'utf8'));
  const { geometry, report } = convertVastuLayout(layout);
  console.info('60x60 ground-floor import report', report);

  expect(report.rooms).toBe(19);
  expect(report.furniture).toBe(43);
  expect(report.openings).toBe(37);
  expect(Object.values(geometry.openings).filter((opening) => opening.type === 'door')).toHaveLength(24);
  expect(Object.values(geometry.openings).filter((opening) => opening.type === 'window')).toHaveLength(13);
  expect(report.annotations).toBe(4);
  expect(report.unmapped).toEqual(['black-box']);
  expect(report.residuals).toEqual([]);
  expect(Object.values(geometry.annotations)).toContainEqual(expect.objectContaining({
    text: '⚠ ASSET UNAVAILABLE: black-box',
    color: '#ef4444',
  }));
  expect(validateFloorPlanIntegrity(geometry).errors).toEqual([]);

  for (const wall of Object.values(geometry.walls)) {
    const a = geometry.vertices[wall.startVertexId].position;
    const b = geometry.vertices[wall.endVertexId].position;
    const openings = wall.openingIds.map((id) => geometry.openings[id]);
    const positions = createWallGeometry(a, b, wall.thickness, wall.height, undefined, openings).getAttribute('position');
    expect(positions.count).toBeGreaterThan(0);
    expect(Array.from(positions.array).every(Number.isFinite)).toBe(true);
  }
});
