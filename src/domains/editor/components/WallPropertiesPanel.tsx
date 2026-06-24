// src/domains/editor/components/WallPropertiesPanel.tsx

import React from 'react';
import { useAppStore } from '@/store';

// Clamp ranges mirror the store guard in `storeGuards.ts` (height 0–2000, thickness 0–200 cm).
const HEIGHT_MIN = 50;
const HEIGHT_MAX = 600;
const THICK_MIN = 5;
const THICK_MAX = 100;

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/**
 * Floating in-canvas panel for editing the geometry of the currently selected wall.
 *
 * Appears in the top-right of the 2D editor when a wall is selected with the Select tool,
 * letting the user adjust the wall's height and thickness (in cm) and toggle whether it's
 * load-bearing. Changes update the 3D model live; one undo step is recorded per edit
 * gesture via the history transaction API. Renders nothing when no wall is selected.
 */
export const WallPropertiesPanel: React.FC = () => {
  const selectedIds = useAppStore((s) => s.selectedIds);
  const walls = useAppStore((s) => s.walls);
  const updateWall = useAppStore((s) => s.updateWall);
  const activeTool = useAppStore((s) => s.activeTool);

  const selectedWallId = selectedIds.find((id) => walls[id]);
  const wall = selectedWallId ? walls[selectedWallId] : null;

  // Only the Select tool exposes wall geometry editing, so painting / drawing walls doesn't
  // pop this panel open over those workflows.
  if (activeTool !== 'select' || !wall) return null;

  const wallId = wall.id;

  // Live update during a drag/typing gesture; history is bracketed by the transaction API so
  // a whole slider drag collapses into a single undo step.
  const begin = () => useAppStore.getState().beginTransaction();
  const commit = () => useAppStore.getState().commitTransaction('Edit Wall');

  const setHeight = (cm: number) => updateWall(wallId, { height: clamp(Math.round(cm), 1, 2000) });
  const setThickness = (cm: number) => updateWall(wallId, { thickness: clamp(Math.round(cm), 1, 200) });

  return (
    <div style={panel}>
      <div style={heading}>Wall properties</div>

      {/* Height */}
      <label style={label} htmlFor="wall-height-range">Height: {wall.height} cm</label>
      <div style={row}>
        <input
          id="wall-height-range"
          type="range"
          min={HEIGHT_MIN}
          max={HEIGHT_MAX}
          step={1}
          value={clamp(wall.height, HEIGHT_MIN, HEIGHT_MAX)}
          onMouseDown={begin}
          onTouchStart={begin}
          onChange={(e) => setHeight(Number(e.target.value))}
          onMouseUp={commit}
          onTouchEnd={commit}
          style={range}
        />
        <input
          type="number"
          min={1}
          max={2000}
          value={wall.height}
          onFocus={begin}
          onChange={(e) => setHeight(Number(e.target.value))}
          onBlur={commit}
          style={num}
          aria-label="Wall height in centimeters"
        />
      </div>

      {/* Thickness */}
      <label style={label} htmlFor="wall-thickness-range">Thickness: {wall.thickness} cm</label>
      <div style={row}>
        <input
          id="wall-thickness-range"
          type="range"
          min={THICK_MIN}
          max={THICK_MAX}
          step={1}
          value={clamp(wall.thickness, THICK_MIN, THICK_MAX)}
          onMouseDown={begin}
          onTouchStart={begin}
          onChange={(e) => setThickness(Number(e.target.value))}
          onMouseUp={commit}
          onTouchEnd={commit}
          style={range}
        />
        <input
          type="number"
          min={1}
          max={200}
          value={wall.thickness}
          onFocus={begin}
          onChange={(e) => setThickness(Number(e.target.value))}
          onBlur={commit}
          style={num}
          aria-label="Wall thickness in centimeters"
        />
      </div>

      {/* Load-bearing (affects Vastu) */}
      <label style={checkboxRow}>
        <input
          type="checkbox"
          checked={wall.isLoadBearing}
          onChange={(e) => {
            const next = e.target.checked;
            useAppStore.getState().recordHistory('Toggle Load-Bearing', () =>
              updateWall(wallId, { isLoadBearing: next })
            );
          }}
        />
        Load-bearing wall
      </label>
    </div>
  );
};

const panel: React.CSSProperties = {
  position: 'absolute',
  top: 12,
  right: 12,
  width: 220,
  padding: '12px',
  background: 'rgba(255,255,255,0.97)',
  borderRadius: '10px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
  border: '1px solid #e2e8f0',
  zIndex: 5,
};

const heading: React.CSSProperties = {
  fontSize: '0.72rem',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: '#94a3b8',
  marginBottom: '10px',
};

const label: React.CSSProperties = {
  display: 'block',
  fontSize: '0.78rem',
  fontWeight: 600,
  color: '#334155',
  margin: '6px 0 4px',
};

const row: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  marginBottom: '4px',
};

const range: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
};

const num: React.CSSProperties = {
  width: 56,
  padding: '4px 6px',
  borderRadius: '6px',
  border: '1px solid #cbd5e1',
  fontSize: '0.8rem',
  boxSizing: 'border-box',
};

const checkboxRow: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  marginTop: '10px',
  fontSize: '0.8rem',
  color: '#334155',
  cursor: 'pointer',
};
