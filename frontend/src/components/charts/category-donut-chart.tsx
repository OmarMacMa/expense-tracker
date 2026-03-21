import { ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import type { CategoryBreakdown } from '@/hooks/useInsights';
import { formatCurrency } from '@/lib/expense-utils';

interface CategoryDonutChartProps {
  data: CategoryBreakdown[];
  totalAmount: string;
  currencyCode?: string;
}

const CATEGORY_CHART_COLORS = [
  '#8BA89A', // sage
  '#A0889C', // dusty-rose
  '#7C6FA0', // lavender
  '#B5A24A', // butter
  '#C4B8D8', // light lavender fallback
];

export function CategoryDonutChart({
  data,
  totalAmount,
  currencyCode = 'USD',
}: CategoryDonutChartProps) {
  const chartData = data.map((cat) => ({
    name: cat.category_name,
    value: parseFloat(cat.total),
    percentage: parseFloat(cat.percentage),
  }));

  return (
    <div className="flex flex-col items-center gap-5 md:gap-6">
      <div className="relative">
        <ResponsiveContainer width={160} height={160}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={48}
              outerRadius={72}
              paddingAngle={2}
              dataKey="value"
              strokeWidth={0}
            >
              {chartData.map((_entry, index) => (
                <Cell
                  key={index}
                  fill={
                    CATEGORY_CHART_COLORS[index % CATEGORY_CHART_COLORS.length]
                  }
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Center text */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[10px] text-muted-foreground">Total</span>
          <span className="text-sm font-bold text-foreground">
            {formatCurrency(totalAmount, currencyCode)}
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex w-full flex-col gap-2.5">
        {data.map((cat, index) => (
          <div
            key={cat.category_id}
            className="flex items-center gap-2.5 text-[13px] text-muted-foreground"
          >
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
              style={{
                backgroundColor:
                  CATEGORY_CHART_COLORS[index % CATEGORY_CHART_COLORS.length],
              }}
            />
            <span className="flex-1">{cat.category_name}</span>
            <span className="whitespace-nowrap text-xs">
              <span className="font-semibold text-foreground">
                {parseFloat(cat.percentage).toFixed(0)}%
              </span>{' '}
              · {formatCurrency(cat.total, currencyCode)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
