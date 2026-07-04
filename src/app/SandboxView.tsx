import React, { useState } from 'react';
import { useAppStore } from '../store';
import { SnappingTestSandbox } from '../domains/editor/components/SnappingTestSandbox';
import { EditorScreen } from '../domains/editor/components/EditorScreen';
import { FloorSwitcher } from '../domains/editor/components/FloorSwitcher';
import { ViewerCanvas } from '../domains/viewer/components/ViewerCanvas';
import { VastuPanel } from '../domains/vastu/components/VastuPanel';
import { VastuLegend } from '../domains/vastu/components/VastuLegend';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { FURNITURE_CATALOG_IDS, getCatalogEntry } from '../domains/viewer/hooks/useAssetLoader';
import { WALL_FINISHES, FLOOR_FINISHES, categoryOf } from '../domains/shared/materials/finishPalette';
import { useGlbWallDiscovery } from '../domains/shared/hooks/useGlbWallDiscovery';
import { kindsForFamily, getOpeningKind, type OpeningFamily } from '../domains/shared/openings/openingCatalog';
import { formatClock, azimuthLabel, dayPhase } from '../domains/viewer/services/sun';
import { loadSampleHouse } from '../domains/editor/services/samplePlan';
import { exportFloorPlan, importFloorPlan } from '../store/persistence/fileIO';
import { exportEditor2D, exportViewer3D, type ImageExportFormat } from '../store/persistence/imageExport';
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

// A color swatch button for the Paint tool's palette. Shows the finish color with a ring
// when selected; labels the finish name. Border adapts to light/dark swatches for contrast.
const Swatch: React.FC<{
  finish: { id: string; name: string; swatch: string };
  selected: boolean;
  onClick: () => void;
}> = ({ finish, selected, onClick }) => {
  // Light swatches need a dark border so they don't vanish on the white card.
  const isLight = finish.swatch.toLowerCase() > '#b0b0b0';
  return (
    <button
      onClick={onClick}
      title={finish.name}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '3px 8px 3px 3px',
        background: selected ? '#fef3c7' : '#f1f5f9',
        border: selected ? '2px solid #f59e0b' : `1px solid ${isLight ? '#cbd5e1' : 'transparent'}`,
        borderRadius: '6px',
        cursor: 'pointer',
        fontSize: '0.78rem',
        color: '#334155',
        fontWeight: selected ? 600 : 500,
        transition: 'border 0.12s, background 0.12s',
      }}
    >
      <span style={{ width: '18px', height: '18px', borderRadius: '4px', background: finish.swatch, border: '1px solid rgba(0,0,0,0.15)', flexShrink: 0 }} />
      {finish.name}
    </button>
  );
};

// A compact labelled number input (cm) for opening size overrides. Blank = use preset.
const NumInput: React.FC<{
  label: string;
  value: number | undefined;
  placeholder: number | undefined;
  onChange: (v: number | undefined) => void;
}> = ({ label, value, placeholder, onChange }) => (
  <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#475569' }}>
    {label}
    <input
      type="number"
      min={1}
      value={value ?? ''}
      placeholder={placeholder != null ? String(placeholder) : ''}
      onChange={(e) => {
        const t = e.target.value.trim();
        onChange(t === '' ? undefined : Math.max(1, Number(t)));
      }}
      style={{
        width: '64px',
        padding: '3px 6px',
        border: '1px solid #cbd5e1',
        borderRadius: '5px',
        fontSize: '0.78rem',
      }}
    />
  </label>
);

// ---- Rooms panel: assign room types so Vastu scoring is meaningful ---------

const RoomsPanel: React.FC = () => {
  const rooms = useAppStore((s) => s.rooms);
  const updateRoom = useAppStore((s) => s.updateRoom);
  const selectedIds = useAppStore((s) => s.selectedIds);
  const select = useAppStore((s) => s.select);
  const roomList = Object.values(rooms);

  if (roomList.length === 0) {
    return <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: 0 }}>No rooms yet. Close a loop of walls (or load the sample house).</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <p style={{ margin: '0 0 4px', fontSize: '0.78rem', color: '#94a3b8' }}>
        {roomList.length} room{roomList.length === 1 ? '' : 's'} detected. Click a row (or a box in the 2D editor) to select it, then set its type.
      </p>
      {roomList.map((room) => {
        const isSelected = selectedIds.includes(room.id);
        return (
          <div
            key={room.id}
            onClick={() => select([room.id])}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '8px',
              fontSize: '0.85rem',
              padding: '6px 8px',
              borderRadius: '6px',
              cursor: 'pointer',
              background: isSelected ? '#fff7ed' : '#f8fafc',
              border: isSelected ? '1px solid #f59e0b' : '1px solid transparent',
            }}
          >
            <span style={{ color: '#f59e0b', fontSize: '0.9rem', width: '12px' }}>{isSelected ? '◉' : ''}</span>
            <input
              type="text"
              value={room.label}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => updateRoom(room.id, { label: e.target.value })}
              style={{ flex: 1, minWidth: 0, padding: '3px 6px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem', color: '#475569' }}
              aria-label="Room name"
            />
            <select
              value={room.roomType}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => {
                const next = e.target.value as RoomType;
                useAppStore.getState().recordHistory('Set Room Type', () => updateRoom(room.id, { roomType: next }));
              }}
              style={{ padding: '3px 6px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem' }}
            >
              {ROOM_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        );
      })}
    </div>
  );
};

// ---- main view ------------------------------------------------------------

export const SandboxView: React.FC = () => {
  const activeTool = useAppStore((s) => s.activeTool);
  const setActiveTool = useAppStore((s) => s.setActiveTool);
  const isChainModeEnabled = useAppStore((s) => s.isChainModeEnabled);
  const setChainMode = useAppStore((s) => s.setChainMode);
  const showDimensions = useAppStore((s) => s.showDimensions);
  const toggleDimensions = useAppStore((s) => s.toggleDimensions);
  const scalePlan = useAppStore((s) => s.scalePlan);
  const furnitureCatalogId = useAppStore((s) => s.furnitureCatalogId);
  const setFurnitureCatalogId = useAppStore((s) => s.setFurnitureCatalogId);
  const roadWidth = useAppStore((s) => s.roadWidth);
  const setRoadWidth = useAppStore((s) => s.setRoadWidth);
  const stairWidthCm = useAppStore((s) => s.stairWidthCm);
  const setStairWidth = useAppStore((s) => s.setStairWidth);
  const railingHeightCm = useAppStore((s) => s.railingHeightCm);
  const railingElevationCm = useAppStore((s) => s.railingElevationCm);
  const railingStyle = useAppStore((s) => s.railingStyle);
  const setRailingHeight = useAppStore((s) => s.setRailingHeight);
  const setRailingElevation = useAppStore((s) => s.setRailingElevation);
  const setRailingStyle = useAppStore((s) => s.setRailingStyle);
  const beamElevationCm = useAppStore((s) => s.beamElevationCm);
  const setBeamElevation = useAppStore((s) => s.setBeamElevation);
  // Array tool
  const arrayConfig = useAppStore((s) => s.arrayConfig);
  const setArrayConfig = useAppStore((s) => s.setArrayConfig);
  const resetArrayConfig = useAppStore((s) => s.resetArrayConfig);
  const stairError = useAppStore((s) => s.activeTool === 'stair' ? null : null); // sourced from tool state in EditorCanvas
  void stairError;
  const paintFinishId = useAppStore((s) => s.paintFinishId);
  const setPaintFinishId = useAppStore((s) => s.setPaintFinishId);
  const glbWallFinishes = useGlbWallDiscovery();

  // Picking a finish swatch sets it as the active paint, AND immediately applies it to any
  // compatible surface that's already selected. This enables the "select the floor, then
  // pick a tile" flow: click a room (selects it), then click a floor-tile swatch to apply.
  // Wall paints behave the same way for a selected wall.
  const pickFinish = (finishId: string) => {
    setPaintFinishId(finishId);
    const state = useAppStore.getState();
    const category = categoryOf(finishId);
    state.selectedIds.forEach((id) => {
      if (category === 'wall' && state.walls[id]) {
        state.recordHistory('Paint Wall', () => state.updateWall(id, { materialId: finishId }));
      } else if (category === 'floor' && state.rooms[id]) {
        state.recordHistory('Paint Floor', () => state.updateRoom(id, { floorMaterialId: finishId }));
      } else if (category === 'floor' && state.deckSlabs[id]) {
        state.recordHistory('Paint Deck', () => state.updateDeckSlab(id, { materialId: finishId }));
      }
    });
  };
  const showVastuOverlay2D = useAppStore((s) => s.showVastuOverlay2D);
  const showVastuOverlay3D = useAppStore((s) => s.showVastuOverlay3D);
  const selectedOpeningKinds = useAppStore((s) => s.selectedOpeningKinds);
  const setOpeningKind = useAppStore((s) => s.setOpeningKind);
  const openingSizeOverrides = useAppStore((s) => s.openingSizeOverrides);
  const setOpeningSize = useAppStore((s) => s.setOpeningSize);
  const resetOpeningSize = useAppStore((s) => s.resetOpeningSize);
  const toggleVastuOverlay2D = useAppStore((s) => s.toggleVastuOverlay2D);
  const toggleVastuOverlay3D = useAppStore((s) => s.toggleVastuOverlay3D);
  const cameraMode = useAppStore((s) => s.cameraMode);
  const setCameraMode = useAppStore((s) => s.setCameraMode);
  const triggerCameraReset = useAppStore((s) => s.triggerCameraReset);
  const renderQuality = useAppStore((s) => s.renderQuality);
  const setRenderQuality = useAppStore((s) => s.setRenderQuality);

  // Sun controls (real-time day arc). time-of-day drives the whole arc; the manual direction
  // toggle + slider let the user aim the sun from a chosen compass direction instead.
  const sunTimeHours = useAppStore((s) => s.sunTimeHours);
  const setSunTime = useAppStore((s) => s.setSunTime);
  const sunAzimuthDeg = useAppStore((s) => s.sunAzimuthDeg);
  const setSunAzimuth = useAppStore((s) => s.setSunAzimuth);
  const sunDirectionOverride = useAppStore((s) => s.sunDirectionOverride);
  const setSunDirectionOverride = useAppStore((s) => s.setSunDirectionOverride);

  const selectedIds = useAppStore((s) => s.selectedIds);
  const furniture = useAppStore((s) => s.furniture);
  const walls = useAppStore((s) => s.walls);
  const pillars = useAppStore((s) => s.pillars);
  const beams = useAppStore((s) => s.beams);
  const deckSlabs = useAppStore((s) => s.deckSlabs);
  const rotateFurniture = useAppStore((s) => s.rotateFurniture);
  const removeFurniture = useAppStore((s) => s.removeFurniture);
  const removeWall = useAppStore((s) => s.removeWall);
  const removePillar = useAppStore((s) => s.removePillar);
  const removeBeam = useAppStore((s) => s.removeBeam);
  const removeDeckSlab = useAppStore((s) => s.removeDeckSlab);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const clearAll = useAppStore((s) => s.clearAll);

  // Undo / redo (Installment 4 — history slice)
  const canUndo = useAppStore((s) => s.canUndo);
  const canRedo = useAppStore((s) => s.canRedo);
  const undo = useAppStore((s) => s.undo);
  const redo = useAppStore((s) => s.redo);

  const [showSnapTest, setShowSnapTest] = useState(false);
  // Which panel fills the work area: 'split' (50/50), 'editor' (2D full), 'viewer' (3D full).
  const [maximized, setMaximized] = useState<'split' | 'editor' | 'viewer'>('split');
  const [isWalking, setIsWalking] = useState(false);
  const [ioMessage, setIoMessage] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<ImageExportFormat>('png');
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const result = await importFloorPlan(file);
    setIoMessage(result.success ? `Loaded “${file.name}”.` : `Import failed: ${result.error}`);
    e.target.value = ''; // allow re-importing the same file
  };

  const handleExportImage = async (which: '2d' | '3d') => {
    setIoMessage(`Exporting ${which.toUpperCase()} as ${exportFormat.toUpperCase()}…`);
    const result = which === '2d' ? await exportEditor2D(exportFormat) : await exportViewer3D(exportFormat);
    setIoMessage(
      result.success
        ? `Exported ${which.toUpperCase()} as ${exportFormat.toUpperCase()}.`
        : `Export failed: ${result.error}`
    );
  };

  // Track pointer-lock so we can show/hide the "click to walk" prompt.
  React.useEffect(() => {
    const onChange = () => setIsWalking(Boolean(document.pointerLockElement));
    document.addEventListener('pointerlockchange', onChange);
    return () => document.removeEventListener('pointerlockchange', onChange);
  }, []);

  const selectedFurnitureId = selectedIds.find((id) => furniture[id]);
  const selectedWallId = selectedIds.find((id) => walls[id]);
  const selectedPillarId = selectedIds.find((id) => pillars[id]);
  const selectedBeamId = selectedIds.find((id) => beams[id]);
  const selectedDeckId = selectedIds.find((id) => deckSlabs[id]);
  const openings = useAppStore((s) => s.openings);
  const removeOpening = useAppStore((s) => s.removeOpening);
  const selectedOpeningId = selectedIds.find((id) => openings[id]);
  const selectionLabel = selectedFurnitureId
    ? getCatalogEntry(furniture[selectedFurnitureId].catalogId).label
    : selectedOpeningId
      ? (getOpeningKind(openings[selectedOpeningId].kind ?? '')?.label ?? openings[selectedOpeningId].type)
      : selectedPillarId
        ? 'Pillar'
      : selectedBeamId
        ? 'Beam'
      : selectedDeckId
        ? 'Deck slab'
      : selectedWallId
        ? 'Wall'
        : 'nothing selected';

  const rotateSelected = (deltaDeg: number) => {
    useAppStore.getState().recordHistory('Rotate', () => {
      selectedIds.forEach((id) => {
        const item = furniture[id];
        if (item) rotateFurniture(id, item.rotation + (deltaDeg * Math.PI) / 180);
      });
    });
  };

  const deleteSelected = () => {
    const state = useAppStore.getState();
    state.recordHistory('Delete', () => {
      selectedIds.forEach((id) => {
        if (state.walls[id]) removeWall(id);
        if (state.furniture[id]) removeFurniture(id);
        if (state.openings[id]) removeOpening(id);
        if (state.pillars[id]) removePillar(id);
        if (state.beams[id]) removeBeam(id);
        if (state.deckSlabs[id]) removeDeckSlab(id);
      });
      clearSelection();
    });
  };

  const scaleBy = (factor: number) => {
    useAppStore.getState().recordHistory('Scale Plan', () => scalePlan(factor));
  };

  const clearAllWithHistory = () => {
    useAppStore.getState().recordHistory('Clear All', () => clearAll());
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
          <button style={btn(activeTool === 'road')} onClick={() => setActiveTool('road')}>🛣️ Road</button>
          <button style={btn(activeTool === 'pillar', '#475569')} onClick={() => setActiveTool('pillar')}>🏛️ Pillar</button>
          <button style={btn(activeTool === 'beam', '#475569')} onClick={() => setActiveTool('beam')}>━ Beam</button>
          <button style={btn(activeTool === 'deck', '#0284c7')} onClick={() => setActiveTool('deck')}>▱ Deck</button>
          <button style={btn(activeTool === 'railing', '#ea580c')} onClick={() => setActiveTool('railing')}>🛡️ Railing</button>
          <button style={btn(activeTool === 'furniture')} onClick={() => setActiveTool('furniture')}>🛋️ Furniture</button>
          <button style={btn(activeTool === 'door')} onClick={() => setActiveTool('door')}>🚪 Door</button>
          <button style={btn(activeTool === 'window')} onClick={() => setActiveTool('window')}>🪟 Window</button>
          <button style={btn(activeTool === 'vent')} onClick={() => setActiveTool('vent')}>💨 Vent</button>
          <button style={btn(activeTool === 'ac')} onClick={() => setActiveTool('ac')}>❄️ AC</button>
          <button style={btn(activeTool === 'paint')} onClick={() => setActiveTool('paint')}>🎨 Paint</button>
          <button style={btn(activeTool === 'room')} onClick={() => setActiveTool('room')}>🏷️ Name Room</button>
          <button style={btn(activeTool === 'stair', '#7c3aed')} onClick={() => setActiveTool('stair')}>🪜 Stair</button>
          <button style={btn(activeTool === 'array', '#f59e0b')} onClick={() => { resetArrayConfig(); setActiveTool('array'); }}>🔁 Array</button>
          <label style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: '0.5rem', fontSize: '0.82rem', color: '#374151', cursor: 'pointer' }}>
            <input type="checkbox" checked={isChainModeEnabled} onChange={(e) => setChainMode(e.target.checked)} />
            Chain mode
          </label>
        </Row>

        {(activeTool === 'door' || activeTool === 'window' || activeTool === 'vent' || activeTool === 'ac') && (
          <Row label={`${activeTool[0].toUpperCase()}${activeTool.slice(1)} type`}>
            {kindsForFamily(activeTool as OpeningFamily).map((k) => (
              <button
                key={k.id}
                style={btn(selectedOpeningKinds[activeTool as OpeningFamily] === k.id, '#0ea5e9')}
                onClick={() => setOpeningKind(activeTool as OpeningFamily, k.id)}
                title={`${k.width}×${k.height} cm`}
              >
                {k.icon} {k.label}
              </button>
            ))}
            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
              {activeTool === 'ac'
                ? 'Click a wall to mount the AC (any wall).'
                : activeTool === 'door'
                  ? 'Click a wall to place. Doors/gates can go on any wall.'
                  : 'Click a perimeter wall to place.'}
            </span>
          </Row>
        )}

        {(activeTool === 'door' || activeTool === 'window' || activeTool === 'vent') && (() => {
          const family = activeTool as OpeningFamily;
          const kind = getOpeningKind(selectedOpeningKinds[family]);
          const ov = openingSizeOverrides[family];
          const hasOverride = ov && (ov.width != null || ov.height != null || ov.elevation != null);
          return (
            <Row label="Custom size">
              <NumInput label="Width" value={ov?.width} placeholder={kind?.width} onChange={(v) => setOpeningSize(family, { width: v })} />
              <NumInput label="Height" value={ov?.height} placeholder={kind?.height} onChange={(v) => setOpeningSize(family, { height: v })} />
              {family !== 'door' && (
                <NumInput label="Sill" value={ov?.elevation} placeholder={kind?.elevation} onChange={(v) => setOpeningSize(family, { elevation: v })} />
              )}
              <button style={{ ...btn(false), opacity: hasOverride ? 1 : 0.5 }} disabled={!hasOverride} onClick={() => resetOpeningSize(family)}>
                ↺ Reset
              </button>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                cm. Blank = preset. {family !== 'door' ? 'Sill = height from floor to opening bottom. ' : ''}Applies to the next placed {family}.
              </span>
            </Row>
          );
        })()}

        {activeTool === 'road' && (
          <Row label="Road width">
            <input
              type="range" min={60} max={1000} step={10}
              value={roadWidth}
              onChange={(e) => setRoadWidth(parseFloat(e.target.value))}
              style={{ width: '180px' }}
              aria-label="Road width"
            />
            <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '70px', fontWeight: 600 }}>
              {(roadWidth / 100).toFixed(2)} m
            </span>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
              Click to start, click to end. Hold <kbd>Shift</kbd> for angle snap. Chain mode keeps paving. <kbd>Esc</kbd> cancels.
            </span>
          </Row>
        )}

        {activeTool === 'pillar' && (
          <>
            <Row label="Pillar">
              <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                Click to place a structural pillar. Use Select to adjust height/elevation.
              </span>
            </Row>
            <Row label="Height">
              <input
                type="range" min={100} max={600} step={10}
                value={300}
                onChange={(e) => {
                  const h = parseInt(e.target.value);
                  useAppStore.getState().recordHistory('Set Pillar Height', () => {
                    const pillarId = useAppStore.getState().selectedIds.find((id) => useAppStore.getState().pillars[id]);
                    if (pillarId) useAppStore.getState().updatePillar(pillarId, { height: h });
                  });
                }}
                style={{ width: '160px' }}
                aria-label="Pillar height"
              />
              <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '70px', fontWeight: 600 }}>
                300 cm (default)
              </span>
            </Row>
            <Row label="Elevation">
              <input
                type="range" min={0} max={300} step={10}
                value={0}
                disabled
                style={{ width: '160px', opacity: 0.5 }}
                aria-label="Pillar elevation"
              />
              <span style={{ fontSize: '0.8rem', color: '#94a3b8', minWidth: '70px', fontWeight: 600 }}>
                0 cm
              </span>
            </Row>
          </>
        )}

        {/* Selected pillar properties (visible when a pillar is selected in select mode) */}
        {activeTool === 'select' && selectedPillarId && (
          (() => {
            const p = pillars[selectedPillarId];
            if (!p) return null;
            return (
              <>
                <Row label="Pillar Height">
                  <input
                    type="range" min={100} max={600} step={10}
                    value={p.height}
                    onChange={(e) => {
                      const h = parseInt(e.target.value);
                      useAppStore.getState().recordHistory('Set Pillar Height', () => {
                        useAppStore.getState().updatePillar(selectedPillarId, { height: h });
                      });
                    }}
                    style={{ width: '160px' }}
                    aria-label="Selected pillar height"
                  />
                  <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '60px', fontWeight: 600 }}>
                    {p.height} cm
                  </span>
                </Row>
                <Row label="Pillar Elev">
                  <input
                    type="range" min={0} max={300} step={10}
                    value={p.elevationCm}
                    onChange={(e) => {
                      const ev = parseInt(e.target.value);
                      useAppStore.getState().recordHistory('Set Pillar Elevation', () => {
                        useAppStore.getState().updatePillar(selectedPillarId, { elevationCm: ev });
                      });
                    }}
                    style={{ width: '160px' }}
                    aria-label="Selected pillar elevation"
                  />
                  <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '60px', fontWeight: 600 }}>
                    {p.elevationCm} cm
                  </span>
                </Row>
              </>
            );
          })()
        )}

        {/* Selected beam: lower the height to seat the beam INTO the pillar at any level
            (the beam's bottom sits at this elevation), or raise it to rest on the pillar top. */}
        {activeTool === 'select' && selectedBeamId && (
          (() => {
            const b = beams[selectedBeamId];
            if (!b) return null;
            return (
              <Row label="Beam Height">
                <input
                  type="range" min={0} max={600} step={5}
                  value={b.elevationCm}
                  onChange={(e) => {
                    const ev = parseInt(e.target.value);
                    useAppStore.getState().recordHistory('Set Beam Height', () => {
                      useAppStore.getState().updateBeam(selectedBeamId, { elevationCm: ev });
                    });
                  }}
                  style={{ width: '160px' }}
                  aria-label="Selected beam height"
                />
                <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '70px', fontWeight: 600 }}>
                  {b.elevationCm} cm
                </span>
              </Row>
            );
          })()
        )}

        {activeTool === 'beam' && (
          <>
            <Row label="Beam">
              <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                Click start and end points; snap the ends to pillars and the beam seats onto them. Drag <strong>Beam Height</strong> down to sink it into the pillars.
              </span>
            </Row>
            {/* When a beam is selected (e.g. the one just placed), this slider edits THAT
                beam's height live; with nothing selected it sets the default height used for
                the next beam. Without this the just-placed beam couldn't be lowered from here
                — the slider only touched the next-placement default, which read as "broken". */}
            {(() => {
              const selBeam = selectedBeamId ? beams[selectedBeamId] : null;
              const value = selBeam ? selBeam.elevationCm : beamElevationCm;
              return (
                <Row label="Beam Height">
                  <input
                    type="range" min={0} max={600} step={10}
                    value={value}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value);
                      if (selBeam && selectedBeamId) {
                        useAppStore.getState().recordHistory('Set Beam Height', () => {
                          useAppStore.getState().updateBeam(selectedBeamId, { elevationCm: v });
                        });
                      } else {
                        setBeamElevation(v);
                      }
                    }}
                    style={{ width: '160px' }}
                    aria-label="Beam height"
                  />
                  <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '90px', fontWeight: 600 }}>
                    {selBeam ? `${selBeam.elevationCm} cm` : beamElevationCm === 0 ? 'Auto (top)' : `${beamElevationCm} cm`}
                  </span>
                </Row>
              );
            })()}
          </>
        )}

        {activeTool === 'deck' && (
          <Row label="Deck">
            <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
              Click polygon corners; click near the first point to close and create a slab/deck. Esc cancels.
            </span>
          </Row>
        )}

        {/* Selected deck properties: same finish palette as room floors, since decks are
            rendered with getFloorMaterial(slab.materialId) too. */}
        {activeTool === 'select' && selectedDeckId && (
          (() => {
            const slab = deckSlabs[selectedDeckId];
            if (!slab) return null;
            return (
              <>
                <Row label="Deck texture">
                  {FLOOR_FINISHES.map((f) => (
                    <Swatch
                      key={f.id}
                      finish={f}
                      selected={slab.materialId === f.id}
                      onClick={() => {
                        useAppStore.getState().recordHistory('Paint Deck', () => {
                          useAppStore.getState().updateDeckSlab(selectedDeckId, { materialId: f.id });
                        });
                      }}
                    />
                  ))}
                </Row>
              </>
            );
          })()
        )}

      {activeTool === 'railing' && (
        <>
          <Row label="Railing">
            <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
              Click start and end points to place a safety railing/parapet. Use Select to move/delete.
            </span>
          </Row>
          <Row label="Height">
            <input
              type="range" min={50} max={300} step={10}
              value={railingHeightCm}
              onChange={(e) => setRailingHeight(parseFloat(e.target.value))}
              style={{ width: '160px' }}
              aria-label="Railing height"
            />
            <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '70px', fontWeight: 600 }}>
              {railingHeightCm} cm
            </span>
          </Row>
          <Row label="Elevation">
            <input
              type="range" min={0} max={500} step={10}
              value={railingElevationCm}
              onChange={(e) => setRailingElevation(parseFloat(e.target.value))}
              style={{ width: '160px' }}
              aria-label="Railing elevation"
            />
            <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '70px', fontWeight: 600 }}>
              {railingElevationCm} cm
            </span>
          </Row>
          <Row label="Style">
            <button 
              style={btn(railingStyle === 'open', '#ea580c')} 
              onClick={() => setRailingStyle('open')}
            >
              Open (Bars)
            </button>
            <button 
              style={btn(railingStyle === 'solid', '#ea580c')} 
              onClick={() => setRailingStyle('solid')}
            >
              Solid (Parapet)
            </button>
          </Row>
        </>
      )}

        {activeTool === 'array' && (
          <>
            <Row label="Entity">
              <button style={btn(arrayConfig.entityType === 'furniture', '#0ea5e9')} onClick={() => setArrayConfig({ entityType: 'furniture', isPreviewing: true })}>
                🛋️ Furniture
              </button>
              <button style={btn(arrayConfig.entityType === 'pillar', '#475569')} onClick={() => setArrayConfig({ entityType: 'pillar', isPreviewing: true })}>
                🏛️ Pillar
              </button>
              <button style={btn(arrayConfig.entityType === 'building', '#10b981')} onClick={() => setArrayConfig({ entityType: 'building', isPreviewing: true })}>
                🏠 Building
              </button>
              <button style={btn(arrayConfig.entityType === 'component', '#8b5cf6')} onClick={() => {
                const state = useAppStore.getState();
                const id = state.selectedIds[0];
                if (id) {
                  setArrayConfig({ entityType: 'component', referenceId: id, isPreviewing: true });
                } else {
                  alert('Please select a component first (furniture, wall, pillar, beam, deck, railing, or road).');
                }
              }}>
                🎯 Component
              </button>
              {arrayConfig.entityType === 'furniture' && (
                <select
                  value={arrayConfig.referenceId ?? furnitureCatalogId}
                  onChange={(e) => setArrayConfig({ referenceId: e.target.value })}
                  style={{ padding: '3px 6px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem' }}
                >
                  {FURNITURE_CATALOG_IDS.map((id) => (
                    <option key={id} value={id}>{getCatalogEntry(id).label}</option>
                  ))}
                </select>
              )}
            </Row>
            <Row label="Count">
              <input
                type="range" min={2} max={20} step={1}
                value={arrayConfig.count}
                onChange={(e) => setArrayConfig({ count: parseInt(e.target.value) })}
                style={{ width: '160px' }}
                aria-label="Array count"
              />
              <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '40px', fontWeight: 600 }}>
                {arrayConfig.count}
              </span>
            </Row>
            <Row label="Spacing">
              <input
                type="range"
                min={50}
                max={arrayConfig.entityType === 'building' ? 5000 : 500}
                step={arrayConfig.entityType === 'building' ? 50 : 10}
                value={arrayConfig.spacing}
                onChange={(e) => setArrayConfig({ spacing: parseInt(e.target.value) })}
                style={{ width: '160px' }}
                aria-label="Array spacing"
              />
              <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '70px', fontWeight: 600 }}>
                {arrayConfig.spacing} cm ({(arrayConfig.spacing / 100).toFixed(2)} m)
              </span>
            </Row>
            <Row label="Angle">
              <input
                type="range" min={0} max={360} step={5}
                value={Math.round((arrayConfig.angle * 180) / Math.PI)}
                onChange={(e) => setArrayConfig({ angle: (parseInt(e.target.value) * Math.PI) / 180 })}
                style={{ width: '160px' }}
                aria-label="Array angle"
              />
              <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '40px', fontWeight: 600 }}>
                {Math.round((arrayConfig.angle * 180) / Math.PI)}°
              </span>
              <button style={btn(false, '#6366f1')} onClick={() => setArrayConfig({ angle: 0 })}>↺ 0°</button>
              <button style={btn(false, '#6366f1')} onClick={() => setArrayConfig({ angle: Math.PI / 2 })}>↺ 90°</button>
            </Row>
            <Row label="Preview">
              <button style={btn(true, '#10b981')} onClick={() => setArrayConfig({ isPreviewing: true })}>👁️ Show Preview</button>
              <button style={btn(false, '#ef4444')} onClick={() => { resetArrayConfig(); }}>✕ Cancel</button>
              <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                Click in the editor to place the array. <kbd>Esc</kbd> to cancel.
              </span>
            </Row>
          </>
        )}

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

        {activeTool === 'room' && (
          <Row label="Name Room">
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
              Click a room in the 2D editor to select it, then set its type and name in the popup.
            </span>
          </Row>
        )}

        {activeTool === 'stair' && (
          <>
            <Row label="Stair width">
              <input
                type="range" min={60} max={500} step={10}
                value={stairWidthCm}
                onChange={(e) => setStairWidth(parseFloat(e.target.value))}
                style={{ width: '160px' }}
                aria-label="Stair width"
              />
              <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '60px', fontWeight: 600 }}>
                {stairWidthCm} cm
              </span>
            </Row>
            <Row label="How to draw">
              <span style={{ fontSize: '0.78rem', color: '#64748b', lineHeight: 1.5 }}>
                <strong>Requires 2+ floors.</strong> Click in the editor to place points:
                <br />
                <strong>2 points</strong> = Straight staircase • <strong>3 points</strong> = L-shaped (1 landing) • <strong>4 points</strong> = U-shaped (2 landings)
                <br />
                <strong>Double-click</strong> or press <kbd>Enter</kbd> to finish. <kbd>Esc</kbd> cancels. <kbd>Delete</kbd> removes selected stair.
              </span>
            </Row>
          </>
        )}

        {activeTool === 'paint' && (
          <>
            <Row label="Wall paint">
              {WALL_FINISHES.map((f) => (
                <Swatch key={f.id} finish={f} selected={paintFinishId === f.id} onClick={() => pickFinish(f.id)} />
              ))}
            </Row>
            {glbWallFinishes.length > 0 && (
              <Row label="Custom walls">
                {glbWallFinishes.map((f) => (
                  <Swatch key={f.id} finish={f} selected={paintFinishId === f.id} onClick={() => pickFinish(f.id)} />
                ))}
              </Row>
            )}
            <Row label="Floor tile">
              {FLOOR_FINISHES.map((f) => (
                <Swatch key={f.id} finish={f} selected={paintFinishId === f.id} onClick={() => pickFinish(f.id)} />
              ))}
            </Row>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#94a3b8' }}>
              Two ways to paint: pick a finish then click a <strong>wall</strong> (wall paint) or a
              {' '}<strong>room floor</strong> (floor tile) in the 2D editor — or click the surface first
              to select it, then pick a swatch to apply.
            </p>
          </>
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
          <button style={btn(showDimensions, '#0ea5e9')} onClick={toggleDimensions}>📏 Dimensions</button>
        </Row>

        <Row label="Scale">
          <button style={btn(false, '#6366f1')} onClick={() => scaleBy(1 / 1.1)}>➖ Scale Down</button>
          <button style={btn(false, '#6366f1')} onClick={() => scaleBy(1.1)}>➕ Scale Up</button>
          <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
            Resize the whole plan (±10% each step). Wall lengths update live; furniture keeps real-world size.
          </span>
        </Row>

        <Row label="Camera">
          <button style={btn(cameraMode === 'orbit', '#f59e0b')} onClick={() => setCameraMode('orbit')}>🚁 Orbit</button>
          <button style={btn(cameraMode === 'firstPerson', '#f59e0b')} onClick={() => setCameraMode('firstPerson')}>🚶 First-Person (WASD)</button>
          <button style={btn(false, '#64748b')} onClick={triggerCameraReset}>🔄 Reset View</button>
        </Row>

        <Row label="Graphics">
          <button style={btn(renderQuality === 'high', '#8b5cf6')} onClick={() => setRenderQuality('high')}>✨ High</button>
          <button style={btn(renderQuality === 'medium', '#8b5cf6')} onClick={() => setRenderQuality('medium')}>⚖️ Balanced</button>
          <button style={btn(renderQuality === 'low', '#8b5cf6')} onClick={() => setRenderQuality('low')}>🪶 Low</button>
          <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
            High = ambient occlusion + bloom (best looking). Balanced drops bloom. Low turns off
            post-processing for older/slower computers.
          </span>
        </Row>

        <Row label="Sun">
          <input
            type="range" min={0} max={24} step={0.25}
            value={sunTimeHours}
            onChange={(e) => setSunTime(parseFloat(e.target.value))}
            style={{ width: '160px' }}
            aria-label="Time of day"
          />
          <span style={{ fontSize: '0.8rem', color: '#475569', minWidth: '44px', fontWeight: 600 }}>
            {dayPhase(sunTimeHours).icon} {formatClock(sunTimeHours)}
          </span>
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 600,
              color: dayPhase(sunTimeHours).isDay ? '#92400e' : '#1e3a8a',
              background: dayPhase(sunTimeHours).isDay ? '#fef3c7' : '#dbeafe',
              padding: '2px 8px',
              borderRadius: '999px',
            }}
          >
            {dayPhase(sunTimeHours).label}
          </span>
          <label style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: '0.5rem', fontSize: '0.82rem', color: '#374151', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={sunDirectionOverride}
              onChange={(e) => setSunDirectionOverride(e.target.checked)}
            />
            Manual direction
          </label>
          <input
            type="range" min={0} max={360} step={5}
            value={sunAzimuthDeg}
            onChange={(e) => setSunAzimuth(parseFloat(e.target.value))}
            disabled={!sunDirectionOverride}
            style={{ width: '120px', opacity: sunDirectionOverride ? 1 : 0.4 }}
            aria-label="Sun compass direction"
          />
          <span style={{ fontSize: '0.8rem', color: '#64748b', minWidth: '28px' }}>
            {sunDirectionOverride ? azimuthLabel(sunAzimuthDeg) : 'auto'}
          </span>
        </Row>

        <Row label="Floors">
          <FloorSwitcher />
        </Row>

        <Row label="Plan">
          <button style={btn(false, '#8b5cf6')} onClick={loadSampleHouse}>🏠 Load Sample House</button>
          <button style={btn(false, '#0ea5e9')} onClick={() => useAppStore.getState().requestFitView()}>🎯 Center View</button>
          <button style={btn(false, '#ef4444')} onClick={() => { clearAllWithHistory(); }}>♻️ Clear All</button>
        </Row>

        <Row label="History">
          <button style={{ ...btn(false, '#0ea5e9'), opacity: canUndo ? 1 : 0.5 }} disabled={!canUndo} onClick={undo}>↶ Undo</button>
          <button style={{ ...btn(false, '#0ea5e9'), opacity: canRedo ? 1 : 0.5 }} disabled={!canRedo} onClick={redo}>↷ Redo</button>
          <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
            Keyboard: <kbd>Ctrl/Cmd+Z</kbd> undo · <kbd>Ctrl+Y</kbd> / <kbd>Ctrl+Shift+Z</kbd> redo
          </span>
        </Row>

        <Row label="File">
          <button style={btn(false, '#16a34a')} onClick={() => exportFloorPlan()}>💾 Export JSON</button>
          <button style={btn(false, '#16a34a')} onClick={() => fileInputRef.current?.click()}>📂 Import JSON</button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            style={{ display: 'none' }}
            onChange={handleImportFile}
          />
          {ioMessage && <span style={{ fontSize: '0.78rem', color: '#64748b' }}>{ioMessage}</span>}
          <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
            Plans also auto-save to your browser (IndexedDB) and reload on refresh.
          </span>
        </Row>

        <Row label="Export">
          <select
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value as ImageExportFormat)}
            style={{ padding: '0.4rem 0.5rem', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem', color: '#1f2937', fontWeight: 600 }}
            aria-label="Image export format"
          >
            <option value="png">PNG</option>
            <option value="jpg">JPG</option>
            <option value="pdf">PDF</option>
          </select>
          <button style={btn(false, '#0ea5e9')} onClick={() => handleExportImage('2d')}>🖼️ Export 2D Plan</button>
          <button style={btn(false, '#0ea5e9')} onClick={() => handleExportImage('3d')}>🏗️ Export 3D View</button>
          <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
            Saves the current 2D plan or 3D scene as an image or PDF.
          </span>
        </Row>
      </Card>

      {/* Editor + Viewer */}
      <div style={{ display: 'flex', gap: '1rem', height: '78vh', minHeight: '600px', margin: '1rem 0' }}>
        <div style={{ flex: 1, flexDirection: 'column', display: maximized === 'viewer' ? 'none' : 'flex' }}>
          <div style={panelHeader}>
            <span style={badge}>2D Editor</span>
            <button
              style={maxBtn}
              title={maximized === 'editor' ? 'Restore split view' : 'Maximize the 2D editor'}
              onClick={() => setMaximized((m) => (m === 'editor' ? 'split' : 'editor'))}
            >
              {maximized === 'editor' ? '🗗 Restore' : '🗖 Maximize'}
            </button>
          </div>
          <ErrorBoundary>
            <div style={canvasFrame}>
              <EditorScreen />
            </div>
          </ErrorBoundary>
        </div>
        <div style={{ flex: 1, flexDirection: 'column', display: maximized === 'editor' ? 'none' : 'flex' }}>
          <div style={panelHeader}>
            <span style={badge}>3D Viewer {cameraMode === 'firstPerson' ? '— click to enter, then HOLD mouse to walk' : ''}</span>
            <button
              style={maxBtn}
              title={maximized === 'viewer' ? 'Restore split view' : 'Maximize the 3D viewer'}
              onClick={() => setMaximized((m) => (m === 'viewer' ? 'split' : 'viewer'))}
            >
              {maximized === 'viewer' ? '🗗 Restore' : '🗖 Maximize'}
            </button>
          </div>
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

        {(showVastuOverlay2D || showVastuOverlay3D) && (
          <Card title="🧭 Vastu Chakra Legend">
            <VastuLegend />
          </Card>
        )}

        <Card title="⌨️ How to test">
          <ul style={{ margin: 0, paddingLeft: '1.1rem', color: '#475569', fontSize: '0.82rem', lineHeight: 1.7 }}>
            <li><strong>Draw Wall:</strong> click to start, click to end. Hold <kbd>Shift</kbd> for angle snap. <kbd>Esc</kbd> / right-click cancels.</li>
            <li><strong>Pillar:</strong> click to place a structural column; select and drag to align it to the grid.</li>
            <li><strong>Beam:</strong> click start and end to draw a horizontal structural member above the floor.</li>
            <li><strong>Deck:</strong> click corners to outline a custom balcony/corridor/roof slab, then click the first point to close it.</li>
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

const panelHeader: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '0.5rem',
};

const maxBtn: React.CSSProperties = {
  fontSize: '0.7rem',
  fontWeight: 600,
  color: '#334155',
  background: '#e2e8f0',
  border: '1px solid #cbd5e1',
  borderRadius: '6px',
  padding: '2px 8px',
  cursor: 'pointer',
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
