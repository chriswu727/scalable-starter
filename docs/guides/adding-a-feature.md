# Adding a feature

The skeleton is designed so a new resource is mechanical. We'll add a `projects`
resource. Use the existing `items` files as a copy-paste template.

> Rule of thumb: **logic goes in the service layer.** Routers stay thin,
> repositories stay dumb, schemas define the wire contract.

## Backend (one file per layer)

1. **ORM model** — `apps/api/app/db/models/project.py`, then export it from
   `app/db/models/__init__.py` so Alembic sees it.

2. **Schemas** — `apps/api/app/schemas/project.py`: `ProjectCreate`,
   `ProjectUpdate`, `ProjectRead`.

3. **Repository** — `apps/api/app/repositories/project.py`

   ```python
   class ProjectRepository(BaseRepository[ProjectModel]):
       model = ProjectModel
   ```

4. **Service** — `apps/api/app/services/project.py`: your business rules,
   raising `NotFoundError` / `ConflictError` as needed.

5. **Router** — `apps/api/app/api/v1/routes/projects.py`: thin handlers that
   call the service. Add a `get_project_service` dependency in `deps.py`.

6. **Register** the router in `apps/api/app/api/v1/router.py`.

7. **Migrate**:

   ```bash
   make migration m="add projects"
   make migrate
   ```

8. **Test** — copy `tests/test_items.py` to `tests/test_projects.py`.

## Frontend

1. Add types to the shared contract (`packages/api-contract/src/index.ts`) or
   regenerate from OpenAPI.
2. Add a typed client in `apps/web/lib/api-client.ts` (mirror `itemsApi`).
3. Add routes/components under `apps/web/app/`.

## Then delete the example

Once you have real resources, remove the `items` files across all layers and the
`ItemModel` (plus a migration to drop the table). The skeleton stands without it.
