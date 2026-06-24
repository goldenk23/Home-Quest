// src/domains/viewer/components/WallMesh.tsx

import React, { useMemo } from 'react';
import * as THREE from 'three';
import { useAppStore } from '@/store';
import { createWallGeometry } from '../services/extrusion';
import { useMaterial } from '../hooks/useMaterial';
import { furnitureMaterialProps, getFurnitureMaterial } from '../services/furnitureMaterials';
import { resolveKind } from '@/domains/shared/openings/openingCatalog';
import type { Point2D } from '@/types/geometry';
import type { MiterOffsets } from '@/domains/editor/services/wallOps';

interface WallMeshProps {
  id: string;
  start: Point2D;
  end: Point2D;
  thickness: number;
  height: number;
  materialId: string;
  offsets?: MiterOffsets;
}
import { useShallow } from 'zustand/react/shallow';

const CM_TO_M = 0.01;

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


const OpeningFrames: React.FC<{ wallId: string; thickness: number; start: Point2D; end: Point2D }> = React.memo(({ wallId, thickness, start, end }) => {
  const openings = useAppStore(useShallow(s => {
    const wall = s.walls[wallId];
    if (!wall || !wall.openingIds) return [];
    return wall.openingIds.map(oid => s.openings[oid]).filter(Boolean);
  }));

  if (openings.length === 0) return null;

  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const angle = Math.atan2(dy, dx);
  const sx = start.x * CM_TO_M;
  const sz = -start.y * CM_TO_M;
  const thickM = thickness * CM_TO_M;

  return (
    <group position={[sx, 0, sz]} rotation={[0, angle, 0]}>
      {openings.map(opening => {
        const kind = resolveKind(opening.kind, opening.type);

        const ox = opening.offsetCm * CM_TO_M;
        const oy = opening.elevation * CM_TO_M;
        const ow = opening.width * CM_TO_M;
        const oh = opening.height * CM_TO_M;

        const frameDepth = thickM * 0.8;
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
          if (kind.door !== 'gate') return null; // a plain doorway stays open

          // Main gate: a modern double-leaf villa gate (charcoal panels, lattice bands,
          // vertical fluting, raised centre panels, gold pull handles + keypad lock).
          return (
            <group key={opening.id} position={[ox, oy + oh / 2, 0]}>
              <MainGate ow={ow} oh={oh} frameDepth={frameDepth} />
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
          return (
            <group key={opening.id} position={[ox, oy + oh / 2, 0]}>
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

        return (
          <group key={opening.id} position={[ox, oy + oh / 2, 0]}>
            {/* Outer Frame (Jambs, Head, Sill) */}
            <mesh position={[-ow / 2 + border / 2, 0, 0]}><boxGeometry args={[border, oh, frameDepth]} />{frameMaterial}</mesh>
            <mesh position={[ow / 2 - border / 2, 0, 0]}><boxGeometry args={[border, oh, frameDepth]} />{frameMaterial}</mesh>
            <mesh position={[0, oh / 2 - border / 2, 0]}><boxGeometry args={[ow - 2 * border, border, frameDepth]} />{frameMaterial}</mesh>
            <mesh position={[0, -oh / 2 + border / 2, 0]}><boxGeometry args={[ow - 2 * border, border, frameDepth]} />{frameMaterial}</mesh>

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
  ({ id, start, end, thickness, height, materialId, offsets }) => {
    // We must subscribe to the openings of this specific wall so the mesh regenerates when an opening is added
    useAppStore(s => s.walls[id]?.openingIds);
    // Deep map the openings so we re-render if any opening dimensions change
    const openingsStr = useAppStore(s => {
       const wall = s.walls[id];
       if (!wall || !wall.openingIds) return '';
       return wall.openingIds.map(oid => {
          const o = s.openings[oid];
          return o ? `${o.id}-${o.offsetCm}-${o.width}-${o.height}-${o.elevation}-${o.kind ?? o.type}` : '';
       }).join(',');
    });

    const geometry = useMemo(
      () => createWallGeometry(start, end, thickness, height, offsets, id),
      [start.x, start.y, end.x, end.y, thickness, height, offsets?.startLeft, offsets?.startRight, offsets?.endLeft, offsets?.endRight, id, openingsStr]
    );
    const material = useMaterial(materialId);
    return (
      <group>
        <mesh geometry={geometry} material={material} castShadow receiveShadow />
        <OpeningFrames wallId={id} thickness={thickness} start={start} end={end} />
      </group>
    );
  }
);

WallMesh.displayName = 'WallMesh';
