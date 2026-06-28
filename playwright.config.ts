import { defineConfig } from '@playwright/test';

// End-to-end tests against a *running* stack (`make up`, then `make e2e`).
// Override the targets for staging/preview with E2E_BASE_URL / E2E_API_URL.
export default defineConfig({
  testDir: './e2e',
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000',
  },
});
