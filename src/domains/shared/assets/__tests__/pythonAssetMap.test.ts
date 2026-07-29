/// <reference types="node" />
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  FURNITURE_NAME_TO_CATALOG,
  SYMBOL2D_PATH,
  FLOORING_TYPE_TO_MATERIAL,
} from '../pythonAssetMap';
import { FURNITURE_CATALOG } from '@/domains/viewer/hooks/useAssetLoader';
import { getFinishById } from '@/domains/shared/materials/finishPalette';

const PUBLIC = path.resolve(process.cwd(), 'public');

describe('pythonAssetMap — no dangling references', () => {
  it('every furniture name resolves to a real catalog id', () => {
    for (const [name, id] of Object.entries(FURNITURE_NAME_TO_CATALOG)) {
      expect(FURNITURE_CATALOG[id], `${name} -> ${id}`).toBeDefined();
    }
  });

  it('every 2D symbol belongs to a real catalog id and its PNG exists on disk', () => {
    for (const [id, p] of Object.entries(SYMBOL2D_PATH)) {
      expect(FURNITURE_CATALOG[id], id).toBeDefined();
      expect(fs.existsSync(path.join(PUBLIC, p)), `${id}: ${p}`).toBe(true);
    }
  });

  it('every flooring type maps to a real floor finish that has an image texture on disk', () => {
    for (const [type, id] of Object.entries(FLOORING_TYPE_TO_MATERIAL)) {
      const f = getFinishById(id);
      expect(f, `${type} -> ${id}`).not.toBeNull();
      expect(f?.imageTexture, id).toBeTruthy();
      expect(fs.existsSync(path.join(PUBLIC, f!.imageTexture!)), f!.imageTexture!).toBe(true);
    }
  });
});
