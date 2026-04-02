/* 这个文件负责渲染单币页的交易视图骨架。 */

import { AppShell } from "../../../components/app-shell";
import { MultiTimeframeSummary } from "../../../components/multi-timeframe-summary";
import { PageHero } from "../../../components/page-hero";
import { ResearchSidecard } from "../../../components/research-sidecard";
import { TimeframeTabs } from "../../../components/timeframe-tabs";
import { TradingChartPanel } from "../../../components/trading-chart-panel";
import {
  getMarketChart,
  type MarketChartData,
  type ResearchCockpitSummary,
} from "../../../lib/api";
import { getControlSessionState } from "../../../lib/session";


type PageProps = {
  params: Promise<{ symbol: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

/* 渲染单币交易视图骨架。 */
export default async function MarketSymbolPage({ params, searchParams }: PageProps) {
  const session = await getControlSessionState();
  const { symbol } = await params;
  const normalizedSymbol = symbol.toUpperCase();
  const query = (await searchParams) ?? {};
  const interval = readQueryText(query.interval);
  let chartData = getEmptyMarketChartData();

  try {
    const response = await getMarketChart(symbol, interval);
    if (!response.error) {
      chartData = response.data;
    }
  } catch {
    // API 暂时不可用时保留骨架页面。
  }

  const strategyContext = chartData.strategy_context;
  const research_cockpit = chartData.research_cockpit;
  const freqtradeReadiness = chartData.freqtrade_readiness;

  return (
    <AppShell
      title={normalizedSymbol}
      subtitle="单币页现在先切成交易视图骨架，后续再把真正的主图细化进去。"
      currentPath="/market"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="交易视图"
        title={`${normalizedSymbol} 单币页`}
        description="这里先回答三件事：当前看哪个周期、主图里有什么关键点、研究解释建议下一步怎么做。"
      />

      <TimeframeTabs
        symbol={normalizedSymbol}
        activeInterval={chartData.active_interval}
        supportedIntervals={chartData.supported_intervals}
      />

      <div className="trading-layout">
        <TradingChartPanel
          symbol={normalizedSymbol}
          interval={chartData.active_interval}
          items={chartData.items}
          markers={chartData.markers}
        />
        <ResearchSidecard
          cockpit={research_cockpit}
          nextStep={strategyContext.next_step}
        />
      </div>

      <MultiTimeframeSummary items={chartData.multi_timeframe_summary} />

      <section className="panel">
        <p className="eyebrow">Freqtrade 准备情况</p>
        <h3>执行前先确认联调状态</h3>
        <p>当前后端：{freqtradeReadiness.backend}</p>
        <p>当前模式：{freqtradeReadiness.runtime_mode}</p>
        <p>真实 dry-run 条件：{freqtradeReadiness.ready_for_real_freqtrade ? "ready" : "not_ready"}</p>
        <p>下一步：{formatText(freqtradeReadiness.next_step, "n/a")}</p>
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

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
