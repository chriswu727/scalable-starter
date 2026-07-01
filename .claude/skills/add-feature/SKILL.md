---
name: add-feature
description: Add a new API resource (model + schema + repository + service + router + tests) to this scalable-starter codebase, conforming to its layered system design. Use whenever adding a CRUD resource, endpoint, table, or model.
---

# Add a feature the on-pattern way

Always keep the invariants in `AGENTS.md`. To add a resource named `<singular>`
(e.g. `project`, plural `projects`):

## 1. Scaffold from the example

```bash
make feature name=<singular>
```

This stamps `app/db/models/<x>.py`, `app/schemas/<x>.py`,
`app/repositories/<x>.py`, `app/services/<x>.py`,
`app/api/v1/routes/<plural>.py`, and `tests/test_<plural>.py` from the `items`
template, renamed consistently and auto-formatted.

## 2. Complete the wiring it prints

- `apps/api/app/api/v1/deps.py` — add `get_<x>_service` (uses `SessionDep`) and
  `get_<x>_read_service` (uses `ReadSessionDep`), plus `<X>ServiceDep` /
  `Read<X>ServiceDep`. Copy the `item` versions.
- `apps/api/app/db/models/__init__.py` — import `<X>Model`, add to `__all__`.
- `apps/api/app/api/v1/router.py` — import the router and `include_router(...)`.

## 3. Put logic in the right layer

- **Business rules go in the service** (`app/services/<x>.py`), raising
  `NotFoundError` / `ConflictError`. Keep the router thin. SQL only in the
  repository.
- **GET routes** use `Read<X>ServiceDep` (read replica); **mutations** use
  `<X>ServiceDep` (primary).
- Model any DB uniqueness with a real constraint and map `IntegrityError` →
  `ConflictError` (see the `items` service).

## 4. Migrate, regenerate the contract, test

```bash
make migration m="add <plural>"   # autogenerate the Alembic migration; review it
make migrate                      # apply
make contract                     # regenerate OpenAPI types — never hand-edit generated.ts
make check                        # lint + typecheck + tests must be green
```

## Do NOT

- Put business logic in a router, or touch the DB/session outside a repository.
- Read `os.environ` (add a field to `Settings` + `.env.example` instead).
- Add durable in-process state (breaks horizontal scaling — use Postgres/Redis).
- Do heavy work inline in a request (enqueue a job; handlers must be idempotent).
- Hand-edit `packages/api-contract/src/generated.ts`.

## Frontend (optional)

Mirror `itemsApi` in `apps/web/lib/api-client.ts` using the generated types, and
add a route under `apps/web/app/`.
