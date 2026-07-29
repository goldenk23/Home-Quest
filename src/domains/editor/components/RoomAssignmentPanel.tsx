// src/domains/editor/components/RoomAssignmentPanel.tsx

import React from 'react';
import { useAppStore } from '@/store';
import type { RoomType } from '@/types/editor';

const ROOM_TYPES: RoomType[] = [
  'living', 'bedroom', 'kitchen', 'bathroom', 'puja', 'study',
  'dining', 'storage', 'garage', 'balcony', 'entrance', 'corridor', 'custom',
];

/**
 * Floating in-canvas panel for assigning a room type to the currently selected room.
 *
 * It appears in the top-right of the 2D editor whenever a detected room is selected
 * (click inside a box with the Select tool). This lets the user say "this box is the
 * kitchen, that box is the bedroom" directly on the drawing, without hunting through a
 * side list. Renders nothing when no room is selected.
 */
export const RoomAssignmentPanel: React.FC = () => {
  const selectedIds = useAppStore((s) => s.selectedIds);
  const rooms = useAppStore((s) => s.rooms);
  const updateRoom = useAppStore((s) => s.updateRoom);
  const activeTool = useAppStore((s) => s.activeTool);

  const selectedRoomId = selectedIds.find((id) => rooms[id]);
  const room = selectedRoomId ? rooms[selectedRoomId] : null;
  // Only offer room naming/assignment with the dedicated "Name Room" tool, so selecting a
  // room while painting (or with any other tool) doesn't pop this panel open.
  if (activeTool !== 'room' || !room) return null;

  return (
    <div style={panel}>
      <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: '6px' }}>
        Assign selected room
      </div>
      <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: '8px', fontSize: '0.9rem' }}>{room.label}</div>

      <label style={{ display: 'block', fontSize: '0.78rem', color: '#475569', marginBottom: '4px' }}>This box is a:</label>
      <select
        autoFocus
        value={room.roomType}
        onChange={(e) => {
          const next = e.target.value as RoomType;
          useAppStore.getState().recordHistory('Set Room Type', () => updateRoom(room.id, { roomType: next }));
        }}
        style={select}
      >
        {ROOM_TYPES.map((t) => (
          <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
        ))}
      </select>

      <label style={{ display: 'block', fontSize: '0.78rem', color: '#475569', margin: '8px 0 4px' }}>Name (optional):</label>
      <input
        type="text"
        value={room.label}
        onChange={(e) => updateRoom(room.id, { label: e.target.value })}
        style={select}
        placeholder="e.g. Master Bedroom"
      />

      <label style={{ display: 'block', fontSize: '0.78rem', color: '#475569', margin: '8px 0 4px' }}>Fill:</label>
      <select
        value={room.fillMode ?? 'filled'}
        onChange={(e) => {
          const next = e.target.value as NonNullable<typeof room.fillMode>;
          useAppStore.getState().recordHistory('Set Room Fill', () => updateRoom(room.id, { fillMode: next }));
        }}
        style={select}
      >
        <option value="filled">Filled</option>
        <option value="transparent">Transparent (outline)</option>
        <option value="walls-only">Walls only</option>
      </select>

      <label style={{ display: 'block', fontSize: '0.78rem', color: '#475569', margin: '8px 0 4px' }}>Fill color (optional):</label>
      <input
        type="color"
        value={room.fillColor ?? '#60a5fa'}
        onChange={(e) => updateRoom(room.id, { fillColor: e.target.value })}
        style={{ ...select, padding: '2px', height: 32 }}
      />
    </div>
  );
};

const panel: React.CSSProperties = {
  position: 'absolute',
  top: 12,
  right: 12,
  width: 200,
  padding: '12px',
  background: 'rgba(255,255,255,0.97)',
  borderRadius: '10px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
  border: '1px solid #e2e8f0',
  zIndex: 5,
};

const select: React.CSSProperties = {
  width: '100%',
  padding: '6px 8px',
  borderRadius: '6px',
  border: '1px solid #cbd5e1',
  fontSize: '0.82rem',
  boxSizing: 'border-box',
};
