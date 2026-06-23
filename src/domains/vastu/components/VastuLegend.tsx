// src/domains/vastu/components/VastuLegend.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { VASTU_ZONES_8 } from '../services/zones';
import { ROOM_NAME } from '../services/scoring';
import type { RoomType } from '@/types/editor';

export const VastuLegend: React.FC = () => {
  const showVastu2D = useAppStore((s) => s.showVastuOverlay2D);
  const showVastu3D = useAppStore((s) => s.showVastuOverlay3D);

  if (!showVastu2D && !showVastu3D) return null;

  return (
    <div style={gridStyle}>
      {VASTU_ZONES_8.map((zone) => {
        // Convert internal room keys to human readable labels
        const rooms = zone.recommendedRooms
          .map((r) => ROOM_NAME[r as RoomType] || r)
          .join(', ');

        return (
          <div key={zone.direction} style={rowStyle}>
            <div style={{ ...colorSwatchStyle, backgroundColor: zone.color }} />
            <div style={infoContainerStyle}>
              <div style={directionStyle}>
                <strong>{zone.direction}</strong> <span style={elementStyle}>• {zone.element}</span>
              </div>
              <div style={roomsStyle}>{rooms}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// --- Styles ---

const gridStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
};

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: '10px',
};

const colorSwatchStyle: React.CSSProperties = {
  width: '14px',
  height: '14px',
  borderRadius: '50%',
  border: '1px solid rgba(0,0,0,0.1)',
  flexShrink: 0,
  marginTop: '2px',
};

const infoContainerStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
};

const directionStyle: React.CSSProperties = {
  fontSize: '0.8rem',
  color: '#0f172a',
  lineHeight: 1.2,
};

const elementStyle: React.CSSProperties = {
  color: '#64748b',
  fontWeight: 500,
  textTransform: 'capitalize',
};

const roomsStyle: React.CSSProperties = {
  fontSize: '0.75rem',
  color: '#475569',
  marginTop: '2px',
  lineHeight: 1.3,
};
