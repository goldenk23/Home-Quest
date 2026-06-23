// src/utils/env.ts
// Centralizes all `import.meta.env` reads so the rest of the app never touches
// `import.meta` directly. Keeps env access typed and in one place.

export const config = {
  apiUrl: import.meta.env.VITE_API_URL ?? '',
  assetsCdn: import.meta.env.VITE_ASSETS_CDN ?? '',
  sentryDsn: import.meta.env.VITE_SENTRY_DSN ?? '',
  analyticsId: import.meta.env.VITE_ANALYTICS_ID ?? '',
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
} as const;
