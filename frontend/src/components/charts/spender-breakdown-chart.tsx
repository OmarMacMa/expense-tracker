import type { SpenderBreakdown } from '@/hooks/useInsights';
import { formatCurrency } from '@/lib/expense-utils';

interface SpenderBreakdownChartProps {
  data: SpenderBreakdown[];
  currencyCode?: string;
}

export function SpenderBreakdownChart({
  data,
  currencyCode = 'USD',
}: SpenderBreakdownChartProps) {
  return (
    <div className="flex flex-col gap-4">
      {data.map((spender) => {
        const pct = parseFloat(spender.percentage);
        const initial = spender.display_name.charAt(0).toUpperCase();
        return (
          <div key={spender.spender_id} className="flex items-center gap-3">
            {spender.avatar_url ? (
              <img
                src={spender.avatar_url}
                alt={spender.display_name}
                className="h-8 w-8 shrink-0 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-bold text-accent-foreground">
                {initial}
              </div>
            )}

            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-baseline justify-between gap-2">
                <span className="truncate text-sm font-medium text-foreground">
                  {spender.display_name}
                </span>
                <span className="shrink-0 text-sm font-semibold text-foreground">
                  {formatCurrency(spender.total, currencyCode)}
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-secondary">
                <div
                  className="h-2 rounded-full bg-primary transition-all"
                  style={{ width: `${Math.max(pct, 2)}%` }}
                />
              </div>
              <span className="mt-0.5 text-[11px] text-muted-foreground">
                {pct.toFixed(1)}%
              </span>
            </div>
          </div>
        );
      })}
      {data.length === 0 && (
        <p className="py-4 text-center text-sm text-muted-foreground">
          No spender data yet
        </p>
      )}
    </div>
  );
}
