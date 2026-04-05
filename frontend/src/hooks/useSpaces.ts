import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api-client';
import type { ApiError } from '@/lib/api-client';
import type { Space } from '@/types/api';

interface CreateSpaceData {
  name: string;
  currency_code: string;
  timezone: string;
  default_tax_pct?: number | null;
  seed_default_categories: boolean;
}

interface InviteResponse {
  token: string;
  expires_at: string;
}

export function useCreateSpace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateSpaceData) =>
      api.post<Space>('/spaces', data as unknown as Record<string, unknown>),
    onSuccess: () => {
      toast.success('Space created');
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to create space');
    },
  });
}

export function useGenerateInvite(spaceId: string) {
  return useMutation({
    mutationFn: () => api.post<InviteResponse>(`/spaces/${spaceId}/invite`),
    onSuccess: () => {
      toast.success('Invite link generated');
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to generate invite');
    },
  });
}
