/* 这个文件负责渲染单币页的交易主区。 */

"use client";

import { useEffect, useState } from "react";

import type { ChartIndicatorSummary, ChartMarkerGroups, MarketCandle } from "../lib/api";
import { ProChartScript } from "./pro-chart-script";
import { ProKlineChart } from "./pro-kline-chart";
import { TimeframeTabs } from "./timeframe-tabs";


type TradingChartPanelProps = {
  symbol: string;
  interval: string;
  supportedIntervals: string[];
  items: MarketCandle[];
  markers: ChartMarkerGroups;
  overlays: ChartIndicatorSummary;
  onSelectInterval: (interval: string) => void;
  pendingInterval?: string;
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
const SHORT_INTERVALS = ["1m", "3m", "5m", "15m", "30m"];
const LONG_INTERVALS = ["1h", "4h", "1d", "1w"];

/* 渲染交易主区的专业图表壳子。 */
export function TradingChartPanel({
  symbol,
  interval,
  supportedIntervals,
  items,
  markers,
  overlays,
  onSelectInterval,
  pendingInterval = "",
}: TradingChartPanelProps) {
  const [runtimeReady, setRuntimeReady] = useState(false);
  const normalizedItems = items;
  const currentPrice = resolveLatestCloseText(items);
  const latestSignal = formatLatestMarkerSummary(markers);
  const shortIntervals = pickIntervals(supportedIntervals, SHORT_INTERVALS);
  const longIntervals = pickIntervals(supportedIntervals, LONG_INTERVALS);

  useEffect(() => {
    if (typeof window !== "undefined" && window.LightweightCharts) {
      setRuntimeReady(true);
    }
  }, []);

  return (
    <section className="panel trading-chart-panel">
      <ProChartScript onReady={() => setRuntimeReady(true)} />

      <div className="trading-chart-head">
        <div>
          <p className="eyebrow">交易主区</p>
          <h3>{symbol.toUpperCase()}</h3>
          <p>图表是主角，研究层只做辅助判断。</p>
        </div>

        <div className="chart-status-row">
          <span>当前周期：{interval}</span>
          <span>当前价格：{currentPrice}</span>
          <span>最近图表点：{latestSignal}</span>
          <span>入场：{formatLatestMarkerPrice(markers.entries)}</span>
          <span>止损：{formatLatestMarkerPrice(markers.stops)}</span>
        </div>
      </div>

      <div className="trading-chart-grid">
        <TimeframeTabs
          symbol={symbol}
          activeInterval={interval}
          supportedIntervals={shortIntervals}
          onSelect={onSelectInterval}
          pendingInterval={pendingInterval}
          align="left"
        />

        <div className="trading-chart-stage">
          {runtimeReady && normalizedItems.length ? (
            <ProKlineChart
              symbol={symbol}
              interval={interval}
              items={normalizedItems}
              markers={markers}
              overlays={overlays}
              runtimeReady={runtimeReady}
            />
          ) : (
            renderFallbackChart(symbol, interval, normalizedItems, markers)
          )}
        </div>

        <TimeframeTabs
          symbol={symbol}
          activeInterval={interval}
          supportedIntervals={longIntervals}
          onSelect={onSelectInterval}
          pendingInterval={pendingInterval}
          align="right"
        />
      </div>

      <section className="panel" style={{ marginTop: 18 }}>
        <p className="eyebrow">图表下一步</p>
        <h3>看完图以后直接进入执行判断</h3>
        <p>最近图表点：{latestSignal}</p>
        <p>如果这根图和你的判断一致，下一步就去策略中心确认执行动作。</p>
        <a href={`/strategies?symbol=${encodeURIComponent(symbol.toUpperCase())}`}>进入策略中心</a>
      </section>
    </section>
  );
}

/* 按优先级挑选需要放到左右两侧的周期。 */
function pickIntervals(supportedIntervals: string[], preferredIntervals: string[]): string[] {
  const picked = preferredIntervals.filter((interval) => supportedIntervals.includes(interval));
  return picked.length ? picked : supportedIntervals;
}

/* 渲染 SVG 兜底视图。 */
function renderFallbackChart(symbol: string, interval: string, items: MarketCandle[], markers: ChartMarkerGroups) {
  if (!items.length) {
    return (
      <div className="chart-stage chart-stage-empty">
        <div className="chart-empty-state">
          <p className="eyebrow">交易主区</p>
          <h3>{symbol.toUpperCase()}</h3>
          <p>当前周期：{interval}</p>
          <p>暂无图表数据，先确认市场接口已经返回当前周期的 K 线。</p>
        </div>
      </div>
    );
  }

  const priceDomain = resolvePriceDomain(items, markers);
  const candles = buildChartCandles(items, priceDomain);
  const entryLine = resolveHorizontalLineY(markers.entries, candles, priceDomain);
  const stopLine = resolveHorizontalLineY(markers.stops, candles, priceDomain);
  const signals = buildSignalPoints(markers.signals, candles, priceDomain);
  const candleBodyWidth = resolveCandleBodyWidth(candles.length);

  return (
    <div className="chart-stage chart-stage-loading">
      <div className="chart-empty-state">
        <p className="eyebrow">交易主区</p>
        <h3>{symbol.toUpperCase()}</h3>
        <p>当前周期：{interval}</p>
      </div>

      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label={`${symbol} ${interval} candlestick chart`}
        style={{ width: "100%", height: "auto", display: "block" }}
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

      <div className="metric-grid chart-metrics-grid">
        <article className="metric-card">
          <p className="metric-label">最近图表点</p>
          <p className="metric-value">{formatLatestMarkerSummary(markers)}</p>
          <p className="metric-detail">主图里离现在最近的一次提示</p>
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
          <p className="metric-value">{resolveLatestCloseText(items)}</p>
          <p className="metric-detail">当前周期最后一根 K 线收盘价</p>
        </article>
      </div>
    </div>
  );
}

/* 根据价格范围构造可绘制 K 线。 */
function buildChartCandles(items: MarketCandle[], priceDomain: { min: number; max: number }): ChartCandle[] {
  const validItems = items.flatMap((item) => {
    const prices = resolveCandleValues(item);
    if (!prices) {
      return [];
    }
    return [{ item, prices }];
  });
  const step = validItems.length > 1 ? (CHART_WIDTH - CHART_PADDING * 2) / (validItems.length - 1) : 0;

  return validItems.map(({ item, prices }, index) => {
    const x = CHART_PADDING + step * index;
    const openY = mapPriceToY(prices.open, priceDomain);
    const closeY = mapPriceToY(prices.close, priceDomain);
    const highY = mapPriceToY(prices.high, priceDomain);
    const lowY = mapPriceToY(prices.low, priceDomain);
    const rising = prices.close >= prices.open;

    return {
      open_time: item.open_time,
      x,
      bodyX: x - resolveCandleBodyWidth(validItems.length) / 2,
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
  const prices: Array<number | null> = [];

  for (const item of items) {
    const candleValues = resolveCandleValues(item);
    if (candleValues) {
      prices.push(candleValues.high, candleValues.low, candleValues.open, candleValues.close);
    }
  }
  for (const group of [markers.entries, markers.stops, markers.signals]) {
    for (const item of group) {
      const price = toNumber(item.price);
      if (price !== null) {
        prices.push(price);
      }
    }
  }

  const finitePrices = prices.filter((price): price is number => price !== null);
  const min = finitePrices.length ? Math.min(...finitePrices) : 0;
  const max = finitePrices.length ? Math.max(...finitePrices) : 1;
  if (max === min) {
    return { min: min - 1, max: max + 1 };
  }

  const padding = (max - min) * 0.08;
  return { min: min - padding, max: max + padding };
}

/* 解析单个 K 线的数值。 */
function resolveCandleValues(item: MarketCandle): { open: number; high: number; low: number; close: number } | null {
  const open = toNumber(item.open);
  const high = toNumber(item.high);
  const low = toNumber(item.low);
  const close = toNumber(item.close);

  if (open === null || high === null || low === null || close === null) {
    return null;
  }

  return { open, high, low, close };
}

/* 根据价格范围映射 Y 轴位置。 */
function mapPriceToY(price: number, priceDomain: { min: number; max: number }): number {
  const chartHeight = CHART_HEIGHT - CHART_PADDING * 2;
  const ratio = (price - priceDomain.min) / (priceDomain.max - priceDomain.min);
  return CHART_HEIGHT - CHART_PADDING - chartHeight * ratio;
}

/* 构造信号点。 */
function buildSignalPoints(
  markers: Array<Record<string, unknown>>,
  candles: ChartCandle[],
  priceDomain: { min: number; max: number },
): ChartMarkerPoint[] {
  return markers.flatMap((item, index) => {
    const time = toNumber(item.time);
    const price = toNumber(item.price);
    if (time === null || price === null) {
      return [];
    }

    const candle = candles.find((candidate) => candidate.open_time === time);
    if (!candle) {
      return [];
    }

    return [
      {
        key: `${String(item.strategy_id ?? "signal")}-${index}`,
        x: candle.x,
        y: mapPriceToY(price, priceDomain),
      },
    ];
  });
}

/* 计算 K 线主体宽度。 */
function resolveCandleBodyWidth(length: number): number {
  if (length <= 4) {
    return 24;
  }
  return Math.max(8, Math.min(18, ((CHART_WIDTH - CHART_PADDING * 2) / length) * 0.65));
}

/* 解析横向价格线。 */
function resolveHorizontalLineY(
  items: Array<Record<string, unknown>>,
  candles: ChartCandle[],
  priceDomain: { min: number; max: number },
): number | null {
  const price = resolveLatestMarkerPrice(items);
  if (price === null) {
    return null;
  }

  const hasCandle = candles.length > 0;
  return hasCandle ? mapPriceToY(price, priceDomain) : null;
}

/* 格式化最新标记价格。 */
function formatLatestMarkerPrice(items: Array<Record<string, unknown>>): string {
  const price = resolveLatestMarkerPrice(items);
  if (price === null) {
    return "n/a";
  }
  return formatPrice(price);
}

/* 返回最近一个图表标记的摘要，避免把 entry/stop 都误说成 signal。 */
function formatLatestMarkerSummary(markers: ChartMarkerGroups): string {
  const latest = [...markers.signals, ...markers.entries, ...markers.stops]
    .slice()
    .sort((left, right) => {
      const leftTime = toNumber(left.time) ?? 0;
      const rightTime = toNumber(right.time) ?? 0;
      return rightTime - leftTime;
    })[0];

  if (!latest) {
    return "暂无";
  }

  const label = String(latest.label ?? latest.strategy_id ?? "signal").trim();
  const price = resolveSingleMarkerPrice(latest);
  return price === null ? label : `${label} @ ${formatPrice(price)}`;
}

/* 解析最近一个价格。 */
function resolveLatestMarkerPrice(items: Array<Record<string, unknown>>): number | null {
  const reversed = items.slice().reverse();
  for (const item of reversed) {
    const price = resolveSingleMarkerPrice(item);
    if (price !== null) {
      return price;
    }
  }
  return null;
}

/* 解析单个标记上的价格字段。 */
function resolveSingleMarkerPrice(item: Record<string, unknown>): number | null {
  return toNumber(item.price);
}

/* 获取最新收盘价。 */
function resolveLatestCloseText(items: MarketCandle[]): string {
  const latest = items[items.length - 1];
  return latest ? latest.close : "n/a";
}

/* 将数值统一成图表可读形式。 */
function formatPrice(value: number): string {
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 6 });
}

/* 将未知值转换成数字。 */
function toNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
