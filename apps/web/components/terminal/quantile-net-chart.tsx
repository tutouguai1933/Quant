/**
 * 分位组合净值图组件
 * 用于展示 Q1-Q5 分位组合净值对比
 */
"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from "recharts";

/* 分位组合净值图属性 */
export type QuantileNetChartProps = {
  /** 分位数据，每条线一个分位 */
  data: Array<{
    date: string;
    Q1?: number;
    Q2?: number;
    Q3?: number;
    Q4?: number;
    Q5?: number;
  }>;
  /** 图表高度 */
  height?: number;
  /** 额外的类名 */
  className?: string;
}

/* 分位颜色 */
const QUANTILE_COLORS = [
  "var(--terminal-muted)",    // Q1 - 低
  "var(--terminal-yellow)",   // Q2
  "var(--terminal-purple)",   // Q3
  "var(--terminal-cyan)",     // Q4
  "var(--terminal-green)",    // Q5 - 高
];

/* 分位标签 */
const QUANTILE_LABELS = ["Q1 低", "Q2", "Q3", "Q4", "Q5 高"];

/* 分位组合净值图组件 */
export function QuantileNetChart({
  data,
  height = 300,
  className = "",
}: QuantileNetChartProps) {
  // 如果没有数据，显示空状态
  if (!data || data.length === 0) {
    return (
      <div className={`terminal-chart-panel flex items-center justify-center ${className}`} style={{ height }}>
        <div className="text-center">
          <p className="text-[var(--terminal-muted)] text-[13px]">
            当前研究产物没有分位组合净值
          </p>
          <p className="text-[var(--terminal-dim)] text-[11px] mt-1">
            请先运行因子分析生成分位数据
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`terminal-chart-panel ${className}`}>
      <div className="terminal-chart-title">分位组合净值（Q5=因子值最高）</div>

      {/* 图例 */}
      <div className="flex gap-3 mb-3 text-[11px]">
        {QUANTILE_LABELS.map((label, i) => (
          <div key={label} className="flex items-center gap-1">
            <div className="w-2.5 h-0.5" style={{ backgroundColor: QUANTILE_COLORS[i] }} />
            <span className="text-[var(--terminal-muted)]">{label}</span>
          </div>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          {/* X 轴 */}
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--terminal-dim)", fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: "var(--terminal-border)" }}
          />
          {/* Y 轴 */}
          <YAxis
            tick={{ fill: "var(--terminal-dim)", fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: "var(--terminal-border)" }}
          />
          {/* Q1-Q5 线 */}
          {["Q1", "Q2", "Q3", "Q4", "Q5"].map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={QUANTILE_COLORS[i]}
              strokeWidth={i === 4 ? 2 : 1.5}
              dot={false}
              name={QUANTILE_LABELS[i]}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
