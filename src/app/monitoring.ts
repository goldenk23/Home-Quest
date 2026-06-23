// src/app/monitoring.ts
//
// Lightweight, dependency-free monitoring layer.
//
// The implementation guide wires this to `@sentry/react`. Per the request to skip the
// deployment setup, this is a self-contained shim with the same surface area
// (`initMonitoring`, `captureException`, `markFlowStart`, `markFlowEnd`) that logs to the
// console in development and no-ops in production. Swapping in Sentry later only means
// re-implementing these four functions — no call sites change.

import { config } from '@/utils/env';

export interface CaptureScope {
  level?: 'fatal' | 'error' | 'warning' | 'info';
  tags?: Record<string, string | number | boolean | undefined>;
  extra?: Record<string, unknown>;
}

export function initMonitoring(): void {
  // No external monitoring is wired up. In production this is intentionally silent.
  if (config.isDev) {
    // eslint-disable-next-line no-console
    console.info('[monitoring] dev mode — errors are logged to the console.');
  }
}

/** Report a captured exception. In dev this surfaces the error + context to the console. */
export function captureException(error: unknown, scope: CaptureScope = {}): void {
  if (!config.isDev) return;
  // eslint-disable-next-line no-console
  console.error('[monitoring] captured exception', { error, ...scope });
}

/** Lightweight performance marks for critical flows. */
export function markFlowStart(name: string): void {
  performance.mark(`${name}-start`);
}

export function markFlowEnd(name: string): void {
  performance.mark(`${name}-end`);
  try {
    performance.measure(name, `${name}-start`, `${name}-end`);
  } catch {
    // Ignore if the matching start mark was never set.
  }
}
