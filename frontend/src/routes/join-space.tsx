import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api-client';
import { useAuth } from '@/hooks/useAuth';

interface JoinResult {
  space_id: string;
  space_name: string;
  message: string;
}

export default function JoinSpace() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, isLoading: authLoading, signInWithGoogle } = useAuth();
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<JoinResult | null>(null);

  const handleJoin = async () => {
    if (!token) return;
    setJoining(true);
    setError(null);
    try {
      const result = await api.post<JoinResult>(`/spaces/join/${token}`);
      setSuccess(result);
    } catch (err: unknown) {
      const apiErr = err as { data?: { error?: { message?: string } } };
      setError(apiErr?.data?.error?.message || 'Failed to join space. The invite may be expired or already used.');
    } finally {
      setJoining(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FAFAFE]">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#7C6FA0] border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAFAFE] px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-8 text-center"
        style={{ boxShadow: '0 2px 12px rgba(29,27,32,0.04), 0 6px 24px rgba(29,27,32,0.03)' }}>
        
        <h1 className="text-2xl font-bold text-[#1D1B20]">Join a Space</h1>
        <p className="mt-2 text-sm text-[#615D69]">
          You've been invited to join a shared expense tracking space.
        </p>

        {success ? (
          <div className="mt-6">
            <div className="rounded-lg bg-green-50 p-4">
              <p className="font-medium text-green-800">
                Successfully joined "{success.space_name}"!
              </p>
            </div>
            <Button
              onClick={() => navigate('/home')}
              className="mt-4 w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]"
            >
              Go to Dashboard
            </Button>
          </div>
        ) : error ? (
          <div className="mt-6">
            <div className="rounded-lg bg-red-50 p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
            <Button
              onClick={() => navigate('/')}
              variant="outline"
              className="mt-4 w-full"
            >
              Go to Home
            </Button>
          </div>
        ) : !isAuthenticated ? (
          <div className="mt-6">
            <p className="text-sm text-[#615D69]">
              Sign in with Google to accept this invitation.
            </p>
            <Button
              onClick={signInWithGoogle}
              className="mt-4 w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]"
            >
              Sign in with Google
            </Button>
          </div>
        ) : (
          <div className="mt-6">
            <Button
              onClick={handleJoin}
              disabled={joining}
              className="w-full bg-[#7C6FA0] hover:bg-[#6B5F8A]"
            >
              {joining ? 'Joining...' : 'Join Space'}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
