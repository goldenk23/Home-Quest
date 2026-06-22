// src/domains/viewer/services/materials.ts

import * as THREE from 'three';

const materialCache = new Map<string, THREE.Material>();

function createBrickTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    // Base brick color
    ctx.fillStyle = '#b34730';
    ctx.fillRect(0, 0, 512, 512);

    // Add some noise for realism
    for(let i=0; i<10000; i++) {
        ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.1})`;
        ctx.fillRect(Math.random()*512, Math.random()*512, 2, 2);
    }

    // Mortar lines
    ctx.fillStyle = '#e0dbd1'; // Light grey mortar
    const brickW = 128; // 4 bricks per meter (25cm each)
    const brickH = 64;  // 8 bricks per meter (12.5cm each)
    const mortarW = 6;

    for (let y = 0; y < 512; y += brickH) {
      ctx.fillRect(0, y, 512, mortarW);
      const offset = (y / brickH) % 2 === 0 ? 0 : brickW / 2;
      for (let x = -brickW; x < 512 + brickW; x += brickW) {
        ctx.fillRect(x + offset, y, mortarW, brickH);
      }
    }
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1, 1);
  return texture;
}

function createBrickBumpMap() {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    // Bricks are white (raised)
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, 512, 512);

    // Mortar lines are black (recessed)
    ctx.fillStyle = '#000000';
    const brickW = 128;
    const brickH = 64;
    const mortarW = 6;

    for (let y = 0; y < 512; y += brickH) {
      // Horizontal mortar
      // We make the mortar slightly blurry/anti-aliased by using shadow or simple drawing
      ctx.fillRect(0, y, 512, mortarW);
      const offset = (y / brickH) % 2 === 0 ? 0 : brickW / 2;
      for (let x = -brickW; x < 512 + brickW; x += brickW) {
        // Vertical mortar
        ctx.fillRect(x + offset, y, mortarW, brickH);
      }
    }
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1, 1);
  return texture;
}

let sharedBrickTexture: THREE.CanvasTexture | null = null;
let sharedBrickBumpMap: THREE.CanvasTexture | null = null;

function getBrickTexture() {
    if (!sharedBrickTexture) sharedBrickTexture = createBrickTexture();
    return sharedBrickTexture;
}

function getBrickBumpMap() {
    if (!sharedBrickBumpMap) sharedBrickBumpMap = createBrickBumpMap();
    return sharedBrickBumpMap;
}

/** Factory per material id. Add new surfaces here. */
export const MATERIAL_DEFINITIONS: Record<string, () => THREE.Material> = {
  'default-wall': () => new THREE.MeshStandardMaterial({ 
      map: getBrickTexture(), 
      bumpMap: getBrickBumpMap(),
      bumpScale: 0.05, // 5cm bump depth for realistic lighting interaction
      roughness: 0.9, 
      metalness: 0 
  }),
  'brick-wall': () => new THREE.MeshStandardMaterial({ 
      map: getBrickTexture(), 
      bumpMap: getBrickBumpMap(),
      bumpScale: 0.05,
      roughness: 0.9, 
      metalness: 0 
  }),
  'default-floor': () => new THREE.MeshStandardMaterial({ color: '#d4c5a9', roughness: 0.7, metalness: 0 }),
  'tile-floor': () => new THREE.MeshStandardMaterial({ color: '#e8e0d0', roughness: 0.4, metalness: 0.1 }),
};

/** Returns the one shared material instance for an id (falls back to default‑wall). */
export function getMaterial(materialId: string): THREE.Material {
  const cached = materialCache.get(materialId);
  if (cached) return cached;
  const factory = MATERIAL_DEFINITIONS[materialId] ?? MATERIAL_DEFINITIONS['default-wall'];
  const material = factory();
  materialCache.set(materialId, material);
  return material;
}
