# Requirements

This document defines the **non-functional requirements, quality bars, and testing strategy** for the Expense Tracker & Budget Insights application. These are the constraints the system must satisfy regardless of which feature is being built.

---

## 1) Security & privacy

### Authentication
- Google SSO only (OAuth 2.0) in MVP.
- JWT stored in httpOnly cookies with `Secure` and `SameSite=Lax` flags.
- JWT must include user ID, issued-at timestamp, and expiration.
- **JWT expiration**: 7 days. On each authenticated request, if the token has less than 1 day remaining, the backend re-issues a fresh JWT in the response cookie (sliding window). This avoids forcing re-login for active users while keeping tokens short-lived.
- **Expired token handling**: if the JWT is expired, the backend returns `401`. The frontend redirects to the sign-in page. No refresh token flow in MVP — the sliding window on active requests is sufficient.
- Sign-out must clear the cookie server-side.

### Rate limiting
- **Strategy**: middleware-based rate limiting using a per-user sliding window counter.
- **Default limits**:
  - Authenticated endpoints: 30 requests per minute per user.
  - Auth endpoints (`/auth/google`, `/auth/google/callback`): 5 requests per minute per IP.
  - Internal cron endpoints: 5 requests per minute per token.
- **Response**: `429 Too Many Requests` with `Retry-After` header.
- **Implementation**: in-memory counter (MVP). Can be migrated to Redis if needed at scale.

### Tenant isolation
- **Every API endpoint** scoped to a space must validate that the authenticated user is a member of that space.
- Database queries must always include `space_id` in WHERE clauses — never rely solely on application-level checks.
- Users can only see, edit, and delete data within spaces they belong to.
- No cross-space data leakage in any response.

**Enforcement via SpaceScopedRepository pattern:**
- All database access for space-scoped tables (`expenses`, `expense_lines`, `categories`, `tags`, `payment_methods`, `limits`, `limit_filters`, `recurring_templates`, `merchants`, `monthly_wraps`) must go through a `SpaceScopedRepository` base class (or equivalent query builder) that **automatically injects `space_id`** from the request context into every query.
- Developers must never write raw queries against space-scoped tables. All reads and writes go through repository methods (e.g., `repo.get_by_id(expense_id)`, `repo.list(filters)`, `repo.create(data)`) that guarantee the `space_id` filter is always present.
- Direct UUID lookups (e.g., `GET /expenses/{expense_id}`) must always include `AND space_id = :space_id` — never fetch by primary key alone, as UUIDs can be guessed, leaked via logs, or shared via URLs.
- **Automated guardrail**: add a test that scans all SQLAlchemy query code and fails if any space-scoped table is queried without a `space_id` condition. This catches regressions during code review and CI.
- **Defense-in-depth (optional, recommended for 2.0.0+)**: enable PostgreSQL Row-Level Security (RLS) on space-scoped tables with a policy like `USING (space_id = current_setting('app.current_space_id')::uuid)`. Set the session variable via `SET app.current_space_id = :space_id` at the start of each request. This ensures the database itself rejects cross-space queries even if application code has a bug.

### Invite links
- Tokens must be **cryptographically random** (e.g., `secrets.token_urlsafe(32)` in Python).
- Single-use: once used, the link is permanently invalidated.
- Expiry: 7 days from creation.
- Must not be guessable or enumerable.

### Input sanitization
- Notes field: treat as plain text. Sanitize output to prevent XSS (escape HTML entities on render).
- Merchant field: plain text, no HTML rendering.
- All user input validated server-side via Pydantic schemas.

### CORS
- **Not required in production** — Azure Static Web Apps proxies API requests via `linkedBackend`, so all requests appear same-origin.
- Development mode: Vite dev server `proxy` in `vite.config.ts` forwards `/api/*` to `localhost:8000` — also no CORS needed.
- As a defense-in-depth measure, the backend should still reject requests from unexpected `Origin` headers.

### Data storage
- No files, receipts, or binary data stored anywhere.
- No sensitive financial data beyond expense amounts and merchant names.

### Secret management & rotation
- **Secrets**: `JWT_SECRET`, `GOOGLE_CLIENT_SECRET`, `INTERNAL_CRON_TOKEN`, `DATABASE_URL`.
- **Storage**: Azure App Service application settings (encrypted at rest). Never in source code.
- **Rotation plan**:
  - `JWT_SECRET`: rotation invalidates all active sessions. Plan: support two active secrets (current + previous) during rotation window. Check the current secret first, fall back to the previous. Remove the previous after 7 days (max JWT lifetime).
  - `GOOGLE_CLIENT_SECRET`: rotated via Google Cloud Console. Update in Azure App Service settings. Downtime: none if done atomically.
  - `INTERNAL_CRON_TOKEN`: rotated by updating both GitHub Actions secret and Azure App Service setting simultaneously.
  - `DATABASE_URL`: rotated via Azure PostgreSQL credential reset. Update in App Service settings. Brief restart required.
- **Frequency**: rotate secrets at minimum annually, or immediately if a compromise is suspected.

---

## 2) Reliability

### Data integrity
- **No future-dated expenses**: `purchase_datetime` must be ≤ current time (UTC). Enforced server-side (API returns 422). The frontend disables future dates in the date picker.
- Expense creation with split lines must be **atomic** (database transaction). Either all lines are saved, or none are.
- Split line validation: the sum of line amounts must equal the expense total. Enforced both client-side (UI blocks save) and server-side (API returns 422 if mismatch).
- Category deletion must atomically reassign all affected expense lines to "Uncategorized".
- `expenses.updated_at` is set to `NOW()` by the service layer on every update. No database triggers — keeps ORM behavior predictable and testable.

### Recurring expense generation (1.1.0+)
- **Idempotent**: the generator must check for existing pending expenses (by template ID + scheduled date) before creating new ones. Running the function twice for the same day must produce no duplicates.
- **Backfill**: if the function was down for multiple days, it must generate all missed pending entries on the next run.
- **Transaction safety**: all pending expense creation and `next_due_date` advancement must happen within a database transaction.

### Date/time handling
- All datetimes stored as **UTC** (`TIMESTAMPTZ` in PostgreSQL).
- The space timezone is used exclusively for:
  - Display formatting
  - Time window boundary calculations (week/month/quarter/year start/end)
  - Analytics grouping (which day/week/month an expense belongs to)
- Never perform timezone-naive datetime comparisons.
- Use proper timezone libraries (`pytz` or `zoneinfo` in Python, `date-fns-tz` or `Intl` in JavaScript).

### Limit recalculation
- Limits must recalculate when:
  - An expense is created
  - An expense is edited (amount or purchase date changed)
  - An expense is deleted
  - A pending expense is confirmed
- Recalculation should be efficient — only recalculate limits whose filters match the affected expense.

---

## 3) Performance

### Dashboard load time
- Home dashboard should load in **under 2 seconds** on a typical connection.
- Insights page initial load should complete in **under 3 seconds**.
- Use efficient database queries with proper indexes (see ARCHITECTURE.md §5.2).
- Avoid N+1 query patterns — use JOINs or batch queries.

### Concurrent user targets
| Version | Target concurrent users |
|---|---|
| 1.0.0 (MVP) | < 5 |
| 1.1.0 | < 10 |
| 2.0.0 | < 50 |
| 2.1.0 | < 100 |
| 3.0.0 | Defined based on usage |

### API request size limits
- **Max request body size**: 1 MB (enforced by FastAPI middleware).
- **Field-level max lengths** (enforced by Pydantic schemas):
  | Field | Max length |
  |---|---|
  | Merchant name | 100 characters |
  | Notes | 500 characters |
  | Tag name | 50 characters |
  | Category name | 50 characters |
  | Payment method label | 50 characters |
  | Limit name | 100 characters |
  | Recurring template name | 100 characters |
  | Space name | 100 characters |
- **Numeric field constraints** (enforced by Pydantic + database CHECK):
  | Field | Min | Max | Negative allowed |
  |---|---|---|---|
  | Expense amount (total + per line) | 0.01 | 999,999.99 | No |
  | Limit threshold | 0.01 | 999,999.99 | No |
  | Recurring default amount | 0.01 | 999,999.99 | No |
  | Default tax % | 0.00 | 99.99 | No |
- **Collection limits** (enforced at app level):
  | Collection | Max per entity |
  |---|---|
  | Tags per expense line | 10 |
  | Split lines per expense | 20 |
  | Categories per space | 50 |
  | Payment methods per member | 20 |
  | Limits per space | 30 |
  | Recurring templates per space | 50 |
  | Members per space | 10 |

### Pagination
- Transaction list: **cursor-based infinite scroll** (not offset-based, to avoid performance degradation on large datasets).
- Default page size: 20 items.
- API must return a cursor token for the next page.

### Caching strategy
- TanStack Query handles client-side caching.
- Stale time: 2 minutes (auto-refetch when page is active and data is older than 2 minutes).
- Optimistic updates for expense creation/deletion (instant UI feedback, reconcile with server response).
- No server-side caching in MVP (queries hit PostgreSQL directly). Server-side caching (Redis) can be added if performance requires it.

### Database optimization
- Index all columns used in WHERE, JOIN, ORDER BY, and GROUP BY for common queries.
- Use `EXPLAIN ANALYZE` during development to verify query plans.
- Merchant autocomplete: use prefix matching on `merchants.normalized_name` index (dedicated table, not expense scan).
- Connection pooling: see ARCHITECTURE.md §8 for pool configuration.

### Health check
- `GET /api/2.0.0/health` — no authentication required.
- Returns `{ "status": "ok", "db": "connected" }` when healthy.
- Returns `{ "status": "degraded", "db": "disconnected" }` with `503` status when DB is unreachable.
- Used by Azure App Service health probes (configure 30-second interval, 5-second timeout, 3 consecutive failures → restart).
- Response must complete within 5 seconds.

### Graceful degradation
- **DB connection failure**: health check returns 503. API endpoints return `{ "error": { "code": "SERVICE_UNAVAILABLE", "message": "..." } }` with 503 status. Frontend shows "Service temporarily unavailable" with a retry button.
- **Slow queries**: set a query timeout of 30 seconds at the SQLAlchemy level. Queries exceeding this return 504 Gateway Timeout.
- **Frontend offline**: if API requests fail, show cached data (from TanStack Query cache) with a "Connection lost — showing cached data" banner. New writes queue locally and retry when connectivity resumes (best-effort, not guaranteed).
- **Scheduled job failure**: if recurring generation or wrap generation fails, GitHub Actions reports the failure. The endpoints are idempotent — the next scheduled run will catch up.

---

## 4) Accessibility

### Keyboard navigation
- All forms must be fully navigable via keyboard (Tab, Shift+Tab, Enter, Escape).
- Modal dialogs must trap focus within the modal when open.
- Dropdowns and selectors must support arrow key navigation.

### Screen readers
- All interactive elements must have appropriate ARIA labels.
- Chart components must include accessible summaries (e.g., `aria-label="Category breakdown: Groceries 45%, Dining Out 25%..."`)
- Color is never the sole indicator — payment method chips must always show the label alongside the color.
- Alert cards must use `role="alert"` for limit warnings.

### Visual
- Minimum contrast ratio: WCAG 2.1 AA (4.5:1 for normal text, 3:1 for large text).
- Touch targets: minimum 44x44px on mobile.
- Light mode only through 2.0.0. Dark mode planned for 3.0.0.

---

## 5) Internationalization (i18n)

### Architecture
- MVP ships with **English only**. Strings may be hardcoded in components during MVP for speed.
- **2.0.0**: externalize all user-facing strings into translation files and make the codebase i18n-ready.
- **2.1.0**: add Spanish translations and locale-aware formatting.
- Use `react-i18next` for the frontend.
- Backend API error messages should use error codes (not human-readable strings) — the frontend maps codes to localized messages.

### Currency formatting
- Use `Intl.NumberFormat` with the space's `currency_code`.
- The space's currency is set during creation and is immutable.
- Display format follows the currency's standard convention (symbol, separators, decimal places).

### Date formatting
- Use the space timezone for display.
- Format dates according to the user's browser locale (e.g., "Feb 15, 2026" for en-US, "15 Feb 2026" for en-GB).
- Use `Intl.DateTimeFormat` or a library like `date-fns` with locale support.

---

## 6) Data freshness & sync

### Strategy
- MVP uses **manual refresh + auto-refetch** (no WebSocket/SSE).
- TanStack Query `refetchInterval`: **2 minutes** when the page/tab is active.
- Refetching pauses when the tab is inactive (background tabs don't poll).
- On expense create/edit/delete: optimistic update + server reconciliation.

### Conflict handling
- MVP does not handle concurrent edit conflicts (last write wins).
- This is acceptable for a small-group product (2-5 members). Conflict resolution can be added in 3.0.0 if needed.

---

## 7) Testing strategy

### Backend testing (pytest + httpx)

#### Unit tests
Cover business logic in isolation:
- Limit calculation: given a set of expenses and a limit definition, verify correct progress computation.
- Recurring generation: verify pending expenses are created correctly, idempotency works, backfill handles gaps.
- Split line validation: verify sum validation, rejection of mismatched totals.
- 3-month average computation: verify correct averaging with varying data availability (0, 1, 2, 3+ prior periods).
- Category deletion: verify expense lines are reassigned to "Uncategorized".
- Tag normalization: verify deduplication, casing, trimming.
- Time window calculations: verify correct boundaries for all timeframes across timezone edge cases.

#### Integration tests
Cover API endpoints end-to-end (with test database):
- Auth flow: Google OAuth mock → JWT cookie → authenticated requests.
- Expense CRUD: create (single + split), read, update (all fields), delete.
- Insights queries: verify correct aggregation results for known test data.
- Invite lifecycle: generate link → join → link invalidated → expired link rejected.
- Limit alerts: create limit → add expenses → verify warning/alert thresholds.
- Recurring lifecycle: create template → trigger generation → confirm/deny pending.
- Space membership: verify non-members get 403 on space-scoped endpoints.

#### Test database
- Use a dedicated PostgreSQL database for tests.
- Each test runs in a transaction that is rolled back after completion (clean state per test).
- Alternatively, use a fresh schema per test run.

### Frontend testing
- **No automated frontend tests in MVP.** UI changes too rapidly during early development.
- Manual testing covers user flows.
- Frontend E2E tests (Playwright/Cypress) can be added once the UI stabilizes (1.1.0+).

### Testing principles
- Tests must be deterministic (no flaky tests from timing, randomness, or external dependencies).
- Test data must be self-contained (each test creates its own data, no shared fixtures that cause coupling).
- Integration tests mock only external services (Google OAuth). Database is real.
- CI pipeline should run all tests on every PR.

---

## 8) Error handling

### API error responses
- Use consistent error response format:
  ```json
  {
    "error": {
      "code": "SPLIT_SUM_MISMATCH",
      "message": "Split line amounts must equal the expense total",
      "details": { "expected": 100.00, "actual": 95.50 }
    }
  }
  ```
- HTTP status codes:
  - `400` — bad request (validation errors)
  - `401` — not authenticated
  - `403` — not authorized (not a member of the space)
  - `404` — resource not found
  - `409` — conflict (e.g., duplicate category name)
  - `422` — unprocessable entity (business rule violation)
  - `500` — internal server error

### Frontend error handling
- API errors displayed as toast notifications (non-blocking).
- Form validation errors shown inline next to the relevant field.
- Network errors: show a retry prompt.
- Never show raw error messages or stack traces to users.

---

## 9) Logging, observability & monitoring

### Request tracing
- Every API request must be assigned a **correlation ID** (UUID v4), generated by middleware at request entry.
- The correlation ID must be:
  - Included in **every** log line produced during that request
  - Returned in the response header `X-Correlation-ID`
  - Available in the request context for all service/repository layers
- This enables tracing a user-reported issue to the exact request chain.

### Structured logging format
- All backend logs must be **structured JSON** (not free-text). Use Python `structlog` or `python-json-logger`.
- Every log entry must include at minimum:
  - `timestamp` (ISO 8601 UTC)
  - `level` (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - `correlation_id` (from request middleware; omitted for startup/shutdown logs)
  - `message` (human-readable summary)
  - Additional context fields as documented below

### What to log

**API request lifecycle (INFO)** — every request/response pair:
- `event`: `"api_request"`
- Fields: `method`, `path`, `status_code`, `duration_ms`, `user_id`, `space_id`, `ip`

**Authentication events (INFO / WARNING):**
- Successful sign-in: user ID, email, method (Google SSO)
- Sign-out: user ID
- Failed auth attempt (WARNING): reason (expired JWT, invalid token, missing cookie), IP address
- JWT sliding window refresh: user ID, old expiry, new expiry

**Business events (INFO):**
- Expense created/updated/deleted: expense ID, space ID, user ID, amount
- Limit breached/warned: limit ID, space ID, current progress, threshold
- Category deleted with orphan reassignment: category ID, count of reassigned expenses
- Invite link generated/used/expired: invite ID, space ID
- Space created: space ID, creator user ID
- Member joined space: user ID, space ID, invite ID

**Scheduled job execution (INFO / ERROR):**
- Job start: job name, trigger time
- Job completion: job name, duration, counts (e.g., "generated 3 pending expenses across 2 spaces")
- Job failure (ERROR): job name, error message, stack trace

**Errors (ERROR / CRITICAL):**
- Unhandled exceptions: full stack trace, correlation ID, request context
- Database connection failures (CRITICAL): connection pool state, retry count
- External service failures (Google OAuth): error code, response body

**Performance warnings (WARNING):**
- Slow queries: queries exceeding 1 second — log parameterized query text (no user data) and duration
- Slow requests: requests exceeding 10 seconds

### What NOT to log
- Passwords, tokens, secrets, or API keys (even partially)
- Full request/response bodies in production (metadata only; full bodies allowed at DEBUG level in development)
- PII beyond user ID and email (no IP addresses in production logs except for auth events)

### Log levels
- Production default: **INFO** (configurable via `LOG_LEVEL` environment variable)
- DEBUG must never be enabled in production (may expose sensitive data)

### Frontend logging
- No structured logging framework required in MVP
- Use `console.error` for unexpected errors (caught by React error boundaries)
- TanStack Query failures are logged automatically by the library

### Monitoring
- Azure App Service built-in monitoring for uptime, response times, and error rates
- Health check endpoint (`GET /api/2.0.0/health`) polled by Azure health probes
- Recommended Azure Monitor alerts: health check failures (3 consecutive), error rate > 5%, avg response time > 5s
- No external monitoring services required in 2.0.0. Azure Monitor is sufficient.
