import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api-client';
import { useAuth } from '@/hooks/useAuth';
import { setPendingInvite, clearPendingInvite } from '@/lib/pendingInvite';

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
  const [joining, setJoining] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState<JoinResult | null>(null);

  const signInToAcceptInvite = () => {
    if (token) {
      // Persist the token across the Google OAuth roundtrip; auth-callback
      // reads it after sign-in and routes back here.
      setPendingInvite(token);
    }
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

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FAFAFE]">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#7C6FA0] border-t-transparent" />
      </div>
    );
  }

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
        <p className="mt-2 text-sm text-[#615D69]">
          You've been invited to join a shared expense tracking space.
        </p>

        {success ? (
          <SuccessState
            spaceName={success.space_name}
            onContinue={() => navigate('/home')}
          />
        ) : errorCode === 'ALREADY_HAS_SPACE' ? (
          <AlreadyHasSpaceState
            currentSpaceName={currentSpace?.name ?? 'your current space'}
            onCancel={() => navigate('/home')}
          />
        ) : errorCode ? (
          <ErrorState
            code={errorCode}
            message={errorMessage ?? ''}
            onCancel={() => navigate('/')}
          />
        ) : !isAuthenticated ? (
          <UnauthenticatedState onSignIn={signInToAcceptInvite} />
        ) : hasSpace ? (
          // Authenticated, already in a space. Don't auto-call the API; show
          // the user the leave-first path. Note: pending_invite_token is NOT
          // cleared here — useLeaveSpace (PR 2) consumes it after the user
          // leaves their current space, so they get auto-routed back to this
          // invite to complete the join.
          <AlreadyHasSpaceState
            currentSpaceName={currentSpace?.name ?? 'your current space'}
            onCancel={() => navigate('/home')}
          />
        ) : (
          <ReadyToJoinState joining={joining} onJoin={handleJoin} />
        )}
      </div>
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

function ReadyToJoinState({
  joining,
  onJoin,
}: {
  joining: boolean;
  onJoin: () => void;
}) {
  return (
    <div className="mt-6">
      <Button
        onClick={onJoin}
        disabled={joining}
        className="w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]"
      >
        {joining ? 'Joining...' : 'Join Space'}
      </Button>
    </div>
  );
}

function AlreadyHasSpaceState({
  currentSpaceName,
  onCancel,
}: {
  currentSpaceName: string;
  onCancel: () => void;
}) {
  return (
    <div className="mt-6">
      <div className="rounded-lg bg-amber-50 p-4 text-left">
        <p className="font-medium text-amber-900">
          You're already in "{currentSpaceName}"
        </p>
        <p className="mt-2 text-sm text-amber-800">
          To join this new space, you need to leave your current space first.
          Your invite will wait for you here.
        </p>
      </div>
      <Link to="/settings#danger-zone">
        <Button className="mt-4 w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]">
          Go to Settings
        </Button>
      </Link>
      <Button onClick={onCancel} variant="outline" className="mt-2 w-full">
        Cancel
      </Button>
    </div>
  );
}

function ErrorState({
  code,
  message,
  onCancel,
}: {
  code: string;
  message: string;
  onCancel: () => void;
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
      <Button onClick={onCancel} variant="outline" className="mt-4 w-full">
        Go to Home
      </Button>
    </div>
  );
}
