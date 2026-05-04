/**
 * 净值曲线图组件
 * 用于展示策略净值和基准对比
 */
"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
  AreaChart,
} from "recharts";

/* 净值曲线图属性 */
export type EquityCurveChartProps = {
  /** 净值数据 */
  data: Array<{
    date: string;
    value: number;
    benchmark?: number;
  }>;
  /** 策略名称 */
  strategyName?: string;
  /** 图表高度 */
  height?: number;
  /** 额外的类名 */
  className?: string;
};

/* 净值曲线图组件 */
export function EquityCurveChart({
  data,
  strategyName = "策略净值",
  height = 320,
  className = "",
}: EquityCurveChartProps) {
  // 如果没有数据，显示空状态
  if (!data || data.length === 0) {
    return (
      <div className={`terminal-chart-panel flex items-center justify-center ${className}`} style={{ height }}>
        <div className="text-center">
          <p className="text-[var(--terminal-muted)] text-[13px]">
            当前研究产物没有返回净值序列
          </p>
          <p className="text-[var(--terminal-dim)] text-[11px] mt-1">
            请先运行回测生成净值数据
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`terminal-chart-panel ${className}`}>
      <div className="terminal-chart-title">{strategyName}</div>
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
              name="基准"
            />
          )}
          {/* 策略净值面积 */}
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--terminal-cyan)"
            fill="var(--terminal-cyan)"
            fillOpacity={0.15}
            dot={false}
            name={strategyName}
          />
          {/* 策略净值线 */}
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--terminal-cyan)"
            strokeWidth={2}
            dot={false}
            name={strategyName}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* 回撤图属性 */
export type DrawdownChartProps = {
  /** 回撤数据 */
  data: Array<{
    date: string;
    drawdown: number;
  }>;
  /** 图表高度 */
  height?: number;
  /** 额外的类名 */
  className?: string;
};

/* 回撤图组件 */
export function DrawdownChart({
  data,
  height = 120,
  className = "",
}: DrawdownChartProps) {
  // 如果没有数据，显示空状态
  if (!data || data.length === 0) {
    return (
      <div className={`terminal-chart-panel flex items-center justify-center ${className}`} style={{ height }}>
        <p className="text-[var(--terminal-dim)] text-[11px]">
          暂无回撤数据
        </p>
      </div>
    );
  }

  return (
    <div className={`terminal-chart-panel ${className}`}>
      <div className="terminal-chart-title text-[11px]">回撤</div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data}>
          {/* X 轴 */}
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--terminal-dim)", fontSize: 9 }}
            tickLine={false}
            axisLine={{ stroke: "var(--terminal-border)" }}
          />
          {/* Y 轴 */}
          <YAxis
            tick={{ fill: "var(--terminal-dim)", fontSize: 9 }}
            tickLine={false}
            axisLine={{ stroke: "var(--terminal-border)" }}
          />
          {/* 回撤面积 */}
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="var(--terminal-red)"
            fill="var(--terminal-red)"
            fillOpacity={0.3}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
