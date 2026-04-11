import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';

export type Period = 'this_week' | 'this_month';

const STORAGE_KEY = 'expense-tracker:period';
const VALID_PERIODS: Period[] = ['this_week', 'this_month'];

interface PeriodContextValue {
  period: Period;
  setPeriod: (p: Period) => void;
}

const PeriodContext = createContext<PeriodContextValue | undefined>(undefined);

function readStoredPeriod(): Period {
  const stored = localStorage.getItem(STORAGE_KEY);
  return VALID_PERIODS.includes(stored as Period)
    ? (stored as Period)
    : 'this_month';
}

export function PeriodProvider({ children }: { children: ReactNode }) {
  const [period, setPeriod] = useState<Period>(readStoredPeriod);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, period);
  }, [period]);

  return (
    <PeriodContext.Provider value={{ period, setPeriod }}>
      {children}
    </PeriodContext.Provider>
  );
}

export function usePeriod() {
  const ctx = useContext(PeriodContext);
  if (!ctx) {
    throw new Error('usePeriod must be used within a PeriodProvider');
  }
  return ctx;
}
