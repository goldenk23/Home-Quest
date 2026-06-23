// src/app/hooks/useKeyboardShortcuts.ts

import { useEffect } from 'react';
import { useAppStore } from '@/store';

/** Ctrl/Cmd+Z to undo, Ctrl+Y or Ctrl/Cmd+Shift+Z to redo. Mount once near the root. */
export function useKeyboardShortcuts(): void {
  const undo = useAppStore((s) => s.undo);
  const redo = useAppStore((s) => s.redo);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isMeta = e.ctrlKey || e.metaKey;
      if (isMeta && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if ((isMeta && e.key === 'y') || (isMeta && e.shiftKey && e.key === 'z')) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [undo, redo]);
}
