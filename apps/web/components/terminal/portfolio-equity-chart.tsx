/**
 * 组合净值图组件
 * 用于展示 Top-K 组合与等权基准对比
 */
"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from "recharts";

/* 组合净值图属性 */
export type PortfolioEquityChartProps = {
  /** 净值数据 */
  data: Array<{
    date: string;
    portfolio: number;
    benchmark?: number;
  }>;
  /** 图表标题 */
  title?: string;
  /** 副标题 */
  subtitle?: string;
  /** 图表高度 */
  height?: number;
  /** 额外的类名 */
  className?: string;
};

/* 组合净值图组件 */
export function PortfolioEquityChart({
  data,
  title = "组合净值 vs 等权基准",
  subtitle,
  height = 360,
  className = "",
}: PortfolioEquityChartProps) {
  // 如果没有数据，显示空状态
  if (!data || data.length === 0) {
    return (
      <div className={`terminal-chart-panel flex items-center justify-center ${className}`} style={{ height }}>
        <div className="text-center">
          <p className="text-[var(--terminal-muted)] text-[13px]">
            当前研究产物没有返回组合净值序列
          </p>
          <p className="text-[var(--terminal-dim)] text-[11px] mt-1">
            请先运行选币回测生成组合净值
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`terminal-chart-panel ${className}`}>
      {/* 标题区 */}
      <div className="mb-3">
        <div className="terminal-chart-title">{title}</div>
        {subtitle && (
          <div className="text-[var(--terminal-dim)] text-[11px] mt-1">{subtitle}</div>
        )}
      </div>

      {/* 图例 */}
      <div className="flex gap-4 mb-3 text-[11px]">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-[var(--terminal-cyan)]" />
          <span className="text-[var(--terminal-muted)]">Top-K 组合</span>
        </div>
        {data[0]?.benchmark !== undefined && (
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-0.5 bg-[var(--terminal-muted)] border-dashed" />
            <span className="text-[var(--terminal-muted)]">等权基准</span>
          </div>
        )}
      </div>

      {/* 图表 */}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data}>
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
          {/* 基准线 */}
          {data[0]?.benchmark !== undefined && (
            <Line
              type="monotone"
              dataKey="benchmark"
              stroke="var(--terminal-muted)"
              strokeDasharray="4 4"
              dot={false}
              name="等权基准"
            />
          )}
          {/* 组合净值面积 */}
          <Area
            type="monotone"
            dataKey="portfolio"
            stroke="var(--terminal-cyan)"
            fill="var(--terminal-cyan)"
            fillOpacity={0.12}
            dot={false}
            name="Top-K 组合"
          />
          {/* 组合净值线 */}
          <Line
            type="monotone"
            dataKey="portfolio"
            stroke="var(--terminal-cyan)"
            strokeWidth={2}
            dot={false}
            name="Top-K 组合"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
