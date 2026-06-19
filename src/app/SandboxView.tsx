import React from 'react';
import { useAppStore } from '../store';

// Import the feature components you want to test here
import { SnappingTestSandbox } from '../domains/editor/components/SnappingTestSandbox';

export const SandboxView: React.FC = () => {
  const { featureFlags } = useAppStore();

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
          Uncomment and replace the code below to test your new features!
        */}
        
        <section style={{ padding: '1.5rem', backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <h2 style={{ fontSize: '1.2rem', marginTop: 0, marginBottom: '1rem' }}>Geometry & Snapping Test</h2>
          <SnappingTestSandbox />
        </section>

      </main>
    </div>
  );
};
