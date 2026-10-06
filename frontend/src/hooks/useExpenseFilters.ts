import { useSearchParams } from 'react-router';
import type { SetStateAction } from 'react';
import { usePeriod } from './usePeriod';
import {
  filtersFromParams,
  filtersToParams,
  type ExpenseFilters,
} from '@/lib/expenseFilters';

export function useExpenseFilters() {
  const [params, setParams] = useSearchParams();
  const { period } = usePeriod();
  const filters = filtersFromParams(params);
  const queryFilters: ExpenseFilters = {
    ...filters,
    period: filters.period ?? (filters.month ? 'this_month' : period),
  };
  const setFilters = (next: SetStateAction<ExpenseFilters>) => {
    // History updates synchronously, even while React Router transitions render.
    // Read the latest URL so rapid checkbox events cannot overwrite each other.
    const current = filtersFromParams(
      new URLSearchParams(window.location.search),
    );
    setParams(
      filtersToParams(typeof next === 'function' ? next(current) : next),
      { replace: true },
    );
  };
  return { filters, queryFilters, setFilters };
}
