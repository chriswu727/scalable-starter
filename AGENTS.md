# AGENTS.md — engineering conventions for this codebase

This project was bootstrapped from **scalable-starter**, and its system design is
deliberate. Any AI agent (Claude, Cursor, Copilot, Codex, Gemini, …) or human MUST
keep changes on-pattern so the design still holds as the app grows and scales.
Read this before writing code.

**Prime directive:** extend the seams that already exist; do not invent new ones.
If a change seems to need a brand-new pattern, it almost always belongs in an
existing layer instead.

## Non-negotiable invariants (these are what keep it scalable + distributed)

1. **Stateless compute.** Services and request handlers hold NO durable,
   per-user, or cross-request state in process memory. All state lives in
   Postgres or Redis. Never add a module-level dict / cache / counter that must
   survive across requests or replicas — it breaks horizontal scaling. (State
   scoped to a single request is fine.)
2. **State is external and managed.** Postgres is the source of truth; Redis is
   cache / queue / rate-limit store. Don't add a new stateful backing service
   without a deliberate, documented decision.
3. **Scale horizontally, never by hack.** More load → more replicas (the HPA
   handles it). Heavy / slow / bursty work → the worker tier via `enqueue()`,
   never inline in a request. Hot reads → read replica (`get_read_session`) +
   cache-aside (`get_or_set`).
4. **Config only through `settings`.** Never read `os.environ` directly. New
   config = a typed field on `Settings` (`app/core/config.py`) + a line in
   `.env.example`.
5. **Migrations own the schema.** Never `create_all` in app code. Every schema
   change is an Alembic migration (`make migration`). Name constraints (the
   `ck_` naming convention requires explicit `CheckConstraint(name=...)`).

## Layering — where code goes

Dependencies point inward only: **transport → service → repository → data.**

- `app/api/v1/routes/` — thin HTTP handlers: validate (Pydantic), call a service,
  return a schema. NO business logic, NO SQL, NO direct session/DB use.
- `app/services/` — business rules / use-cases; raise domain exceptions; depend on
  repositories, never the ORM/session directly. **Your logic goes here.**
- `app/repositories/` — data access; the ONLY place that touches SQLAlchemy;
  subclass `BaseRepository`. Never import FastAPI here.
- `app/schemas/` — Pydantic DTOs = the wire contract (separate Create/Update/Read).
- `app/db/` — engine, session, ORM models, base. `app/core/` — config, logging,
  security, lifespan, http_client. `app/{middleware,observability,cache,workers}/`
  — cross-cutting.

If a router reaches for the DB, or a repository imports FastAPI — stop, it's in
the wrong layer.

## Adding a resource (the mechanical path — don't hand-write)

```bash
make feature name=<singular>     # stamps model/schema/repository/service/router/test
```

Then complete the wiring it prints:

- `app/api/v1/deps.py` — add `get_<x>_service` / `get_<x>_read_service` +
  `<X>ServiceDep` / `Read<X>ServiceDep`.
- `app/db/models/__init__.py` — import `<X>Model`, add to `__all__`.
- `app/api/v1/router.py` — import the router + `include_router(...)`.

```bash
make migration m="add <plural>"   # generate the migration
make migrate                      # apply it
make contract                     # regenerate the OpenAPI types (frontend contract)
make check                        # lint + typecheck + tests must pass
```

GET routes use the **read** service dep (replica); mutations use the primary.
Mirror the `items` example exactly.

## Rules by concern

- **Errors:** raise an `AppError` subclass (`app/exceptions.py`); the handler
  renders RFC-9457 problem+json. Never return raw error strings or leak
  internals. Unique-constraint races → catch `IntegrityError` → `ConflictError`.
- **Cache:** use the `Cache` protocol; for read-through use `get_or_set`
  (single-flight). Don't hand-roll caching.
- **Background jobs:** produce with `enqueue()`, consume with a `@handler`.
  **Handlers MUST be idempotent** — delivery is at-least-once.
- **Outbound HTTP:** use the shared `HttpClient` (`app.state.http`: bounded
  timeouts, retries, circuit breaker). Never call `httpx`/`requests` ad hoc.
- **Observability:** log via `get_logger()` (structured, request-id + trace
  correlated). Never `print()`. Metrics/traces are auto-instrumented — leave them on.
- **Auth:** the JWT seam is `app/core/security.py` + `get_current_subject`. Wire
  your IdP there; don't scatter token logic across routes.

## Frontend (`apps/web`)

- Types come from `@repo/api-contract` (generated from OpenAPI). After any API
  change run `make contract`; never hand-edit `generated.ts`.
- All API calls go through `lib/api-client.ts` (`apiFetch`). Server components use
  the internal URL, the browser the public URL (`lib/env.ts`). Keep secrets out of
  `NEXT_PUBLIC_*`.

## Kubernetes / deploy

- New workloads follow the base templates: non-root with a **numeric**
  `runAsUser`, `readOnlyRootFilesystem`, dropped caps, seccomp, resource
  requests+limits, probes, topology spread, a PDB, and a NetworkPolicy allow —
  never a bare pod spec.
- Non-secret config in the ConfigMap; secrets via External Secrets (never a
  committed Secret in `base/`). Overlays patch per-env; don't fork `base/`.

## Before you commit

- `make check` is green (it's exactly what CI enforces).
- `make contract` run if the API surface changed (CI diff-gates the contract).
- New behavior has tests (a service unit test against a fake repo + an
  integration test; a coverage floor is enforced).
- No secrets, no `print()`, no direct `os.environ`, no new durable in-process state.

## When the design genuinely must change

If a requirement truly doesn't fit (you need sharding, event-sourcing, websockets,
multi-region, …), that's a deliberate architecture decision — not an ad-hoc patch.
Write an ADR in `docs/adr/`, update `ARCHITECTURE.md`, and preserve the invariants
above unless you are consciously and explicitly trading one away.
