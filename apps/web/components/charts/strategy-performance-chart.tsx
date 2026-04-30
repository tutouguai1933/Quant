"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface StrategyPerformanceChartProps {
  data: Array<{
    strategy_name: string;
    total_pnl: string;
    trade_count: number;
    win_rate: string;
  }>;
}

export function StrategyPerformanceChart({ data }: StrategyPerformanceChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无策略表现数据
      </div>
    );
  }

  const chartData = data.map((item) => ({
    name: item.strategy_name.length > 10
      ? item.strategy_name.substring(0, 10) + "..."
      : item.strategy_name,
    fullName: item.strategy_name,
    pnl: parseFloat(item.total_pnl) || 0,
    trades: item.trade_count,
    winRate: parseFloat(item.win_rate) * 100,
  }));

  const formatValue = (value: number) => {
    if (Math.abs(value) < 0.0001) return "0";
    return value.toFixed(4);
  };

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">策略盈亏对比</h4>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            angle={-20}
            textAnchor="end"
            interval={0}
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
                nameStr === "pnl" ? formatValue(numValue) : numValue,
                nameStr === "pnl" ? "盈亏" : nameStr === "winRate" ? "胜率(%)" : "交易数",
              ];
            }}
            labelFormatter={(label, payload) => {
              const item = payload?.[0]?.payload;
              return item?.fullName || label;
            }}
          />
          <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.pnl >= 0 ? "#22c55e" : "#ef4444"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface StrategyWinRateChartProps {
  data: Array<{
    strategy_name: string;
    win_rate: string;
    trade_count: number;
  }>;
}

export function StrategyWinRateChart({ data }: StrategyWinRateChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无策略表现数据
      </div>
    );
  }

  const chartData = data.map((item) => ({
    name: item.strategy_name.length > 10
      ? item.strategy_name.substring(0, 10) + "..."
      : item.strategy_name,
    fullName: item.strategy_name,
    winRate: parseFloat(item.win_rate) * 100,
    trades: item.trade_count,
  }));

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">策略胜率对比</h4>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            angle={-20}
            textAnchor="end"
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
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
                nameStr === "winRate" ? `${numValue.toFixed(1)}%` : numValue,
                nameStr === "winRate" ? "胜率" : "交易数",
              ];
            }}
            labelFormatter={(label, payload) => {
              const item = payload?.[0]?.payload;
              return item?.fullName || label;
            }}
          />
          <Bar dataKey="winRate" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}