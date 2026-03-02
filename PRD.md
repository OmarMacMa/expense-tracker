# Product Requirements Document — Expense Tracker & Budget Insights

This document defines **what** the product does and **why**. For technical implementation details, see `ARCHITECTURE.md`. For quality constraints, see `REQUIREMENTS.md`. For version scope, see `SCOPE.md`. Features are delivered progressively across versions (MVP → V0.5 → V1 → V1.5+).

---

## 1) Product summary

A **multi-tenant web app** for couples/families (and eventually individuals) to track expenses in a shared space with:

- Fast manual expense entry (single or split purchases)
- Shared custom categories (flat)
- Optional tags for cross-cutting themes (e.g., `#vacation`, `#pizza`)
- Weekly/monthly/quarterly/yearly limits with warnings/alerts
- A high-signal Home dashboard + a powerful Insights area
- Recurring expenses that auto-generate **pending** entries that users confirm/edit/deny
- Shareable Insights links (URL encodes filters)

**MVP real usage:** one couple/family. **Product form:** multi-tenant SaaS (many unrelated users can sign up) with strong tenant isolation.

---

## 2) Goals and non-goals

### Goals
- Become the **source of truth** for shared expenses.
- Make it easy to answer:
  - "Where did our money go this week/month?"
  - "What merchants/categories are trending up?"
  - "Are we about to exceed a limit?"
  - "What's unusual compared to our normal?"
- Keep entry friction low while enabling accurate analytics.
- Provide an Insights experience powerful enough to diagnose spikes and patterns.

### Non-goals (MVP)
See `SCOPE.md` for the full exclusion list and version roadmap. Key non-goals for MVP:
- Split purchases, beneficiary tracking (V1)
- Recurring expenses (V0.5)
- Income tracking, transfers, file uploads, bank sync
- Soft deletes, dark mode, multi-currency, offline/PWA
- Real-time sync, push notifications, AI insights
- Tax calculator (V1.5), i18n (V1.5)
- Payment method customization (V1)

---

## 3) Personas

### Primary
- **Couple/family co-managing spend** (all members are first-class users, full transparency).

### Secondary
- Individual who wants budgets + insights (enabled later via personal space).

---

## 4) Core concepts & terminology

### Tenant
A top-level account boundary. Users only access data within spaces they are members of.

### Space
A financial "workspace". Focus is **Shared Space**.
- **Shared space**: multiple members, shared categories, shared limits, shared insights.
- **Personal space**: planned later (architected as another space type).
- **Initial constraint**: a user belongs to **one space only**, but the system is designed to support multiple spaces per user in the future.
- **Soft member limit**: 10 members per space. The invite endpoint returns a clear error when the limit is reached: *"This space has reached its member limit (10)."* Sufficient for couples, families, and roommates.
- **No member removal** — members cannot be kicked. Space lifecycle management (archival/deprecation) is a future consideration (post-V1).
- **Timezone**: each space has a timezone setting (auto-detected from browser during setup, overridable). All time window calculations (weeks, months, quarters, years) use the space timezone. Datetimes are stored as UTC.
- **Currency**: single currency per space, selected during creation, immutable after creation. Displayed using the currency's standard format.

### Member
A user inside a space. In shared space, all members are first-class: can view/edit/delete anything.

### Expense
A logged purchase instance, anchored by **purchase date/time**.

### Purchase (header) vs Split lines
- **Purchase header**: merchant, purchase datetime, spender, payment method, notes.
- **Split line(s)**: the actual categorized amounts.

If not split, a purchase has exactly **one** split line.

### Spender vs Beneficiary
- **Spender**: who paid (any member). Required at purchase level. **Defaults to the logged-in user.**
- **Beneficiary**: who it was for (any member / Shared). Required per split line. **Defaults to Shared.** — **V1+ only**; MVP does not track beneficiary.

This supports long-distance and mixed-benefit purchases (e.g., groceries shared + shampoo for Person B). In MVP, all expenses are implicitly shared.

### Category
Shared, user-defined, **flat** taxonomy inside a space. Used for primary budgeting and analytics.
- **"Uncategorized"** is a permanent, non-deletable system category. Users cannot assign expenses to it directly; it is only used as a fallback when a user-created category is deleted and expenses are orphaned.

### Tag
Optional, free-form, normalized label (e.g., `#vacation`). Used for search and optional slicing.
- Tags never replace categories.
- Tags can be used for category-like specificity (e.g., `#coffee`, `#dominos`) under a broader category.
- **Trigger**: the `#` character triggers inline tag creation/autocomplete.
- **Allowed characters**: alphanumeric, hyphens, underscores. Regex: `[a-zA-Z0-9_-]+`. No spaces.
- **Normalization**: lowercase, trimmed. The `#` prefix is a **display convention only** — tags are stored without it in the database (e.g., stored as `vacation`, displayed as `#vacation`).
- **Autocomplete**: Obsidian-style — as the user types `#` followed by characters, previously used tags in the space are suggested in a dropdown. User can select an existing tag or continue typing to create a new one.
- **Deduplication**: normalized form is the unique key; `Vacation`, `vacation`, `#vacation` all resolve to `#vacation`.
- **Creation**: auto-created on first use when an expense is saved with a new tag name.

### Payment method
A unified concept representing *how* a purchase was paid. A **single flat list of payment methods per space**.

- **Space defaults**: every space starts with a built-in **Cash** method (shared, no owner).
- **Member-created methods**: each member can add their own cards/accounts. Each has:
  - **Label** (user-chosen name, e.g., "Visa 4821", "Amex Gold")
  - **Color** (user-chosen, for quick visual identification) — **V1+**; MVP uses default colors
  - **Owner** (the member who created it)
  - **Unique ID** (two members can have methods with the same label — they are distinct records)
- **Cross-member usage**: the spender can select **any** method in the space (including another member's card). The method's owner is preserved.
- **Selector UX**: MVP shows a simple dropdown with method labels. V1+ renders colored chips/pills with `<name>` (or `<name> (<owner>)` when disambiguation is needed).
- **Deletion behavior**: when deleted, `payment_method_id` becomes NULL on historical expenses. The frontend resolves NULL to a **"Deleted method"** display label. This is a frontend display convention — no schema change or snapshot column needed.
- Managed per-member under Settings.

### Limit
A weekly or monthly threshold (quarterly/yearly added in V1) applied to a combination of filters.
- MVP supports category-only filters. V1 expands to category/tag/merchant/spender/beneficiary/payment method.
- A single expense can count toward multiple limits.
- **Only confirmed expenses count** — pending recurring expenses do NOT affect limit calculations.

### Recurring template (V0.5+)
A rule that generates "pending expenses" on a schedule (weekly/monthly; quarterly/yearly added in V1).

### Pending expense (V0.5+)
An auto-generated expense instance from a recurring template that requires user action:
- ✅ Confirm (becomes normal expense, now counts toward limits/insights)
- ✏️ Edit (adjust fields then confirm)
- ❌ Deny (does not post)

Pending stays pending indefinitely until acted upon.
- **Does NOT count toward limits.**
- **Does NOT appear in Insights charts.**
- **Does appear** on the Home dashboard and in the Recurring view.

---

## 5) Key product decisions (locked)

### Spaces & collaboration
- The system is **multi-tenant**.
- MVP focuses on **one shared space per user**, but supports multiple spaces in the future.
- All members are first-class, full transparency: can view/edit/delete any shared expenses.
- No member removal (all versions through V1).

### Data & entry
- **Expenses-only** (no income tracking; planned for V2).
- Single currency per space with currency-aware formatting.
- Purchase datetime drives analytics/limits. Creation datetime is metadata shown in detail views.
- **Hard deletes** with a simple "Are you sure?" confirmation dialog.
- No attachments ever (notes-only).
- **Everything is editable** after creation, including purchase date. Limits recalculate when date or amount changes.
- **No future-dated expenses.** Purchase datetime must be ≤ now. Enforced server-side (API returns 422). The frontend disables future dates in the date picker.

### Categories, merchants, tags
- Shared **custom** categories (flat). "Uncategorized" is a system-only fallback.
- Merchant is free text with **autocomplete** from previously used merchants (cached in dedicated `merchants` table).
- Merchant → category auto-suggestion: **latest used category for that merchant** (by expense creation time, case-insensitive, no ML).
- Merchant search/filtering: **case-insensitive contains** matching.
- Tags: free-form, normalized, `#`-triggered inline autocomplete.

### Split purchases (V1)
- Hybrid UX: default single line; optional split.
- Split line requires **Amount + Category + Beneficiary**.
- **UX**: modal overlay for single-line; expands to full page when "Split" is toggled.

### Recurring (V0.5+)
- Schedules: weekly, monthly (V0.5). Quarterly, yearly (V1).
- Generates pending expenses that users confirm/edit/deny.
- Pending surfaced on Home and via nav badge.
- **Backfill**: missed scheduled dates generate all missed pending entries (idempotent, no duplicates).

### Limits & insights
- Limits: weekly, monthly (MVP). Quarterly, yearly (V1). Week starts Monday.
- Warnings/alerts on Home (2–3 max). **In-app only** (no push notifications).
- Insights layout: desktop split view; mobile chart-first.
- Default comparisons emphasize **vs last 3-month average**.
- Shareable Insights links (V0.5+).

### Taxes
- Two entry modes: **Enter Total** (default) and **Enter Pre-tax + Tax** (frontend convenience calculator using space's default tax %).
- **Only total is stored.** Pre-tax/tax is not persisted.
- **Tax calculator is V1.5.** MVP users enter the total directly.

### Invites
- Link-based invites with **7-day expiry + single-use**.

### Data freshness
- Manual refresh + **auto-refetch every 2 minutes** when the page is active. No real-time sync.

---

## 6) Feature set (functional requirements)

> **Note**: This section describes the complete product vision. See `SCOPE.md` for which features are in each version. Features below are annotated with their target version where they differ from MVP.

### 6.1 Authentication & onboarding

#### Authentication
- **Google SSO only** (no email/password until V2).
- Sign up / sign in / sign out flows.
- Session persistence.

#### Onboarding
- After first sign-in, user creates a shared space:
  - Space name
  - Currency (selected from a list; immutable after creation)
  - Timezone (auto-detected, overridable)
  - Default tax % (optional)
  - Optional: seed with recommended default categories (see Appendix)

### 6.2 Shared space management
- Space has: name, currency, timezone, default tax %, members, shared categories, limits, recurring templates, payment methods.
- Member roles: everyone is equal (no admin roles).
- **Invite flow**:
  1. Member clicks "Invite partner"
  2. App generates a single-use invite link (7-day expiry)
  3. Partner opens link → Google sign-in → added to space
  4. Invite link is invalidated after use

### 6.3 Expense entry

#### Add expense (single-line) — MVP
- Merchant (required; with autocomplete from prior merchants)
- Purchase datetime (required; default = now)
- Spender (required; default = logged-in user)
- Payment method (optional but recommended)
- Notes (optional; max 500 characters)
- Split line (single):
  - Amount (required; entered as total)
  - Category (required; auto-suggested from merchant)
  - Tags (optional; `#`-triggered autocomplete; max 10 per line)

#### Add expense (split) — V1
- Same purchase header fields
- Multiple split lines, each with: Amount, Category, Beneficiary, Tags (optional)
- **Validation**: sum of split line amounts must equal total. UI blocks saving until resolved.

#### Taxes input convenience — V1.5
- Frontend toggle: "Enter Total" (default) or "Enter Pre-tax + Tax"
- Tax calculator uses space's default tax %.
- Only total is stored.

### 6.4 Merchant auto-suggest for category
- When merchant is entered/changed, category auto-selects the **latest category** used with that merchant (by expense creation time, case-insensitive). Creation time is used rather than purchase date because it reflects the user's most recent categorization intent and avoids conditional updates.
- User can override.
- After save, future suggestions use the latest mapping.
- Edge case: merchant used across multiple categories → suggestion uses latest; optionally show "Recent categories: …" in dropdown.

### 6.5 Categories management
- Create/edit/delete shared categories (flat, case-insensitive dedup).
- "Uncategorized" is always present, non-deletable, non-selectable by users.
- **Deletion**: orphaned expenses are reassigned to "Uncategorized".

### 6.6 Tags
- Optional tags on expense split lines.
- `#` character triggers inline autocomplete. Allowed characters: `[a-zA-Z0-9_-]+` (no spaces).
- Free-form with normalization (lowercase, trim) and Obsidian-style autocomplete.
- Auto-created on first use.
- Max 10 tags per expense line.
- MVP usage: search, filter. No tag-specific insights or default graphs by tag.

### 6.7 Limits
- **Timeframes**: weekly / monthly (MVP). Quarterly / yearly added in V1.
- **Filters**: category only (MVP). Full filter set (category, merchant, tag, spender, beneficiary, payment method) added in V1.
- **Warning threshold**: 80% (default). Alert at 100%.
- Only confirmed expenses count (pending excluded).
- A transaction can count toward multiple limits.
- **In-app alerts only** (2–3 cards on Home), no push notifications.
- **Limit progress bars**: in Insights (V1+). Home shows limit alert cards only.

### 6.8 Recurring expenses (V0.5+)
- **Template fields**: name, schedule, default amount/merchant/category/spender/payment method/tags, next due date, active/inactive.
- **Schedules**: weekly, monthly (V0.5). Quarterly, yearly added in V1.
- **Generation**: automated daily via internal scheduled endpoint. Checks templates where `next_due_date <= today`. Idempotent. Backfills missed dates.
- **User actions**: confirm → normal expense; edit + confirm; deny → not posted.
- **Visibility**: Home card + nav badge with pending count.

### 6.9 Home dashboard
High-signal entry point. Shows:
1. **Hero number**: Total spent for selected window + **delta vs 3-month average** (e.g., "+12%" or "-8% vs avg").
2. **Time toggle**: "This Week" / "This Month" — all content updates.
3. **Alerts** (2–3 max): limits breached/near-breached.
4. **Pending recurring**: confirmations card. — **V0.5+**
5. **Core graphs (MVP)**:
   - Spending trend line (cumulative, current period vs 3-month avg)
   - Category distribution (pie/donut)
   - Merchant leaderboard (top by amount only; Amount/Count toggle in V0.5+)
6. **Latest transactions**: count + quick link to full list.
7. **Monthly wrap** card (first 5 days of month). — **V1+**

### 6.10 Insights
Analysis playground.

**Layout**: Desktop: split view (charts + transactions side-by-side). Mobile: charts first, then transactions.

**Filters** (global, apply to charts and list):
- Time: this week/last week, this month/last month, month picker, YTD. Quarter picker added in V1.
- Spender, category, merchant, tag, payment method. Beneficiary filter added in V1.

**Charts (MVP)**: spending trend line, category distribution pie, merchant leaderboard (amount), spender breakdown.

**Charts (V1+)**: category bar comparison (current vs 3-month avg), limit progress bars.

**Drill-down** (V1+): clicking chart elements filters the transaction list.

**Share** (V0.5+): "Share" button copies a URL with encoded filter state.

### 6.11 Monthly wrap (V1+, non-AI)
- **Trigger**: shown on first login of a month (or within first 5 days).
- **Pre-computed** for instant display.
- **Eligibility**: only generated for **active spaces** — spaces with **≥10 confirmed expenses** in the previous month. Inactive/abandoned spaces are skipped.
- **Content**: best category improvements, worst spikes, frequently breached limits, rule-based recommendations (propose limit adjustments based on history).

---

## 7) User stories & use cases

### Core use cases
1. As a user, I can add a quick grocery expense in <10 seconds.
2. As a user, I can split a mixed basket (groceries + shampoo for B) and assign beneficiaries.
3. As a couple, we can see total groceries and who paid and who benefited.
4. As a user, I can set weekly/monthly/quarterly/yearly limits and get warned when near or over.
5. As a user, I can see spending trends vs normal (3-month average).
6. As a user, I can view top merchants and identify "problem merchants".
7. As a user, I can create recurring items and confirm them when they appear.
8. As a user, I can use tags like `#vacation` to see cross-category spend.
9. As a user, I can share an Insights view link with my partner.
10. As a user, I can edit any field of a past expense, including its date.
11. As a user, I can see a hero "total spent" number with a comparison to my 3-month average.

### Edge cases
- Logging late: purchase date determines where it counts.
- Merchant used for multiple purposes: latest category suggestion may be wrong; user overrides.
- Split sums mismatch: UI blocks saving until fixed.
- Pending recurring accumulating: Home surfaces them without being invasive; nav badge shows count.
- Hard delete mistakes: "Are you sure?" dialog, no recovery.
- Category deletion: orphaned expenses become "Uncategorized".
- Payment method deletion: historical expenses show "Deleted method" (frontend resolves NULL).
- Editing purchase date: limits recalculate; expense may move to a different time window.
- Recurring backfill: missed scheduled dates generate all missed pending entries (idempotent).

---

## 8) Pages / views (UI requirements)

### 8.0 Navigation
- **Landing page**: public page for unauthenticated visitors. Authenticated users redirect to Home.
- **Mobile**: bottom tab bar with centered FAB (floating action button) for "Add Expense".
  - Tabs: Home, Transactions, [FAB: Add], Insights, Settings.
  - Recurring and Limits accessible as sub-views.
  - Recurring shows a **count badge** when pending items exist.
- **Desktop**: left sidebar navigation; "Add Expense" as a prominent button.

### 8.1 Auth
- Google SSO sign-in / sign-up page.
- Session persistence.

### 8.2 Onboarding
- Create shared space (name, currency, timezone, default tax %, seed categories).
- Invite partner (copy invite link).

### 8.3 Home
- Hero total + delta vs average.
- Week/Month toggle.
- Alerts, pending recurring, graph cards, latest transactions, monthly wrap.

### 8.4 Add Expense
- **Modal** for single-line expenses (MVP).
- **Full page** when "Split" is toggled (V1).
- **MVP fields**: merchant (autocomplete), datetime (default = now), spender (default = self), payment method (dropdown), category (auto-suggested), amount, tags (`#`-triggered), notes.
- **V1 adds**: beneficiary (default = Shared), split editor, colored payment method chips.
- **V1.5 adds**: total/pre-tax toggle.

### 8.5 Transaction list
- **Grouped by date** (Today, Yesterday, This Week, Earlier…). Within each group, sorted by `purchase_datetime DESC`, then `created_at DESC` as tiebreaker.
- **Infinite scroll**.
- Filters (same as Insights).
- Search by merchant/notes/tags.

### 8.6 Expense detail
- All fields displayed (purchase datetime, created datetime, merchant, spender, payment method, notes, split lines with categories/tags).
- V1 adds: beneficiary per line, payment method color.
- Edit button (all fields editable).
- Delete button ("Are you sure?" dialog).

### 8.7 Insights
- Global filters, chart area, transaction list, share button, drill-down.

### 8.8 Limits
- List with progress bars, create/edit form, progress + warnings + days remaining.

### 8.9 Recurring
- Template list (active/inactive toggle), create/edit form, pending items with confirm/edit/deny, nav badge.

### 8.10 Settings
- Space name (editable), currency (display only), timezone, default tax %, members list (display only, no removal), invite link management, categories CRUD, payment methods management (per-member).

---

## 9) Core flows (step-by-step)

### 9.1 Create space + invite partner
1. User clicks "Sign in with Google" → authenticated
2. First-time user → onboarding: creates shared space (name, currency, timezone)
3. Optionally seeds default categories
4. Clicks "Invite partner" → link generated (single-use, 7-day expiry)
5. Partner opens link → Google sign-in → added to space → link invalidated

### 9.2 Add an expense (single-line) — MVP
1. Tap FAB / "Add expense" → modal opens
2. Enter merchant (autocomplete suggests prior merchants)
3. Category auto-selects from latest mapping
4. Spender defaults to logged-in user
5. Enter amount
6. Optionally add payment method, tags, notes
7. Save → modal closes, data refreshes

### 9.3 Add an expense (split) — V1
1. Start as single-line (modal)
2. Toggle "Split purchase" → expands to full page
3. Enter purchase header
4. Add 2+ split lines (amount, category, beneficiary, tags)
5. Running sum shown; **save blocked** until sum matches total
6. Save

### 9.4 Recurring pending confirmation — V0.5+
1. Pending entries generated daily by automated job
2. Home shows pending card; nav badge shows count
3. User taps pending item: confirm / edit+confirm / deny

### 9.5 Limit warning
1. Expense saved → affected limits recalculated
2. 80% → warning; 100% → alert
3. Home shows alert card (up to 2–3)
4. Click alert → Insights filtered to that limit's criteria

### 9.6 Share Insights — V0.5+
1. Configure filters
2. Click "Share" → link copied with encoded filter state
3. Partner opens link → same Insights view

### 9.7 Edit expense
1. Open expense detail → click "Edit"
2. All fields editable
3. Save → limits recalculate if amount or date changed

### 9.8 Delete expense
1. Open expense detail → click "Delete"
2. "Are you sure?" dialog → confirm → hard delete → limits recalculate

---

## 10) Analytics definitions

### Time semantics
- **Purchase datetime** determines the time bucket.
- All time windows use the **space timezone**.
- Weekly: Monday 00:00 → Sunday 23:59. Monthly: calendar month. Quarterly: Jan–Mar, Apr–Jun, Jul–Sep, Oct–Dec. Yearly: calendar year.

### "3-month average"
- Compare cumulative spend by day-of-period vs average of prior 3 comparable periods.
- If fewer than 3 prior periods exist, use as many as available.

### Hero total + delta
- Total = sum of confirmed expenses in selected window.
- Delta = `((total - average) / average) × 100` → "+X%" or "-X% vs avg".
- If no prior data, delta is not shown.

### Limit progress
- Spent = sum of confirmed expenses matching limit filters in current window.
- Progress = spent / threshold.
- Warning at progress ≥ warning_pct; alert at progress ≥ 1.0.
- Days remaining = end of window - today.

### Merchant leaderboard
- By amount: sum per merchant (case-insensitive grouping).
- By count: count of purchases per merchant.
- Optional change: current vs previous comparable window.

### Spender breakdown
- Group totals by spender within the selected window.

---

## 11) Acceptance criteria (what "done" looks like)

### MVP (V0.1) is complete when:
- Google SSO sign in/sign up with session persistence
- Create shared space (name, currency, timezone) + invite link join (single-use, 7-day expiry)
- Add/edit/delete single-line expenses (all fields editable post-creation)
- Merchant autocomplete + merchant → category auto-suggestion
- Spender (defaults to self) on every expense
- Payment methods with labels (Cash + member-created, no custom colors)
- Tags with `#`-triggered autocomplete and normalization
- Home dashboard with hero total + delta, week/month toggle, alerts, trend line, category pie, merchant leaderboard (amount), latest transactions
- Insights with filters, trend line, category pie, merchant leaderboard, spender breakdown
- Limits (weekly/monthly, category filter only) with 80% warning + 100% alert on Home
- Transaction list grouped by date with infinite scroll
- Categories with "Uncategorized" system fallback
- Currency-aware formatting
- Auto-refetch every 2 minutes when page active
- Hard delete with confirmation dialog
- Health check endpoint
- Rate limiting

### V0.5 adds:
- Recurring templates generating pending instances with confirm/edit/deny
- Pending expenses surfaced on Home + nav badge count
- Shareable Insights links (URL-encoded filter state)
- Merchant leaderboard Amount/Count toggle

### V1 adds:
- Split purchases with multiple lines
- Beneficiary field (member or Shared) on expense lines
- Monthly wrap card (pre-computed, rule-based)
- Quarterly/yearly timeframes for limits and recurring
- Full limit filter set (category, merchant, tag, spender, beneficiary, payment method)
- Payment method colors and colored chip display
- Insights drill-down, limit progress bars, category bar comparison
- i18n-ready architecture (English only)

### V1.5 adds:
- Tax convenience calculator
- Spanish translations, locale-aware formatting

---

## 12) Appendix — recommended default categories (optional)
Provide an onboarding option to seed defaults (users can edit/delete):
- Groceries
- Dining Out
- Rent
- Utilities
- Transportation
- Health
- Personal Care
- Entertainment
- Travel
- Gifts
- Subscriptions
