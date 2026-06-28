/**
 * Shared API contract between frontend and backend.
 *
 * `generated.ts` is codegen'd from the backend's OpenAPI spec (`make contract`),
 * so resource shapes can't silently drift — CI regenerates and `git diff`s it.
 * The aliases below give ergonomic names; `Page<T>` stays a hand-written generic
 * because FastAPI emits a concrete `Page_ItemRead_` per resource, and `Problem`
 * is rendered by middleware so it isn't in the route-level OpenAPI.
 */
import type { components } from './generated';

export type { components, paths } from './generated';

export type Item = components['schemas']['ItemRead'];
export type ItemCreate = components['schemas']['ItemCreate'];
export type ItemUpdate = components['schemas']['ItemUpdate'];

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
  instance?: string | null;
  request_id: string | null;
  errors?: Array<Record<string, unknown>> | null;
}
