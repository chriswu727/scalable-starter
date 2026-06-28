import { expect, test } from '@playwright/test';

// Hits a running stack: web on baseURL, api on E2E_API_URL. Start it with
// `make up`, then `make e2e`.
const API = process.env.E2E_API_URL ?? 'http://localhost:8000';

test('the web app renders', async ({ page }) => {
  const response = await page.goto('/');
  expect(response?.ok()).toBeTruthy();
});

test('items round-trip through the API', async ({ request }) => {
  const name = `e2e-${Math.random().toString(36).slice(2)}`;

  const created = await request.post(`${API}/api/v1/items`, { data: { name } });
  expect(created.status()).toBe(201);
  const { id } = await created.json();

  const fetched = await request.get(`${API}/api/v1/items/${id}`);
  expect(fetched.status()).toBe(200);
  expect((await fetched.json()).name).toBe(name);

  await request.delete(`${API}/api/v1/items/${id}`);
});
