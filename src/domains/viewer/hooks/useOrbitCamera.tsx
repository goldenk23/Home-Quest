// src/domains/viewer/hooks/useOrbitCamera.ts

import React, { useRef, useEffect } from 'react';
import { OrbitControls } from '@react-three/drei';
import { useAppStore } from '@/store';

/**
 * Bird's-eye orbit camera. Clamps distance and polar angle so you can't fly underground
 * or zoom inside a wall, and re-targets the plan centroid whenever it changes.
 */
export const OrbitCameraController: React.FC = () => {
  const controlsRef = useRef<any>(null);
  const planCentroid = useAppStore((s) => s.planCentroid3D);

  useEffect(() => {
    if (controlsRef.current && planCentroid) {
      controlsRef.current.target.set(planCentroid.x, 0, planCentroid.z);
      controlsRef.current.update();
    }
  }, [planCentroid]);

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
