// src/domains/viewer/components/SceneEnvironment.tsx

import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Environment, Lightformer, Sky } from '@react-three/drei';
import * as THREE from 'three';
import { useAppStore } from '@/store';
import { computeSun } from '../services/sun';

/**
 * All the lighting + atmosphere for the 3D view, in one place.
 *
 * The centrepiece is a REAL moving sun. Its position, colour and intensity come from a pure
 * sun model (services/sun.ts) driven by a wall-clock time-of-day (and an optional manual
 * compass direction). Because the wall geometry already has genuine holes cut for every
 * window (see extrusion.ts), the sun's beam and its shadow physically stream through those
 * openings into the rooms — and as the time changes the shadows lengthen/shorten and the
 * light shifts warm↔white, just like a real house through the day.
 *
 * Cost notes: no HDRI files, no post-processing passes, no soft-shadow sampling. The sky is
 * a single fullscreen shader (drei <Sky>); everything else is the existing IBL + standard
 * lights. This is deliberately cheap.
 */
export const SceneEnvironment: React.FC = () => {
  const sunTimeHours = useAppStore((s) => s.sunTimeHours);
  const sunAzimuthDeg = useAppStore((s) => s.sunAzimuthDeg);
  const sunDirectionOverride = useAppStore((s) => s.sunDirectionOverride);
  const planCentroid3D = useAppStore((s) => s.planCentroid3D);

  // Compute the sun from current store values. Pure + trivial cost, so safe each render.
  const sun = useMemo(
    () => computeSun({ timeHours: sunTimeHours, azimuthDeg: sunAzimuthDeg, directionOverride: sunDirectionOverride }),
    [sunTimeHours, sunAzimuthDeg, sunDirectionOverride]
  );

  // The directional light's shadow camera is centred on its target. We move that target onto
  // the plan centroid every frame (cheap) so the shadow frustum always covers the house —
  // otherwise a house drawn away from the origin would fall outside the shadow bounds and
  // cast no shadow at all.
  const lightRef = useRef<THREE.DirectionalLight>(null);
  const targetRef = useRef<THREE.Object3D>(null);
  useFrame(() => {
    const light = lightRef.current;
    const target = targetRef.current;
    if (!light || !target) return;
    const cx = planCentroid3D?.x ?? 0;
    const cz = planCentroid3D?.z ?? 0;
    target.position.set(cx, 0, cz);
    // Position the light relative to the target so the sun stays at its modelled direction
    // no matter where the house sits.
    light.position.set(cx + sun.position[0], sun.position[1], cz + sun.position[2]);
    light.target = target;
  });

  // Ambient/hemisphere dim toward night so the day/night arc actually reads. At night we
  // keep a soft moonlit floor (cool blue) instead of crushing to black, so the scene stays
  // navigable and clearly reads as "night" rather than "lights off".
  const ambientIntensity = sun.isNight ? 0.12 : 0.18 + 0.12 * (sun.intensity / 3.2);
  const hemiIntensity = sun.isNight ? 0.22 : 0.4;
  // A faint cool "moon" key light at night gives surfaces some shape/shadow after sunset.
  const moonIntensity = sun.isNight ? 0.35 : 0;
  const hemiSkyColor = sun.isNight ? '#3a4a78' : sun.skyTopColor;

  return (
    <>
      {/* Sky dome — the sun's position drives its colour/gradient, so the sky and the light
          always agree. Replaces the old flat background colour with a real gradient. */}
      <Sky sunPosition={sun.position} turbidity={8} rayleigh={2} mieCoefficient={0.005} mieDirectionalG={0.8} />

      {/* Fog tracks the horizon colour so dusk feels warm/hazy and night feels deep. */}
      <fog attach="fog" args={[sun.skyHorizonColor, 40, 120]} />

      {/* Warm key light (the sun) — casts the scene's shadows and streams through windows. */}
      <object3D ref={targetRef} />
      <directionalLight
        ref={lightRef}
        intensity={sun.intensity}
        color={sun.color}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={0.5}
        shadow-camera-far={120}
        shadow-camera-left={-40}
        shadow-camera-right={40}
        shadow-camera-top={40}
        shadow-camera-bottom={-40}
        shadow-bias={-0.0001}
      />

      {/* Sky/ground bounce + a gentle ambient floor so nothing is crushed to black. */}
      <hemisphereLight args={[hemiSkyColor, '#9a8366', hemiIntensity]} />
      <ambientLight intensity={ambientIntensity} />

      {/* Cool moonlight after sunset — high and soft, so night has shape without daylight. */}
      <directionalLight
        intensity={moonIntensity}
        color="#aebfd9"
        position={[12, 30, -18]}
      />

      {/*
       * Procedural image-based lighting. Rendered a single time (frames={1}) at a tiny
       * resolution, then reused — negligible ongoing cost. The panels act like softboxes:
       * a big neutral one overhead, a cool one on one side and a warm one on the other,
       * which gives surfaces a believable, slightly directional sheen.
       */}
      <Environment resolution={128} frames={1} background={false}>
        <Lightformer
          form="rect"
          intensity={2.2}
          color="#ffffff"
          position={[0, 9, 0]}
          rotation={[Math.PI / 2, 0, 0]}
          scale={[12, 12, 1]}
        />
        <Lightformer
          form="rect"
          intensity={0.9}
          color="#cfe0ff"
          position={[-9, 4, 5]}
          rotation={[0, Math.PI / 3, 0]}
          scale={[7, 7, 1]}
        />
        <Lightformer
          form="rect"
          intensity={0.8}
          color="#ffe7c7"
          position={[9, 4, -5]}
          rotation={[0, -Math.PI / 3, 0]}
          scale={[7, 7, 1]}
        />
      </Environment>
    </>
  );
};
