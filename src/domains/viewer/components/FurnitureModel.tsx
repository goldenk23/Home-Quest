// src/domains/viewer/components/FurnitureModel.tsx

import React, { useMemo } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useGLTF, Clone } from '@react-three/drei';
import { useAppStore } from '@/store';
import { useCollidingFurnitureIds } from '@/domains/editor/hooks/useCollisions';
import { planTo3D } from '../services/transform';
import { getCatalogEntry, FURNITURE_CATALOG } from '../hooks/useAssetLoader';
import { prepareWhole, prepareVariants, footprintOf } from '../services/modelPrep';
import { renderProceduralPrefab } from './furniture/ProceduralPrefabs';
import type { FurnitureCatalogEntry } from '../hooks/useAssetLoader';
import type { FurnitureItem } from '@/types/editor';

const CM_TO_M = 0.01;

// Preload every catalog model (and any topper) so placed items appear without a load hitch.
Object.values(FURNITURE_CATALOG).forEach((c) => {
  if (c.model) useGLTF.preload(c.model);
  if (c.topper) useGLTF.preload(c.topper.model);
});

/**
 * Renders every placed furniture item. Items whose catalog entry has a `model` render as the
 * real glTF asset (scaled to fit their footprint and grounded); the rest fall back to a
 * procedural prefab. Colliding procedural items render red so the collision engine is visible.
 */
export const FurnitureInstances: React.FC = () => {
  const furniture = useAppStore(useShallow((s) => Object.values(s.furniture)));
  const colliding = useCollidingFurnitureIds();
  return (
    <group>
      {furniture.map((item) => {
        const catalog = getCatalogEntry(item.catalogId);
        return catalog.model ? (
          <ModelPiece key={item.id} item={item} catalog={catalog} />
        ) : (
          <ProceduralPiece key={item.id} item={item} catalog={catalog} colliding={colliding.has(item.id)} />
        );
      })}
    </group>
  );
};

/** A real glTF model fitted to the item's footprint and resting on the floor. */
const ModelPiece: React.FC<{ item: FurnitureItem; catalog: FurnitureCatalogEntry }> = React.memo(
  ({ item, catalog }) => {
    const { scene } = useGLTF(catalog.model!);

    const { object, fit, topY } = useMemo(() => {
      const inst =
        catalog.modelVariant !== undefined
          ? prepareVariants(scene)[catalog.modelVariant] ?? prepareWhole(scene)
          : prepareWhole(scene);
      const fp = footprintOf(inst);
      const tw = catalog.bounds.width * CM_TO_M;
      const td = catalog.bounds.depth * CM_TO_M;
      // Uniform scale so the model sits within its 2D footprint (keeps proportions).
      const fitScale = Math.min(tw / (fp.w || tw), td / (fp.d || td));
      // World-space height of the fitted base model, used to rest a topper on top.
      return { object: inst, fit: fitScale, topY: fp.h * fitScale };
    }, [scene, catalog]);

    const position = useMemo(() => {
      // The prepared model is already grounded (base at y = 0), so place it directly.
      const p = planTo3D(item.position, 0);
      return [p.x, 0, p.z] as [number, number, number];
    }, [item.position]);

    return (
      <group position={position} rotation={[0, item.rotation, 0]}>
        <Clone object={object} scale={fit * item.scale} />
        {catalog.topper && (
          <Topper
            model={catalog.topper.model}
            baseY={topY * item.scale}
            targetWidthM={catalog.bounds.width * CM_TO_M * (catalog.topper.widthFrac ?? 0.7)}
            scale={item.scale}
          />
        )}
      </group>
    );
  }
);
ModelPiece.displayName = 'ModelPiece';

/** A secondary model (e.g. a TV) resting centred on top of its host item, scaled to fit. */
const Topper: React.FC<{ model: string; baseY: number; targetWidthM: number; scale: number }> = ({
  model,
  baseY,
  targetWidthM,
  scale,
}) => {
  const { scene } = useGLTF(model);
  const { object, fit } = useMemo(() => {
    const inst = prepareWhole(scene);
    const fp = footprintOf(inst);
    const fitScale = targetWidthM / (fp.w || targetWidthM);
    return { object: inst, fit: fitScale };
  }, [scene, targetWidthM]);
  // The topper is grounded (base at y = 0), so lifting the group by the host's top height
  // rests it on the surface, centred on the footprint.
  return (
    <group position={[0, baseY, 0]}>
      <Clone object={object} scale={fit * scale} />
    </group>
  );
};

/** A procedural prefab sized to real-world dimensions (fallback when no model exists). */
const ProceduralPiece: React.FC<{ item: FurnitureItem; catalog: FurnitureCatalogEntry; colliding: boolean }> =
  React.memo(({ item, catalog, colliding }) => {
    const w = catalog.bounds.width * CM_TO_M * item.scale;
    const d = catalog.bounds.depth * CM_TO_M * item.scale;
    const h = catalog.bounds.height * CM_TO_M * item.scale;

    const position = useMemo(() => {
      const p = planTo3D(item.position, 0);
      // Box origin is its center, so lift it by half its height to sit on the floor.
      return [p.x, h / 2, p.z] as [number, number, number];
    }, [item.position, h]);

    return (
      <group position={position} rotation={[0, item.rotation, 0]}>
        {renderProceduralPrefab(item.catalogId, w, h, d, catalog.color, colliding)}
      </group>
    );
  });
ProceduralPiece.displayName = 'ProceduralPiece';
