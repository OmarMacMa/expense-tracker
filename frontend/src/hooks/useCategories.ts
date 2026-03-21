import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { Category } from '@/types/api';
import { useAuth } from './useAuth';

export function useCategories() {
  const { currentSpace } = useAuth();
  return useQuery<Category[]>({
    queryKey: ['categories', currentSpace?.id],
    queryFn: () =>
      api.get<Category[]>(`/spaces/${currentSpace?.id}/categories`),
    enabled: !!currentSpace?.id,
  });
}

export function useCreateCategory() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string }) =>
      api.post(`/spaces/${currentSpace?.id}/categories`, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['categories'] }),
  });
}

export function useUpdateCategory() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string } }) =>
      api.put(`/spaces/${currentSpace?.id}/categories/${id}`, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['categories'] }),
  });
}

export function useDeleteCategory() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/spaces/${currentSpace?.id}/categories/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['categories'] }),
  });
}
