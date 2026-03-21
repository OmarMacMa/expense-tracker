import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { useAuth } from './useAuth';

interface MerchantSuggestion {
  name: string;
  use_count: number;
}

interface MerchantCategory {
  name: string;
  last_category_id: string | null;
  last_category_name: string | null;
}

export function useMerchantList() {
  const { currentSpace } = useAuth();
  return useQuery<string[]>({
    queryKey: ['merchants', 'list', currentSpace?.id],
    queryFn: () => api.get<string[]>(`/spaces/${currentSpace?.id}/merchants`),
    enabled: !!currentSpace?.id,
  });
}

export function useMerchantSuggest(query: string) {
  const { currentSpace } = useAuth();
  return useQuery<MerchantSuggestion[]>({
    queryKey: ['merchants', 'suggest', query],
    queryFn: () =>
      api.get<MerchantSuggestion[]>(
        `/spaces/${currentSpace?.id}/merchants/suggest`,
        { q: query },
      ),
    enabled: query.length >= 1,
    staleTime: 30_000,
  });
}

export function useMerchantCategory(merchantName: string) {
  const { currentSpace } = useAuth();
  return useQuery<MerchantCategory>({
    queryKey: ['merchants', 'category', merchantName],
    queryFn: () =>
      api.get<MerchantCategory>(
        `/spaces/${currentSpace?.id}/merchants/${encodeURIComponent(merchantName)}/category`,
      ),
    enabled: merchantName.length >= 1,
  });
}
