/* 这个文件负责把单币页组织成客户端交易工作区。 */

"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";

import { getMarketChart, type MarketChartData, type ResearchCandidateItem } from "../lib/api";
import { MultiTimeframeSummary } from "./multi-timeframe-summary";
import { ResearchSidecard } from "./research-sidecard";
import { StatusBadge } from "./status-badge";
import { TradingChartPanel } from "./trading-chart-panel";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";


type MarketSymbolWorkspaceProps = {
  symbol: string;
  initialData: MarketChartData;
  candidate: ResearchCandidateItem | null;
};

const chartCache = new Map<string, MarketChartData>();

/* 用客户端状态把主图区、研究侧卡和多周期摘要串起来。 */
export function MarketSymbolWorkspace({ symbol, initialData, candidate }: MarketSymbolWorkspaceProps) {
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
    <section className="space-y-5">
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
        <section className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5">
          <p className="eyebrow">切换反馈</p>
          <h3 className="text-lg font-semibold">图表没有切过去</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{errorMessage}</p>
        </section>
      ) : null}

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_340px] lg:items-start">
        <div className="space-y-5">
          <MultiTimeframeSummary items={chartData.multi_timeframe_summary} />
        </div>

        <div className="grid gap-4 lg:sticky lg:top-6">
          <ResearchSidecard cockpit={chartData.research_cockpit} nextStep={chartData.strategy_context.next_step} />
          <CompactDecisionCard
            symbol={symbol}
            candidate={candidate}
            entryHint={chartData.research_cockpit.entry_hint}
            stopHint={chartData.research_cockpit.stop_hint}
            nextStep={chartData.strategy_context.next_step}
            freqtradeReadiness={freqtradeReadiness}
          />
        </div>
      </section>
    </section>
  );
}

function CompactDecisionCard({
  symbol,
  candidate,
  entryHint,
  stopHint,
  nextStep,
  freqtradeReadiness,
}: {
  symbol: string;
  candidate: ResearchCandidateItem | null;
  entryHint?: string;
  stopHint?: string;
  nextStep?: string;
  freqtradeReadiness: MarketChartData["freqtrade_readiness"];
}) {
  const gateValue = candidate ? (candidate.allowed_to_dry_run ? "ready_for_dry_run" : candidate.dry_run_gate.status) : "unavailable";
  const gateReasons = candidate?.dry_run_gate.reasons.length ? candidate.dry_run_gate.reasons.join(" / ") : "无";

  return (
    <Card className="bg-card/92">
      <CardHeader className="gap-3">
        <p className="eyebrow">执行摘要</p>
        <CardTitle>把判断压缩成一组可执行结论</CardTitle>
        <CardDescription>这里不再拉长页面，只保留当前这个币最关键的研究结论、执行准备和下一步动作。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          <CompactStat label="研究分数" value={candidate?.score ?? "n/a"} />
          <CompactStat label="研究门" valueNode={<StatusBadge value={gateValue} />} />
          <CompactStat label="入场参考" value={formatText(entryHint, "n/a")} />
          <CompactStat label="止损参考" value={formatText(stopHint, "n/a")} />
          <CompactStat label="执行模式" value={freqtradeReadiness.runtime_mode} />
          <CompactStat label="真实 dry-run" value={freqtradeReadiness.ready_for_real_freqtrade ? "ready" : "not_ready"} />
        </div>

        {candidate ? (
          <div className="rounded-2xl border border-border/70 bg-background/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">{candidate.symbol}</p>
                <p className="text-xs text-muted-foreground">{candidate.strategy_template}</p>
              </div>
              <StatusBadge value={gateValue} />
            </div>
            <div className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2 lg:grid-cols-1">
              <p>回测收益：<span className="text-foreground">{readMetric(candidate, "total_return_pct")}%</span></p>
              <p>最大回撤：<span className="text-foreground">{readMetric(candidate, "max_drawdown_pct")}%</span></p>
              <p>Sharpe：<span className="text-foreground">{readMetric(candidate, "sharpe")}</span></p>
            </div>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">失败原因：<span className="text-foreground">{gateReasons}</span></p>
          </div>
        ) : null}

        <div className="rounded-2xl border border-border/70 bg-background/50 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">下一步动作</p>
          <p className="mt-2 text-sm leading-6 text-foreground">{formatText(nextStep, "先继续观察。")}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <Button asChild>
              <Link href={`/strategies?symbol=${encodeURIComponent(symbol.toUpperCase())}`}>进入策略中心</Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href="/signals">返回信号页继续研究</Link>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CompactStat({
  label,
  value,
  valueNode,
}: {
  label: string;
  value?: string;
  valueNode?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/35 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <div className="mt-2 text-sm font-medium text-foreground">{valueNode ?? value}</div>
    </div>
  );
}

function readMetric(candidate: ResearchCandidateItem, key: string): string {
  return String(candidate.backtest.metrics[key] || "n/a");
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
