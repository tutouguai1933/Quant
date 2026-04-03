/* 这个文件负责渲染单币页的交易终端外壳。 */

import { AppShell } from "../../../components/app-shell";
import { MarketSymbolWorkspace } from "../../../components/market-symbol-workspace";
import { PageHero } from "../../../components/page-hero";
import { ResearchCandidateBoard } from "../../../components/research-candidate-board";
import { getMarketChart, getResearchCandidate, getResearchCandidatesFallback, type MarketChartData, type ResearchCockpitSummary } from "../../../lib/api";
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
  let candidate = getResearchCandidatesFallback().items.find((item) => item.symbol === normalizedSymbol) ?? null;

  try {
    const response = await getMarketChart(symbol, interval);
    if (!response.error) {
      chartData = response.data;
    }
  } catch {
    // API 暂时不可用时保留骨架页面。
  }

  try {
    const response = await getResearchCandidate(normalizedSymbol);
    if (!response.error) {
      candidate = response.data.item;
    }
  } catch {
    // API 暂时不可用时保留候选兜底数据。
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
      />
      {/* MarketSymbolWorkspace 统一承载 TimeframeTabs / TradingChartPanel / ResearchSidecard / MultiTimeframeSummary，替代旧的 trading-layout 直出结构。 */}
      <MarketSymbolWorkspace symbol={normalizedSymbol} initialData={chartData} />
      <ResearchCandidateBoard
        title="研究候选"
        summary={{
          candidate_count: candidate ? 1 : 0,
          ready_count: candidate?.allowed_to_dry_run ? 1 : 0,
        }}
        items={candidate ? [candidate] : []}
        focusSymbol={normalizedSymbol}
        nextStep={chartData.strategy_context.next_step || "下一步动作：先看是否允许进入 dry-run，再决定要不要进入策略中心。"}
      />
      <section className="panel">
        <p className="eyebrow">下一步动作</p>
        <h3>先决定继续研究还是进入执行</h3>
        <p>
          {candidate?.allowed_to_dry_run
            ? "这个币当前已经允许进入 dry-run，可以继续去策略中心确认是否派发。"
            : "这个币当前还不适合直接进入执行，先回信号页继续研究。"}
        </p>
        <div className="action-grid">
          <a className="button-link secondary-link" href={`/strategies?symbol=${encodeURIComponent(normalizedSymbol)}`}>
            进入策略中心
          </a>
          <a className="button-link secondary-link" href="/signals">
            返回信号页继续研究
          </a>
        </div>
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
