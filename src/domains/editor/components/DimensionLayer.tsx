// src/domains/editor/components/DimensionLayer.tsx

import React, { useEffect, useRef, useState } from 'react';
import { useWallSegments } from '@/store/selectors/editorSelectors';
import { useAppStore } from '@/store';
import { formatLength, fromCm, toCm } from '../services/units';
import { endpointFromLength } from '../services/geometry';

interface DimensionLayerProps {
  /** Current zoom scale (px per cm) so the inline edit input keeps a constant on-screen size. */
  scale?: number;
}

/**
 * Dimension annotations: draws each wall's real-world length as a CAD-style label off the
 * wall centerline, formatted in the active display unit. Clicking a label opens a small
 * numeric input; submitting a new length resizes the wall by moving its END vertex along the
 * wall direction (its START stays put). Shared vertices move with it (graph model).
 *
 * Port of the Python editor's editable dimensions (`DimensionDrawer` + `line_edit_manager`).
 */
export const DimensionLayer: React.FC<DimensionLayerProps> = React.memo(({ scale = 1 }) => {
  const walls = useWallSegments();
  const displayUnit = useAppStore((s) => s.displayUnit);
  const [editing, setEditing] = useState<{ wallId: string } | null>(null);
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const openEditor = (wallId: string, lenCm: number) => {
    setValue(fromCm(lenCm, displayUnit).toFixed(2));
    setEditing({ wallId });
  };

  const commit = () => {
    if (!editing) return;
    const newLen = toCm(parseFloat(value), displayUnit);
    setEditing(null);
    if (!(newLen > 0)) return;
    const store = useAppStore.getState();
    const wall = store.walls[editing.wallId];
    if (!wall) return;
    const sv = store.vertices[wall.startVertexId];
    const ev = store.vertices[wall.endVertexId];
    if (!sv || !ev) return;
    const dx = ev.position.x - sv.position.x;
    const dy = ev.position.y - sv.position.y;
    if (Math.hypot(dx, dy) < 1e-6) return; // no direction to grow along
    // Keep START fixed; move END along the wall's current direction to the exact new length.
    const newEnd = endpointFromLength(sv.position, newLen, Math.atan2(dy, dx));
    store.recordHistory('Resize Wall', () => store.moveVertex(wall.endVertexId, newEnd));
  };

  return (
    <g className="dimension-layer">
      {walls.map((w) => {
        const dx = w.end.x - w.start.x;
        const dy = w.end.y - w.start.y;
        const len = Math.hypot(dx, dy);
        if (len < 1) return null;

        // Midpoint in SVG space (world Y is flipped to -y on screen).
        const mx = (w.start.x + w.end.x) / 2;
        const my = -(w.start.y + w.end.y) / 2;

        // Angle of the wall on screen; keep text upright (never upside-down).
        let deg = (Math.atan2(-dy, dx) * 180) / Math.PI;
        if (deg > 90) deg -= 180;
        if (deg < -90) deg += 180;

        const label = formatLength(len, displayUnit);
        const offset = w.thickness / 2 + 8; // lift the label just clear of the wall fill
        const isEditing = editing?.wallId === w.id;

        return (
          <g key={w.id} transform={`translate(${mx} ${my}) rotate(${deg})`}>
            {isEditing ? (
              // Counter-scale so the input stays a constant px size regardless of zoom.
              <g transform={`scale(${1 / scale})`}>
                <foreignObject x={-46} y={-offset * scale - 14} width={92} height={26} style={{ overflow: 'visible' }}>
                  <input
                    ref={inputRef}
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    onBlur={commit}
                    onKeyDown={(e) => {
                      e.stopPropagation();
                      if (e.key === 'Enter') commit();
                      else if (e.key === 'Escape') setEditing(null);
                    }}
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={(e) => e.stopPropagation()}
                    inputMode="decimal"
                    style={{
                      width: 78,
                      background: '#0b1220',
                      border: '1px solid #34d399',
                      borderRadius: 4,
                      color: 'white',
                      font: '12px sans-serif',
                      padding: '2px 4px',
                      textAlign: 'center',
                    }}
                  />
                </foreignObject>
              </g>
            ) : (
              <text
                x={0}
                y={-offset}
                fill="#fde68a"
                stroke="#1c1917"
                strokeWidth={0.7}
                paintOrder="stroke"
                fontSize={14}
                fontWeight={600}
                fontFamily="sans-serif"
                textAnchor="middle"
                style={{ cursor: 'pointer' }}
                onMouseDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  openEditor(w.id, len);
                }}
              >
                {label}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
});

DimensionLayer.displayName = 'DimensionLayer';
