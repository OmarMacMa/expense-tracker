import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { InsightsSummary, LimitProgress } from '@/types/api';
import type { ExpenseFilters } from './useExpenses';
import { useAuth } from './useAuth';

interface TrendPoint {
  day: number;
  cumulative: string;
}

export interface SpendingTrend {
  current_series: TrendPoint[];
  average_series: TrendPoint[];
  timeframe: string;
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

function filtersToParams(filters: ExpenseFilters): Record<string, string> {
  const params: Record<string, string> = {};
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params[k] = v;
  });
  return params;
}

export function useInsightsSummary(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<InsightsSummary>({
    queryKey: ['insights', 'summary', currentSpace?.id, filters],
    queryFn: () =>
      api.get<InsightsSummary>(
        `/spaces/${currentSpace?.id}/insights/summary`,
        filtersToParams(filters),
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useSpendingTrend(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<SpendingTrend>({
    queryKey: ['insights', 'trend', currentSpace?.id, filters],
    queryFn: () =>
      api.get<SpendingTrend>(
        `/spaces/${currentSpace?.id}/insights/spending-trend`,
        filtersToParams(filters),
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useCategoryBreakdown(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<CategoryBreakdown[]>({
    queryKey: ['insights', 'categories', currentSpace?.id, filters],
    queryFn: () =>
      api.get<CategoryBreakdown[]>(
        `/spaces/${currentSpace?.id}/insights/category-breakdown`,
        filtersToParams(filters),
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useMerchantLeaderboard(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<MerchantLeaderboard[]>({
    queryKey: ['insights', 'merchants', currentSpace?.id, filters],
    queryFn: () =>
      api.get<MerchantLeaderboard[]>(
        `/spaces/${currentSpace?.id}/insights/merchant-leaderboard`,
        { ...filtersToParams(filters), limit: '10' },
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useLimitProgress() {
  const { currentSpace } = useAuth();
  return useQuery<LimitProgress[]>({
    queryKey: ['insights', 'limits', currentSpace?.id],
    queryFn: () =>
      api.get<LimitProgress[]>(
        `/spaces/${currentSpace?.id}/insights/limit-progress`,
      ),
    enabled: !!currentSpace?.id,
  });
}

export function useSpenderBreakdown(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();
  return useQuery<SpenderBreakdown[]>({
    queryKey: ['insights', 'spenders', currentSpace?.id, filters],
    queryFn: () =>
      api.get<SpenderBreakdown[]>(
        `/spaces/${currentSpace?.id}/insights/spender-breakdown`,
        filtersToParams(filters),
      ),
    enabled: !!currentSpace?.id,
  });
}
