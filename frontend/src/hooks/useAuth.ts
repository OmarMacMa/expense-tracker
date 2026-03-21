import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { AuthMeResponse } from '@/types/api';

export function useAuth() {
  const queryClient = useQueryClient();

  const {
    data: user,
    isLoading,
    isError,
  } = useQuery<AuthMeResponse>({
    queryKey: ['auth', 'me'],
    queryFn: () => api.get<AuthMeResponse>('/auth/me'),
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const isAuthenticated = !!user && !isError;
  const currentSpace = user?.spaces?.[0] ?? null;
  const hasSpace = !!currentSpace;

  const logout = async () => {
    await api.post('/auth/logout');
    queryClient.clear();
    window.location.href = '/';
  };

  const signInWithGoogle = () => {
    window.location.href = '/api/v1/auth/google';
  };

  return {
    user,
    isLoading,
    isAuthenticated,
    currentSpace,
    hasSpace,
    logout,
    signInWithGoogle,
  };
}
