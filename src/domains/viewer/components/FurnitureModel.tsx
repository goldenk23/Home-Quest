// src/domains/viewer/components/FurnitureModel.tsx

import React, { useMemo } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useAppStore } from '@/store';
import { planTo3D } from '../services/transform';
import { useFurnitureModel, FURNITURE_CATALOG } from '../hooks/useAssetLoader';
import type { FurnitureItem } from '@/types/editor';

/** Renders every placed furniture item. */
export const FurnitureInstances: React.FC = () => {
  const furniture = useAppStore(useShallow((s) => Object.values(s.furniture)));
  return (
    <group>
      {furniture.map((item) => (
        <FurniturePiece key={item.id} item={item} />
      ))}
    </group>
  );
};

const FurniturePiece: React.FC<{ item: FurnitureItem }> = React.memo(({ item }) => {
  const model = useFurnitureModel(item.catalogId, item.id);
  const catalog = FURNITURE_CATALOG[item.catalogId];
  const scale = (catalog?.scale ?? 0.01) * item.scale;
  const yOffset = catalog?.yOffset ?? 0;

  const position = useMemo(() => {
    const p = planTo3D(item.position, 0);
    return [p.x, p.y + yOffset, p.z] as [number, number, number];
  }, [item.position, yOffset]);

  return <primitive object={model} position={position} rotation={[0, item.rotation, 0]} scale={[scale, scale, scale]} />;
});

FurniturePiece.displayName = 'FurniturePiece';
