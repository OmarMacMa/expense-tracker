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
  return useQuery<MerchantSuggestion[]>({
    queryKey: ['merchants', 'list', currentSpace?.id],
    queryFn: ({ signal }) =>
      api.get<MerchantSuggestion[]>(
        `/spaces/${currentSpace?.id}/merchants/suggest`,
        { q: '' },
        signal,
      ),
    enabled: !!currentSpace?.id,
    staleTime: 60_000,
  });
}

export function useMerchantSuggest(query: string) {
  const { currentSpace } = useAuth();
  return useQuery<MerchantSuggestion[]>({
    queryKey: ['merchants', 'suggest', currentSpace?.id, query],
    queryFn: ({ signal }) =>
      api.get<MerchantSuggestion[]>(
        `/spaces/${currentSpace?.id}/merchants/suggest`,
        { q: query },
        signal,
      ),
    enabled: !!currentSpace?.id && query.length >= 1,
    staleTime: 30_000,
  });
}

export function useMerchantCategory(merchantName: string) {
  const { currentSpace } = useAuth();
  return useQuery<MerchantCategory>({
    queryKey: ['merchants', 'category', currentSpace?.id, merchantName],
    queryFn: ({ signal }) =>
      api.get<MerchantCategory>(
        `/spaces/${currentSpace?.id}/merchants/${encodeURIComponent(merchantName)}/category`,
        undefined,
        signal,
      ),
    enabled: !!currentSpace?.id && merchantName.length >= 1,
  });
}
