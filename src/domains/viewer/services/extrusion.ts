// src/domains/viewer/services/extrusion.ts

import * as THREE from 'three';
import type { Point2D } from '@/types/geometry';
import type { MiterOffsets } from '@/domains/editor/services/wallOps';

const CM_TO_M = 0.01;

import { useAppStore } from '@/store';

/** An opening reduced to a clamped rectangle in the wall's 2D shape space (meters). */
type OpeningRect = {
  left: number;
  right: number;
  bottom: number;
  top: number;
  /** True when the sill reaches the floor (a doorway) ⇒ cut as a notch, not a hole. */
  toFloor: boolean;
};

/**
 * Builds a BufferGeometry for one wall using ExtrudeGeometry so that holes
 * (doors, windows, vents) can be natively punched out of the wall surface.
 */
export function createWallGeometry(
  start: Point2D,
  end: Point2D,
  thicknessCm: number,
  heightCm: number,
  offsets?: MiterOffsets,
  wallId?: string
): THREE.BufferGeometry {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthCm = Math.hypot(dx, dy);
  if (lengthCm < 0.01) return new THREE.BufferGeometry();

  const lenM = lengthCm * CM_TO_M;
  const hM = heightCm * CM_TO_M;
  const thickM = thicknessCm * CM_TO_M;

  // Geometry guard (meters): EDGE keeps interior holes off the wall boundary; a hole that
  // *touches* the outline is degenerate for the triangulator and tears the mesh into stray
  // holes/slivers. Doors are cut as floor notches instead of holes.
  const EDGE = 0.005; // 5 mm

  // 1. Collect this wall's openings as rectangles, CLAMPED to the wall so an oversized or
  //    badly-placed opening can never breach an edge.
  const rects: OpeningRect[] = [];
  if (wallId) {
    const state = useAppStore.getState();
    const wall = state.walls[wallId];
    if (wall && wall.openingIds) {
      for (const oid of wall.openingIds) {
        const opening = state.openings[oid];
        if (!opening) continue;
        // ACs are surface-mounted units, not holes — never cut the wall for them.
        if (opening.type === 'ac') continue;
        const ox = opening.offsetCm * CM_TO_M;
        const oy = opening.elevation * CM_TO_M;
        const ow = opening.width * CM_TO_M;
        const oh = opening.height * CM_TO_M;
        if (ow <= 0 || oh <= 0) continue;

        const left = Math.max(0, Math.min(lenM, ox - ow / 2));
        const right = Math.max(0, Math.min(lenM, ox + ow / 2));
        if (right - left < 0.01) continue; // entirely outside / too thin after clamping

        const toFloor = opening.type === 'door'; // doorways open to the floor
        const bottom = toFloor ? 0 : oy;
        const top = Math.min(hM, oy + oh);
        if (top - bottom < 0.01) continue;

        rects.push({ left, right, bottom, top, toFloor });
      }
    }
  }

  // 2. Build the wall outline. Doorways (sill on the floor) become NOTCHES so they open
  //    all the way down while staying watertight; windows/vents are punched as holes.
  const notches = rects.filter((r) => r.toFloor).sort((a, b) => a.left - b.left);
  const windows = rects.filter((r) => !r.toFloor);

  // Merge overlapping/adjacent doorways so the bottom outline stays a simple path.
  const merged: OpeningRect[] = [];
  for (const r of notches) {
    const last = merged[merged.length - 1];
    if (last && r.left <= last.right + EDGE) {
      last.right = Math.max(last.right, r.right);
      last.top = Math.max(last.top, r.top);
    } else {
      merged.push({ ...r });
    }
  }

  const shape = new THREE.Shape();
  shape.moveTo(0, 0);
  let cursorX = 0;
  for (const n of merged) {
    // Keep a thin lintel above very tall doorways so the wall stays one connected piece.
    const top = Math.min(n.top, hM - EDGE);
    if (n.left > cursorX) shape.lineTo(n.left, 0); // floor run up to the doorway
    shape.lineTo(n.left, top);   // up the near jamb
    shape.lineTo(n.right, top);  // across the head
    shape.lineTo(n.right, 0);    // down the far jamb
    cursorX = n.right;
  }
  if (cursorX < lenM) shape.lineTo(lenM, 0);
  shape.lineTo(lenM, hM);
  shape.lineTo(0, hM);
  shape.lineTo(0, 0);

  // 3. Punch windows / vents as interior holes, inset from every edge so they never meet
  //    the wall boundary.
  for (const w of windows) {
    const left = Math.max(EDGE, w.left);
    const right = Math.min(lenM - EDGE, w.right);
    const bottom = Math.max(EDGE, w.bottom);
    const top = Math.min(hM - EDGE, w.top);
    if (right - left < 0.01 || top - bottom < 0.01) continue;

    const hole = new THREE.Path();
    hole.moveTo(left, bottom);
    hole.lineTo(left, top);
    hole.lineTo(right, top);
    hole.lineTo(right, bottom);
    hole.lineTo(left, bottom);
    shape.holes.push(hole);
  }

  // 4. Extrude the shape
  const extrudeSettings: THREE.ExtrudeGeometryOptions = {
    depth: thickM,
    bevelEnabled: false,
  };
  const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);

  // ExtrudeGeometry builds along the Z axis (0 to depth).
  // We need the wall to be centered on Z, so we translate Z by -thickM/2.
  geometry.translate(0, 0, -thickM / 2);

  // Apply miter offsets by shearing the vertices before rotating
  const posAttribute = geometry.getAttribute('position');
  const posArray = posAttribute.array as Float32Array;
  for (let i = 0; i < posArray.length; i += 3) {
    const x = posArray[i];
    const z = posArray[i + 2];
    
    // Left face is z < 0, right face is z > 0
    const isLeft = z < 0;
    const sOffset = isLeft ? (offsets?.startLeft ?? 0) : (offsets?.startRight ?? 0);
    const eOffset = isLeft ? -(offsets?.endRight ?? 0) : -(offsets?.endLeft ?? 0);
    
    const sOffsetM = sOffset * CM_TO_M;
    const eOffsetM = eOffset * CM_TO_M;
    
    const t = lenM > 0.001 ? x / lenM : 0;
    const shift = sOffsetM * (1 - t) + eOffsetM * t;
    
    posArray[i] = x + shift;
  }

  // By default, the shape's X is the wall length, Y is wall height, Z is thickness.
  // We want to orient this geometry to match the start->end vector.
  const angle = Math.atan2(dy, dx); // Angle in 2D plan

  // The 2D plan has +Y pointing "down" visually on screen, but mathematically in ThreeJS +Z is "down/forward".
  // Let's use a Matrix4 to place it exactly.
  // Start point in 3D:
  const sx = start.x * CM_TO_M;
  const sz = -start.y * CM_TO_M; // plan y to 3D -z

  const matrix = new THREE.Matrix4();
  // Translate to start
  matrix.makeTranslation(sx, 0, sz);
  // Rotate around Y axis
  const rotation = new THREE.Matrix4().makeRotationY(angle);
  matrix.multiply(rotation);

  geometry.applyMatrix4(matrix);

  // Compute vertex normals for lighting
  geometry.computeVertexNormals();

  return geometry;
}
