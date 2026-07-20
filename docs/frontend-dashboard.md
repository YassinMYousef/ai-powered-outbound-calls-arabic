# Frontend / Dashboard — Person E, Sprints 1–2

Module owner: Person E (Frontend/Dashboard). Source of truth for sprint scope:
`sprint_plan.md.pdf` (v2 — supersedes `sprint_plan_visual.pdf`, which is v1 and
does not reflect the corrected Sprint 4 dependency below).

## Scope

| Sprint | Tasks | Goal | Status |
|---|---|---|---|
| 1 | Build React dashboard shell | Base dashboard app structure ready | Done |
| 2 | Add charts (FCR rate / AHT / completion %); build embeddable chat UI component | Dashboard visuals + chat widget UI built, on mock data | Done |
| 3 | Integrate dashboard with the reporting API (needs Backend, Sprint 2) | Dashboard shows live data instead of mocks | Not started — blocked, see below |
| 4 | Connect chat widget to the RAG answer-generation API (needs Person C's RAG work **and** Person D's OAuth2/access-control, both resolving end of Sprint 3); write integration tests across the full call flow; write a chatbot-accuracy test suite | Full system connected end-to-end, test coverage in place | Not started — blocked, see below |

Sprint 4's dual dependency (RAG **and** auth) is a v2 correction over the original
plan: the RAG API will likely require an authenticated request once Person D's
OAuth2/RBAC is live, so the chat widget's real integration can't land until both
are done — not just the RAG pipeline alone.

## Design system

Chosen via the `ui-ux-pro-max` skill (`--design-system` "internal analytics
dashboard, dense" + `--domain typography` "arabic RTL bilingual chat widget"),
then adjusted for this project's specific constraints below.

**Palette** — data-dense dashboard pattern, status colors reserved for KPI
thresholds rather than decoration:

| Role | Light | Dark |
|---|---|---|
| Brand / primary | `#1e40af` | `#60a5fa` |
| Accent (warn) | `#d97706` | `#f59e0b` |
| Success | `#16a34a` | `#22c55e` |
| Destructive | `#dc2626` | `#f87171` |
| Surface / card / border | `#f8fafc` / `#ffffff` / `#e2e8f0` | `#0b1220` / `#111827` / `#1f2937` |

Defined as CSS custom properties in `frontend/src/index.css`, switched via
`@media (prefers-color-scheme: dark)` — no manual theme toggle; the app follows
the OS setting, which is sufficient for an internal tool nobody asked to
override.

**Typography** — Inter for all UI chrome (headings, labels, body — chosen over
the tool's raw "Fira Code headings" suggestion, which reads as code rather than
prose at heading size); a monospace face (JetBrains Mono, `.font-mono-num`) is
reserved specifically for KPI numbers, which is where a dashboard's "precise,
technical" feel actually belongs. Noto Sans Arabic handles the chat widget's
Arabic content (`.font-arabic`).

**Language policy** — the frontend's own UI (labels, buttons, headers,
placeholders, KPI section) is English throughout. Arabic is used only where the
product itself requires it: the agent's typed query, the RAG model's generated
answer, and literal cited quotes pulled verbatim from Arabic KB documents
(`backend/app/conversation/rag/answer.py`'s `quotes` field). Source *titles* are
English display labels, not model output, so they stay English too.

**Density** — dashboard-tier spacing (8–32px scale), not the wider marketing-page
default, per the tool's density dial for this product type.

## What's built

- `frontend/src/index.css` — design tokens, Google Fonts import, dark-mode
  media query.
- `frontend/src/components/layout/AppShell.tsx` — header + content container
  (Sprint 1 shell), the signed-in user chip / sign-out / dev role switcher
  described below, and an optional tab bar (`tabs` prop) for roles with more
  than one sub-page.
- `frontend/src/components/StatCard.tsx` — KPI card with status coloring.
  Only FCR rate gets a good/warn/bad judgment, because ≥90% is the one
  explicit target in the requirements doc; completion % and AHT show neutral
  trend deltas without inventing an unstated threshold.
- `frontend/src/components/KpiStatCards.tsx` — the 3 stat cards, extracted so
  Overview and Details can both render them without duplicating the mock-data
  wiring.
- `frontend/src/components/charts/TrendChart.tsx` — reusable 14-day trend
  chart (recharts `AreaChart`), instantiated three times in `DetailsPage`.
- `frontend/src/components/ChatWidget.tsx` — full chat UI: message list,
  citation display, suggested-query chips, loading state, RTL/LTR mixed
  layout per the language policy above.
- `frontend/src/pages/DashboardPage.tsx` — the quality-manager view: an
  `AppShell` with an Overview/Details/Agent Activity tab bar, switching between:
  - `frontend/src/pages/OverviewPage.tsx` — small insights: the 3 stat cards
    only, for a quick glance.
  - `frontend/src/pages/DetailsPage.tsx` — the same stat cards for context,
    plus the 3 trend charts.
  - `frontend/src/pages/AgentActivityPage.tsx` — see "Agent activity" below.
- `frontend/src/pages/AgentConsolePage.tsx` — the agent view: an `AppShell`
  with an Assistant/Call Queue tab bar (same tab pattern as the quality
  manager's tabs), switching between:
  - the Knowledge Base Assistant (`ChatWidget`)
  - `frontend/src/pages/CallQueuePage.tsx` — see "Call queue" below.
- `frontend/src/types/reports.ts`, `frontend/src/types/chat.ts`,
  `frontend/src/types/calls.ts`, `frontend/src/types/agentActivity.ts` —
  TypeScript types mirroring the exact backend shapes where one exists
  (`GET /api/reports/kpis`, `POST /api/chat/query`, the `CallLog` model's
  status/outcome check constraints) so later swaps are a drop-in replacement
  of a data source, not a rewrite; `agentActivity.ts` has no backend
  counterpart yet (see below).
- `frontend/src/data/mockReports.ts`, `frontend/src/data/mockChat.ts`,
  `frontend/src/data/mockCalls.ts`, `frontend/src/data/mockAgentActivity.ts` —
  the mock data backing each mocked view.

## Role-based access (mock, pending backend RBAC)

`backend/app/data/auth.py` is a stub — `get_current_user()` and
`require_role()` both `raise NotImplementedError`, and there is no
`/api/auth/token` route (Person D's Sprint 3 task, not started). The pages
below exist so the UI shape is ready, but **nothing here calls the backend**:

- `frontend/src/auth/AuthContext.tsx` — in-memory-only auth state (`user`,
  `login`, `switchRole`, `logout`). `login` never hits the network; it just
  stores the role picked on the login form.
- `frontend/src/pages/LoginPage.tsx` — sign-in form (email/password + a
  temporary role selector), clearly labeled as a mock, not wired to
  `/api/auth/token`.
- `frontend/src/pages/UnauthorizedPage.tsx` — shown for a signed-in role that
  isn't mapped to a page. Defensive today (both current roles route
  somewhere); becomes load-bearing once real roles come from the backend.
- `frontend/src/App.tsx`'s `RoleRouter` — `quality_manager` → `DashboardPage`,
  `agent` → `AgentConsolePage`, anything else → `UnauthorizedPage`.
- `AppShell`'s header — signed-in user chip, sign-out button, and (dev-build
  only, `import.meta.env.DEV`) a role switcher for previewing both views
  without re-authenticating.

**Once Person D ships OAuth2/RBAC**, per this task's explicit instruction,
wire this back up to what he built rather than replacing it wholesale:

1. Add a real `POST /api/auth/token` call in `AuthContext.login`, and derive
   `user` (including `role`) from the decoded JWT the backend returns instead
   of the local role select.
2. Drop the dev-only role switcher in `AppShell` — real users won't have one.
3. Attach the token to every `/api` request that needs it (`ChatWidget`'s
   future `POST /api/chat/query` call in particular — see
   `backend/app/api/chat.py`'s `TODO(auth)`).
4. `RoleRouter`'s mapping and `UnauthorizedPage` can stay as-is; they already
   key off `user.role`, which will just come from the server instead of the
   login form.

## Call queue (agent, mostly simulated + one real control — outside the formal sprint plan)

Requested directly (not in `sprint_plan.md.pdf`): agents should see scheduled
calls and the queue, and be able to trigger a call with a button. Built as
`frontend/src/pages/CallQueuePage.tsx`:

- **The table is still simulated mock data** — there's still no `GET` list
  endpoint for calls, so there's nothing real to populate rows from. "Start
  call" / "Retry" plays out `queued → initiated → ringing → in_progress →
  completed/no_answer/failed` client-side with a random outcome, using the
  same status values and retry rule as the backend
  (`backend/app/telephony/call_flow.py`'s `MAX_ATTEMPTS = 3` and
  `_RETRYABLE_STATUSES`).
- **Manual status/outcome override**: once a call is finalized (`completed`,
  `no_answer`, `busy`, `failed`, `cancelled`), the row grows inline `<select>`
  editors so an agent can correct the recorded status/outcome by hand. This is
  a local-only mutation — there's no `PATCH`/update endpoint yet either.
- **`frontend/src/components/PlaceRealCallForm.tsx` is genuinely wired up** —
  it `POST`s to `/api/calls` (below), which really dials through Twilio. Kept
  as a visually separate card below the mock table, not a button on a mock
  row, so a click can never be confused with the simulated ones. It requires
  a phone number, shows a browser `confirm()` naming the number before
  sending, and surfaces the created call's id/status or any error inline.

### The new backend endpoint (`backend/app/api/calls.py`)

Person B's `workers/tasks.py` (`place_outbound_call`, `schedule_follow_up_batch`)
and the `/telephony/*` webhook loop (`voice` → `gather` → dialog → `status`,
including `CallLog` persistence and retry) were already fully implemented —
but `api/calls.py`, the HTTP layer the frontend actually calls, was never
updated to use them; it was still three routes of `HTTPException(501)`. That
mismatch — not a missing feature — was the actual blocker for "make a call
through the UI":

- `POST /api/calls` *(new)* — creates a `CallLog` row (`status="queued"`) and
  enqueues `place_outbound_call` via Celery (`apply_async(..., retry=False)`,
  same fire-and-forget-if-the-broker's-down pattern as `api/kb.py`'s
  `_enqueue_ingest`). This is what `PlaceRealCallForm` calls.
- `POST /api/calls/schedule` *(fixed)* — now actually enqueues
  `schedule_follow_up_batch` instead of raising 501. Careful with this one
  manually: it dials **every** `CallLog` row currently at `status="queued"`,
  not just one.
- `GET /api/calls/{call_id}` *(fixed)* — now actually reads the `CallLog` row
  instead of raising 501.

Tests: `backend/tests/test_calls_api.py` (6 cases). The Celery enqueue calls
are monkeypatched in tests, same pattern as `test_kb_api.py`, so the suite
never needs Redis or real Twilio credentials.

**Live-verified end-to-end**, not just unit tests: `docker compose up -d`
(Postgres/Redis/TEI) → `alembic upgrade head` → `uvicorn app.main:app` →
`celery -A app.workers.celery_app worker --pool=solo` (`--pool=solo` because
the default prefork pool doesn't work on Windows) → a real call placed from
`PlaceRealCallForm` to the team's verified test number
(`HUMAN_AGENT_NUMBER` in `.env`). First attempt landed a `CallLog` row with a
real Twilio SID but got stuck at `status="initiated"` forever, no
`duration_seconds`/`completed_at` — root cause was `PUBLIC_BASE_URL`'s ngrok
tunnel being offline (`ERR_NGROK_3200`), so Twilio could never reach
`/telephony/voice` or `/telephony/status`. **The tunnel must be running
(`ngrok http --url=<PUBLIC_BASE_URL's host> 8000`) for any real call to
resolve past "initiated"** — this isn't specific to the new endpoint, it's
true of `place_call` generally, but it's easy to miss since the endpoint
still returns 202 and creates the row either way. With the tunnel up, a
second call completed correctly: `status="completed"`, `duration_seconds=14`,
`started_at`/`completed_at` both set, transcript recorded.

TODO(auth): `POST /api/calls` is unauthenticated, same gap already flagged on
`/api/chat` and `/api/kb` — guard with `data/auth.require_role` once RBAC lands.

## Agent activity (manager, mock — outside the formal sprint plan)

Also requested directly: the quality manager should see each agent's progress
and what they did. Built as `frontend/src/pages/AgentActivityPage.tsx`, a
third `DashboardPage` tab — a roster table (calls handled, resolved %, KB
queries asked, last active) plus a per-agent chronological activity feed.

**Why this one has no real-data path yet, unlike the other mocked views**:
`backend/app/data/models.py`'s `CallLog` has no agent-identity column at all —
outbound calls are AI-driven, and a human agent only enters the picture via
`call_flow.transfer_to_agent`, which doesn't persist *who* picked up. So this
isn't blocked on an unimplemented endpoint the way KPIs/chat/calls are —
there's no schema to point an endpoint at yet. Surfacing this is itself the
useful output: before this can go live, `CallLog` (or a new table) needs an
agent-identity field, and something needs to record KB-query events per
agent (today `ChatWidget` has no concept of "whose" question it is either).

## Explicitly mocked / out of scope for this PR

- No live API calls anywhere: `GET /api/reports/kpis` returns HTTP 501 today
  (`backend/app/data/reporting.py` is all `NotImplementedError`), and
  `POST /api/chat/query` needs `ANTHROPIC_API_KEY` + the TEI embedder +
  pgvector all running, none of which are wired into local dev yet.
- No real authentication (see Role-based access above) — sign-in is a local
  role picker, not connected to the backend.
- The call queue *table* is still simulated (see Call queue above) — only
  `PlaceRealCallForm`'s single control actually dials.
- No real agent-activity data (see Agent activity above) — the backend has
  nothing to fetch yet, not just an unimplemented endpoint.
- No manual dark-mode toggle (see Design system above).

## Continuing into Sprint 3/4

1. In `KpiStatCards.tsx` and `DetailsPage.tsx`, replace the `data/mockReports.ts`
   imports with `api<Kpis>('/api/reports/kpis')` (see `frontend/src/api/client.ts`)
   once Person D's reporting pipeline is live.
2. In `ChatWidget.tsx`, replace `mockAnswer()` with
   `api<ChatResponse>('/api/chat/query', { method: 'POST', body: JSON.stringify({ query }) })`,
   including an auth token — not a raw unauthenticated request, per the v2
   plan's explicit reminder.
3. Wire real OAuth2/RBAC into `AuthContext` per the Role-based access section
   above, once Person D's backend work lands.
4. Add integration tests across the full call flow and a chatbot-accuracy test
   suite (Sprint 4 tasks, not yet started).
5. In `CallQueuePage.tsx`, once Person B's queue and a real `/api/calls` list +
   schedule endpoint exist, replace `data/mockCalls.ts` and `simulateCall()`
   with a real fetch + `POST /api/calls/schedule` — and add an explicit
   confirm step before that call, since it dials (and bills) a real number.

## Verification

- `npm run build` (`tsc --noEmit && vite build`) passes clean.
- `npm run dev` serves the app at `http://localhost:5173`.
- No headless-browser tool was available in the environment this was built in,
  so the UI was verified by build/type-check only — open the dev server in a
  browser to confirm the visual result before merging.
