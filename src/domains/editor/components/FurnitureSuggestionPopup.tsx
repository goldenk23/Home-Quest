// src/domains/editor/components/FurnitureSuggestionPopup.tsx

import React from 'react';
import { getCatalogEntry } from '@/domains/viewer/hooks/useAssetLoader';

interface FurnitureSuggestionPopupProps {
  /** Catalog ids to offer. */
  items: string[];
  /** Screen-space (SVG px) anchor for the popup. */
  sx: number;
  sy: number;
  /** Place the chosen item. */
  onPick: (catalogId: string) => void;
  /** Dismiss without placing. */
  onClose: () => void;
}

/**
 * Small in-canvas popup listing suggested furniture for a double-clicked room. Rendered as an
 * SVG <foreignObject> at screen space so it doesn't scale with zoom. Clicking an item places it.
 *
 * Port of the Python editor's `FurnitureSuggestionPopup`.
 */
export const FurnitureSuggestionPopup: React.FC<FurnitureSuggestionPopupProps> = ({
  items,
  sx,
  sy,
  onPick,
  onClose,
}) => {
  const stop = (e: React.SyntheticEvent) => e.stopPropagation();
  return (
    <foreignObject x={sx} y={sy} width={200} height={Math.min(items.length, 8) * 30 + 40} style={{ overflow: 'visible' }}>
      <div
        onMouseDown={stop}
        onClick={stop}
        onDoubleClick={stop}
        style={{
          background: 'rgba(17,24,39,0.97)',
          border: '1px solid #38bdf8',
          borderRadius: 8,
          padding: 6,
          font: '12px sans-serif',
          color: 'white',
          boxShadow: '0 4px 16px rgba(0,0,0,0.45)',
          width: 188,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 4px 6px' }}>
          <span style={{ color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.68rem' }}>Suggested</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: 14 }}>✕</button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 240, overflowY: 'auto' }}>
          {items.map((id) => (
            <button
              key={id}
              onClick={() => onPick(id)}
              style={{
                textAlign: 'left',
                background: '#0b1220',
                border: '1px solid #334155',
                borderRadius: 5,
                color: 'white',
                padding: '5px 8px',
                cursor: 'pointer',
              }}
            >
              {getCatalogEntry(id).label}
            </button>
          ))}
        </div>
      </div>
    </foreignObject>
  );
};
