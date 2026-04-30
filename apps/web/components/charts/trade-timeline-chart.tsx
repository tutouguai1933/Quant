"use client";

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ZAxis,
} from "recharts";

interface TradeTimelineChartProps {
  data: Array<{
    trade_id: string;
    symbol: string;
    side: string;
    quantity: string;
    price: string;
    pnl: string;
    executed_at: string;
  }>;
}

export function TradeTimelineChart({ data }: TradeTimelineChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无交易记录
      </div>
    );
  }

  // Parse and sort data by time
  const chartData = data
    .map((item) => ({
      ...item,
      time: new Date(item.executed_at).getTime(),
      pnlValue: parseFloat(item.pnl) || 0,
      quantityValue: parseFloat(item.quantity) || 1,
      displayTime: new Date(item.executed_at).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }),
    }))
    .sort((a, b) => a.time - b.time);

  const formatValue = (value: number) => {
    if (Math.abs(value) < 0.0001) return "0";
    return value.toFixed(6);
  };

  // Get min/max time for domain
  const times = chartData.map((d) => d.time);
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const timeRange = maxTime - minTime || 1;

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">交易时间线</h4>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="displayTime"
            type="category"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            angle={-45}
            textAnchor="end"
            height={60}
            interval="preserveStartEnd"
          />
          <YAxis
            dataKey="pnlValue"
            type="number"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickFormatter={formatValue}
          />
          <ZAxis dataKey="quantityValue" range={[50, 400]} />
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
              if (nameStr === "pnlValue") return [formatValue(numValue), "盈亏"];
              if (nameStr === "quantityValue") return [numValue, "数量"];
              return [numValue, nameStr];
            }}
            labelFormatter={(label) => `时间: ${label}`}
          />
          <Scatter data={chartData} fill="#8884d8">
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.pnlValue >= 0 ? "#22c55e" : "#ef4444"}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

interface TradePnlDistributionProps {
  data: Array<{
    trade_id: string;
    symbol: string;
    pnl: string;
  }>;
}

export function TradePnlDistribution({ data }: TradePnlDistributionProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无交易记录
      </div>
    );
  }

  // Create histogram bins
  const pnlValues = data.map((d) => parseFloat(d.pnl) || 0).filter((v) => v !== 0);
  if (pnlValues.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无盈亏分布数据
      </div>
    );
  }

  const min = Math.min(...pnlValues);
  const max = Math.max(...pnlValues);
  const range = max - min || 1;
  const binCount = Math.min(20, Math.ceil(pnlValues.length / 3));
  const binSize = range / binCount;

  const bins: Array<{ range: string; count: number; pnl: number }> = [];
  for (let i = 0; i < binCount; i++) {
    const binStart = min + i * binSize;
    const binEnd = min + (i + 1) * binSize;
    const binMid = (binStart + binEnd) / 2;
    bins.push({
      range: `${binStart.toFixed(6)}`,
      count: 0,
      pnl: binMid,
    });
  }

  pnlValues.forEach((v) => {
    const binIndex = Math.min(
      Math.floor((v - min) / binSize),
      binCount - 1
    );
    if (binIndex >= 0 && binIndex < bins.length) {
      bins[binIndex].count++;
    }
  });

  const formatValue = (value: number) => {
    if (Math.abs(value) < 0.0001) return "0";
    return value.toFixed(6);
  };

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">盈亏分布</h4>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="pnl"
            type="number"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickFormatter={formatValue}
          />
          <YAxis
            dataKey="count"
            type="number"
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
                nameStr === "count" ? numValue : formatValue(numValue),
                nameStr === "count" ? "交易数" : "盈亏",
              ];
            }}
          />
          <Scatter data={bins} fill="#3b82f6">
            {bins.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.pnl >= 0 ? "#22c55e" : "#ef4444"}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}