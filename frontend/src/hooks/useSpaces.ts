import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
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
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
    },
  });
}

export function useGenerateInvite(spaceId: string) {
  return useMutation({
    mutationFn: () => api.post<InviteResponse>(`/spaces/${spaceId}/invite`),
  });
}
