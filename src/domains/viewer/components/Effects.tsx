// src/domains/viewer/components/Effects.tsx
//
// Screen-space post-processing — the single biggest "render, not game" upgrade per line of
// code. This is what adds the soft contact shading in corners and under furniture (ambient
// occlusion), a gentle glow on bright highlights (bloom), and clean edge anti-aliasing that
// together read as a photographed interior rather than a flat real-time scene.
//
// WHY IT'S CHEAP / RUNS EVERYWHERE:
// These are full-screen passes whose cost scales with the number of on-screen PIXELS, not
// with how much furniture is in the house. Combined with the canvas dpr cap of 2, they run
// comfortably on the integrated GPUs shipped in ordinary laptops (any WebGL2 browser). There
// is no ray tracing and no dependency on a discrete graphics card.
//
// QUALITY TIERS (driven by the store's renderQuality so weak machines stay smooth):
//   • low    → no post-processing at all (cheapest; the raw scene still has sun + shadows).
//   • medium → half-resolution ambient occlusion + SMAA anti-aliasing.
//   • high   → full-resolution ambient occlusion + bloom + SMAA + a whisper of vignette.
//
// Tone mapping: the canvas sets ACES filmic tone mapping in onCreated; @react-three/
// postprocessing's EffectComposer reads that automatically and applies it as the final step,
// so the photographic colour curve is preserved. frameBufferType=HalfFloat keeps the HDR
// range intact so bloom and tone mapping behave correctly.

import React from 'react';
import * as THREE from 'three';
import { EffectComposer, N8AO, Bloom, SMAA, Vignette } from '@react-three/postprocessing';
import { useAppStore } from '@/store';
import { useHeavyScene } from '../hooks/useHeavyScene';

export const Effects: React.FC = () => {
  const quality = useAppStore((s) => s.renderQuality);
  // Campus-scale plans skip post-processing too: N8AO's depth pre-pass re-renders every
  // mesh, which a scene with thousands of meshes cannot afford.
  const heavyScene = useHeavyScene();

  // Low tier: skip the composer entirely. Returning null means zero post-processing cost.
  if (quality === 'low' || heavyScene) return null;

  const isHigh = quality === 'high';

  return (
    <EffectComposer
      // SMAA does our anti-aliasing, so the composer's own MSAA is off (cheaper).
      multisampling={0}
      // Keep HDR precision through the chain so bloom + ACES tone mapping look right.
      frameBufferType={THREE.HalfFloatType}
    >
      {/*
       * Ambient occlusion. This is the star of the show: it darkens the creases where walls
       * meet floors, the contact line under every bed/sofa, and the insides of cabinets —
       * exactly the soft shading your eye reads as "real". On medium it runs at half-res
       * ("performance") to stay light; on high it runs full quality.
       */}
      <N8AO
        aoRadius={isHigh ? 1.2 : 0.9}
        distanceFalloff={1.0}
        intensity={isHigh ? 2.2 : 1.6}
        quality={isHigh ? 'high' : 'performance'}
        halfRes={!isHigh}
        color="#0a0a0a"
      />

      {/* High tier only — these add polish but cost a little more. */}
      {isHigh ? (
        <>
          {/*
           * Bloom on the brightest pixels only (sunlit window glass, glossy highlights).
           * mipmapBlur gives a soft, wide glow cheaply. luminanceThreshold high so ordinary
           * surfaces don't wash out — only genuine highlights bloom.
           */}
          <Bloom intensity={0.35} luminanceThreshold={0.9} luminanceSmoothing={0.3} mipmapBlur />
          <SMAA />
          {/* Barely-there vignette focuses the eye toward the centre, like a real lens. */}
          <Vignette eskil={false} offset={0.2} darkness={0.5} />
        </>
      ) : (
        <SMAA />
      )}
    </EffectComposer>
  );
};
