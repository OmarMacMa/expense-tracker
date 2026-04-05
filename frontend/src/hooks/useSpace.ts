import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api-client';
import type { ApiError } from '@/lib/api-client';
import type { Space } from '@/types/api';
import { useAuth } from './useAuth';

export function useSpace() {
  const { currentSpace } = useAuth();
  const spaceId = currentSpace?.id;

  return useQuery<Space>({
    queryKey: ['space', spaceId],
    queryFn: () => api.get<Space>(`/spaces/${spaceId}`),
    enabled: !!spaceId,
  });
}

export function useUpdateSpace() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      name: string;
      timezone: string;
      default_tax_pct: number | null;
    }) =>
      api.put<Space>(
        `/spaces/${currentSpace?.id}`,
        data as unknown as Record<string, unknown>,
      ),
    onSuccess: () => {
      toast.success('Space updated');
      queryClient.invalidateQueries({ queryKey: ['space'] });
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to update space');
    },
  });
}
