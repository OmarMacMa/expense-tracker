import {
  ResponsiveContainer,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Line,
  ReferenceLine,
  ComposedChart,
  usePlotArea,
} from 'recharts';
import type {
  SpendingTrend,
  SpendingTrendTimeframe,
} from '@/hooks/useInsights';
import { formatCurrency, getCurrencySymbol } from '@/lib/expense-utils';
import {
  getTrendDomain,
  getTrendTicks,
  MONTH_NAMES,
  trendDayDate,
  WEEKDAYS,
} from '@/lib/spendingTrendAxis';

const PERIOD_DISPLAY: Record<string, string> = {
  this_week: 'This week',
  last_week: 'Last week',
  this_month: 'This month',
  last_month: 'Last month',
  ytd: 'Year to date',
};

const AVG_LABEL: Partial<Record<SpendingTrendTimeframe, string>> = {
  monthly: '3-month avg',
  quarterly: '3-quarter avg',
};

interface SpendingTrendChartProps {
  data: SpendingTrend;
  periodLabel?: string;
  currencyCode?: string;
}

/** Converts a 1-based day-of-year to its month abbreviation for the given year. */
function dayOfYearToMonthName(day: number, year: number): string {
  const date = trendDayDate(day, year);
  return MONTH_NAMES[date.getUTCMonth()];
}

/** Converts a 1-based day-of-year to a "Mon DD" string (zero-padded day). */
function dayOfYearToMonthDay(day: number, year: number): string {
  const date = trendDayDate(day, year);
  return `${MONTH_NAMES[date.getUTCMonth()]} ${String(date.getUTCDate()).padStart(2, '0')}`;
}

function TrendXAxis({ data }: Pick<SpendingTrendChartProps, 'data'>) {
  const plotArea = usePlotArea();
  const domain = getTrendDomain(data);
  return (
    <XAxis
      dataKey="day"
      type="number"
      scale="linear"
      domain={domain}
      allowDataOverflow
      padding={{ left: 12, right: 12 }}
      ticks={getTrendTicks(
        domain,
        Math.max(0, (plotArea?.width ?? 0) - 24),
        data.timeframe,
        data.year,
      )}
      interval={0}
      tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
      tickLine={false}
      axisLine={false}
      tickFormatter={(day: number) => {
        if (data.timeframe === 'weekly') return WEEKDAYS[(day - 1) % 7];
        if (data.timeframe === 'yearly')
          return dayOfYearToMonthName(day, data.year);
        return `${day}`;
      }}
    />
  );
}

export function SpendingTrendChart({
  data,
  periodLabel,
  currencyCode = 'USD',
}: SpendingTrendChartProps) {
  const symbol = getCurrencySymbol(currencyCode);
  const isWeekly = data.timeframe === 'weekly';
  const isYearly = data.timeframe === 'yearly';
  const hasAverage =
    data.average_series.length > 0 && data.average_period_count !== 0;
  const avgLabel = isWeekly
    ? data.average_period_count != null
      ? `${data.average_period_count}-week avg`
      : 'Weekly avg'
    : AVG_LABEL[data.timeframe];
  const trendYear = data.year;
  const domain = getTrendDomain(data);
  const currentDay =
    data.current_day != null &&
    data.current_day >= domain[0] &&
    data.current_day <= domain[1]
      ? data.current_day
      : null;
  const chartData = data.current_series.map((point) => {
    const avgPoint = data.average_series.find((a) => a.day === point.day);
    return {
      day: point.day,
      current:
        currentDay !== null && point.day > currentDay
          ? null
          : parseFloat(point.cumulative),
      ...(avgPoint
        ? { average: parseFloat(avgPoint.cumulative) }
        : { average: null }),
    };
  });

  return (
    <div data-testid="spending-trend-chart">
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart
          data={chartData}
          margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
        >
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7C6FA0" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#7C6FA0" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="none"
            stroke="var(--border)"
            vertical={false}
          />
          <TrendXAxis data={data} />
          <YAxis
            width="auto"
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) =>
              v >= 1000 ? `${symbol}${(v / 1000).toFixed(1)}k` : `${symbol}${v}`
            }
          />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const currentValue = payload.find(
                (item) => item.dataKey === 'current',
              )?.value;
              const averageValue = payload.find(
                (item) => item.dataKey === 'average',
              )?.value;
              return (
                <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-[var(--shadow-card)]">
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    {isWeekly
                      ? WEEKDAYS[(label as number) - 1] || `Day ${label}`
                      : isYearly
                        ? dayOfYearToMonthDay(label as number, trendYear)
                        : `Day ${label}`}
                  </p>
                  {currentValue != null && (
                    <p className="text-sm font-semibold text-foreground">
                      Current:{' '}
                      {formatCurrency(String(currentValue), currencyCode)}
                    </p>
                  )}
                  {averageValue != null && (
                    <p className="text-sm text-muted-foreground">
                      Average:{' '}
                      {formatCurrency(String(averageValue), currencyCode)}
                    </p>
                  )}
                </div>
              );
            }}
          />
          <Area
            type="monotone"
            dataKey="current"
            stroke="#7C6FA0"
            strokeWidth={2.5}
            fill="url(#areaGradient)"
          />
          {hasAverage && (
            <Line
              type="monotone"
              dataKey="average"
              stroke="var(--muted-foreground)"
              strokeWidth={2}
              strokeDasharray="6 4"
              strokeOpacity={0.4}
              dot={false}
              connectNulls
            />
          )}
          {currentDay !== null && (
            <ReferenceLine
              x={currentDay}
              stroke="#7C6FA0"
              strokeDasharray="3 3"
              strokeOpacity={0.5}
              label={{
                value: 'Today',
                position:
                  currentDay <= (domain[0] + domain[1]) / 2
                    ? 'insideTopLeft'
                    : 'insideTopRight',
                offset: 6,
                fill: 'var(--muted-foreground)',
                fontSize: 10,
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-2.5 flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-[#7C6FA0]" />
          {PERIOD_DISPLAY[periodLabel ?? ''] ?? 'Current period'}
        </span>
        {hasAverage && avgLabel && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-muted-foreground opacity-40" />
            {avgLabel}
          </span>
        )}
      </div>
    </div>
  );
}
