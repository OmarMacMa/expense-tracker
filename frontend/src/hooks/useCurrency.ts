import { useCallback } from 'react';
import { useSpace } from './useSpace';
import { formatCurrency } from '@/lib/expense-utils';

export function useCurrency() {
  const { data: space } = useSpace();
  const currencyCode = space?.currency_code ?? 'USD';

  const format = useCallback(
    (amount: string | number) => formatCurrency(amount, currencyCode),
    [currencyCode],
  );

  return { format, currencyCode };
}
