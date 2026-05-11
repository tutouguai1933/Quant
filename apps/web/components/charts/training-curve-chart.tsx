"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface TrainingCurveChartProps {
  series: Array<{
    step: number;
    train_score?: number;
    validation_score?: number;
    train_loss?: number;
    validation_loss?: number;
  }>;
  title?: string;
  showLoss?: boolean;
}

export function TrainingCurveChart({
  series,
  title = "训练曲线",
  showLoss = false,
}: TrainingCurveChartProps) {
  if (!series || series.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        暂无训练数据
      </div>
    );
  }

  const formatValue = (value: number) => {
    if (Math.abs(value) < 0.0001) return "0";
    return value.toFixed(4);
  };

  const hasScore =
    series.some((s) => s.train_score !== undefined) ||
    series.some((s) => s.validation_score !== undefined);
  const hasLoss =
    series.some((s) => s.train_loss !== undefined) ||
    series.some((s) => s.validation_loss !== undefined);

  const displayLoss = showLoss && hasLoss;
  const displayScore = hasScore;

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-foreground">{title}</h4>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={series} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="trainScoreGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="valScoreGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="step"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            label={{ value: "迭代", position: "insideBottomRight", offset: -5, fontSize: 11 }}
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
              const labels: Record<string, string> = {
                train_score: "训练分数",
                validation_score: "验证分数",
                train_loss: "训练损失",
                validation_loss: "验证损失",
              };
              return [formatValue(numValue), labels[nameStr] || nameStr];
            }}
          />
          <Legend
            formatter={(value) => {
              const labels: Record<string, string> = {
                train_score: "训练分数",
                validation_score: "验证分数",
                train_loss: "训练损失",
                validation_loss: "验证损失",
              };
              return labels[value] || value;
            }}
          />
          {displayScore && (
            <>
              <Line
                type="monotone"
                dataKey="train_score"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="validation_score"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            </>
          )}
          {displayLoss && (
            <>
              <Line
                type="monotone"
                dataKey="train_loss"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
                strokeDasharray="5 5"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="validation_loss"
                stroke="#ef4444"
                strokeWidth={2}
                dot={false}
                strokeDasharray="5 5"
                connectNulls
              />
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
