import { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '@/hooks/useAuth';
import {
  readPendingInvite,
  hasPendingInviteIntent,
  clearPendingInvite,
} from '@/lib/pendingInvite';
import { Button } from '@/components/ui/button';

export default function AuthCallback() {
  const { isAuthenticated, hasSpace, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoading) return;
    if (isAuthenticated && hasPendingInviteIntent() && !readPendingInvite())
      return;

    // Pending invite token wins — route back to /join/:token to complete the
    // join (or to show "already in a space" if the user already has one).
    // Don't clear here: /join/:token consumes it on successful join, and the
    // "leave then auto-rejoin" path needs it to survive a Settings detour.
    const pendingToken = readPendingInvite();
    if (isAuthenticated && pendingToken) {
      navigate(`/join/${pendingToken}`, { replace: true });
      return;
    }

    if (isAuthenticated && hasSpace) {
      navigate('/home', { replace: true });
    } else if (isAuthenticated && !hasSpace) {
      navigate('/onboarding', { replace: true });
    } else {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, hasSpace, isLoading, navigate]);

  if (
    !isLoading &&
    isAuthenticated &&
    hasPendingInviteIntent() &&
    !readPendingInvite()
  ) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-6">
        <h1 className="text-xl font-semibold">Invitation expired</h1>
        <p role="alert">
          Your pending invitation expired. Open the intended invite link again.
          No membership has changed.
        </p>
        <Button
          onClick={() => {
            clearPendingInvite();
            navigate(hasSpace ? '/home' : '/onboarding', { replace: true });
          }}
        >
          Abandon invitation
        </Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="mt-4 text-on-surface-variant">Signing you in...</p>
      </div>
    </div>
  );
}
