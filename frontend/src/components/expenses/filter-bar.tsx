import { Search, X } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import type { ExpenseFilters } from '@/hooks/useExpenses';
import { cn } from '@/lib/utils';

const PERIOD_OPTIONS = [
  { value: 'this_week', label: 'This Week' },
  { value: 'last_week', label: 'Last Week' },
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'ytd', label: 'YTD' },
];

interface FilterBarProps {
  filters: ExpenseFilters;
  onFiltersChange: (filters: ExpenseFilters) => void;
  spenders?: { id: string; display_name: string }[];
  categories?: { id: string; name: string }[];
  merchants?: string[];
  tags?: { id: string; name: string }[];
  paymentMethods?: { id: string; label: string }[];
  showSearch?: boolean;
  showPeriodChips?: boolean;
}

export function FilterBar({
  filters,
  onFiltersChange,
  spenders = [],
  categories = [],
  merchants = [],
  tags = [],
  paymentMethods = [],
  showSearch = true,
  showPeriodChips = false,
}: FilterBarProps) {
  const hasActiveFilters =
    filters.period ||
    filters.spender ||
    filters.category ||
    filters.search ||
    filters.merchant ||
    filters.tag ||
    filters.payment_method;

  const updateFilter = (key: keyof ExpenseFilters, value: string) => {
    onFiltersChange({ ...filters, [key]: value || undefined });
  };

  const resetFilters = () => {
    onFiltersChange({});
  };

  return (
    <div className="space-y-3">
      {/* Search bar */}
      {showSearch && (
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search merchants, notes, tags…"
            value={filters.search ?? ''}
            onChange={(e) => updateFilter('search', e.target.value)}
            className="h-11 rounded-xl border-none bg-secondary pl-10 text-sm shadow-none placeholder:text-muted-foreground/70 focus-visible:ring-1"
          />
        </div>
      )}

      {/* Period chips (pill buttons) */}
      {showPeriodChips && (
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 scrollbar-none">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() =>
                updateFilter(
                  'period',
                  filters.period === opt.value ? '' : opt.value,
                )
              }
              className={cn(
                'shrink-0 rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors',
                filters.period === opt.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:bg-secondary/80',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {/* Filter chips row */}
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 scrollbar-none">
        {/* Period (dropdown) — only when not using chips */}
        {!showPeriodChips && (
          <Select
            value={filters.period ?? ''}
            onValueChange={(v) => updateFilter('period', v)}
          >
            <SelectTrigger
              className={`shrink-0 rounded-full border-none px-3.5 py-1.5 text-[13px] font-medium shadow-none ${
                filters.period
                  ? 'bg-accent text-accent-foreground'
                  : 'bg-secondary text-muted-foreground'
              }`}
            >
              <SelectValue placeholder="Period" />
            </SelectTrigger>
            <SelectContent>
              {PERIOD_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Spender */}
        {spenders.length > 0 && (
          <Select
            value={filters.spender ?? ''}
            onValueChange={(v) => updateFilter('spender', v)}
          >
            <SelectTrigger
              className={`shrink-0 rounded-full border-none px-3.5 py-1.5 text-[13px] font-medium shadow-none ${
                filters.spender
                  ? 'bg-accent text-accent-foreground'
                  : 'bg-secondary text-muted-foreground'
              }`}
            >
              <SelectValue placeholder="Spender" />
            </SelectTrigger>
            <SelectContent>
              {spenders.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Category */}
        {categories.length > 0 && (
          <Select
            value={filters.category ?? ''}
            onValueChange={(v) => updateFilter('category', v)}
          >
            <SelectTrigger
              className={`shrink-0 rounded-full border-none px-3.5 py-1.5 text-[13px] font-medium shadow-none ${
                filters.category
                  ? 'bg-accent text-accent-foreground'
                  : 'bg-secondary text-muted-foreground'
              }`}
            >
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              {categories.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Merchant */}
        {merchants.length > 0 && (
          <Select
            value={filters.merchant ?? ''}
            onValueChange={(v) => updateFilter('merchant', v)}
          >
            <SelectTrigger
              className={`shrink-0 rounded-full border-none px-3.5 py-1.5 text-[13px] font-medium shadow-none ${
                filters.merchant
                  ? 'bg-accent text-accent-foreground'
                  : 'bg-secondary text-muted-foreground'
              }`}
            >
              <SelectValue placeholder="Merchant" />
            </SelectTrigger>
            <SelectContent>
              {merchants.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Tag */}
        {tags.length > 0 && (
          <Select
            value={filters.tag ?? ''}
            onValueChange={(v) => updateFilter('tag', v)}
          >
            <SelectTrigger
              className={`shrink-0 rounded-full border-none px-3.5 py-1.5 text-[13px] font-medium shadow-none ${
                filters.tag
                  ? 'bg-accent text-accent-foreground'
                  : 'bg-secondary text-muted-foreground'
              }`}
            >
              <SelectValue placeholder="Tag" />
            </SelectTrigger>
            <SelectContent>
              {tags.map((t) => (
                <SelectItem key={t.id} value={t.name}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Payment Method */}
        {paymentMethods.length > 0 && (
          <Select
            value={filters.payment_method ?? ''}
            onValueChange={(v) => updateFilter('payment_method', v)}
          >
            <SelectTrigger
              className={`shrink-0 rounded-full border-none px-3.5 py-1.5 text-[13px] font-medium shadow-none ${
                filters.payment_method
                  ? 'bg-accent text-accent-foreground'
                  : 'bg-secondary text-muted-foreground'
              }`}
            >
              <SelectValue placeholder="Payment Method" />
            </SelectTrigger>
            <SelectContent>
              {paymentMethods.map((pm) => (
                <SelectItem key={pm.id} value={pm.id}>
                  {pm.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Reset */}
        {hasActiveFilters && (
          <button
            onClick={resetFilters}
            className="flex shrink-0 items-center gap-1 rounded-full bg-secondary px-3 py-1.5 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-secondary/80"
          >
            <X className="h-3.5 w-3.5" />
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
