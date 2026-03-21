import { useNavigate } from 'react-router';
import type { Expense } from '@/types/api';
import { cn } from '@/lib/utils';
import {
  getCategoryColor,
  formatCurrency,
  getRelativeDate,
} from '@/lib/expense-utils';

interface TransactionItemProps {
  expense: Expense;
}

export function TransactionItem({ expense }: TransactionItemProps) {
  const navigate = useNavigate();
  const primaryCategory = expense.lines[0]?.category_name ?? 'Uncategorized';
  const color = getCategoryColor(primaryCategory);
  const initial = expense.merchant.charAt(0).toUpperCase();

  return (
    <div
      role="button"
      tabIndex={0}
      className="flex cursor-pointer items-center gap-3 rounded-2xl bg-card p-3.5 shadow-[var(--shadow-card)] transition-colors hover:bg-secondary/50 md:p-4"
      onClick={() => navigate(`/transactions/${expense.id}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          navigate(`/transactions/${expense.id}`);
        }
      }}
    >
      {/* Initial circle */}
      <div
        className={cn(
          'flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-base font-bold',
          color.circleBg,
          color.circleText,
        )}
      >
        {initial}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <div className="text-[15px] font-medium text-foreground">
          {expense.merchant}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">
            {getRelativeDate(expense.purchase_datetime)} ·{' '}
            {expense.spender.display_name}
          </span>
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
              color.bg,
              color.text,
            )}
          >
            {primaryCategory}
          </span>
        </div>
      </div>

      {/* Amount */}
      <div className="shrink-0 text-base font-bold text-foreground">
        {formatCurrency(expense.total_amount)}
      </div>
    </div>
  );
}
