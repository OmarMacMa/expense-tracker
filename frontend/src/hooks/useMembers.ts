import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { SpaceMember } from '@/types/api';
import { useAuth } from './useAuth';

export function useMembers() {
  const { currentSpace } = useAuth();
  return useQuery<SpaceMember[]>({
    queryKey: ['members', currentSpace?.id],
    queryFn: () =>
      api.get<SpaceMember[]>(`/spaces/${currentSpace?.id}/members`),
    enabled: !!currentSpace?.id,
  });
}
