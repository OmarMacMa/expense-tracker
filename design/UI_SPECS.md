# UI Specifications

This document defines the **visual layout and component placement** for each view in the app, organized by version. For functional requirements see `PRD.md`. For version scope see `SCOPE.md`.

Design system: **shadcn/ui + Tailwind CSS**, with **Material Design 3 (M3) as visual inspiration** — adopt M3's rounded shapes, tonal surfaces, and component patterns (FAB, segmented buttons, card elevation via tone shifts) while using shadcn/ui's copy-paste React components and Tailwind for implementation. Charts: **Recharts**. Light mode only (dark mode in V2).

### Design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Font** | Ubuntu (Google Fonts) | Distinctive, rounded, warm techy feel. Readable at all sizes. |
| **Icons** | Lucide | shadcn/ui default. Clean outlined style. Lightweight. |
| **Boundaries** | Tonal surface shifts only | No 1px borders. Define card boundaries through background color contrast (`#FFFFFF` cards on `#F3F1F8` surface). Simpler to implement than hybrid approach. |
| **Elevation** | M3 solid tonal surfaces | No glassmorphism. Solid backgrounds maintain clarity for financial data. |
| **Buttons** | Solid fill (M3 standard) | No gradients. Primary uses `primary` color with `on-primary` text. |
| **Spacing** | Symmetric everywhere | No asymmetric margins. Predictable, responsive-friendly. |
| **Amounts** | Positive numbers only | No minus signs. Everything is an expense (income tracking deferred to V2). |
| **Category icons** | Colored chips only (MVP–V1) | No icons on categories until V1.5. Categories identified by name + chip color. V1.5 adds user-selectable Lucide icons per category. |
| **Card elevation** | Subtle ambient shadow | Cards use light multi-layer shadow (`0 2px 12px rgba(29,27,32,0.04), 0 6px 24px rgba(29,27,32,0.03)`) on top of tonal shift for gentle float effect. |
| **Content centering** | Centered with max-width | Main content area centered within available space (`max-width: 1100px`), not left-aligned. Prevents dead zones on wide monitors. |

### Responsive breakpoints

| Breakpoint | Layout | Navigation | Content |
|------------|--------|------------|---------|
| `<768px` | Mobile | Bottom tab bar + FAB | Single column, stacked cards |
| `768–1024px` | Tablet vertical | Sidebar (narrower, 220px) | Single column (charts stack) |
| `1024–1280px` | Small desktop | Full sidebar (248px) | 2-column grid for charts |
| `1280px+` | Desktop | Full sidebar (248px) | 2-column grid, centered max-width |

Tablet horizontal uses the desktop experience. Browser split-view gracefully collapses to the appropriate breakpoint.

### Color palette — Cool Lavender + Sage

**Primary group** (brand, FAB, active nav, main CTAs):
| Token | Value | Usage |
|-------|-------|-------|
| `primary` | `#7C6FA0` | FAB, active nav, primary buttons, links |
| `on-primary` | `#FFFFFF` | Text/icons on primary |
| `primary-container` | `#E9DDFF` | Active nav pill fill, selected states, transport category chips |
| `on-primary-container` | `#32264E` | Text on primary-container |

**Secondary group** (category chips, secondary actions):
| Token | Value | Usage |
|-------|-------|-------|
| `secondary` | `#8BA89A` | Secondary actions, sage accent |
| `on-secondary` | `#FFFFFF` | Text on secondary |
| `secondary-container` | `#D4E8DD` | Groceries/health category chips |
| `on-secondary-container` | `#2E4A3D` | Text on secondary-container |

**Tertiary group** (accent variety):
| Token | Value | Usage |
|-------|-------|-------|
| `tertiary` | `#A0889C` | Tertiary accent |
| `on-tertiary` | `#FFFFFF` | Text on tertiary |
| `tertiary-container` | `#F2DDE9` | Dining/entertainment category chips |
| `on-tertiary-container` | `#4A3346` | Text on tertiary-container |

**Extended — Butter** (4th category chip color):
| Token | Value | Usage |
|-------|-------|-------|
| `butter` | `#B5A24A` | Butter accent |
| `butter-container` | `#F5EDCF` | Shopping/subscriptions category chips |
| `on-butter-container` | `#4A4220` | Text on butter-container |

**Surface group** (backgrounds, cards, containers):
| Token | Value | Usage |
|-------|-------|-------|
| `background` | `#FAFAFE` | Page background (the "desk") |
| `surface` | `#F3F1F8` | Section backgrounds, toggle tracks, bottom nav, progress bar tracks |
| `surface-container` | `#FFFFFF` | Cards (sit on surface via tonal shift) |
| `on-surface` | `#1D1B20` | Primary text (never pure `#000000`) |
| `on-surface-variant` | `#615D69` | Secondary text, labels, placeholders |
| `outline` | `rgba(124, 120, 133, 0.15)` | Ghost borders if accessibility requires (felt, not seen) |

**Category chip color cycling**: categories are assigned one of 4 container colors in order: sage → dusty rose → lavender → butter → repeat. The mapping is deterministic based on category creation order within a space.

### Semantic status colors

A consistent color system is used across all status indicators (limit progress, spending delta, alert cards):

| State | Color | Tailwind tokens | Used for |
|-------|-------|-----------------|----------|
| **Healthy** | Green | `text-green-600`, `bg-green-100`, `border-green-200` | Limit progress < user's `warning_pct`; delta badge when spending is below average (↓) |
| **Warning** | Amber | `text-amber-600`, `bg-amber-100`, `border-amber-200` | Limit progress ≥ user's `warning_pct` and < 90% |
| **Critical** | Red | `text-red-600`, `bg-red-100`, `border-red-200` | Limit progress ≥ 90% and ≤ 100%; delta badge when spending is above average (↑) |
| **Exceeded** | Purple | `text-[#2E064F]`, `bg-purple-100`, `border-purple-200` | Limit progress > 100% (overflow) |
| **Neutral** | Gray | `text-gray-500`, `bg-gray-100` | Delta badge hidden or no comparison data available |

**Limit color thresholds** are driven by a **per-limit configurable `warning_pct`** (default: 60%):
- < `warning_pct` → green (healthy)
- ≥ `warning_pct` and < 90% → amber (warning)
- ≥ 90% and ≤ 100% → red (critical)
- > 100% → purple (exceeded/overflow)

**Application rules:**
- **Limit alert cards** (Home): hidden when healthy (< `warning_pct`). Show on Home only at warning (amber), critical (red), or exceeded (purple). Progress bar fill color matches the state.
- **Limit list view** (`/limits`): all limits shown regardless of state. Progress bar uses green / amber / red / purple based on the limit's `warning_pct` and the fixed 90% critical threshold.
- **Delta badge** (Home hero): green + ↓ arrow when below 3-month average, red + ↑ arrow when above. Hidden entirely when no prior data exists.
- **Color is never the sole indicator** — always paired with text labels, percentages, or icons (accessibility requirement).

---

## Global shell

### Mobile (<768px)

**Top bar** (present on all views):

```
| SpaceSelector  |  (camera notch)  |  Avatar |
```

- **Space selector** (top-left): dropdown to switch spaces. Only visible if user belongs to >1 space.
- Center gap respects the phone's **camera notch / Dynamic Island**.
- **Avatar** (top-right): user profile icon/photo. Tapping opens a profile menu with: **Settings** link, **Sign out** action.

**Bottom tab bar** (fixed at bottom, all views):

MVP:
```
| Home | Transactions | [FAB: +] | Limits | Insights |
```

V0.5+:
```
| Home | Recurring | [FAB: +] | Limits | Insights |
```

- FAB is a raised circular button for "Add Expense" — visually elevated above the tab bar.
- **MVP**: Transactions tab links to `/transactions`. Replaced by Recurring in V0.5+.
- **V0.5+**: Recurring tab links to `/recurring` and shows a badge with pending count. Transactions accessible from Home "View all →" link and within Insights.
- **Settings** is accessed from the avatar profile menu (top-right), not from the tab bar.
- Active tab highlighted with fill or underline.

### Desktop (≥768px)

**Left sidebar** (fixed, full height):

MVP:
```
┌──────────────────────┐
│  Logo / App Name     │
│                      │
│  [+ Add Expense]     │  ← prominent primary button
│                      │
│  🏠 Home             │
│  📋 Transactions     │
│  🎯 Limits           │
│  📊 Insights         │
│                      │
│  (spacer)            │
│                      │
│  ⚙️ Settings         │  ← settings link at bottom
│  👤 User Name        │  ← avatar + name, sign out menu
└──────────────────────┘
```

V0.5+:
```
┌──────────────────────┐
│  Logo / App Name     │
│                      │
│  [+ Add Expense]     │  ← prominent primary button
│                      │
│  🏠 Home             │
│  🔄 Recurring    [3] │  ← badge with pending count
│  🎯 Limits           │
│  📊 Insights         │
│                      │
│  (spacer)            │
│                      │
│  ⚙️ Settings         │
│  👤 User Name        │  ← avatar + name, sign out menu
└──────────────────────┘
```

- "+ Add Expense" must be prominently visible at all times.
- Space selector (top of sidebar or next to logo) only visible if user belongs to >1 space.
- **MVP nav links**: Home, Transactions, Limits, Insights, Settings.
- **V0.5+ nav links**: Home, Recurring (with pending badge), Limits, Insights, Settings. Transactions accessible from Home "View all →" and within Insights.
- Active item highlighted.

### Version additions
- **V0.5**: Recurring replaces Transactions in bottom tab bar; pending count badge. Transactions accessible from Home and Insights.
- **V2**: dark mode toggle in settings; PWA "Add to Home Screen" prompt.

---

## 1. Landing page (`/`)

Public page for unauthenticated visitors. Authenticated users redirect to `/home`.

### MVP
- Product name/logo, value proposition tagline.
- "Sign in with Google" button (primary CTA).
- Brief feature highlights (2–3 bullet points or cards).

---

## 2. Auth (`/auth/callback`)

### MVP
- Google OAuth callback handler. Loading spinner while processing.
- Redirects to `/onboarding` (new user) or `/home` (existing user with space).

---

## 3. Onboarding (`/onboarding`)

### MVP
- Step-by-step form or single form:
  1. Space name (text input).
  2. Currency (select, locked after creation).
  3. Timezone (select).
  4. Default tax % (number input, optional).
  5. Seed categories (checkboxes with recommended defaults, optional).
- "Create Space" primary button.
- After creation: invite partner section with "Copy Invite Link" button.

---

## 4. Home dashboard (`/home`)

### Top area layout (mobile)

```
| SpaceSelector  |  (camera notch)  |       Avatar |
|                |                  | Week | Month |
| $3,247.50      |                  |              |
| ↑12% vs avg   |                  |              |
```

- The top row respects the phone's **camera notch / Dynamic Island** — space selector sits left of it, avatar sits right.
- **Week / Month toggle** (top-right, below avatar): pill-style toggle. Controls the time window for the entire page.
- **Hero total** (left-aligned, large): currency-formatted total spent for the selected window.
- **Delta badge** (below hero total): percentage vs 3-month average. Green with ↓ arrow if under average, red/orange with ↑ arrow if over. Hidden if no prior data exists.

### MVP sections (top to bottom, scrollable)

1. **Hero + toggle** (described above).

2. **Limit alert cards** (2–3 max):
   - Each card: limit name + percentage (e.g., "Groceries at 92%"), progress bar, spent vs threshold (e.g., "$368 / $400").
   - **Warning** (≥ user's `warning_pct`): amber bar and text.
   - **Critical** (≥90%): red bar and text.
   - **Exceeded** (>100%): purple bar and text with "Exceeded" label.
   - Hidden entirely if no limits are at warning or above.
   - Tapping a card navigates to Insights filtered by that limit's criteria.

3. **Spending trend line chart**:
   - Cumulative line chart, two lines:
     - **Solid line**: current period's cumulative spend day-by-day.
     - **Dashed/lighter line**: 3-month average cumulative spend.
   - X-axis: days in the period (1–7 for week, 1–28/31 for month).
   - Y-axis: cumulative dollar amount.
   - Subtle grid, clean axis labels.

4. **Category donut chart**:
   - Donut/pie chart showing spend breakdown by category.
   - Legend with category name + percentage (or amount).
   - Distinct but harmonious color palette.

5. **Merchant leaderboard**:
   - Ranked list of top 5 merchants by total amount.
   - Each row: rank, merchant name, total amount.
   - Clean rows with subtle separators.

6. **Latest transactions**:
   - Header with count (e.g., "12 transactions this week").
   - Preview of last 3–5 transactions: merchant, amount, category badge, relative date (Today, Yesterday, etc.).
   - "View all →" link to `/transactions`.

### Responsive behavior
- **Mobile**: all sections stack vertically in single-column scroll.
- **Desktop**: charts can sit in a 2-column grid (e.g., trend line + donut side by side). Leaderboard and latest transactions below.

### V0.5 additions
- **Pending recurring card** (between limit alerts and charts): shows pending items with confirm ✅ / edit ✏️ / deny ✖️ actions. Merchant name + amount per row.
- **Merchant leaderboard**: Amount / Count toggle.

### V1 additions
- **Monthly wrap card** (top of page, first 5 days of month only): highlights from pre-computed monthly analysis — improvements, spikes, recommendations. Dismissible.
- Limit progress bars **move to Insights**; Home keeps only the alert cards.
- Category bar comparison (current vs 3-month avg) **moves to Insights**.

### V2 additions
- **Pin chart to Home**: user-customizable dashboard cards.

---

## 5. Add Expense (`/expenses/new`)

### MVP — Full page (single-line)
- Triggered by FAB (mobile) or "+ Add Expense" button (desktop). Navigates to `/expenses/new`.
- **Fields** (top to bottom):
  1. Amount (number input, currency-formatted).
  2. Merchant (text input with autocomplete from prior merchants).
  3. Category (dropdown, auto-suggested from merchant's latest category).
  4. Purchase datetime (date+time picker, defaults to now, no future dates).
  5. Spender (dropdown of space members, defaults to logged-in user).
  6. Payment method (dropdown, cross-member selection).
  7. Tags (text input with `#`-triggered inline autocomplete, Obsidian-style).
  8. Notes (text area).
- **Actions**: "Save" primary button, "Cancel" / back navigation.
- On save: navigates back to previous page; data refreshes in background.

### V1 additions — Split purchase
- "Split" toggle appears next to Amount field (pill-style, off by default).
- Toggling on reveals split line editor below: each line has amount + category + beneficiary + tags.
- "Add line" button appends rows. Running sum shown; save blocked until sum matches total.
- Toggling off collapses back to single-line (clears extra lines with confirmation if data entered).
- Beneficiary field per line (default: Shared).
- Colored payment method chips.

### V1.5 additions
- Total / Pre-tax toggle with tax calculator using space default tax %.

---

## 6. Transaction list (`/transactions`)

### MVP
- **Search bar** (top): search by merchant, notes, tags (case-insensitive contains).
- **Filter bar**: time window, spender, category, merchant, tag, payment method.
- **Grouped list**:
  - Groups: Today, Yesterday, This Week, Earlier.
  - Within group: sorted by purchase datetime DESC, then created_at DESC.
  - Each row: merchant, amount, category badge, spender, relative date.
- **Infinite scroll** (cursor-based, 20 items per page).
- Tapping a row opens expense detail.

### V1 additions
- Beneficiary filter.

---

## 7. Expense detail (`/transactions/:id`)

### MVP
- All fields displayed: merchant, amount, category, purchase datetime, created datetime, spender, payment method, tags, notes.
- **Edit button** → opens editable form (all fields editable, including purchase date).
- **Delete button** → "Are you sure?" confirmation dialog. Hard delete.

### V1 additions
- Beneficiary per line.
- Payment method color chip.
- Split lines displayed with per-line category, amount, tags.

---

## 8. Insights (`/insights`)

### MVP

**Layout**:
- Desktop: split view — charts (left) + transaction list (right) side by side.
- Mobile: charts first (scrollable), then transaction list below.

**Filter bar** (top, applies to all charts + list):
- Time presets: This Week, Last Week, This Month, Last Month, Month Picker, YTD.
- Spender, category, merchant, tag, payment method.

**Charts**:
1. Spending trend line (same as Home: cumulative, current vs 3-month avg).
2. Category distribution pie/donut.
3. Merchant leaderboard (by amount).
4. Spender breakdown (bar or pie, totals per spender).

**Transaction list**: same component as `/transactions` but filtered by Insights filters.

### V0.5 additions
- **Share button**: copies URL with encoded filter state.

### V1 additions
- **Drill-down**: clicking chart elements filters the transaction list.
- **Limit progress bars**: moved from Home, shown as progress indicators.
- **Category bar comparison**: current period vs 3-month average per category.
- Quarter picker time preset.
- Beneficiary filter.

---

## 9. Limits (`/limits`)

### MVP
- **List view**: all limits with progress bar, spent vs threshold, days remaining, warning/alert state.
- **Create / Edit form** (modal or inline):
  - Name, threshold amount, timeframe (Weekly / Monthly), category filter.
  - Warning threshold % (default: 60%) — at what percentage of the threshold to start showing warnings.
- **Delete**: confirmation dialog.
- Only confirmed expenses count toward limits.

### V1 additions
- Timeframes: Quarterly, Yearly.
- Expanded filters: merchant, tag, spender, beneficiary, payment method.

---

## 10. Settings (`/settings`)

### MVP
Hub-and-spoke navigation layout. Top section shows space info inline; below is a navigation list of drill-down sub-pages. Each item is a card/row with a `>` chevron.

**Top section (inline):**
- **Space info**: space name (editable), currency (display only), timezone (editable).

**Navigation list (each opens a sub-page):**
- **Categories >**: CRUD list. "Uncategorized" shown but not editable/deletable. Deletion shows warning about reassignment.
- **Payment Methods >**: per-member list. Built-in "Cash" (non-deletable). Create/delete own methods (label only).
- **Tags >**: list of all tags used in the space (read-only view for awareness; tags are auto-created on first use).
- **Members >**: list of members (display only, no removal). Member count shown (max 10).
- **Invite >**: generate invite link (single-use, 7-day expiry), disable active link.
- **Taxes >**: default tax % (editable).

### V0.5 additions
- **Recurring Expenses >**: shortcut to `/recurring` template management.

### V1 additions
- Payment method custom colors (hex picker + preview chip).

### V1.5 additions
- Language selector (English / Spanish).
- Category icon picker (searchable Lucide icon grid in category create/edit form).

### V2 additions
- Dark mode toggle.
- Data export (CSV).

---

## 11. Join Space (`/join/:token`)

### MVP
- Displays space name from invite token.
- "Join with Google" button → Google sign-in → added to space → redirect to `/home`.
- Error states: expired link, already-used link, space full (10 members).

---

## 12. Recurring (`/recurring`) — V0.5+

### V0.5
- **Template list**: active/inactive toggle per template. Each row: name, schedule (weekly/monthly), default amount, category.
- **Create / Edit form**: name, schedule, default merchant, amount, category, payment method, tags.
- **Pending items**: list of generated pending expenses. Each row: merchant, amount, due date, with confirm ✅ / edit ✏️ / deny ✖️ actions.

### V1 additions
- Schedules: Quarterly, Yearly.
- Beneficiary field on templates.
