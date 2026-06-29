// src/domains/viewer/hooks/useFirstPerson.ts

import { useRef, useEffect, useCallback } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { useAppStore } from '@/store';
import { planTo3D, stairRampHeightAt } from '../services/transform';
import { getCatalogEntry, STAIRS_CATALOG_ID } from '../hooks/useAssetLoader';
import { computeSignedArea } from '@/domains/editor/services/roomDetection';
import type { StairEntity, StairFlight } from '@/types/stair';

interface FirstPersonConfig {
  moveSpeed: number; // meters / second
  sprintMultiplier: number; // speed multiplier while holding Shift
  lookSpeed: number; // radians / pixel
  eyeHeight: number; // meters
  collisionRadius: number; // meters — how far to stay clear of wall faces
  acceleration: number; // 1/s — how quickly velocity ramps toward the target (higher = snappier)
  lookSmoothing: number; // 1/s — how quickly the view eases toward the mouse target (higher = tighter)
  heightSmoothing: number; // 1/s — how quickly the camera's vertical position eases toward the
  // floor/stair ramp height under the player's feet (higher = snappier). Without this, walking
  // down stairs feels like falling: the raw ramp height is correct in theory, but any tiny
  // discontinuity (floor-selection flipping, ramp engagement window edges) reads as a sudden drop.
  stairHeightSmoothing: number; // 1/s — near-snap vertical tracking while riding a stair ramp.
  // A stair ramp is a KNOWN continuous slope, so the gentle heightSmoothing (which exists to mask
  // discrete floor-selection flips) only hurts here: its lag puts the camera below the real steps
  // when climbing (you clip through the stairs) and above them when descending (you float, then
  // fall). Tracking the ramp almost exactly removes both.
  headingAlign: number; // 1/s — how gently the view eases to face up/down a flight while you move
  // along it. Soft assist, not a snap: you keep full mouse control, it just nudges you straight.
}

const DEFAULT_CONFIG: FirstPersonConfig = {
  moveSpeed: 3.5,
  sprintMultiplier: 2.2,
  lookSpeed: 0.0022,
  eyeHeight: 1.6,
  collisionRadius: 0.3,
  acceleration: 9,
  lookSmoothing: 22,
  heightSmoothing: 9,
  stairHeightSmoothing: 40,
  headingAlign: 1.8,
};

const CM_PER_M = 100;
const MIN_FOV = 30;
const MAX_FOV = 110; // wide-angle so small rooms don't feel cramped
const DEFAULT_FOV = 82;

/** Shortest distance (cm) from a plan-space point to a wall centerline segment. */
function pointToSegmentDistanceCm(
  px: number, py: number,
  ax: number, ay: number,
  bx: number, by: number
): number {
  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return Math.hypot(px - ax, py - ay);
  let t = ((px - ax) * dx + (py - ay) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

// Tolerance (m) at a flight's ends/sides for engagement checks — lets the player step onto a
// flight from the room and not fall through the gap at the very edge of its footprint.
const FLIGHT_EDGE_TOL_M = 0.15;

// Length (m) of the free "apron" at each END of a flight where the lateral axis-lock and width
// clamp are RELEASED. The lock exists to stop you strafing off the side mid-climb, but at the very
// bottom/top you need lateral freedom to mount, dismount, and turn off to the side onto the floor —
// otherwise you get funnelled straight into whatever wall faces the top of the stairs and trapped.
// The ends are at floor level, so stepping off the side there just lands you on the adjacent floor.
const FLIGHT_END_APRON_M = 0.6;

// How far (m) a flight's ramp surface may sit ABOVE the player's feet and still be CLIMBABLE (you
// get lifted onto it) rather than a wall. Generous (0.5m ≈ 3 step rises) so that while climbing a
// continuous ramp you are ALWAYS lifted and never get blocked by your own next step — the cause of
// the "stuck at the bottom, can't go up" deadlock when this sat at 0.30 while the height engagement
// lifted only up to 0.28 (a 2cm gap a single fast/low-fps frame could fall into). Used by BOTH the
// height ramp and the rigid-body guard so they can never disagree.
const STAIR_STEP_UP_M = 0.5;
// Above this height (m) over the feet, a flight surface is overhead clearance, not a wall: you walk
// UNDER it (e.g. the upper flight of a switchback). Between STAIR_STEP_UP_M and this, the surface is
// a step face at body height — the solid side you must not pass through.
const STAIR_HEAD_CLEARANCE_M = 2.0;

/**
 * Ease an angle toward a target along the SHORTEST arc, by fraction t. Naively lerping radians
 * spins the long way around the ±π seam (e.g. from -3.1 to +3.1); wrapping the delta into (-π, π]
 * first guarantees the short rotation. Used to gently align the view with a stair flight's axis.
 */
function approachAngle(current: number, target: number, t: number): number {
  const diff = Math.atan2(Math.sin(target - current), Math.cos(target - current));
  return current + diff * t;
}

/**
 * Local (along the flight's ascent axis / across its width) frame for a stair flight, in 3D
 * metres. `along` 0→flightLenM maps bottom→top of the flight; `across` 0 is the centerline.
 * Shared by the height ramp, the lateral axis-lock, and the edge clamp so all three agree on
 * exactly the same footprint.
 */
function flightFrame(flight: StairFlight): {
  ux: number; uy: number; nx: number; ny: number;
  ox: number; oz: number; flightLenM: number; halfWidthM: number;
} | null {
  const dx = flight.endPoint.x - flight.startPoint.x;
  const dy = flight.endPoint.y - flight.startPoint.y;
  const planLen = Math.hypot(dx, dy);
  if (planLen < 0.001) return null;
  const ux = dx / planLen;
  const uy = dy / planLen;
  const nx = -uy;
  const ny = ux;
  return {
    ux, uy, nx, ny,
    ox: flight.startPoint.x / CM_PER_M,
    oz: -flight.startPoint.y / CM_PER_M,
    flightLenM: planLen / CM_PER_M,
    halfWidthM: flight.widthCm / 2 / CM_PER_M,
  };
}

/**
 * Local (along, across) coordinates of a 3D point (x, z) relative to a flight frame.
 * Plan +X → 3D +X; plan +Y → 3D -Z, so the 3D direction along the flight is (ux, -uy).
 */
function flightLocalCoords(
  frame: { ux: number; uy: number; nx: number; ny: number; ox: number; oz: number },
  x: number,
  z: number
): { along: number; across: number } {
  const along = (x - frame.ox) * frame.ux + (z - frame.oz) * (-frame.uy);
  const across = (x - frame.ox) * frame.nx + (z - frame.oz) * (-frame.ny);
  return { along, across };
}

/**
 * First-person walkthrough controls.
 *
 * Movement options (all while pointer is locked):
 *  - Hold the LEFT mouse button to glide forward in the direction you're looking
 *    (the easy mode — no keyboard needed, just steer with the mouse).
 *  - Hold the RIGHT mouse button to glide backward.
 *  - WASD or the Arrow keys to move.
 *  - Hold Shift to sprint.
 *
 * Movement is multiplied by `delta` so speed is identical at any framerate.
 */
export function useFirstPersonControls(config = DEFAULT_CONFIG) {
  const { camera, gl } = useThree();
  const euler = useRef(new THREE.Euler(0, 0, 0, 'YXZ')); // TARGET orientation (driven by mouse)
  const smoothEuler = useRef(new THREE.Euler(0, 0, 0, 'YXZ')); // RENDERED orientation (eased toward target)
  const velocity = useRef(new THREE.Vector3()); // current horizontal velocity (m/s) in world x,z
  const smoothedGroundM = useRef<number | null>(null); // eased ground height (m), eyeHeight excluded
  const keys = useRef(new Set<string>());
  const isLocked = useRef(false);
  const mouseMove = useRef(0); // +1 = forward (LMB), -1 = backward (RMB), 0 = none
  const sprinting = useRef(false);

  const requestLock = useCallback(() => {
    const el = gl.domElement;
    if (document.pointerLockElement === el) return; // already locked
    // requestPointerLock returns a Promise in newer browsers; it can reject (e.g. the
    // ~1s security cool-down right after the user hit Esc). Swallow that so it doesn't
    // surface as an uncaught error — the next click will succeed.
    const res = el.requestPointerLock() as unknown as Promise<void> | undefined;
    if (res && typeof res.catch === 'function') res.catch(() => {});
  }, [gl]);

  // Reliably enter pointer-lock on ANY click on the 3D canvas while first-person mode is
  // active. This replaces the old approach of raycasting an invisible world-space plane,
  // which silently failed whenever the camera faced away from (or was positioned past)
  // that plane — leaving the user unable to start walking.
  useEffect(() => {
    const el = gl.domElement;
    const onCanvasClick = () => requestLock();
    el.addEventListener('click', onCanvasClick);
    return () => el.removeEventListener('click', onCanvasClick);
  }, [gl, requestLock]);

  // Spawn standing in the MIDDLE of a room (the largest one) so you don't start jammed
  // against a wall. Falls back to the plan centroid, then the origin.
  const resetCameraTick = useAppStore((s) => s.resetCameraTick);

  useEffect(() => {
    const state = useAppStore.getState();
    const { floors, activeFloorId, floorData, planCentroid3D } = state;
    // Spawn on the storey the player will actually stand in (ground level / lowest floor),
    // pulling its geometry from the parked set if it isn't the floor being edited.
    const ground = floors.reduce((lo, f) => (f.elevationCm < lo.elevationCm ? f : lo), floors[0]);
    const geo =
      ground && ground.id !== activeFloorId && floorData[ground.id]
        ? floorData[ground.id]
        : { rooms: state.rooms, vertices: state.vertices };
    const rooms = geo.rooms;
    const vertices = geo.vertices;

    let spawnX = planCentroid3D?.x ?? 0;
    let spawnZ = planCentroid3D?.z ?? 0;

    const roomList = Object.values(rooms);
    if (roomList.length > 0) {
      // Pick the largest room by area.
      let best = roomList[0];
      let bestArea = -Infinity;
      for (const room of roomList) {
        const pts = room.boundaryVertexIds
          .map((id) => vertices[id]?.position)
          .filter((p): p is { x: number; y: number } => Boolean(p));
        if (pts.length < 3) continue;
        const area = Math.abs(computeSignedArea(pts));
        if (area > bestArea) {
          bestArea = area;
          best = room;
        }
      }
      const pts = best.boundaryVertexIds
        .map((id) => vertices[id]?.position)
        .filter((p): p is { x: number; y: number } => Boolean(p));
      if (pts.length >= 3) {
        const avg = pts.reduce((a, p) => ({ x: a.x + p.x, y: a.y + p.y }), { x: 0, y: 0 });
        const center = planTo3D({ x: avg.x / pts.length, y: avg.y / pts.length }, 0);
        spawnX = center.x;
        spawnZ = center.z;
      }
    }

    camera.position.set(spawnX, config.eyeHeight, spawnZ);
    euler.current.set(0, 0, 0, 'YXZ');
    smoothEuler.current.set(0, 0, 0, 'YXZ');
    velocity.current.set(0, 0, 0);
    smoothedGroundM.current = null; // re-snap on next frame instead of easing from the old floor
    camera.quaternion.setFromEuler(euler.current);
    if ((camera as THREE.PerspectiveCamera).isPerspectiveCamera) {
      (camera as THREE.PerspectiveCamera).fov = DEFAULT_FOV;
      (camera as THREE.PerspectiveCamera).updateProjectionMatrix();
    }
  }, [camera, config.eyeHeight, resetCameraTick]);

  useEffect(() => {
    const onLockChange = () => {
      isLocked.current = document.pointerLockElement === gl.domElement;
      if (!isLocked.current) {
        // Stop all motion when the mouse is released.
        keys.current.clear();
        mouseMove.current = 0;
        sprinting.current = false;
        velocity.current.set(0, 0, 0);
      }
    };
    const onMouseMove = (e: MouseEvent) => {
      if (!isLocked.current) return;
      // Update only the TARGET orientation here. The frame loop eases the camera toward it,
      // which removes the raw per-event jitter and gives a smooth, settled look feel.
      euler.current.y -= e.movementX * config.lookSpeed;
      euler.current.x -= e.movementY * config.lookSpeed;
      // Clamp pitch so you can't flip over backwards.
      euler.current.x = Math.max(-Math.PI / 2 + 0.01, Math.min(Math.PI / 2 - 0.01, euler.current.x));
    };
    const onMouseDown = (e: MouseEvent) => {
      if (!isLocked.current) return; // the initial lock-click shouldn't trigger movement
      if (e.button === 0) mouseMove.current = 1; // left = forward
      else if (e.button === 2) mouseMove.current = -1; // right = backward
    };
    const onMouseUp = (e: MouseEvent) => {
      if (e.button === 0 && mouseMove.current === 1) mouseMove.current = 0;
      if (e.button === 2 && mouseMove.current === -1) mouseMove.current = 0;
    };
    const onContextMenu = (e: MouseEvent) => {
      if (isLocked.current) e.preventDefault(); // let RMB mean "walk back", not a menu
    };
    const onKeyDown = (e: KeyboardEvent) => {
      keys.current.add(e.code);
      if (e.code === 'ShiftLeft' || e.code === 'ShiftRight') sprinting.current = true;
    };
    const onKeyUp = (e: KeyboardEvent) => {
      keys.current.delete(e.code);
      if (e.code === 'ShiftLeft' || e.code === 'ShiftRight') sprinting.current = false;
    };
    // Scroll wheel zooms the field of view (true optical zoom — never moves you into a wall).
    const onWheel = (e: WheelEvent) => {
      if (!isLocked.current) return;
      const cam = camera as THREE.PerspectiveCamera;
      if (!cam.isPerspectiveCamera) return;
      e.preventDefault();
      cam.fov = Math.max(MIN_FOV, Math.min(MAX_FOV, cam.fov + e.deltaY * 0.03));
      cam.updateProjectionMatrix();
    };

    document.addEventListener('pointerlockchange', onLockChange);
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('mouseup', onMouseUp);
    document.addEventListener('contextmenu', onContextMenu);
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('keyup', onKeyUp);
    document.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      document.removeEventListener('pointerlockchange', onLockChange);
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('mouseup', onMouseUp);
      document.removeEventListener('contextmenu', onContextMenu);
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('keyup', onKeyUp);
      document.removeEventListener('wheel', onWheel);
    };
  }, [camera, gl, config.lookSpeed]);

  /**
   * The geometry (walls/vertices/openings) of the storey the camera is currently standing in,
   * chosen by eye height. The global store only holds the ACTIVE floor's geometry; the other
   * floors are parked in `floorData`. Without this, the walkthrough always collided against
   * whatever floor was being EDITED — so while building an upper storey you'd walk straight
   * through the ground-floor walls you actually see. Resolving by elevation fixes that and is
   * a no-op for a single-floor plan (it just returns the ground floor / working set).
   */
  const floorGeometryAtEye = useCallback(() => {
    const state = useAppStore.getState();
    const { floors, activeFloorId, floorData } = state;
    const feetElevCm = (camera.position.y - config.eyeHeight) * CM_PER_M;
    let chosen = floors[0];
    let bestDiff = Infinity;
    for (const f of floors) {
      const diff = Math.abs(f.elevationCm - feetElevCm);
      if (diff < bestDiff) {
        bestDiff = diff;
        chosen = f;
      }
    }
    if (chosen && chosen.id !== activeFloorId) {
      const g = floorData[chosen.id];
      if (g) return { walls: g.walls, vertices: g.vertices, openings: g.openings };
    }
    // Active floor (or fallback): live working set.
    return { walls: state.walls, vertices: state.vertices, openings: state.openings };
  }, [camera, config.eyeHeight]);

  /** Every stair flight across all floors (active floor's live set + parked floors' data). */
  const getAllFlights = useCallback((): StairFlight[] => {
    const state = useAppStore.getState();
    const { floors, activeFloorId, floorData } = state;
    const flights: StairFlight[] = [];
    for (const f of floors) {
      const sta: Record<string, StairEntity> =
        f.id === activeFloorId ? state.stairs : (floorData[f.id]?.stairs ?? {});
      for (const stair of Object.values(sta)) flights.push(...stair.flights);
    }
    return flights;
  }, []);

  /**
   * Height (m, world Y of the surface under the player's feet) at plan-meters (x, z). Normally
   * this is the elevation of the storey nearest the player's current feet height, so they
   * stand on each floor. If the player is within a staircase footprint, they instead ride that
   * staircase's ramp: progress along its ascent axis (local +Z) maps 0→1 to bottom→top, and
   * the top equals the floor above's base — so walking up a flight smoothly lifts the camera
   * one storey, after which `floorGeometryAtEye` switches collision to the upper floor.
   */
  const groundHeightAtM = useCallback((x: number, z: number): { height: number; onStair: boolean } => {
    const state = useAppStore.getState();
    const { floors, activeFloorId, floorData } = state;
    const feetGuessM = camera.position.y - config.eyeHeight;

    // Default: the floor whose base sits nearest the current feet height.
    let groundM = 0;
    let onStair = false; // true when the chosen height comes from a stair ramp/landing, not a flat floor
    let bestDiff = Infinity;
    for (const f of floors) {
      const eM = f.elevationCm / CM_PER_M;
      const diff = Math.abs(eM - feetGuessM);
      if (diff < bestDiff) {
        bestDiff = diff;
        groundM = eM;
      }
    }

    // Legacy furniture-based stairs: ride the ramp of any staircase footprint we're on.
    for (const f of floors) {
      const fur = f.id === activeFloorId ? state.furniture : floorData[f.id]?.furniture;
      if (!fur) continue;
      const baseM = f.elevationCm / CM_PER_M;
      for (const item of Object.values(fur)) {
        if (item.catalogId !== STAIRS_CATALOG_ID) continue;
        const cat = getCatalogEntry(item.catalogId);
        const halfW = (cat.bounds.width / 2) * item.scale / CM_PER_M;
        const halfD = (cat.bounds.depth / 2) * item.scale / CM_PER_M;
        const riseM = (cat.bounds.height * item.scale) / CM_PER_M;
        const cx = item.position.x / CM_PER_M;
        const cz = -item.position.y / CM_PER_M; // plan y → 3D z
        const rampM = stairRampHeightAt(x, z, cx, cz, item.rotation, halfW, halfD, baseM, riseM);
        if (rampM === null) continue;
        if (Math.abs(rampM - feetGuessM) < Math.abs(groundM - feetGuessM)) {
          groundM = rampM;
          onStair = true;
        }
      }
    }

    // New StairEntity stairs: ride each flight (linear ramp).
    for (const flight of getAllFlights()) {
      const frame = flightFrame(flight);
      if (!frame) continue;
      const { along, across } = flightLocalCoords(frame, x, z);
      if (along < -FLIGHT_EDGE_TOL_M || along > frame.flightLenM + FLIGHT_EDGE_TOL_M) continue;
      if (Math.abs(across) > frame.halfWidthM + FLIGHT_EDGE_TOL_M) continue;

      // Clamp along so progress stays in [0,1] even in the tolerance band.
      const clampedAlong = Math.max(0, Math.min(frame.flightLenM, along));
      const progress = clampedAlong / frame.flightLenM;
      // bottomElevationCm / topElevationCm are absolute (global) elevations in cm.
      const bottomM = flight.bottomElevationCm / CM_PER_M;
      const topM = flight.topElevationCm / CM_PER_M;
      const rampM = bottomM + progress * (topM - bottomM);
      // Accept the ramp if within a climbable step above OR the full flight height below.
      // The old maxDropM=0.6 caused descent to break once the player was >60cm
      // below the upper floor — the ramp was never re-engaged and they floated up.
      // maxStepUp shares STAIR_STEP_UP_M with the rigid-body guard so a step is never
      // simultaneously "too high to climb" AND "not yet a wall" (the ascent deadlock).
      const maxStepUpM = STAIR_STEP_UP_M;
      const maxDropM = Math.max(4.5, (topM - bottomM) + 0.5);
      if (rampM >= feetGuessM - maxDropM && rampM <= feetGuessM + maxStepUpM) {
        groundM = rampM;
        onStair = true;
      }
    }

    // New StairEntity stairs: stand on each landing.
    for (const f of floors) {
      const sta: Record<string, StairEntity> =
        f.id === activeFloorId ? state.stairs : (floorData[f.id]?.stairs ?? {});
      for (const stair of Object.values(sta)) {
        // Check each landing (flat platform).
        for (const landing of stair.landings) {
          const cx = landing.center.x / CM_PER_M;
          const cz = -landing.center.y / CM_PER_M;
          const halfW = landing.widthCm / 2 / CM_PER_M;
          const halfD = landing.depthCm / 2 / CM_PER_M;
          const rot = landing.rotation;
          const cos = Math.cos(rot);
          const sin = Math.sin(rot);
          const lx = (x - cx) * cos + (z - cz) * (-sin);
          const lz = (x - cx) * sin + (z - cz) * cos;
          const edgeTolL = 0.15;
          if (Math.abs(lx) > halfW + edgeTolL || Math.abs(lz) > halfD + edgeTolL) continue;
          const landM = landing.elevationCm / CM_PER_M;
          const maxStepUpL = 0.28;
          const maxDropL = 4.5;
          if (landM >= feetGuessM - maxDropL && landM <= feetGuessM + maxStepUpL) {
            groundM = landM;
            onStair = true;
          }
        }
      }
    }

    return { height: groundM, onStair };
  }, [camera, config.eyeHeight, getAllFlights]);

  /**
   * Constrains the player to a flight's incline direction once they're inside its footprint:
   * strips the across-the-width component out of the intended step so you can't drift/strafe
   * off the side of a stair while ascending or descending — only forward/back progress along
   * the flight's axis is allowed. Mirrors the engagement window groundHeightAtM uses, so a step
   * is locked exactly when the ramp height calc would also be riding this flight.
   */
  const lockStepToFlightAxis = useCallback((
    x: number, z: number, stepX: number, stepZ: number
  ): { x: number; z: number } => {
    for (const flight of getAllFlights()) {
      const frame = flightFrame(flight);
      if (!frame) continue;
      const { along, across } = flightLocalCoords(frame, x, z);
      if (along < -FLIGHT_EDGE_TOL_M || along > frame.flightLenM + FLIGHT_EDGE_TOL_M) continue;
      if (Math.abs(across) > frame.halfWidthM + FLIGHT_EDGE_TOL_M) continue;
      // Release the lock in the end aprons so you can turn off onto the floor at the bottom/top.
      const apron = Math.min(FLIGHT_END_APRON_M, frame.flightLenM * 0.4);
      if (along < apron || along > frame.flightLenM - apron) continue;

      // Across-direction unit vector in 3D (x, z), per the same basis as flightLocalCoords.
      const acrossX = frame.nx;
      const acrossZ = -frame.ny;
      const stepAcross = stepX * acrossX + stepZ * acrossZ;
      return { x: stepX - stepAcross * acrossX, z: stepZ - stepAcross * acrossZ };
    }
    return { x: stepX, z: stepZ };
  }, [getAllFlights]);

  /**
   * Safety net for lockStepToFlightAxis: if a position ever ends up past a flight's side edge
   * (e.g. the player entered the footprint mid-step, before the lock could engage), clamp it
   * back to the flight's width instead of letting them walk off the stair.
   */
  const clampToFlightBounds = useCallback((x: number, z: number): { x: number; z: number } => {
    for (const flight of getAllFlights()) {
      const frame = flightFrame(flight);
      if (!frame) continue;
      const { along, across } = flightLocalCoords(frame, x, z);
      if (along < -FLIGHT_EDGE_TOL_M || along > frame.flightLenM + FLIGHT_EDGE_TOL_M) continue;
      if (Math.abs(across) <= frame.halfWidthM) continue;
      // Don't clamp in the end aprons — you're meant to step off the side onto the floor there.
      const apron = Math.min(FLIGHT_END_APRON_M, frame.flightLenM * 0.4);
      if (along < apron || along > frame.flightLenM - apron) continue;

      const clampedAcross = Math.sign(across) * frame.halfWidthM;
      return {
        x: frame.ox + along * frame.ux + clampedAcross * frame.nx,
        z: frame.oz - along * frame.uy - clampedAcross * frame.ny,
      };
    }
    return { x, z };
  }, [getAllFlights]);

  /**
   * Treats each flight as a SOLID body: returns true if moving to (x, z) would put the player inside
   * a flight footprint where the ramp surface is a step face at BODY height in front of them — i.e.
   * they'd be walking into the solid side of the rise. Used like a wall in the integration step, so
   * a flight blocks (and slides) instead of letting you phase through it.
   *
   * Two bounds, both relative to the feet:
   *  - Below STAIR_STEP_UP_M above the feet → climbable: the height engagement lifts you instead, so
   *    NOT a wall (this shared threshold is what prevents the ascent deadlock). Anything at/below the
   *    feet is also walkable, so descending is never blocked.
   *  - Above STAIR_HEAD_CLEARANCE_M over the feet → overhead clearance: you walk UNDER it (e.g. the
   *    upper flight of a switchback), so NOT a wall.
   * Only the band between the two — a step face roughly knee-to-head high — blocks.
   */
  const stairBodyBlocks = useCallback((x: number, z: number): boolean => {
    if (isNaN(x) || isNaN(z)) return false;
    const feetM = camera.position.y - config.eyeHeight;
    for (const flight of getAllFlights()) {
      const frame = flightFrame(flight);
      if (!frame) continue;
      const { along, across } = flightLocalCoords(frame, x, z);
      // Use the tight footprint (no edge tolerance) so we only block genuinely-inside-the-body
      // positions, never the approach band where the player is meant to mount the flight.
      if (along < 0 || along > frame.flightLenM) continue;
      if (Math.abs(across) > frame.halfWidthM) continue;
      const progress = along / frame.flightLenM;
      const bottomM = flight.bottomElevationCm / CM_PER_M;
      const topM = flight.topElevationCm / CM_PER_M;
      const rampM = bottomM + progress * (topM - bottomM);
      const aboveFeet = rampM - feetM;
      if (aboveFeet > STAIR_STEP_UP_M && aboveFeet < STAIR_HEAD_CLEARANCE_M) return true;
    }
    return false;
  }, [camera, config.eyeHeight, getAllFlights]);

  /**
   * While moving along a flight, gently eases the look TARGET (euler.current.y) toward facing
   * straight up or down that flight — so "press forward" naturally walks you along the stairs
   * without hand-steering. A soft assist, not a snap: it nudges the mouse target, which the look
   * smoothing then eases the rendered camera toward, so you keep full control.
   *
   * (worldDirX, worldDirZ) is the player's intended world-space move direction this frame.
   * No-ops when there's no movement input (so looking around while standing still is never forced),
   * when not inside a flight footprint, or when moving purely across the flight (a deliberate strafe).
   * Legacy furniture stairs have no flight frame, so this simply doesn't engage for them.
   */
  const alignHeadingToFlight = useCallback((
    curX: number, curZ: number, worldDirX: number, worldDirZ: number, deltaSec: number
  ): void => {
    for (const flight of getAllFlights()) {
      const frame = flightFrame(flight);
      if (!frame) continue;
      const { along, across } = flightLocalCoords(frame, curX, curZ);
      if (along < -FLIGHT_EDGE_TOL_M || along > frame.flightLenM + FLIGHT_EDGE_TOL_M) continue;
      if (Math.abs(across) > frame.halfWidthM + FLIGHT_EDGE_TOL_M) continue;

      // 3D ascent direction of the flight is (ux, -uy) (plan +Y → 3D -Z). How much of the intended
      // motion runs along it decides whether we aim up the flight or down it.
      const alongDot = worldDirX * frame.ux + worldDirZ * -frame.uy;
      if (Math.abs(alongDot) < 0.2) return; // pure strafe across the flight — don't spin the view

      // Camera forward from yaw y is (-sin y, 0, -cos y); solving it equal to the chosen direction
      // gives yaw = atan2(-dirX, -dirZ). Ascent dir (ux,-uy) → atan2(-ux, uy); descent flips sign.
      const targetYaw = alongDot > 0
        ? Math.atan2(-frame.ux, frame.uy)
        : Math.atan2(frame.ux, -frame.uy);
      const alignT = 1 - Math.exp(-config.headingAlign * deltaSec);
      euler.current.y = approachAngle(euler.current.y, targetYaw, alignT);
      return;
    }
  }, [config.headingAlign, getAllFlights]);

  /**
   * Ease the camera's Y toward the ground height under (x, z) instead of snapping to it. The
   * raw ramp math in groundHeightAtM is already a continuous slope while walking a flight, but
   * mode switches (floor-selection flip, ramp engagement window edges) can still produce small
   * jumps; smoothing turns those into a brief glide instead of a perceptible teleport/fall.
   */
  const updateHeight = useCallback((x: number, z: number, deltaSec: number) => {
    const { height: target, onStair } = groundHeightAtM(x, z);
    if (smoothedGroundM.current === null) {
      smoothedGroundM.current = target;
    } else {
      // A stair ramp is a continuous, known slope, so track it almost exactly (high k) — the gentle
      // floor smoothing's lag would otherwise sink the camera into the steps going up and float it
      // going down. Flat floor-to-floor changes keep the gentle rate to mask discrete selection flips.
      const k = onStair ? config.stairHeightSmoothing : config.heightSmoothing;
      const heightT = 1 - Math.exp(-k * deltaSec);
      smoothedGroundM.current += (target - smoothedGroundM.current) * heightT;
    }
    camera.position.y = smoothedGroundM.current + config.eyeHeight;
  }, [camera, config.eyeHeight, config.heightSmoothing, config.stairHeightSmoothing, groundHeightAtM]);

  const collidesWithWall = useCallback(
    (mx: number, mz: number): boolean => {
      if (isNaN(mx) || isNaN(mz)) return false;
      const { walls, vertices, openings } = floorGeometryAtEye();
      const px = mx * CM_PER_M;
      const py = -mz * CM_PER_M; // inverse of planTo3D's z = -y
      const radiusCm = config.collisionRadius * CM_PER_M;
      for (const wall of Object.values(walls)) {
        const a = vertices[wall.startVertexId]?.position;
        const b = vertices[wall.endVertexId]?.position;
        if (!a || !b) continue;
        const dist = pointToSegmentDistanceCm(px, py, a.x, a.y, b.x, b.y);
        
        if (dist < wall.thickness / 2 + radiusCm) {
          // Check if we are passing through a door
          let insideDoor = false;
          if (wall.openingIds && wall.openingIds.length > 0) {
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const lenSq = dx * dx + dy * dy;
            let t = 0;
            if (lenSq > 0) {
              t = ((px - a.x) * dx + (py - a.y) * dy) / lenSq;
              t = Math.max(0, Math.min(1, t));
            }
            const distAlongWall = t * Math.sqrt(lenSq);
            
            for (const oid of wall.openingIds) {
              const opening = openings[oid];
              if (opening && opening.type === 'door') {
                // Relax the boundary by adding radiusCm so the player doesn't get stuck on door edges
                if (Math.abs(distAlongWall - opening.offsetCm) < (opening.width / 2) + radiusCm) {
                  insideDoor = true;
                  break;
                }
              }
            }
          }
          if (!insideDoor) return true;
        }
      }
      return false;
    },
    [config.collisionRadius, floorGeometryAtEye]
  );

  /** Unit tangent (3D x,z) of the wall nearest to plan-meters (mx, mz), or null. */
  const nearestWallTangent = useCallback((mx: number, mz: number): { x: number; z: number } | null => {
    if (isNaN(mx) || isNaN(mz)) return null;
    const { walls, vertices } = floorGeometryAtEye();
    const px = mx * CM_PER_M;
    const py = -mz * CM_PER_M;
    let bestDist = Infinity;
    let tangent: { x: number; z: number } | null = null;
    for (const wall of Object.values(walls)) {
      const a = vertices[wall.startVertexId]?.position;
      const b = vertices[wall.endVertexId]?.position;
      if (!a || !b) continue;
      const dist = pointToSegmentDistanceCm(px, py, a.x, a.y, b.x, b.y);
      if (dist < bestDist) {
        bestDist = dist;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const len = Math.hypot(dx, dy);
        if (len > 0) tangent = { x: dx / len, z: -dy / len }; // plan (dx,dy) → 3D (x, -z)
      }
    }
    return tangent;
  }, [floorGeometryAtEye]);

  /**
   * Unit direction (3D x,z) pointing AWAY from the nearest wall, for un-sticking the player.
   * Used instead of the old "phase through everything" escape hatch: if the camera ever ends
   * up inside a wall band, we nudge it straight back out toward open space rather than letting
   * it travel freely through solid walls.
   */
  const wallEjectDir = useCallback((mx: number, mz: number): { x: number; z: number } | null => {
    if (isNaN(mx) || isNaN(mz)) return null;
    const { walls, vertices } = floorGeometryAtEye();
    const px = mx * CM_PER_M;
    const py = -mz * CM_PER_M;
    let bestDist = Infinity;
    let dir: { x: number; z: number } | null = null;
    for (const wall of Object.values(walls)) {
      const a = vertices[wall.startVertexId]?.position;
      const b = vertices[wall.endVertexId]?.position;
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const lenSq = dx * dx + dy * dy;
      let t = lenSq > 0 ? ((px - a.x) * dx + (py - a.y) * dy) / lenSq : 0;
      t = Math.max(0, Math.min(1, t));
      const nx = a.x + t * dx;
      const ny = a.y + t * dy;
      const dist = Math.hypot(px - nx, py - ny);
      if (dist < bestDist) {
        bestDist = dist;
        const vx = px - nx;
        const vy = py - ny;
        const len = Math.hypot(vx, vy);
        if (len > 1e-3) {
          dir = { x: vx / len, z: -vy / len }; // plan → 3D (x, -z)
        } else {
          // Dead on the centerline: push along the wall normal so we still escape.
          const wl = Math.hypot(dx, dy) || 1;
          dir = { x: -dy / wl, z: -dx / wl };
        }
      }
    }
    return dir;
  }, [floorGeometryAtEye]);

  useFrame((_, delta) => {
    if (!isLocked.current) return;

    // Prevent massive jumps if the tab was backgrounded.
    const clampedDelta = Math.min(delta, 0.1);

    // --- 1. Smooth look ------------------------------------------------------
    // Ease the rendered orientation toward the mouse target. Exponential smoothing makes it
    // frame-rate independent: the same feel at 30fps or 144fps. High lookSmoothing keeps it
    // tight and responsive while shaving off raw per-event jitter.
    const lookT = 1 - Math.exp(-config.lookSmoothing * clampedDelta);
    smoothEuler.current.y += (euler.current.y - smoothEuler.current.y) * lookT;
    smoothEuler.current.x += (euler.current.x - smoothEuler.current.x) * lookT;
    camera.quaternion.setFromEuler(smoothEuler.current);

    // --- 2. Desired movement direction (relative to facing) ------------------
    const direction = new THREE.Vector3();
    const fwd = keys.current.has('KeyW') || keys.current.has('ArrowUp');
    const back = keys.current.has('KeyS') || keys.current.has('ArrowDown');
    const left = keys.current.has('KeyA') || keys.current.has('ArrowLeft');
    const right = keys.current.has('KeyD') || keys.current.has('ArrowRight');

    if (fwd) direction.z -= 1;
    if (back) direction.z += 1;
    if (left) direction.x -= 1;
    if (right) direction.x += 1;

    // Hold-mouse-to-walk: left = forward, right = backward.
    if (mouseMove.current === 1) direction.z -= 1;
    else if (mouseMove.current === -1) direction.z += 1;

    // Build the target velocity in world space. When there's no input the target is zero, so
    // the velocity smoothly decays and the player glides to a stop instead of stopping dead.
    const target = new THREE.Vector3();
    if (direction.lengthSq() > 0) {
      direction.normalize();
      // Move relative to where you're facing, but ignore pitch so you don't fly.
      const moveQuat = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, smoothEuler.current.y, 0));
      direction.applyQuaternion(moveQuat);
      // While moving along a flight, gently steer the view to face up/down it (no-op off a flight).
      // Inside this `lengthSq > 0` block, so it only ever engages when the player is actively moving.
      alignHeadingToFlight(camera.position.x, camera.position.z, direction.x, direction.z, clampedDelta);
      const speed = config.moveSpeed * (sprinting.current ? config.sprintMultiplier : 1);
      target.set(direction.x * speed, 0, direction.z * speed);
    }

    // --- 3. Accelerate / decelerate toward the target velocity ---------------
    const accelT = 1 - Math.exp(-config.acceleration * clampedDelta);
    velocity.current.x += (target.x - velocity.current.x) * accelT;
    velocity.current.z += (target.z - velocity.current.z) * accelT;

    // Below a tiny threshold, snap to rest so we don't integrate microscopic drift forever.
    if (velocity.current.lengthSq() < 1e-6) {
      velocity.current.set(0, 0, 0);
      const c = clampToFlightBounds(camera.position.x, camera.position.z);
      camera.position.x = c.x;
      camera.position.z = c.z;
      updateHeight(camera.position.x, camera.position.z, clampedDelta);
      return;
    }

    // --- 4. Integrate position with wall collision + sliding -----------------
    const cur = camera.position;
    // While inside a stair flight's footprint, strip out the across-the-width component so
    // travel strictly follows the flight's incline direction — you can't strafe off the side.
    const lockedStep = lockStepToFlightAxis(
      cur.x, cur.z, velocity.current.x * clampedDelta, velocity.current.z * clampedDelta
    );
    const stepX = lockedStep.x;
    const stepZ = lockedStep.z;

    // NaN safety net: if camera somehow broke, reset it to origin
    if (isNaN(cur.x) || isNaN(cur.z)) {
      cur.set(0, config.eyeHeight, 0);
      velocity.current.set(0, 0, 0);
      return;
    }

    // UN-STICK: if the player is somehow already inside a wall band (e.g. clipped a door
    // jamb, or spawned tight to a wall), eject them straight back out toward open space
    // instead of integrating their step. The old behaviour allowed FREE movement here, which
    // let the player phase through every wall once they touched one — the "walk through
    // walls" bug. Doorways/gates are exempt in collidesWithWall, so standing in an opening
    // never triggers this.
    if (collidesWithWall(cur.x, cur.z)) {
      const dir = wallEjectDir(cur.x, cur.z);
      if (dir) {
        const ejectSpeed = Math.max(config.moveSpeed, 2); // m/s, gentle but firm
        cur.x += dir.x * ejectSpeed * clampedDelta;
        cur.z += dir.z * ejectSpeed * clampedDelta;
      }
      const c = clampToFlightBounds(cur.x, cur.z);
      cur.x = c.x;
      cur.z = c.z;
      updateHeight(cur.x, cur.z, clampedDelta);
      return;
    }

    // A flight is a solid body too: combine wall + stair-body blocking so you slide along the side
    // of a staircase exactly as you would a wall, instead of phasing through it.
    const blocked = (bx: number, bz: number) => collidesWithWall(bx, bz) || stairBodyBlocks(bx, bz);

    if (!blocked(cur.x + stepX, cur.z + stepZ)) {
      // Clear path — go straight.
      cur.x += stepX;
      cur.z += stepZ;
    } else {
      // Heading into a wall: auto-correct by sliding ALONG the wall (project the desired
      // movement onto the wall's tangent), so you smoothly follow it instead of stopping.
      const tan = nearestWallTangent(cur.x + stepX, cur.z + stepZ);
      let slid = false;
      if (tan) {
        const dot = stepX * tan.x + stepZ * tan.z;
        const sx = tan.x * dot;
        const sz = tan.z * dot;
        if ((sx !== 0 || sz !== 0) && !blocked(cur.x + sx, cur.z + sz)) {
          cur.x += sx;
          cur.z += sz;
          // Re-project velocity onto the wall too, so we keep gliding along it next frame
          // instead of fighting the wall and stalling.
          const vDot = velocity.current.x * tan.x + velocity.current.z * tan.z;
          velocity.current.x = tan.x * vDot;
          velocity.current.z = tan.z * vDot;
          slid = true;
        }
      }
      if (!slid) {
        // Fallback: axis-separated sliding (handles corners / axis-aligned walls).
        if (!blocked(cur.x + stepX, cur.z)) cur.x += stepX;
        else velocity.current.x = 0;
        if (!blocked(cur.x, cur.z + stepZ)) cur.z += stepZ;
        else velocity.current.z = 0;
      }
    }

    const c = clampToFlightBounds(cur.x, cur.z);
    cur.x = c.x;
    cur.z = c.z;
    updateHeight(cur.x, cur.z, clampedDelta); // ride floors/stairs
  });

  return { requestLock, isLocked };
}
