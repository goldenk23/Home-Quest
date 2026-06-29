// src/domains/viewer/components/StairMesh.tsx
//
// 3D renderer for a StairEntity.
//
// Coordinate convention:
//   plan (x, y) → 3D (x * CM, elevation * CM, -y * CM)
//   plan direction (ux, uy) → 3D flight direction (ux, 0, -uy) in world XZ
//
// Y-rotation formula:
//   To align local +X with world direction (ux, 0, uz), use rotation-Y = atan2(-uz, ux).
//   Three.js Ry(θ) maps local +X → world (cosθ, 0, -sinθ), so cosθ=ux, -sinθ=uz → sinθ=-uz.

import React, { useMemo } from 'react';
import * as THREE from 'three';
import type { StairEntity, StairFlight, StairLanding } from '@/types/stair';

const CM = 0.01; // cm → m

// Shared materials.
const treadMat = new THREE.MeshStandardMaterial({ color: '#c8a96e', roughness: 0.65, metalness: 0 });
// polygonOffset pushes risers and the landing slab slightly behind treads in the depth buffer,
// eliminating Z-fighting at the nosing overlap (riser bottom ↔ previous tread top, same Y plane).
const riserMat = new THREE.MeshStandardMaterial({ color: '#f0ece4', roughness: 0.55, metalness: 0, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 4 });
const stringerMat = new THREE.MeshStandardMaterial({ color: '#5a4230', roughness: 0.7, metalness: 0 });
const railMat = new THREE.MeshStandardMaterial({ color: '#8b9cad', roughness: 0.25, metalness: 0.7 });
// Landing slab top face coincides with the last tread top face — same polygonOffset fix.
const landingMat = new THREE.MeshStandardMaterial({ color: '#b8a99a', roughness: 0.7, metalness: 0, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 4 });

// ---------------------------------------------------------------------------
// Flight mesh
// ---------------------------------------------------------------------------

interface FlightMeshProps {
  flight: StairFlight;
  floorElevationCm: number;
  /** True if there is a landing platform immediately at the top of this flight. */
  hasTopLanding?: boolean;
  /** True if there is a landing platform immediately at the bottom of this flight. */
  hasBottomLanding?: boolean;
}

const FlightMesh: React.FC<FlightMeshProps> = ({ flight, floorElevationCm, hasTopLanding = false, hasBottomLanding = false }) => {
  const {
    startPoint, endPoint, widthCm,
    bottomElevationCm, stepCount, risePerStepCm, goingPerStepCm,
  } = flight;

  // 3D flight direction in world XZ:  plan +Y → 3D -Z
  const dx = (endPoint.x - startPoint.x) * CM;
  const dz = -(endPoint.y - startPoint.y) * CM;   // plan y → 3D -z
  const hLen = Math.hypot(dx, dz) || 1;            // horizontal length (m)
  const ux = dx / hLen;                             // unit along flight (world X)
  const uz = dz / hLen;                             // unit along flight (world Z)

  // Right-hand perpendicular in XZ (right side when facing up the flight).
  const rx = -uz;
  const rz = ux;

  // Y-rotation angle that aligns local +X with (ux, 0, uz):
  //   Ry(θ) * (1,0,0) = (cosθ, 0, -sinθ)  →  cosθ = ux, sinθ = -uz
  const yAngle = Math.atan2(-uz, ux);

  // Flight origin in world space (bottom of first riser).
  const ox = startPoint.x * CM;
  const oy = (bottomElevationCm - floorElevationCm) * CM;
  const oz = -startPoint.y * CM;

  const w = widthCm * CM;
  const rise = risePerStepCm * CM;
  const going = goingPerStepCm * CM;
  const treadW = w;                              // tread width = full stair width
  const treadT = Math.min(0.035, rise * 0.38);  // tread board thickness
  const riserT = Math.min(0.018, going * 0.22); // riser board thickness (along-flight)
  const nosing  = going * 0.08;                 // small tread overhang

  // Stringer (closed side board).
  const stringerW = 0.05;                        // board width (across-flight)
  const stringerH = Math.max(0.22, rise * 1.3); // board depth (perpendicular to slope)
  const pitch = Math.atan2(rise, going);         // slope angle

  // Full slope length of the flight.
  const slopeLen = stepCount * Math.hypot(going, rise);
  // Full horizontal length of the flight (m).
  const horizLen = going * stepCount;

  // Quaternion that correctly orients a box's local X along the slope direction
  // for any flight heading. Steps:
  //   Q1 = Ry(yAngle)  → aligns local X with (ux, 0, uz) in world XZ
  //   Q2 = rotation by `pitch` around the across-flight axis (rx, 0, rz)
  //         → tilts local X upward to the slope direction (ux·cos, sin, uz·cos)
  // This is mathematically correct for all headings; plain Euler [0,yAngle,pitch]
  // only works for East-facing flights.
  const stringerQuat = useMemo(() => {
    const q1 = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yAngle);
    const q2 = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(rx, 0, rz), pitch);
    return q2.multiply(q1);
  }, [yAngle, pitch, rx, rz]);

  // Handrail dims.
  const railH = 0.9;       // handrail height above tread nosing
  const railThick = 0.045; // rail bar section

  // Trim stringer/rail so they stop at the landing edge instead of extending
  // into the landing platform from either end.
  const landingTrim = w / 2; // half the landing depth = half the stair width
  const bottomTrimH = hasBottomLanding ? landingTrim : 0;
  const topTrimH    = hasTopLanding    ? landingTrim : 0;
  // Horizontal and slope lengths covered by the (possibly trimmed) stringer.
  const trimmedHorizLen = horizLen - bottomTrimH - topTrimH;
  const trimmedSlopeLen = trimmedHorizLen > 0 ? slopeLen * (trimmedHorizLen / horizLen) : 0;
  // Horizontal midpoint of the trimmed stringer (measured from flight origin).
  const hCenter = bottomTrimH + trimmedHorizLen / 2;
  // Elevation at hCenter above the floor reference.
  const elevCenter = oy + (hCenter / going) * rise;
  // Horizontal positions of rail posts (clamped to flight extent).
  const hPostBottom = bottomTrimH;
  const hPostTop    = horizLen - topTrimH;

  // ---- Treads & risers -------------------------------------------------------
  const steps = Array.from({ length: stepCount }, (_, i) => {
    // Centre of tread in along-flight space.
    const tAt = i * going + (going + nosing) / 2; // along-flight centre of tread
    const tTopY = oy + (i + 1) * rise;

    // Tread world position.
    const tcx = ox + ux * tAt;
    const tcz = oz + uz * tAt;
    const tcy = tTopY - treadT / 2;

    // Riser world position (at the FRONT face of step i).
    const rAt = i * going + riserT / 2;
    const rcx = ox + ux * rAt;
    const rcz = oz + uz * rAt;
    const rcy = oy + (i + 0.5) * rise;

    return (
      <group key={i}>
        {/* Tread */}
        <mesh position={[tcx, tcy, tcz]} rotation={[0, yAngle, 0]} material={treadMat} castShadow receiveShadow>
          <boxGeometry args={[going + nosing, treadT, treadW]} />
        </mesh>
        {/* Riser */}
        <mesh position={[rcx, rcy, rcz]} rotation={[0, yAngle, 0]} material={riserMat} castShadow receiveShadow>
          <boxGeometry args={[riserT, rise, treadW]} />
        </mesh>
      </group>
    );
  });

  // ---- Closed stringers (solid side boards) ---------------------------------
  // Stringer centre placed so its top edge sits on the nosing line, trimmed at
  // both ends where a landing platform sits (so it doesn't intrude into the slab).
  const midY = elevCenter - (stringerH / 2) * Math.cos(pitch);

  const stringerMesh = (side: 1 | -1) => {
    const sOff = side * (w / 2 + stringerW / 2); // just outside the tread edge
    // Stringer (trimmed) centre in world space.
    const scx = ox + rx * sOff + ux * hCenter;
    const scz = oz + rz * sOff + uz * hCenter;
    // Post positions at the trimmed ends.
    const elevBottom = oy + (hPostBottom / going) * rise;
    const elevTop    = oy + (hPostTop    / going) * rise;
    const postBx = ox + rx * sOff + ux * hPostBottom;
    const postBz = oz + rz * sOff + uz * hPostBottom;
    const postTx = ox + rx * sOff + ux * hPostTop;
    const postTz = oz + rz * sOff + uz * hPostTop;
    return (
      <group key={side}>
        {/* Stringer board (trimmed where landings attach) */}
        {trimmedSlopeLen > 0 && (
          <mesh
            position={[scx, midY, scz]}
            quaternion={stringerQuat}
            material={stringerMat}
            castShadow
            receiveShadow
          >
            <boxGeometry args={[trimmedSlopeLen, stringerH, stringerW]} />
          </mesh>
        )}
        {/* Handrail post at flight bottom */}
        <mesh
          position={[postBx, elevBottom + railH / 2, postBz]}
          material={railMat}
          castShadow
        >
          <boxGeometry args={[railThick, railH, railThick]} />
        </mesh>
        {/* Handrail post at flight top */}
        <mesh
          position={[postTx, elevTop + railH / 2, postTz]}
          material={railMat}
          castShadow
        >
          <boxGeometry args={[railThick, railH, railThick]} />
        </mesh>
        {/* Continuous handrail bar (angled along trimmed slope) */}
        {trimmedSlopeLen > 0 && (
          <mesh
            position={[scx, elevCenter + railH, scz]}
            quaternion={stringerQuat}
            material={railMat}
            castShadow
          >
            <boxGeometry args={[trimmedSlopeLen, railThick, railThick * 1.5]} />
          </mesh>
        )}
      </group>
    );
  };

  return (
    <group>
      {steps}
      {stringerMesh(-1)}
      {stringerMesh(1)}
    </group>
  );
};

// ---------------------------------------------------------------------------
// Landing mesh
// ---------------------------------------------------------------------------

interface LandingMeshProps {
  landing: StairLanding;
  floorElevationCm: number;
  /** Plan-space angle (radians) of the outgoing flight, so we can suppress rails where flights connect. */
  outgoingAngle: number;
}

/**
 * Maps any plan-space angle θ to the landing local face that the corresponding
 * 3D flight direction "points toward" from the landing center.
 *
 * Derivation: plan angle θ → 3D world dir (cos θ, 0, −sin θ).
 * Landing group rotation = yRot = −inA (inA = landing.rotation).
 * World-to-local transform (inverse of group rotation = rotate by +inA around Y):
 *   lx = wx·cos(inA) + wz·sin(inA)
 *   lz = −wx·sin(inA) + wz·cos(inA)
 * For (wx, wz) = (cos θ, −sin θ): lx = cos(θ+inA), lz = −sin(θ+inA).
 */
function planAngleToLocalFace(
  planAngle: number,
  inA: number
): 'posX' | 'negX' | 'posZ' | 'negZ' {
  const lx = Math.cos(planAngle + inA);
  const lz = -Math.sin(planAngle + inA);
  if (Math.abs(lx) >= Math.abs(lz)) return lx > 0 ? 'posX' : 'negX';
  return lz > 0 ? 'posZ' : 'negZ';
}

const LandingMesh: React.FC<LandingMeshProps> = ({ landing, floorElevationCm, outgoingAngle }) => {
  const { center, widthCm, depthCm, elevationCm, rotation } = landing;
  const cx = center.x * CM;
  const cz = -center.y * CM;
  const cy = (elevationCm - floorElevationCm) * CM;
  const w = widthCm * CM;
  const d = depthCm * CM;
  const thick = 0.06;
  const railH = 0.9;
  const railThick = 0.045;

  // Landing group rotation: plan angle → 3D Y-rotation (negate for plan-Y → 3D -Z).
  const yRot = -rotation;

  // Determine which local faces connect to flights (no rail there) and which are open (rail needed).
  // Incoming flight arrives FROM the negative of its travel direction, so the face it occupies
  // is in the direction OPPOSITE to the incoming flight's local direction.
  // Local direction of plan angle θ = (cos(θ+inA), −sin(θ+inA)), so the opposite face:
  const inA = rotation;
  // Incoming: travel direction is inA, body is behind landing → face in −incoming direction.
  // That's plan angle = inA + π (flip 180°).
  const incomingFace = planAngleToLocalFace(inA + Math.PI, inA);
  // Outgoing: flight body extends FORWARD from center in the outgoing direction.
  const outgoingFace = planAngleToLocalFace(outgoingAngle, inA);

  const showPosX = incomingFace !== 'posX' && outgoingFace !== 'posX';
  const showNegX = incomingFace !== 'negX' && outgoingFace !== 'negX';
  const showPosZ = incomingFace !== 'posZ' && outgoingFace !== 'posZ';
  const showNegZ = incomingFace !== 'negZ' && outgoingFace !== 'negZ';

  // Corner posts: show at a corner if at least one adjacent rail side is open.
  const showCornerNX_NZ = showNegX || showNegZ;
  const showCornerPX_NZ = showPosX || showNegZ;
  const showCornerPX_PZ = showPosX || showPosZ;
  const showCornerNX_PZ = showNegX || showPosZ;

  return (
    <group position={[cx, cy, cz]} rotation={[0, yRot, 0]}>
      {/* Platform slab */}
      <mesh position={[0, -thick / 2, 0]} material={landingMat} castShadow receiveShadow>
        <boxGeometry args={[w, thick, d]} />
      </mesh>

      {/* Guardrails — only on the sides NOT connected to an incoming or outgoing flight */}
      {showPosX && (
        <mesh position={[w / 2, railH, 0]} material={railMat} castShadow>
          <boxGeometry args={[railThick, railThick, d]} />
        </mesh>
      )}
      {showNegX && (
        <mesh position={[-w / 2, railH, 0]} material={railMat} castShadow>
          <boxGeometry args={[railThick, railThick, d]} />
        </mesh>
      )}
      {showPosZ && (
        <mesh position={[0, railH, d / 2]} material={railMat} castShadow>
          <boxGeometry args={[w, railThick, railThick]} />
        </mesh>
      )}
      {showNegZ && (
        <mesh position={[0, railH, -d / 2]} material={railMat} castShadow>
          <boxGeometry args={[w, railThick, railThick]} />
        </mesh>
      )}

      {/* Corner posts only where at least one adjacent side has a rail */}
      {showCornerNX_NZ && (
        <mesh position={[-w / 2, railH / 2, -d / 2]} material={railMat} castShadow>
          <boxGeometry args={[railThick, railH, railThick]} />
        </mesh>
      )}
      {showCornerPX_NZ && (
        <mesh position={[w / 2, railH / 2, -d / 2]} material={railMat} castShadow>
          <boxGeometry args={[railThick, railH, railThick]} />
        </mesh>
      )}
      {showCornerPX_PZ && (
        <mesh position={[w / 2, railH / 2, d / 2]} material={railMat} castShadow>
          <boxGeometry args={[railThick, railH, railThick]} />
        </mesh>
      )}
      {showCornerNX_PZ && (
        <mesh position={[-w / 2, railH / 2, d / 2]} material={railMat} castShadow>
          <boxGeometry args={[railThick, railH, railThick]} />
        </mesh>
      )}
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

export const StairMesh: React.FC<StairMeshProps> = React.memo(({ stair, floorElevationCm }) => (
  <group>
    {stair.flights.map((flight, idx) => (
      <FlightMesh
        key={flight.id}
        flight={flight}
        floorElevationCm={floorElevationCm}
        hasTopLanding={idx < stair.flights.length - 1}
        hasBottomLanding={idx > 0}
      />
    ))}
    {stair.landings.map((landing, idx) => {
      // The outgoing flight from landing idx is flight idx+1 (landings are between flights).
      const outFlight = stair.flights[idx + 1];
      const outgoingAngle = outFlight
        ? Math.atan2(
            outFlight.endPoint.y - outFlight.startPoint.y,
            outFlight.endPoint.x - outFlight.startPoint.x
          )
        : landing.rotation + Math.PI / 2; // fallback: 90° turn
      return (
        <LandingMesh
          key={landing.id}
          landing={landing}
          floorElevationCm={floorElevationCm}
          outgoingAngle={outgoingAngle}
        />
      );
    })}
  </group>
));

StairMesh.displayName = 'StairMesh';
