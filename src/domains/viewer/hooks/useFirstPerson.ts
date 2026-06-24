// src/domains/viewer/hooks/useFirstPerson.ts

import { useRef, useEffect, useCallback } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { useAppStore } from '@/store';
import { planTo3D } from '../services/transform';
import { computeSignedArea } from '@/domains/editor/services/roomDetection';

interface FirstPersonConfig {
  moveSpeed: number; // meters / second
  sprintMultiplier: number; // speed multiplier while holding Shift
  lookSpeed: number; // radians / pixel
  eyeHeight: number; // meters
  collisionRadius: number; // meters — how far to stay clear of wall faces
  acceleration: number; // 1/s — how quickly velocity ramps toward the target (higher = snappier)
  lookSmoothing: number; // 1/s — how quickly the view eases toward the mouse target (higher = tighter)
}

const DEFAULT_CONFIG: FirstPersonConfig = {
  moveSpeed: 3.5,
  sprintMultiplier: 2.2,
  lookSpeed: 0.0022,
  eyeHeight: 1.6,
  collisionRadius: 0.3,
  acceleration: 9,
  lookSmoothing: 22,
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
    const { rooms, vertices, planCentroid3D } = useAppStore.getState();

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

  const collidesWithWall = useCallback(
    (mx: number, mz: number): boolean => {
      if (isNaN(mx) || isNaN(mz)) return false;
      const { walls, vertices, openings } = useAppStore.getState();
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
    [config.collisionRadius]
  );

  /** Unit tangent (3D x,z) of the wall nearest to plan-meters (mx, mz), or null. */
  const nearestWallTangent = useCallback((mx: number, mz: number): { x: number; z: number } | null => {
    if (isNaN(mx) || isNaN(mz)) return null;
    const { walls, vertices } = useAppStore.getState();
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
  }, []);

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
      camera.position.y = config.eyeHeight;
      return;
    }

    // --- 4. Integrate position with wall collision + sliding -----------------
    const stepX = velocity.current.x * clampedDelta;
    const stepZ = velocity.current.z * clampedDelta;
    const cur = camera.position;

    // NaN safety net: if camera somehow broke, reset it to origin
    if (isNaN(cur.x) || isNaN(cur.z)) {
      cur.set(0, config.eyeHeight, 0);
      velocity.current.set(0, 0, 0);
      return;
    }

    // ESCAPE HATCH: If the player is somehow already stuck inside a wall
    // (e.g. clipped the edge of a door frame), allow free movement so they can walk out
    // rather than permanently freezing their position.
    if (collidesWithWall(cur.x, cur.z)) {
      cur.x += stepX;
      cur.z += stepZ;
      camera.position.y = config.eyeHeight;
      return;
    }

    if (!collidesWithWall(cur.x + stepX, cur.z + stepZ)) {
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
        if ((sx !== 0 || sz !== 0) && !collidesWithWall(cur.x + sx, cur.z + sz)) {
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
        if (!collidesWithWall(cur.x + stepX, cur.z)) cur.x += stepX;
        else velocity.current.x = 0;
        if (!collidesWithWall(cur.x, cur.z + stepZ)) cur.z += stepZ;
        else velocity.current.z = 0;
      }
    }

    camera.position.y = config.eyeHeight; // pinned to standing height
  });

  return { requestLock, isLocked };
}
