/* 这个文件负责渲染单币页的交易终端外壳。 */

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { AppShell } from "../../../components/app-shell";
import { MarketSymbolWorkspace } from "../../../components/market-symbol-workspace";
import { PageHero } from "../../../components/page-hero";
import { Button } from "../../../components/ui/button";
import {
  type ApiEnvelope,
  getMarketChart,
  getResearchCandidate,
  getResearchCandidatesFallback,
  type MarketChartData,
  type ResearchCandidateItem,
  type ResearchCockpitSummary,
} from "../../../lib/api";
import { getControlSessionState } from "../../../lib/session";

type PageProps = {
  params: Promise<{ symbol: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

/* 渲染单币交易终端页面。 */
export default async function MarketSymbolPage({ params, searchParams }: PageProps) {
  const session = await getControlSessionState();
  const { symbol } = await params;
  const normalizedSymbol = symbol.toUpperCase();
  const query = (await searchParams) ?? {};
  const interval = readQueryText(query.interval);
  let chartData = getEmptyMarketChartData();
  let candidate: ResearchCandidateItem | null =
    getResearchCandidatesFallback().items.find((item) => item.symbol === normalizedSymbol) ?? null;

  const [chartResult, candidateResult] = await Promise.all([
    withTimeout(getMarketChart(symbol, interval), getMarketChartTimeoutFallback(), 2500),
    withTimeout(getResearchCandidate(normalizedSymbol), getResearchCandidateTimeoutFallback(), 1500),
  ]);
  if (!chartResult.error) {
    chartData = chartResult.data;
  }
  if (!candidateResult.error) {
    candidate = candidateResult.data.item;
  }

  return (
    <AppShell
      title={normalizedSymbol}
      subtitle="图表是主角，周期切换、研究判断和执行准备都围绕主图展开。"
      currentPath="/market"
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
        <MarketSymbolWorkspace symbol={normalizedSymbol} initialData={chartData} candidate={candidate} />
      </section>
    </AppShell>
  );
}

/* 读取查询参数里的单个文本值。 */
function readQueryText(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
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
