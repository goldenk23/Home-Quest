// src/domains/vastu/components/VastuOverlay2D.tsx

import React, { useMemo } from 'react';
import { useAppStore } from '@/store';
import { VASTU_ZONES_8, type VastuZone } from '../services/zones';
import { calculateBrahmasthan } from '../services/brahmasthan';
import type { Point2D } from '@/types/geometry';

export const VastuOverlay2D: React.FC = () => {
  const planBoundary = useAppStore((s) => s.planBoundary);
  const showVastu = useAppStore((s) => s.showVastuOverlay2D);

  const brahmasthan = useMemo(
    () => (planBoundary ? calculateBrahmasthan(planBoundary) : null),
    [planBoundary]
  );

  if (!showVastu || !brahmasthan || !planBoundary) return null;

  // Sectors reach a bit past the furthest boundary vertex.
  const maxDist = planBoundary.reduce(
    (max, p) => Math.max(max, Math.hypot(p.x - brahmasthan.x, p.y - brahmasthan.y)),
    0
  );

  return (
    <g opacity={0.3} pointerEvents="none">
      {VASTU_ZONES_8.map((zone) => (
        <ZoneSector key={zone.direction} zone={zone} center={brahmasthan} radius={maxDist * 1.1} />
      ))}
      <circle cx={brahmasthan.x} cy={-brahmasthan.y} r={maxDist / 6} fill="gold" opacity={0.4} stroke="goldenrod" strokeWidth={1} />
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
