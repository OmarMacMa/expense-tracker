import { useSearchParams } from 'react-router';
import { useEffect, type SetStateAction } from 'react';
import { usePeriod } from './usePeriod';
import { useAuth } from './useAuth';
import {
  parseStoredPeriod,
  readPeriodSelection,
  type PeriodSelection,
} from '@/lib/periodSelection';
import {
  canonicalFilters,
  filtersFromParams,
  filtersToParams,
  type ExpenseFilterContext,
  type ExpenseFilters,
} from '@/lib/expenseFilters';

export function useExpenseFilters(
  context: ExpenseFilterContext = 'transactions',
) {
  const [params, setParams] = useSearchParams();
  const { period } = usePeriod();
  const { user, currentSpace } = useAuth();
  const storageKey =
    user && currentSpace
      ? `expense-tracker:period-override:${user.id}:${currentSpace.id}:${context}`
      : null;
  const filters = filtersFromParams(params, context);
  const urlPeriod = readPeriodSelection(filters);
  const rememberedPeriod = storageKey
    ? parseStoredPeriod(localStorage.getItem(storageKey))
    : null;
  const periodOverride = urlPeriod ?? rememberedPeriod;
  const serializedUrlPeriod = urlPeriod ? JSON.stringify(urlPeriod) : null;
  const queryFilters: ExpenseFilters = {
    ...filters,
    ...(periodOverride ?? { period }),
    month: periodOverride?.month,
  };

  useEffect(() => {
    if (storageKey && serializedUrlPeriod) {
      localStorage.setItem(storageKey, serializedUrlPeriod);
    }
  }, [storageKey, serializedUrlPeriod]);

  const setFilters = (next: SetStateAction<ExpenseFilters>) => {
    // History updates synchronously, even while React Router transitions render.
    // Read the latest URL so rapid checkbox events cannot overwrite each other.
    const currentUrl = filtersFromParams(
      new URLSearchParams(window.location.search),
      context,
    );
    const current: ExpenseFilters = {
      ...currentUrl,
      ...(readPeriodSelection(currentUrl) ??
        (storageKey
          ? parseStoredPeriod(localStorage.getItem(storageKey))
          : null) ??
        {}),
    };
    const updated = canonicalFilters(
      typeof next === 'function' ? next(current) : next,
      context,
    );
    const selected = readPeriodSelection(updated);
    if (storageKey) {
      if (selected) localStorage.setItem(storageKey, JSON.stringify(selected));
      else localStorage.removeItem(storageKey);
    }
    setParams(filtersToParams(updated), { replace: true });
  };
  const setPeriodOverride = (selection: PeriodSelection) =>
    setFilters((current) => ({
      ...current,
      period: selection.period,
      month: selection.month,
    }));
  const useHomePeriod = () =>
    setFilters((current) => ({
      ...current,
      period: undefined,
      month: undefined,
    }));

  return {
    filters,
    queryFilters,
    setFilters,
    periodOverride,
    homePeriod: period,
    setPeriodOverride,
    useHomePeriod,
  };
}
