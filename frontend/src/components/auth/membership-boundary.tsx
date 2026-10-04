import { useSyncExternalStore } from 'react';
import { useNavigate } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import {
  membershipRefreshStore,
  refreshMembership,
} from '@/lib/membershipCache';

export function MembershipBoundary({
  children,
}: {
  children: React.ReactNode;
}) {
  const state = useSyncExternalStore(
    membershipRefreshStore.subscribe,
    membershipRefreshStore.getSnapshot,
  );
  const client = useQueryClient();
  const navigate = useNavigate();
  if (!state) return children;
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-4 rounded-2xl bg-card p-6 shadow-[var(--shadow-card)]">
        <h1 className="text-xl font-semibold">Membership change completed</h1>
        <p className="text-sm text-muted-foreground">
          Your membership change succeeded. Do not submit it again.
        </p>
        {state.busy ? (
          <p role="status">Refreshing your session...</p>
        ) : (
          <>
            <p role="alert" className="text-sm text-destructive">
              Unable to refresh your session. {state.error}
            </p>
            <Button
              className="w-full"
              onClick={() => {
                // The boundary retains and displays refresh errors, never retries
                // the already-committed membership mutation.
                void refreshMembership(
                  client,
                  state.destinationId,
                  navigate,
                ).catch(() => {});
              }}
            >
              Refresh session
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => window.location.reload()}
            >
              Reload page
            </Button>
          </>
        )}
      </div>
    </main>
  );
}
