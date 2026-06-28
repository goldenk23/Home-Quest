// src/domains/viewer/components/WallMesh.tsx

import React, { useMemo, useEffect } from 'react';
import * as THREE from 'three';
import { createWallGeometry } from '../services/extrusion';
import { getMaterial } from '../services/materials';
import { furnitureMaterialProps, getFurnitureMaterial } from '../services/furnitureMaterials';
import { resolveKind } from '@/domains/shared/openings/openingCatalog';
import type { Point2D } from '@/types/geometry';
import type { Opening } from '@/types/editor';
import type { MiterOffsets } from '@/domains/editor/services/wallOps';

interface WallMeshProps {
  id: string;
  start: Point2D;
  end: Point2D;
  thickness: number;
  height: number;
  materialId: string;
  /** Optional per-face paints (side A = +z face, side B = −z face). Fall back to materialId. */
  materialSideA?: string;
  materialSideB?: string;
  offsets?: MiterOffsets;
  /** Openings on this wall (passed in so the mesh works for any floor, active or parked). */
  openings: Opening[];
  /** Room polygons (plan cm) on this floor — used to orient the main gate outward. */
  roomPolys: Point2D[][];
}

const CM_TO_M = 0.01;

/** Vertical lift (m) for door/gate frames so their base clears the floor finish (y=0.02)
 *  and stops z-fighting at the threshold. */
const DOOR_THRESHOLD_LIFT = 0.015;

/**
 * A small, deterministic depth-offset "slot" for a wall, derived from its id.
 *
 * Adjacent walls interpenetrate at a mitred corner: one wall's end cap crosses through the
 * neighbour's face. Where those two surfaces reach the same depth they z-fight, which on the
 * low tier (no anti-aliasing to smooth it) shows up as the radial "fan" streaks across the
 * walls. Two walls of the same finish share one cached material, so a per-finish bias can't
 * separate them — but giving each wall instance a distinct `polygonOffsetUnits` makes one
 * consistently win the depth test at the seam, so the corner renders clean.
 *
 * Integer steps spread symmetrically around 0: small enough to never shove a wall through
 * distant geometry, but a ≥1-unit gap between neighbours reliably resolves on the depth
 * buffer. `factor` is kept at 0 elsewhere so the ordering never changes with camera angle.
 */
function wallDepthOffsetSlot(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return (h % 16) - 8; // integer units in [-8, +7]
}

// A row of nested-square lattice motifs (the geometric "grille" bands at the top and bottom
// of each gate leaf). Each motif is a raised square outline with a small square at its centre.
const SquareMotif: React.FC<{ size: number; depth: number; material: THREE.Material }> = ({ size, depth, material }) => {
  const t = size * 0.16; // bar thickness of the outline
  return (
    <group>
      <mesh material={material} position={[0, size / 2 - t / 2, 0]}><boxGeometry args={[size, t, depth]} /></mesh>
      <mesh material={material} position={[0, -size / 2 + t / 2, 0]}><boxGeometry args={[size, t, depth]} /></mesh>
      <mesh material={material} position={[-size / 2 + t / 2, 0, 0]}><boxGeometry args={[t, size - 2 * t, depth]} /></mesh>
      <mesh material={material} position={[size / 2 - t / 2, 0, 0]}><boxGeometry args={[t, size - 2 * t, depth]} /></mesh>
      <mesh material={material} position={[0, 0, 0]}><boxGeometry args={[t * 1.1, t * 1.1, depth]} /></mesh>
    </group>
  );
};

/**
 * Modern residential main gate: two solid charcoal leaves, each with a nested-square lattice
 * band top and bottom, vertical fluting on the outer half, a raised central panel, and a
 * tall gold pull handle near the centre. A small keypad lock sits where the two leaves meet.
 * Replaces the old "jail bars" look with a contemporary villa gate.
 */
const MainGate: React.FC<{ ow: number; oh: number; frameDepth: number }> = ({ ow, oh, frameDepth }) => {
  const bodyMat = getFurnitureMaterial('matteBlack', '#3b424e'); // charcoal slate body
  const trimMat = getFurnitureMaterial('matteBlack', '#475061'); // slightly lighter raised trim
  const goldMat = getFurnitureMaterial('metal', '#d4af37'); // brass/gold handles
  const keypadMat = getFurnitureMaterial('matteBlack', '#15171c');
  const keypadFace = getFurnitureMaterial('screen', '#1b2742');

  const gap = 0.02; // centre reveal between the two leaves
  const bodyDepth = frameDepth;
  const frontZ = bodyDepth / 2; // front (room-facing) face of the body plate
  const fr = 0.04; // perimeter/trim border width
  const proud = bodyDepth * 0.35; // how far raised trim sits proud of the body face

  const leafW = (ow - gap) / 2;

  // Decorative band geometry (shared by both leaves).
  const bandH = oh * 0.12;
  const topBandY = oh / 2 - fr - bandH / 2;
  const botBandY = -oh / 2 + fr + bandH / 2;
  const midTop = topBandY - bandH / 2 - 0.03;
  const midBot = botBandY + bandH / 2 + 0.03;
  const midH = midTop - midBot;
  const midY = (midTop + midBot) / 2;

  const motifSize = bandH * 0.62;
  const motifCount = Math.max(2, Math.floor(leafW / (motifSize * 1.5)));

  // Renders one leaf. `innerDir` points toward the gate centre in leaf-local coords
  // (+1 for the left leaf, -1 for the right leaf) so handles/panels hug the middle.
  const renderLeaf = (innerDir: 1 | -1, key: string) => {
    const cx = innerDir === 1 ? -(ow + gap) / 4 : (ow + gap) / 4;

    // Raised central panel hugging the inner edge.
    const panelW = leafW * 0.5;
    const panelH = midH * 0.84;
    const panelX = innerDir * (leafW / 2 - fr - panelW / 2);

    // Vertical fluting fills the outer field (between outer frame and the central panel).
    const fluteOuter = -innerDir * (leafW / 2 - fr - 0.02);
    const fluteInner = panelX - innerDir * (panelW / 2 + 0.04);
    const fluteLo = Math.min(fluteOuter, fluteInner);
    const fluteHi = Math.max(fluteOuter, fluteInner);
    const fluteSpan = fluteHi - fluteLo;
    const fluteCount = Math.max(3, Math.floor(fluteSpan / 0.055));
    const fluteH = midH * 0.92;

    // Gold pull handle near the inner edge.
    const handleX = innerDir * (leafW / 2 - fr - 0.05);
    const handleH = midH * 0.4;

    const motifXs = Array.from({ length: motifCount }, (_, i) =>
      -leafW / 2 + fr + 0.02 + ((leafW - 2 * fr - 0.04) * (i + 0.5)) / motifCount
    );

    return (
      <group key={key} position={[cx, 0, 0]}>
        {/* Solid body plate */}
        <mesh material={bodyMat} castShadow receiveShadow><boxGeometry args={[leafW, oh, bodyDepth]} /></mesh>

        {/* Perimeter frame (raised) */}
        <mesh material={trimMat} position={[-leafW / 2 + fr / 2, 0, frontZ + proud / 2]}><boxGeometry args={[fr, oh, proud]} /></mesh>
        <mesh material={trimMat} position={[leafW / 2 - fr / 2, 0, frontZ + proud / 2]}><boxGeometry args={[fr, oh, proud]} /></mesh>
        <mesh material={trimMat} position={[0, oh / 2 - fr / 2, frontZ + proud / 2]}><boxGeometry args={[leafW, fr, proud]} /></mesh>
        <mesh material={trimMat} position={[0, -oh / 2 + fr / 2, frontZ + proud / 2]}><boxGeometry args={[leafW, fr, proud]} /></mesh>

        {/* Top + bottom lattice bands */}
        {motifXs.map((mx, i) => (
          <group key={`tm${i}`} position={[mx, topBandY, frontZ + proud * 0.4]}>
            <SquareMotif size={motifSize} depth={proud * 0.8} material={trimMat} />
          </group>
        ))}
        {motifXs.map((mx, i) => (
          <group key={`bm${i}`} position={[mx, botBandY, frontZ + proud * 0.4]}>
            <SquareMotif size={motifSize} depth={proud * 0.8} material={trimMat} />
          </group>
        ))}

        {/* Vertical fluting on the outer field */}
        {Array.from({ length: fluteCount }).map((_, i) => {
          const fx = fluteLo + (fluteSpan * (i + 0.5)) / fluteCount;
          return (
            <mesh key={`fl${i}`} material={trimMat} position={[fx, midY, frontZ + proud * 0.25]}>
              <boxGeometry args={[0.018, fluteH, proud * 0.5]} />
            </mesh>
          );
        })}

        {/* Raised central panel */}
        <mesh material={trimMat} position={[panelX, midY, frontZ + proud * 0.5]}>
          <boxGeometry args={[panelW, panelH, proud]} />
        </mesh>

        {/* Gold pull handle */}
        <mesh material={goldMat} castShadow position={[handleX, midY, frontZ + proud * 1.15]}>
          <boxGeometry args={[0.05, handleH, 0.03]} />
        </mesh>
      </group>
    );
  };

  return (
    <group>
      {renderLeaf(1, 'leaf-left')}
      {renderLeaf(-1, 'leaf-right')}

      {/* Keypad lock where the leaves meet */}
      <group position={[0, midY - midH * 0.04, frontZ + proud * 0.5]}>
        <mesh material={keypadMat} castShadow><boxGeometry args={[0.07, 0.16, 0.025]} /></mesh>
        <mesh material={keypadFace} position={[0, -0.01, 0.014]}><boxGeometry args={[0.05, 0.08, 0.004]} /></mesh>
        <mesh material={keypadFace} position={[0, 0.055, 0.014]}><cylinderGeometry args={[0.012, 0.012, 0.004, 16]} /></mesh>
      </group>
    </group>
  );
};


/**
 * Sectional garage shutter: a panel that fills the whole opening, divided into horizontal
 * ribbed sections (the classic "garage door" look), with a row of small windows near the
 * top and a centred lift handle. Light powder-coated metal. Fills the opening like the gate
 * does, so the DoorFrame is rendered with no leaves and this supplies the panel.
 */
const GarageShutter: React.FC<{ ow: number; oh: number; frameDepth: number }> = ({ ow, oh, frameDepth }) => {
  const panelMat = getFurnitureMaterial('white', '#cbd5e1');
  const grooveMat = getFurnitureMaterial('matteBlack', '#94a3b8');
  const glassMat = getFurnitureMaterial('glass', '#cde4f5');
  const handleMat = getFurnitureMaterial('metal', '#475569');

  const inset = 0.06; // sits just inside the jambs
  const pw = ow - inset * 2;
  const ph = oh - inset * 2;
  const depth = frameDepth * 0.5;
  const frontZ = frameDepth / 2;

  const sections = Math.max(3, Math.round(ph / 0.5)); // ~50cm tall sections
  const secH = ph / sections;
  // Windows live in the second section from the top.
  const winRow = sections - 2;
  const winCount = Math.max(3, Math.floor(pw / 0.5));

  return (
    <group position={[0, -oh / 2, 0]}>
      <group position={[0, oh / 2, 0]}>
        {/* main slab */}
        <mesh material={panelMat} castShadow receiveShadow position={[0, 0, frontZ - depth / 2]}>
          <boxGeometry args={[pw, ph, depth]} />
        </mesh>
        {/* horizontal groove lines between sections */}
        {Array.from({ length: sections - 1 }).map((_, i) => {
          const y = -ph / 2 + secH * (i + 1);
          return (
            <mesh key={`g${i}`} material={grooveMat} position={[0, y, frontZ + 0.004]}>
              <boxGeometry args={[pw, 0.02, 0.02]} />
            </mesh>
          );
        })}
        {/* a row of small windows near the top */}
        {Array.from({ length: winCount }).map((_, i) => {
          const x = -pw / 2 + (pw * (i + 0.5)) / winCount;
          const y = -ph / 2 + secH * (winRow + 0.5);
          return (
            <mesh key={`w${i}`} material={glassMat} position={[x, y, frontZ + 0.006]}>
              <boxGeometry args={[(pw / winCount) * 0.6, secH * 0.5, 0.02]} />
            </mesh>
          );
        })}
        {/* centred lift handle near the bottom */}
        <mesh material={handleMat} castShadow position={[0, -ph / 2 + secH * 0.5, frontZ + 0.03]}>
          <boxGeometry args={[pw * 0.16, 0.05, 0.04]} />
        </mesh>
      </group>
    </group>
  );
};


/**
 * A realistic door assembly used for standard and double doors (and as the surround for the
 * main gate). Renders a deep timber casing (two jambs + head), a proud architrave trim on
 * BOTH faces, and one or two solid door leaves with raised stiles/rails, recessed panels and
 * a lever handle. The leaf sits centred in the wall thickness; the floor stays open (the wall
 * is cut as a notch), so the doorway is walkable while the frame reads as a real door.
 */
const DoorFrame: React.FC<{ ow: number; oh: number; frameDepth: number; variant: 'single' | 'double' | 'gate' | 'shutter' }> = ({
  ow,
  oh,
  frameDepth,
  variant,
}) => {
  const casingMat = variant === 'gate' || variant === 'shutter' ? getFurnitureMaterial('matteBlack', '#2f343d') : getFurnitureMaterial('darkWood', '#6f5135');
  const leafMat = getFurnitureMaterial('lightWood', '#b3884f');
  const railMat = getFurnitureMaterial('darkWood', '#9a6f3e');
  const handleMat = getFurnitureMaterial('metal', '#c9b079');

  const jamb = Math.min(0.08, ow * 0.07); // casing width
  const depth = frameDepth;
  const archProud = depth * 0.45; // architrave standing proud of the wall face
  const archW = 0.04;
  const innerW = ow - 2 * jamb;
  const innerTop = oh - jamb; // open at the floor, head at the top
  const leafDepth = Math.min(0.05, depth * 0.6);

  // Architrave (flat trim) on one face: a thin border framing the opening, proud of the wall.
  const architrave = (z: number) => (
    <group position={[0, 0, z]}>
      <mesh material={casingMat}><boxGeometry args={[ow + archW, archW, archProud]} /></mesh>
      <mesh material={casingMat} position={[0, oh, 0]}><boxGeometry args={[ow + archW, archW, archProud]} /></mesh>
      <mesh material={casingMat} position={[-ow / 2, oh / 2, 0]}><boxGeometry args={[archW, oh, archProud]} /></mesh>
      <mesh material={casingMat} position={[ow / 2, oh / 2, 0]}><boxGeometry args={[archW, oh, archProud]} /></mesh>
    </group>
  );

  // One leaf: solid body + raised top/bottom rails + two recessed-look panels + a handle.
  const renderLeaf = (leafW: number, cx: number, handleDir: 1 | -1) => {
    const stile = Math.min(0.09, leafW * 0.16);
    const panelW = leafW - 2 * stile;
    const railH = 0.12;
    const proud = leafDepth * 0.35;
    const upperH = innerTop * 0.34;
    const lowerH = innerTop * 0.44;
    const upperY = innerTop - jamb - upperH / 2 - railH;
    const lowerY = lowerH / 2 + railH;
    const panel = (y: number, h: number, z: number) => (
      <mesh material={railMat} position={[cx, y, z]}><boxGeometry args={[panelW, h, proud]} /></mesh>
    );
    const handleX = cx + handleDir * (leafW / 2 - stile * 0.6);
    return (
      <group key={`leaf${cx}`}>
        <mesh material={leafMat} castShadow receiveShadow position={[cx, innerTop / 2, 0]}>
          <boxGeometry args={[leafW - 0.01, innerTop, leafDepth]} />
        </mesh>
        {/* Raised panels, front + back faces. */}
        {panel(upperY, upperH, leafDepth / 2)}
        {panel(lowerY, lowerH, leafDepth / 2)}
        {panel(upperY, upperH, -leafDepth / 2)}
        {panel(lowerY, lowerH, -leafDepth / 2)}
        {/* Lever handles, both faces. */}
        <mesh material={handleMat} castShadow position={[handleX, innerTop * 0.46, leafDepth / 2 + 0.025]}>
          <boxGeometry args={[0.11, 0.025, 0.05]} />
        </mesh>
        <mesh material={handleMat} castShadow position={[handleX, innerTop * 0.46, -leafDepth / 2 - 0.025]}>
          <boxGeometry args={[0.11, 0.025, 0.05]} />
        </mesh>
      </group>
    );
  };

  // The whole frame is positioned by the caller with its CENTRE at the opening centre, so
  // shift down by oh/2 to work in floor-relative (0..oh) coordinates here.
  return (
    <group position={[0, -oh / 2, 0]}>
      {/* Casing: jambs + head. */}
      <mesh material={casingMat} castShadow position={[-ow / 2 + jamb / 2, oh / 2, 0]}><boxGeometry args={[jamb, oh, depth]} /></mesh>
      <mesh material={casingMat} castShadow position={[ow / 2 - jamb / 2, oh / 2, 0]}><boxGeometry args={[jamb, oh, depth]} /></mesh>
      <mesh material={casingMat} castShadow position={[0, oh - jamb / 2, 0]}><boxGeometry args={[ow, jamb, depth]} /></mesh>

      {architrave(depth / 2 + archProud / 2)}
      {architrave(-depth / 2 - archProud / 2)}

      {/* Leaves — skipped for the gate (MainGate supplies its own panels). */}
      {variant === 'double' ? (
        <>
          {renderLeaf(innerW / 2 - 0.005, -innerW / 4, -1)}
          {renderLeaf(innerW / 2 - 0.005, innerW / 4, 1)}
        </>
      ) : variant === 'single' ? (
        renderLeaf(innerW, 0, 1)
      ) : null}
    </group>
  );
};

/** Ray-casting point-in-polygon test (polygon points in plan cm). */
function pointInPoly(px: number, py: number, poly: Point2D[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y, xj = poly[j].x, yj = poly[j].y;
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

const OpeningFrames: React.FC<{ thickness: number; start: Point2D; end: Point2D; openings: Opening[]; roomPolys: Point2D[][] }> = React.memo(({ thickness, start, end, openings, roomPolys }) => {
  if (openings.length === 0) return null;

  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const angle = Math.atan2(dy, dx);
  const sx = start.x * CM_TO_M;
  const sz = -start.y * CM_TO_M;
  const thickM = thickness * CM_TO_M;

  // Plan-space direction of the group's local +z axis (the wall's +normal). Used to decide
  // which side of a wall is "outside" for gate orientation.
  const wallLen = Math.hypot(dx, dy) || 1;
  const zDirX = dy / wallLen;
  const zDirY = -dx / wallLen;

  return (
    <group position={[sx, 0, sz]} rotation={[0, angle, 0]}>
      {openings.map(opening => {
        const kind = resolveKind(opening.kind, opening.type);

        const ox = opening.offsetCm * CM_TO_M;
        const oy = opening.elevation * CM_TO_M;
        const ow = opening.width * CM_TO_M;
        const oh = opening.height * CM_TO_M;

        const frameDepth = thickM; // line the full wall depth so the cut reveal is never raw wall
        const border = 0.05; // 5cm frame border

        // Tuned materials (env-map response so frames/louvres catch the sky, glass reads as
        // real glass). Glass casts/receives NO shadow so sunlight passes cleanly through.
        const frameMaterial = <meshStandardMaterial {...furnitureMaterialProps('white', '#f8fafc')} />;
        const glassMaterial = <meshStandardMaterial {...furnitureMaterialProps('glass', '#cde4f5')} />;
        const louvreMaterial = <meshStandardMaterial {...furnitureMaterialProps('metal', '#cbd5e1')} />;
        const acBodyMaterial = <meshStandardMaterial {...furnitureMaterialProps('white', '#ffffff')} />;
        const acTrimMaterial = <meshStandardMaterial {...furnitureMaterialProps('matteBlack', '#1f2937')} />;

        // ---- Doors --------------------------------------------------------
        if (kind.type === 'door') {
          const variant: 'single' | 'double' | 'gate' | 'shutter' =
            kind.door === 'shutter' ? 'shutter' : kind.door === 'gate' ? 'gate' : kind.id === 'door-double' ? 'double' : 'single';

          // For the main gate / garage shutter, decide which way it should face. Its
          // decorated front is on the +z side; we want that pointing OUTWARD (the side not
          // inside a room). Probe a point just off the +z face at the centre — if it lands
          // inside a room, +z is the interior, so flip the assembly 180° to face outside.
          let gateFlip = false;
          if (variant === 'gate' || variant === 'shutter') {
            const cxPlan = start.x + (dx / wallLen) * opening.offsetCm;
            const cyPlan = start.y + (dy / wallLen) * opening.offsetCm;
            const probe = thickness / 2 + 40; // cm off the face
            const pX = cxPlan + zDirX * probe;
            const pY = cyPlan + zDirY * probe;
            gateFlip = roomPolys.some((poly) => pointInPoly(pX, pY, poly));
          }

          return (
            <group
              key={opening.id}
              // Lift the whole door/gate assembly ~1.5cm so its base clears the room floor
              // finish (which sits at y=0.02). Without this, the bottom architrave bar and the
              // gate body plate are coplanar with the floor at exactly y=0.02 and z-fight,
              // which is the "blinking" band the user saw at the gate base. The door bottom
              // stays just under the finish so no gap shows.
              position={[ox, oy + oh / 2 + DOOR_THRESHOLD_LIFT, 0]}
              rotation={(variant === 'gate' || variant === 'shutter') && gateFlip ? [0, Math.PI, 0] : [0, 0, 0]}
            >
              <DoorFrame ow={ow} oh={oh} frameDepth={frameDepth} variant={variant} />
              {variant === 'gate' && <MainGate ow={ow} oh={oh} frameDepth={frameDepth} />}
              {variant === 'shutter' && <GarageShutter ow={ow} oh={oh} frameDepth={frameDepth} />}
            </group>
          );
        }

        // ---- Air conditioner: surface-mounted unit (protrudes into the room) --
        if (kind.type === 'ac') {
          const acDepth = 0.18;
          const zFront = thickM / 2 + acDepth / 2;
          return (
            <group key={opening.id} position={[ox, oy + oh / 2, zFront]}>
              <mesh castShadow receiveShadow>
                <boxGeometry args={[ow, oh, acDepth]} />
                {acBodyMaterial}
              </mesh>
              <mesh position={[0, -oh / 2 + oh * 0.16, acDepth / 2 - 0.012]} rotation={[Math.PI / 7, 0, 0]}>
                <boxGeometry args={[ow * 0.9, 0.02, acDepth * 0.55]} />
                {acTrimMaterial}
              </mesh>
              <mesh position={[ow * 0.3, -oh / 2 + oh * 0.34, acDepth / 2 + 0.004]}>
                <boxGeometry args={[ow * 0.16, 0.008, 0.005]} />
                {acTrimMaterial}
              </mesh>
            </group>
          );
        }

        // ---- Ventilation: exhaust fan -------------------------------------
        if (kind.type === 'vent' && kind.vent === 'exhaust') {
          const r = Math.min(ow, oh) / 2;
          return (
            <group key={opening.id} position={[ox, oy + oh / 2, 0]}>
              <mesh rotation={[Math.PI / 2, 0, 0]}>
                <cylinderGeometry args={[r, r, frameDepth, 20, 1, true]} />
                {louvreMaterial}
              </mesh>
              <mesh rotation={[Math.PI / 2, 0, 0]}>
                <cylinderGeometry args={[r * 0.18, r * 0.18, frameDepth * 0.6, 12]} />
                {acTrimMaterial}
              </mesh>
              {Array.from({ length: 5 }).map((_, i) => {
                const a = (i / 5) * Math.PI * 2;
                return (
                  <mesh key={i} position={[Math.cos(a) * r * 0.5, Math.sin(a) * r * 0.5, 0]} rotation={[0, 0.4, a]}>
                    <boxGeometry args={[r * 0.8, r * 0.5, 0.006]} />
                    {louvreMaterial}
                  </mesh>
                );
              })}
            </group>
          );
        }

        // ---- Ventilation: louvre grille -----------------------------------
        if (kind.type === 'vent') {
          const slats = Math.max(2, Math.floor((oh - 2 * border) / 0.06));
          const vb = border * 0.7; // surround frame width
          return (
            <group key={opening.id} position={[ox, oy + oh / 2, 0]}>
              {/* Surround frame so the louvre sits in a proper vent box, not floating slats. */}
              <mesh position={[-ow / 2 + vb / 2, 0, 0]}><boxGeometry args={[vb, oh, frameDepth]} />{frameMaterial}</mesh>
              <mesh position={[ow / 2 - vb / 2, 0, 0]}><boxGeometry args={[vb, oh, frameDepth]} />{frameMaterial}</mesh>
              <mesh position={[0, oh / 2 - vb / 2, 0]}><boxGeometry args={[ow - 2 * vb, vb, frameDepth]} />{frameMaterial}</mesh>
              <mesh position={[0, -oh / 2 + vb / 2, 0]}><boxGeometry args={[ow - 2 * vb, vb, frameDepth]} />{frameMaterial}</mesh>
              {/* Mesh insect screen backing (very thin, recessed). */}
              <mesh position={[0, 0, -frameDepth * 0.35]}><boxGeometry args={[ow - 2 * vb, oh - 2 * vb, 0.004]} />{louvreMaterial}</mesh>
              {Array.from({ length: slats }).map((_, i) => {
                const spacing = (oh - 2 * border) / slats;
                const yPos = (oh / 2 - border) - spacing * (i + 0.5);
                return (
                  <mesh key={i} position={[0, yPos, 0]} rotation={[Math.PI / 6, 0, 0]}>
                    <boxGeometry args={[ow - 2 * border, 0.012, frameDepth * 0.7]} />
                    {louvreMaterial}
                  </mesh>
                );
              })}
            </group>
          );
        }

        // ---- Windows: framed glazing, layout driven by the kind -----------
        const style = kind.window ?? { panels: 2, orientation: 'horizontal' as const };
        const horizontal = style.orientation === 'horizontal';
        const panels = Math.max(1, style.panels);
        const innerW = ow - 2 * border;
        const innerH = oh - 2 * border;
        const gap = border * 0.6;
        const sillProud = frameDepth * 0.5 + 0.04; // window sill ledge depth (each face)

        return (
          <group key={opening.id} position={[ox, oy + oh / 2, 0]}>
            {/* Outer Frame (Jambs, Head, Sill) */}
            <mesh position={[-ow / 2 + border / 2, 0, 0]}><boxGeometry args={[border, oh, frameDepth]} />{frameMaterial}</mesh>
            <mesh position={[ow / 2 - border / 2, 0, 0]}><boxGeometry args={[border, oh, frameDepth]} />{frameMaterial}</mesh>
            <mesh position={[0, oh / 2 - border / 2, 0]}><boxGeometry args={[ow - 2 * border, border, frameDepth]} />{frameMaterial}</mesh>
            <mesh position={[0, -oh / 2 + border / 2, 0]}><boxGeometry args={[ow - 2 * border, border, frameDepth]} />{frameMaterial}</mesh>

            {/* Protruding sill ledge along the bottom (reads as a real window sill on both
                faces). Slightly wider than the opening and standing proud of the wall. */}
            <mesh position={[0, -oh / 2 + border * 0.25, 0]} castShadow>
              <boxGeometry args={[ow + 0.06, border * 0.7, frameDepth + 2 * sillProud]} />
              {frameMaterial}
            </mesh>

            {Array.from({ length: panels }).map((_, i) => {
              if (horizontal) {
                const paneW = (innerW - gap * (panels - 1)) / panels;
                const x = -innerW / 2 + paneW / 2 + i * (paneW + gap);
                return (
                  <group key={i}>
                    <mesh position={[x, 0, 0]} castShadow={false} receiveShadow={false}>
                      <boxGeometry args={[paneW, innerH, 0.02]} />{glassMaterial}
                    </mesh>
                    {i < panels - 1 && (
                      <mesh position={[x + paneW / 2 + gap / 2, 0, 0]}><boxGeometry args={[gap, innerH, frameDepth * 0.5]} />{frameMaterial}</mesh>
                    )}
                  </group>
                );
              }
              const paneH = (innerH - gap * (panels - 1)) / panels;
              const y = -innerH / 2 + paneH / 2 + i * (paneH + gap);
              return (
                <group key={i}>
                  <mesh position={[0, y, 0]} castShadow={false} receiveShadow={false}>
                    <boxGeometry args={[innerW, paneH, 0.02]} />{glassMaterial}
                  </mesh>
                  {i < panels - 1 && (
                    <mesh position={[0, y + paneH / 2 + gap / 2, 0]}><boxGeometry args={[innerW, gap, frameDepth * 0.5]} />{frameMaterial}</mesh>
                  )}
                </group>
              );
            })}
          </group>
        );
      })}
    </group>
  );
});

export const WallMesh: React.FC<WallMeshProps> = React.memo(
  ({ id, start, end, thickness, height, materialId, materialSideA, materialSideB, offsets, openings, roomPolys }) => {
    // A compact signature of the openings so the geometry rebuilds when any of them change.
    const openingsStr = openings
      .map((o) => `${o.id}-${o.offsetCm}-${o.width}-${o.height}-${o.elevation}-${o.kind ?? o.type}`)
      .join(',');

    const geometry = useMemo(
      () => createWallGeometry(start, end, thickness, height, offsets, openings),
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [start.x, start.y, end.x, end.y, thickness, height, offsets?.startLeft, offsets?.startRight, offsets?.endLeft, offsets?.endRight, id, openingsStr]
    );

    // Material array matches the geometry's groups: [edges/sides, −z face (B), +z face (A)].
    // Faces that haven't been painted individually fall back to the wall's base material.
    // We clone the cached materials so this wall can carry its own depth-offset slot (see
    // wallDepthOffsetSlot): that's what stops same-finish corners from z-fighting into the
    // "fan" artifacts on the low tier. Clones share the underlying textures, so the only cost
    // is a few extra lightweight material objects per wall.
    const materials = useMemo(() => {
      const units = wallDepthOffsetSlot(id);
      const clones: THREE.Material[] = [];
      const make = (mid: string): THREE.Material => {
        const m = getMaterial(mid).clone() as THREE.MeshStandardMaterial;
        m.polygonOffset = true;
        m.polygonOffsetFactor = 0;
        m.polygonOffsetUnits = units;
        clones.push(m);
        return m;
      };
      const base = make(materialId);
      const sideA = materialSideA ? make(materialSideA) : base;
      const sideB = materialSideB ? make(materialSideB) : base;
      return { array: [base, sideB, sideA] as THREE.Material[], clones };
    }, [materialId, materialSideA, materialSideB, id]);

    // Dispose the previous wall's cloned materials when they're replaced or the wall unmounts.
    useEffect(() => () => materials.clones.forEach((m) => m.dispose()), [materials]);

    return (
      <group>
        <mesh geometry={geometry} material={materials.array} castShadow receiveShadow />
        <OpeningFrames thickness={thickness} start={start} end={end} openings={openings} roomPolys={roomPolys} />
      </group>
    );
  }
);

WallMesh.displayName = 'WallMesh';
