import type { Point2D } from '@/types/geometry';

export interface ArrayPlacementConfig {
  count: number;
  spacing: number;
  angle: number;
}

export interface ArrayPlacementItem {
  index: number;
  position: Point2D;
}

export function normalizeArrayCount(count: number): number {
  if (!Number.isFinite(count)) return 1;
  return Math.max(1, Math.min(20, Math.round(count)));
}

export function normalizeArraySpacing(spacing: number): number {
  if (!Number.isFinite(spacing)) return 100;
  return Math.max(1, Math.min(5000, Math.round(spacing)));
}

export function generateArrayPositions(origin: Point2D, config: ArrayPlacementConfig): ArrayPlacementItem[] {
  const count = normalizeArrayCount(config.count);
  const spacing = normalizeArraySpacing(config.spacing);
  const angle = Number.isFinite(config.angle) ? config.angle : 0;
  const dx = Math.cos(angle) * spacing;
  const dy = Math.sin(angle) * spacing;

  return Array.from({ length: count }, (_, index) => ({
    index,
    position: {
      x: origin.x + dx * index,
      y: origin.y + dy * index,
    },
  }));
}
