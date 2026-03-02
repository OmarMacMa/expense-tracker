# Architecture

This document describes the **technical architecture, tech stack, API design, database schema, and deployment topology** for the Expense Tracker & Budget Insights application.

---

## 1) Tech stack overview

| Layer | Technology | Hosting |
|---|---|---|
| Frontend | Vite + React + TypeScript | Azure Static Web Apps (free tier) |
| Routing | React Router v7 | — |
| UI components | shadcn/ui + Tailwind CSS | — |
| Charts | Recharts | — |
| Data fetching | TanStack Query (React Query) | — |
| Backend API | FastAPI (Python) + Pydantic | Azure App Service (Linux, B1) |
| Database | PostgreSQL | Azure Database for PostgreSQL Flexible Server (B1ms) |
| ORM | SQLAlchemy 2.0 (async, with asyncpg driver) | — |
| Migrations | Alembic | — |
| Scheduled jobs | Internal FastAPI endpoints + external cron trigger | Azure App Service (same instance) |
| Auth | Google OAuth 2.0 → JWT in httpOnly cookies | — |
| Rate limiting | slowapi (backed by limits library) | — |
| i18n | react-i18next (V1+) | — |

### Why these choices

- **Vite + React SPA on Azure Static Web Apps**: this app is entirely behind auth — no public content, no SEO, no SSR/SSG need. A plain SPA is the simplest deployment model: static files served globally with zero server-side execution. Azure Static Web Apps handles SPAs flawlessly (custom domains, free SSL, GitHub CI/CD, `linkedBackend` API proxy). Vite provides fast builds and instant HMR.
- **React Router v7**: file-based convention routing, loaders, error boundaries. Lightweight and purpose-built for SPAs. No server component complexity.
- **shadcn/ui + Tailwind**: accessible, customizable components owned by the project (not a dependency). Rapid UI development.
- **Recharts**: React-native composable JSX charting. Handles all chart types (line, bar, pie, composed).
- **TanStack Query**: caching, background refetching (2-minute stale refresh), optimistic updates, parallel queries for Insights.
- **FastAPI**: async-native, auto OpenAPI docs, Pydantic validation, Python ecosystem for analytics.
- **SQLAlchemy 2.0 (async)**: handles complex analytics queries (aggregations, window functions), Alembic for migrations.
- **PostgreSQL**: relational data model, aggregation queries, JSONB for flexible metadata, row-level security potential.
- **Internal scheduled jobs**: recurring generation and monthly wrap run as internal FastAPI endpoints triggered by an external cron (GitHub Actions schedule or Azure App Service WebJob). Avoids the deployment complexity and cold-start latency of a separate Azure Functions resource.

---

## 2) Architecture diagram

```
┌─────────────────────────────┐
│   Azure Static Web Apps     │
│   (Free tier)               │
│   Vite + React + TS (SPA)   │
│   React Router v7           │
│   shadcn/ui + Tailwind      │
│   Recharts                  │
│   TanStack Query            │
└─────────────┬───────────────┘
              │ HTTPS (proxied via linkedBackend — no CORS)
              ▼
┌─────────────────────────────┐
│   Azure App Service (API)   │
│   FastAPI + Pydantic        │
│   SQLAlchemy 2.0 (async)    │
│   JWT auth middleware       │
│   Internal scheduled jobs:  │
│   - POST /internal/cron/    │
│     recurring-generate      │
│   - POST /internal/cron/    │
│     wrap-generate           │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│   Azure PostgreSQL          │
│   Flexible Server           │
│   (all data, UTC datetimes) │
│   Automated backups (7-day) │
└─────────────────────────────┘

┌─────────────────────────────┐
│   GitHub Actions            │
│   (cron triggers)           │
│   - Daily: call recurring   │
│     generate endpoint       │
│   - Monthly: call wrap      │
│     generate endpoint       │
└─────────────────────────────┘
```

### Component responsibilities

**Azure Static Web Apps (Frontend)**
- Serves the Vite-built SPA (static HTML/JS/CSS bundles)
- All routing handled client-side by React Router v7
- Proxies API requests to backend via `linkedBackend` configuration
- No server-side execution — purely static file hosting with SPA fallback
- TanStack Query manages data fetching, caching, and auto-refetch

**Azure App Service (Backend API)**
- All business logic and data validation
- Auth middleware: validates JWT cookie on every request, enforces space membership
- Exposes RESTful endpoints with OpenAPI documentation
- Handles expense CRUD, limit calculations, category management, invite lifecycle
- Hosts internal scheduled job endpoints (protected by internal auth token)

**Azure PostgreSQL**
- Single source of truth for all data
- All datetimes stored as UTC
- Indexes optimized for common query patterns (analytics, filtering, autocomplete)
- Automated backups with 7-day retention (Azure default, no extra cost)

**GitHub Actions (Cron Triggers)**
- **Recurring generator** (daily schedule): calls `POST /api/v1/internal/cron/recurring-generate` with an internal auth token. The endpoint checks all active templates where `next_due_date <= today`, generates pending expenses (idempotent), advances `next_due_date`, backfills missed dates.
- **Monthly wrap generator** (1st of month schedule): calls `POST /api/v1/internal/cron/wrap-generate` with an internal auth token. The endpoint pre-computes wrap summaries for eligible spaces and stores as JSONB.

---

## 3) Authentication flow

```
User → "Sign in with Google" → Frontend redirects to backend
→ GET /api/v1/auth/google → redirects to Google OAuth consent
→ Google callback → GET /api/v1/auth/google/callback
→ Backend validates OAuth token (scopes: `openid`, `email`, `profile`), creates/updates user record
→ Backend issues JWT, sets httpOnly cookie (Secure, SameSite=Lax)
→ Redirects to frontend (onboarding if new user, Home if existing)
```

- JWT contains: user ID, issued-at, expiration
- Cookie: httpOnly, Secure, SameSite=Lax
- Every API request: middleware extracts JWT from cookie, validates, injects user into request context
- Space membership: middleware checks `space_members` table for every `/spaces/{space_id}/...` endpoint

### Frontend routes (React Router v7)

| Path | Component | Description |
|---|---|---|
| `/` | Landing | Public landing page (unauthenticated visitors) |
| `/auth/callback` | AuthCallback | Google OAuth callback handler |
| `/onboarding` | Onboarding | Space creation for new users |
| `/home` | Home | Dashboard (hero, charts, alerts) |
| `/transactions` | TransactionList | Filtered, searchable, infinite scroll |
| `/transactions/:id` | ExpenseDetail | View/edit/delete expense |
| `/insights` | Insights | Charts + transaction split view |
| `/limits` | Limits | Limit management + progress |
| `/recurring` | Recurring | Templates + pending items (V0.5+) |
| `/settings` | Settings | Space + member + category management |
| `/join/:token` | JoinSpace | Invite acceptance flow |

- **Auth guard**: all routes except `/`, `/auth/callback`, and `/join/:token` require authentication. Unauthenticated users are redirected to `/`.
- **Space guard**: authenticated users with no space are redirected to `/onboarding`.
- **Default redirect**: authenticated users with a space landing on `/` are redirected to `/home`.

---

## 4) API design

**RESTful API with OpenAPI auto-documentation (FastAPI built-in).**

All endpoints scoped under `/api/v1/` with JWT cookie authentication. Space-scoped endpoints validate membership.

### 4.1 Health check
```
GET  /api/v1/health                  → returns { "status": "ok", "db": "connected" }
```
No authentication required. Returns DB connectivity status. Used by Azure App Service health probes and monitoring.

### 4.2 Auth endpoints
```
GET  /api/v1/auth/google            → initiate Google OAuth
GET  /api/v1/auth/google/callback   → handle callback, set JWT cookie
POST /api/v1/auth/logout            → clear JWT cookie
GET  /api/v1/auth/me                → get current user info + their space(s)
```

### 4.3 Space endpoints
```
POST /api/v1/spaces                          → create space
GET  /api/v1/spaces/{space_id}               → get space details
PUT  /api/v1/spaces/{space_id}               → update space settings
POST /api/v1/spaces/{space_id}/invite        → generate invite link
POST /api/v1/spaces/join/{invite_token}      → join space via invite
GET  /api/v1/spaces/{space_id}/members       → list members
```

### 4.4 Expense endpoints
```
POST   /api/v1/spaces/{space_id}/expenses                → create expense (with split lines)
GET    /api/v1/spaces/{space_id}/expenses                 → list expenses (filters, search, cursor pagination)
GET    /api/v1/spaces/{space_id}/expenses/{expense_id}    → get expense detail
PATCH  /api/v1/spaces/{space_id}/expenses/{expense_id}    → partial update expense (send only changed fields)
DELETE /api/v1/spaces/{space_id}/expenses/{expense_id}    → hard delete expense
```

**List expenses query parameters:**
```
?cursor={cursor_id}         → cursor-based pagination
&limit=20                   → page size
&period=this_month          → time filter
&month=2026-01              → specific month
&spender={user_id}          → filter by spender
&beneficiary={user_id|shared} → filter by beneficiary (V1+)
&category={cat_id}          → filter by category
&merchant={name}            → filter by merchant (case-insensitive contains)
&tag={tag_name}             → filter by tag
&payment_method={method_id} → filter by payment method
&search={text}              → search merchant/notes/tags
```

**Cursor pagination:**
- Cursor = `(purchase_datetime, id)` encoded as opaque base64 string.
- Sort: `purchase_datetime DESC`, tie-broken by `id DESC`.
- First request: omit `cursor`. Response: `{ "data": [...], "next_cursor": "..." }`.
- `next_cursor` is `null` when no more results exist.
- Stable under concurrent inserts (unlike offset-based pagination).

**Expense update contract (PATCH):**
- **Single-line (MVP):** client sends changed header fields and/or `amount`. When `amount` is sent, the backend updates both `expenses.total_amount` and the sole `expense_lines.amount` atomically.
- **Split (V1+):** client sends changed header fields and/or a full `lines` array. When `lines` is present, all existing lines are replaced (delete + re-insert). `total_amount` is recalculated from the new lines. Sum validation applies (422 if mismatch).
- Omitted fields are unchanged (`model.model_dump(exclude_unset=True)`).
- If `purchase_datetime` or any amount changes, affected limits recalculate.

### 4.5 Category endpoints
```
GET    /api/v1/spaces/{space_id}/categories               → list categories
POST   /api/v1/spaces/{space_id}/categories               → create category
PUT    /api/v1/spaces/{space_id}/categories/{cat_id}      → update category
DELETE /api/v1/spaces/{space_id}/categories/{cat_id}      → delete (orphans → Uncategorized)
```

### 4.6 Tag endpoints
```
GET /api/v1/spaces/{space_id}/tags    → list tags (for autocomplete)
```
Tags are created implicitly when expenses are saved with new tag names.

### 4.7 Payment method endpoints
```
GET    /api/v1/spaces/{space_id}/payment-methods                 → list all methods in space
POST   /api/v1/spaces/{space_id}/payment-methods                 → create method (for current user)
PATCH  /api/v1/spaces/{space_id}/payment-methods/{method_id}     → partial update (owner only)
DELETE /api/v1/spaces/{space_id}/payment-methods/{method_id}     → delete (owner only)
```

### 4.8 Limit endpoints
```
GET    /api/v1/spaces/{space_id}/limits                → list limits with current progress
POST   /api/v1/spaces/{space_id}/limits                → create limit
PATCH  /api/v1/spaces/{space_id}/limits/{limit_id}     → partial update limit
DELETE /api/v1/spaces/{space_id}/limits/{limit_id}     → delete limit
```

### 4.9 Recurring endpoints (V0.5+)
```
GET    /api/v1/spaces/{space_id}/recurring                                 → list templates
POST   /api/v1/spaces/{space_id}/recurring                                 → create template
PATCH  /api/v1/spaces/{space_id}/recurring/{template_id}                   → partial update template
DELETE /api/v1/spaces/{space_id}/recurring/{template_id}                   → delete template
GET    /api/v1/spaces/{space_id}/recurring/pending                         → list pending expenses
POST   /api/v1/spaces/{space_id}/recurring/pending/{pending_id}/confirm    → confirm pending
POST   /api/v1/spaces/{space_id}/recurring/pending/{pending_id}/deny       → deny pending
PATCH  /api/v1/spaces/{space_id}/recurring/pending/{pending_id}            → partial update pending
```

### 4.10 Insights / analytics endpoints
```
GET /api/v1/spaces/{space_id}/insights/summary              → hero total + delta vs average
GET /api/v1/spaces/{space_id}/insights/spending-trend        → cumulative trend + 3-month avg
GET /api/v1/spaces/{space_id}/insights/category-breakdown    → category totals (bar + pie data)
GET /api/v1/spaces/{space_id}/insights/merchant-leaderboard  → top merchants by amount (MVP); amount/count toggle (V0.5+)
GET /api/v1/spaces/{space_id}/insights/spender-breakdown     → totals per spender
GET /api/v1/spaces/{space_id}/insights/limit-progress        → all limits with current progress
```

**Shared query parameters for all insights endpoints:**
```
?period=this_month|last_month|this_week|last_week|ytd|quarter
&month=2026-01
&quarter=2026-Q1              → V1+ (quarter picker)
&spender={user_id}
&beneficiary={user_id|shared} → V1+ (beneficiary filter)
&category={cat_id}
&merchant={merchant_name}
&tag={tag_name}
&payment_method={method_id}
```

### 4.11 Merchant suggestion endpoints
```
GET /api/v1/spaces/{space_id}/merchants/suggest?q={query}   → autocomplete merchant names
GET /api/v1/spaces/{space_id}/merchants/{name}/category      → latest category for merchant
```

### 4.12 Monthly wrap endpoint (V1+)
```
GET /api/v1/spaces/{space_id}/wrap/{year}/{month}   → pre-computed wrap data
```

### 4.13 Internal cron endpoints (V0.5+)

Protected by internal auth token (not JWT cookies). Only callable by the cron trigger (GitHub Actions).

```
POST /api/v1/internal/cron/recurring-generate   → generate pending expenses for all spaces
POST /api/v1/internal/cron/wrap-generate         → generate monthly wraps for all eligible spaces
```

Authentication: `Authorization: Bearer {INTERNAL_CRON_TOKEN}` header. The token is a shared secret between GitHub Actions and the backend, stored as environment variables in both.

---

## 5) Database schema

### 5.1 Tables

```sql
-- Users (from Google OAuth)
users
  id              UUID PRIMARY KEY
  google_id       TEXT UNIQUE NOT NULL
  email           TEXT NOT NULL
  display_name    TEXT NOT NULL
  avatar_url      TEXT
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- Shared financial workspaces
spaces
  id              UUID PRIMARY KEY
  name            TEXT NOT NULL
  currency_code   TEXT NOT NULL          -- e.g., "USD", "EUR", "MXN"
  timezone        TEXT NOT NULL          -- e.g., "America/New_York"
  default_tax_pct DECIMAL(5,2)          -- nullable, e.g., 8.25
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- User membership in spaces
space_members
  id              UUID PRIMARY KEY
  space_id        UUID NOT NULL REFERENCES spaces(id)
  user_id         UUID NOT NULL REFERENCES users(id)
  joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
  UNIQUE(space_id, user_id)

-- Single-use invite links
invite_links
  id              UUID PRIMARY KEY
  space_id        UUID NOT NULL REFERENCES spaces(id)
  token           TEXT UNIQUE NOT NULL   -- cryptographically random
  created_by      UUID NOT NULL REFERENCES users(id)
  expires_at      TIMESTAMPTZ NOT NULL
  used_at         TIMESTAMPTZ           -- null if unused
  used_by         UUID REFERENCES users(id)

-- Shared categories per space
categories
  id              UUID PRIMARY KEY
  space_id        UUID NOT NULL REFERENCES spaces(id)
  name            TEXT NOT NULL
  normalized_name TEXT NOT NULL          -- lowercase, trimmed
  is_system       BOOLEAN NOT NULL DEFAULT FALSE  -- true for "Uncategorized"
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
  UNIQUE(space_id, normalized_name)

-- Payment methods (Cash is system, others are member-owned)
payment_methods
  id              UUID PRIMARY KEY
  space_id        UUID NOT NULL REFERENCES spaces(id)
  owner_id        UUID REFERENCES users(id)  -- null for Cash (shared)
  label           TEXT NOT NULL              -- max 50 characters
  color           TEXT                       -- hex string, e.g., "#4A90D9" (V1+; null in MVP)
  is_system       BOOLEAN NOT NULL DEFAULT FALSE  -- true for Cash
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- Merchant lookup and category suggestion cache (best-effort: use_count and last_category_id
-- are updated on expense creation only — never decremented on expense edit/delete.
-- This is autocomplete fuel, not accounting data.)
merchants
  id                UUID PRIMARY KEY
  space_id          UUID NOT NULL REFERENCES spaces(id)
  name              TEXT NOT NULL              -- original casing, max 100 characters
  normalized_name   TEXT NOT NULL              -- lowercase, trimmed (for search/grouping)
  last_category_id  UUID REFERENCES categories(id) ON DELETE SET NULL
  use_count         INTEGER NOT NULL DEFAULT 1
  last_used_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
  UNIQUE(space_id, normalized_name)

-- Expense headers (purchase-level)
expenses
  id                    UUID PRIMARY KEY
  space_id              UUID NOT NULL REFERENCES spaces(id)
  merchant              TEXT NOT NULL           -- max 100 characters
  merchant_normalized   TEXT NOT NULL           -- lowercase, trimmed (for search/grouping)
  purchase_datetime     TIMESTAMPTZ NOT NULL
  total_amount          DECIMAL(12,2) NOT NULL CHECK (total_amount >= 0.01 AND total_amount <= 999999.99)  -- denormalized sum of split lines; enforced on save
  spender_id            UUID NOT NULL REFERENCES users(id)
  payment_method_id     UUID REFERENCES payment_methods(id) ON DELETE SET NULL
  notes                 TEXT                    -- max 500 characters
  status                TEXT NOT NULL CHECK (status IN ('confirmed', 'pending'))  -- 'pending' used by recurring (V0.5+)
  -- V0.5+ columns (nullable, unused in MVP)
  recurring_template_id UUID REFERENCES recurring_templates(id) ON DELETE SET NULL
  scheduled_date        DATE                   -- for pending: the scheduled date
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- Expense split lines (amount + category per line; beneficiary added in V1)
expense_lines
  id                UUID PRIMARY KEY
  expense_id        UUID NOT NULL REFERENCES expenses(id) ON DELETE CASCADE
  amount            DECIMAL(12,2) NOT NULL CHECK (amount >= 0.01 AND amount <= 999999.99)
  category_id       UUID NOT NULL REFERENCES categories(id) ON DELETE RESTRICT  -- service layer reassigns to "Uncategorized" before delete
  -- V1+ columns (nullable, unused in MVP)
  beneficiary_type  TEXT CHECK (beneficiary_type IN ('member', 'shared'))  -- null in MVP
  beneficiary_id    UUID REFERENCES users(id)  -- null when type='shared' or in MVP
  line_order        INTEGER NOT NULL

-- Tags (normalized, space-scoped)
tags
  id              UUID PRIMARY KEY
  space_id        UUID NOT NULL REFERENCES spaces(id)
  name            TEXT NOT NULL           -- normalized: lowercase, trimmed, no # prefix in storage; max 50 chars
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
  UNIQUE(space_id, name)

-- Many-to-many: expense lines ↔ tags (max 10 tags per expense line, enforced at app level)
expense_line_tags
  expense_line_id UUID NOT NULL REFERENCES expense_lines(id) ON DELETE CASCADE
  tag_id          UUID NOT NULL REFERENCES tags(id)
  PRIMARY KEY (expense_line_id, tag_id)

-- Spending limits with flexible filters
limits
  id               UUID PRIMARY KEY
  space_id         UUID NOT NULL REFERENCES spaces(id)
  name             TEXT NOT NULL           -- max 100 characters
  timeframe        TEXT NOT NULL CHECK (timeframe IN ('weekly', 'monthly', 'quarterly', 'yearly'))
  threshold_amount DECIMAL(12,2) NOT NULL CHECK (threshold_amount >= 0.01 AND threshold_amount <= 999999.99)
  warning_pct      DECIMAL(5,4) NOT NULL DEFAULT 0.8000  -- e.g., 0.8000 = 80%
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- Filter criteria for limits (one row per filter condition)
-- Tech debt note: filter_value is TEXT for flexibility (stores UUIDs, merchant names, tag names).
-- No FK enforcement on this column. Validation is handled in the service layer.
-- Future migration path: typed junction tables or JSONB filter object when limits grow more complex.
limit_filters
  id            UUID PRIMARY KEY
  limit_id      UUID NOT NULL REFERENCES limits(id) ON DELETE CASCADE
  filter_type   TEXT NOT NULL CHECK (filter_type IN ('category', 'merchant', 'tag', 'spender', 'beneficiary', 'payment_method'))
  filter_value  TEXT NOT NULL   -- category UUID, merchant name, tag name, user UUID, "shared", method UUID

-- Recurring expense templates (V0.5+)
recurring_templates
  id                         UUID PRIMARY KEY
  space_id                   UUID NOT NULL REFERENCES spaces(id)
  name                       TEXT NOT NULL           -- max 100 characters
  schedule                   TEXT NOT NULL CHECK (schedule IN ('weekly', 'monthly', 'quarterly', 'yearly'))
  default_amount             DECIMAL(12,2) NOT NULL CHECK (default_amount >= 0.01 AND default_amount <= 999999.99)
  default_merchant           TEXT NOT NULL           -- max 100 characters
  default_category_id        UUID NOT NULL REFERENCES categories(id)
  default_spender_id         UUID NOT NULL REFERENCES users(id)
  default_beneficiary_type   TEXT CHECK (default_beneficiary_type IN ('member', 'shared'))  -- V1+; null in V0.5
  default_beneficiary_id     UUID REFERENCES users(id)  -- V1+; null when type='shared' or in V0.5
  default_payment_method_id  UUID REFERENCES payment_methods(id) ON DELETE SET NULL
  default_tags               JSONB DEFAULT '[]'          -- array of tag name strings
  next_due_date              DATE NOT NULL
  is_active                  BOOLEAN NOT NULL DEFAULT TRUE
  created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- Pre-computed monthly wrap summaries
monthly_wraps
  id          UUID PRIMARY KEY
  space_id    UUID NOT NULL REFERENCES spaces(id)
  year        INTEGER NOT NULL
  month       INTEGER NOT NULL
  data        JSONB NOT NULL            -- pre-computed wrap content
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  UNIQUE(space_id, year, month)
```

### 5.2 Key indexes

```sql
-- Expense queries (analytics, filtering, listing)
CREATE INDEX idx_expenses_space_purchase ON expenses(space_id, purchase_datetime DESC);
CREATE INDEX idx_expenses_space_status ON expenses(space_id, status);
CREATE INDEX idx_expenses_space_merchant ON expenses(space_id, merchant_normalized);
CREATE INDEX idx_expenses_space_spender ON expenses(space_id, spender_id, purchase_datetime DESC);

-- Expense line queries (category analytics, beneficiary filtering)
CREATE INDEX idx_expense_lines_expense ON expense_lines(expense_id);
CREATE INDEX idx_expense_lines_category ON expense_lines(category_id);

-- Merchant autocomplete and category suggestion
CREATE INDEX idx_merchants_space_name ON merchants(space_id, normalized_name);
CREATE INDEX idx_merchants_space_usage ON merchants(space_id, use_count DESC);

-- Tag autocomplete
CREATE INDEX idx_tags_space_name ON tags(space_id, name);

-- Limit queries
CREATE INDEX idx_limits_space ON limits(space_id);
CREATE INDEX idx_limit_filters_limit ON limit_filters(limit_id);

-- Recurring template scheduling (V0.5+)
CREATE INDEX idx_recurring_space_active ON recurring_templates(space_id, is_active, next_due_date);

-- Payment method filter (Insights)
CREATE INDEX idx_expenses_space_payment ON expenses(space_id, payment_method_id);

-- Invite link lookup
CREATE INDEX idx_invite_links_token ON invite_links(token);
```

---

## 6) Analytics computation

### TimeWindowResolver utility

All time-based analytics depend on correctly computing window boundaries in the space's timezone against UTC-stored data. This is a high-risk area (DST transitions, year-boundary weeks, leap years). A single shared `TimeWindowResolver` utility must handle **all** time window logic. No ad-hoc timezone math anywhere in the codebase.

**Interface (Python backend — the authoritative source):**

| Method | Input | Output | Description |
|---|---|---|---|
| `get_current_window(timeframe, ref_date?)` | `timeframe`: weekly/monthly/quarterly/yearly; `ref_date`: defaults to today in space TZ | `(start_utc, end_utc)` | UTC-converted boundaries of the current period |
| `get_previous_windows(timeframe, count=3, ref_date?)` | Same + `count` | `list[(start_utc, end_utc)]` | N prior comparable windows for average computation. Returns fewer if insufficient history. |
| `get_day_of_period(dt, timeframe)` | UTC datetime + timeframe | `int` (0-based) | Day index within the period, for cumulative trend alignment |
| `localize_for_display(dt_utc)` | UTC datetime | Localized datetime | Convert UTC to space timezone for UI display |

**Required test coverage (minimum):**
- DST spring-forward: a week window spanning the spring-forward transition (e.g., 2nd Sunday of March in US)
- DST fall-back: a week window spanning the fall-back transition
- Year-boundary week: a week that starts in December and ends in January
- Leap year: February window in a leap year vs non-leap year
- Quarter boundaries: Q1→Q2, Q4→Q1 transitions
- Edge: `ref_date` is the first or last day of a period
- Edge: space timezone is UTC (no DST), UTC+13 (Tonga), UTC-12 (Baker Island)

**Frontend mirror:** A TypeScript equivalent using `Intl.DateTimeFormat` and `date-fns-tz` must produce identical boundaries for any given space timezone. Parity tests should verify backend and frontend agree on window boundaries for a set of reference dates and timezones.

### Time window boundaries
All computed using the **space timezone**. Datetimes stored as UTC.

| Timeframe | Start | End |
|---|---|---|
| Weekly | Monday 00:00:00 (space TZ) | Sunday 23:59:59 (space TZ) |
| Monthly | 1st 00:00:00 | Last day 23:59:59 |
| Quarterly | Jan 1 / Apr 1 / Jul 1 / Oct 1 | Mar 31 / Jun 30 / Sep 30 / Dec 31 |
| Yearly | Jan 1 00:00:00 | Dec 31 23:59:59 |

### 3-month average computation
- For a given period (e.g., "this month to date"):
  - Get cumulative daily spend for the current period
  - Get cumulative daily spend for each of the prior 3 comparable periods
  - Average the 3 prior periods by day-of-period
  - If fewer than 3 prior periods exist, use as many as available
- Result: two series (current cumulative, average cumulative) for trend line chart

### Hero total + delta
- `total` = sum of all confirmed expenses in selected window
- `average` = mean of same metric across prior 3 comparable windows
- `delta` = `((total - average) / average) * 100` → displayed as "+X%" or "-X%"
- Edge case: if no prior data, delta is not shown

### Limit progress
- `spent` = sum of confirmed expenses matching all limit filters in current window
- `progress` = `spent / threshold`
- `days_remaining` = end of current window - today
- Warning at `progress >= warning_pct`, alert at `progress >= 1.0`

### Merchant leaderboard
- Group by `merchant_normalized` within the selected window
- By amount: `SUM(expense_lines.amount)` per merchant
- By count: `COUNT(DISTINCT expenses.id)` per merchant
- Optional change: compare current window vs previous comparable window

---

## 7) Scheduled jobs (Internal endpoints + GitHub Actions cron)

Scheduled jobs run as internal FastAPI endpoints triggered by GitHub Actions on a cron schedule. Each endpoint is protected by an `INTERNAL_CRON_TOKEN` — a shared secret stored as an environment variable in both GitHub Actions and the backend.

### 7.1 Recurring expense generator (V0.5+)
- **Trigger**: GitHub Actions cron, daily (e.g., 06:00 UTC)
- **Endpoint**: `POST /api/v1/internal/cron/recurring-generate`
- **Logic**:
  1. Query all active recurring templates across all spaces where `next_due_date <= today`
  2. For each template, for each missed date (from `next_due_date` through today):
     a. Check if a pending expense already exists for this template + date (idempotency)
     b. If not, create a pending expense with template defaults
     c. Advance `next_due_date` to the next scheduled date
  3. Commit all changes in a transaction

### 7.2 Monthly wrap generator (V1+)
- **Trigger**: GitHub Actions cron, 1st of each month (e.g., 08:00 UTC)
- **Endpoint**: `POST /api/v1/internal/cron/wrap-generate`
- **Logic**:
  1. Query **active spaces only**: spaces with ≥10 confirmed expenses in the previous month. Skip all others.
  2. For each active space, compute the wrap for the previous month:
     - Category improvements (spending below 3-month average)
     - Category spikes (spending above 3-month average)
     - Limits frequently breached (>50% of weeks/months in the period)
     - Rule-based recommendations (propose limit adjustments)
  3. Store as JSONB in `monthly_wraps` table
  4. Upsert to handle re-runs safely

---

## 8) Deployment topology

### Estimated monthly cost (Azure — all-in-one cloud)
| Service | Tier | Est. cost |
|---|---|---|
| Static Web Apps (Frontend) | Free | $0 |
| App Service (API) | Linux B1 | ~$13/mo |
| PostgreSQL Flexible | Burstable B1ms | ~$15-25/mo |
| GitHub Actions (Cron) | Free tier | $0 |
| **Total** | | **~$28-38/mo** |

### Environment strategy
- **Production**: Azure Static Web Apps (frontend) + Azure App Service (backend + scheduled jobs) + Azure PostgreSQL
- **Development**: local Vite dev server + local FastAPI + local PostgreSQL (Docker)
- **Staging** (optional, within Azure budget): separate App Service slot or second resource group

### Frontend → Backend proxy
- Azure Static Web Apps `linkedBackend` configuration proxies `/api/*` requests to the App Service
- **No CORS configuration needed** — requests appear same-origin to the browser
- Development: Vite dev server `proxy` in `vite.config.ts` forwards `/api/*` to `localhost:8000`

### Database backups
- Azure PostgreSQL Flexible Server includes automated backups at no extra cost
- Default retention: 7 days (configurable up to 35 days)
- Point-in-time restore available within the retention window
- No action needed for MVP; increased retention can be configured for V2+

### Connection pooling
- SQLAlchemy async connection pool configuration:
  - `pool_size`: 5 (MVP), scale to 10-20 for V1+
  - `max_overflow`: 5 (allows burst connections beyond pool_size)
  - `pool_timeout`: 30 seconds
  - `pool_recycle`: 1800 seconds (30 minutes, prevents stale connections)
- Azure PostgreSQL B1ms supports up to 50 concurrent connections; pool limits must stay well below this
