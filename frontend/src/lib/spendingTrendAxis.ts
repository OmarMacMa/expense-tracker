import type { SpendingTrend } from '@/hooks/useInsights';

export const MONTH_NAMES = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** The API's dense current series covers the selected window, including future
 * days. Never infer the window from today's cutoff or the comparison series. */
export function getTrendDomain(data: SpendingTrend): [number, number] {
  const days = data.current_series.map((point) => point.day);
  if (days.length === 0) return [1, 2];
  const first = Math.min(...days);
  const last = Math.max(...days);
  return first === last ? [first - 0.5, last + 0.5] : [first, last];
}

export function getTrendTicks(
  domain: [number, number],
  plotWidth: number,
  timeframe: SpendingTrend['timeframe'],
  year: number,
): number[] {
  const [first, last] = domain;
  const capacity = Math.max(1, Math.floor(plotWidth / 36));
  if (timeframe === 'yearly') {
    const jan1 = Date.UTC(year, 0, 1);
    const months = MONTH_NAMES.map(
      (_, month) =>
        Math.round((Date.UTC(year, month, 1) - jan1) / 86_400_000) + 1,
    ).filter((day) => day >= first && day <= last);
    const stride = Math.max(1, Math.ceil(months.length / (capacity + 1)));
    return months.filter((_, index) => index % stride === 0);
  }
  const start = Math.ceil(first);
  const end = Math.floor(last);
  const step = Math.max(1, Math.ceil((end - start) / capacity));
  // Do not append the last day: that would introduce a shorter final interval.
  return Array.from(
    { length: Math.floor((end - start) / step) + 1 },
    (_, index) => start + index * step,
  );
}

export function trendDayDate(day: number, year: number): Date {
  return new Date(Date.UTC(year, 0, day));
}
