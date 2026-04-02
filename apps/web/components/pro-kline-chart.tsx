/* 这个文件负责渲染专业 K 线主图。 */

"use client";

import { useEffect, useRef, useState } from "react";

import type { ChartIndicatorSummary, ChartMarkerGroups, MarketCandle } from "../lib/api";

type ProKlineChartProps = {
  symbol: string;
  interval: string;
  items: MarketCandle[];
  markers: ChartMarkerGroups;
  overlays: ChartIndicatorSummary;
  runtimeReady: boolean;
};

type NormalizedCandle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  openText: string;
  highText: string;
  lowText: string;
  closeText: string;
  volumeText: string;
};

type HoverState = {
  timeText: string;
  openText: string;
  highText: string;
  lowText: string;
  closeText: string;
  volumeText: string;
} | null;

type LightweightChartsRuntime = {
  createChart: (container: HTMLElement, options: Record<string, unknown>) => LightweightChartInstance;
  LineStyle: {
    Solid: number;
    Dotted: number;
    Dashed: number;
  };
  CrosshairMode: {
    Normal: number;
  };
};

type LightweightChartInstance = {
  addCandlestickSeries: (options: Record<string, unknown>) => CandlestickSeries;
  addHistogramSeries: (options: Record<string, unknown>) => HistogramSeries;
  subscribeCrosshairMove: (handler: (param: CrosshairMoveParam) => void) => void;
  unsubscribeCrosshairMove: (handler: (param: CrosshairMoveParam) => void) => void;
  timeScale: () => {
    fitContent: () => void;
  };
  applyOptions: (options: Record<string, unknown>) => void;
  remove: () => void;
};

type CandlestickSeries = {
  setData: (data: Array<Record<string, unknown>>) => void;
  setMarkers: (markers: Array<Record<string, unknown>>) => void;
  createPriceLine: (options: Record<string, unknown>) => void;
};

type HistogramSeries = {
  setData: (data: Array<Record<string, unknown>>) => void;
};

type CrosshairMoveParam = {
  time?: number | { year: number; month: number; day: number };
  seriesData: Map<unknown, Record<string, unknown>>;
};

declare global {
  interface Window {
    LightweightCharts?: LightweightChartsRuntime;
  }
}

const CHART_HEIGHT = 520;

/* 渲染专业 K 线、成交量和悬浮信息。 */
export function ProKlineChart({
  symbol,
  interval,
  items,
  markers,
  overlays,
  runtimeReady,
}: ProKlineChartProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [hoverState, setHoverState] = useState<HoverState>(null);

  useEffect(() => {
    if (!runtimeReady || !hostRef.current || !window.LightweightCharts) {
      return undefined;
    }

    const runtime = window.LightweightCharts;
    const normalizedItems = normalizeCandles(items);
    const width = Math.max(Math.floor(hostRef.current.getBoundingClientRect().width), 320);
    const chart = runtime.createChart(hostRef.current, {
      width,
      height: CHART_HEIGHT,
      layout: {
        background: { color: "rgba(0, 0, 0, 0)" },
        textColor: "#1a2e35",
        fontFamily: '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
      },
      grid: {
        vertLines: { color: "rgba(21, 40, 49, 0.06)" },
        horzLines: { color: "rgba(21, 40, 49, 0.06)" },
      },
      crosshair: {
        mode: runtime.CrosshairMode.Normal,
        vertLine: {
          width: 1,
          style: runtime.LineStyle.Dashed,
          color: "rgba(25, 95, 88, 0.7)",
        },
        horzLine: {
          width: 1,
          style: runtime.LineStyle.Dashed,
          color: "rgba(25, 95, 88, 0.7)",
        },
      },
      rightPriceScale: {
        visible: true,
        borderColor: "rgba(21, 40, 49, 0.12)",
      },
      timeScale: {
        visible: true,
        timeVisible: true,
        secondsVisible: interval === "1m",
        borderColor: "rgba(21, 40, 49, 0.12)",
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      localization: {
        locale: "zh-CN",
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#195f58",
      downColor: "#b64e3f",
      borderVisible: false,
      wickUpColor: "#195f58",
      wickDownColor: "#b64e3f",
    });
    const histogramSeries = chart.addHistogramSeries({
      color: "rgba(25, 95, 88, 0.34)",
      priceFormat: { type: "volume" },
      priceScaleId: "",
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    candleSeries.setData(
      normalizedItems.map((item) => ({
        time: item.time,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
      })),
    );
    histogramSeries.setData(
      normalizedItems.map((item) => ({
        time: item.time,
        value: item.volume,
        color: item.close >= item.open ? "rgba(25, 95, 88, 0.28)" : "rgba(182, 78, 63, 0.28)",
      })),
    );

    candleSeries.setMarkers(buildChartMarkers(markers, normalizedItems));
    attachPriceLines(candleSeries, markers);
    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (!hostRef.current) {
        return;
      }
      const rect = hostRef.current.getBoundingClientRect();
      chart.applyOptions({
        width: Math.max(Math.floor(rect.width), 320),
        height: CHART_HEIGHT,
      });
    });
    resizeObserver.observe(hostRef.current);

    const hoverHandler = (param: CrosshairMoveParam) => {
      if (!param.time || !param.seriesData) {
        setHoverState(null);
        return;
      }

      const pointData = param.seriesData.get(candleSeries);
      if (!pointData) {
        setHoverState(null);
        return;
      }

      setHoverState({
        timeText: formatCrosshairTime(param.time),
        openText: formatMaybeNumber(pointData.open, "n/a"),
        highText: formatMaybeNumber(pointData.high, "n/a"),
        lowText: formatMaybeNumber(pointData.low, "n/a"),
        closeText: formatMaybeNumber(pointData.close, "n/a"),
        volumeText: formatMaybeNumber(pointData.volume, "n/a"),
      });
    };

    chart.subscribeCrosshairMove(hoverHandler);

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(hoverHandler);
      chart.remove();
    };
  }, [runtimeReady, items, markers, interval]);

  const latest = getLatestCandle(items);

  if (!runtimeReady) {
    return (
      <div className="chart-stage chart-stage-loading">
        <div className="chart-empty-state">
          <p className="eyebrow">图表引擎加载中</p>
          <h3>{symbol.toUpperCase()}</h3>
          <p>专业图表运行时正在准备，随后会显示可拖拽、可缩放的 K 线主图。</p>
        </div>
      </div>
    );
  }

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

  return (
    <div className="chart-stage">
      <div className="chart-topline">
        <div>
          <p className="eyebrow">交易主区</p>
          <h3>{symbol.toUpperCase()}</h3>
        </div>
        <div className="chart-topline-meta">
          <span>当前周期：{interval}</span>
          <span>当前价格：{latest?.closeText ?? "n/a"}</span>
          <span>信号：{markers.signals.length}</span>
        </div>
      </div>

      <div ref={hostRef} className="pro-kline-chart" aria-label={`${symbol} ${interval} K 线图`} />

      <div className="chart-summary-strip">
        <article className="chart-summary-chip">
          <span>EMA 快</span>
          <strong>{formatOverlayMetric(overlays.ema_fast)}</strong>
        </article>
        <article className="chart-summary-chip">
          <span>EMA 慢</span>
          <strong>{formatOverlayMetric(overlays.ema_slow)}</strong>
        </article>
        <article className="chart-summary-chip">
          <span>ATR</span>
          <strong>{formatOverlayMetric(overlays.atr)}</strong>
        </article>
        <article className="chart-summary-chip">
          <span>RSI</span>
          <strong>{formatOverlayMetric(overlays.rsi)}</strong>
        </article>
        <article className="chart-summary-chip">
          <span>成交量均值</span>
          <strong>{formatOverlayMetric(overlays.volume_sma)}</strong>
        </article>
      </div>

      <div className="chart-hover-panel">
        <div className="chart-hover-line">
          <strong>悬浮信息</strong>
          <span>{hoverState?.timeText ?? "移动鼠标查看单根 K 线"}</span>
        </div>
        <div className="chart-hover-grid">
          <div>
            <span>开</span>
            <strong>{hoverState?.openText ?? latest?.openText ?? "n/a"}</strong>
          </div>
          <div>
            <span>高</span>
            <strong>{hoverState?.highText ?? latest?.highText ?? "n/a"}</strong>
          </div>
          <div>
            <span>低</span>
            <strong>{hoverState?.lowText ?? latest?.lowText ?? "n/a"}</strong>
          </div>
          <div>
            <span>收</span>
            <strong>{hoverState?.closeText ?? latest?.closeText ?? "n/a"}</strong>
          </div>
          <div>
            <span>量</span>
            <strong>{hoverState?.volumeText ?? latest?.volumeText ?? "n/a"}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}

/* 把字符串 K 线数据转成数值数据。 */
function normalizeCandles(items: MarketCandle[]): NormalizedCandle[] {
  return items
    .map((item) => {
      const open = toNumber(item.open);
      const high = toNumber(item.high);
      const low = toNumber(item.low);
      const close = toNumber(item.close);
      const volume = toNumber(item.volume);
      if ([open, high, low, close, volume].some((value) => value === null)) {
        return null;
      }
      return {
        time: Math.floor(item.open_time / 1000),
        open,
        high,
        low,
        close,
        volume,
        openText: item.open,
        highText: item.high,
        lowText: item.low,
        closeText: item.close,
        volumeText: item.volume,
      };
    })
    .filter((item): item is NormalizedCandle => item !== null)
    .sort((left, right) => left.time - right.time);
}

/* 把研究标记转成图表标记。 */
function buildChartMarkers(markers: ChartMarkerGroups, candles: NormalizedCandle[]): Array<Record<string, unknown>> {
  const knownTimes = new Set(candles.map((item) => item.time));
  return [...markers.signals, ...markers.entries, ...markers.stops].flatMap((item) => {
    const time = resolveMarkerTime(item);
    if (time === null || !knownTimes.has(time)) {
      return [];
    }
    return [
      {
        time,
        position: resolveMarkerPosition(item),
        color: resolveMarkerColor(item),
        shape: resolveMarkerShape(item),
        text: resolveMarkerText(item),
      },
    ];
  });
}

/* 给入场和止损线生成价格线。 */
function attachPriceLines(series: CandlestickSeries, markers: ChartMarkerGroups) {
  const entryPrice = resolveLatestMarkerPrice(markers.entries);
  if (entryPrice !== null) {
    series.createPriceLine({
      price: entryPrice,
      color: "#bc8c2b",
      lineStyle: 2,
      lineWidth: 2,
      axisLabelVisible: true,
      title: "entry",
    });
  }

  const stopPrice = resolveLatestMarkerPrice(markers.stops);
  if (stopPrice !== null) {
    series.createPriceLine({
      price: stopPrice,
      color: "#b64e3f",
      lineStyle: 2,
      lineWidth: 2,
      axisLabelVisible: true,
      title: "stop",
    });
  }
}

/* 解析图表标记的时间。 */
function resolveMarkerTime(item: Record<string, unknown>): number | null {
  const time = toNumber(item.time);
  if (time !== null) {
    return Math.floor(time / 1000);
  }
  return null;
}

/* 解析图表标记的价格。 */
function resolveLatestMarkerPrice(items: Array<Record<string, unknown>>): number | null {
  const reversed = items.slice().reverse();
  for (const item of reversed) {
    const price = toNumber(item.price);
    if (price !== null) {
      return price;
    }
  }
  return null;
}

/* 解析图表标记的位置。 */
function resolveMarkerPosition(item: Record<string, unknown>): "aboveBar" | "belowBar" | "inBar" {
  const label = String(item.label ?? item.strategy_id ?? "").toLowerCase();
  if (label.includes("stop")) {
    return "aboveBar";
  }
  if (label.includes("entry") || label.includes("signal")) {
    return "belowBar";
  }
  return "inBar";
}

/* 解析图表标记的颜色。 */
function resolveMarkerColor(item: Record<string, unknown>): string {
  const label = String(item.label ?? item.strategy_id ?? "").toLowerCase();
  if (label.includes("stop")) {
    return "#b64e3f";
  }
  if (label.includes("entry")) {
    return "#bc8c2b";
  }
  return "#195f58";
}

/* 解析图表标记的形状。 */
function resolveMarkerShape(item: Record<string, unknown>): "arrowUp" | "arrowDown" | "circle" {
  const label = String(item.label ?? item.strategy_id ?? "").toLowerCase();
  if (label.includes("stop")) {
    return "arrowDown";
  }
  if (label.includes("entry")) {
    return "arrowUp";
  }
  return "circle";
}

/* 解析图表标记的文字。 */
function resolveMarkerText(item: Record<string, unknown>): string {
  const label = String(item.label ?? item.strategy_id ?? "signal").trim();
  const reason = String(item.reason ?? "").trim();
  return reason ? `${label} · ${reason}` : label;
}

/* 获取最新一根 K 线。 */
function getLatestCandle(items: MarketCandle[]): NormalizedCandle | null {
  const normalized = normalizeCandles(items);
  return normalized.length ? normalized[normalized.length - 1] : null;
}

/* 格式化交叉光标时间。 */
function formatCrosshairTime(value: number | { year: number; month: number; day: number }): string {
  if (typeof value === "number") {
    return new Date(value * 1000).toLocaleString("zh-CN", { hour12: false });
  }
  return `${value.year}-${String(value.month).padStart(2, "0")}-${String(value.day).padStart(2, "0")}`;
}

/* 格式化可选数字。 */
function formatMaybeNumber(value: unknown, fallback: string): string {
  const numberValue = toNumber(value);
  if (numberValue === null) {
    return fallback;
  }
  return formatPrice(numberValue);
}

/* 格式化指标摘要。 */
function formatOverlayMetric(item: ChartIndicatorSummary["ema_fast"]): string {
  if (!item.ready || item.value === null) {
    return "n/a";
  }
  return item.value;
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
