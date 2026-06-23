// src/app/ResponsiveLayout.tsx

import React, { Suspense, lazy, useState } from 'react';
import { useResponsiveLayout } from './hooks/useResponsiveLayout';
import { LoadingSpinner } from '@/domains/shared/components/LoadingSpinner';
import { ErrorBoundary } from './ErrorBoundary';
import { EditorFallback } from './fallbacks/EditorFallback';
import { ViewerFallback } from './fallbacks/ViewerFallback';

const EditorScreen = lazy(() => import('@/domains/editor/components/EditorScreen').then((m) => ({ default: m.EditorScreen })));
const ViewerCanvas = lazy(() => import('@/domains/viewer/components/ViewerCanvas').then((m) => ({ default: m.ViewerCanvas })));
const VastuPanel = lazy(() => import('@/domains/vastu/components/VastuPanel').then((m) => ({ default: m.VastuPanel })));

export const ResponsiveLayout: React.FC = () => {
  const layout = useResponsiveLayout();
  const [activeTab, setActiveTab] = useState<'editor' | 'viewer'>('editor');

  if (layout.mode === 'desktop') {
    return (
      <div className="flex-1 flex">
        <section className="flex-1" aria-label="2D Floor Plan Editor">
          <ErrorBoundary level="domain" fallback={(e, r) => <EditorFallback error={e} reset={r} />}>
            <Suspense fallback={<LoadingSpinner label="Loading editor…" />}><EditorScreen /></Suspense>
          </ErrorBoundary>
        </section>
        <section className="flex-1" aria-label="3D Visualization">
          <ErrorBoundary level="domain" fallback={(e, r) => <ViewerFallback error={e} reset={r} />}>
            <Suspense fallback={<LoadingSpinner label="Loading viewer…" />}><ViewerCanvas /></Suspense>
          </ErrorBoundary>
        </section>
        <aside className="w-80 border-l border-neutral-700" aria-label="Vastu Analysis">
          <Suspense fallback={<LoadingSpinner label="Loading analysis…" />}><VastuPanel /></Suspense>
        </aside>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      <div className="flex border-b border-neutral-700" role="tablist" aria-label="View selector">
        <button role="tab" aria-selected={activeTab === 'editor'} aria-controls="editor-panel" onClick={() => setActiveTab('editor')}
          className={`flex-1 py-2 text-sm font-medium ${activeTab === 'editor' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-neutral-400'}`}>2D Editor</button>
        <button role="tab" aria-selected={activeTab === 'viewer'} aria-controls="viewer-panel" onClick={() => setActiveTab('viewer')}
          className={`flex-1 py-2 text-sm font-medium ${activeTab === 'viewer' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-neutral-400'}`}>3D View</button>
      </div>

      <div id="editor-panel" role="tabpanel" className={`flex-1 ${activeTab !== 'editor' ? 'hidden' : ''}`}>
        <Suspense fallback={<LoadingSpinner label="Loading editor…" />}><EditorScreen /></Suspense>
      </div>
      <div id="viewer-panel" role="tabpanel" className={`flex-1 ${activeTab !== 'viewer' ? 'hidden' : ''}`}>
        <Suspense fallback={<LoadingSpinner label="Loading viewer…" />}><ViewerCanvas /></Suspense>
      </div>

      {layout.panelPosition === 'bottom' && (
        <aside className="h-48 border-t border-neutral-700 overflow-y-auto" aria-label="Vastu Analysis">
          <Suspense fallback={<LoadingSpinner label="Loading analysis…" />}><VastuPanel /></Suspense>
        </aside>
      )}
    </div>
  );
};
