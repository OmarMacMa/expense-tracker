import { Link } from 'react-router';
import { Settings, LogOut } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface TopBarProps {
  user: {
    display_name: string;
    avatar_url: string | null;
    email: string;
  } | null;
  spaceName: string | undefined;
  onLogout: () => void;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function TopBar({ user, spaceName, onLogout }: TopBarProps) {
  return (
    <header className="flex items-center justify-between px-5 pt-3 pb-1">
      {/* Space name */}
      <div className="rounded-full bg-[#F3F1F8] px-3 py-1.5 text-[0.8rem] font-medium text-muted-foreground">
        {spaceName ?? 'My Space'}
      </div>

      {/* Avatar with dropdown */}
      {user && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="focus:outline-none">
              <Avatar className="size-9">
                <AvatarImage src={user.avatar_url ?? undefined} />
                <AvatarFallback className="bg-gradient-to-br from-accent to-primary text-[0.8rem] font-bold text-primary-foreground">
                  {getInitials(user.display_name)}
                </AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem asChild>
              <Link to="/settings">
                <Settings className="mr-2 size-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={onLogout}>
              <LogOut className="mr-2 size-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </header>
  );
}
