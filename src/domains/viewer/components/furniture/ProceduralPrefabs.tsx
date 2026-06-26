// src/domains/viewer/components/furniture/ProceduralPrefabs.tsx
//
// Procedural, asset-free furniture. Each prefab is built from primitive meshes sized in
// METERS and centered on the origin (y spans -h/2 .. +h/2, so the parent group lifts it to
// sit on the floor). w = width (X), d = depth (Z), h = height (Y). The "front" of a piece
// faces +Z in its local space. Prefabs are intentionally low-poly but detailed enough to
// read as modern furniture (legs, cushions, frames, hardware) rather than plain boxes.

import React from 'react';
import {
  furnitureMaterialProps,
  type FurniturePartKind,
} from '../../services/furnitureMaterials';
import { getSharedProceduralTexture, getSharedProceduralBump, bumpScaleFor } from '../../services/materials';

interface PrefabProps {
  w: number;
  h: number;
  d: number;
  color: string;
  colliding: boolean;
}

// ---- shared materials (modern palette) ------------------------------------
// Each helper resolves tuned PBR params (roughness/metalness + env-map response, and a
// procedural texture where it helps) from furnitureMaterials, then forces the colour to red
// when the piece is colliding. The texture prop is dropped in collision mode so a red piece
// reads as a flat warning rather than a textured one.
//
// When a part kind carries a procedural texture (wood grain, marble veining), we attach the
// SHARED cached texture + bump map so the surface shows real grain and relief instead of a
// flat colour — and because the textures are shared singletons, referencing them here (in a
// render path) allocates nothing and never leaks a GPU texture.
const RED = '#ef4444';
function mat(kind: FurniturePartKind, c: boolean, colorOverride?: string) {
  const { texture, ...props } = furnitureMaterialProps(kind, colorOverride);
  // Colliding pieces render as a flat red warning — no texture/relief.
  const map = !c && texture ? getSharedProceduralTexture(texture.kind, texture.repeatMeters) : undefined;
  const bumpMap = !c && texture ? getSharedProceduralBump(texture.kind, texture.repeatMeters) : null;
  return (
    <meshStandardMaterial
      color={c ? RED : props.color}
      map={map}
      bumpMap={bumpMap ?? undefined}
      bumpScale={bumpMap && texture ? bumpScaleFor(texture.kind) : undefined}
      roughness={props.roughness}
      metalness={props.metalness}
      envMapIntensity={props.envMapIntensity}
      transparent={props.transparent}
      opacity={props.opacity}
    />
  );
}
const fabric = (color: string, c: boolean) => mat('fabric', c, color);
const lightWood = (c: boolean) => mat('lightWood', c);
const darkWood = (c: boolean) => mat('darkWood', c);
const white = (c: boolean) => mat('white', c);
const metal = (c: boolean) => mat('metal', c);
const matteBlack = (c: boolean) => mat('matteBlack', c);
const glass = (c: boolean) => mat('glass', c);
const quartz = (c: boolean) => mat('quartz', c);

/** Four slim tapered legs at the corners of a w×d footprint, of the given height. */
const Legs: React.FC<{ w: number; d: number; legH: number; baseY: number; colliding: boolean; inset?: number; r?: number }> = ({ w, d, legH, baseY, colliding, inset = 0.06, r = 0.022 }) => {
  const xs = [-w / 2 + inset, w / 2 - inset];
  const zs = [-d / 2 + inset, d / 2 - inset];
  return (
    <>
      {xs.map((x) => zs.map((z) => (
        <mesh key={`${x}:${z}`} position={[x, baseY + legH / 2, z]} castShadow>
          <cylinderGeometry args={[r, r * 0.8, legH, 10]} />
          {metal(colliding)}
        </mesh>
      )))}
    </>
  );
};

// --- Sofa (modern low-profile, plump cushions + accent throw pillows) ------
// Tuned to read like the light-grey lounge sofa in the reference: low matte-black
// feet, a deep upholstered base, softly rounded seat/back cushions, slim track arms
// and a pair of contrasting scatter cushions.
const SofaPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => {
  const legH = 0.1;
  const armW = 0.15;
  const baseY = -h / 2 + legH;
  const bodyH = h - legH;
  const seatTop = baseY + bodyH * 0.46;
  const seats = w > 1.4 ? 3 : w > 1.0 ? 2 : 1;
  const innerW = w - armW * 2;
  // A subtly darker tone for the scatter cushions so they pop against the body.
  const accent = colliding ? color : '#33414e';
  return (
    <group>
      {/* short matte-black feet (modern, not metal pins) */}
      {[[-w / 2 + 0.08, -d / 2 + 0.08], [w / 2 - 0.08, -d / 2 + 0.08], [-w / 2 + 0.08, d / 2 - 0.08], [w / 2 - 0.08, d / 2 - 0.08]].map(([x, z], i) => (
        <mesh key={i} position={[x, -h / 2 + legH / 2, z]} castShadow>
          <boxGeometry args={[0.05, legH, 0.05]} />
          {matteBlack(colliding)}
        </mesh>
      ))}
      {/* deep base block */}
      <mesh position={[0, baseY + bodyH * 0.24, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, bodyH * 0.48, d]} />
        {fabric(color, colliding)}
      </mesh>
      {/* slim track arms */}
      <mesh position={[-w / 2 + armW / 2, baseY + bodyH * 0.44, 0]} castShadow>
        <boxGeometry args={[armW, bodyH * 0.8, d]} />
        {fabric(color, colliding)}
      </mesh>
      <mesh position={[w / 2 - armW / 2, baseY + bodyH * 0.44, 0]} castShadow>
        <boxGeometry args={[armW, bodyH * 0.8, d]} />
        {fabric(color, colliding)}
      </mesh>
      {/* low backrest */}
      <mesh position={[0, baseY + bodyH * 0.58, -d / 2 + 0.1]} castShadow>
        <boxGeometry args={[innerW, bodyH * 0.92, 0.2]} />
        {fabric(color, colliding)}
      </mesh>
      {/* plump seat cushions (rounded edges) */}
      {Array.from({ length: seats }).map((_, i) => {
        const cw = innerW / seats;
        const cx = -innerW / 2 + cw * (i + 0.5);
        return (
          <mesh key={`s${i}`} position={[cx, seatTop, 0.07]} castShadow receiveShadow>
            <boxGeometry args={[cw * 0.95, 0.2, d - 0.26]} />
            {fabric(color, colliding)}
          </mesh>
        );
      })}
      {/* soft back cushions */}
      {Array.from({ length: seats }).map((_, i) => {
        const cw = innerW / seats;
        const cx = -innerW / 2 + cw * (i + 0.5);
        return (
          <mesh key={`b${i}`} position={[cx, seatTop + 0.2, -d / 2 + 0.24]} castShadow>
            <boxGeometry args={[cw * 0.92, 0.3, 0.14]} />
            {fabric(color, colliding)}
          </mesh>
        );
      })}
      {/* two accent scatter cushions toward the ends */}
      {(seats > 1 ? [-innerW / 2 + 0.22, innerW / 2 - 0.22] : [0]).map((px, i) => (
        <mesh key={`p${i}`} position={[px, seatTop + 0.22, 0.02]} rotation={[0, 0, Math.PI / 14]} castShadow>
          <boxGeometry args={[0.34, 0.34, 0.1]} />
          {fabric(accent, colliding)}
        </mesh>
      ))}
    </group>
  );
};

// --- Armchair (white barrel / tub accent chair) ----------------------------
// The reference uses rounded white tub chairs, so this is built from a curved
// half-cylinder shell (back + wrap-around arms) with a round seat cushion on
// splayed legs rather than a boxy frame.
const ArmchairPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => {
  const legH = 0.13;
  const baseY = -h / 2 + legH;
  const bodyH = h - legH;
  const r = Math.min(w, d) / 2;
  const seatY = baseY + bodyH * 0.36;
  return (
    <group>
      {/* curved tub shell — open toward +Z (the front) */}
      <mesh position={[0, baseY + bodyH * 0.5, -0.02]} castShadow receiveShadow>
        <cylinderGeometry args={[r, r * 0.92, bodyH, 24, 1, true, Math.PI * 0.18, Math.PI * 1.64]} />
        {fabric(color, colliding)}
      </mesh>
      {/* solid lower drum so it doesn't look hollow from the seat down */}
      <mesh position={[0, baseY + bodyH * 0.22, -0.02]} castShadow>
        <cylinderGeometry args={[r * 0.96, r * 0.88, bodyH * 0.44, 24]} />
        {fabric(color, colliding)}
      </mesh>
      {/* round seat cushion */}
      <mesh position={[0, seatY, 0.02]} castShadow receiveShadow>
        <cylinderGeometry args={[r * 0.82, r * 0.82, 0.14, 24]} />
        {fabric(color, colliding)}
      </mesh>
      {/* four splayed wooden legs */}
      {[0.25, 0.75, 1.25, 1.75].map((f) => {
        const a = Math.PI * f;
        return (
          <mesh key={f} position={[Math.cos(a) * r * 0.7, -h / 2 + legH / 2, Math.sin(a) * r * 0.7]} rotation={[0, 0, 0]} castShadow>
            <cylinderGeometry args={[0.018, 0.012, legH, 8]} />
            {lightWood(colliding)}
          </mesh>
        );
      })}
    </group>
  );
};

// --- Bed (platform, tall charcoal upholstered headboard, white bedding) ----
// Matches the reference master bed: a dark padded headboard, a low platform,
// a clean white duvet with two stacked pillows and a folded accent runner at
// the foot.
const BedPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => {
  const frameH = h * 0.5;
  const mattressH = 0.22;
  const baseTop = -h / 2 + frameH;
  const charcoal = colliding ? color : '#2f3640';
  const runner = colliding ? color : '#8a98a8';
  return (
    <group>
      {/* platform frame */}
      <mesh position={[0, -h / 2 + frameH / 2, 0.05]} castShadow receiveShadow>
        <boxGeometry args={[w, frameH, d - 0.1]} />
        {matteBlack(colliding)}
      </mesh>
      {/* tall padded headboard with quilted panels */}
      <mesh position={[0, -h / 2 + h * 0.7, -d / 2 + 0.04]} castShadow>
        <boxGeometry args={[w + 0.08, h * 1.4, 0.12]} />
        {fabric(charcoal, colliding)}
      </mesh>
      {[-w / 3, 0, w / 3].map((px) => (
        <mesh key={px} position={[px, -h / 2 + h * 0.8, -d / 2 + 0.11]} castShadow>
          <boxGeometry args={[w * 0.28, h * 0.9, 0.03]} />
          {fabric(charcoal, colliding)}
        </mesh>
      ))}
      {/* mattress */}
      <mesh position={[0, baseTop + mattressH / 2, 0.08]} castShadow receiveShadow>
        <boxGeometry args={[w - 0.06, mattressH, d - 0.22]} />
        {white(colliding)}
      </mesh>
      {/* white duvet covering the lower portion */}
      <mesh position={[0, baseTop + mattressH + 0.04, 0.08 + (d - 0.22) * 0.16]} castShadow>
        <boxGeometry args={[w - 0.03, 0.12, (d - 0.22) * 0.7]} />
        {white(colliding)}
      </mesh>
      {/* folded accent runner near the foot */}
      <mesh position={[0, baseTop + mattressH + 0.1, 0.08 + (d - 0.22) * 0.42]} castShadow>
        <boxGeometry args={[w - 0.03, 0.06, (d - 0.22) * 0.18]} />
        {fabric(runner, colliding)}
      </mesh>
      {/* two stacked pillows */}
      {(w > 1.2 ? [-w / 4, w / 4] : [0]).map((px) => (
        <group key={px}>
          <mesh position={[px, baseTop + mattressH + 0.07, -d / 2 + 0.36]} rotation={[-0.18, 0, 0]} castShadow>
            <boxGeometry args={[w > 1.2 ? w / 2.5 : w * 0.6, 0.12, 0.32]} />
            {white(colliding)}
          </mesh>
          <mesh position={[px, baseTop + mattressH + 0.13, -d / 2 + 0.5]} castShadow>
            <boxGeometry args={[w > 1.2 ? w / 2.8 : w * 0.5, 0.1, 0.24]} />
            {white(colliding)}
          </mesh>
        </group>
      ))}
    </group>
  );
};

// --- Dining table with chairs ----------------------------------------------
// A modern upholstered dining chair: solid seat pad, gently reclined padded
// back and four slim tapered legs.
const DiningChair: React.FC<{ colliding: boolean; seatColor?: string }> = ({ colliding, seatColor }) => {
  const seatH = 0.46, sw = 0.44, sd = 0.44;
  const pad = colliding ? '#ef4444' : (seatColor ?? '#41566a');
  return (
    <group>
      {/* upholstered seat pad */}
      <mesh position={[0, seatH, 0]} castShadow>
        <boxGeometry args={[sw, 0.08, sd]} />
        {fabric(pad, colliding)}
      </mesh>
      {/* reclined padded back (chair faces +Z) */}
      <mesh position={[0, seatH + 0.26, -sd / 2 + 0.04]} rotation={[0.12, 0, 0]} castShadow>
        <boxGeometry args={[sw * 0.92, 0.46, 0.07]} />
        {fabric(pad, colliding)}
      </mesh>
      {[-sw / 2 + 0.04, sw / 2 - 0.04].map((x) => [-sd / 2 + 0.04, sd / 2 - 0.04].map((z) => (
        <mesh key={`${x}:${z}`} position={[x, seatH / 2, z]} castShadow>
          <cylinderGeometry args={[0.02, 0.014, seatH, 8]} />
          {darkWood(colliding)}
        </mesh>
      )))}
    </group>
  );
};

/** A small decorative centerpiece (vase + foliage) for dining tables. */
const Centerpiece: React.FC<{ topY: number; colliding: boolean }> = ({ topY, colliding }) => (
  <group>
    <mesh position={[0, topY + 0.09, 0]} castShadow>
      <cylinderGeometry args={[0.05, 0.07, 0.18, 14]} />
      {white(colliding)}
    </mesh>
    <mesh position={[0, topY + 0.24, 0]} castShadow>
      <sphereGeometry args={[0.11, 12, 12]} />
      {mat('foliage', colliding)}
    </mesh>
  </group>
);

const TablePrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const topH = 0.05;
  const legW = 0.07;
  const perSide = w > 1.3 ? 3 : 2;
  const gap = 0.3;
  return (
    <group>
      {/* top */}
      <mesh position={[0, h / 2 - topH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, topH, d]} />
        {lightWood(colliding)}
      </mesh>
      {[-w / 2 + legW, w / 2 - legW].map((x) => [-d / 2 + legW, d / 2 - legW].map((z) => (
        <mesh key={`${x}:${z}`} position={[x, 0, z]} castShadow>
          <boxGeometry args={[legW, h - topH, legW]} />
          {darkWood(colliding)}
        </mesh>
      )))}
      <Centerpiece topY={h / 2} colliding={colliding} />
      {/* chairs along both long sides, sitting on the floor (group is lifted by h/2) */}
      {Array.from({ length: perSide }).map((_, i) => {
        const cx = -w / 2 + (w / perSide) * (i + 0.5);
        return (
          <group key={`row${i}`}>
            <group position={[cx, -h / 2, -d / 2 - gap]}>
              <DiningChair colliding={colliding} />
            </group>
            <group position={[cx, -h / 2, d / 2 + gap]} rotation={[0, Math.PI, 0]}>
              <DiningChair colliding={colliding} />
            </group>
          </group>
        );
      })}
    </group>
  );
};

// --- Round dining set (pedestal table + radial chairs + centerpiece) -------
const RoundDiningPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const r = Math.min(w, d) / 2;
  const topH = 0.05;
  const chairs = 4;
  const ring = r + 0.34;
  return (
    <group>
      {/* round top */}
      <mesh position={[0, h / 2 - topH / 2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[r, r, topH, 36]} />
        {lightWood(colliding)}
      </mesh>
      {/* central pedestal + foot */}
      <mesh position={[0, 0, 0]} castShadow>
        <cylinderGeometry args={[0.07, 0.09, h - topH, 16]} />
        {darkWood(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + 0.03, 0]} castShadow>
        <cylinderGeometry args={[r * 0.42, r * 0.42, 0.05, 24]} />
        {darkWood(colliding)}
      </mesh>
      <Centerpiece topY={h / 2} colliding={colliding} />
      {/* chairs arranged radially, each facing the table centre */}
      {Array.from({ length: chairs }).map((_, i) => {
        const a = (i / chairs) * Math.PI * 2;
        const cx = Math.sin(a) * ring;
        const cz = Math.cos(a) * ring;
        return (
          <group key={i} position={[cx, -h / 2, cz]} rotation={[0, a + Math.PI, 0]}>
            <DiningChair colliding={colliding} />
          </group>
        );
      })}
    </group>
  );
};

// --- Bar stool (wooden seat, slim metal frame + footrest) ------------------
// The kitchen island in the reference is lined with tall wooden stools.
const BarStoolPrefab: React.FC<PrefabProps> = ({ w, h, colliding }) => {
  const r = w * 0.42;
  return (
    <group>
      {/* round wooden seat */}
      <mesh position={[0, h / 2 - 0.04, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[r, r, 0.06, 20]} />
        {lightWood(colliding)}
      </mesh>
      {/* low back loop */}
      <mesh position={[0, h / 2 + 0.1, -r + 0.02]} castShadow>
        <boxGeometry args={[r * 1.4, 0.22, 0.03]} />
        {lightWood(colliding)}
      </mesh>
      {/* four splayed legs + footrest ring */}
      {[0.25, 0.75, 1.25, 1.75].map((f) => {
        const a = Math.PI * f;
        return (
          <mesh key={f} position={[Math.cos(a) * r * 0.7, 0, Math.sin(a) * r * 0.7]} castShadow>
            <cylinderGeometry args={[0.014, 0.018, h - 0.08, 8]} />
            {metal(colliding)}
          </mesh>
        );
      })}
      <mesh position={[0, -h / 2 + h * 0.32, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <torusGeometry args={[r * 0.7, 0.012, 8, 20]} />
        {metal(colliding)}
      </mesh>
    </group>
  );
};

// --- Sun lounger (teak-slat poolside chaise with a tilted backrest) --------
const SunLoungerPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const frameH = h * 0.42;
  const seatY = -h / 2 + frameH;
  const slatGap = d / 8;
  return (
    <group>
      {/* slatted seat deck */}
      {Array.from({ length: 7 }).map((_, i) => (
        <mesh key={i} position={[0, seatY, -d / 2 + slatGap * (i + 1)]} castShadow receiveShadow>
          <boxGeometry args={[w * 0.92, 0.035, slatGap * 0.6]} />
          {lightWood(colliding)}
        </mesh>
      ))}
      {/* tilted backrest at the head (-Z) */}
      <group position={[0, seatY, -d / 2 + slatGap * 0.6]} rotation={[-Math.PI / 4, 0, 0]}>
        {Array.from({ length: 4 }).map((_, i) => (
          <mesh key={i} position={[0, slatGap * (i + 0.5), 0]} castShadow>
            <boxGeometry args={[w * 0.92, 0.035, slatGap * 0.6]} />
            {lightWood(colliding)}
          </mesh>
        ))}
      </group>
      {/* side rails + legs */}
      {[-w / 2 + 0.05, w / 2 - 0.05].map((x) => (
        <group key={x}>
          <mesh position={[x, seatY - 0.04, 0]} castShadow>
            <boxGeometry args={[0.05, 0.05, d]} />
            {darkWood(colliding)}
          </mesh>
          {[-d / 2 + 0.12, d / 2 - 0.12].map((z) => (
            <mesh key={z} position={[x, -h / 2 + frameH / 2 - 0.04, z]} castShadow>
              <boxGeometry args={[0.05, frameH, 0.05]} />
              {darkWood(colliding)}
            </mesh>
          ))}
        </group>
      ))}
    </group>
  );
};

// --- Coffee table (rounded warm-wood top + lower shelf) --------------------
const CoffeeTablePrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const r = Math.min(w, d) / 2;
  const topH = 0.05;
  return (
    <group>
      {/* round wooden top */}
      <mesh position={[0, h / 2 - topH / 2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[r, r, topH, 32]} />
        {lightWood(colliding)}
      </mesh>
      {/* lower shelf */}
      <mesh position={[0, -h / 2 + 0.12, 0]} castShadow>
        <cylinderGeometry args={[r * 0.82, r * 0.82, 0.03, 32]} />
        {darkWood(colliding)}
      </mesh>
      {/* a small stack of books as styling */}
      <mesh position={[r * 0.2, h / 2 + 0.03, 0]} rotation={[0, 0.4, 0]} castShadow>
        <boxGeometry args={[0.22, 0.04, 0.16]} />
        {matteBlack(colliding)}
      </mesh>
      <Legs w={w * 0.9} d={d * 0.9} legH={h - topH} baseY={-h / 2} colliding={colliding} r={0.022} />
    </group>
  );
};

// --- Office chair ----------------------------------------------------------
const OfficeChairPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => {
  const seatY = -h / 2 + h * 0.42;
  return (
    <group>
      <mesh position={[0, -h / 2 + 0.03, 0]} castShadow>
        <cylinderGeometry args={[w * 0.55, w * 0.55, 0.05, 5]} />
        {matteBlack(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + (h * 0.42) / 2, 0]} castShadow>
        <cylinderGeometry args={[0.03, 0.03, h * 0.42, 10]} />
        {metal(colliding)}
      </mesh>
      <mesh position={[0, seatY, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, 0.1, d]} />
        {fabric(color, colliding)}
      </mesh>
      <mesh position={[0, seatY + h * 0.28, -d / 2 + 0.06]} castShadow>
        <boxGeometry args={[w * 0.9, h * 0.5, 0.07]} />
        {fabric(color, colliding)}
      </mesh>
    </group>
  );
};

// --- Toilet ----------------------------------------------------------------
const ToiletPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const tankH = h * 0.55;
  return (
    <group>
      <mesh position={[0, h / 2 - tankH / 2, -d / 2 + 0.09]} castShadow>
        <boxGeometry args={[w, tankH, 0.16]} />
        {white(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + h * 0.22, 0.06]} castShadow receiveShadow>
        <cylinderGeometry args={[w / 2, w / 2.6, h * 0.44, 18]} />
        {white(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + h * 0.45, 0.06]} castShadow>
        <cylinderGeometry args={[w / 1.8, w / 2, 0.04, 18]} />
        {white(colliding)}
      </mesh>
    </group>
  );
};

// --- Kitchen counter (cabinets + quartz top with sink + cooktop) -----------
const KitchenCounterPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => {
  const topH = 0.05;
  return (
    <group>
      <mesh position={[0, -topH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, h - topH, d]} />
        {fabric(color, colliding)}
      </mesh>
      {/* quartz worktop */}
      <mesh position={[0, h / 2 - topH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w + 0.04, topH, d + 0.04]} />
        {quartz(colliding)}
      </mesh>
      {/* sink basin */}
      <mesh position={[-w * 0.26, h / 2, 0]} castShadow>
        <boxGeometry args={[w * 0.28, 0.04, d * 0.6]} />
        {metal(colliding)}
      </mesh>
      {/* faucet */}
      <mesh position={[-w * 0.26, h / 2 + 0.12, -d * 0.22]} castShadow>
        <cylinderGeometry args={[0.015, 0.015, 0.24, 8]} />
        {metal(colliding)}
      </mesh>
      {/* cooktop burners */}
      {[-0.09, 0.09].map((bx) => [-0.09, 0.09].map((bz) => (
        <mesh key={`${bx}:${bz}`} position={[w * 0.26 + bx, h / 2 + 0.005, bz]} castShadow>
          <cylinderGeometry args={[0.06, 0.06, 0.012, 16]} />
          {matteBlack(colliding)}
        </mesh>
      )))}
      {/* cabinet handles */}
      {[-w * 0.3, 0, w * 0.3].map((hx) => (
        <mesh key={hx} position={[hx, 0.05, d / 2 + 0.01]} castShadow>
          <boxGeometry args={[0.012, 0.012, 0.02]} />
          {metal(colliding)}
        </mesh>
      ))}
    </group>
  );
};

// --- Storage (wardrobe / bookshelf / sideboard) ----------------------------
const StoragePrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => (
  <group>
    <mesh position={[0, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      {darkWood(colliding)}
    </mesh>
    {/* door split + handles */}
    <mesh position={[0, 0, d / 2 + 0.005]}>
      <boxGeometry args={[0.015, h - 0.08, 0.01]} />
      {matteBlack(colliding)}
    </mesh>
    {[-w / 4, w / 4].map((hx) => (
      <mesh key={hx} position={[hx + (hx < 0 ? 0.06 : -0.06), 0, d / 2 + 0.02]} castShadow>
        <cylinderGeometry args={[0.012, 0.012, 0.18, 8]} />
        {metal(colliding)}
      </mesh>
    ))}
  </group>
);

// --- Nightstand ------------------------------------------------------------
const NightstandPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => (
  <group>
    <Legs w={w} d={d} legH={0.12} baseY={-h / 2} colliding={colliding} r={0.018} />
    <mesh position={[0, 0.06, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, h - 0.12, d]} />
      {lightWood(colliding)}
    </mesh>
    <mesh position={[0, 0.06, d / 2 + 0.01]} castShadow>
      <cylinderGeometry args={[0.014, 0.014, 0.06, 8]} />
      {metal(colliding)}
    </mesh>
  </group>
);

// --- TV unit (slim console + wall-style flat screen) -----------------------
const TVUnitPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const consoleH = 0.32;
  const tvW = w * 0.92;
  const tvH = h * 0.5;
  return (
    <group>
      <mesh position={[0, -h / 2 + consoleH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, consoleH, d]} />
        {darkWood(colliding)}
      </mesh>
      {/* floating shelf line */}
      <mesh position={[0, -h / 2 + consoleH * 0.6, d / 2 + 0.005]}>
        <boxGeometry args={[w * 0.96, 0.012, 0.01]} />
        {metal(colliding)}
      </mesh>
      {/* screen */}
      <mesh position={[0, h / 2 - tvH / 2, -d * 0.2]} castShadow>
        <boxGeometry args={[tvW, tvH, 0.04]} />
        {matteBlack(colliding)}
      </mesh>
    </group>
  );
};

// --- Fridge (modern white, double door) ------------------------------------
const FridgePrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => (
  <group>
    <mesh position={[0, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      {white(colliding)}
    </mesh>
    <mesh position={[0, h * 0.12, d / 2 + 0.004]}>
      <boxGeometry args={[w - 0.02, 0.015, 0.008]} />
      {matteBlack(colliding)}
    </mesh>
    {[-w / 2 + 0.07, w / 2 - 0.07].map((hx) => (
      <mesh key={hx} position={[hx, h * 0.3, d / 2 + 0.02]} castShadow>
        <boxGeometry args={[0.025, h * 0.4, 0.03]} />
        {matteBlack(colliding)}
      </mesh>
    ))}
  </group>
);

// --- Washing machine -------------------------------------------------------
const WasherPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => (
  <group>
    <mesh position={[0, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      {white(colliding)}
    </mesh>
    <mesh position={[0, h * 0.05, d / 2 - 0.005]} rotation={[Math.PI / 2, 0, 0]} castShadow>
      <cylinderGeometry args={[w * 0.3, w * 0.3, 0.06, 24]} />
      {matteBlack(colliding)}
    </mesh>
    <mesh position={[0, h * 0.05, d / 2 + 0.01]} rotation={[Math.PI / 2, 0, 0]}>
      <cylinderGeometry args={[w * 0.22, w * 0.22, 0.04, 24]} />
      {glass(colliding)}
    </mesh>
    <mesh position={[-w / 2 + 0.08, h / 2 - 0.05, d / 2 + 0.005]}>
      <boxGeometry args={[w * 0.5, 0.05, 0.01]} />
      {metal(colliding)}
    </mesh>
  </group>
);

// --- Shower enclosure (glass + tray + head) --------------------------------
const ShowerPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => (
  <group>
    <mesh position={[0, -h / 2 + 0.04, 0]} receiveShadow>
      <boxGeometry args={[w, 0.08, d]} />
      {white(colliding)}
    </mesh>
    {/* two glass panels (L) */}
    <mesh position={[0, 0.04, d / 2 - 0.01]} castShadow>
      <boxGeometry args={[w, h - 0.08, 0.02]} />
      {glass(colliding)}
    </mesh>
    <mesh position={[w / 2 - 0.01, 0.04, 0]} castShadow>
      <boxGeometry args={[0.02, h - 0.08, d]} />
      {glass(colliding)}
    </mesh>
    {/* shower head */}
    <mesh position={[-w / 2 + 0.12, h / 2 - 0.12, -d / 2 + 0.08]} castShadow>
      <cylinderGeometry args={[0.06, 0.06, 0.03, 16]} />
      {metal(colliding)}
    </mesh>
  </group>
);

// --- Vanity (bathroom sink cabinet + mirror) -------------------------------
const VanityPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const cabH = h * 0.7;
  return (
    <group>
      <mesh position={[0, -h / 2 + cabH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, cabH, d]} />
        {darkWood(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + cabH, 0]} castShadow>
        <boxGeometry args={[w + 0.03, 0.05, d + 0.03]} />
        {quartz(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + cabH + 0.04, 0.04]} castShadow>
        <boxGeometry args={[w * 0.5, 0.04, d * 0.55]} />
        {white(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + cabH + 0.16, -d / 2 + 0.04]} castShadow>
        <cylinderGeometry args={[0.014, 0.014, 0.2, 8]} />
        {metal(colliding)}
      </mesh>
      {/* mirror */}
      <mesh position={[0, h / 2 - 0.12, -d / 2 + 0.02]}>
        <boxGeometry args={[w * 0.7, h * 0.4, 0.02]} />
        {glass(colliding)}
      </mesh>
    </group>
  );
};

// --- Plant (modern pot + foliage) ------------------------------------------
const PlantPrefab: React.FC<PrefabProps> = ({ w, h, color, colliding }) => {
  const potH = h * 0.32;
  return (
    <group>
      <mesh position={[0, -h / 2 + potH / 2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[w * 0.34, w * 0.26, potH, 18]} />
        {white(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + potH + 0.02, 0]} castShadow>
        <sphereGeometry args={[w * 0.45, 16, 16]} />
        {fabric(color, colliding)}
      </mesh>
      <mesh position={[-w * 0.22, -h / 2 + potH + 0.22, 0.04]} castShadow>
        <sphereGeometry args={[w * 0.36, 16, 16]} />
        {fabric(color, colliding)}
      </mesh>
      <mesh position={[w * 0.2, -h / 2 + potH + 0.16, -w * 0.06]} castShadow>
        <sphereGeometry args={[w * 0.34, 16, 16]} />
        {fabric(color, colliding)}
      </mesh>
    </group>
  );
};

// --- Rug -------------------------------------------------------------------
const RugPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => (
  <mesh position={[0, -h / 2 + 0.005, 0]} receiveShadow>
    <boxGeometry args={[w, 0.01, d]} />
    {fabric(color, colliding)}
  </mesh>
);

// --- Air Conditioner (white split-unit, wall-style) ------------------------
const ACPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => (
  <group>
    {/* Main body */}
    <mesh position={[0, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      {white(colliding)}
    </mesh>
    {/* Rounded front fascia, very slightly proud of the body */}
    <mesh position={[0, h * 0.08, d / 2 + 0.003]}>
      <boxGeometry args={[w * 0.98, h * 0.66, 0.012]} />
      {white(colliding)}
    </mesh>
    {/* Angled bottom air-outlet louvre (dark recessed slot) */}
    <mesh position={[0, -h / 2 + h * 0.16, d / 2 - 0.012]} rotation={[Math.PI / 7, 0, 0]}>
      <boxGeometry args={[w * 0.9, 0.02, d * 0.55]} />
      {matteBlack(colliding)}
    </mesh>
    {/* Status LED strip on the lower-right */}
    <mesh position={[w * 0.3, -h / 2 + h * 0.34, d / 2 + 0.008]}>
      <boxGeometry args={[w * 0.16, 0.008, 0.005]} />
      {matteBlack(colliding)}
    </mesh>
  </group>
);

// --- Bathtub (freestanding oval soaking tub) -------------------------------
// The reference bathrooms feature a freestanding oval tub. Built as an outer
// shell with a recessed inner basin and a slim wall-mounted filler.
const BathtubPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const rx = w / 2;
  const rz = d / 2;
  return (
    <group>
      {/* outer shell — a squashed cylinder reads as an oval tub */}
      <mesh position={[0, -h / 2 + h * 0.45, 0]} scale={[1, 1, rz / rx]} castShadow receiveShadow>
        <cylinderGeometry args={[rx, rx * 0.86, h * 0.9, 36]} />
        {white(colliding)}
      </mesh>
      {/* rolled rim */}
      <mesh position={[0, -h / 2 + h * 0.9, 0]} scale={[1, 1, rz / rx]} castShadow>
        <torusGeometry args={[rx * 0.92, 0.04, 12, 36]} />
        {white(colliding)}
      </mesh>
      {/* recessed water/basin */}
      <mesh position={[0, -h / 2 + h * 0.86, 0]} scale={[1, 1, rz / rx]}>
        <cylinderGeometry args={[rx * 0.82, rx * 0.72, 0.04, 32]} />
        {glass(colliding)}
      </mesh>
      {/* slim floor filler tap at one end */}
      <mesh position={[0, -h / 2 + h * 0.55, -d / 2 + 0.06]} castShadow>
        <cylinderGeometry args={[0.02, 0.02, h * 1.1, 10]} />
        {metal(colliding)}
      </mesh>
      <mesh position={[0, -h / 2 + h * 1.05, -d / 2 + 0.12]} rotation={[Math.PI / 2.4, 0, 0]} castShadow>
        <cylinderGeometry args={[0.018, 0.018, 0.14, 10]} />
        {metal(colliding)}
      </mesh>
    </group>
  );
};

// --- Router ----------------------------------------------------------------
// --- Stairs (straight flight, solid stepped profile) -----------------------
// A straight staircase that climbs one storey. Steps ascend along +Z (the piece's "front"),
// so the bottom step is at -Z and the top tread lands at +h/2 (= the floor above's base, since
// the catalog height is one storey). The first-person walkthrough reads this same convention
// to ride the player up (see useFirstPerson groundHeightAtM).
// ponytail: bare treads, no railings/stringers — enough to walk and read as stairs. There is
// also no stairwell hole cut in the ceiling slab above, so climbing clips through that 20cm
// slab briefly; cutting the slab is the upgrade if it matters.
const StairsPrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const n = Math.max(3, Math.round(h / 0.18)); // ~18cm risers
  const rise = h / n;
  const run = d / n;
  return (
    <group>
      {Array.from({ length: n }).map((_, i) => {
        const boxH = (i + 1) * rise;            // solid from floor up to this tread
        const cy = -h / 2 + boxH / 2;
        const cz = -d / 2 + (i + 0.5) * run;    // bottom step at -Z, ascending toward +Z
        return (
          <mesh key={i} position={[0, cy, cz]} castShadow receiveShadow>
            <boxGeometry args={[w, boxH, run]} />
            {lightWood(colliding)}
          </mesh>
        );
      })}
    </group>
  );
};

export const renderProceduralPrefab = (
  catalogId: string,
  w: number,
  h: number,
  d: number,
  color: string,
  colliding: boolean
) => {
  const props = { w, h, d, color, colliding };

  if (catalogId.includes('stair')) return <StairsPrefab {...props} />;
  if (catalogId.includes('sofa')) return <SofaPrefab {...props} />;
  if (catalogId.includes('armchair')) return <ArmchairPrefab {...props} />;
  if (catalogId.startsWith('ac')) return <ACPrefab {...props} />;
  if (catalogId.includes('bed')) return <BedPrefab {...props} />;
  if (catalogId.includes('coffee')) return <CoffeeTablePrefab {...props} />;
  if (catalogId.includes('bar') || catalogId.includes('stool')) return <BarStoolPrefab {...props} />;
  if (catalogId.includes('round')) return <RoundDiningPrefab {...props} />;
  if (catalogId.includes('table')) return <TablePrefab {...props} />;
  if (catalogId.includes('office')) return <OfficeChairPrefab {...props} />;
  if (catalogId.includes('bathtub') || catalogId.includes('tub')) return <BathtubPrefab {...props} />;
  if (catalogId.includes('toilet')) return <ToiletPrefab {...props} />;
  if (catalogId.includes('kitchen')) return <KitchenCounterPrefab {...props} />;
  if (catalogId.includes('fridge')) return <FridgePrefab {...props} />;
  if (catalogId.includes('washer')) return <WasherPrefab {...props} />;
  if (catalogId.includes('shower')) return <ShowerPrefab {...props} />;
  if (catalogId.includes('vanity')) return <VanityPrefab {...props} />;
  if (catalogId.includes('night')) return <NightstandPrefab {...props} />;
  if (catalogId.includes('tv')) return <TVUnitPrefab {...props} />;
  if (catalogId.includes('lounger') || catalogId.includes('sun')) return <SunLoungerPrefab {...props} />;
  if (catalogId.includes('wardrobe') || catalogId.includes('bookshelf') || catalogId.includes('side')) return <StoragePrefab {...props} />;
  if (catalogId.includes('plant')) return <PlantPrefab {...props} />;
  if (catalogId.includes('rug')) return <RugPrefab {...props} />;

  return (
    <mesh position={[0, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      {fabric(color, colliding)}
    </mesh>
  );
};
