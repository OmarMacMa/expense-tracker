export const PERIOD_OPTIONS = [
  { value: 'this_week', label: 'This Week' },
  { value: 'last_week', label: 'Last Week' },
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'ytd', label: 'Year to Date' },
] as const;

export type AnalysisPeriod = (typeof PERIOD_OPTIONS)[number]['value'];

export interface PeriodSelection {
  period: AnalysisPeriod;
  month?: string;
}

export function readPeriodSelection(value: {
  period?: string;
  month?: string;
}): PeriodSelection | null {
  if (value.month && /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value.month)) {
    return { period: 'this_month', month: value.month };
  }
  const period = PERIOD_OPTIONS.find((option) => option.value === value.period);
  return period ? { period: period.value } : null;
}

export function parseStoredPeriod(raw: string | null): PeriodSelection | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value !== 'object' || value === null) return null;
    return readPeriodSelection({
      period:
        'period' in value && typeof value.period === 'string'
          ? value.period
          : undefined,
      month:
        'month' in value && typeof value.month === 'string'
          ? value.month
          : undefined,
    });
  } catch {
    // Stored preferences can outlive an old build or be edited outside the app.
    return null;
  }
}

export function periodLabel(selection: PeriodSelection): string {
  if (selection.month) {
    const [year, month] = selection.month.split('-').map(Number);
    const date = new Date(0);
    date.setUTCFullYear(year, month - 1, 1);
    return new Intl.DateTimeFormat('en-US', {
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(date);
  }
  return (
    PERIOD_OPTIONS.find((option) => option.value === selection.period)?.label ??
    'This Month'
  );
}
