import React, { useState } from 'react';
import { useAppStore } from '../../../store';
import type { FeatureFlags } from '../../../store/slices/settingsSlice';

export const DevToolsPanel: React.FC = () => {
  const { devMode, featureFlags, toggleFeatureFlag, activeView, setActiveView } = useAppStore();
  const [isExpanded, setIsExpanded] = useState(false);

  if (!devMode) return null;

  return (
    <div 
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        zIndex: 9999,
        backgroundColor: '#1e1e1e',
        color: '#fff',
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
        fontFamily: 'monospace',
        width: isExpanded ? '300px' : 'auto',
        transition: 'width 0.2s ease-in-out',
      }}
    >
      <div 
        style={{
          padding: '10px 15px',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: isExpanded ? '1px solid #333' : 'none',
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <strong>🛠 Dev Tools</strong>
        <span style={{ fontSize: '12px', color: '#888' }}>{isExpanded ? '▼' : '▲'}</span>
      </div>

      {isExpanded && (
        <div style={{ padding: '15px', display: 'flex', flexDirection: 'column', gap: '15px' }}>
          
          {/* View Toggle */}
          <div>
            <div style={{ marginBottom: '8px', fontSize: '12px', color: '#aaa', textTransform: 'uppercase', letterSpacing: '1px' }}>
              Environment
            </div>
            <div style={{ display: 'flex', gap: '5px' }}>
              <button
                onClick={() => setActiveView('app')}
                style={{
                  flex: 1,
                  padding: '6px',
                  backgroundColor: activeView === 'app' ? '#3b82f6' : '#333',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                App
              </button>
              <button
                onClick={() => setActiveView('sandbox')}
                style={{
                  flex: 1,
                  padding: '6px',
                  backgroundColor: activeView === 'sandbox' ? '#10b981' : '#333',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Sandbox
              </button>
            </div>
          </div>

          {/* Feature Flags */}
          <div>
            <div style={{ marginBottom: '8px', fontSize: '12px', color: '#aaa', textTransform: 'uppercase', letterSpacing: '1px' }}>
              Feature Flags
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {(Object.keys(featureFlags) as Array<keyof FeatureFlags>).map((flag) => (
                <label key={flag} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
                  <input
                    type="checkbox"
                    checked={featureFlags[flag]}
                    onChange={() => toggleFeatureFlag(flag)}
                    style={{ cursor: 'pointer' }}
                  />
                  {flag}
                </label>
              ))}
            </div>
          </div>

        </div>
      )}
    </div>
  );
};
