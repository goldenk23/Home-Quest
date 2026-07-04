import React from 'react';
import { useAppStore } from '@/store';
import { computeComponentBounds, type ComponentCloneGeometry } from '../services/componentClone';

/**
 * Visual marker for the Array tool's replication source. When the user clicks an entity in
 * array mode, this draws an animated ("marching ants") dashed border around that entity plus
 * an "Array Source" label, so it's obvious which component the ghost copies are cloned from.
 */
export const ArraySourceHighlight: React.FC = React.memo(() => {
  const config = useAppStore((s) => s.arrayConfig);
  const vertices = useAppStore((s) => s.vertices);
  const walls = useAppStore((s) => s.walls);
  const openings = useAppStore((s) => s.openings);
  const pillars = useAppStore((s) => s.pillars);
  const beams = useAppStore((s) => s.beams);
  const deckSlabs = useAppStore((s) => s.deckSlabs);
  const railings = useAppStore((s) => s.railings);
  const furniture = useAppStore((s) => s.furniture);
  const roads = useAppStore((s) => s.roads);

  if (config.entityType !== 'component' || !config.referenceId) return null;

  const g: ComponentCloneGeometry = { vertices, walls, openings, pillars, beams, deckSlabs, railings, furniture, roads };
  const bounds = computeComponentBounds(config.referenceId, g);
  if (!bounds) return null;

  const pad = 8;
  const x = bounds.min.x - pad;
  const y = -bounds.max.y - pad; // world +y is up; SVG +y is down
  const w = bounds.max.x - bounds.min.x + pad * 2;
  const h = bounds.max.y - bounds.min.y + pad * 2;

  return (
    <g className="array-source-highlight" pointerEvents="none">
      <rect x={x} y={y} width={w} height={h} fill="rgba(139,92,246,0.08)" stroke="#8b5cf6" strokeWidth={2.5} strokeDasharray="8 6">
        <animate attributeName="stroke-dashoffset" from="28" to="0" dur="1s" repeatCount="indefinite" />
      </rect>
      <text
        x={bounds.center.x}
        y={y - 8}
        textAnchor="middle"
        fontSize={12}
        fontWeight={700}
        fontFamily="sans-serif"
        fill="#c4b5fd"
        stroke="#111827"
        strokeWidth={0.75}
        paintOrder="stroke"
      >
        Array Source
      </text>
    </g>
  );
});

ArraySourceHighlight.displayName = 'ArraySourceHighlight';
