import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { Tag } from '@/types/api';
import { useAuth } from './useAuth';

export function useTags() {
  const { currentSpace } = useAuth();
  return useQuery<Tag[]>({
    queryKey: ['tags', currentSpace?.id],
    queryFn: () => api.get<Tag[]>(`/spaces/${currentSpace?.id}/tags`),
    enabled: !!currentSpace?.id,
  });
}
