/* 这个文件负责把单币页组织成客户端交易工作区。 */

"use client";

import { useEffect, useRef, useState } from "react";

import { getMarketChart, type MarketChartData } from "../lib/api";
import { MultiTimeframeSummary } from "./multi-timeframe-summary";
import { ResearchSidecard } from "./research-sidecard";
import { TradingChartPanel } from "./trading-chart-panel";


type MarketSymbolWorkspaceProps = {
  symbol: string;
  initialData: MarketChartData;
};

const chartCache = new Map<string, MarketChartData>();

/* 用客户端状态把主图区、研究侧卡和多周期摘要串起来。 */
export function MarketSymbolWorkspace({ symbol, initialData }: MarketSymbolWorkspaceProps) {
  const [chartData, setChartData] = useState(initialData);
  const [pendingInterval, setPendingInterval] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const requestIdRef = useRef(0);

  useEffect(() => {
    setChartData(initialData);
    chartCache.set(`${symbol}:${initialData.active_interval}`, initialData);
  }, [initialData, symbol]);

  function handleIntervalSelect(nextInterval: string) {
    if (nextInterval === chartData.active_interval) {
      return;
    }

    requestIdRef.current += 1;
    const requestId = requestIdRef.current;
    const cacheKey = `${symbol}:${nextInterval}`;
    const cached = chartCache.get(cacheKey);
    if (cached) {
      setChartData(cached);
      setPendingInterval("");
      setErrorMessage("");
      syncIntervalToAddressBar(symbol, cached.active_interval);
      return;
    }

    setPendingInterval(nextInterval);
    setErrorMessage("");

    void getMarketChart(symbol, nextInterval)
      .then((response) => {
        if (requestIdRef.current !== requestId) {
          return;
        }

        if (response.error) {
          setErrorMessage(response.error.message || "切换周期失败。");
          return;
        }

        chartCache.set(cacheKey, response.data);
        setChartData(response.data);
        syncIntervalToAddressBar(symbol, response.data.active_interval);
      })
      .catch(() => {
        if (requestIdRef.current === requestId) {
          setErrorMessage("图表切换失败，请稍后再试。");
        }
      })
      .finally(() => {
        if (requestIdRef.current === requestId) {
          setPendingInterval("");
        }
      }
      );
  }

  const freqtradeReadiness = chartData.freqtrade_readiness;

  return (
    <section className="terminal-layout">
      <div className="terminal-main">
        <TradingChartPanel
          symbol={symbol}
          interval={chartData.active_interval}
          supportedIntervals={chartData.supported_intervals}
          onSelectInterval={handleIntervalSelect}
          pendingInterval={pendingInterval}
          items={chartData.items}
          overlays={chartData.overlays}
          markers={chartData.markers}
        />

        {errorMessage ? (
          <section className="panel terminal-inline-error">
            <p className="eyebrow">切换反馈</p>
            <h3>图表没有切过去</h3>
            <p>{errorMessage}</p>
          </section>
        ) : null}

        <MultiTimeframeSummary items={chartData.multi_timeframe_summary} />

        <section className="panel terminal-footer-grid">
          <article>
            <p className="eyebrow">图表动作</p>
            <h3>先看入场位和止损位</h3>
            <p>入场参考：{formatText(chartData.research_cockpit.entry_hint, "n/a")}</p>
            <p>止损参考：{formatText(chartData.research_cockpit.stop_hint, "n/a")}</p>
            <p>下一步：{formatText(chartData.strategy_context.next_step, "先继续观察。")}</p>
          </article>
          <article>
            <p className="eyebrow">Freqtrade 准备情况</p>
            <h3>执行前先确认联调状态</h3>
            <p>当前后端：{freqtradeReadiness.backend}</p>
            <p>当前模式：{freqtradeReadiness.runtime_mode}</p>
            <p>真实 dry-run 条件：{freqtradeReadiness.ready_for_real_freqtrade ? "ready" : "not_ready"}</p>
          </article>
        </section>

      </div>

      <ResearchSidecard cockpit={chartData.research_cockpit} nextStep={chartData.strategy_context.next_step} />
    </section>
  );
}

/* 只更新浏览器地址栏里的周期参数，不触发整页刷新。 */
function syncIntervalToAddressBar(symbol: string, interval: string) {
  if (typeof window === "undefined") {
    return;
  }

  const url = new URL(window.location.href);
  url.pathname = `/market/${encodeURIComponent(symbol)}`;
  url.searchParams.set("interval", interval);
  window.history.replaceState(window.history.state, "", url.toString());
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
