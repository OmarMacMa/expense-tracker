import { createContext, useContext, useState, type ReactNode } from 'react';

export type Period = 'this_week' | 'this_month';

interface PeriodContextValue {
  period: Period;
  setPeriod: (p: Period) => void;
}

const PeriodContext = createContext<PeriodContextValue>({
  period: 'this_month',
  setPeriod: () => {},
});

export function PeriodProvider({ children }: { children: ReactNode }) {
  const [period, setPeriod] = useState<Period>('this_month');
  return (
    <PeriodContext.Provider value={{ period, setPeriod }}>
      {children}
    </PeriodContext.Provider>
  );
}

export function usePeriod() {
  return useContext(PeriodContext);
}
