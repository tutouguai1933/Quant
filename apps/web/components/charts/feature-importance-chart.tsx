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

interface FeatureImportanceChartProps {
  series: Array<{
    feature: string;
    importance: number;
    category?: string;
    rank?: number;
  }>;
  title?: string;
  maxItems?: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  momentum: "#22c55e",
  volatility: "#f59e0b",
  volume: "#3b82f6",
  trend: "#8b5cf6",
  oscillator: "#ec4899",
  price: "#06b6d4",
  default: "#6366f1",
};

export function FeatureImportanceChart({
  series,
  title = "特征重要性",
  maxItems = 20,
}: FeatureImportanceChartProps) {
  if (!series || series.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无特征重要性数据
      </div>
    );
  }

  const sortedData = [...series]
    .sort((a, b) => b.importance - a.importance)
    .slice(0, maxItems)
    .reverse();

  const formatValue = (value: number) => {
    if (Math.abs(value) < 0.0001) return "0";
    return value.toFixed(4);
  };

  const getColor = (category?: string) => {
    if (!category) return CATEGORY_COLORS.default;
    const key = category.toLowerCase();
    for (const [k, v] of Object.entries(CATEGORY_COLORS)) {
      if (key.includes(k) || k.includes(key)) {
        return v;
      }
    }
    return CATEGORY_COLORS.default;
  };

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">{title}</h4>
      <ResponsiveContainer width="100%" height={Math.max(280, sortedData.length * 24 + 40)}>
        <BarChart
          data={sortedData}
          layout="vertical"
          margin={{ top: 10, right: 30, left: 100, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickFormatter={formatValue}
          />
          <YAxis
            type="category"
            dataKey="feature"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            width={90}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            labelStyle={{ color: "hsl(var(--foreground))" }}
            formatter={(value, name, props) => {
              const numValue = typeof value === "number" ? value : 0;
              const category = props.payload?.category;
              return [
                <div key="tooltip">
                  <div>重要性: {formatValue(numValue)}</div>
                  {category && <div className="text-muted-foreground text-xs">分类: {category}</div>}
                </div>,
                "",
              ];
            }}
          />
          <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
            {sortedData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getColor(entry.category)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {Object.entries(CATEGORY_COLORS)
          .filter(([k]) => k !== "default")
          .map(([category, color]) => (
            <div key={category} className="flex items-center gap-1">
              <div className="h-3 w-3 rounded" style={{ backgroundColor: color }} />
              <span className="capitalize">{category}</span>
            </div>
          ))}
      </div>
    </div>
  );
}
