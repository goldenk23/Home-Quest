import React, { useState } from 'react';
import { useAppStore } from '../store';
import { SnappingTestSandbox } from '../domains/editor/components/SnappingTestSandbox';
import { EditorScreen } from '../domains/editor/components/EditorScreen';
import { ViewerCanvas } from '../domains/viewer/components/ViewerCanvas';
import { VastuPanel } from '../domains/vastu/components/VastuPanel';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { FURNITURE_CATALOG_IDS, getCatalogEntry } from '../domains/viewer/hooks/useAssetLoader';
import { loadSampleHouse } from '../domains/editor/services/samplePlan';
import type { RoomType } from '../types/editor';

const ROOM_TYPES: RoomType[] = [
  'living', 'bedroom', 'kitchen', 'bathroom', 'puja', 'study',
  'dining', 'storage', 'garage', 'balcony', 'entrance', 'corridor', 'custom',
];

// ---- small styled helpers -------------------------------------------------

const btn = (active: boolean, accent = '#3b82f6'): React.CSSProperties => ({
  padding: '0.45rem 0.9rem',
  background: active ? accent : '#e5e7eb',
  color: active ? '#fff' : '#1f2937',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
  fontSize: '0.85rem',
  fontWeight: 600,
  transition: 'background 0.15s',
});

const Card: React.FC<{ title: string; children: React.ReactNode; right?: React.ReactNode }> = ({ title, children, right }) => (
  <section style={{ padding: '1rem', background: '#fff', borderRadius: '10px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
      <h2 style={{ fontSize: '0.95rem', margin: 0, color: '#111827' }}>{title}</h2>
      {right}
    </div>
    {children}
  </section>
);

const Row: React.FC<{ children: React.ReactNode; label?: string }> = ({ children, label }) => (
  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
    {label && <strong style={{ fontSize: '0.8rem', color: '#6b7280', minWidth: '70px' }}>{label}</strong>}
    {children}
  </div>
);

// ---- Rooms panel: assign room types so Vastu scoring is meaningful ---------

const RoomsPanel: React.FC = () => {
  const rooms = useAppStore((s) => s.rooms);
  const updateRoom = useAppStore((s) => s.updateRoom);
  const roomList = Object.values(rooms);

  if (roomList.length === 0) {
    return <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: 0 }}>No rooms yet. Close a loop of walls (or load the sample house).</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {roomList.map((room) => (
        <div key={room.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', fontSize: '0.85rem' }}>
          <span style={{ color: '#475569' }}>{room.label}</span>
          <select
            value={room.roomType}
            onChange={(e) => updateRoom(room.id, { roomType: e.target.value as RoomType })}
            style={{ padding: '3px 6px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem' }}
          >
            {ROOM_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
};

// ---- main view ------------------------------------------------------------

export const SandboxView: React.FC = () => {
  const activeTool = useAppStore((s) => s.activeTool);
  const setActiveTool = useAppStore((s) => s.setActiveTool);
  const isChainModeEnabled = useAppStore((s) => s.isChainModeEnabled);
  const setChainMode = useAppStore((s) => s.setChainMode);
  const furnitureCatalogId = useAppStore((s) => s.furnitureCatalogId);
  const setFurnitureCatalogId = useAppStore((s) => s.setFurnitureCatalogId);
  const showVastuOverlay2D = useAppStore((s) => s.showVastuOverlay2D);
  const showVastuOverlay3D = useAppStore((s) => s.showVastuOverlay3D);
  const toggleVastuOverlay2D = useAppStore((s) => s.toggleVastuOverlay2D);
  const toggleVastuOverlay3D = useAppStore((s) => s.toggleVastuOverlay3D);
  const cameraMode = useAppStore((s) => s.cameraMode);
  const setCameraMode = useAppStore((s) => s.setCameraMode);

  const selectedIds = useAppStore((s) => s.selectedIds);
  const furniture = useAppStore((s) => s.furniture);
  const walls = useAppStore((s) => s.walls);
  const rotateFurniture = useAppStore((s) => s.rotateFurniture);
  const removeFurniture = useAppStore((s) => s.removeFurniture);
  const removeWall = useAppStore((s) => s.removeWall);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const clearAll = useAppStore((s) => s.clearAll);

  const [showSnapTest, setShowSnapTest] = useState(false);
  const [isWalking, setIsWalking] = useState(false);

  // Track pointer-lock so we can show/hide the "click to walk" prompt.
  React.useEffect(() => {
    const onChange = () => setIsWalking(Boolean(document.pointerLockElement));
    document.addEventListener('pointerlockchange', onChange);
    return () => document.removeEventListener('pointerlockchange', onChange);
  }, []);

  const selectedFurnitureId = selectedIds.find((id) => furniture[id]);
  const selectedWallId = selectedIds.find((id) => walls[id]);
  const selectionLabel = selectedFurnitureId
    ? getCatalogEntry(furniture[selectedFurnitureId].catalogId).label
    : selectedWallId
      ? 'Wall'
      : 'nothing selected';

  const rotateSelected = (deltaDeg: number) => {
    selectedIds.forEach((id) => {
      const item = furniture[id];
      if (item) rotateFurniture(id, item.rotation + (deltaDeg * Math.PI) / 180);
    });
  };

  const deleteSelected = () => {
    const state = useAppStore.getState();
    selectedIds.forEach((id) => {
      if (state.walls[id]) removeWall(id);
      if (state.furniture[id]) removeFurniture(id);
    });
    clearSelection();
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f1f5f9', padding: '1.25rem' }}>
      <header style={{ marginBottom: '1rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.4rem', color: '#0f172a' }}>🏡 Home Quest — Interactive Playground</h1>
        <p style={{ color: '#64748b', margin: '0.25rem 0 0', fontSize: '0.9rem' }}>
          Every implemented feature (through Installment 3) is testable here. Start with <strong>Load Sample House</strong>, or draw your own.
        </p>
      </header>

      {/* Toolbar */}
      <Card title="🧰 Tools & Controls">
        <Row label="Tool">
          <button style={btn(activeTool === 'select')} onClick={() => setActiveTool('select')}>🖱️ Select</button>
          <button style={btn(activeTool === 'wall')} onClick={() => setActiveTool('wall')}>📏 Draw Wall</button>
          <button style={btn(activeTool === 'furniture')} onClick={() => setActiveTool('furniture')}>🛋️ Furniture</button>
          <label style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: '0.5rem', fontSize: '0.82rem', color: '#374151', cursor: 'pointer' }}>
            <input type="checkbox" checked={isChainModeEnabled} onChange={(e) => setChainMode(e.target.checked)} />
            Chain mode
          </label>
        </Row>

        {activeTool === 'furniture' && (
          <Row label="Catalog">
            {FURNITURE_CATALOG_IDS.map((id) => (
              <button
                key={id}
                style={btn(furnitureCatalogId === id, '#0ea5e9')}
                onClick={() => setFurnitureCatalogId(id)}
              >
                {getCatalogEntry(id).label}
              </button>
            ))}
          </Row>
        )}

        <Row label="Selection">
          <button style={{ ...btn(false), opacity: selectedFurnitureId ? 1 : 0.5 }} disabled={!selectedFurnitureId} onClick={() => rotateSelected(-15)}>⟲ Rotate −15°</button>
          <button style={{ ...btn(false), opacity: selectedFurnitureId ? 1 : 0.5 }} disabled={!selectedFurnitureId} onClick={() => rotateSelected(15)}>⟳ Rotate +15°</button>
          <button style={{ ...btn(false, '#ef4444'), opacity: selectedIds.length ? 1 : 0.5 }} disabled={!selectedIds.length} onClick={deleteSelected}>🗑️ Delete</button>
          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
            Selected: <strong>{selectionLabel}</strong>
            {selectedWallId && !selectedFurnitureId ? ' (rotation applies to furniture)' : ''}
          </span>
        </Row>

        <Row label="Overlays">
          <button style={btn(showVastuOverlay2D, '#10b981')} onClick={toggleVastuOverlay2D}>Vastu 2D</button>
          <button style={btn(showVastuOverlay3D, '#10b981')} onClick={toggleVastuOverlay3D}>Vastu 3D</button>
        </Row>

        <Row label="Camera">
          <button style={btn(cameraMode === 'orbit', '#f59e0b')} onClick={() => setCameraMode('orbit')}>🚁 Orbit</button>
          <button style={btn(cameraMode === 'firstPerson', '#f59e0b')} onClick={() => setCameraMode('firstPerson')}>🚶 First-Person (WASD)</button>
        </Row>

        <Row label="Plan">
          <button style={btn(false, '#8b5cf6')} onClick={loadSampleHouse}>🏠 Load Sample House</button>
          <button style={btn(false, '#ef4444')} onClick={() => { clearAll(); }}>♻️ Clear All</button>
        </Row>
      </Card>

      {/* Editor + Viewer */}
      <div style={{ display: 'flex', gap: '1rem', height: '78vh', minHeight: '600px', margin: '1rem 0' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={badge}>2D Editor</div>
          <ErrorBoundary>
            <div style={canvasFrame}>
              <EditorScreen />
            </div>
          </ErrorBoundary>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={badge}>3D Viewer {cameraMode === 'firstPerson' ? '— click to enter, then HOLD mouse to walk' : ''}</div>
          <ErrorBoundary>
            <div style={{ ...canvasFrame, position: 'relative' }}>
              <ViewerCanvas />
              {cameraMode === 'firstPerson' && !isWalking && (
                <div style={fpOverlay}>
                  <div style={fpCard}>
                    <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>🚶 Click here to start walking</div>
                    <div style={{ fontSize: '0.85rem', opacity: 0.9, marginTop: '8px', lineHeight: 1.5 }}>
                      Then <strong>hold the left mouse button</strong> to walk forward.<br />
                      Move mouse to look · right mouse = back · scroll = zoom · <kbd>Shift</kbd> = run · <kbd>Esc</kbd> = exit
                    </div>
                  </div>
                </div>
              )}
            </div>
          </ErrorBoundary>
        </div>
      </div>

      {/* Bottom panels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        <Card title="📋 Rooms">
          <RoomsPanel />
        </Card>

        <VastuPanel />

        <Card title="⌨️ How to test">
          <ul style={{ margin: 0, paddingLeft: '1.1rem', color: '#475569', fontSize: '0.82rem', lineHeight: 1.7 }}>
            <li><strong>Draw Wall:</strong> click to start, click to end. Hold <kbd>Shift</kbd> for angle snap. <kbd>Esc</kbd> / right-click cancels.</li>
            <li><strong>Chain mode:</strong> keeps drawing connected walls.</li>
            <li><strong>Rooms:</strong> close a loop → auto-detected with area. Set its type in the Rooms panel to drive Vastu.</li>
            <li><strong>Furniture:</strong> pick a catalog item, click to place. Overlapping pieces turn <span style={{ color: '#ef4444', fontWeight: 700 }}>red</span> (collision).</li>
            <li><strong>Move:</strong> with the Select tool, <strong>drag a piece of furniture or a wall</strong> to reposition just that component (a live readout shows distance + angle); drag empty space to move the whole diagram.</li>
            <li><strong>Smart align:</strong> on drop, furniture snaps to the grid and to the nearest 90°, and near-straight walls auto-straighten to keep right angles — so the house won't drift into a random shape.</li>
            <li><strong>Rotate/Delete:</strong> select a furniture piece, then <kbd>R</kbd>/<kbd>Shift+R</kbd> or the Rotate buttons; <kbd>Del</kbd> removes the selection (walls or furniture). Rotation applies to furniture only.</li>
            <li><strong>Pan/zoom:</strong> with the Select tool, <strong>drag empty space to move the diagram</strong> around (or Alt/middle-drag in any tool); scroll wheel zooms.</li>
            <li><strong>3D:</strong> updates live. Orbit to inspect, or First-Person to walk through the house.</li>
            <li><strong>Walk (First-Person):</strong> click the 3D view, then <strong>hold the left mouse to walk forward</strong> and steer with the mouse (right mouse = back). WASD/arrows also work; <kbd>Shift</kbd> sprints; <strong>scroll to zoom</strong>; <kbd>Esc</kbd> exits.</li>
            <li><strong>Smart walking:</strong> you start standing in the middle of the largest room, and you can't walk through walls — the camera auto-slides along a wall instead of getting stuck or going dark.</li>
          </ul>
        </Card>
      </div>

      {/* Optional: snapping algorithm visualizer */}
      <div style={{ marginTop: '1rem' }}>
        <Card
          title="🧲 Snapping Algorithm Visualizer"
          right={<button style={btn(showSnapTest)} onClick={() => setShowSnapTest((v) => !v)}>{showSnapTest ? 'Hide' : 'Show'}</button>}
        >
          {showSnapTest ? (
            <SnappingTestSandbox />
          ) : (
            <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.85rem' }}>Isolated view of the raw → snapped pipeline. Click “Show” to open.</p>
          )}
        </Card>
      </div>
    </div>
  );
};

const badge: React.CSSProperties = {
  fontSize: '0.72rem',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: '#64748b',
  marginBottom: '4px',
};

const canvasFrame: React.CSSProperties = {
  flex: 1,
  border: '1px solid #cbd5e1',
  borderRadius: '8px',
  overflow: 'hidden',
  background: '#171717',
};

// Instruction overlay for first-person mode. pointerEvents: none so the click passes
// through to the 3D canvas (which requests pointer-lock).
const fpOverlay: React.CSSProperties = {
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(0,0,0,0.4)',
  pointerEvents: 'none',
};

const fpCard: React.CSSProperties = {
  background: 'rgba(15,23,42,0.9)',
  color: '#f8fafc',
  padding: '1.25rem 1.5rem',
  borderRadius: '10px',
  textAlign: 'center',
  maxWidth: '80%',
  border: '1px solid rgba(255,255,255,0.15)',
};
