import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api-client';
import type { ApiError } from '@/lib/api-client';
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
    onSuccess: () => {
      toast.success('Limit created');
      queryClient.invalidateQueries({ queryKey: ['limits'] });
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to create limit');
    },
  });
}

export function useUpdateLimit() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.patch(`/spaces/${currentSpace?.id}/limits/${id}`, data),
    onSuccess: () => {
      toast.success('Limit updated');
      queryClient.invalidateQueries({ queryKey: ['limits'] });
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to update limit');
    },
  });
}

export function useDeleteLimit() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/spaces/${currentSpace?.id}/limits/${id}`),
    onSuccess: () => {
      toast.success('Limit deleted');
      queryClient.invalidateQueries({ queryKey: ['limits'] });
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to delete limit');
    },
  });
}
