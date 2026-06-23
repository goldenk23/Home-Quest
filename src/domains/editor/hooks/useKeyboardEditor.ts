// src/domains/editor/hooks/useKeyboardEditor.ts

import { useEffect, useCallback } from 'react';
import { useAppStore } from '@/store';
import type { Point2D } from '@/types';

const NUDGE_AMOUNT = 10; // cm
const FINE_NUDGE = 1; // cm with Shift

export function useKeyboardEditor(): void {
  const selectedIds = useAppStore((s) => s.selectedIds);
  const moveVertex = useAppStore((s) => s.moveVertex);
  const moveFurniture = useAppStore((s) => s.moveFurniture);
  const removeWall = useAppStore((s) => s.removeWall);
  const removeFurniture = useAppStore((s) => s.removeFurniture);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Ignore when typing in a field.
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (selectedIds.length === 0) return;
      const nudge = e.shiftKey ? FINE_NUDGE : NUDGE_AMOUNT;

      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault();
          useAppStore.getState().recordHistory('Nudge', () =>
            nudgeSelection(selectedIds, { x: 0, y: nudge }, moveVertex, moveFurniture)
          );
          announcePosition('up', nudge);
          break;
        case 'ArrowDown':
          e.preventDefault();
          useAppStore.getState().recordHistory('Nudge', () =>
            nudgeSelection(selectedIds, { x: 0, y: -nudge }, moveVertex, moveFurniture)
          );
          announcePosition('down', nudge);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          useAppStore.getState().recordHistory('Nudge', () =>
            nudgeSelection(selectedIds, { x: -nudge, y: 0 }, moveVertex, moveFurniture)
          );
          announcePosition('left', nudge);
          break;
        case 'ArrowRight':
          e.preventDefault();
          useAppStore.getState().recordHistory('Nudge', () =>
            nudgeSelection(selectedIds, { x: nudge, y: 0 }, moveVertex, moveFurniture)
          );
          announcePosition('right', nudge);
          break;
        case 'Delete':
        case 'Backspace':
          e.preventDefault();
          useAppStore.getState().recordHistory('Delete', () =>
            deleteSelection(selectedIds, removeWall, removeFurniture)
          );
          break;
      }
    },
    [selectedIds, moveVertex, moveFurniture, removeWall, removeFurniture]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

function nudgeSelection(
  ids: string[],
  delta: Point2D,
  moveVertex: (id: string, pos: Point2D) => void,
  moveFurniture: (id: string, pos: Point2D) => void
): void {
  const state = useAppStore.getState();
  for (const id of ids) {
    if (state.vertices[id]) {
      const p = state.vertices[id].position;
      moveVertex(id, { x: p.x + delta.x, y: p.y + delta.y });
    } else if (state.furniture[id]) {
      const p = state.furniture[id].position;
      moveFurniture(id, { x: p.x + delta.x, y: p.y + delta.y });
    }
  }
}

function deleteSelection(
  ids: string[],
  removeWall: (id: string) => void,
  removeFurniture: (id: string) => void
): void {
  const state = useAppStore.getState();
  for (const id of ids) {
    if (state.walls[id]) removeWall(id);
    else if (state.furniture[id]) removeFurniture(id);
  }
  useAppStore.getState().clearSelection();
}

function announcePosition(direction: string, amount: number): void {
  const el = document.getElementById('sr-announcer');
  if (el) el.textContent = `Moved ${direction} by ${amount} centimeters`;
}
