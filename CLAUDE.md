# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI-powered call center for Arabic (Egyptian + Modern Standard) with two products sharing one backend:

1. **Outbound follow-up calls** — automated calls verify customers completed the procedures discussed on a prior inbound call, log outcomes, and feed an auto-generated "First Call Resolutions" (FCR) report for the quality team.
2. **Agent-facing RAG chatbot** — Arabic Q&A over the internal knowledge base with **cited sources**, embedded in the agent desktop as a widget.

Scope and success metrics live in `AI-Powered Outbound Calls (Arabic) (1).docx` (the source of truth). `sprint_plan_visual.pdf` maps modules to a 5-person team — **treat its sprint sequencing as directional only; it has known logical inconsistencies** (e.g., CRM-list integration scheduled after the queue that consumes it, RAG connected to real KB storage after answer generation is built). Don't derive task ordering from it.

**Status: early skeleton — check the code, it moves fast.** Most functions are stubs (`NotImplementedError` in modules, HTTP 501 in `/api/*` endpoints). Implemented so far: `/health`, and in telephony `place_call` (dials a real Twilio call — never smoke-test it), `POST /telephony/voice` (TwiML greeting), and `POST /telephony/status`; `/telephony/gather` is still a stub. Don't assume anything else described here is implemented yet.

Project skills in `.claude/skills/` cover the recurring workflows: `run-stack` (launch/health-check the dev stack), `verify` (verify a change end-to-end), `test-call-flow` (simulate the Twilio loop, Arabic intent phrases, tunnel setup), `db-migrate` (Alembic setup and per-change migrations).

## Commands

Backend (from `backend/`):
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Infra: `docker compose up -d` (from repo root — Postgres 18 w/ pgvector + Redis 7 + TEI embedding server), then `alembic upgrade head` (from `backend/`)
- API: `uvicorn app.main:app --reload` → http://localhost:8000/docs
- Worker: `celery -A app.workers.celery_app worker --loglevel=info`
- Tests: `pytest` · single test: `pytest tests/test_health.py::test_health -v`
- Lint: `ruff check app tests`

Frontend (from `frontend/`):
- `npm ci` · `npm run dev` (proxies `/api` → :8000) · `npm run build`

## Engineering process

See [CONTRIBUTING.md](CONTRIBUTING.md) — it is binding: never commit to `main` directly; branch as `<module>/<short-desc>`; Conventional Commits; PRs need green CI (`backend` + `frontend` checks in `.github/workflows/ci.yml`) and one review (owners in `.github/CODEOWNERS`); PR descriptions state how the change was verified (verify skill); schema changes ship an Alembic migration in the same PR.

## Architecture

Monorepo: FastAPI backend (`backend/app/`) + React/Vite dashboard (`frontend/`). The backend is organized by team module, one owner each — keep new code inside its owning module and call across modules through their public functions:

- `app/speech/` — Whisper STT, Arabic TTS (provider not yet selected — all TTS calls stay behind `tts.synthesize`), telephony↔model audio conversion (pydub, needs ffmpeg)
- `app/telephony/` — Twilio client wrapper, webhook router mounted at `/telephony/*`, retry policy + human-agent fallback (`call_flow.py`)
- `app/conversation/` — branching dialog tree (`dialog.py`: intents نعم/لا/غير متأكد/agent → actions) and `rag/` (ingest→chunk→embed via the local TEI container into pgvector `kb_chunks`, hybrid top-K retrieval (pgvector cosine + Arabic-normalized BM25, RRF-fused), cited answer generation)
- `app/data/` — SQLAlchemy models (`CallLog`, `KBDocument`), FCR/KPI reporting, OAuth2 + RBAC (KB content is proprietary; chat/kb/report endpoints get role-guarded)
- `app/workers/` — Celery app (Redis broker) + all scheduled/queued work: call batches, retries, nightly KB ingestion, report generation
- `app/api/` — HTTP surface consumed by the dashboard: `calls`, `reports`, `chat`, `kb`

### The call loop (crosses every module)
`workers/tasks.py` enqueues a call → `telephony/client.place_call` dials via Twilio → Twilio POSTs to `telephony/webhooks.py` → audio → `speech/audio` (format) → `speech/stt.transcribe` → `conversation/dialog.next_action` (mark resolved / offer help / transfer to human) → `speech/tts.synthesize` Arabic reply → outcome persisted to `CallLog` → aggregated by `data/reporting.py` → served at `/api/reports` → dashboard.

### The RAG loop
Upload via `/api/kb` → `conversation/rag/ingest.py` (chunk + embed via the TEI container, vectors → pgvector `kb_chunks`, stamps `KBDocument.embedded_at`) → agent query via `/api/chat/query` → `rag/retrieve.py` → `rag/answer.py` (Arabic answer **with source citations** — a hard requirement, so citations are *not* prompted for: each retrieved chunk is sent as its own plain-text `document` block with Anthropic's **Citations API** enabled, and the returned citations are bound to exact spans of those passages — a citation cannot name a document that was never retrieved) → `ChatWidget` in the frontend. Embeddings are `intfloat/multilingual-e5-large` (1024-dim); e5 needs `query:`/`passage:` prefixes, applied inside `rag/embeddings.py` — never prefix at call sites.

## Conventions

- All config through `app/config.py` (`from app.config import settings`) — never read `os.environ` in modules. New key = `Settings` field + `.env.example` entry (+ docker-compose service if it's infra).
- Provider SDKs and services (Twilio, OpenAI, the TEI embedding server, TTS) stay isolated behind their module's wrapper so providers can be swapped; the planning docs name specific vendors but every one is marked swappable (Pinecone was already swapped for pgvector).
- Webhook handlers under `/telephony` must respond fast and be idempotent — Twilio retries on timeout.
- Customer/agent-facing text is Arabic; code, comments, and logs are English. Arabic UI content renders RTL (`dir="rtl"`, see `ChatWidget.tsx`).
- Alembic lives in `backend/alembic/`; migration `0001` is hand-written and must run on both Postgres and SQLite (`tests/test_migrations.py` enforces model↔migration parity). Every `models.py` change ships a migration in the same PR (`db-migrate` skill).
