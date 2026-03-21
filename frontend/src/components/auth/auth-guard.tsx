import { Navigate } from 'react-router';
import { useAuth } from '@/hooks/useAuth';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { isAuthenticated, hasSpace, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FAFAFE]">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#7C6FA0] border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (!hasSpace) {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
}
