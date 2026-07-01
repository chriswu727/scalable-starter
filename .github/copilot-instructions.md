# GitHub Copilot instructions

This repo follows the conventions in [AGENTS.md](../AGENTS.md) — read it and keep
changes on-pattern.

**Working principles:** understand the code and find the right place before
changing it; **no hardcoding** (values via `settings`/env, never inline); pick the
best, simplest solution; keep the diff minimal and finished; verify it works;
report honestly; never commit secrets.

- **Layered architecture:** transport (routes) → service → repository → data.
  Routers are thin; business logic lives in services; SQL lives only in
  repositories (never import FastAPI there).
- **Stateless compute:** no durable in-process state — all state in Postgres/Redis.
  Scale horizontally; heavy work goes to the worker tier via `enqueue()` (handlers
  must be idempotent); hot reads use the read replica + `get_or_set` cache-aside.
- **Config via `settings`** only (never `os.environ`); **schema via Alembic**
  migrations (never `create_all`); errors as `AppError` → RFC-9457; outbound HTTP
  via the shared `HttpClient`; logs via `get_logger()` (never `print()`).
- **Add a resource** with `make feature name=<x>`, then wire deps/model/router +
  `make migration` + `make contract`. Frontend types are generated — run
  `make contract`, never hand-edit `generated.ts`.
- `make check` must pass before committing.
