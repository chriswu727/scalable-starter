import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    // env.ts validates NEXT_PUBLIC_API_URL at import time.
    env: { NEXT_PUBLIC_API_URL: 'http://test.local' },
    include: ['**/*.test.ts'],
  },
});
