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
const RED = '#ef4444';
function mat(kind: FurniturePartKind, c: boolean, colorOverride?: string) {
  const { texture, ...props } = furnitureMaterialProps(kind, colorOverride);
  return (
    <meshStandardMaterial
      color={c ? RED : props.color}
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

// --- Sofa (modern, upholstered with feet + back cushions) ------------------
const SofaPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => {
  const legH = 0.12;
  const armW = 0.16;
  const baseY = -h / 2 + legH;
  const bodyH = h - legH;
  const seatTop = baseY + bodyH * 0.42;
  const seats = w > 1.4 ? 3 : w > 1.0 ? 2 : 1;
  const innerW = w - armW * 2;
  return (
    <group>
      <Legs w={w} d={d} legH={legH} baseY={-h / 2} colliding={colliding} />
      {/* base block */}
      <mesh position={[0, baseY + bodyH * 0.25, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, bodyH * 0.5, d]} />
        {fabric(color, colliding)}
      </mesh>
      {/* arms */}
      <mesh position={[-w / 2 + armW / 2, baseY + bodyH * 0.42, 0]} castShadow>
        <boxGeometry args={[armW, bodyH * 0.84, d]} />
        {fabric(color, colliding)}
      </mesh>
      <mesh position={[w / 2 - armW / 2, baseY + bodyH * 0.42, 0]} castShadow>
        <boxGeometry args={[armW, bodyH * 0.84, d]} />
        {fabric(color, colliding)}
      </mesh>
      {/* backrest */}
      <mesh position={[0, baseY + bodyH * 0.6, -d / 2 + 0.1]} castShadow>
        <boxGeometry args={[innerW, bodyH * 1.0, 0.2]} />
        {fabric(color, colliding)}
      </mesh>
      {/* seat cushions */}
      {Array.from({ length: seats }).map((_, i) => {
        const cw = innerW / seats;
        const cx = -innerW / 2 + cw * (i + 0.5);
        return (
          <mesh key={`s${i}`} position={[cx, seatTop, 0.06]} castShadow receiveShadow>
            <boxGeometry args={[cw * 0.94, 0.16, d - 0.28]} />
            {fabric(color, colliding)}
          </mesh>
        );
      })}
      {/* back cushions */}
      {Array.from({ length: seats }).map((_, i) => {
        const cw = innerW / seats;
        const cx = -innerW / 2 + cw * (i + 0.5);
        return (
          <mesh key={`b${i}`} position={[cx, seatTop + 0.16, -d / 2 + 0.22]} castShadow>
            <boxGeometry args={[cw * 0.9, 0.26, 0.12]} />
            {fabric(color, colliding)}
          </mesh>
        );
      })}
    </group>
  );
};

// --- Armchair (single accent chair) ----------------------------------------
const ArmchairPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => {
  const legH = 0.14;
  const armW = 0.14;
  const baseY = -h / 2 + legH;
  const bodyH = h - legH;
  return (
    <group>
      <Legs w={w} d={d} legH={legH} baseY={-h / 2} colliding={colliding} />
      <mesh position={[0, baseY + bodyH * 0.22, 0.04]} castShadow receiveShadow>
        <boxGeometry args={[w - armW * 1.2, bodyH * 0.5, d - 0.1]} />
        {fabric(color, colliding)}
      </mesh>
      <mesh position={[-w / 2 + armW / 2, baseY + bodyH * 0.4, 0]} castShadow>
        <boxGeometry args={[armW, bodyH * 0.8, d]} />
        {fabric(color, colliding)}
      </mesh>
      <mesh position={[w / 2 - armW / 2, baseY + bodyH * 0.4, 0]} castShadow>
        <boxGeometry args={[armW, bodyH * 0.8, d]} />
        {fabric(color, colliding)}
      </mesh>
      <mesh position={[0, baseY + bodyH * 0.62, -d / 2 + 0.1]} castShadow>
        <boxGeometry args={[w - armW * 2, bodyH, 0.18]} />
        {fabric(color, colliding)}
      </mesh>
    </group>
  );
};

// --- Bed (low platform, upholstered headboard, duvet + pillows) ------------
const BedPrefab: React.FC<PrefabProps> = ({ w, h, d, color, colliding }) => {
  const frameH = h * 0.55;
  const mattressH = 0.2;
  const baseTop = -h / 2 + frameH;
  return (
    <group>
      {/* platform frame (slightly larger than mattress) */}
      <mesh position={[0, -h / 2 + frameH / 2, 0.05]} castShadow receiveShadow>
        <boxGeometry args={[w, frameH, d - 0.1]} />
        {darkWood(colliding)}
      </mesh>
      {/* upholstered headboard */}
      <mesh position={[0, -h / 2 + h * 0.55, -d / 2 + 0.05]} castShadow>
        <boxGeometry args={[w + 0.06, h * 1.1, 0.1]} />
        {fabric('#7c8a99', colliding)}
      </mesh>
      {/* mattress */}
      <mesh position={[0, baseTop + mattressH / 2, 0.08]} castShadow receiveShadow>
        <boxGeometry args={[w - 0.06, mattressH, d - 0.22]} />
        {white(colliding)}
      </mesh>
      {/* duvet (covers lower 2/3) */}
      <mesh position={[0, baseTop + mattressH + 0.03, 0.08 + (d - 0.22) * 0.18]} castShadow>
        <boxGeometry args={[w - 0.04, 0.1, (d - 0.22) * 0.66]} />
        {fabric(color, colliding)}
      </mesh>
      {/* pillows */}
      {(w > 1.2 ? [-w / 4, w / 4] : [0]).map((px) => (
        <mesh key={px} position={[px, baseTop + mattressH + 0.06, -d / 2 + 0.34]} castShadow>
          <boxGeometry args={[w > 1.2 ? w / 2.4 : w * 0.6, 0.12, 0.34]} />
          {white(colliding)}
        </mesh>
      ))}
    </group>
  );
};

// --- Dining table with chairs ----------------------------------------------
const DiningChair: React.FC<{ colliding: boolean }> = ({ colliding }) => {
  const seatH = 0.45, sw = 0.42, sd = 0.42;
  return (
    <group>
      <mesh position={[0, seatH, 0]} castShadow>
        <boxGeometry args={[sw, 0.06, sd]} />
        {lightWood(colliding)}
      </mesh>
      {/* backrest on -Z (chair faces +Z) */}
      <mesh position={[0, seatH + 0.22, -sd / 2 + 0.03]} castShadow>
        <boxGeometry args={[sw, 0.42, 0.05]} />
        {lightWood(colliding)}
      </mesh>
      {[-sw / 2 + 0.04, sw / 2 - 0.04].map((x) => [-sd / 2 + 0.04, sd / 2 - 0.04].map((z) => (
        <mesh key={`${x}:${z}`} position={[x, seatH / 2, z]} castShadow>
          <cylinderGeometry args={[0.02, 0.016, seatH, 8]} />
          {metal(colliding)}
        </mesh>
      )))}
    </group>
  );
};

const TablePrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => {
  const topH = 0.05;
  const legW = 0.07;
  const perSide = w > 1.3 ? 3 : 2;
  const gap = 0.28;
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

// --- Coffee table (glass top, wood frame) ----------------------------------
const CoffeeTablePrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => (
  <group>
    <mesh position={[0, h / 2 - 0.02, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, 0.03, d]} />
      {glass(colliding)}
    </mesh>
    <mesh position={[0, 0, 0]} castShadow>
      <boxGeometry args={[w * 0.5, h * 0.5, d * 0.5]} />
      {lightWood(colliding)}
    </mesh>
    <Legs w={w} d={d} legH={h - 0.03} baseY={-h / 2} colliding={colliding} r={0.025} />
  </group>
);

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

// --- Fridge (modern stainless, double door) --------------------------------
const FridgePrefab: React.FC<PrefabProps> = ({ w, h, d, colliding }) => (
  <group>
    <mesh position={[0, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      {metal(colliding)}
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

// --- Router ----------------------------------------------------------------
export const renderProceduralPrefab = (
  catalogId: string,
  w: number,
  h: number,
  d: number,
  color: string,
  colliding: boolean
) => {
  const props = { w, h, d, color, colliding };

  if (catalogId.includes('sofa')) return <SofaPrefab {...props} />;
  if (catalogId.includes('armchair')) return <ArmchairPrefab {...props} />;
  if (catalogId.includes('bed')) return <BedPrefab {...props} />;
  if (catalogId.includes('coffee')) return <CoffeeTablePrefab {...props} />;
  if (catalogId.includes('table')) return <TablePrefab {...props} />;
  if (catalogId.includes('office')) return <OfficeChairPrefab {...props} />;
  if (catalogId.includes('toilet')) return <ToiletPrefab {...props} />;
  if (catalogId.includes('kitchen')) return <KitchenCounterPrefab {...props} />;
  if (catalogId.includes('fridge')) return <FridgePrefab {...props} />;
  if (catalogId.includes('washer')) return <WasherPrefab {...props} />;
  if (catalogId.includes('shower')) return <ShowerPrefab {...props} />;
  if (catalogId.includes('vanity')) return <VanityPrefab {...props} />;
  if (catalogId.includes('night')) return <NightstandPrefab {...props} />;
  if (catalogId.includes('tv')) return <TVUnitPrefab {...props} />;
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
