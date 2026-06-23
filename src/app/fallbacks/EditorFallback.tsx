// src/app/fallbacks/EditorFallback.tsx

import React from 'react';

export const EditorFallback: React.FC<{ error: Error; reset: () => void }> = ({ error, reset }) => (
  <div className="flex flex-col items-center justify-center h-full bg-neutral-900 text-white p-8" role="alert" aria-live="assertive">
    <h2 className="text-xl font-semibold mb-2">Editor encountered an error</h2>
    <p className="text-neutral-400 mb-4 text-center max-w-md">
      {error.message || 'An unexpected error occurred in the floor plan editor.'}
    </p>
    <div className="flex gap-3">
      <button onClick={reset} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md" aria-label="Retry loading the editor">Try Again</button>
      <button onClick={() => window.location.reload()} className="px-4 py-2 bg-neutral-700 hover:bg-neutral-600 rounded-md" aria-label="Reload the page">Reload Page</button>
    </div>
  </div>
);
