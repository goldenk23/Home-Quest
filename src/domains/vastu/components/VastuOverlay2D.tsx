// src/domains/vastu/components/VastuOverlay2D.tsx

import React, { useMemo } from 'react';
import { useAppStore } from '@/store';
import { VASTU_ZONES_8, type VastuZone } from '../services/zones';
import { calculateBrahmasthan } from '../services/brahmasthan';
import { computeZoneGrid } from '../services/zoneGrid';
import type { Point2D } from '@/types/geometry';

export const VastuOverlay2D: React.FC = () => {
  const planBoundary = useAppStore((s) => s.planBoundary);
  const showVastu = useAppStore((s) => s.showVastuOverlay2D);
  const zoneCount = useAppStore((s) => s.vastuZoneCount);
  const northDeg = useAppStore((s) => s.vastuNorthDeg);
  const chakraMode = useAppStore((s) => s.vastuChakraMode);
  const showDivisions = useAppStore((s) => s.showVastuDivisionLines);

  const brahmasthan = useMemo(
    () => (planBoundary ? calculateBrahmasthan(planBoundary) : null),
    [planBoundary]
  );

  const grid = useMemo(
    () => (planBoundary && brahmasthan ? computeZoneGrid(planBoundary, brahmasthan, zoneCount, northDeg, chakraMode) : null),
    [planBoundary, brahmasthan, zoneCount, northDeg, chakraMode]
  );

  if (!showVastu || !brahmasthan || !planBoundary) return null;

  // Sectors reach a bit past the furthest boundary vertex.
  const maxDist = planBoundary.reduce(
    (max, p) => Math.max(max, Math.hypot(p.x - brahmasthan.x, p.y - brahmasthan.y)),
    0
  );

  // North marker: an arrow from the center toward north (world +Y, rotated by northDeg).
  const northAngle = Math.PI / 2 - (northDeg * Math.PI) / 180;
  const northTip = {
    x: brahmasthan.x + Math.cos(northAngle) * maxDist * 0.9,
    y: brahmasthan.y + Math.sin(northAngle) * maxDist * 0.9,
  };

  return (
    <g pointerEvents="none">
      {/* Legacy 8-sector color wash stays for the classic look (only in 8-zone mode). */}
      {zoneCount === 8 && (
        <g opacity={0.22}>
          {VASTU_ZONES_8.map((zone) => (
            <ZoneSector key={zone.direction} zone={zone} center={brahmasthan} radius={maxDist * 1.1} />
          ))}
        </g>
      )}

      {/* Sector division lines. */}
      {showDivisions && grid && (
        <g stroke="rgba(250, 204, 21, 0.55)" strokeWidth={1.5}>
          {grid.divisions.map((d, i) => (
            <line key={i} x1={d.a.x} y1={-d.a.y} x2={d.b.x} y2={-d.b.y} />
          ))}
        </g>
      )}

      {/* Zone labels. */}
      {grid && grid.labels.map((l, i) => (
        <text
          key={i}
          x={l.at.x}
          y={-l.at.y}
          fill="#fde68a"
          stroke="#1c1917"
          strokeWidth={0.6}
          paintOrder="stroke"
          fontSize={zoneCount === 32 ? maxDist * 0.03 : maxDist * 0.05}
          fontFamily="sans-serif"
          textAnchor="middle"
          dominantBaseline="middle"
        >
          {l.text}
        </text>
      ))}

      {/* Brahmasthan (center). */}
      <circle cx={brahmasthan.x} cy={-brahmasthan.y} r={maxDist / 6} fill="gold" opacity={0.3} stroke="goldenrod" strokeWidth={1} />

      {/* North marker. */}
      <line x1={brahmasthan.x} y1={-brahmasthan.y} x2={northTip.x} y2={-northTip.y} stroke="#ef4444" strokeWidth={2.5} />
      <circle cx={northTip.x} cy={-northTip.y} r={maxDist * 0.05} fill="#ef4444" />
      <text x={northTip.x} y={-northTip.y} fill="#fff" fontSize={maxDist * 0.05} fontWeight={700} textAnchor="middle" dominantBaseline="middle">N</text>
    </g>
  );
};

const ZoneSector: React.FC<{ zone: VastuZone; center: Point2D; radius: number }> = ({ zone, center, radius }) => {
  const path = useMemo(() => {
    // World angles are CCW; SVG Y is flipped, so we negate the y component of each point.
    const startAngle = zone.startAngle;
    const endAngle = zone.startAngle + zone.spanAngle;
    const x1 = center.x + radius * Math.cos(startAngle);
    const y1 = -center.y - radius * Math.sin(startAngle);
    const x2 = center.x + radius * Math.cos(endAngle);
    const y2 = -center.y - radius * Math.sin(endAngle);
    const largeArc = zone.spanAngle > Math.PI ? 1 : 0;
    // sweep-flag 0 because the Y-flip turns world-CCW into SVG-CW.
    return `M ${center.x} ${-center.y} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 0 ${x2} ${y2} Z`;
  }, [zone, center, radius]);

  return <path d={path} fill={zone.color} />;
};
