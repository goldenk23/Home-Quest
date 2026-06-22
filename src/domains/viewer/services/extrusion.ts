// src/domains/viewer/services/extrusion.ts

import * as THREE from 'three';
import type { Point2D } from '@/types/geometry';
import type { MiterOffsets } from '@/domains/editor/services/wallOps';

const CM_TO_M = 0.01;

/**
 * Builds a BufferGeometry for one wall: a rectangular prism standing on the ground,
 * long axis along the wall, with correct per‑face normals and UVs for texturing.
 */
export function createWallGeometry(
  start: Point2D,
  end: Point2D,
  thicknessCm: number,
  heightCm: number,
  offsets?: MiterOffsets
): THREE.BufferGeometry {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  if (length < 0.01) return new THREE.BufferGeometry(); // skip degenerate walls

  const vx = dx / length;
  const vy = dy / length;

  // 2D perpendicular unit vector — offsets the centerline to the two wall faces.
  const nx = -vy;
  const ny = vx;
  const halfThick = thicknessCm / 2;
  const h = heightCm;

  const sLeft = offsets?.startLeft ?? 0;
  const sRight = offsets?.startRight ?? 0;
  const eLeft = offsets?.endLeft ?? 0;
  const eRight = offsets?.endRight ?? 0;

  const corners2D = {
    startLeft: { x: start.x + nx * halfThick + vx * sLeft, y: start.y + ny * halfThick + vy * sLeft },
    startRight: { x: start.x - nx * halfThick + vx * sRight, y: start.y - ny * halfThick + vy * sRight },
    endLeft: { x: end.x + nx * halfThick - vx * eRight, y: end.y + ny * halfThick - vy * eRight },
    endRight: { x: end.x - nx * halfThick - vx * eLeft, y: end.y - ny * halfThick - vy * eLeft },
  };

  // Convert each corner to 3D (meters). Bottom at y=0, top at y=height. 2D‑Y → 3D‑(−Z).
  const v = {
    bsl: [corners2D.startLeft.x * CM_TO_M, 0, -corners2D.startLeft.y * CM_TO_M],
    bsr: [corners2D.startRight.x * CM_TO_M, 0, -corners2D.startRight.y * CM_TO_M],
    bel: [corners2D.endLeft.x * CM_TO_M, 0, -corners2D.endLeft.y * CM_TO_M],
    ber: [corners2D.endRight.x * CM_TO_M, 0, -corners2D.endRight.y * CM_TO_M],
    tsl: [corners2D.startLeft.x * CM_TO_M, h * CM_TO_M, -corners2D.startLeft.y * CM_TO_M],
    tsr: [corners2D.startRight.x * CM_TO_M, h * CM_TO_M, -corners2D.startRight.y * CM_TO_M],
    tel: [corners2D.endLeft.x * CM_TO_M, h * CM_TO_M, -corners2D.endLeft.y * CM_TO_M],
    ter: [corners2D.endRight.x * CM_TO_M, h * CM_TO_M, -corners2D.endRight.y * CM_TO_M],
  };

  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  let vertexOffset = 0;

  // Adds one quad (4 verts, 2 triangles) with a flat normal and simple UVs.
  function addFace(p0: number[], p1: number[], p2: number[], p3: number[], normal: number[], uW: number, uH: number) {
    positions.push(...p0, ...p1, ...p2, ...p3);
    normals.push(...normal, ...normal, ...normal, ...normal);
    uvs.push(0, 0, uW, 0, uW, uH, 0, uH);
    indices.push(vertexOffset, vertexOffset + 1, vertexOffset + 2, vertexOffset, vertexOffset + 2, vertexOffset + 3);
    vertexOffset += 4;
  }

  const lenM = length * CM_TO_M;
  const hM = h * CM_TO_M;
  const thickM = thicknessCm * CM_TO_M;

  addFace(v.bsl, v.bel, v.tel, v.tsl, [nx, 0, -ny], lenM, hM);            // left face
  addFace(v.ber, v.bsr, v.tsr, v.ter, [-nx, 0, ny], lenM, hM);           // right face
  addFace(v.bsr, v.bsl, v.tsl, v.tsr, [-vx, 0, vy], thickM, hM); // start cap (adjusted normal to -v instead of -dx/len)
  addFace(v.bel, v.ber, v.ter, v.tel, [vx, 0, -vy], thickM, hM); // end cap (adjusted normal to v instead of dx/len)
  addFace(v.tsl, v.tel, v.ter, v.tsr, [0, 1, 0], lenM, thickM);          // top
  addFace(v.bsr, v.ber, v.bel, v.bsl, [0, -1, 0], lenM, thickM);         // bottom

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  return geometry;
}
