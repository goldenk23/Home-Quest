// src/domains/viewer/components/ViewerCanvas.tsx

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Preload, Stats } from '@react-three/drei';
import { SceneEnvironment } from './SceneEnvironment';
import { SceneContent } from './SceneContent';

/**
 * The 3D viewport.
 * - shadows + PCF soft shadow maps for grounded lighting
 * - dpr capped at 2 so 4K displays don't tank the framerate
 * - a Suspense boundary so async GLTF loads don't crash the tree
 * - OrbitControls is a placeholder camera until Part 13's CameraController
 */
export const ViewerCanvas: React.FC = () => {
  return (
    <div className="w-full h-full">
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', stencil: false }}
        camera={{ fov: 60, near: 0.1, far: 1000, position: [10, 10, 10] }}
      >
        <Suspense fallback={null}>
          <SceneEnvironment />
          <SceneContent />
          <OrbitControls makeDefault />
          <Preload all />
        </Suspense>
        {import.meta.env.DEV && <Stats />}
      </Canvas>
    </div>
  );
};
