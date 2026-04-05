import { Sidebar } from './sidebar';
import { BottomNav } from './bottom-nav';
import { TopBar } from './top-bar';
import { ErrorBoundary } from '@/components/error-boundary';
import { useAuth } from '@/hooks/useAuth';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { user, currentSpace, logout } = useAuth();
  const userProps = user ?? null;

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop sidebar */}
      <div className="hidden md:fixed md:inset-y-0 md:flex md:w-[248px]">
        <Sidebar user={userProps} onLogout={logout} />
      </div>

      {/* Mobile top bar */}
      <div className="md:hidden">
        <TopBar
          user={userProps}
          spaceName={currentSpace?.name}
          onLogout={logout}
        />
      </div>

      {/* Main content */}
      <main className="md:pl-[248px]">
        <div className="mx-auto max-w-[1100px] px-4 py-6 pb-24 md:px-10 md:pb-6 md:pt-7">
          <ErrorBoundary>{children}</ErrorBoundary>
        </div>
      </main>

      {/* Mobile bottom nav */}
      <div className="md:hidden">
        <BottomNav />
      </div>
    </div>
  );
}
