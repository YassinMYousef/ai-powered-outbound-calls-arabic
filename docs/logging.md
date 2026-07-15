# Centralized logging (Grafana + Loki)

Sprint 1 uses Grafana Loki rather than ELK. Loki is a smaller, Docker-native log
aggregation stack and is sufficient for the application's structured logs without
adding Elasticsearch's operational overhead. The backend writes JSON Lines to
`backend/logs/callcenter.jsonl`; Promtail tails that file and sends it to Loki.
Grafana is provisioned with Loki as its default data source.

## Run locally

From the repository root:

```bash
docker compose up -d
cd backend
cp .env.example .env
uvicorn app.main:app --reload
```

Open `http://localhost:3000` and sign in with `admin` / `admin` (local development
only). In **Explore**, select Loki and query:

```logql
{service="callcenter-backend"}
```

Call `GET http://localhost:8000/health`; its JSON request-completion record should
appear shortly. The response's `X-Request-ID` can be used to correlate application
logs for a single request.

## Operational notes

`LOG_FILE`, `LOG_LEVEL`, `LOG_MAX_BYTES`, and `LOG_BACKUP_COUNT` are configured
through `app.config.Settings`. The default file handler rotates at 10 MiB and keeps
five old files. Set a non-default Grafana administrator password before any shared
deployment, and replace the local filesystem Loki storage with managed/object storage
when deploying beyond a single node.
