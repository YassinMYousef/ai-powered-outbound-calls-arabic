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
  `AppShell` with an Overview/Details tab bar, switching between:
  - `frontend/src/pages/OverviewPage.tsx` — small insights: the 3 stat cards
    only, for a quick glance.
  - `frontend/src/pages/DetailsPage.tsx` — the same stat cards for context,
    plus the 3 trend charts.
- `frontend/src/pages/AgentConsolePage.tsx` — the agent view: the Knowledge
  Base Assistant only, one page, no tabs. Split out from `DashboardPage` so
  each role maps to a whole page rather than a section within one page.
- `frontend/src/types/reports.ts`, `frontend/src/types/chat.ts` — TypeScript
  types mirroring the exact backend response shapes (`GET /api/reports/kpis`,
  `GET /api/reports/trends`, and `POST /api/chat/query`).
- `frontend/src/hooks/useReports.ts` — fetches KPIs + trends once per
  `DashboardPage` mount and exposes loading/error/retry state. (The Sprint 2
  mock files `data/mockReports.ts` / `data/mockChat.ts` were deleted when the
  real endpoints landed.)

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

## Still mocked / out of scope

- The dashboard and chat widget now call the real API (`/api/reports/kpis`,
  `/api/reports/trends`, `POST /api/chat/query`) with loading/error states.
  Chat still needs `ANTHROPIC_API_KEY` + the TEI embedder + pgvector running,
  or the widget shows its error bubble.
- No real authentication (see Role-based access above) — sign-in is a local
  role picker, not connected to the backend, and `/api/chat/query` is sent
  unauthenticated until OAuth2/RBAC lands (`backend/app/api/chat.py`
  `TODO(auth)`).
- No manual dark-mode toggle (see Design system above).

## Continuing into Sprint 3/4

1. Wire real OAuth2/RBAC into `AuthContext` per the Role-based access section
   above, once Person D's backend work lands, and attach the bearer token to
   the `ChatWidget` and reports requests.
2. Add integration tests across the full call flow and a chatbot-accuracy test
   suite (Sprint 4 tasks, not yet started).

## Verification

- `npm run build` (`tsc --noEmit && vite build`) passes clean.
- `npm run dev` serves the app at `http://localhost:5173`.
- No headless-browser tool was available in the environment this was built in,
  so the UI was verified by build/type-check only — open the dev server in a
  browser to confirm the visual result before merging.
