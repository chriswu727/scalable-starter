/**
 * Single typed API client. Wraps `fetch` with base URL resolution, timeouts,
 * request-id propagation, and error normalization so callers never repeat this.
 */
import type { Item, Page } from '@repo/api-contract';
import { apiBaseUrl } from './env';

/** Normalized error mirroring the backend's RFC 9457 problem+json body. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 10_000, headers, ...rest } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${apiBaseUrl()}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...headers },
    });

    const requestId = res.headers.get('x-request-id') ?? undefined;

    if (!res.ok) {
      const problem = (await res.json().catch(() => ({}))) as {
        code?: string;
        detail?: string;
      };
      throw new ApiError(
        res.status,
        problem.code ?? 'error',
        problem.detail ?? res.statusText,
        requestId,
      );
    }

    if (res.status === 204) {
      return undefined as T;
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Example typed resource client — mirrors the backend `items` resource.
// Types come from the shared @repo/api-contract package. Copy this shape for
// your own resources, then delete it.
// ---------------------------------------------------------------------------
export type { Item, Page };

export const itemsApi = {
  list: (params?: { limit?: number; offset?: number }) =>
    apiFetch<Page<Item>>(
      `/api/v1/items?limit=${params?.limit ?? 50}&offset=${params?.offset ?? 0}`,
    ),
  get: (id: string) => apiFetch<Item>(`/api/v1/items/${id}`),
  create: (body: { name: string; description?: string }) =>
    apiFetch<Item>('/api/v1/items', { method: 'POST', body: JSON.stringify(body) }),
};
