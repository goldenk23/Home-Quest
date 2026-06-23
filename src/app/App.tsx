// src/app/App.tsx
//
// The hardened, three-pane application shell from the implementation guide (Parts 21 & 24).
// This composes error boundaries, lazy-loaded domains, accessibility primitives, and the
// undo/redo + keyboard-editing engine hooks. The default export in `src/App.tsx` currently
// renders the interactive SandboxView used for manual testing; this component is the
// production layout and can be swapped in as the root render target.

import React, { Suspense, lazy } from 'react';
import { ErrorBoundary } from './ErrorBoundary';
import { EditorFallback } from './fallbacks/EditorFallback';
import { ViewerFallback } from './fallbacks/ViewerFallback';
import { VastuFallback } from './fallbacks/VastuFallback';
import { LoadingSpinner } from '@/domains/shared/components/LoadingSpinner';
import { ScreenReaderAnnouncer } from '@/domains/shared/components/ScreenReaderAnnouncer';
import { SkipLinks } from '@/domains/shared/components/SkipLinks';
import { Toolbar } from '@/domains/shared/components/Toolbar';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useKeyboardEditor } from '@/domains/editor/hooks/useKeyboardEditor';

// EditorScreen mounts useRoomDetection + useVastuAnalysis so the model stays live.
const EditorScreen = lazy(() =>
  import('@/domains/editor/components/EditorScreen').then((m) => ({ default: m.EditorScreen }))
);
const ViewerCanvas = lazy(() =>
  import('@/domains/viewer/components/ViewerCanvas').then((m) => ({ default: m.ViewerCanvas }))
);
const VastuPanel = lazy(() =>
  import('@/domains/vastu/components/VastuPanel').then((m) => ({ default: m.VastuPanel }))
);

export const App: React.FC = () => {
  // Engine hooks: undo/redo shortcuts and arrow-key nudging / delete.
  useKeyboardShortcuts();
  useKeyboardEditor();

  return (
    <ErrorBoundary
      level="global"
      fallback={(error, reset) => (
        <div className="flex items-center justify-center h-screen bg-neutral-950 text-white">
          <div className="text-center">
            <h1 className="text-2xl mb-4">Something went wrong</h1>
            <p className="text-neutral-400 mb-4">{error.message}</p>
            <button onClick={reset} className="px-4 py-2 bg-blue-600 rounded">Restart Application</button>
          </div>
        </div>
      )}
    >
      <SkipLinks />
      <ScreenReaderAnnouncer />
      <div className="h-screen flex flex-col">
        <header className="h-12 bg-neutral-800 border-b border-neutral-700 flex items-center" role="banner">
          <Toolbar />
        </header>
        <main className="flex-1 flex" role="main">
          <section id="editor-canvas" className="flex-1" aria-label="2D Floor Plan Editor">
            <ErrorBoundary level="domain" fallback={(e, r) => <EditorFallback error={e} reset={r} />}>
              <Suspense fallback={<LoadingSpinner label="Loading editor…" />}>
                <EditorScreen />
              </Suspense>
            </ErrorBoundary>
          </section>
          <section id="viewer-canvas" className="flex-1" aria-label="3D Visualization">
            <ErrorBoundary level="domain" fallback={(e, r) => <ViewerFallback error={e} reset={r} />}>
              <Suspense fallback={<LoadingSpinner label="Loading 3D viewer…" />}>
                <ViewerCanvas />
              </Suspense>
            </ErrorBoundary>
          </section>
          <aside id="vastu-panel" className="w-80" aria-label="Vastu Analysis">
            <ErrorBoundary level="domain" fallback={(e, r) => <VastuFallback error={e} reset={r} />}>
              <Suspense fallback={<LoadingSpinner label="Loading analysis…" />}>
                <VastuPanel />
              </Suspense>
            </ErrorBoundary>
          </aside>
        </main>
      </div>
    </ErrorBoundary>
  );
};
