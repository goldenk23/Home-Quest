// src/domains/viewer/services/modelPrep.ts
//
// Shared helpers for turning a loaded glTF scene into render-ready instances that always sit
// on the ground (y = 0) and are centred on their own footprint. Used by the furniture
// renderer (FurnitureModel) and the multi-plant splitting used by garden assets.
//
// Two preparation modes:
//   - prepareWhole:    the entire file is ONE object (a sofa, a table, a cabinet with doors).
//   - prepareVariants: the file PACKS several plants laid out side by side (Poly Haven ships
//                      shrubs/ferns/trees this way). Each individual plant is extracted as its
//                      own grounded instance.
//
// Results are cached per loaded scene (WeakMap) so repeated placements reuse the same prepared
// objects instead of re-cloning/re-measuring on every render.

import * as THREE from 'three';

interface PrepCache {
  whole?: THREE.Object3D;
  variants?: THREE.Object3D[];
}
const cache = new WeakMap<THREE.Object3D, PrepCache>();

function enableShadows(root: THREE.Object3D) {
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.isMesh) { mesh.castShadow = true; mesh.receiveShadow = true; }
  });
}

/**
 * Wraps the given members (clones) so the group's origin sits at the horizontal centre of
 * their combined footprint, with their lowest point resting on y = 0.
 */
function groundAndCentre(members: THREE.Object3D[]): THREE.Object3D {
  const inner = new THREE.Group();
  members.forEach((m) => inner.add(m));
  inner.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(inner);
  const centre = new THREE.Vector3();
  box.getCenter(centre);
  inner.position.set(-centre.x, -box.min.y, -centre.z);
  const wrapper = new THREE.Group();
  wrapper.add(inner);
  return wrapper;
}

/** Trailing single-letter token groups a plant's parts (bark_a + leaves_a) into one plant. */
function groupKeyOf(name: string): string {
  const m = name.match(/_([A-Za-z])$/);
  return m ? m[1].toLowerCase() : '__single';
}

/** The whole file as one grounded, centred instance (furniture, single props). */
export function prepareWhole(scene: THREE.Object3D): THREE.Object3D {
  let entry = cache.get(scene);
  if (entry?.whole) return entry.whole;
  const clone = scene.clone(true);
  enableShadows(clone);
  const whole = groundAndCentre([clone]);
  entry = entry ?? {};
  entry.whole = whole;
  cache.set(scene, entry);
  return whole;
}

/**
 * One grounded, centred instance per individual plant packed in the file. Plants are grouped
 * by the trailing `_a/_b` letter so a tree's bark+leaves stay together while four shrubs
 * spread along X become four separate instances.
 */
export function prepareVariants(scene: THREE.Object3D): THREE.Object3D[] {
  let entry = cache.get(scene);
  if (entry?.variants) return entry.variants;

  const groups = new Map<string, THREE.Object3D[]>();
  scene.children.forEach((child) => {
    const key = groupKeyOf(child.name);
    const arr = groups.get(key);
    if (arr) arr.push(child); else groups.set(key, [child]);
  });

  const variants: THREE.Object3D[] = [];
  groups.forEach((members) => {
    const clones = members.map((m) => {
      const c = m.clone(true);
      enableShadows(c);
      return c;
    });
    variants.push(groundAndCentre(clones));
  });

  entry = entry ?? {};
  entry.variants = variants;
  cache.set(scene, entry);
  return variants;
}

/** Footprint (metres) of a prepared instance: width (x), depth (z), height (y). */
export function footprintOf(obj: THREE.Object3D): { w: number; d: number; h: number } {
  const box = new THREE.Box3().setFromObject(obj);
  const size = new THREE.Vector3();
  box.getSize(size);
  return { w: size.x, d: size.z, h: size.y };
}
