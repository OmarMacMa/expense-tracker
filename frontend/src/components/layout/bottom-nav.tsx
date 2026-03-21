import { Link, useLocation } from 'react-router';
import { Home, List, Target, BarChart3, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';

const TAB_ITEMS = [
  { path: '/home', label: 'Home', icon: Home },
  { path: '/transactions', label: 'Transactions', icon: List },
  // FAB placeholder (index 2)
  { path: '/limits', label: 'Limits', icon: Target },
  { path: '/insights', label: 'Insights', icon: BarChart3 },
];

export function BottomNav() {
  const location = useLocation();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-50 flex items-center justify-around bg-[#F3F1F8] px-5 pb-7 pt-2">
      {/* Home */}
      {TAB_ITEMS.slice(0, 2).map(({ path, label, icon: Icon }) => {
        const isActive =
          location.pathname === path ||
          (path !== '/home' && location.pathname.startsWith(path));

        return (
          <Link
            key={path}
            to={path}
            className={cn(
              'flex w-16 flex-col items-center gap-0.5',
              isActive ? 'text-primary' : 'text-muted-foreground',
            )}
          >
            <div
              className={cn(
                'flex size-7 items-center justify-center rounded-[14px]',
                isActive && 'bg-accent',
              )}
            >
              <Icon className="size-5" />
            </div>
            <span className="text-[0.65rem] font-medium">{label}</span>
          </Link>
        );
      })}

      {/* FAB */}
      <Link
        to="/expenses/new"
        className="flex w-16 flex-col items-center gap-0.5"
      >
        <div className="-mt-7 flex size-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_4px_20px_rgba(124,111,160,0.35)]">
          <Plus className="size-7" strokeWidth={1.5} />
        </div>
      </Link>

      {/* Limits & Insights */}
      {TAB_ITEMS.slice(2).map(({ path, label, icon: Icon }) => {
        const isActive =
          location.pathname === path ||
          (path !== '/home' && location.pathname.startsWith(path));

        return (
          <Link
            key={path}
            to={path}
            className={cn(
              'flex w-16 flex-col items-center gap-0.5',
              isActive ? 'text-primary' : 'text-muted-foreground',
            )}
          >
            <div
              className={cn(
                'flex size-7 items-center justify-center rounded-[14px]',
                isActive && 'bg-accent',
              )}
            >
              <Icon className="size-5" />
            </div>
            <span className="text-[0.65rem] font-medium">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
