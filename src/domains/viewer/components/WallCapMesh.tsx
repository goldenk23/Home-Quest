// src/domains/viewer/components/WallCapMesh.tsx

import React, { useMemo } from 'react';
import { createWallGeometry } from '../services/extrusion';
import { ceilingMaterial } from './SlabMesh';
import type { Point2D } from '@/types/geometry';
import type { MiterOffsets } from '@/domains/editor/services/wallOps';

const CM_TO_M = 0.01;

/**
 * Caps the TOP of one wall, filling from the wall's top up to the floor above. Room slabs
 * only reach the wall centrelines, so the outer half of an exterior wall's top is left open
 * — that leftover strip is what shows as a notch between the ceiling and the storey above.
 * This builds a solid box with the exact wall footprint (reusing the wall geometry builder,
 * so miters line up) sitting in that gap, making the wall read as continuous up to the slab.
 *
 * Same plaster material as the slab; where it overlaps a room slab on the wall's inner half
 * the two surfaces are coplanar with identical colour and normal, so the overlap is invisible.
 */
interface WallCapMeshProps {
  start: Point2D;
  end: Point2D;
  thickness: number;
  /** Wall top in cm (the cap's underside, local to this floor's base). */
  baseCm: number;
  /** Cap height in cm; its top lands on the floor above. */
  capHeightCm: number;
  offsets?: MiterOffsets;
}

export const WallCapMesh: React.FC<WallCapMeshProps> = React.memo(
  ({ start, end, thickness, baseCm, capHeightCm, offsets }) => {
    const geometry = useMemo(() => {
      const g = createWallGeometry(start, end, thickness, capHeightCm, offsets, []);
      g.translate(0, baseCm * CM_TO_M, 0);
      return g;
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [start.x, start.y, end.x, end.y, thickness, baseCm, capHeightCm, JSON.stringify(offsets ?? null)]);

    if (capHeightCm <= 0) return null;
    return <mesh geometry={geometry} material={ceilingMaterial} castShadow receiveShadow />;
  }
);

WallCapMesh.displayName = 'WallCapMesh';
