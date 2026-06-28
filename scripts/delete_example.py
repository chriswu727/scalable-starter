#!/usr/bin/env python3
"""Print a precise checklist for removing the example `items` resource.

The example is deliberately woven through shared files (router, deps, model
registry, frontend), so removal is a guided one-time edit rather than fragile
auto-surgery. Run `make delete-example`, work the list, then `make check`.
"""

from __future__ import annotations

CHECKLIST = """\
Remove the example `items` resource — work top to bottom, then run `make check`:

Backend files to delete:
  apps/api/app/db/models/item.py
  apps/api/app/schemas/item.py
  apps/api/app/repositories/item.py
  apps/api/app/services/item.py
  apps/api/app/api/v1/routes/items.py
  apps/api/tests/test_items.py
  apps/api/tests/test_service.py            # the items-based service unit test

Backend references to edit:
  apps/api/app/db/models/__init__.py        # drop the ItemModel import + __all__ entry
  apps/api/app/api/v1/router.py             # drop `import items` + include_router(items.router)
  apps/api/app/api/v1/deps.py               # drop get_item_service/get_item_read_service
                                            #   + ItemServiceDep/ReadItemServiceDep + imports
  apps/api/scripts/seed.py                  # drop or replace the ItemModel seed data

Frontend:
  apps/web/lib/api-client.ts                # drop itemsApi
  apps/web/app/page.tsx                     # drop the items demo UI

Schema + contract:
  make migration m="drop items"  &&  make migrate   # autogenerate drops the table
  make contract                                     # regenerate the OpenAPI types

The skeleton stands without it. Add your own resources with `make feature name=...`.
"""


def main() -> int:
    print(CHECKLIST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
