import { useMemo } from 'react';
import { Link } from 'react-router';
import { ArrowLeft, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useTags } from '@/hooks/useTags';

export default function SettingsTags() {
  const { data: tags, isLoading } = useTags();

  const sorted = useMemo(
    () => [...(tags ?? [])].sort((a, b) => a.name.localeCompare(b.name)),
    [tags],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="size-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" asChild>
          <Link to="/settings">
            <ArrowLeft className="size-5" />
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">Tags</h1>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 rounded-xl border bg-card p-4 shadow-sm">
        <Info className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Tags are automatically created when used on expenses. They cannot be
          manually added or removed here.
        </p>
      </div>

      {/* Tag chips */}
      <div className="rounded-xl border bg-card p-4 shadow-sm">
        {sorted.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {sorted.map((tag) => (
              <Badge key={tag.id} variant="secondary" className="text-sm">
                #{tag.name}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="py-4 text-center text-muted-foreground">
            No tags yet. Tags will appear here once used on expenses.
          </p>
        )}
      </div>
    </div>
  );
}
