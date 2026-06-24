// src/domains/viewer/components/ViewerCanvas.tsx

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import * as THREE from 'three';
import { Preload, Stats } from '@react-three/drei';
import { SceneEnvironment } from './SceneEnvironment';
import { SceneContent } from './SceneContent';
import { CameraController } from './CameraController';
import { useAppStore } from '@/store';
import { ModelLoadingProgress } from '@/domains/shared/components/ModelLoadingProgress';
import { EmptyState } from '@/domains/shared/components/EmptyState';

/**
 * The 3D viewport.
 * - shadows + PCF soft shadow maps for grounded lighting
 * - dpr capped at 2 so 4K displays don't tank the framerate
 * - a Suspense boundary so async asset loads don't crash the tree
 * - an empty state until the plan has walls, and an asset-loading overlay
 */
export const ViewerCanvas: React.FC = () => {
  const cameraMode = useAppStore((s) => s.cameraMode);
  const hasWalls = useAppStore((s) => Object.keys(s.walls).length > 0);

  if (!hasWalls) {
    return (
      <EmptyState
        title="No floor plan yet"
        description="Draw walls in the 2D editor to see your design come to life in 3D."
        icon="🏗️"
      />
    );
  }

  return (
    <div className="w-full h-full relative">
      <ModelLoadingProgress />
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', stencil: false }}
        camera={{ fov: 60, near: 0.1, far: 1000, position: [10, 10, 10] }}
        onCreated={({ gl }) => {
          // Filmic tone mapping + a hair of extra exposure turns the flat, video-game
          // look into a softer, photographed one. Free — it's just how the final image is
          // mapped to the screen, no extra GPU passes.
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.05;
        }}
      >
        <Suspense fallback={null}>
          <SceneEnvironment />
          <SceneContent />
          <CameraController mode={cameraMode} />
          <Preload all />
        </Suspense>
        {import.meta.env.DEV && <Stats />}
      </Canvas>
    </div>
  );
};
