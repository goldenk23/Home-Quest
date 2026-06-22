import React from 'react';
import { useAppStore } from '../store';

// Import the feature components you want to test here
import { SnappingTestSandbox } from '../domains/editor/components/SnappingTestSandbox';
import { EditorScreen } from '../domains/editor/components/EditorScreen';
import { ViewerCanvas } from '../domains/viewer/components/ViewerCanvas';
import { ErrorBoundary } from '../components/ErrorBoundary';

export const SandboxView: React.FC = () => {
  const { featureFlags, activeTool, setActiveTool } = useAppStore();

  return (
    <div className="sandbox-container" style={{ padding: '2rem', minHeight: '100vh', backgroundColor: '#f0f0f0' }}>
      <header style={{ borderBottom: '1px solid #ccc', paddingBottom: '1rem', marginBottom: '2rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#333' }}>Developer Sandbox</h1>
        <p style={{ color: '#666', marginTop: '0.5rem' }}>
          Use this isolated environment to test individual features, components, and algorithms.
        </p>
      </header>

      <main style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        <section style={{ padding: '1.5rem', backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <h2 style={{ fontSize: '1.2rem', marginTop: 0 }}>Feature Flag Test</h2>
          {featureFlags.showDebugGrid ? (
            <div style={{ padding: '1rem', backgroundColor: '#e0f7fa', color: '#006064', border: '1px solid #b2ebf2', borderRadius: '4px' }}>
              The <strong>showDebugGrid</strong> flag is currently ON.
            </div>
          ) : (
            <div style={{ padding: '1rem', backgroundColor: '#ffebee', color: '#c62828', border: '1px solid #ffcdd2', borderRadius: '4px' }}>
              The <strong>showDebugGrid</strong> flag is currently OFF.
            </div>
          )}
        </section>

        {/* 
          INSTRUCTIONS:
          Add a new <section> per feature you want to visualize/check in isolation.
        */}

        <section style={{ padding: '1.5rem', backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <h2 style={{ fontSize: '1.2rem', marginTop: 0, marginBottom: '0.5rem' }}>Snapping Algorithm Visualizer</h2>
          <p style={{ color: '#666', marginTop: 0, marginBottom: '1rem', fontSize: '0.9rem' }}>
            Move your cursor across the grid. The black dot is the raw position, the red dot is
            the snapped result. Toggle grid and endpoint snapping to see how the pipeline behaves.
          </p>
          <SnappingTestSandbox />
        </section>

        <section style={{ padding: '1.5rem', backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <h2 style={{ fontSize: '1.2rem', marginTop: 0, marginBottom: '1rem' }}>2D Editor & 3D Viewer Integration Test</h2>
          
          <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <strong>Active Tool:</strong>
            <button 
              style={{ padding: '0.5rem 1rem', background: activeTool === 'select' ? '#3b82f6' : '#e5e7eb', color: activeTool === 'select' ? 'white' : 'black', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
              onClick={() => setActiveTool('select')}
            >
              Select
            </button>
            <button 
              style={{ padding: '0.5rem 1rem', background: activeTool === 'wall' ? '#3b82f6' : '#e5e7eb', color: activeTool === 'wall' ? 'white' : 'black', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
              onClick={() => setActiveTool('wall')}
            >
              Draw Wall
            </button>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', marginLeft: '1rem', cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                checked={useAppStore(s => s.isChainModeEnabled)} 
                onChange={(e) => useAppStore.getState().setChainMode(e.target.checked)}
              />
              <span style={{ fontSize: '0.9rem', color: '#444' }}>Continuous Drawing (Chain Mode)</span>
            </label>
            <span style={{ fontSize: '0.85rem', color: '#666', marginLeft: '1rem' }}>
              (Click to start wall, click to end. Watch the 3D viewer update instantly!)
            </span>
          </div>

          <div style={{ display: 'flex', gap: '1rem', height: '600px' }}>
            <ErrorBoundary>
              <div style={{ flex: 1, border: '1px solid #ccc', borderRadius: '4px', overflow: 'hidden' }}>
                <EditorScreen />
              </div>
            </ErrorBoundary>
            <ErrorBoundary>
              <div style={{ flex: 1, border: '1px solid #ccc', borderRadius: '4px', overflow: 'hidden' }}>
                <ViewerCanvas />
              </div>
            </ErrorBoundary>
          </div>
        </section>

      </main>
    </div>
  );
};

