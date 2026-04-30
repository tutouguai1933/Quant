"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface PnlCurveChartProps {
  data: Array<{
    date: string;
    pnl: number;
    cumulative?: number;
  }>;
  title?: string;
}

export function PnlCurveChart({ data, title = "盈亏曲线" }: PnlCurveChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无盈亏数据
      </div>
    );
  }

  // Calculate cumulative PnL
  let cumulativePnl = 0;
  const chartData = data.map((item) => {
    cumulativePnl += item.pnl;
    return {
      ...item,
      cumulative: cumulativePnl,
    };
  });

  const formatValue = (value: number) => {
    if (Math.abs(value) < 0.0001) return "0";
    return value.toFixed(4);
  };

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">{title}</h4>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="pnlGradientPositive" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="pnlGradientNegative" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickFormatter={formatValue}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            labelStyle={{ color: "hsl(var(--foreground))" }}
            formatter={(value, name) => {
              const numValue = typeof value === "number" ? value : 0;
              const nameStr = typeof name === "string" ? name : String(name);
              return [
                formatValue(numValue),
                nameStr === "cumulative" ? "累计盈亏" : "当日盈亏",
              ];
            }}
          />
          <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
          <Area
            type="monotone"
            dataKey="cumulative"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#pnlGradientPositive)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}