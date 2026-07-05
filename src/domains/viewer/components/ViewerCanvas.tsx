// src/domains/viewer/components/ViewerCanvas.tsx

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import * as THREE from 'three';
import { Preload, Stats } from '@react-three/drei';
import { SceneEnvironment } from './SceneEnvironment';
import { SceneContent } from './SceneContent';
import { CameraController } from './CameraController';
import { Effects } from './Effects';
import { useAppStore } from '@/store';
import { useHeavyScene } from '../hooks/useHeavyScene';
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
  const renderQuality = useAppStore((s) => s.renderQuality);
  const hasWalls = useAppStore((s) => Object.keys(s.walls).length > 0);

  // The low tier renders straight to the canvas framebuffer (no EffectComposer). On many
  // GPUs that default depth buffer is only 16-bit, so at orbit distance neighbouring
  // near-coplanar wall surfaces land in the same depth quantum and z-fight into the streaky
  // "fan" artifacts. Medium/high avoid this because N8AO attaches a high-precision depth
  // texture to the composer's render target. A logarithmic depth buffer gives the low tier
  // near-uniform precision regardless of the framebuffer's bit depth, which removes the
  // fighting. It's scoped to low only: medium/high read depth in post (N8AO), where a
  // logarithmic buffer would need special handling, so we leave them exactly as before.
  const lowTier = renderQuality === 'low';

  // Very large plans (e.g. the Hall-1 campus: thousands of meshes across 3 storeys) can't
  // afford the shadow pass — it re-renders every mesh into the shadow map each frame. For
  // those scenes shadows are dropped and the pixel ratio capped; normal houses keep the
  // full treatment.
  const heavyScene = useHeavyScene();

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
    <div id="viewer-canvas" className="w-full h-full relative">
      <ModelLoadingProgress />
      <Canvas
        // Remount when toggling the logarithmic-depth path, since the depth mode is fixed at
        // WebGL-context creation. Only low↔(medium/high) switches remount; medium↔high don't.
        key={lowTier ? 'gl-logdepth' : 'gl-standard'}
        shadows={!heavyScene}
        dpr={heavyScene ? 1 : [1, 2]}
        // preserveDrawingBuffer keeps the rendered frame readable so image/PDF export
        // (canvas.toDataURL / toBlob) works at any time, not just mid-frame.
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: 'high-performance',
          stencil: false,
          preserveDrawingBuffer: true,
          // See the lowTier note above: only the no-composer low path needs this.
          logarithmicDepthBuffer: lowTier,
        }}
        // near is raised above the usual 0.1 to reclaim depth-buffer precision: a smaller
        // near/far ratio leaves coplanar wall faces (corners, joints) z-fighting, especially
        // on the 'low' tier with no post-AA to hide it. First-person mode overrides this to
        // 0.05 on mount (via useFirstPersonControls) to prevent frustum-corner clipping into
        // wall faces, then restores 0.2 on unmount so orbit mode keeps its precision benefit.
        camera={{ fov: 60, near: 0.2, far: 1000, position: [10, 10, 10] }}
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
        {/* Post-processing runs after the scene renders. It reads renderQuality internally
            and disables itself on the 'low' tier, so low-end machines pay nothing. */}
        <Effects />
        {import.meta.env.DEV && <Stats />}
      </Canvas>
    </div>
  );
};
