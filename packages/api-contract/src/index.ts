/**
 * Shared API contract types — the single source of truth between frontend and
 * backend. Hand-written here for the example resource; for the full surface,
 * run `pnpm --filter @repo/api-contract generate` to codegen `generated.ts`
 * directly from the live OpenAPI spec the FastAPI backend serves at
 * `/openapi.json`, then re-export from here.
 */

export interface Item {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** RFC 9457 problem+json — the shape of every API error. */
export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string | null;
  code: string;
  request_id: string | null;
}
