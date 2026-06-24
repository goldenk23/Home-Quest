// src/domains/viewer/services/materials.ts

import * as THREE from 'three';
import {
  ALL_FINISHES,
  FLOOR_FINISHES,
  getFinishById,
  type FinishMaterial,
  type FinishTexture,
} from '@/domains/shared/materials/finishPalette';

const materialCache = new Map<string, THREE.Material>();
/** Floors get their own cached material instance: same finish look, different depth bias. */
const floorMaterialCache = new Map<string, THREE.Material>();

// ----------------------------------------------------------------------------
// Procedural texture generators. Each draws a 512×512 tile onto a <canvas> (works in
// any browser; no external image assets to load) and returns a RepeatWrapping
// CanvasTexture. The tile is authored to cover a 1m × 1m area; the caller sets
// texture.repeat to (1/repeatMeters) so the pattern lands at the right physical size on
// every surface (floor geometry UVs are already in meters).
// ----------------------------------------------------------------------------

function makeCanvas(size = 512): { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D } | null {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  return { canvas, ctx };
}

function finalizeTexture(canvas: HTMLCanvasElement, repeatMeters: number): THREE.CanvasTexture {
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  // A "1m tile" repeated `1/repeatMeters` times per meter = repeatMeters-meter tiles.
  const r = repeatMeters > 0 ? 1 / repeatMeters : 1;
  texture.repeat.set(r, r);
  return texture;
}

function createBrickTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.25);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#b34730';
  ctx.fillRect(0, 0, 512, 512);

  for (let i = 0; i < 10000; i++) {
    ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.1})`;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, 2, 2);
  }

  ctx.fillStyle = '#e0dbd1';
  const brickW = 128;
  const brickH = 64;
  const mortarW = 6;

  for (let y = 0; y < 512; y += brickH) {
    ctx.fillRect(0, y, 512, mortarW);
    const offset = (y / brickH) % 2 === 0 ? 0 : brickW / 2;
    for (let x = -brickW; x < 512 + brickW; x += brickW) {
      ctx.fillRect(x + offset, y, mortarW, brickH);
    }
  }

  return finalizeTexture(canvas, 0.25);
}

function createBrickBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.25);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  ctx.fillStyle = '#000000';
  const brickW = 128;
  const brickH = 64;
  const mortarW = 6;

  for (let y = 0; y < 512; y += brickH) {
    ctx.fillRect(0, y, 512, mortarW);
    const offset = (y / brickH) % 2 === 0 ? 0 : brickW / 2;
    for (let x = -brickW; x < 512 + brickW; x += brickW) {
      ctx.fillRect(x + offset, y, mortarW, brickH);
    }
  }

  return finalizeTexture(canvas, 0.25);
}

/** Square floor tiles with thin grout lines. Tinted by the material color at build time. */
function createTileTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.45);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  // Subtle per-tile variation so a large floor isn't a flat sheet.
  for (let i = 0; i < 4000; i++) {
    ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.04})`;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, 3, 3);
  }

  // Grout lines (drawn as a grid; the tile is a single unit so one set of lines reads as
  // the seam between four tiles when repeated).
  ctx.fillStyle = 'rgba(60,60,60,0.55)';
  ctx.fillRect(0, 0, 512, 4);
  ctx.fillRect(0, 0, 4, 512);

  return finalizeTexture(canvas, 0.45);
}

/** Horizontal wood planks with grain noise and a darker seam between boards. */
function createWoodTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.18);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  const plankH = 64; // 8 planks across the 1m tile
  for (let y = 0; y < 512; y += plankH) {
    // Long grain streaks inside each plank.
    for (let i = 0; i < 60; i++) {
      ctx.fillStyle = `rgba(60,40,20,${Math.random() * 0.10})`;
      const yy = y + Math.random() * plankH;
      ctx.fillRect(0, yy, 512, 1 + Math.random() * 2);
    }
    // Dark seam between boards.
    ctx.fillStyle = 'rgba(40,25,10,0.5)';
    ctx.fillRect(0, y, 512, 2);
  }

  return finalizeTexture(canvas, 0.18);
}

/** Soft diagonal veining on a light field — reads as marble when tinted. */
function createMarbleTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 1.5);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  ctx.lineCap = 'round';
  for (let v = 0; v < 14; v++) {
    ctx.strokeStyle = `rgba(120,120,130,${0.08 + Math.random() * 0.12})`;
    ctx.lineWidth = 1 + Math.random() * 3;
    ctx.beginPath();
    let x = Math.random() * 512;
    let y = Math.random() * 512;
    ctx.moveTo(x, y);
    for (let s = 0; s < 12; s++) {
      x += (Math.random() - 0.5) * 120;
      y += (Math.random() - 0.5) * 120;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  return finalizeTexture(canvas, 1.5);
}

/** Fine speckle — granite. Dense small dots over a dark field. */
function createGraniteTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 1.0);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  for (let i = 0; i < 18000; i++) {
    const shade = Math.random();
    ctx.fillStyle =
      shade < 0.5 ? `rgba(0,0,0,${0.15 + Math.random() * 0.25})`
        : shade < 0.8 ? `rgba(255,255,255,${0.05 + Math.random() * 0.1})`
          : `rgba(120,120,140,${0.1 + Math.random() * 0.15})`;
    const r = Math.random() * 2.5;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, r, r);
  }

  return finalizeTexture(canvas, 1.0);
}

/** Marble-chip terrazzo: scattered color chips over a light binder. */
function createTerrazzoTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 1.2);
  const { canvas, ctx } = made;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);

  const chipColors = ['rgba(180,180,190,0.85)', 'rgba(120,120,140,0.8)', 'rgba(200,190,170,0.8)', 'rgba(90,90,100,0.7)'];
  for (let i = 0; i < 260; i++) {
    ctx.fillStyle = chipColors[i % chipColors.length];
    ctx.save();
    ctx.translate(Math.random() * 512, Math.random() * 512);
    ctx.rotate(Math.random() * Math.PI);
    const w = 8 + Math.random() * 26;
    const h = 5 + Math.random() * 12;
    ctx.fillRect(-w / 2, -h / 2, w, h);
    ctx.restore();
  }

  return finalizeTexture(canvas, 1.2);
}

/**
 * Lawn grass: a dense field of short blade strokes in several greens over a soil-flecked
 * base. Drawn in full colour (not on a white base) so the ground material can use a neutral
 * white tint and show the grass exactly as authored. Designed to tile seamlessly-ish at a
 * small physical size and to break up obvious repetition with random clumps.
 */
function createGrassTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 2);
  const { canvas, ctx } = made;

  // Base lawn fill with a vertical gradient so clumps don't read as a flat sheet.
  const grad = ctx.createLinearGradient(0, 0, 0, 512);
  grad.addColorStop(0, '#43702f');
  grad.addColorStop(1, '#4e8235');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 512, 512);

  // Soft darker/lighter clumps to vary the field and hide the tile seam.
  for (let i = 0; i < 90; i++) {
    const x = Math.random() * 512;
    const y = Math.random() * 512;
    const r = 18 + Math.random() * 60;
    const light = Math.random() > 0.5;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, light ? 'rgba(120,165,70,0.30)' : 'rgba(40,70,28,0.30)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }

  // Thousands of tiny blade strokes in assorted greens (and a few dry-yellow ones).
  const blades = ['#5d9a3d', '#6cab46', '#3c6a2a', '#7bb152', '#356026', '#8aa84f'];
  for (let i = 0; i < 9000; i++) {
    ctx.strokeStyle = blades[(Math.random() * blades.length) | 0];
    ctx.lineWidth = 1;
    const x = Math.random() * 512;
    const y = Math.random() * 512;
    const len = 3 + Math.random() * 7;
    const lean = (Math.random() - 0.5) * 4;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + lean, y - len);
    ctx.stroke();
  }

  return finalizeTexture(canvas, 2);
}

// ---- Additional floor / wall texture generators ---------------------------
// All authored on a 1m tile (white base, tinted at material-build time unless noted).

/** Two-tone checkerboard with grout — classic lobby/kitchen tile. */
function createCheckerTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.6);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  // 2×2 checker on the tile so a repeat lands cleanly.
  ctx.fillStyle = 'rgba(40,40,48,0.78)';
  ctx.fillRect(0, 0, 256, 256);
  ctx.fillRect(256, 256, 256, 256);
  // Grout seams.
  ctx.fillStyle = 'rgba(90,90,90,0.5)';
  ctx.fillRect(0, 0, 512, 4);
  ctx.fillRect(0, 0, 4, 512);
  ctx.fillRect(0, 252, 512, 4);
  ctx.fillRect(252, 0, 4, 512);
  return finalizeTexture(canvas, 0.6);
}

/** Wood laid in a herringbone (zig‑zag) pattern. */
function createHerringboneTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.5);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  const plankW = 128, plankH = 42;
  const drawPlank = (cx: number, cy: number, ang: number) => {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(ang);
    // plank body shade
    ctx.fillStyle = `rgba(120,80,40,${0.10 + Math.random() * 0.12})`;
    ctx.fillRect(-plankW / 2, -plankH / 2, plankW, plankH);
    // grain streaks
    for (let i = 0; i < 10; i++) {
      ctx.fillStyle = `rgba(70,45,20,${Math.random() * 0.12})`;
      ctx.fillRect(-plankW / 2, -plankH / 2 + Math.random() * plankH, plankW, 1);
    }
    // edge seams
    ctx.strokeStyle = 'rgba(40,25,10,0.55)';
    ctx.lineWidth = 2;
    ctx.strokeRect(-plankW / 2, -plankH / 2, plankW, plankH);
    ctx.restore();
  };
  const step = 96;
  for (let y = -step; y < 512 + step; y += step) {
    for (let x = -step; x < 512 + step; x += step * 2) {
      drawPlank(x, y, Math.PI / 4);
      drawPlank(x + step, y, -Math.PI / 4);
    }
  }
  return finalizeTexture(canvas, 0.5);
}

/** Riven slate: irregular dark cleft tiles. */
function createSlateTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.5);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  // Cleft blotches.
  for (let i = 0; i < 700; i++) {
    const g = Math.random();
    ctx.fillStyle = g < 0.5 ? `rgba(0,0,0,${Math.random() * 0.22})` : `rgba(255,255,255,${Math.random() * 0.10})`;
    const w = 6 + Math.random() * 40, h = 6 + Math.random() * 40;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, w, h);
  }
  // Irregular tile seams (2×2 grid, slightly jittered look via thicker dark lines).
  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.fillRect(0, 0, 512, 5);
  ctx.fillRect(0, 0, 5, 512);
  ctx.fillRect(0, 254, 512, 5);
  ctx.fillRect(254, 0, 5, 512);
  return finalizeTexture(canvas, 0.5);
}

/** Cork: warm granular cork board. */
function createCorkTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.3);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 9000; i++) {
    const t = Math.random();
    ctx.fillStyle = t < 0.6 ? `rgba(150,100,55,${0.10 + Math.random() * 0.25})`
      : t < 0.85 ? `rgba(90,55,25,${0.12 + Math.random() * 0.25})`
        : `rgba(210,170,120,${0.10 + Math.random() * 0.2})`;
    const w = 3 + Math.random() * 8, h = 2 + Math.random() * 5;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, w, h);
  }
  return finalizeTexture(canvas, 0.3);
}

/** Sandstone: warm layered sedimentary bands with grain. */
function createSandstoneTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.6);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  // Soft horizontal sediment bands.
  for (let y = 0; y < 512; y += 8 + Math.random() * 10) {
    ctx.fillStyle = `rgba(150,110,60,${Math.random() * 0.10})`;
    ctx.fillRect(0, y, 512, 4 + Math.random() * 6);
  }
  // Fine grain.
  for (let i = 0; i < 8000; i++) {
    ctx.fillStyle = `rgba(120,85,40,${Math.random() * 0.08})`;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, 2, 2);
  }
  // Block seams.
  ctx.fillStyle = 'rgba(90,65,30,0.4)';
  ctx.fillRect(0, 0, 512, 4);
  ctx.fillRect(0, 0, 4, 512);
  return finalizeTexture(canvas, 0.6);
}

/** Vinyl sheet: subtle mottled marbled sheen, low contrast. */
function createVinylTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.3);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 60; i++) {
    const x = Math.random() * 512, y = Math.random() * 512, r = 30 + Math.random() * 90;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(0,0,0,${Math.random() * 0.05})`);
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }
  // faint seams every half tile (plank vinyl)
  ctx.fillStyle = 'rgba(120,120,120,0.18)';
  ctx.fillRect(0, 0, 512, 2);
  ctx.fillRect(0, 256, 512, 2);
  return finalizeTexture(canvas, 0.3);
}

/** Woven coir/door mat: tight cross-hatched weave. */
function createMatTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.25);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  const cell = 32;
  for (let y = 0; y < 512; y += cell) {
    for (let x = 0; x < 512; x += cell) {
      const overUnder = ((x / cell) + (y / cell)) % 2 === 0;
      ctx.fillStyle = `rgba(80,55,25,${overUnder ? 0.28 : 0.14})`;
      if (overUnder) {
        // horizontal strand on top
        ctx.fillRect(x + 1, y + cell * 0.28, cell - 2, cell * 0.44);
      } else {
        // vertical strand on top
        ctx.fillRect(x + cell * 0.28, y + 1, cell * 0.44, cell - 2);
      }
    }
  }
  // grain fleck
  for (let i = 0; i < 3000; i++) {
    ctx.fillStyle = `rgba(40,25,10,${Math.random() * 0.12})`;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, 1, 2);
  }
  return finalizeTexture(canvas, 0.25);
}

/** Carpet: dense soft fibre flecks for a matte woven look. */
function createCarpetTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.5);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 22000; i++) {
    const v = Math.random();
    ctx.fillStyle = v < 0.5 ? `rgba(0,0,0,${Math.random() * 0.10})` : `rgba(255,255,255,${Math.random() * 0.10})`;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, 2, 2);
  }
  return finalizeTexture(canvas, 0.5);
}

/** Bare concrete: broad soft blotches + pinholes. Drawn near-white, tinted at build. */
function createConcreteTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 1.5);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 70; i++) {
    const x = Math.random() * 512, y = Math.random() * 512, r = 40 + Math.random() * 130;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    const dark = Math.random() > 0.5;
    g.addColorStop(0, dark ? `rgba(0,0,0,${Math.random() * 0.08})` : `rgba(255,255,255,${Math.random() * 0.06})`);
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }
  for (let i = 0; i < 2500; i++) {
    ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.12})`;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, 1, 1);
  }
  return finalizeTexture(canvas, 1.5);
}

/** Stacked stone cladding: irregular courses of stone with mortar. */
function createStoneTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.5);
  const { canvas, ctx } = made;
  ctx.fillStyle = 'rgba(60,55,48,0.6)'; // mortar field
  ctx.fillRect(0, 0, 512, 512);
  const courseH = 64;
  for (let y = 0; y < 512; y += courseH) {
    let x = -Math.random() * 60;
    while (x < 512) {
      const w = 40 + Math.random() * 80;
      const pad = 3;
      const shade = 120 + Math.random() * 80;
      ctx.fillStyle = `rgb(${shade},${shade - 8},${shade - 18})`;
      ctx.fillRect(x + pad, y + pad, w - pad, courseH - pad);
      // speckle on the stone
      for (let i = 0; i < 30; i++) {
        ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.18})`;
        ctx.fillRect(x + pad + Math.random() * (w - pad), y + pad + Math.random() * (courseH - pad), 2, 2);
      }
      x += w;
    }
  }
  return finalizeTexture(canvas, 0.5);
}

/** Vertical wood panelling: boards split by shadow grooves, with grain. */
function createWoodPanelTexture(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.22);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 512, 512);
  const boardW = 85;
  for (let x = 0; x < 512; x += boardW) {
    for (let i = 0; i < 60; i++) {
      ctx.fillStyle = `rgba(60,40,20,${Math.random() * 0.10})`;
      const xx = x + Math.random() * boardW;
      ctx.fillRect(xx, 0, 1 + Math.random() * 2, 512);
    }
    // groove between boards
    ctx.fillStyle = 'rgba(35,22,10,0.5)';
    ctx.fillRect(x, 0, 3, 512);
  }
  return finalizeTexture(canvas, 0.22);
}


// reads its LUMINANCE per pixel and perturbs the surface normal, so light catches the relief
// — plank seams sink, tile grout sits below the tiles, stone gets micro-roughness. This is
// the difference between a "printed sticker" floor and a real material, and it costs nothing
// at runtime (it's just another sampled texture; no extra geometry, no extra passes).
//
// Each generator mirrors the GEOMETRY of its colour texture (seams, grout, veins) on a flat
// mid-grey field so only the structural features show as relief.
// ----------------------------------------------------------------------------

/** Wood: each plank face is flat mid-grey; the seam between boards is a dark groove, with a
 *  hint of long grain so the surface isn't glassy. */
function createWoodBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.18);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#bdbdbd';
  ctx.fillRect(0, 0, 512, 512);
  const plankH = 64;
  for (let y = 0; y < 512; y += plankH) {
    for (let i = 0; i < 40; i++) {
      ctx.fillStyle = `rgba(255,255,255,${Math.random() * 0.06})`;
      const yy = y + Math.random() * plankH;
      ctx.fillRect(0, yy, 512, 1);
    }
    ctx.fillStyle = 'rgba(0,0,0,0.85)';
    ctx.fillRect(0, y, 512, 2);
  }
  return finalizeTexture(canvas, 0.18);
}

/** Tile: flat tile faces with the grout lines cut in as dark grooves. */
function createTileBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.45);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#cfcfcf';
  ctx.fillRect(0, 0, 512, 512);
  ctx.fillStyle = 'rgba(0,0,0,0.9)';
  ctx.fillRect(0, 0, 512, 6);
  ctx.fillRect(0, 0, 6, 512);
  return finalizeTexture(canvas, 0.45);
}

/** Marble: soft veins as gentle relief. */
function createMarbleBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 1.5);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#808080';
  ctx.fillRect(0, 0, 512, 512);
  ctx.lineCap = 'round';
  for (let v = 0; v < 14; v++) {
    ctx.strokeStyle = `rgba(0,0,0,${0.12 + Math.random() * 0.12})`;
    ctx.lineWidth = 1 + Math.random() * 3;
    ctx.beginPath();
    let x = Math.random() * 512;
    let y = Math.random() * 512;
    ctx.moveTo(x, y);
    for (let s = 0; s < 12; s++) {
      x += (Math.random() - 0.5) * 120;
      y += (Math.random() - 0.5) * 120;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  return finalizeTexture(canvas, 1.5);
}

/** Granite / terrazzo: dense fine speckle gives a believable stippled micro-relief. */
function createSpeckleBumpMap(repeatMeters: number): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), repeatMeters);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#909090';
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 14000; i++) {
    const v = Math.random();
    ctx.fillStyle = v < 0.5 ? `rgba(0,0,0,${Math.random() * 0.4})` : `rgba(255,255,255,${Math.random() * 0.3})`;
    const r = Math.random() * 2.2;
    ctx.fillRect(Math.random() * 512, Math.random() * 512, r, r);
  }
  return finalizeTexture(canvas, repeatMeters);
}

/** Grass: dense short blade strokes give the lawn a soft, irregular micro-relief. */
function createGrassBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 2);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#808080';
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 9000; i++) {
    const bright = Math.random() > 0.5;
    ctx.strokeStyle = bright ? `rgba(255,255,255,${0.2 + Math.random() * 0.5})` : `rgba(0,0,0,${0.2 + Math.random() * 0.5})`;
    ctx.lineWidth = 1;
    const x = Math.random() * 512;
    const y = Math.random() * 512;
    const len = 3 + Math.random() * 7;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + (Math.random() - 0.5) * 4, y - len);
    ctx.stroke();
  }
  return finalizeTexture(canvas, 2);
}

/** Mat weave: raised cross-hatched strands. */
function createMatBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.25);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#707070';
  ctx.fillRect(0, 0, 512, 512);
  const cell = 32;
  for (let y = 0; y < 512; y += cell) {
    for (let x = 0; x < 512; x += cell) {
      const overUnder = ((x / cell) + (y / cell)) % 2 === 0;
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      if (overUnder) ctx.fillRect(x + 1, y + cell * 0.28, cell - 2, cell * 0.44);
      else ctx.fillRect(x + cell * 0.28, y + 1, cell * 0.44, cell - 2);
    }
  }
  return finalizeTexture(canvas, 0.25);
}

/** Herringbone: plank seams as grooves. */
function createHerringboneBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.5);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#bdbdbd';
  ctx.fillRect(0, 0, 512, 512);
  const plankW = 128, plankH = 42;
  const stroke = (cx: number, cy: number, ang: number) => {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(ang);
    ctx.strokeStyle = 'rgba(0,0,0,0.85)';
    ctx.lineWidth = 2;
    ctx.strokeRect(-plankW / 2, -plankH / 2, plankW, plankH);
    ctx.restore();
  };
  const step = 96;
  for (let y = -step; y < 512 + step; y += step) {
    for (let x = -step; x < 512 + step; x += step * 2) {
      stroke(x, y, Math.PI / 4);
      stroke(x + step, y, -Math.PI / 4);
    }
  }
  return finalizeTexture(canvas, 0.5);
}

/** Stone cladding: deep mortar grooves between raised stones. */
function createStoneBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.5);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#202020'; // recessed mortar
  ctx.fillRect(0, 0, 512, 512);
  const courseH = 64;
  for (let y = 0; y < 512; y += courseH) {
    let x = -((y / courseH) % 2) * 40;
    while (x < 512) {
      const w = 40 + Math.random() * 80;
      ctx.fillStyle = '#d8d8d8';
      ctx.fillRect(x + 3, y + 3, w - 5, courseH - 5);
      x += w;
    }
  }
  return finalizeTexture(canvas, 0.5);
}

/** Wood panel: shadow grooves between vertical boards. */
function createWoodPanelBumpMap(): THREE.CanvasTexture {
  const made = makeCanvas();
  if (!made) return finalizeTexture(document.createElement('canvas'), 0.22);
  const { canvas, ctx } = made;
  ctx.fillStyle = '#c8c8c8';
  ctx.fillRect(0, 0, 512, 512);
  const boardW = 85;
  for (let x = 0; x < 512; x += boardW) {
    ctx.fillStyle = 'rgba(0,0,0,0.9)';
    ctx.fillRect(x, 0, 3, 512);
  }
  return finalizeTexture(canvas, 0.22);
}

const bumpCache = new Map<FinishTexture, THREE.CanvasTexture>();

/** Shared bump map for a texture kind (cached). Brick keeps its own dedicated bump map. */
function getBumpTexture(kind: FinishTexture): THREE.CanvasTexture | null {
  const existing = bumpCache.get(kind);
  if (existing) return existing;
  let tex: THREE.CanvasTexture | null;
  switch (kind) {
    case 'wood': tex = createWoodBumpMap(); break;
    case 'tile': tex = createTileBumpMap(); break;
    case 'marble': tex = createMarbleBumpMap(); break;
    case 'granite': tex = createSpeckleBumpMap(1.0); break;
    case 'terrazzo': tex = createSpeckleBumpMap(1.2); break;
    case 'grass': tex = createGrassBumpMap(); break;
    case 'mat': tex = createMatBumpMap(); break;
    case 'vinyl': tex = createTileBumpMap(); break;
    case 'herringbone': tex = createHerringboneBumpMap(); break;
    case 'checker': tex = createTileBumpMap(); break;
    case 'slate': tex = createSpeckleBumpMap(0.5); break;
    case 'cork': tex = createSpeckleBumpMap(0.3); break;
    case 'sandstone': tex = createSpeckleBumpMap(0.6); break;
    case 'carpet': tex = createGrassBumpMap(); break;
    case 'concrete': tex = createSpeckleBumpMap(1.5); break;
    case 'stone': tex = createStoneBumpMap(); break;
    case 'woodpanel': tex = createWoodPanelBumpMap(); break;
    default: tex = null;
  }
  if (tex) bumpCache.set(kind, tex);
  return tex;
}

/** How much relief each material shows. Small values — bump maps exaggerate fast. */
const BUMP_SCALE: Record<FinishTexture, number> = {
  wood: 0.02,
  tile: 0.03,
  marble: 0.006,
  granite: 0.012,
  terrazzo: 0.02,
  grass: 0.05,
  mat: 0.03,
  vinyl: 0.004,
  herringbone: 0.02,
  checker: 0.03,
  slate: 0.025,
  cork: 0.012,
  sandstone: 0.02,
  carpet: 0.02,
  concrete: 0.01,
  stone: 0.06,
  woodpanel: 0.025,
};

// ----------------------------------------------------------------------------
// Texture singletons. Cached so painting a hundred rooms with the same tile reuses one
// GPU texture. Keyed by FinishTexture kind.
// ----------------------------------------------------------------------------

const textureCache = new Map<FinishTexture, THREE.CanvasTexture>();

function getTexture(kind: FinishTexture): THREE.CanvasTexture {
  const existing = textureCache.get(kind);
  if (existing) return existing;
  let tex: THREE.CanvasTexture;
  switch (kind) {
    case 'tile': tex = createTileTexture(); break;
    case 'wood': tex = createWoodTexture(); break;
    case 'marble': tex = createMarbleTexture(); break;
    case 'granite': tex = createGraniteTexture(); break;
    case 'terrazzo': tex = createTerrazzoTexture(); break;
    case 'grass': tex = createGrassTexture(); break;
    case 'mat': tex = createMatTexture(); break;
    case 'vinyl': tex = createVinylTexture(); break;
    case 'herringbone': tex = createHerringboneTexture(); break;
    case 'checker': tex = createCheckerTexture(); break;
    case 'slate': tex = createSlateTexture(); break;
    case 'cork': tex = createCorkTexture(); break;
    case 'sandstone': tex = createSandstoneTexture(); break;
    case 'carpet': tex = createCarpetTexture(); break;
    case 'concrete': tex = createConcreteTexture(); break;
    case 'stone': tex = createStoneTexture(); break;
    case 'woodpanel': tex = createWoodPanelTexture(); break;
  }
  textureCache.set(kind, tex);
  return tex;
}

/**
 * Returns the shared procedural texture for a kind, CLONED and re-tinted to a neutral base
 * so callers (e.g. furniture tabletops) can apply their own material colour over it. Reuses
 * the cached texture data, so this adds no new GPU memory per call. `repeatMeters` sets the
 * physical tile/plank size on the surface.
 */
export function getProceduralTexture(kind: FinishTexture, repeatMeters: number): THREE.CanvasTexture {
  const base = getTexture(kind);
  const tex = base.clone();
  tex.needsUpdate = true;
  const r = repeatMeters > 0 ? 1 / repeatMeters : 1;
  tex.repeat.set(r, r);
  return tex;
}

// Shared (cached) texture + bump variants, keyed by kind+repeat. Unlike getProceduralTexture
// these return ONE stable instance per key, so callers that reference them inline in JSX
// (e.g. furniture prefab materials, re-evaluated on every React render) don't allocate or
// leak a new GPU texture each render. Use these whenever the texture is referenced from a
// render path rather than built once into a cached material.
const sharedColorCache = new Map<string, THREE.CanvasTexture>();
const sharedBumpCache = new Map<string, THREE.CanvasTexture>();

export function getSharedProceduralTexture(kind: FinishTexture, repeatMeters: number): THREE.CanvasTexture {
  const key = `${kind}:${repeatMeters}`;
  const cached = sharedColorCache.get(key);
  if (cached) return cached;
  const tex = getProceduralTexture(kind, repeatMeters);
  sharedColorCache.set(key, tex);
  return tex;
}

/** Shared bump map for a kind+repeat, or null if the kind has no bump generator. */
export function getSharedProceduralBump(kind: FinishTexture, repeatMeters: number): THREE.CanvasTexture | null {
  const key = `${kind}:${repeatMeters}`;
  const cached = sharedBumpCache.get(key);
  if (cached) return cached;
  const base = getBumpTexture(kind);
  if (!base) return null;
  const tex = base.clone();
  tex.needsUpdate = true;
  const r = repeatMeters > 0 ? 1 / repeatMeters : 1;
  tex.repeat.set(r, r);
  sharedBumpCache.set(key, tex);
  return tex;
}

/** Per-kind bump scale for furniture surfaces (exposed for inline JSX materials). */
export function bumpScaleFor(kind: FinishTexture): number {
  return BUMP_SCALE[kind];
}

// Brick is shared with the legacy 'default-wall'/'brick-wall' ids, so it has its own cache.
let sharedBrickTexture: THREE.CanvasTexture | null = null;
let sharedBrickBumpMap: THREE.CanvasTexture | null = null;

function getBrickTexture(): THREE.CanvasTexture {
  if (!sharedBrickTexture) sharedBrickTexture = createBrickTexture();
  return sharedBrickTexture;
}

function getBrickBumpMap(): THREE.CanvasTexture {
  if (!sharedBrickBumpMap) sharedBrickBumpMap = createBrickBumpMap();
  return sharedBrickBumpMap;
}

// ----------------------------------------------------------------------------
// Material construction.
// ----------------------------------------------------------------------------

/**
 * Stable index per FLOOR finish, used to give each floor finish a distinct depth nudge.
 *
 * Where two rooms with different floor finishes meet along a shared edge their floor
 * polygons can land coincident and z-fight; a per-finish step makes one win deterministically
 * so the seam renders a single stable colour.
 *
 * IMPORTANT: the bias uses `polygonOffsetUnits` only — `polygonOffsetFactor` is left at 0.
 * `factor` scales with the polygon's depth slope in screen space, so it only kicks in as a
 * surface tilts away from the camera. That made the floor-vs-ground ordering flip as you
 * orbited/tilted — the floor colour blinked in the top-down view. `units` is a flat,
 * camera-angle INDEPENDENT depth nudge, which is exactly right for breaking ties between
 * coplanar faces. (Walls are handled per-instance in `WallMesh`, not here.)
 */
const FLOOR_OFFSET_INDEX: ReadonlyMap<string, number> = new Map(
  FLOOR_FINISHES.map((f, i) => [f.id, i])
);

/** Wall depth bias. Walls are separated from each other per-INSTANCE at the mesh (see
 *  `WallMesh`), because two walls of the *same* finish share this one cached material and so
 *  could never be told apart by a per-finish offset — that's exactly what produced the
 *  radial z-fighting "fans" at corners on the low tier. So the shared material stays at a
 *  neutral offset and the real ordering happens per wall. `factor` is 0 so nothing shifts
 *  with camera angle. */
function applyWallDepthBias(material: THREE.MeshStandardMaterial, _finishId: string): void {
  material.polygonOffset = true;
  material.polygonOffsetFactor = 0;
  material.polygonOffsetUnits = 0;
}

/** Floor depth bias: always NEGATIVE units so the room floor is reliably pulled in front of
 *  the lawn (which is pushed back with a large positive offset) and the road, at every
 *  camera angle. A distinct per-finish step keeps differently-painted adjoining floors from
 *  z-fighting along a shared edge. No `factor`, so tilting never reorders anything. */
function applyFloorDepthBias(material: THREE.MeshStandardMaterial, finishId: string): void {
  const idx = FLOOR_OFFSET_INDEX.get(finishId) ?? 0;
  material.polygonOffset = true;
  material.polygonOffsetFactor = 0;
  // -4 keeps every floor clear of the road slab (units -4) and the lawn (units +24); the
  // per-finish step stays small so floors never creep so far forward they fight furniture.
  material.polygonOffsetUnits = -4 - idx * 0.5;
}

/**
 * How strongly a surface picks up the scene's (procedural) environment map. Glossier
 * finishes (low roughness — marble, tile, vitrified) get more sheen/reflection; matte
 * paints get only a whisper. This is what makes floors look polished and walls look
 * painted instead of everything reading as flat plastic. Costs nothing extra at runtime.
 */
function envIntensityFor(roughness: number): number {
  // roughness 0.2 → ~0.85, roughness 0.9 → ~0.3. Clamped to a tasteful range.
  const v = 1.0 - roughness * 0.75;
  return Math.max(0.25, Math.min(0.9, v));
}

/**
 * Builds the shared THREE material for a palette finish.
 * - Solid paints → flat MeshStandardMaterial tinted `color`.
 * - Textured floors/walls → a cached white-base procedural texture tinted `color`, so one
 *   texture (e.g. the tile grid) can serve many color variants.
 */
function buildFinishMaterial(finish: FinishMaterial, kind: 'wall' | 'floor' = 'wall'): THREE.Material {
  const roughness = finish.roughness ?? 0.7;
  let material: THREE.MeshStandardMaterial;

  if (!finish.texture) {
    material = new THREE.MeshStandardMaterial({ color: finish.color, roughness, metalness: 0 });
  } else if (finish.id === 'default-wall') {
    // The brick id keeps its dedicated brick texture + bump map (legacy look).
    material = new THREE.MeshStandardMaterial({
      map: getBrickTexture(),
      bumpMap: getBrickBumpMap(),
      bumpScale: 0.05,
      roughness,
      metalness: 0,
    });
  } else {
    // Generic textured finish: reuse the cached procedural tile for this kind, tinted.
    const texture = getTexture(finish.texture).clone();
    texture.needsUpdate = true;
    const r = finish.repeatMeters && finish.repeatMeters > 0 ? 1 / finish.repeatMeters : 1;
    texture.repeat.set(r, r);
    material = new THREE.MeshStandardMaterial({
      map: texture,
      color: finish.color,
      roughness,
      metalness: 0,
    });
    // Surface relief: plank seams, tile grout, stone speckle. The bump map shares the same
    // physical repeat as the colour map so the relief lines up with the pattern.
    const bump = getBumpTexture(finish.texture);
    if (bump) {
      const bumpTex = bump.clone();
      bumpTex.needsUpdate = true;
      bumpTex.repeat.set(r, r);
      material.bumpMap = bumpTex;
      material.bumpScale = BUMP_SCALE[finish.texture];
    }
  }

  applyDepthBias(material, finish.id, kind);
  material.envMapIntensity = envIntensityFor(roughness);
  return material;
}

/** Routes to the wall- or floor-specific depth bias so a finish painted on a floor never
 *  inherits the wall-corner offset that would push it behind the lawn. */
function applyDepthBias(material: THREE.MeshStandardMaterial, finishId: string, kind: 'wall' | 'floor'): void {
  if (kind === 'floor') applyFloorDepthBias(material, finishId);
  else applyWallDepthBias(material, finishId);
}

/**
 * Returns the one shared material instance for an id.
 *
 * Resolution order:
 *   1. Palette finish (registered in finishPalette) → built once and cached.
 *   2. Legacy aliases ('brick-wall', 'tile-floor') → mapped to their palette counterpart.
 *   3. Anything else → falls back to the default wall material (unchanged prior behavior).
 *
 * Note: brick-wall and tile-floor are kept as explicit aliases so old persisted plans that
 * stored those ids keep rendering as before.
 */
export function getMaterial(materialId: string): THREE.Material {
  const cached = materialCache.get(materialId);
  if (cached) return cached;

  // Legacy aliases → canonical palette id.
  const alias: Record<string, string> = {
    'brick-wall': 'default-wall',
    'tile-floor': 'default-floor',
  };
  const resolvedId = alias[materialId] ?? materialId;

  const finish = getFinishById(resolvedId);
  const material = finish
    ? buildFinishMaterial(finish)
    : buildFinishMaterial(ALL_FINISHES[0]); // default-wall fallback (unchanged semantics)

  materialCache.set(materialId, material);
  return material;
}

/**
 * Like {@link getMaterial}, but for room floors. Builds the same finish look with a
 * floor-specific depth bias (always pulled in front of the lawn/road, never camera-angle
 * dependent) and caches it separately so floors and walls that share a finish id don't
 * clobber each other's bias.
 */
export function getFloorMaterial(materialId: string): THREE.Material {
  const cached = floorMaterialCache.get(materialId);
  if (cached) return cached;

  const alias: Record<string, string> = {
    'brick-wall': 'default-wall',
    'tile-floor': 'default-floor',
  };
  const resolvedId = alias[materialId] ?? materialId;

  const finish = getFinishById(resolvedId);
  const material = finish
    ? buildFinishMaterial(finish, 'floor')
    : buildFinishMaterial(ALL_FINISHES[0], 'floor');

  floorMaterialCache.set(materialId, material);
  return material;
}

/** True when the given id is a registered finish in the palette. */
export function isKnownFinish(materialId: string): boolean {
  return getFinishById(materialId) != null;
}
