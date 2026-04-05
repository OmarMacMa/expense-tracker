# UX Review — One Month as a Daily User

*Reviewed by a staff engineer who's been splitting groceries, dinners, and subscriptions with their partner for 30 days.*

---

## 1. Expense Entry Experience

### The daily ritual: "We just paid — log it now"

When I tried to log a quick coffee purchase from the FAB button on mobile, the flow was:  
**Tap FAB → land on form → type amount → type merchant → pick category → hit Save**. That's **4 distinct interactions** minimum (amount, merchant, category, save). On a good day, with merchant autocomplete kicking in and the category auto-suggestion from `useMerchantCategory`, it drops to **3 taps + 1 blur** — genuinely fast. The hero amount input is smart (`add-expense.tsx:334-351`): the big formatted number at the top gives immediate visual feedback.

**But here's what trips me up daily:**

- **Merchant autocomplete requires `onBlur` to confirm.** I noticed (`add-expense.tsx:376-378`) that when I type a new merchant name and directly scroll down to tap Category, the `onBlur` fires a 200ms `setTimeout` then sets `merchant = merchantQuery`. This works, but on slower phones I've occasionally had the merchant field blank out because the blur/focus race with the dropdown was too fast. The fact that there are *two* state variables (`merchant` and `merchantQuery`) tracking essentially the same thing is fragile — if I type "Costco" and immediately hit Save before the blur fires, `merchant` might still be empty while `merchantQuery` has my text.

- **Category is required (red asterisk) but the form doesn't validate it.** Looking at `handleSubmit` (`add-expense.tsx:262-293`), the only validation is `amount > 0`. I can submit with `category_id: null` — the button disables only on missing amount. The UI says it's required (the `*` label) but the code says otherwise. As a user, I'd either get a silent server error or an uncategorized expense.

- **No "Save & Add Another" button.** After logging a grocery run with 3 different stops, I noticed I get redirected to `/transactions` after each save (`add-expense.tsx:278`). I have to tap the FAB again, wait for the page to mount, re-enter a new expense. A "Save & Add Another" would cut my grocery-day logging time in half.

- **Tag entry is confusing.** The placeholder says "Type # to add tags..." but the dropdown only opens when `tagInput.startsWith('#')` (`add-expense.tsx:170-174`). If I type "grocery" (without `#`), nothing happens until I hit Enter, at which point it strips `#` and adds it. The dual behavior — sometimes needs `#`, sometimes doesn't — is unintuitive. In a month of use, I just started always typing `#` and pressing Enter.

- **No receipt photo support.** Every other expense app I've used lets me snap a receipt photo. I know this is MVP, but it feels like a gap that a real user would notice on Day 1.

### Edit experience

When I tried to fix a typo on an expense, I navigated to the detail view (click transaction item → expense-detail), then hit the Edit button. The `ExpenseEditMode` component (`expense-detail.tsx:308-939`) is essentially a copy of the entire add-expense form — **~600 lines of duplicated logic** including merchant autocomplete, tag input, date picker, all the keyboard handlers. They behave identically. If a bug is fixed in one, the other stays broken.

The good news: editing works. Form state initializes from the existing expense, Save commits a PATCH, cancel returns to view mode. The `key={expense.updated_at}` on `ExpenseEditMode` (`expense-detail.tsx:1028`) is a nice touch — it force-remounts the form if the expense is updated externally.

**Pain points:**
- There's no inline editing — I have to enter full edit mode to change the category. For a "wrong category" fix, that's heavy.
- The edit form doesn't re-apply merchant → category suggestion. In `ExpenseEditMode`, the `useMerchantCategory` hook isn't used at all (`expense-detail.tsx:360` only uses `useMerchantSuggest`, not `useMerchantCategory`). The suggestion feature only works on new expenses.

---

## 2. Transaction List & Search

### Finding that one expense

When I tried to find a specific restaurant expense from last week, I used the search bar in `FilterBar` (`filter-bar.tsx:65-74`). The search is a simple text filter passed as `?search=` to the API. It searches merchants, notes, and tags — this is actually quite useful.

**What works well:**
- Date groups (Today / Yesterday / This Week / Earlier) in `transaction-group.tsx` are genuinely helpful. After a month, I instinctively look at "Today" first.
- Infinite scroll uses `IntersectionObserver` with `rootMargin: '200px'` (`transaction-list.tsx:83-84`), which pre-fetches before I hit bottom. It feels smooth.
- The `TransactionItem` component (`transaction-item.tsx`) is clean — merchant initial circle, category badge, amount, spender name, relative date. All at a glance.

**What's frustrating:**

- **No date range filter.** The transaction list's `FilterBar` is called with no props for spenders, categories, merchants, tags, or payment methods (`transaction-list.tsx:106`). It's just a search box. Compare this to the Insights page (`insights.tsx:182-192`) which passes all filter data sources. The transaction list is missing the most basic filter I'd want: "show me everything from last month."

- **No running total per group.** The "Today" group doesn't tell me how much I spent today. `TransactionGroup` (`transaction-group.tsx:30-43`) renders the label and a list of items, but no sum. I'd love to see "Today — $127.50" at a glance.

- **Count is misleading.** The "X transactions" count (`transaction-list.tsx:98-100`) shows `allExpenses.length`, which is only the *loaded* pages, not the total. If I have 200 transactions but only 20 are loaded, it says "20 transactions." This should come from a server-side total count.

- **No sort options.** Transactions are presumably sorted by `purchase_datetime` DESC from the API, but there's no way to sort by amount, merchant, or category. When I'm trying to find my biggest expense, I can't.

---

## 3. Dashboard & Insights

### Does the hero number tell me something useful?

**Yes.** The hero strip on Home (`home.tsx:135-189`) shows total spent + delta vs average. "↑ 12.3% vs avg" in red immediately tells me I'm spending more. The Week/Month toggle is natural — two pill buttons, visually obvious.

**The spending trend chart** (`spending-trend-chart.tsx`) shows current period vs 3-month average as a cumulative line. This is the most useful chart — I can see if I'm "on pace" to overspend by comparing the solid line (current) to the dashed line (average). The tooltip shows exact values on hover.

**Issues I noticed:**

- **Home page fires 6 parallel API requests.** (`home.tsx:103-116`) — summary, trend, categories, merchants, limits, expenses. On mobile with slow connections, this means the dashboard is a skeleton fest for 2-3 seconds. There's no progressive rendering strategy — everything loads independently.

- **The "Latest Transactions" section on Home is limited to 5.** This is fine, but it uses `useExpenseList` with the period filter, which fetches a full page of 20 from the API just to show 5. That's wasted bandwidth.

- **Budget alerts only show top 3** (`home.tsx:203: alertLimits.slice(0, 3)`). If I have 4 limits in warning state, I only see 3 with no "see more" link.

- **Category donut chart only has 5 colors** (`category-donut-chart.tsx:11-17`). If I have 8+ categories (which I do — Groceries, Dining, Transport, Entertainment, Subscriptions, Healthcare, Shopping, Utilities), colors repeat. Categories 6-8 use the same colors as 1-3, making the chart confusing.

- **No tooltip on the donut chart.** Unlike the trend chart, the donut uses raw Recharts `Pie` with no `Tooltip` component. I can't hover/tap a slice to see the exact amount — I have to read the legend.

- **Insights page vs Home overlap.** The Insights page (`insights.tsx`) has all the same charts as Home *plus* a spender breakdown and a full transaction list. It's unclear why both pages exist. As a user, I started going exclusively to Insights because it has everything Home has, plus more.

### "Where did our money go?"

The Insights page answers this well: category donut, merchant leaderboard, spender breakdown, and a filterable transaction list all in one view. The filter bar with period chips (`filter-bar.tsx:77-99`) lets me quickly switch between This Week / Last Week / This Month / Last Month / YTD.

**Missing insight: comparison view.** I often want to answer "Did we spend more on dining this month vs last month?" There's no way to compare two periods side-by-side. The delta percentage on the summary is "vs average," not "vs last period."

---

## 4. Settings & Onboarding

### Onboarding

When I tried the onboarding flow, it was straightforward: name your space, pick currency, timezone, optional tax rate, seed default categories. The timezone picker detects my browser timezone (`onboarding.tsx:132-138`), which is smart.

**Issues:**
- **Currency warning is easy to miss.** The "Currency cannot be changed after creation" note (`onboarding.tsx:253`) is just a small gray `text-xs` line. This is a **permanent, irreversible decision** buried in fine print. If my partner and I are in a cross-border situation, picking the wrong currency is catastrophic.

- **The invite flow after space creation is optional but feels mandatory.** The SuccessView (`onboarding.tsx:393-525`) prominently shows "Invite your partner" with a big generate button, but "Go to Dashboard" is at the very bottom. First-time users might think they *have* to invite someone before continuing.

- **The "Have an invite link?" section** (`onboarding.tsx:354-385`) uses a raw `<input>` instead of the design system's `<Input>` component. It looks visually inconsistent.

### Settings

When I tried to manage categories, the flow was clear: Settings → Categories → inline add/edit/delete. The `SettingsCategories` component (`categories.tsx`) handles system vs custom categories well — system categories show a "System" badge and can't be edited/deleted.

**Issues:**
- **No drag-to-reorder categories.** I want my most-used categories (Groceries, Dining) at the top of every dropdown. Right now they're in creation order.

- **Timezone editing in Settings is a raw text input** (`settings.tsx:188-200`). During onboarding, I got a nice grouped `<Select>` dropdown. In Settings, I have to type "America/New_York" from memory. There's not even validation — I could type "Pizza/Time" and it would submit.

- **Payment methods can't be renamed.** `SettingsPaymentMethods` (`payment-methods.tsx`) only supports add and delete. If I created "Visa ending 4242" and my card gets replaced, I have to delete it (which sets all expenses to null payment method) and create a new one. Renaming should be trivial.

- **Tags settings page is read-only.** `SettingsTags` (`tags.tsx:38-42`) shows an info banner: "Tags are automatically created when used on expenses. They cannot be manually added or removed here." So if I accidentally create a misspelled tag on an expense, there's no way to delete or rename it. Ever.

- **No Settings link on the mobile bottom nav.** `BottomNav` (`bottom-nav.tsx:5-11`) only has Home, Transactions, [FAB], Limits, Insights. Settings is accessible only through the avatar dropdown in `TopBar` (`top-bar.tsx:52-57`). This is a common pattern but it took me a week to discover Settings existed on mobile.

---

## 5. Navigation & UX Polish

### FAB (Floating Action Button)

The FAB on mobile (`bottom-nav.tsx:47-54`) is a centered `+` button elevated above the nav bar with a purple shadow. It links to `/expenses/new`. This is **the most important button in the app** and it's correctly prominent. The `-mt-7` pulls it above the bar nicely.

**Issue:** The FAB has no label — it's just a `+` icon. There's no `aria-label` on the Link component. Screen reader users get "link" with no context. On desktop, the sidebar's "Add Expense" button (`sidebar.tsx:62-70`) is properly labeled.

### Loading states

Loading states are consistent: skeleton loaders for lists/charts, spinner for full-page loads. The `TransactionListSkeleton` mimics the real item layout. Good.

**Issue:** There's no optimistic update. When I create an expense and it redirects to `/transactions`, there's a brief flash where the new expense isn't in the list yet (TanStack Query invalidates then refetches). The `useCreateExpense` hook (`useExpenses.ts:63-66`) calls `invalidateQueries` on success, which triggers a refetch, not an instant cache update.

### Toasts

Toasts use Sonner (`App.tsx:39`) positioned `top-right`. Expense CRUD shows success/error toasts (`useExpenses.ts:64, 70, 87, 90, 101, 105`). These appear at the right time.

**Issue:** Toasts are only on expense operations. There's no toast feedback for settings operations — creating a category, generating an invite link, updating tax rate. The `useCreateCategory`, `useUpdateSpace`, etc. hooks likely don't have toast calls (I can see `useCreateExpense` does, but the settings hooks just rely on inline state).

### Dead ends

- **`/join/:token` is a stub** (`join-space.tsx`): "Coming soon". If someone receives an invite link and clicks it, they land on a blank page. This is a broken flow.
- **No 404 route.** The `App.tsx` Routes don't have a catch-all `*` route. Navigating to `/nonexistent` shows a blank page.

---

## 6. Missing Features (User Expectations)

These aren't aspirational features — they're things that feel like **bugs or missing pieces** to a daily user:

1. **Join Space is completely broken** — the stub at `/join/:token` means the invite flow is non-functional. My partner literally cannot join our space.

2. **No duplicate detection.** I've accidentally logged the same Costco trip twice (once from my phone, once from my partner's). No warning.

3. **No expense status toggle.** Expenses have a `status` field ("confirmed" / "pending") visible in the detail view, but there's no UI to change it. It's display-only. The business rules say "only confirmed expenses count toward limits" — but I can't mark anything as pending or confirmed.

4. **No "today's summary" in the transaction list.** I have to mentally add up the "Today" group.

5. **No swipe-to-delete on mobile.** Every mobile expense app supports swipe gestures on transaction items.

6. **No keyboard shortcut to add expense on desktop.** There's a sidebar button, but no `Ctrl+N` or similar.

7. **Default tax rate is set but never applied.** The onboarding and settings let me set `default_tax_pct`, but the Add Expense form (`add-expense.tsx`) has no tax field or auto-calculation. The setting exists but does nothing in the UI.

8. **No currency formatting on amount input.** The amount field (`add-expense.tsx:343-351`) is a raw number input. I type "42.5" and the hero shows "$42.50", but the input itself doesn't format. On mobile, the number pad doesn't show `.` by default on all devices with `inputMode="decimal"`.

9. **The limit form hardcodes "$" in its threshold label** (`limit-form-dialog.tsx:178`): `Threshold ($)`. For EUR or MXN spaces, this is wrong.

10. **No bulk operations.** I can't select multiple transactions to delete, re-categorize, or tag.

---

## 7. Top 10 Improvements (Ordered by User Impact)

| # | Improvement | Why It Matters | Effort |
|---|-------------|---------------|--------|
| **1** | **Implement the Join Space flow** (`join-space.tsx` is a stub) | The app is designed for couples/families. Without this, you literally can't share a space. The entire multi-tenant model is broken for new users. | **Medium** |
| **2** | **Add "Save & Add Another" button on the expense form** | Power users (daily loggers) currently face a full page reload cycle between entries. This is the #1 friction in the daily logging loop. Add a second button that clears the form on success instead of navigating away. | **Small** |
| **3** | **Add full filter support to the Transaction List page** (period, category, spender, merchant, tag, payment method) | The transaction list has a search box but zero filter dropdowns. The Insights page already passes all the filter data sources to the same `FilterBar` component — the transaction list just doesn't. Wire up the same props. | **Small** |
| **4** | **Show running totals on date groups in the transaction list** | "Today — $127.50" gives instant awareness. Right now I have to mentally sum. Add a `group.expenses.reduce()` sum next to each group label in `TransactionGroup`. | **Small** |
| **5** | **Fix timezone editing in Settings to use the same `<Select>` as onboarding** | Currently a raw text input where users must type IANA timezone strings from memory. The onboarding page already has a beautiful grouped Select component with all timezones. Extract it and reuse. | **Small** |
| **6** | **Apply the default tax rate to the Add Expense form** | Users set a tax rate during onboarding that does absolutely nothing. Add a "Tax" row that auto-calculates based on `default_tax_pct` with the ability to override per-expense. | **Medium** |
| **7** | **Add a 404 catch-all route** and fix the `/join/:token` dead end | Navigating to any unknown URL shows a blank page. Add `<Route path="*" element={<NotFound />} />`. | **Small** |
| **8** | **Enable tag management (rename/delete) in Settings** | Misspelled tags are permanent — there's no way to fix or remove them. Add edit/delete to the Tags settings page, or at minimum a "merge tags" function. | **Medium** |
| **9** | **Extract the expense form into a shared component** to eliminate ~600 lines of duplication between `add-expense.tsx` and `expense-detail.tsx` | Not a user-visible change, but it directly affects user experience via consistency. Bugs fixed in the add form don't propagate to edit. The merchant→category suggestion works in add but not in edit. A shared `ExpenseForm` component fixes both. | **Medium** |
| **10** | **Expand the donut chart color palette and add tap/hover tooltips** | With 8+ categories, colors repeat and slices are unreadable. Add 10-12 distinct colors and a Recharts `Tooltip` on the Pie. | **Small** |

---

*End of review. TL;DR: The core add-expense → view-list → see-insights loop works well. The biggest gap is the broken invite/join flow that prevents the app's core use case (shared expenses). After that, the transaction list needs filters, the expense form needs "Save & Add Another", and several settings features are incomplete stubs. Fix these and the daily experience jumps from "acceptable prototype" to "app I actually want to use."*
