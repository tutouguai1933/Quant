/**
 * 指标卡组件
 * 用于展示关键指标，支持正负颜色
 * 尺寸约 90-112px 高度
 */

import type { ReactNode } from "react";

/* 指标卡属性 */
export type MetricCardProps = {
  /** 指标标签 */
  label: string;
  /** 指标值 */
  value: string | number | null | undefined;
  /** 辅助说明 */
  detail?: string;
  /** 值的颜色类型：positive=绿, negative=红, neutral=默认 */
  colorType?: "positive" | "negative" | "neutral";
  /** 额外的类名 */
  className?: string;
};

/* 指标卡组件 */
export function MetricCard({
  label,
  value,
  detail,
  colorType = "neutral",
  className = "",
}: MetricCardProps) {
  // 处理空值
  const displayValue = value === null || value === undefined ? "--" : value;

  return (
    <div className={`terminal-metric-card ${className}`}>
      {/* 标签 */}
      <div className="terminal-metric-label">
        {label}
      </div>

      {/* 值 */}
      <div className={`terminal-metric-value ${colorType}`}>
        {displayValue}
      </div>

      {/* 辅助说明 */}
      {detail && (
        <div className="terminal-metric-detail">
          {detail}
        </div>
      )}
    </div>
  );
}

/* 指标卡条组件 - 横向排列多个指标卡 */
export type MetricStripProps = {
  /** 指标列表 */
  metrics: Array<{
    label: string;
    value: string | number | null | undefined;
    detail?: string;
    colorType?: "positive" | "negative" | "neutral";
  }>;
  /** 额外的类名 */
  className?: string;
};

/* 指标卡条组件 */
export function MetricStrip({ metrics, className = "" }: MetricStripProps) {
  return (
    <div className={`grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3 ${className}`}>
      {metrics.map((metric, index) => (
        <MetricCard
          key={index}
          label={metric.label}
          value={metric.value}
          detail={metric.detail}
          colorType={metric.colorType}
        />
      ))}
    </div>
  );
}
