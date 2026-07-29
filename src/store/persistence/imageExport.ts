// src/store/persistence/imageExport.ts
//
// Raster/PDF export for the two viewports:
//   - 2D editor  → an <svg> element (vector). We serialize it, paint the dark
//                  editor background behind it, and rasterize onto a canvas.
//   - 3D viewer  → a WebGL <canvas>. We read its pixels directly (the canvas is
//                  created with preserveDrawingBuffer so the buffer is readable
//                  at any time, not just inside a frame).
//
// From a canvas we can produce PNG, JPG, or a single-page PDF (jsPDF).

import { jsPDF } from 'jspdf';

export type ImageExportFormat = 'png' | 'jpg' | 'pdf';

/** Background painted behind the 2D editor SVG (matches tailwind `bg-neutral-900`). */
const EDITOR_BG = '#171717';
/** Upscale factor for the 2D vector capture so the raster looks crisp, not blurry. */
const RASTER_SCALE = 3;
/** JPEG quality (0–1). */
const JPEG_QUALITY = 0.92;

/** Triggers a browser download for a Blob. */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** Promisified canvas.toBlob. */
function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Canvas is empty — nothing to export.'))),
      type,
      quality
    );
  });
}

/**
 * Rasterizes an <svg> element onto a fresh canvas at RASTER_SCALE resolution, with the
 * editor's dark background painted first (the on-screen background comes from a CSS class,
 * which is not carried by serialization, so we draw it explicitly).
 *
 * Crispness note: we render the SVG at the FULL target pixel size (width×scale) while
 * keeping the viewBox in display coordinates. The browser rasterizes the vectors at that
 * high DPI, so the result is sharp. (Rendering at display size and upscaling the bitmap
 * afterwards is what produces a blurry image.)
 */
async function svgToCanvas(svg: SVGSVGElement): Promise<HTMLCanvasElement> {
  const rect = svg.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));
  const outW = width * RASTER_SCALE;
  const outH = height * RASTER_SCALE;

  // Clone so we can stamp explicit pixel dimensions without disturbing the live SVG.
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  // High pixel size + display-space viewBox = vectors rasterized sharply at high DPI.
  clone.setAttribute('width', String(outW));
  clone.setAttribute('height', String(outH));
  clone.setAttribute('viewBox', `0 0 ${width} ${height}`);

  // Strip screen-only overlays (e.g. the compass rose) that shouldn't be in the export.
  clone.querySelectorAll('[data-export-exclude="true"]').forEach((el) => el.remove());

  const svgString = new XMLSerializer().serializeToString(clone);
  const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgString)}`;

  const img = new Image();
  img.crossOrigin = 'anonymous';
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error('Failed to rasterize the 2D plan.'));
    img.src = svgUrl;
  });

  const canvas = document.createElement('canvas');
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not create a drawing context for export.');

  ctx.fillStyle = EDITOR_BG;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas;
}

/** Saves a canvas as PNG/JPG, or wraps it in a single-page PDF sized to the image. */
async function exportCanvas(canvas: HTMLCanvasElement, format: ImageExportFormat, baseName: string): Promise<void> {
  if (format === 'pdf') {
    // JPEG keeps the PDF small; the plan/scene is a photographic-style image.
    const dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY);
    const orientation = canvas.width >= canvas.height ? 'landscape' : 'portrait';
    const pdf = new jsPDF({ orientation, unit: 'px', format: [canvas.width, canvas.height] });
    pdf.addImage(dataUrl, 'JPEG', 0, 0, canvas.width, canvas.height);
    pdf.save(`${baseName}.pdf`);
    return;
  }

  const mime = format === 'jpg' ? 'image/jpeg' : 'image/png';
  const quality = format === 'jpg' ? JPEG_QUALITY : undefined;

  // JPEG has no alpha — flatten onto an opaque background so transparent areas aren't black.
  let target = canvas;
  if (format === 'jpg') {
    const flat = document.createElement('canvas');
    flat.width = canvas.width;
    flat.height = canvas.height;
    const ctx = flat.getContext('2d');
    if (!ctx) throw new Error('Could not create a drawing context for export.');
    ctx.fillStyle = EDITOR_BG;
    ctx.fillRect(0, 0, flat.width, flat.height);
    ctx.drawImage(canvas, 0, 0);
    target = flat;
  }

  const blob = await canvasToBlob(target, mime, quality);
  downloadBlob(blob, `${baseName}.${format}`);
}

/** `home-quest-2d-2026-06-24T10-58-00`-style stable, filesystem-safe base name. */
function timestampedName(prefix: string): string {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').replace('Z', '');
  return `${prefix}-${stamp}`;
}

/** Exports the 2D editor plan as PNG/JPG/PDF. */
export async function exportEditor2D(format: ImageExportFormat): Promise<{ success: boolean; error?: string }> {
  try {
    const svg = document.querySelector<SVGSVGElement>('#editor-canvas svg');
    if (!svg) return { success: false, error: 'The 2D editor is not available to export.' };
    const canvas = await svgToCanvas(svg);
    await exportCanvas(canvas, format, timestampedName('home-quest-2d'));
    return { success: true };
  } catch (error) {
    return { success: false, error: (error as Error).message };
  }
}

/**
 * Exports a rectangular REGION of the 2D editor plan. `region` is in the SVG's own pixel space
 * (same space as the SVG's default user units, i.e. screen px relative to the SVG top-left).
 */
export async function exportEditor2DRegion(
  region: { x: number; y: number; width: number; height: number },
  format: ImageExportFormat
): Promise<{ success: boolean; error?: string }> {
  try {
    const svg = document.querySelector<SVGSVGElement>('#editor-canvas svg');
    if (!svg) return { success: false, error: 'The 2D editor is not available to export.' };
    const w = Math.max(1, Math.round(region.width));
    const h = Math.max(1, Math.round(region.height));
    const outW = w * RASTER_SCALE;
    const outH = h * RASTER_SCALE;

    const clone = svg.cloneNode(true) as SVGSVGElement;
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', String(outW));
    clone.setAttribute('height', String(outH));
    clone.setAttribute('viewBox', `${region.x} ${region.y} ${w} ${h}`);
    clone.querySelectorAll('[data-export-exclude="true"]').forEach((el) => el.remove());

    const svgString = new XMLSerializer().serializeToString(clone);
    const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgString)}`;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error('Failed to rasterize the region.'));
      img.src = svgUrl;
    });

    const canvas = document.createElement('canvas');
    canvas.width = outW;
    canvas.height = outH;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Could not create a drawing context for export.');
    ctx.fillStyle = EDITOR_BG;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    await exportCanvas(canvas, format, timestampedName('home-quest-region'));
    return { success: true };
  } catch (error) {
    return { success: false, error: (error as Error).message };
  }
}

/** Exports the 3D viewer scene as PNG/JPG/PDF. */
export async function exportViewer3D(format: ImageExportFormat): Promise<{ success: boolean; error?: string }> {
  try {
    const canvas = document.querySelector<HTMLCanvasElement>('#viewer-canvas canvas');
    if (!canvas) {
      return { success: false, error: 'The 3D viewer is not available. Draw some walls first.' };
    }
    await exportCanvas(canvas, format, timestampedName('home-quest-3d'));
    return { success: true };
  } catch (error) {
    return { success: false, error: (error as Error).message };
  }
}
