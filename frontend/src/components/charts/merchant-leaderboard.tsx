import type { MerchantLeaderboard as MerchantLeaderboardData } from '@/hooks/useInsights';
import { formatCurrency } from '@/lib/expense-utils';

interface MerchantLeaderboardProps {
  data: MerchantLeaderboardData[];
  maxItems?: number;
  currencyCode?: string;
}

export function MerchantLeaderboard({
  data,
  maxItems = 10,
  currencyCode = 'USD',
}: MerchantLeaderboardProps) {
  const top5 = data.slice(0, maxItems);

  return (
    <div>
      {top5.map((merchant, index) => (
        <div
          key={merchant.merchant}
          className="flex items-center gap-3 py-2.5"
          style={{
            borderBottom:
              index < top5.length - 1 ? '1px solid var(--border)' : undefined,
          }}
        >
          <div className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-accent-foreground">
            {index + 1}
          </div>
          <div className="flex-1 text-sm text-foreground">
            {merchant.merchant}
          </div>
          <div className="text-sm font-semibold text-foreground">
            {formatCurrency(merchant.total, currencyCode)}
          </div>
        </div>
      ))}
      {top5.length === 0 && (
        <p className="py-4 text-center text-sm text-muted-foreground">
          No merchant data yet
        </p>
      )}
    </div>
  );
}
