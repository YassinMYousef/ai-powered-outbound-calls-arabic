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
  `AppShell` with an Overview/Details/Knowledge Base/Unanswered/Operations/
  Agent Activity/Customers/Agents tab bar, switching between:
  - `frontend/src/pages/OverviewPage.tsx` — small insights: the 3 stat cards
    only, for a quick glance.
  - `frontend/src/pages/DetailsPage.tsx` — the same stat cards for context,
    plus the 3 trend charts.
  - `frontend/src/pages/KnowledgeBasePage.tsx`, `UnansweredQuestionsPage.tsx`,
    `OperationsPage.tsx` — the KB management, KB-gap review, and call/report
    operations sub-pages. Real: wired to `/api/kb/documents`, `/api/kb/gaps`,
    and `/api/calls` + `/api/reports`.
  - `frontend/src/pages/AgentActivityPage.tsx` — see "Agent activity" below (mock).
  - `frontend/src/pages/CustomersPage.tsx` — see "Customers / CRM" below. Real.
  - `frontend/src/pages/AgentsPage.tsx` — see "Agent roster" below. Also real.
- `frontend/src/pages/AgentConsolePage.tsx` — the agent view: an `AppShell`
  with an Assistant/Call Queue tab bar (same tab pattern as the quality
  manager's tabs), switching between:
  - the Knowledge Base Assistant (`ChatWidget`)
  - `frontend/src/pages/CallQueuePage.tsx` — see "Call queue" below. Real.
- `frontend/src/types/reports.ts`, `chat.ts`, `calls.ts`, `customers.ts`,
  `agents.ts`, `agentActivity.ts` — TypeScript types mirroring the exact
  backend shapes where one exists (all of them now, except `agentActivity.ts`
  — see "Agent activity" below for why that one still has no backend counterpart).
- `frontend/src/hooks/useReports.ts` — fetches KPIs + trends once per
  `DashboardPage` mount and exposes loading/error/retry state.
- The Sprint 2 mock files `data/mockReports.ts` / `data/mockChat.ts` were
  deleted when the real reporting + chat endpoints landed;
  `data/mockAgentActivity.ts` remains, backing the still-mocked Agent Activity.

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

## Call queue (agent, real — outside the formal sprint plan)

Requested directly (not in `sprint_plan.md.pdf`): agents should see scheduled
calls and the queue, and be able to trigger a call with a button. Originally
built as a simulated mock table (see git history on
`frontend/src/pages/CallQueuePage.tsx` if that phase needs revisiting), but
once `GET /api/calls` existed there was no reason to keep it mocked, so it
was rewritten to be fully real:

- `CallQueuePage.tsx` fetches `GET /api/calls` (all `CallLog` rows, newest
  first) on mount, with a manual "Refresh" button. A customer flagged on the
  Customers tab shows up here as a `queued` row.
- Each `queued` row gets a real **"Start call"** button →
  `POST /api/calls/{id}/dial` → `confirm()` naming the number first.
  Non-`queued` rows show their status only — there's no manual
  status/outcome override anymore (that was a mock-only affordance; there's
  no `PATCH` endpoint, and overriding real data by hand isn't the goal).
- `frontend/src/components/PlaceRealCallForm.tsx` (unchanged in behavior)
  stays as a separate card below the table, for dialing a number that isn't
  already a customer/queued row — e.g. an ad hoc test call.

### The backend endpoints (`backend/app/api/calls.py`)

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
- `GET /api/calls` *(new)* — every `CallLog` row, newest first. Backs
  `CallQueuePage.tsx`'s table.
- `POST /api/calls/{call_id}/dial` *(new)* — dial one existing row, only
  while it's still `"queued"` (409 otherwise). Backs the per-row "Start call"
  button. Retries are still handled automatically by
  `telephony/webhooks.py`'s `/status` handler, not by re-dialing a finished
  row through here.
- `GET /api/calls/{call_id}` *(fixed)* — now actually reads the `CallLog` row
  instead of raising 501.

Tests: `backend/tests/test_calls_api.py` (12 cases). The Celery enqueue calls
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

## Customers / CRM (manager, real — Person B's Sprint 4)

Person B's Sprint 4 task per `sprint_plan.md.pdf` is "Integrate CRM/customer-
flagged-list API." There is no real external CRM to integrate with — the
requirements doc's architecture diagram has a `[CRM / Inbound Call Records]`
box with nothing concrete behind it. Rather than build a stand-in "import a
list" endpoint, this is a genuine new CRM module living in the project:

- `backend/app/data/models.py`'s new `Customer` model (`name`, `phone`
  unique, `notes`) plus a nullable `CallLog.customer_id` FK — migration
  `6d3bc12f912a_add_customers_table_and_call_logs_.py`. `customer_id` is
  `NULL` for calls dialed ad hoc (e.g. `PlaceRealCallForm`, or anything from
  before this migration) and set when a call originates from flagging a
  customer.
- `backend/app/api/customers.py`: `POST /api/customers` (create, 409 on
  duplicate phone), `GET /api/customers` (list), `GET /api/customers/{id}`
  (customer + call history), `DELETE /api/customers/{id}` (past call history
  is kept — `customer_id` on those rows just goes `NULL`, handled by
  SQLAlchemy's own unit-of-work dependency resolution, not a DB-level
  cascade, so it's identical on SQLite and Postgres),
  `POST /api/customers/{id}/flag` (creates a `status="queued"` `CallLog`
  linked to the customer).
- **Flagging only queues — it does not dial.** `POST /.../flag` returns 201
  and stops there; the row is picked up by the *existing*
  `POST /api/calls/schedule` (or a future nightly scheduler) exactly like any
  other queued row, mirroring the requirements doc's two distinct workflow
  steps ("fetch flagged customers" vs. "schedule outbound call slot"). This
  was a deliberate product decision, not a limitation — see the design
  discussion in this PR's conversation history if the rationale needs
  revisiting.
- `frontend/src/pages/CustomersPage.tsx`: a real (not mock) 4th
  `DashboardPage` tab — add-customer form, customer table, per-row "Flag for
  follow-up" (optional ticket ID), and an expandable per-customer call
  history. All genuinely wired to the endpoints above via `api()`.

**Cross-team note**: this touches `backend/app/data/models.py`, which is
Person D's owned module per `CODEOWNERS` — get their review even though the
feature is framed as Person B's Sprint 4. Anyone with a local dev DB needs
`alembic upgrade head` (from `backend/`) after pulling this to pick up the
new `customers` table.

## Agent roster (manager, real — requested directly, not in the sprint plan)

- `backend/app/data/models.py`'s new `Agent` model (`name`, `email` unique) —
  migration `a64413ab4fa6_add_agents_table.py`. **Not an auth system**:
  `data/auth.py`'s OAuth2/RBAC is still `NotImplementedError`, so this is a
  roster a manager maintains, not account creation or login. **Not yet linked
  to `CallLog`** either — there's no `agent_id` column — so it doesn't yet
  close the gap flagged in Agent Activity above (no real per-agent call
  attribution); that's a natural next step, not done here.
- `backend/app/api/agents.py`: `POST /api/agents` (create, 409 on duplicate
  email), `GET /api/agents` (list), `DELETE /api/agents/{id}`.
- `frontend/src/pages/AgentsPage.tsx`: a real 5th `DashboardPage` tab —
  add-agent form, roster table, per-row delete. Same pattern as
  `CustomersPage.tsx`.

### Full call-flow integration testing (the other half of Sprint 4)

`backend/tests/test_call_flow_integration.py` drives the real functions
across `api/customers.py`, `workers/tasks.py`, and `telephony/webhooks.py`
together — flag a customer → `schedule_follow_up_batch` dials it →
`/telephony/status` reports in-progress then completed → duration/timestamps
persist → the customer's call history reflects it. A second test covers the
no-answer → retry branch. Neither existed before; this was genuinely
untested territory, not a re-test of existing coverage.

Writing it surfaced two real bugs, both fixed alongside it in
`backend/app/telephony/webhooks.py`'s `/status` handler:

1. **The retry row silently dropped `customer_id`.** It copied
   `customer_phone`/`ticket_id` from the original row but not the new FK, so
   a retried call would have lost its CRM link. Fixed by copying
   `customer_id` too.
2. **`place_outbound_call.delay(retry_row.id)` had no error handling** —
   unlike every other Celery enqueue call site in the codebase
   (`api/calls.py`'s `_enqueue_dial`, `api/kb.py`'s `_enqueue_ingest`), a dead
   broker here would have turned a Twilio webhook request into an unhandled
   500. Changed to `apply_async(..., retry=False)` wrapped in the same
   try/except-and-log-a-warning pattern as the others — the row stays
   `"queued"` and `schedule_follow_up_batch` will still pick it up later.

## Explicitly mocked / out of scope for this PR

- The dashboard and chat widget now call the real API (`/api/reports/kpis`,
  `/api/reports/trends`, `POST /api/chat/query`) with loading/error states.
  Chat still needs `ANTHROPIC_API_KEY` + the TEI embedder + pgvector running,
  or the widget shows its error bubble.
- No real authentication (see Role-based access above) — sign-in is a local
  role picker, not connected to the backend, and `/api/chat/query` is sent
  unauthenticated until OAuth2/RBAC lands (`backend/app/api/chat.py`
  `TODO(auth)`).
- No real agent-activity data (see Agent activity above) — the backend has
  nothing to fetch yet, not just an unimplemented endpoint. (The new `Agent`
  roster table doesn't close this gap — it isn't linked to `CallLog`.)
- No manual dark-mode toggle (see Design system above).

## Continuing into Sprint 3/4

1. Wire real OAuth2/RBAC into `AuthContext` per the Role-based access section
   above, once Person D's backend work lands, and attach the bearer token to
   the `ChatWidget` and reports requests (per the v2 plan's explicit reminder,
   not a raw unauthenticated request).
2. Add a chatbot-accuracy test suite (a Sprint 4 task). Full call-flow
   integration testing is done — see `test_call_flow_integration.py` above.
3. Reporting (`/api/reports/kpis` + `/trends`) and chat (`POST /api/chat/query`)
   are now real, and `CallQueuePage.tsx` is fully wired (`GET /api/calls`,
   `POST /api/calls/{id}/dial`). Next natural step is linking `Agent` to
   `CallLog` (an `agent_id` column) so Agent Activity can drop its mock data too.

## Verification

- `npm run build` (`tsc --noEmit && vite build`) passes clean.
- `npm run dev` serves the app at `http://localhost:5173`.
- No headless-browser tool was available in the environment this was built in,
  so the UI was verified by build/type-check only — open the dev server in a
  browser to confirm the visual result before merging.
