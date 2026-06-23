// src/app/fallbacks/ViewerFallback.tsx

import React from 'react';

export const ViewerFallback: React.FC<{ error: Error; reset: () => void }> = ({ error, reset }) => (
  <div className="flex flex-col items-center justify-center h-full bg-black text-white p-8" role="alert" aria-live="assertive">
    <h2 className="text-xl font-semibold mb-2">3D Viewer Error</h2>
    <p className="text-neutral-400 mb-4 text-center max-w-md">
      The 3D viewer failed to render — likely a WebGL or model-loading issue.
    </p>
    <p className="text-neutral-500 text-sm mb-4 font-mono">{error.message}</p>
    <button onClick={reset} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md">Retry</button>
  </div>
);
