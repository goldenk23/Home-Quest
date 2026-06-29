// src/domains/viewer/components/StairMesh.tsx
//
// 3D renderer for a StairEntity. Geometry is computed directly in world space
// so there is no confusion between plan coordinates and 3D orientation.

import React from 'react';
import * as THREE from 'three';
import type { StairEntity, StairFlight, StairLanding } from '@/types/stair';

const CM = 0.01; // cm → m

// Shared materials (module-level so they're created once and reused).
const lightWoodMat = new THREE.MeshStandardMaterial({ color: '#d4a574', roughness: 0.7, metalness: 0 });
const whiteMat = new THREE.MeshStandardMaterial({ color: '#f8fafc', roughness: 0.6, metalness: 0 });
const darkWoodMat = new THREE.MeshStandardMaterial({ color: '#6f5135', roughness: 0.65, metalness: 0 });
const metalMat = new THREE.MeshStandardMaterial({ color: '#94a3b8', roughness: 0.3, metalness: 0.6 });
const landingMat = new THREE.MeshStandardMaterial({ color: '#c8b4a0', roughness: 0.75, metalness: 0 });

// ---------------------------------------------------------------------------
// Flight geometry
// ---------------------------------------------------------------------------

interface FlightMeshProps {
  flight: StairFlight;
  floorElevationCm: number;
}

const FlightMesh: React.FC<FlightMeshProps> = ({ flight, floorElevationCm }) => {
  const { startPoint, endPoint, widthCm, bottomElevationCm, stepCount, risePerStepCm, goingPerStepCm } = flight;

  // 3D plan direction: plan +Y → 3D -Z.
  const dx3 = (endPoint.x - startPoint.x) * CM;
  const dz3 = -(endPoint.y - startPoint.y) * CM; // plan y → 3D -z
  const len3 = Math.hypot(dx3, dz3) || 1;
  const ux = dx3 / len3; // unit along flight in XZ
  const uz = dz3 / len3;
  // Perpendicular (right side when facing up the flight).
  const rx = uz;
  const rz = -ux;

  // Flight origin in world space (bottom step's front-bottom corner).
  const ox = startPoint.x * CM;
  const oz = -startPoint.y * CM;
  const oy = (bottomElevationCm - floorElevationCm) * CM;

  const w = widthCm * CM;
  const rise = risePerStepCm * CM;
  const going = goingPerStepCm * CM;

  // Tread / riser dimensions.
  const tt = Math.min(0.04, rise * 0.4);   // tread board thickness (Y)
  const nosing = going * 0.06;              // tread overhang past riser face
  const rt = Math.min(0.02, going * 0.25); // riser board thickness (along flight)

  // Stringer dimensions.
  const stringerW = 0.04;                              // stringer board width (across-flight)
  const stringerH = Math.max(0.15, rise * 1.2);        // stringer height
  const slopeLen = Math.sqrt(going * going * stepCount * stepCount + rise * rise * stepCount * stepCount);
  const pitch = Math.atan2(rise * stepCount, going * stepCount);
  const railH = 0.9;
  const posts = Math.max(2, Math.floor(slopeLen / 0.5));

  const treadW = Math.max(0.1, w - 2 * stringerW); // tread width between stringers

  // Render each step at its exact world position.
  const steps = Array.from({ length: stepCount }).map((_, i) => {
    // Along-flight offset to the step centre.
    const at = (i + 0.5) * going; // metres along flight
    // Tread top surface Y.
    const topY = oy + (i + 1) * rise;

    // Step centre in world XZ.
    const cx = ox + ux * at;
    const cz = oz + uz * at;

    // Tread: horizontal board, centred at (cx, topY - tt/2, cz + nosing/2 along-flight).
    const treadCx = cx + ux * (nosing / 2);
    const treadCz = cz + uz * (nosing / 2);

    // Riser: vertical board at back of step.
    const riserT = (i + 0) * going; // back edge of step
    const riserCx = ox + ux * riserT + ux * (rt / 2);
    const riserCz = oz + uz * riserT + uz * (rt / 2);
    const riserTopY = oy + (i + 1) * rise - rise / 2;

    return (
      <group key={i}>
        {/* Tread */}
        <mesh
          position={[treadCx, topY - tt / 2, treadCz]}
          rotation={[0, Math.atan2(uz, ux), 0]}
          material={lightWoodMat}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[going + nosing, tt, treadW]} />
        </mesh>
        {/* Riser */}
        <mesh
          position={[riserCx, riserTopY, riserCz]}
          rotation={[0, Math.atan2(uz, ux), 0]}
          material={whiteMat}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[rt, rise, treadW]} />
        </mesh>
      </group>
    );
  });

  // Stringers: one on each side of the flight, raked along the slope.
  // Rotation: Three.js Euler XYZ — Y-rotation aligns local +X with flight direction in XZ,
  // then Z-rotation tilts local +X up the slope. Box X-axis (slopeLen) runs along the slope.
  const flightAngle = Math.atan2(uz, ux);
  const stringer = (side: 1 | -1) => {
    const sideOffset = side * (w / 2 - stringerW / 2);
    const scx = ox + rx * sideOffset + ux * (going * stepCount / 2);
    const scz = oz + rz * sideOffset + uz * (going * stepCount / 2);
    const midY = oy + rise * stepCount / 2;
    return (
      <group
        key={side}
        position={[scx, midY, scz]}
        rotation={[0, flightAngle, -pitch]}
      >
        {/* Stringer board running along the slope */}
        <mesh position={[0, 0, 0]} material={darkWoodMat} castShadow receiveShadow>
          <boxGeometry args={[slopeLen, stringerH, stringerW]} />
        </mesh>
        {/* Handrail running along the slope above the stringer */}
        <mesh position={[0, stringerH / 2 + railH, 0]} material={metalMat} castShadow>
          <boxGeometry args={[slopeLen, 0.04, stringerW * 1.3]} />
        </mesh>
        {/* Balusters (vertical posts) */}
        {Array.from({ length: posts }).map((_, i) => (
          <mesh
            key={i}
            position={[-slopeLen / 2 + (slopeLen * (i + 0.5)) / posts, (stringerH / 2 + railH) / 2, 0]}
            material={metalMat}
            castShadow
          >
            <boxGeometry args={[stringerW * 0.5, stringerH / 2 + railH, stringerW * 0.5]} />
          </mesh>
        ))}
      </group>
    );
  };

  return (
    <group>
      {steps}
      {stringer(-1)}
      {stringer(1)}
    </group>
  );
};

// ---------------------------------------------------------------------------
// Landing geometry
// ---------------------------------------------------------------------------

interface LandingMeshProps {
  landing: StairLanding;
  floorElevationCm: number;
}

const LandingMesh: React.FC<LandingMeshProps> = ({ landing, floorElevationCm }) => {
  const { center, widthCm, depthCm, elevationCm, rotation } = landing;
  const cx = center.x * CM;
  const cz = -center.y * CM;
  const cy = (elevationCm - floorElevationCm) * CM;
  const w = widthCm * CM;
  const d = depthCm * CM;
  const thickness = 0.05;
  const railH = 0.9;

  return (
    <group position={[cx, cy, cz]} rotation={[0, rotation, 0]}>
      {/* Platform slab */}
      <mesh position={[0, -thickness / 2, 0]} material={landingMat} castShadow receiveShadow>
        <boxGeometry args={[w, thickness, d]} />
      </mesh>
      {/* Simple handrail on two sides */}
      <mesh position={[-(w / 2 - 0.02), railH / 2, 0]} material={metalMat} castShadow>
        <boxGeometry args={[0.04, railH, d]} />
      </mesh>
      <mesh position={[w / 2 - 0.02, railH / 2, 0]} material={metalMat} castShadow>
        <boxGeometry args={[0.04, railH, d]} />
      </mesh>
    </group>
  );
};

// ---------------------------------------------------------------------------
// Stair entity renderer
// ---------------------------------------------------------------------------

interface StairMeshProps {
  stair: StairEntity;
  floorElevationCm: number;
}

export const StairMesh: React.FC<StairMeshProps> = React.memo(({ stair, floorElevationCm }) => {
  return (
    <group>
      {stair.flights.map((flight) => (
        <FlightMesh key={flight.id} flight={flight} floorElevationCm={floorElevationCm} />
      ))}
      {stair.landings.map((landing) => (
        <LandingMesh key={landing.id} landing={landing} floorElevationCm={floorElevationCm} />
      ))}
    </group>
  );
});

StairMesh.displayName = 'StairMesh';
