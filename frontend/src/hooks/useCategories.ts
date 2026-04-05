import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api-client';
import type { ApiError } from '@/lib/api-client';
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
    onSuccess: () => {
      toast.success('Category created');
      queryClient.invalidateQueries({ queryKey: ['categories'] });
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to create category');
    },
  });
}

export function useUpdateCategory() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string } }) =>
      api.put(`/spaces/${currentSpace?.id}/categories/${id}`, data),
    onSuccess: () => {
      toast.success('Category updated');
      queryClient.invalidateQueries({ queryKey: ['categories'] });
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to update category');
    },
  });
}

export function useDeleteCategory() {
  const { currentSpace } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/spaces/${currentSpace?.id}/categories/${id}`),
    onSuccess: () => {
      toast.success('Category deleted');
      queryClient.invalidateQueries({ queryKey: ['categories'] });
    },
    onError: (error: ApiError) => {
      toast.error(error?.data?.error?.message || 'Failed to delete category');
    },
  });
}
