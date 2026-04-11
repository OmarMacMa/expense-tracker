import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import { useExpenseList, type ExpenseFilters } from '@/hooks/useExpenses';
import { usePeriod } from '@/hooks/usePeriod';
import { FilterBar } from '@/components/expenses/filter-bar';
import {
  TransactionGroup,
  groupExpensesByDate,
} from '@/components/expenses/transaction-group';

function TransactionListSkeleton() {
  return (
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
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

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-secondary text-3xl">
        📭
      </div>
      <h3 className="mb-1 text-lg font-semibold text-foreground">
        {hasFilters ? 'No matching transactions' : 'No transactions yet'}
      </h3>
      <p className="max-w-xs text-sm text-muted-foreground">
        {hasFilters
          ? 'Try adjusting your filters or search terms.'
          : 'Add your first expense to get started.'}
      </p>
    </div>
  );
}

export default function TransactionList() {
  const { period: globalPeriod } = usePeriod();
  const [localFilters, setLocalFilters] = useState<ExpenseFilters>({});
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Merge shared period with local overrides; strip cleared values so
  // deselecting a chip falls back to globalPeriod instead of undefined.
  const filters = useMemo<ExpenseFilters>(() => {
    const active = Object.fromEntries(
      Object.entries(localFilters).filter(([, v]) => v),
    );
    return { period: globalPeriod, ...active };
  }, [globalPeriod, localFilters]);

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    isError,
  } = useExpenseList(filters);

  const allExpenses = useMemo(
    () => data?.pages.flatMap((page) => page.data) ?? [],
    [data],
  );
  const groups = useMemo(() => groupExpensesByDate(allExpenses), [allExpenses]);

  // Only user-set overrides count as "active filters" for empty-state messaging
  const hasFilters = Object.values(localFilters).some(Boolean);

  // Infinite scroll via IntersectionObserver
  const handleIntersect = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    [hasNextPage, isFetchingNextPage, fetchNextPage],
  );

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(handleIntersect, {
      rootMargin: '200px',
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [handleIntersect]);

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground md:text-[1.3rem]">
          Transactions
        </h1>
        {allExpenses.length > 0 && (
          <p className="mt-1 text-sm text-muted-foreground">
            {allExpenses.length} transaction
            {allExpenses.length !== 1 ? 's' : ''}
          </p>
        )}
      </div>

      {/* Filters */}
      <FilterBar filters={filters} onFiltersChange={setLocalFilters} />

      {/* Content */}
      {isLoading ? (
        <TransactionListSkeleton />
      ) : isError ? (
        <div className="py-12 text-center text-sm text-destructive">
          Failed to load transactions. Please try again.
        </div>
      ) : groups.length === 0 ? (
        <EmptyState hasFilters={hasFilters} />
      ) : (
        <div className="space-y-1">
          {groups.map((group) => (
            <TransactionGroup key={group.label} group={group} />
          ))}
        </div>
      )}

      {/* Infinite scroll sentinel */}
      <div ref={sentinelRef} className="h-px" />

      {/* Loading more indicator */}
      {isFetchingNextPage && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span className="ml-2 text-sm text-muted-foreground">
            Loading more…
          </span>
        </div>
      )}
    </div>
  );
}
