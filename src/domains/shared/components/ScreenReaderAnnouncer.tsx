// src/domains/shared/components/ScreenReaderAnnouncer.tsx

import React from 'react';

/** Two hidden live regions (polite + assertive). Mount once at the app root. */
export const ScreenReaderAnnouncer: React.FC = () => (
  <>
    <div id="sr-announcer" role="status" aria-live="polite" aria-atomic="true" className="sr-only" />
    <div id="sr-announcer-assertive" role="alert" aria-live="assertive" aria-atomic="true" className="sr-only" />
  </>
);

/** Imperatively announce a message to screen readers. */
export function announce(message: string, priority: 'polite' | 'assertive' = 'polite'): void {
  const id = priority === 'assertive' ? 'sr-announcer-assertive' : 'sr-announcer';
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = ''; // clear so the same message re-announces
  requestAnimationFrame(() => {
    el.textContent = message;
  });
}
