# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI-powered call center for Arabic (Egyptian + Modern Standard) with two products sharing one backend:

1. **Outbound follow-up calls** — automated calls verify customers completed the procedures discussed on a prior inbound call, log outcomes, and feed an auto-generated "First Call Resolutions" (FCR) report for the quality team.
2. **Agent-facing RAG chatbot** — Arabic Q&A over the internal knowledge base with **cited sources**, embedded in the agent desktop as a widget.

Scope and success metrics live in `AI-Powered Outbound Calls (Arabic) (1).docx` (the source of truth). `sprint_plan_visual.pdf` maps modules to a 5-person team — **treat its sprint sequencing as directional only; it has known logical inconsistencies** (e.g., CRM-list integration scheduled after the queue that consumes it, RAG connected to real KB storage after answer generation is built). Don't derive task ordering from it.

**Status: skeleton.** Nearly every function is a stub (`NotImplementedError` in modules, HTTP 501 in endpoints); only `/health` works and only `tests/test_health.py` passes. Don't assume any feature described here is implemented yet.

## Commands

Backend (from `backend/`):
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Infra: `docker compose up -d` (from repo root — Postgres 16 + Redis 7)
- API: `uvicorn app.main:app --reload` → http://localhost:8000/docs
- Worker: `celery -A app.workers.celery_app worker --loglevel=info`
- Tests: `pytest` · single test: `pytest tests/test_health.py::test_health -v`
- Lint: `ruff check app tests`

Frontend (from `frontend/`):
- `npm install` · `npm run dev` (proxies `/api` → :8000) · `npm run build`

## Architecture

Monorepo: FastAPI backend (`backend/app/`) + React/Vite dashboard (`frontend/`). The backend is organized by team module, one owner each — keep new code inside its owning module and call across modules through their public functions:

- `app/speech/` — Whisper STT, Arabic TTS (provider not yet selected — all TTS calls stay behind `tts.synthesize`), telephony↔model audio conversion (pydub, needs ffmpeg)
- `app/telephony/` — Twilio client wrapper, webhook router mounted at `/telephony/*`, retry policy + human-agent fallback (`call_flow.py`)
- `app/conversation/` — branching dialog tree (`dialog.py`: intents نعم/لا/غير متأكد/agent → actions) and `rag/` (ingest→chunk→embed to Pinecone, retrieve top-K, cited answer generation)
- `app/data/` — SQLAlchemy models (`CallLog`, `KBDocument`), FCR/KPI reporting, OAuth2 + RBAC (KB content is proprietary; chat/kb/report endpoints get role-guarded)
- `app/workers/` — Celery app (Redis broker) + all scheduled/queued work: call batches, retries, nightly KB ingestion, report generation
- `app/api/` — HTTP surface consumed by the dashboard: `calls`, `reports`, `chat`, `kb`

### The call loop (crosses every module)
`workers/tasks.py` enqueues a call → `telephony/client.place_call` dials via Twilio → Twilio POSTs to `telephony/webhooks.py` → audio → `speech/audio` (format) → `speech/stt.transcribe` → `conversation/dialog.next_action` (mark resolved / offer help / transfer to human) → `speech/tts.synthesize` Arabic reply → outcome persisted to `CallLog` → aggregated by `data/reporting.py` → served at `/api/reports` → dashboard.

### The RAG loop
Upload via `/api/kb` → `conversation/rag/ingest.py` (chunk + embed → Pinecone, stamps `KBDocument.embedded_at`) → agent query via `/api/chat/query` → `rag/retrieve.py` → `rag/answer.py` (LLM answer **with source citations** — a hard requirement) → `ChatWidget` in the frontend.

## Conventions

- All config through `app/config.py` (`from app.config import settings`) — never read `os.environ` in modules. New key = `Settings` field + `.env.example` entry (+ docker-compose service if it's infra).
- Provider SDKs (Twilio, OpenAI, Pinecone, TTS) stay isolated behind their module's wrapper so providers can be swapped; the planning docs name specific vendors but every one is marked swappable.
- Webhook handlers under `/telephony` must respond fast and be idempotent — Twilio retries on timeout.
- Customer/agent-facing text is Arabic; code, comments, and logs are English. Arabic UI content renders RTL (`dir="rtl"`, see `ChatWidget.tsx`).
- No Alembic migrations yet — once schemas leave the skeleton stage, add Alembic before changing `models.py`.
