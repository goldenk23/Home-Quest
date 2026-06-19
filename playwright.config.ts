import { defineConfig } from '@playwright/test';

/**
 * Playwright config for visual regression testing.
 *
 * Two modes:
 * 1. `npm run test:visual` — Tests against dev server (http://localhost:5173)
 * 2. `npm run test:visual:storybook` — Tests against Storybook (http://localhost:6006)
 *
 * Screenshots are saved in `tests/visual/__screenshots__/`.
 * On first run, baseline images are created.
 * On subsequent runs, new screenshots are compared against baselines.
 * If they differ beyond the threshold, the test fails.
 */
export default defineConfig({
  testDir: './tests/visual',
  outputDir: './tests/visual/test-results',
  snapshotDir: './tests/visual/__screenshots__',
  snapshotPathTemplate: '{snapshotDir}/{testFilePath}/{testName}/{projectName}{ext}',

  fullyParallel: true,
  retries: 0,
  workers: 1, // Sequential for consistent screenshots

  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },

  expect: {
    toHaveScreenshot: {
      // Allow 0.5% pixel difference (handles antialiasing variance)
      maxDiffPixelRatio: 0.005,
      // Animations should be disabled for consistent screenshots
      animations: 'disabled',
    },
  },

  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        viewport: { width: 1280, height: 720 },
      },
    },
  ],

  // Auto-start dev server before tests
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 30000,
  },
});
