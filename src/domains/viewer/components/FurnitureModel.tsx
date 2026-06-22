// src/domains/viewer/components/FurnitureModel.tsx

import React, { useMemo } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useAppStore } from '@/store';
import { useCollidingFurnitureIds } from '@/domains/editor/hooks/useCollisions';
import { planTo3D } from '../services/transform';
import { getCatalogEntry } from '../hooks/useAssetLoader';
import type { FurnitureItem } from '@/types/editor';

const CM_TO_M = 0.01;

/**
 * Renders every placed furniture item as a procedural box sized to its real-world
 * dimensions. Colliding items render red so the collision engine is visible in 3D.
 */
export const FurnitureInstances: React.FC = () => {
  const furniture = useAppStore(useShallow((s) => Object.values(s.furniture)));
  const colliding = useCollidingFurnitureIds();
  return (
    <group>
      {furniture.map((item) => (
        <FurniturePiece key={item.id} item={item} colliding={colliding.has(item.id)} />
      ))}
    </group>
  );
};

const FurniturePiece: React.FC<{ item: FurnitureItem; colliding: boolean }> = React.memo(
  ({ item, colliding }) => {
    const catalog = getCatalogEntry(item.catalogId);
    const w = (catalog.bounds.width * CM_TO_M) * item.scale;
    const d = (catalog.bounds.depth * CM_TO_M) * item.scale;
    const h = (catalog.bounds.height * CM_TO_M) * item.scale;

    const position = useMemo(() => {
      const p = planTo3D(item.position, 0);
      // Box origin is its center, so lift it by half its height to sit on the floor.
      return [p.x, h / 2, p.z] as [number, number, number];
    }, [item.position, h]);

    return (
      <mesh position={position} rotation={[0, item.rotation, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, h, d]} />
        <meshStandardMaterial
          color={colliding ? '#ef4444' : catalog.color}
          roughness={0.7}
          metalness={0.05}
        />
      </mesh>
    );
  }
);

FurniturePiece.displayName = 'FurniturePiece';
