import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiFetch } from './api-client';

function mockResponse(
  body: unknown,
  init: { status?: number; headers?: Record<string, string> } = {},
): Response {
  const status = init.status ?? 200;
  return {
    ok: status < 400,
    status,
    statusText: 'mock',
    headers: new Headers(init.headers),
    json: async () => body,
  } as Response;
}

afterEach(() => vi.restoreAllMocks());

describe('apiFetch', () => {
  it('returns parsed JSON on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse({ id: '1', name: 'a' })));
    const data = await apiFetch<{ id: string }>('/x');
    expect(data.id).toBe('1');
  });

  it('throws ApiError with code + request id on problem+json', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          mockResponse(
            { code: 'not_found', detail: 'gone' },
            { status: 404, headers: { 'x-request-id': 'req-1' } },
          ),
        ),
    );
    const err = await apiFetch('/x').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 404, code: 'not_found', requestId: 'req-1' });
  });

  it('returns undefined on 204', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse(null, { status: 204 })));
    const data = await apiFetch('/x', { method: 'DELETE' });
    expect(data).toBeUndefined();
  });
});
