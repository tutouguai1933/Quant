/* 这个文件负责渲染单币页的可读交易主图。 */

import type { ChartMarkerGroups, MarketCandle } from "../lib/api";


type TradingChartPanelProps = {
  symbol: string;
  interval: string;
  items: MarketCandle[];
  markers: ChartMarkerGroups;
};

type ChartCandle = {
  open_time: number;
  x: number;
  bodyX: number;
  openY: number;
  closeY: number;
  highY: number;
  lowY: number;
  bodyY: number;
  bodyHeight: number;
  rising: boolean;
};

type ChartMarkerPoint = {
  key: string;
  x: number;
  y: number;
};

const CHART_WIDTH = 920;
const CHART_HEIGHT = 360;
const CHART_PADDING = 28;

/* 渲染交易主区的最小 SVG K 线视图。 */
export function TradingChartPanel({ symbol, interval, items, markers }: TradingChartPanelProps) {
  const normalizedItems = items.slice(-24);
  const latest = normalizedItems[normalizedItems.length - 1];

  if (!normalizedItems.length) {
    return (
      <section className="panel trading-chart-panel">
        <p className="eyebrow">交易主区</p>
        <h3>{symbol.toUpperCase()}</h3>
        <p>当前周期：{interval}</p>
        <p>暂无图表数据，先确认市场接口已经返回当前周期的 K 线。</p>
      </section>
    );
  }

  const priceDomain = resolvePriceDomain(normalizedItems, markers);
  const candles = buildChartCandles(normalizedItems, priceDomain);
  const currentPrice = formatText(latest?.close, "n/a");
  const entryLine = resolveHorizontalLineY(markers.entries, candles, priceDomain);
  const stopLine = resolveHorizontalLineY(markers.stops, candles, priceDomain);
  const signals = buildSignalPoints(markers.signals, candles, priceDomain);
  const candleBodyWidth = resolveCandleBodyWidth(candles.length);

  return (
    <section className="panel trading-chart-panel">
      <p className="eyebrow">交易主区</p>
      <h3>{symbol.toUpperCase()}</h3>
      <p>当前周期：{interval}</p>
      <p>当前价格：{currentPrice}</p>

      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label={`${symbol} ${interval} candlestick chart`}
      >
        <rect
          x="0"
          y="0"
          width={String(CHART_WIDTH)}
          height={String(CHART_HEIGHT)}
          rx="18"
          fill="rgba(255, 255, 255, 0.72)"
        />
        <line
          x1={String(CHART_PADDING)}
          x2={String(CHART_WIDTH - CHART_PADDING)}
          y1={String(CHART_HEIGHT - CHART_PADDING)}
          y2={String(CHART_HEIGHT - CHART_PADDING)}
          stroke="rgba(21, 40, 49, 0.12)"
          strokeWidth="1"
        />
        {candles.map((item) => (
          <g key={item.open_time}>
            <line
              x1={String(item.x)}
              x2={String(item.x)}
              y1={String(item.highY)}
              y2={String(item.lowY)}
              className="chart-wick"
              stroke={item.rising ? "#195f58" : "#b64e3f"}
              strokeWidth="2"
            />
            <rect
              x={String(item.bodyX)}
              y={String(item.bodyY)}
              width={String(candleBodyWidth)}
              height={String(item.bodyHeight)}
              className={item.rising ? "chart-body-up" : "chart-body-down"}
              fill={item.rising ? "#195f58" : "#b64e3f"}
              opacity="0.9"
              rx="2"
            />
          </g>
        ))}
        {entryLine !== null ? (
          <line
            y1={String(entryLine)}
            y2={String(entryLine)}
            x1={String(CHART_PADDING)}
            x2={String(CHART_WIDTH - CHART_PADDING)}
            className="chart-entry-line"
            stroke="#bc8c2b"
            strokeDasharray="8 6"
            strokeWidth="2"
          />
        ) : null}
        {stopLine !== null ? (
          <line
            y1={String(stopLine)}
            y2={String(stopLine)}
            x1={String(CHART_PADDING)}
            x2={String(CHART_WIDTH - CHART_PADDING)}
            className="chart-stop-line"
            stroke="#b64e3f"
            strokeDasharray="8 6"
            strokeWidth="2"
          />
        ) : null}
        {signals.map((signal) => (
          <circle
            key={signal.key}
            cx={String(signal.x)}
            cy={String(signal.y)}
            r="4"
            className="chart-signal-dot"
            fill="#195f58"
            stroke="#ffffff"
            strokeWidth="2"
          />
        ))}
      </svg>

      <div className="metric-grid">
        <article className="metric-card">
          <p className="metric-label">signal</p>
          <p className="metric-value">{String(signals.length)}</p>
          <p className="metric-detail">主图上的信号点数量</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">entry</p>
          <p className="metric-value">{formatLatestMarkerPrice(markers.entries)}</p>
          <p className="metric-detail">图上的入场参考线</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">stop</p>
          <p className="metric-value">{formatLatestMarkerPrice(markers.stops)}</p>
          <p className="metric-detail">图上的止损参考线</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">当前价格</p>
          <p className="metric-value">{currentPrice}</p>
          <p className="metric-detail">当前周期最后一根 K 线收盘价</p>
        </article>
      </div>
    </section>
  );
}

/* 根据价格范围构造可绘制 K 线。 */
function buildChartCandles(items: MarketCandle[], priceDomain: { min: number; max: number }): ChartCandle[] {
  const step = items.length > 1
    ? (CHART_WIDTH - CHART_PADDING * 2) / (items.length - 1)
    : 0;

  return items.map((item, index) => {
    const x = CHART_PADDING + step * index;
    const openValue = toNumber(item.open);
    const closeValue = toNumber(item.close);
    const highValue = toNumber(item.high);
    const lowValue = toNumber(item.low);
    const openY = mapPriceToY(openValue, priceDomain);
    const closeY = mapPriceToY(closeValue, priceDomain);
    const highY = mapPriceToY(highValue, priceDomain);
    const lowY = mapPriceToY(lowValue, priceDomain);
    const rising = closeValue >= openValue;

    return {
      open_time: item.open_time,
      x,
      bodyX: x - resolveCandleBodyWidth(items.length) / 2,
      openY,
      closeY,
      highY,
      lowY,
      bodyY: Math.min(openY, closeY),
      bodyHeight: Math.max(Math.abs(openY - closeY), 2),
      rising,
    };
  });
}

/* 计算主图展示所需的价格范围。 */
function resolvePriceDomain(items: MarketCandle[], markers: ChartMarkerGroups): { min: number; max: number } {
  const prices: number[] = [];

  for (const item of items) {
    prices.push(toNumber(item.high), toNumber(item.low), toNumber(item.open), toNumber(item.close));
  }
  for (const group of [markers.entries, markers.stops, markers.signals]) {
    for (const item of group) {
      const price = toNumber(item.price);
      if (Number.isFinite(price)) {
        prices.push(price);
      }
    }
  }

  const finitePrices = prices.filter((value) => Number.isFinite(value));
  const min = finitePrices.length ? Math.min(...finitePrices) : 0;
  const max = finitePrices.length ? Math.max(...finitePrices) : 1;
  if (max === min) {
    return { min: min - 1, max: max + 1 };
  }

  const padding = (max - min) * 0.08;
  return { min: min - padding, max: max + padding };
}

/* 把价格映射到 SVG 的 y 坐标。 */
function mapPriceToY(price: number, priceDomain: { min: number; max: number }): number {
  const usableHeight = CHART_HEIGHT - CHART_PADDING * 2;
  const ratio = (price - priceDomain.min) / (priceDomain.max - priceDomain.min);
  return CHART_HEIGHT - CHART_PADDING - ratio * usableHeight;
}

/* 读取最近一个图表标记的价格。 */
function formatLatestMarkerPrice(items: Array<Record<string, unknown>>): string {
  const latest = items[items.length - 1];
  return formatText(latest?.price, "n/a");
}

/* 计算某一组水平参考线在图中的 y 坐标。 */
function resolveHorizontalLineY(
  items: Array<Record<string, unknown>>,
  candles: ChartCandle[],
  priceDomain: { min: number; max: number },
): number | null {
  if (!items.length || !candles.length) {
    return null;
  }
  const latest = items[items.length - 1];
  const price = toNumber(latest.price);
  if (!Number.isFinite(price)) {
    return null;
  }
  return mapPriceToY(price, priceDomain);
}

/* 构造信号点在图上的位置。 */
function buildSignalPoints(
  items: Array<Record<string, unknown>>,
  candles: ChartCandle[],
  priceDomain: { min: number; max: number },
): ChartMarkerPoint[] {
  if (!items.length || !candles.length) {
    return [];
  }

  return items.map((item, index) => {
    const price = toNumber(item.price);
    const fallbackCandle = candles[Math.min(index, candles.length - 1)];
    const x = fallbackCandle.x;
    const y = Number.isFinite(price) ? mapPriceToY(price, priceDomain) : fallbackCandle.closeY;

    return {
      key: `${String(item.time ?? fallbackCandle.open_time)}-${index}`,
      x,
      y,
    };
  });
}

/* 按样本数返回合适的实体宽度。 */
function resolveCandleBodyWidth(count: number): number {
  const usableWidth = CHART_WIDTH - CHART_PADDING * 2;
  if (count <= 1) {
    return 18;
  }
  return Math.max(6, Math.min(18, usableWidth / count * 0.56));
}

/* 把输入统一成可用数值。 */
function toNumber(value: unknown): number {
  const parsed = Number(String(value ?? ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
