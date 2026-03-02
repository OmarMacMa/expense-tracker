# Scope & Roadmap

This document defines **what is in each version** of the Expense Tracker & Budget Insights product. Agents and developers must check this document before building any feature to confirm it is in scope for the current version.

---

## Current version: MVP (V0.1)

---

## MVP (V0.1) — Core expense tracking

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
- [ ] Add single-line expense (merchant, datetime, spender, amount, category, notes, tags, payment method)
- [ ] Merchant autocomplete from previously used merchants in space
- [ ] Merchant → category auto-suggestion (latest used category for that merchant)
- [ ] Spender defaults to logged-in user
- [ ] Purchase datetime defaults to now
- [ ] Modal for single-line expense entry

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
- [ ] 80% warning threshold (default), 100% alert
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
- [ ] Mobile: bottom tab bar + centered FAB for "Add Expense"
- [ ] Desktop: left sidebar + prominent "Add Expense" button

### Settings
- [ ] Space name (editable)
- [ ] Currency (display only, not editable after creation)
- [ ] Timezone (editable)
- [ ] Default tax % (editable)
- [ ] Members list (display only, no removal)
- [ ] Invite link management (generate/disable)
- [ ] Categories CRUD
- [ ] Payment methods management (per-member, label only)

### Cross-cutting
- [ ] Currency-aware formatting via `Intl.NumberFormat`
- [ ] Auto-refetch every 2 minutes when page active
- [ ] Light mode only
- [ ] No future-dated expenses (server-side 422 + date picker restriction)
- [ ] 10-member space limit with clear error message

---

## V0.5 — Automation & sharing

Add recurring expenses and shareable analytics.

### Recurring expenses
- [ ] Create/edit/delete recurring templates
- [ ] Schedules: weekly, monthly
- [ ] Internal scheduled job generates pending expenses (idempotent, backfills missed)
- [ ] Confirm / edit+confirm / deny pending expenses
- [ ] Nav badge with pending count

### Home additions
- [ ] Pending recurring confirmations card
- [ ] Merchant leaderboard: Amount/Count toggle

### Insights additions
- [ ] Shareable Insights links (URL-encoded filter state)
- [ ] Share button copies URL with current filters

---

## V1 — Full-featured product

Split purchases, beneficiaries, advanced analytics, and i18n architecture.

### Split purchases
- [ ] Add split expense (multiple lines: amount, category, tags per line)
- [ ] Split validation: sum of lines must equal total (UI blocks save)
- [ ] Full page for split expense entry

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

### i18n architecture
- [ ] Externalize all user-facing strings into translation files
- [ ] Backend error codes (frontend maps to localized messages)
- [ ] Architecture ready for multiple languages (English only in V1)

---

## V1.5 — Localization & polish

### Tax convenience calculator
- [ ] Frontend toggle: "Enter Total" (default) or "Enter Pre-tax + Tax"
- [ ] Uses space's default tax % for calculation
- [ ] Only total is stored (pre-tax/tax not persisted)

### i18n implementation
- [ ] Spanish translations
- [ ] Locale-aware date and number formatting

---

## V2 — Platform expansion

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

## V3 — Intelligence & reach

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
| Split purchases | V1 | Single-line covers 90% of use cases in MVP |
| Beneficiary | V1 | Requires split architecture; defer until V1 |
| Recurring expenses | V0.5 | Users can manually enter for first weeks |
| Shareable Insights | V0.5 | Partners can open Insights themselves |
| Monthly wrap | V1 | Pre-computed analytics is a luxury |
| Quarterly/yearly timeframes | V1 | Weekly + monthly covers 95% of use |
| Payment method colors | V1 | Plain labels sufficient for MVP |
| Tax calculator | V1.5 | Users can enter the total directly |
| i18n (Spanish) | V1.5 | English-only until user base demands it |
| Insights drill-down | V1 | Complex interaction; defer until core is stable |
| Soft delete / audit trail | V2 | Hard delete with confirmation is acceptable |
| Dark mode | V2 | Light mode only until platform expansion |
| Multi-currency | V2 | Single currency per space covers MVP |
| Income tracking | V2 | Expenses-only until platform expansion |
| Data export (CSV) | V2 | Not needed for small-group usage |
| Email/password auth | V2 | Google SSO covers the target audience |
| Installable PWA (manifest only) | V2 | Minimal effort; improves mobile UX significantly |
| Offline / full PWA (service worker) | V3 | Requires significant architecture changes |
| Push notifications | V3 | In-app alerts are sufficient |
| AI insights | V3 | Rule-based wrap is sufficient |
| Bank sync / import | Never | Manual entry is intentional |
| File uploads / receipts | Never | Notes-only by design |
| Transfers | TBD | May never be needed |
| Real-time sync (WebSocket) | TBD | 2-minute refetch is sufficient |

---

## Concurrent user targets

| Version | Target concurrent users |
|---|---|
| MVP (V0.1) | < 5 |
| V0.5 | < 10 |
| V1 | < 50 |
| V1.5 | < 100 |
| V2 | Defined based on usage |
