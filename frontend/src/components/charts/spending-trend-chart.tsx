import {
  ResponsiveContainer,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Line,
  ComposedChart,
} from 'recharts';
import type { SpendingTrend } from '@/hooks/useInsights';
import { formatCurrency, getCurrencySymbol } from '@/lib/expense-utils';

interface SpendingTrendChartProps {
  data: SpendingTrend;
  currencyCode?: string;
}

export function SpendingTrendChart({
  data,
  currencyCode = 'USD',
}: SpendingTrendChartProps) {
  const symbol = getCurrencySymbol(currencyCode);
  const isWeekly = data.timeframe === 'weekly';
  const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const chartData = data.current_series.map((point) => {
    const avgPoint = data.average_series.find((a) => a.day === point.day);
    return {
      day: point.day,
      current: parseFloat(point.cumulative),
      ...(avgPoint
        ? { average: parseFloat(avgPoint.cumulative) }
        : { average: null }),
    };
  });

  return (
    <div>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart
          data={chartData}
          margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
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
          <XAxis
            dataKey="day"
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) =>
              isWeekly ? weekdays[(v - 1) % 7] || `${v}` : `${v}`
            }
          />
          <YAxis
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
              return (
                <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-[var(--shadow-card)]">
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    {isWeekly
                      ? weekdays[(label as number) - 1] || `Day ${label}`
                      : `Day ${label}`}
                  </p>
                  <p className="text-sm font-semibold text-foreground">
                    Current:{' '}
                    {formatCurrency(
                      String(payload[0]?.value ?? '0'),
                      currencyCode,
                    )}
                  </p>
                  {payload[1] && payload[1].value != null && (
                    <p className="text-sm text-muted-foreground">
                      Average:{' '}
                      {formatCurrency(
                        String(payload[1]?.value ?? '0'),
                        currencyCode,
                      )}
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
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-2.5 flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-[#7C6FA0]" />
          {isWeekly ? 'This week' : 'This month'}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-muted-foreground opacity-40" />
          {isWeekly ? '3-week avg' : '3-month avg'}
        </span>
      </div>
    </div>
  );
}
