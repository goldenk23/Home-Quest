// src/domains/viewer/hooks/useSafeAssetLoader.ts

import React, { useState, useMemo } from 'react';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { AssetLoadError } from '@/utils/errors';
import { captureException } from '@/app/monitoring';

interface AssetLoadState {
  model: THREE.Group | null;
  isLoading: boolean;
  error: AssetLoadError | null;
  retry: () => void;
}

/** Safe wrapper around useGLTF: returns an error state + retry instead of crashing. */
export function useSafeAssetLoader(path: string): AssetLoadState {
  const [retryCount, setRetryCount] = useState(0);
  const retry = () => setRetryCount((c) => c + 1);

  try {
    const { scene } = useGLTF(path);
    const model = useMemo(() => {
      const clone = scene.clone(true);
      clone.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.castShadow = true;
          child.receiveShadow = true;
        }
      });
      return clone as THREE.Group;
    }, [scene, retryCount]);
    return { model, isLoading: false, error: null, retry };
  } catch (e) {
    const assetError = new AssetLoadError(path, e instanceof Error ? e : undefined);
    captureException(assetError, { level: 'error', tags: { error_code: assetError.code } });
    return { model: null, isLoading: false, error: assetError, retry };
  }
}

/** Semi-transparent wireframe box shown when a model fails to load. */
export const AssetPlaceholder: React.FC<{ width: number; depth: number; height?: number }> = ({ width, depth, height = 80 }) => {
  const CM_TO_M = 0.01;
  return (
    <mesh>
      <boxGeometry args={[width * CM_TO_M, height * CM_TO_M, depth * CM_TO_M]} />
      <meshStandardMaterial color="#ff6b6b" transparent opacity={0.4} wireframe />
    </mesh>
  );
};
