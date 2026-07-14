---
name: verify
description: Verify a code change in the CallCenter repo end-to-end — ruff + pytest, then drive the changed surface live (curl the API route with a realistic Arabic/Twilio payload, boot the Celery worker, or build the frontend). Use whenever a backend, worker, or frontend change is about to be called done, before committing, or when asked to confirm a change actually works.
---

# Verify a change

All backend commands run from `backend/` with the existing venv: `source .venv/bin/activate`.
Config loads from `backend/.env` (already present, via `app/config.py` pydantic-settings).

## 1. Always: lint, then tests

```bash
cd backend && source .venv/bin/activate
ruff check app tests
pytest                                        # full suite
pytest tests/test_health.py::test_health -v   # single-test form
```

Both must pass clean before any live verification.

## 2. Backend API changes: drive the route live

If the change touches DB/Redis, start infra from the repo root: `docker compose up -d`
(Postgres 18 on :5432, Redis 7 on :6379, user/pass/db all `callcenter`).

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload                 # :8000, docs at /docs
```

Baseline: `curl -s http://localhost:8000/health` → `{"status":"ok"}`.

Curl the changed route with a realistic payload and read the actual status + body —
import success or the app booting is not verification.

- Chat/dialog payloads: JSON with Arabic text.
  ```bash
  curl -si http://localhost:8000/api/chat/query -H 'Content-Type: application/json' \
    -d '{"query": "ما هي خطوات إعادة تعيين كلمة المرور؟"}'
  ```
- `/telephony/*` webhooks: form-encoded Twilio params, `call_id` as a query param.
  ```bash
  curl -si -X POST http://localhost:8000/telephony/voice
  # 200, TwiML XML containing <Say language="arb" voice="Polly.Zeina">
  curl -si -X POST 'http://localhost:8000/telephony/status?call_id=1' \
    -d 'CallSid=CA123&CallStatus=completed&CallDuration=7'
  # 204, empty body
  ```

Current state (recheck against the code — it moves fast): all `/api/*` routes are 501
stubs; `/telephony/voice` and `/telephony/status` are implemented; `/telephony/gather`
still raises NotImplementedError (500). A 501 from a stub you didn't touch is expected.
A route you just implemented MUST stop returning 501 — if it still does, the route isn't
wired: check the handler's router registration and `include_router` in `app/main.py`.

Do not verify `app/telephony/client.place_call` by invoking it — it places a real Twilio
call and needs a Twilio-reachable `public_base_url`. Cover it via pytest and webhook curls.

## 3. Worker/task changes

Redis must be up (`docker compose up -d` from repo root). Then:

```bash
cd backend && source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

Confirm the worker boots and the changed task appears in the startup banner's `[tasks]`
list (e.g. `app.workers.tasks.place_outbound_call`). Missing from the list = not
registered — tasks must be defined in `app/workers/tasks.py`: `celery_app.py` uses
`autodiscover_tasks(["app.workers"])`, which imports only the `tasks` module, so a task
in any other file silently won't register. Stop the worker after.

## 4. Model/schema changes

There is no Alembic setup yet (the dependency is installed, but no `alembic.ini` or
migrations directory exists). Per CLAUDE.md, once schemas leave the skeleton stage,
set up Alembic and write a migration BEFORE changing `app/data/models.py`. Then verify
by applying it against the compose Postgres and inspecting the tables:

```bash
docker compose up -d                          # from repo root
cd backend && source .venv/bin/activate
alembic upgrade head
docker compose exec postgres psql -U callcenter -d callcenter -c '\d'
```

## 5. Frontend changes

```bash
cd frontend
[ -d node_modules ] || npm ci    # reproducible install from package-lock.json
npm run build                         # tsc --noEmit + vite build; must exit 0
```

For behavior changes: `npm run dev` (:5173, proxies `/api` → :8000) with uvicorn running,
and exercise the changed UI against the live API.