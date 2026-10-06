import { ChevronDown, Search, X } from 'lucide-react';
import type { Dispatch, SetStateAction } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import {
  FILTER_DIMENSIONS,
  type ExpenseFilters,
  type FilterDimension,
} from '@/lib/expenseFilters';
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
  onFiltersChange: Dispatch<SetStateAction<ExpenseFilters>>;
  spenders?: { user_id: string; display_name: string }[];
  categories?: { id: string; name: string }[];
  merchants?: string[];
  tags?: { id: string; name: string }[];
  paymentMethods?: { id: string; label: string }[];
  showSearch?: boolean;
  showPeriodChips?: boolean;
  optionsError?: boolean;
}

interface FilterOption {
  value: string;
  label: string;
}

function MultiSelectFilter({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: FilterOption[];
  selected: string[];
  onChange: (update: (values: string[]) => string[]) => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`${label}: ${selected.length} selected`}
          className={cn(
            'flex min-h-11 shrink-0 items-center gap-2 rounded-full px-3.5 text-[13px] font-medium focus-visible:outline-2 focus-visible:outline-primary',
            selected.length
              ? 'bg-accent text-accent-foreground'
              : 'bg-secondary text-muted-foreground',
          )}
        >
          {label}
          {selected.length > 0 && (
            <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
              {selected.length}
            </span>
          )}
          <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        aria-label={`Select ${label.toLowerCase()}`}
        className="w-72 max-w-[calc(100vw-2rem)] rounded-2xl border-none bg-card p-3 shadow-[var(--shadow-card)]"
      >
        <div className="mb-2 flex items-center justify-between gap-2 px-1">
          <span className="text-sm font-semibold">{label}</span>
          <button
            type="button"
            disabled={!selected.length}
            onClick={() => onChange(() => [])}
            className="min-h-11 px-2 text-xs font-medium text-primary disabled:opacity-40"
          >
            Clear {label.toLowerCase()}
          </button>
        </div>
        <div className="max-h-[min(18rem,50dvh)] overflow-y-auto">
          {options.length === 0 && (
            <p className="p-2 text-sm text-muted-foreground">No options yet</p>
          )}
          {options.map((option) => (
            <label
              key={option.value}
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-2 text-sm hover:bg-secondary"
            >
              <input
                type="checkbox"
                checked={selected.includes(option.value)}
                onChange={(event) => {
                  const checked = event.target.checked;
                  onChange((values) =>
                    checked
                      ? [...values, option.value]
                      : values.filter((value) => value !== option.value),
                  );
                }}
                className="h-4 w-4 shrink-0 accent-primary"
              />
              <span className="break-words">{option.label}</span>
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
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
  optionsError = false,
}: FilterBarProps) {
  const dimensions: Record<
    FilterDimension,
    { label: string; options: FilterOption[] }
  > = {
    spender: {
      label: 'Spender',
      options: spenders.map((s) => ({
        value: s.user_id,
        label: s.display_name,
      })),
    },
    category: {
      label: 'Category',
      options: categories.map((c) => ({ value: c.id, label: c.name })),
    },
    merchant: {
      label: 'Merchant',
      options: merchants.map((name) => ({ value: name, label: name })),
    },
    tag: {
      label: 'Tag',
      options: tags.map((t) => ({ value: t.name, label: `#${t.name}` })),
    },
    payment_method: {
      label: 'Payment Method',
      options: paymentMethods.map((pm) => ({ value: pm.id, label: pm.label })),
    },
  };
  const hasActiveFilters = Object.values(filters).some((value) =>
    Array.isArray(value) ? value.length > 0 : !!value,
  );
  const updateDimension = (
    key: FilterDimension,
    update: (values: string[]) => string[],
  ) =>
    onFiltersChange((current) => {
      const values = update(current[key] ?? []);
      return { ...current, [key]: values.length ? values : undefined };
    });
  const updatePeriod = (period: string) =>
    onFiltersChange((current) => ({ ...current, period, month: undefined }));

  return (
    <div className="space-y-3">
      {showSearch && (
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="Search transactions"
            placeholder="Search merchants, notes, tags…"
            value={filters.search ?? ''}
            onChange={(e) => {
              const search = e.target.value;
              onFiltersChange((current) => ({ ...current, search }));
            }}
            className="h-11 rounded-xl border-none bg-secondary pl-10 text-sm shadow-none"
          />
        </div>
      )}
      {showPeriodChips && (
        <div className="flex flex-wrap gap-2">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              type="button"
              key={opt.value}
              aria-pressed={!filters.month && filters.period === opt.value}
              onClick={() => updatePeriod(opt.value)}
              className={cn(
                'min-h-11 rounded-full px-3.5 text-[13px] font-medium transition-colors',
                !filters.month && filters.period === opt.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:bg-secondary/80',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {!showPeriodChips && (
          <Select
            value={filters.month ? '' : (filters.period ?? '')}
            onValueChange={updatePeriod}
          >
            <SelectTrigger className="min-h-11 rounded-full border-none bg-secondary px-3.5 text-[13px] shadow-none">
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
        <Input
          type="month"
          aria-label="Month picker"
          value={filters.month ?? ''}
          onChange={(e) => {
            const month = e.target.value || undefined;
            onFiltersChange((current) => ({
              ...current,
              month,
              period: 'this_month',
            }));
          }}
          className="h-11 w-44 rounded-full border-none bg-secondary text-[13px]"
        />
        {FILTER_DIMENSIONS.map((key) => {
          const { label, options } = dimensions[key];
          const selected = filters[key] ?? [];
          const retainedOptions = selected
            .filter(
              (value) => !options.some((option) => option.value === value),
            )
            .map((value) => ({ value, label: value }));
          return (
            <MultiSelectFilter
              key={key}
              label={label}
              options={[...options, ...retainedOptions]}
              selected={selected}
              onChange={(update) => updateDimension(key, update)}
            />
          );
        })}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={() => onFiltersChange({})}
            className="flex min-h-11 items-center gap-1 rounded-full bg-secondary px-3 text-[13px] font-medium text-muted-foreground"
          >
            <X className="h-3.5 w-3.5" /> Clear all
          </button>
        )}
      </div>
      {optionsError && (
        <p role="alert" className="text-sm text-destructive">
          Some filter options failed to load. Refresh to try again; existing
          selections are retained.
        </p>
      )}
      <div className="flex flex-wrap gap-2" aria-label="Selected filters">
        {FILTER_DIMENSIONS.flatMap((key) =>
          (filters[key] ?? []).map((value) => {
            const dimension = dimensions[key];
            const label =
              dimension.options.find((option) => option.value === value)
                ?.label ?? value;
            return (
              <button
                type="button"
                key={`${key}:${value}`}
                aria-label={`Remove ${dimension.label.toLowerCase()}: ${label}`}
                onClick={() =>
                  updateDimension(key, (values) =>
                    values.filter((item) => item !== value),
                  )
                }
                className="flex min-h-11 max-w-full items-center gap-2 rounded-full bg-accent px-3 text-xs text-accent-foreground"
              >
                <span className="truncate">
                  {dimension.label}: {label}
                </span>
                <X className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              </button>
            );
          }),
        )}
      </div>
    </div>
  );
}
