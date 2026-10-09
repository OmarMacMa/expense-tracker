import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { InsightsSummary, LimitProgress } from '@/types/api';
import type { ExpenseFilters } from './useExpenses';
import { useAuth } from './useAuth';
import { canonicalFilters, filtersToParams } from '@/lib/expenseFilters';

interface TrendPoint {
  day: number;
  cumulative: string;
}

export type SpendingTrendTimeframe =
  | 'weekly'
  | 'monthly'
  | 'quarterly'
  | 'yearly';

export interface SpendingTrend {
  current_series: TrendPoint[];
  average_series: TrendPoint[];
  average_period_count: number;
  timeframe: SpendingTrendTimeframe;
  year: number;
  current_day?: number | null;
}

export interface CategoryBreakdown {
  category_id: string;
  category_name: string;
  total: string;
  percentage: string;
}

export interface MerchantLeaderboard {
  merchant: string;
  total: string;
  count: number;
}

export interface SpenderBreakdown {
  spender_id: string;
  display_name: string;
  avatar_url: string | null;
  total: string;
  percentage: string;
}

export function useInsightsSummary(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<InsightsSummary>({
    queryKey: [
      'insights',
      'summary',
      currentSpace?.id,
      canonicalFilters(filters),
    ],
    queryFn: ({ signal }) =>
      api.get<InsightsSummary>(
        `/spaces/${currentSpace?.id}/insights/summary`,
        filtersToParams(filters),
        signal,
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useSpendingTrend(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<SpendingTrend>({
    queryKey: [
      'insights',
      'trend',
      currentSpace?.id,
      canonicalFilters(filters),
    ],
    queryFn: ({ signal }) =>
      api.get<SpendingTrend>(
        `/spaces/${currentSpace?.id}/insights/spending-trend`,
        filtersToParams(filters),
        signal,
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useCategoryBreakdown(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<CategoryBreakdown[]>({
    queryKey: [
      'insights',
      'categories',
      currentSpace?.id,
      canonicalFilters(filters),
    ],
    queryFn: ({ signal }) =>
      api.get<CategoryBreakdown[]>(
        `/spaces/${currentSpace?.id}/insights/category-breakdown`,
        filtersToParams(filters),
        signal,
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useMerchantLeaderboard(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<MerchantLeaderboard[]>({
    queryKey: [
      'insights',
      'merchants',
      currentSpace?.id,
      canonicalFilters(filters),
    ],
    queryFn: ({ signal }) =>
      api.get<MerchantLeaderboard[]>(
        `/spaces/${currentSpace?.id}/insights/merchant-leaderboard`,
        filtersToParams(filters),
        signal,
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useLimitProgress() {
  const { currentSpace } = useAuth();
  return useQuery<LimitProgress[]>({
    queryKey: ['insights', 'limits', currentSpace?.id],
    queryFn: ({ signal }) =>
      api.get<LimitProgress[]>(
        `/spaces/${currentSpace?.id}/insights/limit-progress`,
        undefined,
        signal,
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useSpenderBreakdown(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<SpenderBreakdown[]>({
    queryKey: [
      'insights',
      'spenders',
      currentSpace?.id,
      canonicalFilters(filters),
    ],
    queryFn: ({ signal }) =>
      api.get<SpenderBreakdown[]>(
        `/spaces/${currentSpace?.id}/insights/spender-breakdown`,
        filtersToParams(filters),
        signal,
      ),
    enabled: !!currentSpace?.id,
  });
}
