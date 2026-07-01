import { useState, useEffect } from 'react';
import {
  registerDynamicFinish,
  getDynamicFinishes,
  type FinishMaterial,
} from '@/domains/shared/materials/finishPalette';

function slugify(filename: string): string {
  return filename
    .replace(/\.(glb|gltf)$/i, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase();
}

function humanize(filename: string): string {
  return filename
    .replace(/\.(glb|gltf)$/i, '')
    .replace(/[-_]+/g, ' ')
    .replace(/\b1k\b/i, '(1K)')
    .replace(/\b2k\b/i, '(2K)')
    .replace(/\b4k\b/i, '(4K)')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/**
 * Fetches /walls/manifest.json and registers each discovered GLB/GLTF as a
 * dynamic wall finish. Returns the list so the Paint tool can render swatches.
 *
 * Safe to call from multiple components — registerDynamicFinish deduplicates.
 */
export function useGlbWallDiscovery(): readonly FinishMaterial[] {
  const [finishes, setFinishes] = useState<readonly FinishMaterial[]>(getDynamicFinishes);

  useEffect(() => {
    let cancelled = false;

    fetch('/walls/manifest.json')
      .then((r) => r.json())
      .then((files: string[]) => {
        if (cancelled) return;
        for (const file of files) {
          const id = `glb-${slugify(file)}`;
          registerDynamicFinish({
            id,
            name: humanize(file),
            category: 'wall',
            swatch: '#9a8a7a',
            color: '#9a8a7a',
            glbPath: `/walls/${file}`,
            roughness: 0.7,
          });
        }
        setFinishes([...getDynamicFinishes()]);
      })
      .catch(() => {});

    return () => { cancelled = true; };
  }, []);

  return finishes;
}
