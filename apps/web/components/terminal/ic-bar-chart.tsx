/**
 * IC 柱状图组件
 * 用于展示测试集逐日 IC 的正负柱状图
 */
"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";

/* IC 柱状图属性 */
export type IcBarChartProps = {
  /** IC 数据列表 */
  data: Array<{
    /** 日期或标签 */
    date: string;
    /** IC 值 */
    ic: number;
  }>;
  /** 图表高度 */
  height?: number;
  /** 额外的类名 */
  className?: string;
};

/* IC 柱状图组件 */
export function IcBarChart({
  data,
  height = 280,
  className = "",
}: IcBarChartProps) {
  // 如果没有数据，显示空状态
  if (!data || data.length === 0) {
    return (
      <div className={`terminal-chart-panel flex items-center justify-center ${className}`} style={{ height }}>
        <div className="text-center">
          <p className="text-[var(--terminal-muted)] text-[13px]">
            当前研究产物没有返回 IC 序列
          </p>
          <p className="text-[var(--terminal-dim)] text-[11px] mt-1">
            请先运行模型训练生成 IC 数据
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`terminal-chart-panel ${className}`}>
      <div className="terminal-chart-title">测试集逐日 IC</div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} barCategoryGap="20%">
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
          {/* 零线 */}
          <ReferenceLine y={0} stroke="var(--terminal-border)" />
          {/* 柱状图 */}
          <Bar dataKey="ic" radius={[2, 2, 0, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.ic >= 0 ? "var(--terminal-green)" : "var(--terminal-red)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* 特征重要度条形图属性 */
export type FeatureImportanceChartProps = {
  /** 特征重要度数据 */
  data: Array<{
    /** 特征名称 */
    feature: string;
    /** 重要度值 */
    importance: number;
  }>;
  /** 图表高度 */
  height?: number;
  /** 是否是配置权重（非模型真实重要度） */
  isConfigWeight?: boolean;
  /** 额外的类名 */
  className?: string;
};

/* 特征重要度条形图组件 */
export function FeatureImportanceChart({
  data,
  height = 280,
  isConfigWeight = false,
  className = "",
}: FeatureImportanceChartProps) {
  // 如果没有数据，显示空状态
  if (!data || data.length === 0) {
    return (
      <div className={`terminal-chart-panel flex items-center justify-center ${className}`} style={{ height }}>
        <div className="text-center">
          <p className="text-[var(--terminal-muted)] text-[13px]">
            {isConfigWeight ? "暂无配置权重数据" : "当前研究产物没有特征重要度"}
          </p>
          <p className="text-[var(--terminal-dim)] text-[11px] mt-1">
            请先运行模型训练
          </p>
        </div>
      </div>
    );
  }

  // 按重要度排序
  const sortedData = [...data].sort((a, b) => b.importance - a.importance);

  return (
    <div className={`terminal-chart-panel ${className}`}>
      <div className="terminal-chart-title">
        {isConfigWeight ? "配置权重" : "特征重要度"}
        {isConfigWeight && (
          <span className="text-[var(--terminal-dim)] text-[11px] ml-2 font-normal">
            （非模型真实重要度）
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={sortedData}
          layout="vertical"
          barCategoryGap="15%"
        >
          {/* X 轴 */}
          <XAxis
            type="number"
            tick={{ fill: "var(--terminal-dim)", fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: "var(--terminal-border)" }}
          />
          {/* Y 轴 */}
          <YAxis
            type="category"
            dataKey="feature"
            tick={{ fill: "var(--terminal-muted)", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "var(--terminal-border)" }}
            width={80}
          />
          {/* 柱状图 */}
          <Bar
            dataKey="importance"
            fill="var(--terminal-cyan)"
            radius={[0, 2, 2, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
