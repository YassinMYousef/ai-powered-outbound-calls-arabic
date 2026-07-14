---
name: db-migrate
description: Set up and run Alembic migrations for the Postgres schema defined in backend/app/data/models.py. Use when adding/changing SQLAlchemy models (CallLog, KBDocument, new tables/columns), when asked to create or apply a database migration, or when Alembic needs first-time initialization in backend/.
---

# Database migrations (Alembic + Postgres 18)

Run every alembic command from `backend/` with the venv active (`source .venv/bin/activate`).
Alembic (>=1.13) is already installed via `pip install -e ".[dev]"`.

## 0. Postgres must be up

From the repo root: `docker compose up -d`
Verify: `docker compose exec postgres pg_isready -U callcenter` → `... accepting connections`.
The URL comes from `settings.database_url` (`backend/.env`; the default already points at the
compose Postgres: `postgresql+psycopg://callcenter:callcenter@localhost:5432/callcenter`).

## 1. First-time setup (only if `backend/alembic/` does not exist)

Alembic is a dependency but NOT initialized — no `backend/alembic/`, no `backend/alembic.ini`.
Check with `ls alembic` (from `backend/`); if missing:

```bash
cd backend
alembic init alembic
```

Edit `alembic/env.py`: after `config = context.config`, add the imports and URL override,
and replace the existing `target_metadata = None`:

```python
from app.config import settings
from app.data.models import Base

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

Notes: `alembic.ini`'s generated `prepend_sys_path = .` makes `app` importable, and
`app/config.py` loads `.env` relative to the CWD (`env_file=".env"`) — two reasons to always
run from `backend/`. The static `sqlalchemy.url = driver://...` line in `alembic.ini` is now
dead (env.py overrides it); delete it or leave it — never put real credentials there.

Then create and apply the initial migration:

```bash
alembic revision --autogenerate -m "initial schema: call_logs, kb_documents"
alembic upgrade head
```

Expected: revision prints `Generating .../alembic/versions/<rev>_initial_schema....py ... done`;
`alembic current` shows `<rev> (head)`; from repo root
`docker compose exec postgres psql -U callcenter -c '\dt'` lists `alembic_version`,
`call_logs`, `kb_documents`.

Commit `alembic.ini` and `alembic/` (including `versions/`), and update the stale
"No Alembic migrations yet" line in CLAUDE.md's Conventions section.

## 2. Per schema change

1. Edit `backend/app/data/models.py` (new models must live there or be imported into it so
   they register on `Base.metadata`, or autogenerate will not see them).
2. `alembic revision --autogenerate -m "<what changed>"`
3. Review the new file in `alembic/versions/` BEFORE applying. Autogenerate misses renames:
   a renamed column/table shows up as drop + create, which destroys data. Rewrite those as
   `op.alter_column(..., new_column_name=...)` / `op.rename_table(...)` (and mirror in
   `downgrade()`).
4. `alembic upgrade head`
5. CLAUDE.md requires every `models.py` change to go through Alembic — ship the migration in
   the same change as the models.py edit.

## Rules

- Never edit a migration that has already been applied or committed — fix mistakes with a
  new revision on top.
- Empty autogenerate (`pass` in `upgrade()`) means models and DB already match — delete the
  useless revision file instead of applying it.
- Iterating locally: `alembic downgrade -1` to undo the last revision; `alembic history`
  and `alembic current` to inspect state.
