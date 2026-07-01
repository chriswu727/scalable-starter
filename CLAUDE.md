# CLAUDE.md

This project follows the engineering conventions in **[AGENTS.md](./AGENTS.md)** —
read it before making changes and keep every change on-pattern. The system design
is what keeps the app stateless, scalable, and distributed as it grows; don't
erode it with one-off patterns.

**Non-negotiables** (full detail in AGENTS.md):

- **Stateless services** — no durable in-process state; all state in Postgres/Redis.
- **Layered** — transport (routes) → service → repository → data. Routers stay
  thin, business logic lives in services, SQL lives only in repositories.
- **Config via `settings`** (never `os.environ`); **schema via Alembic** (never
  `create_all`).
- Errors as `AppError` → RFC-9457; jobs via `enqueue()` with **idempotent**
  handlers; outbound calls via the shared `HttpClient`; logs via `get_logger()`
  (never `print()`).
- Heavy work → the worker tier; hot reads → read replica + `get_or_set` cache-aside.

**Add a resource:** `make feature name=<singular>`, then wire deps/model/router,
then `make migration` + `make contract`. **Before committing:** `make check` must
be green (and `make contract` if the API changed). Run `make help` for everything.

When a requirement truly doesn't fit the design, don't hack around it — write an
ADR in `docs/adr/` and update `ARCHITECTURE.md`.
