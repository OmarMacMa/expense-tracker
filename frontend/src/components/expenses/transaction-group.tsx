import type { Expense } from '@/types/api';
import { TransactionItem } from './transaction-item';
import { getDateGroup } from '@/lib/expense-utils';

export interface DateGroup {
  label: string;
  expenses: Expense[];
}

export function groupExpensesByDate(expenses: Expense[]): DateGroup[] {
  const groupOrder = ['Today', 'Yesterday', 'This Week', 'Earlier'];
  const groups = new Map<string, Expense[]>();

  for (const expense of expenses) {
    const label = getDateGroup(expense.purchase_datetime);
    const existing = groups.get(label) ?? [];
    existing.push(expense);
    groups.set(label, existing);
  }

  return groupOrder
    .filter((label) => groups.has(label))
    .map((label) => ({ label, expenses: groups.get(label)! }));
}

interface TransactionGroupProps {
  group: DateGroup;
}

export function TransactionGroup({ group }: TransactionGroupProps) {
  return (
    <div className="mb-2">
      <div className="px-1 pb-2 pt-3 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
        {group.label}
      </div>
      <div className="flex flex-col gap-2">
        {group.expenses.map((expense) => (
          <TransactionItem key={expense.id} expense={expense} />
        ))}
      </div>
    </div>
  );
}
