import { useState, useMemo } from 'react';
import { Link } from 'react-router';
import { TrendingDown, TrendingUp } from 'lucide-react';
import { useExpenseList, type ExpenseFilters } from '@/hooks/useExpenses';
import { usePeriod } from '@/hooks/usePeriod';
import {
  useInsightsSummary,
  useSpendingTrend,
  useCategoryBreakdown,
  useMerchantLeaderboard,
  useSpenderBreakdown,
} from '@/hooks/useInsights';
import { useMembers } from '@/hooks/useMembers';
import { useCategories } from '@/hooks/useCategories';
import { useTags } from '@/hooks/useTags';
import { usePaymentMethods } from '@/hooks/usePaymentMethods';
import { useMerchantList } from '@/hooks/useMerchants';
import { FilterBar } from '@/components/expenses/filter-bar';
import { SpendingTrendChart } from '@/components/charts/spending-trend-chart';
import { CategoryDonutChart } from '@/components/charts/category-donut-chart';
import { MerchantLeaderboard } from '@/components/charts/merchant-leaderboard';
import { SpenderBreakdownChart } from '@/components/charts/spender-breakdown-chart';
import {
  TransactionGroup,
  groupExpensesByDate,
} from '@/components/expenses/transaction-group';
import { useCurrency } from '@/hooks/useCurrency';
import { cn } from '@/lib/utils';

function ChartCard({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'rounded-2xl bg-card p-5 shadow-[var(--shadow-card)]',
        className,
      )}
    >
      <h3 className="mb-4 text-[13px] font-bold uppercase tracking-widest text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-3">
      <div className="h-4 w-24 rounded bg-secondary" />
      <div className="h-[160px] rounded-xl bg-secondary" />
    </div>
  );
}

function TransactionListSkeleton() {
  return (
    <div className="space-y-3">
      {[...Array(4)].map((_, i) => (
        <div
          key={i}
          className="flex animate-pulse items-center gap-3 rounded-2xl bg-card p-4 shadow-[var(--shadow-card)]"
        >
          <div className="h-10 w-10 shrink-0 rounded-full bg-secondary" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-32 rounded bg-secondary" />
            <div className="h-3 w-48 rounded bg-secondary" />
          </div>
          <div className="h-5 w-16 rounded bg-secondary" />
        </div>
      ))}
    </div>
  );
}

export default function Insights() {
  const { period: globalPeriod } = usePeriod();
  const [localFilters, setLocalFilters] = useState<ExpenseFilters>({});
  const { format, currencyCode } = useCurrency();

  // For data queries: use local period if set, otherwise fall back to global
  const queryFilters = useMemo<ExpenseFilters>(() => {
    const active = Object.fromEntries(
      Object.entries(localFilters).filter(([, v]) => v),
    );
    if (!active.period) active.period = globalPeriod;
    return active;
  }, [globalPeriod, localFilters]);

  // Filter data sources
  const { data: members } = useMembers();
  const { data: categories } = useCategories();
  const { data: tagList } = useTags();
  const { data: paymentMethodList } = usePaymentMethods();
  const { data: merchantList } = useMerchantList();

  // Insights data
  const { data: summary } = useInsightsSummary(queryFilters);
  const { data: trendData, isLoading: trendLoading } =
    useSpendingTrend(queryFilters);
  const { data: categoryData, isLoading: categoryLoading } =
    useCategoryBreakdown(queryFilters);
  const { data: merchantData, isLoading: merchantLoading } =
    useMerchantLeaderboard(queryFilters);
  const { data: spenderData, isLoading: spenderLoading } =
    useSpenderBreakdown(queryFilters);

  // Transaction list (same filters)
  const { data: expensePages, isLoading: expensesLoading } =
    useExpenseList(queryFilters);

  const allExpenses = useMemo(
    () => (expensePages?.pages[0]?.data ?? []).slice(0, 15),
    [expensePages],
  );
  const groups = useMemo(() => groupExpensesByDate(allExpenses), [allExpenses]);

  const deltaSign = summary?.delta_pct
    ? summary.delta_pct > 0
      ? 'up'
      : 'down'
    : null;

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground md:text-[1.3rem]">
          Insights
        </h1>
        {summary && (
          <div className="mt-1 flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {summary.period_label}
            </span>
            <span className="text-lg font-bold text-foreground">
              {format(summary.total_spent)}
            </span>
            {deltaSign && (
              <span
                className={cn(
                  'flex items-center gap-0.5 text-xs font-semibold',
                  deltaSign === 'up' ? 'text-destructive' : 'text-[#2E7D5B]',
                )}
              >
                {deltaSign === 'up' ? (
                  <TrendingUp className="h-3.5 w-3.5" />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5" />
                )}
                {Math.abs(summary.delta_pct!).toFixed(0)}% vs avg
              </span>
            )}
          </div>
        )}
      </div>

      {/* Filter bar */}
      <FilterBar
        filters={localFilters}
        onFiltersChange={setLocalFilters}
        spenders={members}
        categories={categories}
        merchants={merchantList?.map((m) => m.name) ?? []}
        tags={tagList}
        paymentMethods={paymentMethodList}
        showSearch={false}
        showPeriodChips
      />

      {/* Main content — desktop split, mobile stacked */}
      <div className="flex flex-col gap-5 lg:flex-row">
        {/* Charts panel */}
        <div className="flex flex-col gap-4 lg:w-[60%] lg:shrink-0">
          {/* Spending trend */}
          <ChartCard title="Spending Trend">
            {trendLoading || !trendData ? (
              <ChartSkeleton />
            ) : (
              <SpendingTrendChart
                data={trendData}
                periodLabel={queryFilters.period ?? 'this_month'}
                currencyCode={currencyCode}
              />
            )}
          </ChartCard>

          {/* Two-column grid for category + merchant on desktop */}
          <div className="grid gap-4 md:grid-cols-2">
            {/* Category donut */}
            <ChartCard title="By Category">
              {categoryLoading || !categoryData ? (
                <ChartSkeleton />
              ) : categoryData.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No category data yet
                </p>
              ) : (
                <CategoryDonutChart
                  data={categoryData}
                  totalAmount={summary?.total_spent ?? '0'}
                  currencyCode={currencyCode}
                />
              )}
            </ChartCard>

            {/* Merchant leaderboard */}
            <ChartCard title="Top Merchants">
              {merchantLoading || !merchantData ? (
                <ChartSkeleton />
              ) : (
                <MerchantLeaderboard
                  data={merchantData}
                  maxItems={10}
                  currencyCode={currencyCode}
                />
              )}
            </ChartCard>
          </div>

          {/* Spender breakdown */}
          <ChartCard title="By Spender">
            {spenderLoading || !spenderData ? (
              <ChartSkeleton />
            ) : (
              <SpenderBreakdownChart
                data={spenderData}
                currencyCode={currencyCode}
              />
            )}
          </ChartCard>
        </div>

        {/* Transaction list panel */}
        <div className="min-w-0 lg:flex-1">
          <div className="rounded-2xl bg-card p-4 shadow-[var(--shadow-card)] md:p-5">
            <h3 className="mb-4 text-[13px] font-bold uppercase tracking-widest text-muted-foreground">
              Transactions
            </h3>

            {expensesLoading ? (
              <TransactionListSkeleton />
            ) : groups.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-2xl">
                  📭
                </div>
                <p className="text-sm text-muted-foreground">
                  No transactions match these filters
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {groups.map((group) => (
                  <TransactionGroup key={group.label} group={group} />
                ))}
              </div>
            )}

            {groups.length > 0 && (
              <div className="mt-3 text-center">
                <Link
                  to="/transactions"
                  className="text-sm font-medium text-primary hover:underline"
                >
                  View all transactions →
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
