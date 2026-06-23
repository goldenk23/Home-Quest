// src/domains/shared/components/SkipLinks.tsx

import React from 'react';

/** Keyboard "skip to…" links, hidden until focused. */
export const SkipLinks: React.FC = () => (
  <nav aria-label="Skip links" className="sr-only focus-within:not-sr-only focus-within:fixed focus-within:z-50 focus-within:top-0 focus-within:left-0">
    <ul className="flex gap-2 p-2 bg-blue-600">
      <li><a href="#editor-canvas" className="px-3 py-1 bg-white text-blue-600 rounded font-medium">Skip to Editor</a></li>
      <li><a href="#viewer-canvas" className="px-3 py-1 bg-white text-blue-600 rounded font-medium">Skip to 3D Viewer</a></li>
      <li><a href="#vastu-panel" className="px-3 py-1 bg-white text-blue-600 rounded font-medium">Skip to Vastu Analysis</a></li>
    </ul>
  </nav>
);
