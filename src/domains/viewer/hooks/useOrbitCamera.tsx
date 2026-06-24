// src/domains/viewer/hooks/useOrbitCamera.ts

import React, { useRef, useEffect } from 'react';
import { OrbitControls } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useAppStore } from '@/store';

/**
 * Bird's-eye orbit camera. Clamps distance and polar angle so you can't fly underground
 * or zoom inside a wall, and re-targets the plan centroid whenever it changes.
 */
export const OrbitCameraController: React.FC = () => {
  const controlsRef = useRef<any>(null);
  const planCentroid = useAppStore((s) => s.planCentroid3D);
  const resetCameraTick = useAppStore((s) => s.resetCameraTick);

  useEffect(() => {
    if (controlsRef.current) {
      if (planCentroid) {
        controlsRef.current.target.set(planCentroid.x, 0, planCentroid.z);
      } else {
        controlsRef.current.target.set(0, 0, 0);
      }
      
      const cam = controlsRef.current.object;
      cam.position.set(10, 10, 10);
      controlsRef.current.update();
    }
  }, [planCentroid, resetCameraTick]);

  // Adaptive near/far plane.
  //
  // A perspective depth buffer spends almost all of its precision right in front of the near
  // plane, and the resolvable depth gap grows with the *square* of the distance from the
  // camera. With a fixed tiny near (0.2 m) and the house sitting 30–50 m away in an orbit,
  // neighbouring near-coplanar surfaces (wall faces, mitred corners, floor/wall junctions)
  // land in the same depth quantum and z-fight. The low tier shows this raw — it has no
  // anti-aliasing to smooth the shimmer — which is the streaky "fan" distortion.
  //
  // Scaling the near plane with the orbit distance keeps the precision roughly constant: when
  // you're pulled back there's nothing close to the camera to clip, so a larger near is free
  // and buys back enormous precision; when you zoom right in, near shrinks back toward 0.2 so
  // nothing gets clipped. far tracks distance too so the range never gets wider than needed.
  useFrame(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    const cam = controls.object;
    const dist = cam.position.distanceTo(controls.target);
    const near = Math.min(Math.max(dist * 0.06, 0.2), 6);
    const far = Math.max(dist * 4, 200) + 100;
    if (Math.abs(cam.near - near) > 0.01 || Math.abs(cam.far - far) > 0.01) {
      cam.near = near;
      cam.far = far;
      cam.updateProjectionMatrix();
    }
  });

  // Restore a small near plane when leaving orbit so first-person (which can stand right up
  // against a wall) never clips through it.
  useEffect(() => {
    const controls = controlsRef.current;
    return () => {
      const cam = controls?.object;
      if (cam) {
        cam.near = 0.2;
        cam.far = 1000;
        cam.updateProjectionMatrix();
      }
    };
  }, []);

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      minDistance={2}
      maxDistance={50}
      maxPolarAngle={Math.PI / 2 - 0.05} // stay above ground
      minPolarAngle={0.1}
      enableDamping
      dampingFactor={0.05}
      rotateSpeed={0.5}
      panSpeed={0.8}
      zoomSpeed={1.2}
    />
  );
};
