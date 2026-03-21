import { Link } from 'react-router';
import { ArrowLeft, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useMembers } from '@/hooks/useMembers';

const MAX_MEMBERS = 10;

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function SettingsMembers() {
  const { data: members, isLoading } = useMembers();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="size-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const count = members?.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" asChild>
          <Link to="/settings">
            <ArrowLeft className="size-5" />
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">Members</h1>
      </div>

      {/* Member count */}
      <div className="flex items-center gap-2 rounded-xl border bg-card px-4 py-3 shadow-sm">
        <Users className="size-5 text-muted-foreground" />
        <span className="text-sm font-medium">
          {count} / {MAX_MEMBERS} members
        </span>
      </div>

      {/* Member list */}
      <div className="rounded-xl border bg-card shadow-sm">
        <ul className="divide-y">
          {members?.map((member) => (
            <li key={member.id} className="flex items-center gap-4 px-4 py-3">
              <Avatar className="size-10">
                <AvatarImage src={member.avatar_url ?? undefined} />
                <AvatarFallback>
                  {getInitials(member.display_name)}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{member.display_name}</p>
                <p className="truncate text-sm text-muted-foreground">
                  {member.email}
                </p>
              </div>
              <span className="shrink-0 text-xs text-muted-foreground">
                Joined {formatDate(member.joined_at)}
              </span>
            </li>
          ))}
          {count === 0 && (
            <li className="px-4 py-8 text-center text-muted-foreground">
              No members found.
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
