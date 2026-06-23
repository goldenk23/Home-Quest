// src/domains/shared/components/ModelLoadingProgress.tsx

import React from 'react';
import { useProgress } from '@react-three/drei';

/** Overlay showing GLTF/texture load progress, driven by R3F's useProgress. */
export const ModelLoadingProgress: React.FC = () => {
  const { active, progress, item } = useProgress();
  if (!active) return null;
  const filename = item?.split('/').pop() ?? 'assets';

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 z-10" role="progressbar"
      aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100} aria-label={`Loading 3D assets: ${Math.round(progress)}%`}>
      <div className="w-64">
        <div className="flex justify-between text-sm text-neutral-400 mb-2">
          <span>Loading {filename}</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="h-2 bg-neutral-800 rounded-full overflow-hidden">
          <div className="h-full bg-blue-500 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
      </div>
    </div>
  );
};
