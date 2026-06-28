#!/usr/bin/env python3
"""Scaffold a new resource by stamping the `items` example across every layer.

Usage:  python scripts/scaffold_feature.py <name>   (or `make feature name=<name>`)
where <name> is a lowercase singular noun, e.g. `project`. It writes a model,
schema, repository, service, router, and test, then prints the few edits left to
wire it in. Delete the example afterwards with `scripts/delete_example.py`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

API = Path(__file__).resolve().parent.parent / "apps" / "api"

# (template, output template) relative to apps/api
FILES = [
    ("app/db/models/item.py", "app/db/models/{name}.py"),
    ("app/schemas/item.py", "app/schemas/{name}.py"),
    ("app/repositories/item.py", "app/repositories/{name}.py"),
    ("app/services/item.py", "app/services/{name}.py"),
    ("app/api/v1/routes/items.py", "app/api/v1/routes/{names}.py"),
    ("tests/test_items.py", "tests/test_{names}.py"),
]


def substitute(text: str, name: str, names: str) -> str:
    # Order matters: plural before "Item"/"item" so e.g. "items" -> "projects"
    # and "ItemModel" -> "ProjectModel" both come out right.
    return (
        text.replace("items", names)
        .replace("Item", name.capitalize())
        .replace("item", name)
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: scaffold_feature.py <name>  (lowercase singular, e.g. project)")
        return 2
    name = argv[1].strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        print(f"invalid name {name!r}: use a lowercase singular noun (e.g. project)")
        return 2
    names = f"{name}s"
    title = name.capitalize()

    targets = [
        (API / tmpl, API / out.format(name=name, names=names)) for tmpl, out in FILES
    ]
    for _, out_path in targets:
        if out_path.exists():
            print(
                f"refusing to overwrite existing apps/api/{out_path.relative_to(API)}"
            )
            return 1

    created = []
    for tmpl_path, out_path in targets:
        out_path.write_text(substitute(tmpl_path.read_text(), name, names))
        created.append(out_path)
        print(f"created  apps/api/{out_path.relative_to(API)}")

    # Reflow renamed lines that now exceed the line length (best-effort).
    subprocess.run(
        ["ruff", "format", *map(str, created)], check=False, capture_output=True
    )

    print(
        f"\nWire it up:\n"
        f"  1. app/api/v1/deps.py — add (importing {title}Service / {title}Repository):\n"
        f"       def get_{name}_service(session: SessionDep) -> {title}Service:\n"
        f"           return {title}Service({title}Repository(session))\n"
        f"       def get_{name}_read_service(session: ReadSessionDep) -> {title}Service:\n"
        f"           return {title}Service({title}Repository(session))\n"
        f"       {title}ServiceDep = Annotated[{title}Service, Depends(get_{name}_service)]\n"
        f"       Read{title}ServiceDep = "
        f"Annotated[{title}Service, Depends(get_{name}_read_service)]\n"
        f"  2. app/db/models/__init__.py — import {title}Model, add to __all__\n"
        f"  3. app/api/v1/router.py — import {names}, "
        f"api_router.include_router({names}.router)\n"
        f'  4. make migration m="add {names}"  &&  make migrate\n'
        f"  5. make contract — regenerate the OpenAPI types\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
