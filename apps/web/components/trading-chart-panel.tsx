/* 这个文件负责渲染单币页的交易主区骨架。 */

import type { ChartMarkerGroups, MarketCandle } from "../lib/api";


type TradingChartPanelProps = {
  symbol: string;
  interval: string;
  items: MarketCandle[];
  markers: ChartMarkerGroups;
};

/* 渲染交易主区的轻量图表骨架。 */
export function TradingChartPanel({ symbol, interval, items, markers }: TradingChartPanelProps) {
  const latest = items[items.length - 1];
  const signalCount = markers.signals.length;
  const latestEntry = formatLatestMarkerPrice(markers.entries);
  const latestStop = formatLatestMarkerPrice(markers.stops);

  return (
    <section className="panel trading-chart-panel">
      <p className="eyebrow">交易主区</p>
      <h3>{symbol.toUpperCase()} / {interval}</h3>
      <p>当前阶段先把周期切换和交易主区摆出来，下一步再把真正的 K 线绘制细化进去。</p>

      <div className="metric-grid">
        <article className="metric-card">
          <p className="metric-label">已加载 K 线</p>
          <p className="metric-value">{String(items.length)}</p>
          <p className="metric-detail">当前主图区拿到的标准化样本数量</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">最新收盘</p>
          <p className="metric-value">{formatText(latest?.close, "n/a")}</p>
          <p className="metric-detail">先确认最近一根的价格落点</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">信号点</p>
          <p className="metric-value">{String(signalCount)}</p>
          <p className="metric-detail">图表层里当前能看到的策略信号数量</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">点位参考</p>
          <p className="metric-value">{latestEntry} / {latestStop}</p>
          <p className="metric-detail">入场参考 / 止损参考</p>
        </article>
      </div>
    </section>
  );
}

/* 返回最近一个图表标记价格。 */
function formatLatestMarkerPrice(items: Array<Record<string, unknown>>): string {
  const latest = items[items.length - 1];
  return formatText(latest?.price, "n/a");
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
