// src/domains/editor/components/AnnotationLayer.tsx

import React, { useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store';

interface AnnotationLayerProps {
  /** Zoom scale (px per cm) so the inline editor stays a constant on-screen size. */
  scale?: number;
}

/**
 * Renders free text annotations on the plan (Y-flipped, rotatable). Double-click a label to
 * edit it inline; empty text on commit deletes the annotation. Dragging is handled by the
 * canvas select-drag (see EditorCanvas `hitTestAnnotation` + the 'annotation' drag kind).
 */
export const AnnotationLayer: React.FC<AnnotationLayerProps> = React.memo(({ scale = 1 }) => {
  const annotations = useAppStore((s) => s.annotations);
  const selectedIds = useAppStore((s) => s.selectedIds);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId) inputRef.current?.focus();
  }, [editingId]);

  const commit = () => {
    if (!editingId) return;
    const id = editingId;
    setEditingId(null);
    const store = useAppStore.getState();
    const text = value.trim();
    if (text === '') {
      store.recordHistory('Delete Text', () => store.removeAnnotation(id));
    } else {
      store.recordHistory('Edit Text', () => store.updateAnnotation(id, { text }));
    }
  };

  return (
    <g className="annotation-layer">
      {Object.values(annotations).map((a) => {
        const deg = a.rotation ? (-a.rotation * 180) / Math.PI : 0;
        const isSelected = selectedIds.includes(a.id);
        const isEditing = editingId === a.id;

        return (
          <g key={a.id} transform={`translate(${a.position.x} ${-a.position.y}) rotate(${deg})`} data-entity-id={a.id} data-entity-type="annotation">
            {isEditing ? (
              <g transform={`scale(${1 / scale})`}>
                <foreignObject x={-90} y={-14} width={180} height={28} style={{ overflow: 'visible' }}>
                  <input
                    ref={inputRef}
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    onBlur={commit}
                    onKeyDown={(e) => {
                      e.stopPropagation();
                      if (e.key === 'Enter') commit();
                      else if (e.key === 'Escape') setEditingId(null);
                    }}
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      width: 172,
                      background: '#0b1220',
                      border: '1px solid #38bdf8',
                      borderRadius: 4,
                      color: 'white',
                      font: '13px sans-serif',
                      padding: '2px 5px',
                      textAlign: 'center',
                    }}
                  />
                </foreignObject>
              </g>
            ) : (
              <text
                x={0}
                y={0}
                fill={a.color}
                stroke="#1c1917"
                strokeWidth={a.fontSizeCm * 0.04}
                paintOrder="stroke"
                fontSize={a.fontSizeCm}
                fontFamily="sans-serif"
                textAnchor="middle"
                dominantBaseline="middle"
                style={{ cursor: 'pointer', userSelect: 'none' }}
                onDoubleClick={(e) => {
                  e.stopPropagation();
                  setValue(a.text);
                  setEditingId(a.id);
                }}
              >
                {a.text}
              </text>
            )}
            {isSelected && !isEditing && (
              <rect
                x={-(a.text.length * a.fontSizeCm * 0.32)}
                y={-a.fontSizeCm * 0.7}
                width={a.text.length * a.fontSizeCm * 0.64}
                height={a.fontSizeCm * 1.4}
                fill="none"
                stroke="#f59e0b"
                strokeWidth={2}
                pointerEvents="none"
              />
            )}
          </g>
        );
      })}
    </g>
  );
});

AnnotationLayer.displayName = 'AnnotationLayer';
