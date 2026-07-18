# CallCenter — AI-Powered Arabic Call Center

Two products sharing one backend:

1. **AI outbound follow-up calls (Arabic)** — automated calls verify that customers completed the procedures discussed on a prior inbound call, log outcomes, and feed a "First Call Resolutions" (FCR) report.
2. **Agent-facing RAG chatbot** — Arabic Q&A over the internal knowledge base with cited sources, embedded in the agent desktop.

Requirements: `AI-Powered Outbound Calls (Arabic) (1).docx` · Team/sprint plan: `sprint_plan_visual.pdf`

## Documentation

- **[docs/implementation.md](docs/implementation.md)** — what is built today: module status, the RAG pipeline, the dialog engine, the data model, config, tests, and the known gaps. **Start here.**
- [docs/architecture.md](docs/architecture.md) — target design: system model, call loop, dialog tree, retry policy, RAG loops (Mermaid; exports in [docs/diagrams/](docs/diagrams/)).
- [CONTRIBUTING.md](CONTRIBUTING.md) — branching, commits, review, and CI rules (binding).

## Layout

```
backend/    FastAPI API + call engine + Celery workers (Python 3.11+)
  app/
    speech/         STT (Whisper) / TTS / audio conversion      — Person A
    telephony/      Twilio client, webhooks, retry & fallback   — Person B
    conversation/   Dialog tree + rag/ (ingest, retrieve, answer) — Person C
    data/           DB models, FCR reporting, OAuth2/RBAC       — Person D
    workers/        Celery app + scheduled tasks
    api/            HTTP endpoints consumed by the dashboard
frontend/   React + Vite dashboard & embeddable chat widget     — Person E
```

## Quickstart

```bash
# Infra (Postgres 18 + Redis 7)
docker compose up -d

# Backend API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # fill in provider keys
uvicorn app.main:app --reload # http://localhost:8000/docs

# Celery worker (separate terminal, same venv)
celery -A app.workers.celery_app worker --loglevel=info

# Frontend
cd frontend
npm ci
npm run dev                   # http://localhost:5173, proxies /api → :8000
```

See `CLAUDE.md` for architecture details and conventions.

## Sprint 1 operations

The Sprint 1 storage schema is managed with Alembic. After starting PostgreSQL,
run `cd backend && alembic upgrade head`. Centralized structured logging is provided
by Grafana + Loki; see [docs/logging.md](docs/logging.md) for setup and verification.
