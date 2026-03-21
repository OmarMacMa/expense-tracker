import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { Expense, ExpenseListResponse } from '@/types/api';
import { useAuth } from './useAuth';

export interface ExpenseFilters {
  period?: string;
  month?: string;
  spender?: string;
  category?: string;
  merchant?: string;
  tag?: string;
  payment_method?: string;
  search?: string;
}

export function useExpenseList(filters: ExpenseFilters = {}) {
  const { currentSpace } = useAuth();

  return useInfiniteQuery<ExpenseListResponse>({
    queryKey: ['expenses', currentSpace?.id, filters],
    queryFn: ({ pageParam }) => {
      const params: Record<string, string> = { limit: '20' };
      if (pageParam) params.cursor = pageParam as string;
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params[k] = v;
      });
      return api.get<ExpenseListResponse>(
        `/spaces/${currentSpace?.id}/expenses`,
        params,
      );
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: !!currentSpace?.id,
  });
}

export function useExpense(expenseId: string) {
  const { currentSpace } = useAuth();
  return useQuery<Expense>({
    queryKey: ['expense', expenseId],
    queryFn: () =>
      api.get<Expense>(`/spaces/${currentSpace?.id}/expenses/${expenseId}`),
    enabled: !!currentSpace?.id && !!expenseId,
  });
}

export function useCreateExpense() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.post<Expense>(`/spaces/${currentSpace?.id}/expenses`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
    },
  });
}

export function useUpdateExpense() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.patch<Expense>(`/spaces/${currentSpace?.id}/expenses/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['expense'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
    },
  });
}

export function useDeleteExpense() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/spaces/${currentSpace?.id}/expenses/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
    },
  });
}
