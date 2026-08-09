"use client";

import { useState, useEffect } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import { TrendingUp, TrendingDown, Activity, Target, AlertTriangle, BarChart3 } from "lucide-react";

interface ProfitCurvePoint {
  date: string;
  profit: number;
  cumulative: number;
}

interface Statistics {
  total_return: number;
  gross_return: number;
  net_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  turnover: number;
  max_loss_streak: number;
}

interface Distribution {
  wins: number;
  losses: number;
  avg_win: number;
  avg_loss: number;
  win_rate: number;
  total_trades: number;
}

interface BacktestChartsProps {
  backtestId?: string;
  refreshKey?: number;
}

export function BacktestCharts({ backtestId = "latest", refreshKey = 0 }: BacktestChartsProps) {
  const [profitCurve, setProfitCurve] = useState<ProfitCurvePoint[]>([]);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [distribution, setDistribution] = useState<Distribution | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/v1/backtest/${backtestId}/charts`);
        if (!response.ok) throw new Error("Failed to fetch chart data");
        const result = await response.json();
        const data = result.data || {};

        setProfitCurve(data.profit_curve || []);
        setStatistics(data.statistics || null);
        setDistribution(data.distribution || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [backtestId, refreshKey]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        Loading chart data...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center text-destructive">
        Error: {error}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <StatisticsCards statistics={statistics} />
      <ProfitCurveChart data={profitCurve} />
      <TradeDistributionChart distribution={distribution} />
    </div>
  );
}

function StatisticsCards({ statistics }: { statistics: Statistics | null }) {
  if (!statistics) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="text-muted-foreground text-sm">暂无统计数据</div>
        </div>
      </div>
    );
  }

  const formatValue = (value: number, suffix: string = "") => {
    if (value === 0) return "0" + suffix;
    return value.toFixed(2) + suffix;
  };

  const isPositiveReturn = statistics.total_return >= 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <TrendingUp className="h-4 w-4" />
          累计收益
        </div>
        <div className={`mt-2 text-2xl font-bold ${isPositiveReturn ? "text-green-500" : "text-red-500"}`}>
          {formatValue(statistics.total_return, "%")}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          净收益: {formatValue(statistics.net_return, "%")}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <AlertTriangle className="h-4 w-4" />
          最大回撤
        </div>
        <div className="mt-2 text-2xl font-bold text-red-500">
          {formatValue(statistics.max_drawdown, "%")}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          最长连亏: {statistics.max_loss_streak}次
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Activity className="h-4 w-4" />
          夏普比率
        </div>
        <div className="mt-2 text-2xl font-bold text-blue-500">
          {formatValue(statistics.sharpe_ratio)}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          换手率: {formatValue(statistics.turnover * 100, "%")}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Target className="h-4 w-4" />
          胜率
        </div>
        <div className="mt-2 text-2xl font-bold text-green-500">
          {formatValue(statistics.win_rate * 100, "%")}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          毛收益: {formatValue(statistics.gross_return, "%")}
        </div>
      </div>
    </div>
  );
}

function ProfitCurveChart({ data }: { data: ProfitCurvePoint[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <TrendingUp className="h-5 w-5" />
          收益曲线
        </div>
        <div className="flex h-64 items-center justify-center text-muted-foreground rounded-lg border border-border bg-card">
          暂无收益曲线数据
        </div>
      </div>
    );
  }

  const formatValue = (value: number) => {
    if (Math.abs(value) < 0.0001) return "0";
    return value.toFixed(4);
  };

  const minValue = Math.min(...data.map((d) => d.cumulative));
  const maxValue = Math.max(...data.map((d) => d.cumulative));

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <TrendingUp className="h-5 w-5" />
        收益曲线
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="profitGradientPositive" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="profitGradientNegative" x1="0" y1="0" x2="0" y2="1">
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
              tickFormatter={(value) => value.slice(5)}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--border))" }}
              tickFormatter={formatValue}
              domain={[minValue * 1.1, maxValue * 1.1]}
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
                  formatValue(numValue) + "%",
                  nameStr === "cumulative" ? "累计收益" : "当日收益",
                ];
              }}
            />
            <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="cumulative"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#profitGradientPositive)"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function TradeDistributionChart({ distribution }: { distribution: Distribution | null }) {
  if (!distribution || distribution.total_trades === 0) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <BarChart3 className="h-5 w-5" />
          交易分布
        </div>
        <div className="flex h-64 items-center justify-center text-muted-foreground rounded-lg border border-border bg-card">
          暂无交易分布数据
        </div>
      </div>
    );
  }

  const barData = [
    {
      name: "盈利交易",
      count: distribution.wins,
      avg: distribution.avg_win,
      fill: "#22c55e",
    },
    {
      name: "亏损交易",
      count: distribution.losses,
      avg: distribution.avg_loss,
      fill: "#ef4444",
    },
  ];

  const formatValue = (value: number) => {
    if (value === 0) return "0";
    return value.toFixed(4);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <BarChart3 className="h-5 w-5" />
        交易分布
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div className="text-center p-3 rounded-lg bg-green-500/10 border border-green-500/20">
            <div className="text-lg font-bold text-green-500">{distribution.wins}</div>
            <div className="text-sm text-muted-foreground">盈利次数</div>
            <div className="text-xs text-green-500 mt-1">平均: +{formatValue(distribution.avg_win)}%</div>
          </div>
          <div className="text-center p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <div className="text-lg font-bold text-red-500">{distribution.losses}</div>
            <div className="text-sm text-muted-foreground">亏损次数</div>
            <div className="text-xs text-red-500 mt-1">平均: {formatValue(distribution.avg_loss)}%</div>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={barData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--border))" }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--border))" }}
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
                  nameStr === "avg" ? formatValue(numValue) + "%" : numValue,
                  nameStr === "avg" ? "平均收益" : "交易次数",
                ];
              }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {barData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="text-center mt-4 text-sm text-muted-foreground">
          总交易次数: {distribution.total_trades} | 胜率: {(distribution.win_rate * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  );
}