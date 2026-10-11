import type { AmountRange } from './amount-range';

export const FILTER_DIMENSIONS = [
  'spender',
  'category',
  'merchant',
  'tag',
  'payment_method',
] as const;

export type FilterDimension = (typeof FILTER_DIMENSIONS)[number];
export type ExpenseFilterContext = 'transactions' | 'insights';

export interface ExpenseFilters extends AmountRange {
  period?: string;
  month?: string;
  spender?: string[];
  category?: string[];
  merchant?: string[];
  tag?: string[];
  payment_method?: string[];
  search?: string;
  status?: string;
}

const SCALAR_KEYS = [
  'period',
  'month',
  'search',
  'status',
  'min_amount',
  'max_amount',
] as const;

export function canonicalFilters(
  filters: ExpenseFilters,
  context: ExpenseFilterContext = 'transactions',
): ExpenseFilters {
  const result: ExpenseFilters = {};
  for (const key of SCALAR_KEYS) {
    if (context === 'insights' && key === 'search') continue;
    if (filters[key]) result[key] = filters[key];
  }
  for (const key of FILTER_DIMENSIONS) {
    const values = (filters[key] ?? [])
      .map((value) =>
        key === 'tag' ? value.trim().toLowerCase().replace(/^#+/, '') : value,
      )
      .filter(Boolean);
    if (values.length) result[key] = [...new Set(values)].sort();
  }
  return result;
}

export function filtersToParams(filters: ExpenseFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(canonicalFilters(filters))) {
    if (Array.isArray(value)) {
      for (const selection of value) params.append(key, selection);
    } else if (value) {
      params.set(key, value);
    }
  }
  return params;
}

export function filtersFromParams(
  params: URLSearchParams,
  context: ExpenseFilterContext = 'transactions',
): ExpenseFilters {
  const filters: ExpenseFilters = {};
  for (const key of SCALAR_KEYS) {
    filters[key] = params.get(key) ?? undefined;
  }
  for (const key of FILTER_DIMENSIONS) {
    filters[key] = params.getAll(key);
  }
  return canonicalFilters(filters, context);
}
