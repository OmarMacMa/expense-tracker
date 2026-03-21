import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { LimitProgress } from '@/types/api';
import { useAuth } from './useAuth';

export function useLimits() {
  const { currentSpace } = useAuth();
  return useQuery<LimitProgress[]>({
    queryKey: ['limits', currentSpace?.id],
    queryFn: () =>
      api.get<LimitProgress[]>(`/spaces/${currentSpace?.id}/limits`),
    enabled: !!currentSpace?.id,
  });
}

export function useCreateLimit() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.post(`/spaces/${currentSpace?.id}/limits`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['limits'] }),
  });
}

export function useUpdateLimit() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.patch(`/spaces/${currentSpace?.id}/limits/${id}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['limits'] }),
  });
}

export function useDeleteLimit() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/spaces/${currentSpace?.id}/limits/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['limits'] }),
  });
}
