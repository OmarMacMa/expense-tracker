import { Pencil, Trash2, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { LimitProgress } from '@/types/api';
import { useCurrency } from '@/hooks/useCurrency';

function getStatusColor(status: string) {
  switch (status) {
    case 'ok':
      return {
        bar: 'bg-green-500',
        text: 'text-green-600',
        bg: 'bg-green-100',
        track: 'bg-green-100',
      };
    case 'warning':
      return {
        bar: 'bg-amber-500',
        text: 'text-amber-600',
        bg: 'bg-amber-100',
        track: 'bg-amber-100',
      };
    case 'critical':
      return {
        bar: 'bg-red-500',
        text: 'text-red-600',
        bg: 'bg-red-100',
        track: 'bg-red-100',
      };
    case 'exceeded':
      return {
        bar: 'bg-purple-600',
        text: 'text-[#2E064F]',
        bg: 'bg-purple-100',
        track: 'bg-purple-100',
      };
    default:
      return {
        bar: 'bg-gray-400',
        text: 'text-gray-500',
        bg: 'bg-gray-100',
        track: 'bg-gray-100',
      };
  }
}

interface LimitCardProps {
  limit: LimitProgress;
  onEdit: (limit: LimitProgress) => void;
  onDelete: (limit: LimitProgress) => void;
}

export function LimitCard({ limit, onEdit, onDelete }: LimitCardProps) {
  const colors = getStatusColor(limit.status);
  const { format } = useCurrency();
  const progressPct = Math.min(parseFloat(limit.progress) * 100, 100);
  const displayPct = parseFloat(limit.progress) * 100;

  return (
    <div className="rounded-lg border bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-foreground sm:text-base">
              {limit.name}
            </h3>
            <span className="inline-flex shrink-0 items-center rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
              {limit.timeframe === 'weekly' ? 'Weekly' : 'Monthly'}
            </span>
          </div>
          {limit.filters.length > 0 && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {limit.filters.map((f) => f.filter_display_name || f.filter_value).join(', ')}
            </p>
          )}
        </div>

        <div className="flex shrink-0 gap-1">
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onEdit(limit)}
            aria-label={`Edit ${limit.name}`}
          >
            <Pencil className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onDelete(limit)}
            aria-label={`Delete ${limit.name}`}
          >
            <Trash2 className="size-3.5 text-destructive" />
          </Button>
        </div>
      </div>

      {/* Progress bar */}
      <div
        className={cn('h-2 w-full overflow-hidden rounded-full', colors.track)}
      >
        <div
          className={cn('h-full rounded-full transition-all', colors.bar)}
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Details row */}
      <div className="mt-2 flex items-center justify-between text-xs sm:text-sm">
        <span className="text-muted-foreground">
          <span className={cn('font-semibold', colors.text)}>
            {format(limit.spent)}
          </span>
          {' / '}
          {format(limit.threshold_amount)}
        </span>

        <div className="flex items-center gap-2">
          <span className={cn('font-semibold', colors.text)}>
            {displayPct.toFixed(0)}%
          </span>
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Clock className="size-3" />
            {limit.days_remaining}d left
          </span>
        </div>
      </div>
    </div>
  );
}
