/**
 * 图表组件懒加载
 * 使用动态导入减少初始包大小
 */

import dynamic from "next/dynamic";
import { Skeleton } from "../ui/skeleton";

// 加载占位组件
function ChartSkeleton() {
  return <Skeleton className="h-64 w-full rounded-lg" />;
}

// 懒加载图表组件
export const PnlCurveChart = dynamic(
  () => import("./pnl-curve-chart").then((mod) => mod.PnlCurveChart),
  { loading: () => <ChartSkeleton />, ssr: false }
);

export const StrategyPerformanceChart = dynamic(
  () => import("./strategy-performance-chart").then((mod) => mod.StrategyPerformanceChart),
  { loading: () => <ChartSkeleton />, ssr: false }
);

export const StrategyWinRateChart = dynamic(
  () => import("./strategy-performance-chart").then((mod) => mod.StrategyWinRateChart),
  { loading: () => <ChartSkeleton />, ssr: false }
);

export const TradeTimelineChart = dynamic(
  () => import("./trade-timeline-chart").then((mod) => mod.TradeTimelineChart),
  { loading: () => <ChartSkeleton />, ssr: false }
);

export const TradePnlDistribution = dynamic(
  () => import("./trade-timeline-chart").then((mod) => mod.TradePnlDistribution),
  { loading: () => <ChartSkeleton />, ssr: false }
);

export const SymbolAttributionPieChart = dynamic(
  () => import("./attribution-pie-chart").then((mod) => mod.SymbolAttributionPieChart),
  { loading: () => <ChartSkeleton />, ssr: false }
);

export const StrategyAttributionPieChart = dynamic(
  () => import("./attribution-pie-chart").then((mod) => mod.StrategyAttributionPieChart),
  { loading: () => <ChartSkeleton />, ssr: false }
);
