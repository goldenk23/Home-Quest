// src/domains/editor/components/TypedLengthInput.tsx

import React, { useEffect, useRef, useState } from 'react';
import type { Point2D, ViewTransform } from '@/types/geometry';
import { toCm, type DisplayUnit } from '../services/units';

interface TypedLengthInputProps {
  /** The wall/segment start point (world cm). */
  start: Point2D;
  /** Current cursor world point; used to seed the drawing direction. */
  cursor: Point2D | null;
  /** Active view transform (to place the overlay in SVG screen space). */
  view: ViewTransform;
  /** Active display unit for interpreting the typed length. */
  unit: DisplayUnit;
  /** Called with an exact length (cm) and direction (rad, CCW from +X, world Y up). */
  onSubmit: (lengthCm: number, directionRad: number) => void;
  /** Called on Escape. */
  onCancel: () => void;
}

/**
 * Small numeric overlay for typing an exact wall length (and optional angle) while drawing.
 * Rendered as an SVG <foreignObject> at screen space (outside the zoom <g>) so its text stays
 * a constant size. Enter commits; Escape cancels. Direction defaults to the cursor bearing.
 *
 * Port of the Python editor's distance-entry box (`finish_line_with_distance`).
 */
export const TypedLengthInput: React.FC<TypedLengthInputProps> = ({
  start,
  cursor,
  view,
  unit,
  onSubmit,
  onCancel,
}) => {
  const [length, setLength] = useState('');
  const [angle, setAngle] = useState('');
  const lengthRef = useRef<HTMLInputElement>(null);

  // Focus the length field as soon as the overlay appears (once).
  useEffect(() => {
    lengthRef.current?.focus();
  }, []);

  // Anchor near the cursor (or the start if the cursor is unknown), in SVG px.
  const anchor = cursor ?? start;
  const sx = anchor.x * view.scale + view.offsetX + 14;
  const sy = -anchor.y * view.scale + view.offsetY + 14;

  const commit = () => {
    const lenVal = parseFloat(length);
    if (!(lenVal > 0)) return;
    const lengthCm = toCm(lenVal, unit);
    let dirRad: number;
    if (angle.trim() !== '' && !Number.isNaN(parseFloat(angle))) {
      dirRad = (parseFloat(angle) * Math.PI) / 180; // typed degrees, CCW from +X
    } else {
      const dx = anchor.x - start.x;
      const dy = anchor.y - start.y;
      dirRad = dx === 0 && dy === 0 ? 0 : Math.atan2(dy, dx);
    }
    onSubmit(lengthCm, dirRad);
    setLength('');
    setAngle('');
  };

  const stop = (e: React.SyntheticEvent) => e.stopPropagation();

  return (
    <foreignObject x={sx} y={sy} width={190} height={40} style={{ overflow: 'visible' }}>
      <div
        // Stop canvas handlers from firing while interacting with the inputs.
        onMouseDown={stop}
        onClick={stop}
        onDoubleClick={stop}
        style={{
          display: 'flex',
          gap: 4,
          alignItems: 'center',
          background: 'rgba(17,24,39,0.95)',
          border: '1px solid #34d399',
          borderRadius: 6,
          padding: '3px 5px',
          font: '12px sans-serif',
          color: 'white',
          boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
          width: 'fit-content',
        }}
      >
        <input
          ref={lengthRef}
          value={length}
          onChange={(e) => setLength(e.target.value)}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === 'Enter') commit();
            else if (e.key === 'Escape') onCancel();
          }}
          placeholder={`len (${unit})`}
          inputMode="decimal"
          style={{
            width: 64,
            background: '#0b1220',
            border: '1px solid #334155',
            borderRadius: 4,
            color: 'white',
            padding: '2px 4px',
          }}
        />
        <input
          value={angle}
          onChange={(e) => setAngle(e.target.value)}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === 'Enter') commit();
            else if (e.key === 'Escape') onCancel();
          }}
          placeholder="°"
          inputMode="decimal"
          style={{
            width: 42,
            background: '#0b1220',
            border: '1px solid #334155',
            borderRadius: 4,
            color: 'white',
            padding: '2px 4px',
          }}
        />
      </div>
    </foreignObject>
  );
};
