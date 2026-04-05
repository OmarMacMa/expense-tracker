# Implementation Plan — 1.0.0 (MVP)

This plan describes how to go from zero to a working MVP using **agentic development**. A solo developer orchestrates AI agents (Claude Code, Copilot CLI, etc.) that write most or all code. Each phase produces a verifiable milestone. Tasks within a phase are scoped so a single agent session can complete one.

---

## How to use this plan

- **Phases are sequential** — each phase depends on the previous one being complete.
- **Tasks within a phase** can often be done in parallel (marked when possible).
- **Each task** includes context refs, inputs, outputs, and verification so an agent can pick it up cold.
- **Before starting a task**, point the agent to the relevant project docs (PRD, ARCHITECTURE, CONVENTIONS, REQUIREMENTS) and this plan.
- **After each task**, verify the output before moving on. Run tests, check endpoints, inspect the code.
- **If a doc becomes outdated** during implementation, update it as part of the task.

### Agent prompting pattern

When handing a task to an agent, include:
1. The task description from this plan
2. References to the relevant sections of the project docs
3. What already exists (output of previous tasks)
4. The verification criteria

---

## Phase 1 — Project scaffolding

**Goal**: Both projects initialize, run locally, and connect to a database. No features yet.

### Task 1.1 — Initialize repository and backend skeleton

**Context**: `CONVENTIONS.md` §1 (structure), §5 (environment setup), §6 (dependencies)

- Initialize git repo with `.gitignore` (Python, Node, IDE files, `.env`)
- Create `backend/` with FastAPI project structure: `app/main.py`, `app/config.py`, `app/db/session.py`
- `requirements.txt` with pinned core deps: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `python-jose[cryptography]`, `httpx`, `structlog`, `slowapi`
- `requirements-dev.txt`: `pytest`, `pytest-asyncio`, `httpx`, `black`, `ruff`
- `pyproject.toml` with `ruff` and `black` config
- `app/config.py` using `pydantic-settings` to load env vars from `.env`
- `backend/.env.example` with all required vars
- Initialize Alembic (`alembic init alembic`), configure `alembic/env.py` for async SQLAlchemy
- Health check endpoint: `GET /api/2.0.0/health` returning `{"status": "ok"}`
- **Verify**: `uvicorn app.main:app --reload` starts, `curl localhost:8000/api/2.0.0/health` returns OK, `ruff check .` and `black --check .` pass

### Task 1.2 — Initialize frontend skeleton

**Context**: `CONVENTIONS.md` §1 (structure), §5 (environment setup), §6 (dependencies)

- Create `frontend/` with Vite + React + TypeScript (`npm create vite@latest`)
- Install and configure: React Router v7, Tailwind CSS, shadcn/ui (init + a few base components), TanStack Query, Recharts
- Pin exact versions in `package.json`
- Set up `vite.config.ts` with proxy: `/api` → `http://localhost:8000`
- Set up `tsconfig.json` with strict mode, path aliases
- Create route stubs for all MVP pages (empty components, correct paths)
- Create `frontend/.env.example`
- **Verify**: `npm run dev` starts, pages route correctly (even if empty), `npx eslint .` and `npx prettier --check .` pass

### Task 1.3 — Local development environment

- Create `docker-compose.yml` at repo root: PostgreSQL 15 service (port 5432, `expense_tracker` db, `devpass` password)
- Create a root-level `README.md` with quickstart instructions (3 terminals: DB, backend, frontend)
- **Verify**: `docker compose up -d` starts PostgreSQL, backend connects to DB

> **Parallelism**: Tasks 1.1 and 1.2 can run in parallel. Task 1.3 after both.

---

## Phase 2 — Database schema and ORM layer

**Goal**: All MVP tables exist in PostgreSQL via Alembic migration. ORM models are complete and tested.

### Task 2.1 — SQLAlchemy models

**Context**: `ARCHITECTURE.md` §5.1 (full schema), `CONVENTIONS.md` §2 (SQL naming)

Create all SQLAlchemy models in `app/models/`:
- `user.py` — users
- `space.py` — spaces, space_members, invite_links
- `category.py` — categories
- `payment_method.py` — payment_methods
- `merchant.py` — merchants
- `expense.py` — expenses, expense_lines, expense_line_tags
- `tag.py` — tags
- `limit.py` — limits, limit_filters
- `__init__.py` — re-export all models

Include 1.1.0+ columns as nullable (recurring_template_id, scheduled_date, beneficiary fields) so the schema doesn't need migration later.

- **Verify**: all models import without error, relationships are correctly defined

### Task 2.2 — Initial Alembic migration and indexes

**Context**: `ARCHITECTURE.md` §5.2 (indexes)

- Generate migration: `alembic revision --autogenerate -m "initial schema"`
- Add all indexes from `ARCHITECTURE.md` §5.2 to the migration
- **Verify**: `alembic upgrade head` creates all tables, `\dt` in psql lists all expected tables, indexes exist

### Task 2.3 — Database session and SpaceScopedRepository

**Context**: `REQUIREMENTS.md` §1 (tenant isolation), `ARCHITECTURE.md` §8 (connection pooling)

- `app/db/session.py` — async SQLAlchemy session factory with pool config (pool_size=5, max_overflow=5, pool_timeout=30, pool_recycle=1800)
- `app/db/repository.py` — `SpaceScopedRepository` base class that auto-injects `space_id` into every query
- Create `get_db` dependency for FastAPI
- Update health check to actually test DB connectivity (return `"db": "connected"` or `"db": "disconnected"` with 503)
- **Verify**: health check reflects actual DB state, toggling DB on/off changes the response

---

## Phase 3 — Authentication

**Goal**: Users can sign in with Google, receive a JWT cookie, and make authenticated API requests.

### Task 3.1 — Google OAuth + JWT

**Context**: `ARCHITECTURE.md` §3 (auth flow), `REQUIREMENTS.md` §1 (security), `CONVENTIONS.md` §5 (Google OAuth setup)

- `app/auth/oauth.py` — Google OAuth flow (redirect to Google, handle callback)
- `app/auth/jwt.py` — JWT creation (7-day expiry), validation, sliding window refresh (<1 day remaining → re-issue)
- `app/auth/router.py` — routes: `GET /auth/google`, `GET /auth/google/callback`, `POST /auth/logout`, `GET /auth/me`
- On callback: create user record if new (upsert by google_id), set httpOnly/Secure/SameSite=Lax cookie
- `GET /auth/me` returns user info + their space(s) if any
- **Verify**: full OAuth flow works locally (Google Cloud Console configured), JWT cookie is set, `/auth/me` returns user data

### Task 3.2 — Auth middleware and guards

**Context**: `REQUIREMENTS.md` §1 (JWT handling, tenant isolation)

- `app/middleware/auth.py` — extract JWT from cookie, validate, inject user into request state. Return 401 if expired/invalid. Sliding window re-issue.
- `app/middleware/space.py` — for `/spaces/{space_id}/...` endpoints, verify user is a member of the space. Return 403 if not.
- Create FastAPI dependencies: `get_current_user`, `get_current_space_member`
- **Verify**: unauthenticated requests to protected endpoints get 401, requests to wrong space get 403

---

## Phase 4 — Space and membership

**Goal**: Users can create a space, configure it, and invite a partner.

### Task 4.1 — Space CRUD + membership

**Context**: `ARCHITECTURE.md` §4.3 (space endpoints), `PRD.md` §4 (space concept), §6.2 (space management)

- `app/schemas/space.py` — request/response schemas
- `app/services/space.py` — create space (+ auto-add creator as member + create "Uncategorized" category + create "Cash" payment method), get space, update space settings
- `app/routers/spaces.py` — `POST /spaces`, `GET /spaces/{id}`, `PUT /spaces/{id}`, `GET /spaces/{id}/members`
- On space creation: auto-seed default categories if requested
- Enforce 10-member limit
- **Verify**: create space → creator is a member, Uncategorized category exists, Cash payment method exists. Update space settings works. Member list returns correctly.

### Task 4.2 — Invite system

**Context**: `PRD.md` §6.2 (invite flow), `REQUIREMENTS.md` §1 (invite links)

- `app/services/invite.py` — generate invite (cryptographically random token, 7-day expiry, single-use), join space via token, invalidation
- `app/routers/spaces.py` (extend) — `POST /spaces/{id}/invite`, `POST /spaces/join/{token}`
- Validate: token not expired, not already used, space not at member limit
- On join: mark invite as used, add user as space member
- **Verify**: generate invite → join with token → invite is invalidated → second use fails → expired token fails

---

## Phase 5 — Core entity CRUD (Categories, Tags, Payment Methods, Merchants)

**Goal**: All supporting entities have working CRUD endpoints.

### Task 5.1 — Categories

**Context**: `ARCHITECTURE.md` §4.5, `PRD.md` §6.5

- Schemas, service, router for categories
- Case-insensitive dedup (normalized_name)
- "Uncategorized" is non-deletable, non-selectable by users
- Deletion reassigns orphaned expense_lines atomically
- **Verify**: CRUD works, duplicate names (different casing) rejected with 409, delete reassigns to Uncategorized, can't delete Uncategorized

### Task 5.2 — Tags

**Context**: `ARCHITECTURE.md` §4.6, `PRD.md` §6.6

- Schema, router for tag listing: `GET /spaces/{id}/tags`
- Tags are auto-created when expenses are saved with new tag names (no explicit create endpoint)
- Normalized: lowercase, trimmed, no `#` prefix stored
- **Verify**: tag list returns existing tags for autocomplete

### Task 5.3 — Payment methods

**Context**: `ARCHITECTURE.md` §4.7, `PRD.md` §4 (payment method concept)

- Schemas, service, router for payment methods
- "Cash" is system (non-deletable), owner_id null
- Members create their own (owner_id set to current user)
- Only owner can update/delete their methods
- Deletion: `ON DELETE SET NULL` on expenses (handled by DB FK)
- **Verify**: CRUD works, can't delete Cash, non-owner update/delete returns 403

### Task 5.4 — Merchant suggestions

**Context**: `ARCHITECTURE.md` §4.11, `PRD.md` §6.4

- Schema, service, router: `GET /merchants/suggest?q=`, `GET /merchants/{name}/category`
- Autocomplete: prefix match on normalized_name, ordered by use_count DESC
- Category suggestion: return last_category_id for the merchant
- Merchant records are upserted on expense creation (handled in Phase 6)
- **Verify**: suggest endpoint returns merchants matching prefix, category endpoint returns last used category

> **Parallelism**: Tasks 5.1–5.4 can all run in parallel.

---

## Phase 6 — Expense CRUD

**Goal**: Full expense lifecycle — create, list (with pagination and filters), view, update, delete.

### Task 6.1 — Create expense

**Context**: `ARCHITECTURE.md` §4.4 (endpoints + update contract), `PRD.md` §6.3, `REQUIREMENTS.md` §2 (data integrity)

- `app/schemas/expense.py` — create request (header + single line), response
- `app/services/expense.py` — create expense atomically: expense header + single expense_line + auto-create tags + upsert merchant (update use_count, last_category_id, last_used_at)
- Validations: purchase_datetime ≤ now (422 if future), amount in range, max 10 tags per line, merchant/notes max lengths
- Status always `confirmed` (pending is 1.1.0+)
- After creation: trigger limit recalculation (Phase 7 will implement the logic; for now, call a stub)
- **Verify**: create expense → expense_line exists, tags auto-created, merchant upserted, future date returns 422

### Task 6.2 — List expenses with cursor pagination and filters

**Context**: `ARCHITECTURE.md` §4.4 (query params, cursor pagination)

- List endpoint with all MVP query params: cursor, limit, period, month, spender, category, merchant, tag, payment_method, search
- Cursor = `(purchase_datetime, id)` encoded as base64
- Sort: `purchase_datetime DESC`, tie-broken by `id DESC`
- Search: case-insensitive contains on merchant, notes, tag names
- Response: `{ "data": [...], "next_cursor": "..." }`
- **Verify**: pagination works (create 25 expenses, fetch pages of 10), filters narrow results correctly, search finds by merchant/notes/tags

### Task 6.3 — Get, update, delete expense

**Context**: `ARCHITECTURE.md` §4.4 (PATCH contract)

- `GET /expenses/{id}` — full expense detail with lines, tags, category, spender, payment method
- `PATCH /expenses/{id}` — partial update using `exclude_unset=True`. When amount changes, update both expense total and sole line amount atomically. Set `updated_at = NOW()` in service layer.
- `DELETE /expenses/{id}` — hard delete (CASCADE handles lines and line_tags)
- After update/delete: trigger limit recalculation stub
- **Verify**: get returns all fields, patch updates only sent fields, delete removes expense and lines

---

## Phase 7 — Limits and TimeWindowResolver

**Goal**: Users can create spending limits, and the system calculates progress against them.

### Task 7.1 — TimeWindowResolver

**Context**: `ARCHITECTURE.md` §6 (analytics computation, TimeWindowResolver interface, test coverage requirements)

- `app/services/time_window.py` — implement `TimeWindowResolver` with all methods from the ARCHITECTURE.md interface
- Takes space timezone as constructor arg
- Methods: `get_current_window`, `get_previous_windows`, `get_day_of_period`, `localize_for_display`
- **Unit tests** covering all required cases: DST spring-forward, DST fall-back, year-boundary week, leap year, quarter boundaries, edge timezones (UTC, UTC+13, UTC-12)
- **Verify**: all unit tests pass, `ruff check` and `black --check` pass

### Task 7.2 — Limit CRUD + progress calculation

**Context**: `ARCHITECTURE.md` §4.8, §6 (limit progress), `PRD.md` §6.7

- Schemas, service, router for limits
- Create: name, timeframe (weekly/monthly only in MVP), threshold, warning_pct (default 60%), category filters
- List: return limits with current progress (spent, threshold, progress ratio, days_remaining, color state based on warning_pct)
- Progress = sum of confirmed expenses matching limit filters in current time window / threshold
- Use TimeWindowResolver for window boundaries
- **Verify**: create limit → add expenses → progress updates correctly, color changes at warning_pct, at 90%, and above 100%

### Task 7.3 — Wire limit recalculation into expense lifecycle

- Replace the stubs from Phase 6 with actual calls to limit recalculation
- On expense create/update/delete: find affected limits (those whose filters match the expense) and recalculate
- Only recalculate matching limits, not all limits in the space
- **Verify**: create expense → matching limit progress changes, delete → progress decreases, edit purchase_date to different window → limit progress in both windows recalculates

---

## Phase 8 — Insights and analytics endpoints

**Goal**: All analytics endpoints return correct data for the Home dashboard and Insights page.

### Task 8.1 — Summary endpoint (hero total + delta)

**Context**: `ARCHITECTURE.md` §4.10, §6 (hero total + delta, 3-month average)

- `app/routers/insights.py` — `GET /insights/summary`
- Returns: total_spent in current window, delta_pct vs 3-month average, period label
- Uses TimeWindowResolver for window calculation
- Handles edge: no prior data → delta is null
- **Verify**: with known test data, total and delta are correct

### Task 8.2 — Spending trend, category breakdown, merchant leaderboard, spender breakdown

**Context**: `ARCHITECTURE.md` §4.10, §6

- `GET /insights/spending-trend` — cumulative daily spend for current period + 3-month average series
- `GET /insights/category-breakdown` — category totals within window
- `GET /insights/merchant-leaderboard` — top merchants by amount within window
- `GET /insights/spender-breakdown` — totals per spender within window
- All endpoints share the same filter query params
- **Verify**: with known test data, aggregations match expected values

### Task 8.3 — Limit progress endpoint

- `GET /insights/limit-progress` — all limits with current progress (reuses limit service logic from 7.2)
- **Verify**: returns same data as limit list but scoped to insights filters

> **Parallelism**: Tasks 8.1 and 8.2 can run in parallel after 8.3 depends on 7.2.

---

## Phase 9 — Backend hardening

**Goal**: Rate limiting, structured logging, correlation IDs, error handling, seed script, and integration tests.

### Task 9.1 — Rate limiting and correlation ID middleware

**Context**: `REQUIREMENTS.md` §1 (rate limiting), §9 (request tracing)

- Rate limiting with `slowapi`: 100 req/min per user (authenticated), 10 req/min per IP (auth endpoints)
- Correlation ID middleware: generate UUID v4 per request, inject into all logs, return as `X-Correlation-ID` header
- **Verify**: exceed rate limit → get 429 with `Retry-After`, correlation ID appears in response headers

### Task 9.2 — Structured logging and error handling

**Context**: `REQUIREMENTS.md` §8 (error handling), §9 (logging)

- Configure `structlog` for JSON logging with correlation_id, user_id, space_id
- Standardize error responses: `{ "error": { "code": "...", "message": "...", "details": {...} } }`
- Global exception handler for unhandled errors (500 with structured response, log stack trace)
- **Verify**: logs are structured JSON, errors return consistent format, unhandled exceptions don't leak stack traces

### Task 9.3 — Seed script

**Context**: `CONVENTIONS.md` §5 (seed data description)

- `app/seed.py` — idempotent seed: 1 demo space, 2 members, 8 categories, 3 payment methods, ~100 expenses over 3 months, 2 limits, diverse merchants
- Runnable with `python -m app.seed`
- **Verify**: run twice → no duplicates, dashboard has meaningful data

### Task 9.4 — Integration tests

**Context**: `REQUIREMENTS.md` §7 (testing strategy)

- Test setup: dedicated test database, transaction rollback per test, Google OAuth mock
- Tests covering: auth flow, expense CRUD, category lifecycle (delete → reassign), invite lifecycle, limit alerts, space membership (non-member → 403)
- **Verify**: `pytest` passes, all key flows covered

> **Parallelism**: Tasks 9.1 and 9.2 can run in parallel. 9.3 and 9.4 after core is stable.

---

## Phase 10 — Frontend foundation

**Goal**: Auth flow works, layout is in place, API client is wired up, routing with guards works.

### Task 10.1 — API client and auth context

**Context**: `ARCHITECTURE.md` §3 (auth flow, frontend routes), `CONVENTIONS.md` §2 (TypeScript standards)

- `lib/api-client.ts` — axios or fetch wrapper, base URL from env, credentials: include (cookies)
- TanStack Query provider with 2-minute stale time, refetch on window focus
- Auth context/hook: `useAuth` — calls `/auth/me`, provides user + space state, loading state
- Google sign-in redirect to `/api/2.0.0/auth/google`
- Auth callback page: handles redirect after Google OAuth
- **Verify**: sign in → redirected to Google → callback sets cookie → `/auth/me` returns user → app knows user is authenticated

### Task 10.2 — App layout and navigation

**Context**: `PRD.md` §8.0 (navigation), `ARCHITECTURE.md` §3 (frontend routes)

- Desktop: left sidebar with nav links (Home, Transactions, Limits, Insights) + prominent "Add Expense" button; Settings at bottom of sidebar
- Mobile MVP: bottom tab bar with centered FAB for "Add Expense" (Home, Transactions, [FAB], Limits, Insights); Settings accessible from avatar profile menu
- Mobile 1.1.0+: bottom tab bar (Home, Recurring [badge], [FAB], Limits, Insights); Transactions accessible from Home "View all →" and within Insights
- Route guards: unauthenticated → redirect to landing, authenticated without space → redirect to onboarding, authenticated with space on `/` → redirect to `/home`
- Responsive layout (Tailwind breakpoints)
- **Verify**: navigation works on both layouts, guards redirect correctly

### Task 10.3 — Landing page

**Context**: `PRD.md` §8.0, §8.1

- Public landing page at `/` for unauthenticated visitors
- "Sign in with Google" button
- Brief product description
- Authenticated users redirect to `/home`
- **Verify**: unauthenticated visitors see landing, authenticated users redirect

---

## Phase 11 — Frontend: Onboarding and Settings

**Goal**: New users can create a space and manage settings. Existing users can manage categories, payment methods, and invites.

### Task 11.1 — Onboarding flow

**Context**: `PRD.md` §6.1 (onboarding), §9.1 (create space flow)

- Onboarding page at `/onboarding`: space name, currency selector, timezone (auto-detect from browser, overridable), default tax %, option to seed default categories
- On submit: `POST /spaces` → redirect to `/home`
- **Verify**: new user → onboarding → space created → redirected to home

### Task 11.2 — Settings page

**Context**: `PRD.md` §8.10 (settings), SCOPE.md (MVP settings list)

- Space settings: name (editable), currency (display only), timezone (editable), default tax % (editable)
- Members list (display only)
- Invite link: generate button, copy link, show active/expired status
- Categories management: list, create, edit, delete with confirmation
- Payment methods management: list per member, create (label only), delete
- **Verify**: all settings CRUD works, category deletion shows confirmation, invite link can be generated and copied

---

## Phase 12 — Frontend: Expense management

**Goal**: Users can add, view, edit, delete expenses. Transaction list works with filters and infinite scroll.

### Task 12.1 — Add expense page

**Context**: `PRD.md` §8.4, §9.2 (add expense flow), §6.3 (expense entry)

- Full page at `/expenses/new`, triggered by FAB / "Add Expense" button
- Fields (in order): amount, merchant (with autocomplete from `/merchants/suggest`), category (auto-suggested from merchant via `/merchants/{name}/category`), purchase datetime (default now, no future dates), spender (default self, dropdown of members), payment method (dropdown), tags (`#`-triggered autocomplete from `/tags`), notes
- On save: `POST /expenses` → navigate back → refetch data (optimistic update)
- **Verify**: add expense with all fields → appears in transaction list, merchant autocomplete works, category auto-suggests, tags create on first use

### Task 12.2 — Transaction list

**Context**: `PRD.md` §8.5 (transaction list)

- Page at `/transactions`
- Grouped by date sections (Today, Yesterday, This Week, Earlier)
- Infinite scroll (cursor pagination, load more on scroll)
- Filter bar: time window, spender, category, merchant, tag, payment method
- Search bar: merchant/notes/tags (case-insensitive)
- Each item shows: merchant, amount, category, date, spender
- Click → navigate to expense detail
- **Verify**: groups render correctly, infinite scroll loads more, filters narrow results, search works

### Task 12.3 — Expense detail, edit, delete

**Context**: `PRD.md` §8.6 (expense detail), §9.7 (edit flow), §9.8 (delete flow)

- Page at `/transactions/:id`
- Display all fields: merchant, purchase datetime, created datetime, spender, payment method, amount, category, tags, notes
- Edit mode: all fields editable (same form as add, pre-filled)
- Delete button with "Are you sure?" confirmation dialog → hard delete → redirect to transaction list
- **Verify**: view shows all data, edit saves changes, delete removes and redirects

---

## Phase 13 — Frontend: Home dashboard

**Goal**: Home page shows hero total, charts, limit alerts, and latest transactions.

### Task 13.1 — Home dashboard

**Context**: `PRD.md` §8.3, §6.9 (home dashboard), `ARCHITECTURE.md` §6 (analytics definitions)

- Page at `/home`
- Hero card: total spent for current window + delta vs 3-month average ("+12%" / "-8% vs avg")
- Week / Month toggle (switches all content)
- Limit alert cards (2–3 max): limits at warning (≥ warning_pct), critical (≥90%), or exceeded (>100%)
- Charts (use Recharts):
  - Spending trend line: cumulative current period vs 3-month average
  - Category distribution: pie/donut chart
  - Merchant leaderboard: horizontal bar chart (top by amount)
- Latest transactions: count + link to `/transactions`
- All data fetched via TanStack Query hooks (`useInsightsSummary`, `useSpendingTrend`, etc.)
- **Verify**: with seed data, all cards and charts render with real data, toggle switches between week/month views, limit alerts appear when thresholds are crossed

---

## Phase 14 — Frontend: Insights and Limits

**Goal**: Insights page with filters and charts. Limits management page.

### Task 14.1 — Insights page

**Context**: `PRD.md` §8.7, §6.10 (insights)

- Page at `/insights`
- Desktop: split view (charts left, transaction list right)
- Mobile: charts stacked above transaction list
- Global filter bar: time presets (this week/last week/this month/last month/month picker/YTD), spender, category, merchant, tag, payment method — all filters apply to both charts and list
- Charts: spending trend line, category distribution pie, merchant leaderboard (amount), spender breakdown
- Transaction list: reuse component from Phase 12, driven by the same filters
- **Verify**: filters update both charts and list, all chart types render, responsive layout works

### Task 14.2 — Limits management page

**Context**: `PRD.md` §8.8 (limits)

- Page at `/limits`
- List of limits with progress bars (spent / threshold), warning/alert visual indicators, days remaining
- Create form: name, timeframe (weekly/monthly), threshold, warning %, category filter
- Edit (inline or modal)
- Delete with confirmation
- **Verify**: limits display with correct progress, create/edit/delete works, visual indicators match warning/alert thresholds

---

## Phase 15 — Integration, CI/CD, and polish

**Goal**: CI pipeline runs tests and lint, deployment works, cross-cutting concerns are handled.

### Task 15.1 — CI pipeline

**Context**: `CONVENTIONS.md` §4 (git workflow), §1 (project structure for CI)

- `.github/workflows/ci.yml`:
  - Backend: install deps → `ruff check` → `black --check` → `pytest`
  - Frontend: install deps → `eslint` → `prettier --check` → `npm run build`
- Trigger on PR to `main` and push to `main`
- **Verify**: push a PR → CI runs both checks, fails on lint error or test failure

### Task 15.2 — Frontend polish

- Error boundaries (React error boundary at route level)
- Loading skeletons / spinners for data-fetching states
- Toast notifications for success/error on mutations (expense created, deleted, etc.)
- Empty states (no expenses yet, no limits, etc.)
- Currency-aware formatting using `Intl.NumberFormat` with space currency_code
- Auto-refetch: TanStack Query `refetchInterval: 120000` when window is focused
- **Verify**: error boundary catches rendering errors, loading states display, toasts fire on actions, currency formats correctly

### Task 15.3 — CD pipeline and deployment

**Context**: `CONVENTIONS.md` §8 (deployment), `ARCHITECTURE.md` §8 (deployment topology)

- Azure resource setup: Static Web Apps (frontend), App Service (backend), PostgreSQL Flexible Server
- `.github/workflows/deploy.yml`: build → deploy on push to `main`
- `staticwebapp.config.json` with SPA fallback and `linkedBackend`
- Backend startup command for App Service: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app`
- Run `alembic upgrade head` as part of deploy
- **Verify**: push to `main` → deployed → health check passes → full flow works in production

---

## Phase summary

| Phase | Milestone | Backend | Frontend |
|-------|-----------|---------|----------|
| 1 | Projects run locally | ✓ | ✓ |
| 2 | DB schema & ORM | ✓ | |
| 3 | Auth works end-to-end | ✓ | |
| 4 | Spaces & invites | ✓ | |
| 5 | Supporting entities CRUD | ✓ | |
| 6 | Expense lifecycle | ✓ | |
| 7 | Limits & time windows | ✓ | |
| 8 | Analytics endpoints | ✓ | |
| 9 | Hardening & tests | ✓ | |
| 10 | Frontend foundation | | ✓ |
| 11 | Onboarding & settings | | ✓ |
| 12 | Expense management UI | | ✓ |
| 13 | Home dashboard | | ✓ |
| 14 | Insights & limits UI | | ✓ |
| 15 | CI/CD & polish | ✓ | ✓ |

## Notes for agents

- **Always read** `SCOPE.md` before implementing a feature — don't build 1.1.0+ or 2.0.0 features.
- **Schema includes future columns** (beneficiary, recurring) as nullable — don't remove them, but don't implement logic for them.
- **Test with the seed script** after Phase 9 — it provides realistic data for all dashboard and insights development.
- **Commit after each task** with conventional format: `feat: ...`, `chore: ...`, etc.
- **If a design doc is wrong or incomplete**, update it as part of the task and note the change in the commit.
