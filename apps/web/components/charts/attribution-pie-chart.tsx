"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface AttributionPieChartProps {
  data: Array<{
    name: string;
    value: number;
  }>;
  title?: string;
}

const COLORS = [
  "#3b82f6",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
  "#f97316",
  "#6366f1",
];

export function AttributionPieChart({ data, title = "盈亏归因" }: AttributionPieChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无归因数据
      </div>
    );
  }

  // Filter out zero values and sort by absolute value
  const chartData = data
    .filter((d) => d.value !== 0)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 10); // Top 10 items

  if (chartData.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无归因数据
      </div>
    );
  }

  const total = chartData.reduce((sum, item) => sum + item.value, 0);

  const formatValue = (value: number) => {
    if (Math.abs(value) < 0.0001) return "0";
    return value.toFixed(6);
  };

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">{title}</h4>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
            label={({ name, percent }) =>
              `${(name ?? "").length > 8 ? (name ?? "").substring(0, 8) + "..." : (name ?? "")}: ${((percent ?? 0) * 100).toFixed(1)}%`
            }
            labelLine={{ stroke: "hsl(var(--muted-foreground))", strokeWidth: 1 }}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.value >= 0 ? COLORS[index % COLORS.length] : "#ef4444"}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            labelStyle={{ color: "hsl(var(--foreground))" }}
            formatter={(value) => {
              const numValue = typeof value === "number" ? value : 0;
              return [formatValue(numValue), "盈亏"];
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

interface SymbolAttributionPieChartProps {
  data: Array<{
    symbol: string;
    total_pnl: string;
  }>;
}

export function SymbolAttributionPieChart({ data }: SymbolAttributionPieChartProps) {
  const chartData = data.map((item) => ({
    name: item.symbol,
    value: parseFloat(item.total_pnl) || 0,
  }));

  return <AttributionPieChart data={chartData} title="标的盈亏归因" />;
}

interface StrategyAttributionPieChartProps {
  data: Array<{
    strategy_name: string;
    total_pnl: string;
  }>;
}

export function StrategyAttributionPieChart({ data }: StrategyAttributionPieChartProps) {
  const chartData = data.map((item) => ({
    name: item.strategy_name,
    value: parseFloat(item.total_pnl) || 0,
  }));

  return <AttributionPieChart data={chartData} title="策略盈亏归因" />;
}