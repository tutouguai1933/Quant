/* 这个文件负责渲染最小 K 线摘要，当前阶段只输出标准化图表数据。 */

import type { MarketCandle } from "../lib/api";


type CandleChartProps = {
  items: MarketCandle[];
  symbol: string;
  signalCount: number;
  entryHint: string;
  stopHint: string;
  researchBias: string;
};

/* 渲染单币图表摘要。 */
export function CandleChart({ items, symbol, signalCount, entryHint, stopHint, researchBias }: CandleChartProps) {
  if (!items.length) {
    return (
      <section className="empty-panel">
        <h3>暂无图表数据</h3>
        <p>{symbol} 的 K 线数据还没有返回，请先确认市场 API 已接入。</p>
      </section>
    );
  }

  const latest = getLatestCandle(items);
  if (!latest) {
    return (
      <section className="empty-panel">
        <h3>暂无图表数据</h3>
        <p>{symbol} 的 K 线数据还没有返回，请先确认市场 API 已接入。</p>
      </section>
    );
  }

  const candleRange = latest.high && latest.low ? `${latest.low} - ${latest.high}` : "n/a";

  return (
    <section className="panel">
      <p className="eyebrow">图表摘要</p>
      <h3>{symbol.toUpperCase()} 最新 K 线</h3>
      <p>当前阶段先展示标准化数据，后续再接入复杂图表库。</p>

      <div className="metric-grid">
        <article className="metric-card">
          <p className="metric-label">开盘</p>
          <p className="metric-value">{latest.open}</p>
          <p className="metric-detail">时间 {latest.open_time}</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">收盘</p>
          <p className="metric-value">{latest.close}</p>
          <p className="metric-detail">时间 {latest.close_time}</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">区间</p>
          <p className="metric-value">{candleRange}</p>
          <p className="metric-detail">最高 / 最低</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">成交量</p>
          <p className="metric-value">{latest.volume}</p>
          <p className="metric-detail">最后一根 K 线</p>
        </article>
      </div>

      <div className="metric-grid">
        <article className="metric-card">
          <p className="metric-label">信号点</p>
          <p className="metric-value">{String(signalCount)}</p>
          <p className="metric-detail">当前图表返回的关键信号数量</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">入场参考</p>
          <p className="metric-value">{entryHint}</p>
          <p className="metric-detail">最近可参考的入场位置</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">止损参考</p>
          <p className="metric-value">{stopHint}</p>
          <p className="metric-detail">最近需要盯住的失效位</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">研究倾向</p>
          <p className="metric-value">{researchBias}</p>
          <p className="metric-detail">图表图层和研究判断共用同一口径</p>
        </article>
      </div>
    </section>
  );
}

function getCandleTimestamp(item: MarketCandle): number {
  return item.open_time || item.close_time || 0;
}

function getLatestCandle(items: MarketCandle[]): MarketCandle | undefined {
  return [...items].sort((left, right) => getCandleTimestamp(right) - getCandleTimestamp(left))[0];
}
