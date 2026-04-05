# Scope & Roadmap

This document defines **what is in each version** of the Expense Tracker & Budget Insights product. Agents and developers must check this document before building any feature to confirm it is in scope for the current version.

### Versioning scheme

Follows **Semantic Versioning (SemVer)**: `MAJOR.MINOR.PATCH`

- **MAJOR** (X.0.0): large feature release, potential breaking changes
- **MINOR** (X.Y.0): new features, backward-compatible
- **PATCH** (X.Y.Z): bug fixes, hotfixes

---

## Current version: 1.0.0

---

## 1.0.0 — Core expense tracking (MVP)

Ship fast, validate the core expense-tracking loop for one couple.

### Authentication & onboarding
- [ ] Google SSO sign-in / sign-up (OAuth 2.0)
- [ ] JWT session via httpOnly cookies
- [ ] Sign out
- [ ] First-time onboarding: create shared space (name, currency, timezone)
- [ ] Optional: seed default categories during onboarding
- [ ] Optional: set default tax % during onboarding

### Invite system
- [ ] Generate single-use invite link (7-day expiry)
- [ ] Partner joins via invite link → Google sign-in → added to space
- [ ] Invite link invalidated after use

### Expense entry (single-line only)
- [ ] Add single-line expense (amount, merchant, category, datetime, spender, payment method, tags, notes)
- [ ] Merchant autocomplete from previously used merchants in space
- [ ] Merchant → category auto-suggestion (latest used category for that merchant)
- [ ] Spender defaults to logged-in user
- [ ] Purchase datetime defaults to now
- [ ] Full-page expense entry at `/expenses/new`

### Expense management
- [ ] Edit expense (all fields editable, including purchase date → limits recalculate)
- [ ] Delete expense (hard delete, "Are you sure?" confirmation dialog)
- [ ] View expense detail (all fields, created datetime)

### Categories
- [ ] Create/edit/delete shared categories (flat, case-insensitive dedup)
- [ ] "Uncategorized" system category (non-deletable, non-selectable by users)
- [ ] Category deletion reassigns orphaned expenses to "Uncategorized"

### Tags
- [ ] Free-form tags on expense lines
- [ ] `#` character triggers inline autocomplete (Obsidian-style)
- [ ] Allowed characters: alphanumeric, hyphens, underscores (`[a-zA-Z0-9_-]+`)
- [ ] Auto-normalization (lowercase, trim, `#` prefix)
- [ ] Autocomplete from prior tags in space
- [ ] Auto-created on first use
- [ ] No tag-specific insights in MVP

### Payment methods (plain)
- [ ] Built-in "Cash" method per space (shared, non-deletable)
- [ ] Members create their own methods (label only — no custom colors in MVP)
- [ ] Cross-member method selection during expense entry
- [ ] Deletion shows "Deleted method" on historical expenses (frontend resolves NULL)

### Limits
- [ ] Create/edit/delete limits
- [ ] Timeframes: weekly + monthly only (week starts Monday)
- [ ] Filters: category only
- [ ] Configurable warning threshold per limit (`warning_pct`, default 60%)
- [ ] Color states: green (< warning), amber (≥ warning), red (100%), purple (> 100%)
- [ ] Only confirmed expenses count (pending excluded)
- [ ] In-app alerts only (2–3 cards on Home)

### Home dashboard
- [ ] Hero total spent (current week or month) + delta vs 3-month average
- [ ] Week / Month toggle
- [ ] Limit alerts (2–3 max)
- [ ] Spending trend line (cumulative, current period vs 3-month avg)
- [ ] Category distribution pie/donut
- [ ] Merchant leaderboard (top by amount only)
- [ ] Latest transactions count + link to full list

### Insights
- [ ] Desktop: split view (charts + transaction list side-by-side)
- [ ] Mobile: charts first, then transactions
- [ ] Filters: time window, spender, category, merchant, tag, payment method
- [ ] Time presets: this week/last week, this month/last month, month picker, YTD
- [ ] Charts: spending trend line, category distribution pie, merchant leaderboard (amount), spender breakdown
- [ ] Transaction list with filters

### Transaction list
- [ ] Grouped by date (Today, Yesterday, This Week, Earlier…)
- [ ] Infinite scroll
- [ ] Filters (same as Insights)
- [ ] Search by merchant/notes/tags (case-insensitive contains)

### Navigation
- [ ] Public landing page (unauthenticated visitors)
- [ ] Mobile: bottom tab bar (Home, Transactions, [FAB: +], Limits, Insights) + centered FAB for "Add Expense"
- [ ] Desktop: left sidebar (Home, Transactions, Limits, Insights, Settings) + prominent "Add Expense" button
- [ ] Settings accessible from avatar profile menu (mobile) or sidebar bottom (desktop)

### Settings
- [ ] Hub-and-spoke navigation layout with drill-down sub-pages
- [ ] Space info: space name (editable), currency (display only), timezone (editable)
- [ ] Categories > sub-page: CRUD
- [ ] Payment Methods > sub-page: per-member, label only
- [ ] Tags > sub-page: read-only list of space tags
- [ ] Members > sub-page: display only, no removal
- [ ] Invite > sub-page: generate/disable invite link
- [ ] Taxes > sub-page: default tax % (editable)

### Cross-cutting
- [ ] Currency-aware formatting via `Intl.NumberFormat`
- [ ] Auto-refetch every 2 minutes when page active
- [ ] Light mode only
- [ ] No future-dated expenses (server-side 422 + date picker restriction)
- [ ] 10-member space limit with clear error message

### Cross-cutting (Phase 15)
- [ ] Error tracking: Sentry (free tier, 5K errors/mo) — frontend React + backend Python
- [ ] Basic OG meta tags on landing page (title, description) for link sharing
- [ ] React error boundaries at route level
- [ ] Toast notifications for mutation success/error
- [ ] Loading skeletons for data-fetching states
- [ ] Empty states for lists with no data
- [ ] Currency formatting via Intl.NumberFormat with space currency_code
- [ ] CI pipeline (GitHub Actions: lint + test on PRs)
- [ ] CD pipeline (GitHub Actions: deploy on push to main)
- [ ] Azure deployment (Static Web Apps + App Service + PostgreSQL)

### Operational
- [ ] Rollback strategy documented:
  - Azure App Service: swap deployment slots to revert
  - Database: `alembic downgrade -1` for migration rollback
  - Never modify applied migrations — create new ones
- [ ] Azure monitoring alerts (free tier):
  - Health check failure alert
  - 5xx error rate spike alert
  - Response time > 5s alert

---

## 1.1.0 — Automation & sharing

Add recurring expenses and shareable analytics.

### Recurring expenses
- [ ] Create/edit/delete recurring templates
- [ ] Schedules: weekly, monthly
- [ ] Internal scheduled job generates pending expenses (idempotent, backfills missed)
- [ ] Confirm / edit+confirm / deny pending expenses
- [ ] Nav badge with pending count

### Navigation changes
- [ ] Bottom tab bar: Recurring replaces Transactions (Home, Recurring, [FAB: +], Limits, Insights)
- [ ] Desktop sidebar: Recurring replaces Transactions (with pending badge)
- [ ] Transactions remain accessible from Home "View all →" link and within Insights transaction list

### Home additions
- [ ] Pending recurring confirmations card
- [ ] Merchant leaderboard: Amount/Count toggle

### Insights additions
- [ ] Shareable Insights links (URL-encoded filter state)
- [ ] Share button copies URL with current filters

### Expense entry improvements
- [ ] Merchant auto-fill: selecting a known merchant auto-fills category, payment method, spender, and tags from the last expense with that merchant
- [ ] Backend: store `last_payment_method_id`, `last_spender_id`, `last_tags` on merchant records (migration needed)
- [ ] Frontend: populate all fields on merchant select (user can override any)

### Technical improvements
- [ ] Refactor services: domain exceptions instead of HTTPException (unblocks cron jobs)
- [ ] Migrate python-jose → PyJWT (unmaintained dependency)
- [ ] React.lazy() code splitting for routes (bundle size reduction)
- [ ] Deduplicate add/edit expense forms (extract shared ExpenseForm component)
- [ ] Wire filters into transaction list page (match Insights filter bar)
- [ ] Add "Save & Add Another" button to expense form
- [ ] Optimize spending trend: SQL GROUP BY instead of in-memory aggregation
- [ ] Add partial index for confirmed expenses
- [ ] Add Content Security Policy headers

---

## 2.0.0 — Full-featured product

Split purchases, beneficiaries, advanced analytics, i18n architecture, and usage analytics.

### Split purchases
- [ ] "Split" toggle on Add Expense page reveals inline split line editor
- [ ] Add split expense (multiple lines: amount, category, tags per line)
- [ ] Split validation: sum of lines must equal total (UI blocks save)

### Beneficiary
- [ ] Beneficiary field on expense lines (member or Shared)
- [ ] Default beneficiary: Shared
- [ ] Beneficiary filter in Insights and limits

### Monthly wrap
- [ ] Pre-computed by internal scheduled job on 1st of each month
- [ ] Only generated for active spaces (≥10 confirmed expenses in previous month)
- [ ] Highlights: best improvements, worst spikes, frequently breached limits
- [ ] Rule-based recommendations (propose limit adjustments)
- [ ] Monthly wrap card on Home (first 5 days of month)

### Timeframe expansion
- [ ] Limits: quarterly + yearly timeframes
- [ ] Limit filters: full set (category, merchant, tag, spender, beneficiary, payment method)
- [ ] Insights: quarter picker time preset
- [ ] Recurring schedules: quarterly + yearly

### Payment method customization
- [ ] Custom colors (hex, for visual identification)
- [ ] Colored chip display in selectors

### Insights enhancements
- [ ] Drill-down: clicking chart elements filters transaction list
- [ ] Limit progress bars (moved from Home to Insights)
- [ ] Category bar comparison: current vs 3-month average (moved from Home to Insights)

### Usage analytics
- [ ] Self-hosted Umami for privacy-friendly usage tracking (free)
- [ ] Page views, feature usage, user counts
- [ ] No PII collected — anonymized metrics only

### Security & access control
- [ ] RBAC: add `role` column to SpaceMember (owner/member), restrict destructive ops to owner
- [ ] Token revocation: add `jti` claim + server-side deny-list, or shorten access token + refresh token
- [ ] Member removal: `DELETE /spaces/{id}/members/{member_id}` (owner-only)
- [ ] Pagination on all list endpoints (categories, tags, payment methods, members)
- [ ] Commit to or remove SpaceScopedRepository pattern

### Enhanced landing page & SEO
- [ ] Richer public landing page (testimonials, screenshots, feature tour)
- [ ] Open Graph tags (title, description, image) for link sharing
- [ ] sitemap.xml + robots.txt
- [ ] Google Search Console + Bing Webmaster Tools registration

### i18n architecture
- [ ] Externalize all user-facing strings into translation files
- [ ] Backend error codes (frontend maps to localized messages)
- [ ] Architecture ready for multiple languages (English only in 2.0.0)

---

## 2.1.0 — Localization & polish

### Tax convenience calculator
- [ ] Frontend toggle: "Enter Total" (default) or "Enter Pre-tax + Tax"
- [ ] Uses space's default tax % for calculation
- [ ] Only total is stored (pre-tax/tax not persisted)

### Category icons
- [ ] User-selectable Lucide icon per category
- [ ] Icon stored in category model (`icon` field, optional, defaults to null)
- [ ] Display icon alongside category name in chips, dropdowns, and legends
- [ ] Icon picker UI in category create/edit form (searchable Lucide icon grid)

### i18n implementation
- [ ] Spanish translations
- [ ] Locale-aware date and number formatting

---

## 3.0.0 — Platform expansion

- Installable PWA (manifest + standalone display; no offline/service worker — just "Add to Home Screen" for native-feel entry point)
- Soft delete + audit trail (restore deleted expenses)
- Dark mode (manual toggle)
- Multi-currency (per-expense currency selection with conversion)
- Income tracking
- Custom date ranges in Insights
- Share Insights as chart image snapshot
- Data export (CSV)
- Email/password authentication alternative
- Personal API tokens (Bearer auth for CLI/scripts)
- Batch confirm for pending recurring expenses
- Limit alert tuning (mute/snooze)
- Pin chart to Home (custom dashboard)

---

## 4.0.0 — Intelligence & reach

- Saved views library (personal saved filter configurations)
- Share saved views to space
- AI insights card (explainable narrative summaries with drill-down)
- Notification channels (email/push) for limit alerts and pending recurring
- Offline / full PWA support (service worker, background sync, cached reads)

---

## Explicitly deferred

These features are intentionally excluded from the current roadmap. Do not build them until the listed version:

| Feature | Earliest version | Rationale |
|---|---|---|
| Split purchases | 2.0.0 | Single-line covers 90% of use cases in MVP |
| Beneficiary | 2.0.0 | Requires split architecture; defer until 2.0.0 |
| Recurring expenses | 1.1.0 | Users can manually enter for first weeks |
| Shareable Insights | 1.1.0 | Partners can open Insights themselves |
| Merchant auto-fill (full) | 1.1.0 | Category auto-fill sufficient for MVP |
| Monthly wrap | 2.0.0 | Pre-computed analytics is a luxury |
| Quarterly/yearly timeframes | 2.0.0 | Weekly + monthly covers 95% of use |
| Payment method colors | 2.0.0 | Plain labels sufficient for MVP |
| Category icons | 2.1.0 | Colored chips sufficient for MVP–2.0.0 |
| Tax calculator | 2.1.0 | Users can enter the total directly |
| i18n (Spanish) | 2.1.0 | English-only until user base demands it |
| Insights drill-down | 2.0.0 | Complex interaction; defer until core is stable |
| Usage analytics (Umami) | 2.0.0 | Not needed until real users exist |
| Enhanced landing page + SEO | 2.0.0 | Authenticated app; word-of-mouth first |
| Error tracking (Sentry) | 1.0.0 | Added in MVP Phase 15 |
| Soft delete / audit trail | 3.0.0 | Hard delete with confirmation is acceptable |
| Dark mode | 3.0.0 | Light mode only until platform expansion |
| Multi-currency | 3.0.0 | Single currency per space covers MVP |
| Income tracking | 3.0.0 | Expenses-only until platform expansion |
| Data export (CSV) | 3.0.0 | Not needed for small-group usage |
| Email/password auth | 3.0.0 | Google SSO covers the target audience |
| Installable PWA (manifest only) | 3.0.0 | Minimal effort; improves mobile UX significantly |
| Offline / full PWA (service worker) | 4.0.0 | Requires significant architecture changes |
| Push notifications | 4.0.0 | In-app alerts are sufficient |
| AI insights | 4.0.0 | Rule-based wrap is sufficient |
| Bank sync / import | Never | Manual entry is intentional |
| File uploads / receipts | Never | Notes-only by design |
| Transfers | TBD | May never be needed |
| Real-time sync (WebSocket) | TBD | 2-minute refetch is sufficient |

---

## Concurrent user targets

| Version | Target concurrent users |
|---|---|
| 1.0.0 (MVP) | < 5 |
| 1.1.0 | < 10 |
| 2.0.0 | < 50 |
| 2.1.0 | < 100 |
| 3.0.0 | Defined based on usage |
