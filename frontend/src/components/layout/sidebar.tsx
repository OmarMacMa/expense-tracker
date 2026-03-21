import { Link, useLocation } from 'react-router';
import {
  Home,
  List,
  Target,
  BarChart3,
  Settings,
  Plus,
  LogOut,
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface SidebarProps {
  user: {
    display_name: string;
    avatar_url: string | null;
    email: string;
  } | null;
  onLogout: () => void;
}

const NAV_ITEMS = [
  { path: '/home', label: 'Home', icon: Home },
  { path: '/transactions', label: 'Transactions', icon: List },
  { path: '/limits', label: 'Limits', icon: Target },
  { path: '/insights', label: 'Insights', icon: BarChart3 },
];

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function Sidebar({ user, onLogout }: SidebarProps) {
  const location = useLocation();

  return (
    <nav className="flex h-full w-[248px] flex-col bg-[#F3F1F8] p-6 pb-4">
      {/* Logo */}
      <div className="mb-6 flex items-center gap-2.5 px-2">
        <div className="flex size-8 items-center justify-center rounded-[10px] bg-primary text-sm font-bold text-primary-foreground">
          E
        </div>
        <span className="text-[1.15rem] font-bold text-foreground">
          Expense Tracker
        </span>
      </div>

      {/* Add Expense CTA */}
      <Button
        asChild
        className="mb-7 h-auto w-full rounded-2xl px-5 py-3 text-[0.9rem] font-medium"
      >
        <Link to="/expenses/new">
          <Plus className="size-5" strokeWidth={1.5} />
          Add Expense
        </Link>
      </Button>

      {/* Navigation links */}
      <div className="flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const isActive =
            location.pathname === path ||
            (path !== '/home' && location.pathname.startsWith(path));

          return (
            <Link
              key={path}
              to={path}
              className={cn(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 text-[0.88rem] font-medium transition-colors',
                isActive
                  ? 'bg-accent font-semibold text-accent-foreground'
                  : 'text-muted-foreground hover:bg-[rgba(124,111,160,0.06)] hover:text-foreground',
              )}
            >
              <Icon className="size-[22px]" />
              {label}
            </Link>
          );
        })}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Bottom section */}
        <div className="flex flex-col gap-1 border-t border-border pt-3 mt-3">
          {/* Settings */}
          <Link
            to="/settings"
            className={cn(
              'flex items-center gap-3 rounded-xl px-3 py-2.5 text-[0.88rem] font-medium transition-colors',
              location.pathname === '/settings'
                ? 'bg-accent font-semibold text-accent-foreground'
                : 'text-muted-foreground hover:bg-[rgba(124,111,160,0.06)] hover:text-foreground',
            )}
          >
            <Settings className="size-[22px]" />
            Settings
          </Link>

          {/* User section */}
          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left hover:bg-[rgba(124,111,160,0.06)] focus:outline-none">
                  <Avatar className="size-[34px]">
                    <AvatarImage src={user.avatar_url ?? undefined} />
                    <AvatarFallback className="bg-gradient-to-br from-accent to-primary text-[0.72rem] font-bold text-primary-foreground">
                      {getInitials(user.display_name)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex flex-col overflow-hidden">
                    <span className="truncate text-[0.82rem] font-medium text-foreground">
                      {user.display_name}
                    </span>
                    <span className="truncate text-[0.68rem] text-muted-foreground">
                      {user.email}
                    </span>
                  </div>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-48">
                <DropdownMenuItem onClick={onLogout}>
                  <LogOut className="mr-2 size-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </nav>
  );
}
