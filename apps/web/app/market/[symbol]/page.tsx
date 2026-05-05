/* 这个文件负责渲染单币页的交易终端外壳。 */
"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { TerminalShell } from "../../../components/terminal/terminal-shell";
import { MarketSymbolWorkspace } from "../../../components/market-symbol-workspace";
import { PageHero } from "../../../components/page-hero";
import { Button } from "../../../components/ui/button";
import { Skeleton } from "../../../components/ui/skeleton";
import {
  type ApiEnvelope,
  getMarketChart,
  getResearchCandidate,
  getResearchCandidatesFallback,
  type MarketChartData,
  type ResearchCandidateItem,
  type ResearchCockpitSummary,
} from "../../../lib/api";

/* 渲染单币交易终端页面。 */
export default function MarketSymbolPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const symbol = (params?.symbol as string) ?? "";
  const normalizedSymbol = symbol.toUpperCase();
  const interval = searchParams?.get("interval") ?? undefined;

  const [session, setSession] = useState<{ isAuthenticated: boolean }>({
    isAuthenticated: false,
  });
  const [chartData, setChartData] = useState<MarketChartData>(getEmptyMarketChartData());
  const [candidate, setCandidate] = useState<ResearchCandidateItem | null>(
    getResearchCandidatesFallback().items.find((item) => item.symbol === normalizedSymbol) ?? null
  );
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {
        // Keep default session state
      });
  }, []);

  useEffect(() => {
    let mounted = true;

    const loadData = async () => {
      setIsLoading(true);

      const [chartResult, candidateResult] = await Promise.all([
        withTimeout(getMarketChart(symbol, interval), getMarketChartTimeoutFallback(), 2500),
        withTimeout(getResearchCandidate(normalizedSymbol), getResearchCandidateTimeoutFallback(), 1500),
      ]);

      if (!mounted) return;

      if (!chartResult.error) {
        setChartData(chartResult.data);
      }
      if (!candidateResult.error) {
        setCandidate(candidateResult.data.item);
      }

      setIsLoading(false);
    };

    loadData();

    return () => {
      mounted = false;
    };
  }, [symbol, normalizedSymbol, interval]);

  return (
    <TerminalShell
      breadcrumb={`市场 / ${normalizedSymbol}`}
      title={normalizedSymbol}
      subtitle="K线图表和技术指标"
      currentPath="/market/[symbol]"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="交易视图"
        title={`${normalizedSymbol} 单币页`}
        description="这里先看主图，再看研究倾向、入场位和止损位，最后决定要不要进入策略执行。"
        aside={
          <div className="grid gap-2">
            <Button asChild variant="secondary" size="sm">
              <Link href="/market">
                <ArrowLeft />
                返回市场页
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/signals">返回信号页继续研究</Link>
            </Button>
          </div>
        }
      />

      <section className="space-y-6">
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        ) : (
          <MarketSymbolWorkspace symbol={normalizedSymbol} initialData={chartData} candidate={candidate} />
        )}
      </section>
    </TerminalShell>
  );
}

/* 返回单币页的空策略上下文。 */
function getEmptyStrategyContext(): MarketChartData["strategy_context"] {
  return {
    recommended_strategy: "none",
    trend_state: "neutral",
    next_step: "",
    primary_reason: "",
    evaluations: {},
  };
}

/* 返回单币页的空执行准备状态。 */
function getEmptyFreqtradeReadiness(): MarketChartData["freqtrade_readiness"] {
  return {
    executor: "freqtrade",
    backend: "memory",
    runtime_mode: "demo",
    ready_for_real_freqtrade: false,
    reason: "unknown",
    next_step: "",
  };
}

/* 返回单币页的空研究侧卡数据。 */
function getEmptyResearchCockpit(): ResearchCockpitSummary {
  return {
    research_bias: "unavailable",
    recommended_strategy: "none",
    confidence: "low",
    research_gate: { status: "unavailable" },
    primary_reason: "",
    research_explanation: "",
    model_version: "",
    generated_at: "",
    signal_count: 0,
    entry_hint: "n/a",
    stop_hint: "n/a",
    overlay_summary: "0 个信号点 / 入场 n/a / 止损 n/a",
  };
}

/* 返回单币页的空图表数据。 */
function getEmptyMarketChartData(): MarketChartData {
  return {
    items: [],
    overlays: {
      ema_fast: { value: null, ready: false, sample_size: 0, warnings: [], last_candle_closed: false },
      ema_slow: { value: null, ready: false, sample_size: 0, warnings: [], last_candle_closed: false },
      atr: { value: null, ready: false, sample_size: 0, warnings: [], last_candle_closed: false },
      rsi: { value: null, ready: false, sample_size: 0, warnings: [], last_candle_closed: false },
      volume_sma: { value: null, ready: false, sample_size: 0, warnings: [], last_candle_closed: false },
    },
    markers: { signals: [], entries: [], stops: [] },
    active_interval: "4h",
    supported_intervals: ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
    multi_timeframe_summary: [],
    research_cockpit: getEmptyResearchCockpit(),
    strategy_context: getEmptyStrategyContext(),
    freqtrade_readiness: getEmptyFreqtradeReadiness(),
  };
}

/* 为慢接口提供服务端超时降级，避免整页等待过久。 */
async function withTimeout<T>(promise: Promise<T>, fallback: T, timeoutMs: number): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<T>((resolve) => {
        timeoutId = setTimeout(() => resolve(fallback), timeoutMs);
      }),
    ]);
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

/* 返回市场图表接口的超时兜底响应。 */
function getMarketChartTimeoutFallback(): ApiEnvelope<MarketChartData> {
  return {
    data: getEmptyMarketChartData(),
    error: {
      code: "market_chart_timeout",
      message: "图表加载较慢，页面先展示空图，稍后可切换周期重试。",
    },
    meta: {},
  };
}

/* 返回研究候选接口的超时兜底响应。 */
function getResearchCandidateTimeoutFallback(): ApiEnvelope<{ item: ResearchCandidateItem | null }> {
  return {
    data: { item: null },
    error: {
      code: "research_candidate_timeout",
      message: "研究候选加载较慢，页面先展示基础视图。",
    },
    meta: {},
  };
}