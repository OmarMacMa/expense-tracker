import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api-client';
import { useAuth } from '@/hooks/useAuth';
import { setPendingInvite, clearPendingInvite } from '@/lib/pendingInvite';

interface InvitePreview {
  space_id: string;
  space_name: string;
  space_currency_code: string;
}

interface JoinResult {
  space_id: string;
  space_name: string;
  message: string;
}

interface ApiError {
  data?: { error?: { code?: string; message?: string } };
}

export default function JoinSpace() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, hasSpace, currentSpace, isLoading } = useAuth();

  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [joining, setJoining] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState<JoinResult | null>(null);

  // Cancel target depends on the user's auth/space state.
  const cancelTarget = !isAuthenticated
    ? '/'
    : hasSpace
      ? '/home'
      : '/onboarding';
  const cancelLabel = !isAuthenticated
    ? 'Go to Home'
    : hasSpace
      ? 'Back to Dashboard'
      : 'No, create my own space';

  // Fetch the invite preview once the user is authenticated. Unauthenticated
  // users sign in first and re-land here after OAuth (sessionStorage carries
  // the token), at which point this fetch runs.
  useEffect(() => {
    if (!token || !isAuthenticated || isLoading) return;
    let cancelled = false;
    setPreviewLoading(true);
    api
      .get<InvitePreview>(`/spaces/invites/${token}/preview`)
      .then((data) => {
        if (!cancelled) setPreview(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const apiErr = err as ApiError;
        setErrorCode(apiErr?.data?.error?.code ?? null);
        setErrorMessage(
          apiErr?.data?.error?.message ||
            'Failed to load this invite. Please try again.',
        );
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, isAuthenticated, isLoading]);

  const signInToAcceptInvite = () => {
    if (token) setPendingInvite(token);
    window.location.href = '/api/v1/auth/google';
  };

  const handleJoin = async () => {
    if (!token) return;
    setJoining(true);
    setErrorCode(null);
    setErrorMessage(null);
    try {
      const result = await api.post<JoinResult>(`/spaces/join/${token}`);
      clearPendingInvite();
      setSuccess(result);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setErrorCode(apiErr?.data?.error?.code ?? null);
      setErrorMessage(
        apiErr?.data?.error?.message ||
          'Failed to join space. Please try again.',
      );
    } finally {
      setJoining(false);
    }
  };

  const handleDecline = () => {
    // User explicitly declines the invite; clear the token so it doesn't
    // re-trigger on a subsequent /auth/callback hop, and route them to
    // onboarding where they can create their own space.
    clearPendingInvite();
    navigate('/onboarding');
  };

  if (isLoading) return <FullScreenSpinner />;

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAFAFE] px-4">
      <div
        className="w-full max-w-md rounded-xl bg-white p-8 text-center"
        style={{
          boxShadow:
            '0 2px 12px rgba(29,27,32,0.04), 0 6px 24px rgba(29,27,32,0.03)',
        }}
      >
        <h1 className="text-2xl font-bold text-[#1D1B20]">Join a Space</h1>

        {success ? (
          <SuccessState
            spaceName={success.space_name}
            onContinue={() => navigate('/home')}
          />
        ) : errorCode === 'ALREADY_HAS_SPACE' ? (
          <AlreadyHasSpaceState
            currentSpaceName={currentSpace?.name ?? 'your current space'}
            invitedSpaceName={preview?.space_name ?? null}
            cancelTarget={cancelTarget}
            cancelLabel={cancelLabel}
          />
        ) : errorCode ? (
          <ErrorState
            code={errorCode}
            message={errorMessage ?? ''}
            cancelTarget={cancelTarget}
            cancelLabel={cancelLabel}
          />
        ) : !isAuthenticated ? (
          <UnauthenticatedState onSignIn={signInToAcceptInvite} />
        ) : hasSpace ? (
          <AlreadyHasSpaceState
            currentSpaceName={currentSpace?.name ?? 'your current space'}
            invitedSpaceName={preview?.space_name ?? null}
            cancelTarget={cancelTarget}
            cancelLabel={cancelLabel}
          />
        ) : previewLoading || !preview ? (
          <InlineSpinner />
        ) : (
          <ConfirmJoinState
            spaceName={preview.space_name}
            joining={joining}
            onAccept={handleJoin}
            onDecline={handleDecline}
          />
        )}
      </div>
    </div>
  );
}

function FullScreenSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAFAFE]">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#7C6FA0] border-t-transparent" />
    </div>
  );
}

function InlineSpinner() {
  return (
    <div className="mt-8 flex justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-4 border-[#7C6FA0] border-t-transparent" />
    </div>
  );
}

function SuccessState({
  spaceName,
  onContinue,
}: {
  spaceName: string;
  onContinue: () => void;
}) {
  return (
    <div className="mt-6">
      <div className="rounded-lg bg-green-50 p-4">
        <p className="font-medium text-green-800">
          Successfully joined "{spaceName}"!
        </p>
      </div>
      <Button
        onClick={onContinue}
        className="mt-4 w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]"
      >
        Go to Dashboard
      </Button>
    </div>
  );
}

function UnauthenticatedState({ onSignIn }: { onSignIn: () => void }) {
  return (
    <div className="mt-6">
      <p className="text-sm text-[#615D69]">
        Sign in with Google to accept this invitation.
      </p>
      <Button
        onClick={onSignIn}
        className="mt-4 w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]"
      >
        Sign in with Google
      </Button>
    </div>
  );
}

function ConfirmJoinState({
  spaceName,
  joining,
  onAccept,
  onDecline,
}: {
  spaceName: string;
  joining: boolean;
  onAccept: () => void;
  onDecline: () => void;
}) {
  return (
    <div className="mt-6 text-left">
      <p className="text-sm text-[#615D69]">
        You're about to join the shared expense space:
      </p>
      <p className="mt-3 text-center text-xl font-semibold text-[#1D1B20]">
        "{spaceName}"
      </p>
      <p className="mt-3 text-sm text-[#615D69]">
        You'll see and contribute to its expenses, categories, and limits.
        Joining is reversible — you can leave from Settings at any time.
      </p>
      <Button
        onClick={onAccept}
        disabled={joining}
        className="mt-6 w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]"
      >
        {joining ? 'Joining...' : `Yes, join "${spaceName}"`}
      </Button>
      <Button
        onClick={onDecline}
        disabled={joining}
        variant="outline"
        className="mt-2 w-full"
      >
        No, create my own space
      </Button>
    </div>
  );
}

function AlreadyHasSpaceState({
  currentSpaceName,
  invitedSpaceName,
  cancelTarget,
  cancelLabel,
}: {
  currentSpaceName: string;
  invitedSpaceName: string | null;
  cancelTarget: string;
  cancelLabel: string;
}) {
  return (
    <div className="mt-6">
      <div className="rounded-lg bg-amber-50 p-4 text-left">
        <p className="font-medium text-amber-900">
          You're already in "{currentSpaceName}"
        </p>
        <p className="mt-2 text-sm text-amber-800">
          {invitedSpaceName
            ? `To join "${invitedSpaceName}", you need to leave your current space first. Your invite will wait for you here.`
            : 'To join this new space, you need to leave your current space first. Your invite will wait for you here.'}
        </p>
      </div>
      <Button asChild className="mt-4 w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]">
        <Link to="/settings#danger-zone">Go to Settings</Link>
      </Button>
      <Button asChild variant="outline" className="mt-2 w-full">
        <Link to={cancelTarget}>{cancelLabel}</Link>
      </Button>
    </div>
  );
}

function ErrorState({
  code,
  message,
  cancelTarget,
  cancelLabel,
}: {
  code: string;
  message: string;
  cancelTarget: string;
  cancelLabel: string;
}) {
  const friendly = (() => {
    switch (code) {
      case 'INVITE_EXPIRED':
        return 'This invite link has expired. Ask the inviter to send you a new one.';
      case 'INVITE_USED':
        return 'This invite link has already been used. Ask the inviter to send you a new one.';
      case 'MEMBER_LIMIT':
        return 'This space is full (10 members maximum). Ask the inviter for help.';
      case 'ALREADY_MEMBER':
        return "You're already a member of this space.";
      case 'NOT_FOUND':
        return 'Invite link not found. Double-check the link or ask for a new one.';
      default:
        return message;
    }
  })();

  return (
    <div className="mt-6">
      <div className="rounded-lg bg-red-50 p-4">
        <p className="text-sm text-red-800">{friendly}</p>
      </div>
      <Button asChild variant="outline" className="mt-4 w-full">
        <Link to={cancelTarget}>{cancelLabel}</Link>
      </Button>
    </div>
  );
}
