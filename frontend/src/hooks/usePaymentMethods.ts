import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { PaymentMethod } from '@/types/api';
import { useAuth } from './useAuth';

export function usePaymentMethods() {
  const { currentSpace } = useAuth();
  return useQuery<PaymentMethod[]>({
    queryKey: ['payment-methods', currentSpace?.id],
    queryFn: () =>
      api.get<PaymentMethod[]>(`/spaces/${currentSpace?.id}/payment-methods`),
    enabled: !!currentSpace?.id,
  });
}

export function useCreatePaymentMethod() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { label: string }) =>
      api.post(`/spaces/${currentSpace?.id}/payment-methods`, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] }),
  });
}

export function useDeletePaymentMethod() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/spaces/${currentSpace?.id}/payment-methods/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] }),
  });
}
