import { useState } from 'react';
import { Link } from 'react-router';
import {
  useInsightsSummary,
  useSpendingTrend,
  useCategoryBreakdown,
  useMerchantLeaderboard,
  useLimitProgress,
} from '@/hooks/useInsights';
import { useExpenseList } from '@/hooks/useExpenses';
import { formatCurrency } from '@/lib/expense-utils';
import { useCurrency } from '@/hooks/useCurrency';
import { cn } from '@/lib/utils';
import { SpendingTrendChart } from '@/components/charts/spending-trend-chart';
import { CategoryDonutChart } from '@/components/charts/category-donut-chart';
import { MerchantLeaderboard } from '@/components/charts/merchant-leaderboard';
import { TransactionItem } from '@/components/expenses/transaction-item';
import type { LimitProgress } from '@/types/api';

type Period = 'this_week' | 'this_month';

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-muted', className)} />;
}

function LimitAlertCard({
  limit,
  currencyCode,
}: {
  limit: LimitProgress;
  currencyCode: string;
}) {
  const pct = parseFloat(limit.progress) * 100;
  const barWidth = Math.min(pct, 100);

  const statusConfig: Record<
    string,
    { label: string; badgeBg: string; badgeText: string; barColor: string }
  > = {
    warning: {
      label: 'Warning',
      badgeBg: 'bg-amber-100',
      badgeText: 'text-amber-600',
      barColor: 'bg-amber-500',
    },
    critical: {
      label: 'Critical',
      badgeBg: 'bg-red-100',
      badgeText: 'text-red-600',
      barColor: 'bg-red-500',
    },
    exceeded: {
      label: 'Exceeded',
      badgeBg: 'bg-purple-100',
      badgeText: 'text-purple-900',
      barColor: 'bg-purple-900',
    },
    ok: {
      label: 'On Track',
      badgeBg: 'bg-green-100',
      badgeText: 'text-green-600',
      barColor: 'bg-green-500',
    },
  };

  const cfg = statusConfig[limit.status] ?? statusConfig.ok;

  return (
    <div className="flex-1 rounded-2xl bg-card p-4 shadow-[var(--shadow-card)] md:px-5">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">
          {limit.name}
        </span>
        <span
          className={cn(
            'rounded-xl px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide',
            cfg.badgeBg,
            cfg.badgeText,
          )}
        >
          {pct.toFixed(0)}%
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full transition-all', cfg.barColor)}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <div className="mt-1.5 text-right text-xs text-muted-foreground">
        {formatCurrency(limit.spent, currencyCode)} /{' '}
        {formatCurrency(limit.threshold_amount, currencyCode)}
        {limit.status === 'exceeded' && ' · Exceeded'}
      </div>
    </div>
  );
}

export default function Home() {
  const [period, setPeriod] = useState<Period>('this_month');
  const { format, currencyCode } = useCurrency();

  const { data: summary, isLoading: summaryLoading } = useInsightsSummary({
    period,
  });
  const { data: trend, isLoading: trendLoading } = useSpendingTrend({
    period,
  });
  const { data: categories, isLoading: categoriesLoading } =
    useCategoryBreakdown({ period });
  const { data: merchants, isLoading: merchantsLoading } =
    useMerchantLeaderboard({ period });
  const { data: limits, isLoading: limitsLoading } = useLimitProgress();
  const { data: expensePages, isLoading: expensesLoading } = useExpenseList({
    period,
  });

  const expenses = expensePages?.pages.flatMap((p) => p.data) ?? [];
  const latestExpenses = expenses.slice(0, 5);
  const totalCount = expenses.length;

  const alertLimits =
    limits?.filter(
      (l: LimitProgress) =>
        l.status === 'warning' ||
        l.status === 'critical' ||
        l.status === 'exceeded',
    ) ?? [];

  const periodLabel = period === 'this_week' ? 'this week' : 'this month';

  return (
    <div className="mx-auto w-full max-w-[1100px] space-y-4">
      {/* Hero strip */}
      <div className="flex flex-col gap-3.5 rounded-2xl bg-card p-5 shadow-[var(--shadow-card)] md:flex-row md:items-center md:justify-between md:px-7">
        <div className="flex flex-col gap-1 md:flex-row md:items-baseline md:gap-5">
          {summaryLoading ? (
            <Skeleton className="h-9 w-48" />
          ) : (
            <span className="text-4xl font-bold tracking-tight text-foreground md:text-[2rem]">
              {format(summary?.total_spent ?? '0')}
            </span>
          )}
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground">
              Total spent {periodLabel}
            </span>
            {summary?.delta_pct != null && (
              <span
                className={cn(
                  'inline-flex w-fit items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
                  summary.delta_pct > 0
                    ? 'bg-red-50 text-red-600'
                    : 'bg-green-50 text-green-600',
                )}
              >
                {summary.delta_pct > 0 ? '↑' : '↓'}{' '}
                {Math.abs(summary.delta_pct).toFixed(1)}% vs avg
              </span>
            )}
          </div>
        </div>

        {/* Period toggle */}
        <div className="flex overflow-hidden rounded-full bg-muted">
          <button
            className={cn(
              'px-5 py-2 text-[13px] font-medium transition-all',
              period === 'this_week'
                ? 'rounded-full bg-primary text-primary-foreground'
                : 'text-muted-foreground',
            )}
            onClick={() => setPeriod('this_week')}
          >
            Week
          </button>
          <button
            className={cn(
              'px-5 py-2 text-[13px] font-medium transition-all',
              period === 'this_month'
                ? 'rounded-full bg-primary text-primary-foreground'
                : 'text-muted-foreground',
            )}
            onClick={() => setPeriod('this_month')}
          >
            Month
          </button>
        </div>
      </div>

      {/* Limit alerts */}
      {limitsLoading ? (
        <div className="flex flex-col gap-3 md:flex-row">
          <Skeleton className="h-24 flex-1" />
          <Skeleton className="h-24 flex-1" />
        </div>
      ) : alertLimits.length > 0 ? (
        <div>
          <h2 className="mb-3 text-[15px] font-bold text-foreground">
            Budget Alerts
          </h2>
          <div className="flex flex-col gap-3 md:flex-row">
            {alertLimits.slice(0, 3).map((limit: LimitProgress) => (
              <LimitAlertCard
                key={limit.id}
                limit={limit}
                currencyCode={currencyCode}
              />
            ))}
          </div>
        </div>
      ) : null}

      {/* Dashboard grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:grid-rows-[auto_auto]">
        {/* Spending Trend — spans 2 cols on desktop */}
        <div className="rounded-2xl bg-card p-5 shadow-[var(--shadow-card)] lg:col-span-2">
          <h3 className="mb-4 text-[15px] font-semibold text-foreground">
            Spending Trend
          </h3>
          {trendLoading ? (
            <Skeleton className="h-[200px] w-full" />
          ) : trend ? (
            <SpendingTrendChart
              data={trend}
              periodLabel={period}
              currencyCode={currencyCode}
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No trend data available
            </p>
          )}
        </div>

        {/* Category Donut — right column, spans 2 rows on desktop */}
        <div className="flex flex-col rounded-2xl bg-card p-5 shadow-[var(--shadow-card)] lg:row-span-2">
          <h3 className="mb-4 text-[15px] font-semibold text-foreground">
            Category Breakdown
          </h3>
          {categoriesLoading ? (
            <div className="flex flex-1 flex-col items-center gap-4">
              <Skeleton className="h-40 w-40 rounded-full" />
              <div className="w-full space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            </div>
          ) : categories && categories.length > 0 ? (
            <CategoryDonutChart
              data={categories}
              totalAmount={summary?.total_spent ?? '0'}
              currencyCode={currencyCode}
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No category data available
            </p>
          )}
        </div>

        {/* Merchant Leaderboard */}
        <div className="rounded-2xl bg-card p-5 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 text-[15px] font-semibold text-foreground">
            Top Merchants
          </h3>
          {merchantsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : merchants ? (
            <MerchantLeaderboard data={merchants} currencyCode={currencyCode} />
          ) : null}
        </div>

        {/* Latest Transactions */}
        <div className="rounded-2xl bg-card p-5 shadow-[var(--shadow-card)]">
          <div className="mb-2 flex items-baseline justify-between">
            <div>
              <h3 className="text-[15px] font-semibold text-foreground">
                Latest Transactions
              </h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {totalCount} transactions {periodLabel}
              </p>
            </div>
            <Link
              to="/transactions"
              className="text-[13px] font-medium text-primary hover:underline"
            >
              View all →
            </Link>
          </div>
          {expensesLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : latestExpenses.length > 0 ? (
            <div className="space-y-1.5">
              {latestExpenses.map((expense) => (
                <TransactionItem key={expense.id} expense={expense} />
              ))}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No transactions yet
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
