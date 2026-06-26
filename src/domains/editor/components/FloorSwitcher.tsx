// src/domains/editor/components/FloorSwitcher.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';

const tab = (active: boolean): React.CSSProperties => ({
  padding: '0.4rem 0.8rem',
  background: active ? '#0ea5e9' : '#e5e7eb',
  color: active ? '#fff' : '#1f2937',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
  fontSize: '0.82rem',
  fontWeight: 600,
});

const ghost = (accent: string): React.CSSProperties => ({
  padding: '0.4rem 0.7rem',
  background: '#fff',
  color: accent,
  border: `1px solid ${accent}`,
  borderRadius: '6px',
  cursor: 'pointer',
  fontSize: '0.82rem',
  fontWeight: 600,
});

/**
 * Storey selector for the toolbar. Switching a floor swaps the editor's working set, so the
 * 2D editor always shows exactly one storey while the 3D view stacks them all. Floors are
 * listed top-down (highest storey first) so the list reads like a building elevation.
 */
export const FloorSwitcher: React.FC = () => {
  const floors = useAppStore(useShallow((s) => s.floors));
  const activeFloorId = useAppStore((s) => s.activeFloorId);
  const setActiveFloor = useAppStore((s) => s.setActiveFloor);
  const addFloor = useAppStore((s) => s.addFloor);
  const removeFloor = useAppStore((s) => s.removeFloor);
  const renameFloor = useAppStore((s) => s.renameFloor);

  // Highest storey first.
  const ordered = [...floors].sort((a, b) => b.elevationCm - a.elevationCm);

  return (
    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
      {ordered.map((floor) => {
        const isActive = floor.id === activeFloorId;
        return (
          <span key={floor.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            {isActive ? (
              <input
                value={floor.name}
                onChange={(e) => renameFloor(floor.id, e.target.value)}
                style={{
                  ...tab(true),
                  width: `${Math.max(8, floor.name.length + 1)}ch`,
                  border: '1px solid #0284c7',
                }}
                aria-label="Active floor name"
              />
            ) : (
              <button style={tab(false)} onClick={() => setActiveFloor(floor.id)} title={`Switch to ${floor.name}`}>
                {floor.name}
              </button>
            )}
          </span>
        );
      })}

      <button style={ghost('#16a34a')} onClick={() => addFloor()} title="Add a storey on top">
        ＋ Add Floor
      </button>
      <button
        style={{ ...ghost('#ef4444'), opacity: floors.length > 1 ? 1 : 0.5 }}
        disabled={floors.length <= 1}
        onClick={() => removeFloor(activeFloorId)}
        title="Remove the current storey"
      >
        🗑️ Remove Floor
      </button>
      <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
        Edit one storey at a time; the 3D view stacks them all.
      </span>
    </div>
  );
};
