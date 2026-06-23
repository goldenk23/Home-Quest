// src/app/fallbacks/VastuFallback.tsx

import React from 'react';

export const VastuFallback: React.FC<{ error: Error; reset: () => void }> = ({ reset }) => (
  <div className="p-4 bg-yellow-900/20 border border-yellow-700 rounded-md" role="alert">
    <p className="text-yellow-300 text-sm">Vastu analysis temporarily unavailable.</p>
    <button onClick={reset} className="text-yellow-400 underline text-xs mt-1">Retry</button>
  </div>
);
