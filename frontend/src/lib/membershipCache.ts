import type { QueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { AuthMeResponse } from '@/types/api';
import { errorMessage } from '@/lib/api-client';

interface RefreshState {
  destinationId: string | null;
  busy: boolean;
  error: string | null;
}
let state: RefreshState | null = null;
const listeners = new Set<() => void>();
export const membershipRefreshStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  getSnapshot() {
    return state;
  },
};
function updateState(value: RefreshState | null) {
  state = value;
  listeners.forEach((listener) => listener());
}

export async function refreshMembership(
  client: QueryClient,
  destinationId: string | null,
  navigate: (path: string, options: { replace: boolean }) => void,
): Promise<void> {
  // Freeze the old auth snapshot until the new one is ready. Cancel every
  // domain request, including historical keys that do not contain a space ID.
  updateState({ destinationId, busy: true, error: null });
  try {
    await client.cancelQueries();
    client.removeQueries({
      predicate: (query) => query.queryKey[0] !== 'auth',
    });
    const user = await api.get<AuthMeResponse>('/auth/me');
    if (
      destinationId
        ? !user.spaces.some((space) => space.id === destinationId)
        : user.spaces.length !== 0
    ) {
      throw new Error(
        'The refreshed membership is not ready. Reload to continue.',
      );
    }
    client.setQueryData(['auth', 'me'], user);
    navigate(destinationId ? '/home' : '/onboarding', { replace: true });
    updateState(null);
  } catch (error: unknown) {
    updateState({ destinationId, busy: false, error: errorMessage(error) });
    throw error;
  }
}
