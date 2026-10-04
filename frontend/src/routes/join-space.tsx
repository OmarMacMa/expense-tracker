import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { api, errorMessage } from '@/lib/api-client';
import { useAuth } from '@/hooks/useAuth';
import { setPendingInvite, clearPendingInvite } from '@/lib/pendingInvite';
import { refreshMembership } from '@/lib/membershipCache';
import type { InvitePreview } from '@/types/api';

export default function JoinSpace() {
  const { token } = useParams<{ token: string }>();
  return token ? (
    <Invite key={token} token={token} />
  ) : (
    <p role="alert">Invite link is missing.</p>
  );
}

function Invite({ token }: { token: string }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const { isAuthenticated, hasSpace, currentSpace, isLoading } = useAuth();
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState<string | null>(null);
  const preview = useQuery({
    queryKey: ['invite-preview', token],
    queryFn: ({ signal }) =>
      api.get<InvitePreview>(
        `/spaces/invites/${encodeURIComponent(token)}/preview`,
        undefined,
        signal,
      ),
    enabled: isAuthenticated,
    retry: false,
    staleTime: 0,
  });

  useEffect(() => {
    setPendingInvite(token);
  }, [token]);

  const cancel = () => {
    clearPendingInvite();
    navigate(!isAuthenticated ? '/' : hasSpace ? '/home' : '/onboarding');
  };

  const finish = async (destinationId: string) => {
    setJoining(true);
    setError(null);
    try {
      await refreshMembership(client, destinationId, navigate);
    } catch (err: unknown) {
      setError(
        `Joining completed, but your session could not refresh. ${errorMessage(err)}`,
      );
    } finally {
      setJoining(false);
    }
  };

  const join = async () => {
    setJoining(true);
    setError(null);
    let destinationId: string;
    try {
      const result = await api.post<{ space_id: string }>(
        `/spaces/join/${encodeURIComponent(token)}`,
      );
      destinationId = result.space_id;
      clearPendingInvite();
      setCompleted(destinationId);
    } catch (err: unknown) {
      setError(errorMessage(err));
      setJoining(false);
      return;
    }
    await finish(destinationId);
  };

  const target = preview.data;
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="w-full max-w-md space-y-4 rounded-2xl bg-card p-6 text-center shadow-[var(--shadow-card)] md:p-8">
        <h1 className="text-2xl font-bold">Join a Space</h1>
        {isLoading ? (
          <p role="status">Checking your session...</p>
        ) : completed ? (
          <>
            <p>Joining completed.</p>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <Button
              className="w-full"
              disabled={joining}
              onClick={() => finish(completed)}
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
        ) : !isAuthenticated ? (
          <>
            <p className="text-sm text-muted-foreground">
              Sign in with Google to review this invitation.
            </p>
            <Button
              className="w-full"
              onClick={() => {
                window.location.href = '/api/v1/auth/google';
              }}
            >
              Sign in with Google
            </Button>
          </>
        ) : preview.isError ? (
          <>
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(preview.error)}
            </p>
            <Button className="w-full" onClick={() => preview.refetch()}>
              Retry invitation
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => {
                window.location.href = '/api/v1/auth/google';
              }}
            >
              Sign in again
            </Button>
          </>
        ) : !target ? (
          <p role="status">Loading invitation...</p>
        ) : target.already_member ? (
          <>
            <p>You're already in "{target.space_name}".</p>
            <Button
              className="w-full"
              onClick={() => {
                clearPendingInvite();
                setCompleted(target.space_id);
                void finish(target.space_id);
              }}
            >
              Go to Dashboard
            </Button>
          </>
        ) : (
          <>
            <p className="text-xl font-semibold">"{target.space_name}"</p>
            <p className="text-sm text-muted-foreground">
              {target.member_count} / {target.max_members} members
            </p>
            {target.member_count >= target.max_members ? (
              <p role="alert">
                This space is full. Your current membership will not change.
              </p>
            ) : hasSpace ? (
              <>
                <p className="text-sm text-muted-foreground">
                  You're in "{currentSpace?.name}". Review the consequences in
                  Settings, then leave and join "{target.space_name}" in one
                  step. No expense data is moved. If joining fails, your current
                  space is unchanged.
                </p>
                <Button asChild className="w-full">
                  <Link to="/settings#danger-zone">
                    Review switch in Settings
                  </Link>
                </Button>
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  You'll share its expenses, categories and limits. You can
                  leave later in Settings.
                </p>
                <Button className="w-full" disabled={joining} onClick={join}>
                  {joining ? 'Joining...' : `Yes, join "${target.space_name}"`}
                </Button>
              </>
            )}
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
          </>
        )}
        {!completed && (
          <Button
            variant="outline"
            className="w-full"
            disabled={joining}
            onClick={cancel}
          >
            Cancel invitation
          </Button>
        )}
      </div>
    </div>
  );
}
