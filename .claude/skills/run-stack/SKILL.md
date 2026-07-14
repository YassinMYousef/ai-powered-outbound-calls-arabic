---
name: run-stack
description: Launch the full CallCenter dev stack — Postgres+Redis (docker compose), FastAPI API, Celery worker, Vite frontend — and verify each piece is healthy. Use when asked to run/start/launch the app or dev stack, bring services up, check the dev environment, or before any manual end-to-end testing.
---

Each server blocks its terminal: run uvicorn, celery, and vite as background processes (or separate terminals). Bring pieces up in this order — the worker needs Redis; the frontend proxy needs the API.

## 1. Infra (from repo root)
```bash
docker compose up -d
docker compose ps        # expect the postgres and redis services both "Up"/running
```
Postgres 18 on :5432 (user/pass/db all `callcenter`), Redis 7 on :6379.

## 2. Backend API (from backend/)
```bash
ls .env || cp .env.example .env    # .env is gitignored; fresh clones copy the template.
                                   # All Settings fields in app/config.py have defaults,
                                   # so the API boots without provider keys.
source .venv/bin/activate    # .venv exists. Recreate ONLY if missing:
                             #   python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
uvicorn app.main:app --reload    # background this; serves on :8000
```
Health check — must pass before continuing (retry for a few seconds; the server needs a moment to boot):
```bash
curl -s http://localhost:8000/health    # → {"status":"ok"}
```
Interactive docs: http://localhost:8000/docs

## 3. Celery worker (from backend/, same venv; Redis must be up first)
```bash
celery -A app.workers.celery_app worker --loglevel=info    # background this
```
Verify after the startup banner appears:
```bash
celery -A app.workers.celery_app inspect ping    # → "-> celery@<host>: OK ... pong"
```

## 4. Frontend (from frontend/)
```bash
[ -d node_modules ] || npm ci    # reproducible install from package-lock.json
npm run dev                           # background this; serves on http://localhost:5173
```
Verify the dev server and the /api → :8000 proxy in one pass (vite also needs a moment to boot):
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:5173/    # → 200
curl -s http://localhost:5173/api/calls/1    # → {"detail":"Not implemented"} — 501 through the proxy
```

## What "healthy" means in this skeleton
- All `/api/*` endpoints return **501 by design** — the repo is a skeleton. A 501 from
  /api/calls, /api/reports, /api/chat, or /api/kb proves the stack works; it is NOT a failure.
- Implemented and expected to work: `GET /health`; `POST /telephony/voice` (returns TwiML
  `<Say>` — Polly.Zeina, language "arb"/MSA); `POST /telephony/status` (logs CallSid/status, returns 204).
- `POST /telephony/gather` raises NotImplementedError → HTTP 500. Expected; not a stack failure.
- Never smoke-test `app.telephony.client.place_call` — it is implemented and dials a real Twilio call.

## Stop everything
```bash
pkill -f "uvicorn app.main:app"; pkill -f "celery -A app.workers"; pkill -f vite
docker compose down    # from repo root; add -v ONLY to wipe Postgres data
```
