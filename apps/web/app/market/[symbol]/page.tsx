/* 这个文件负责渲染单币图表页。 */

import { AppShell } from "../../../components/app-shell";
import { CandleChart } from "../../../components/candle-chart";
import { MetricGrid } from "../../../components/metric-grid";
import { PageHero } from "../../../components/page-hero";
import { getLatestResearch, getLatestResearchFallback, getMarketChart, type MarketCandle, type MarketChartData, type ResearchCockpitSummary } from "../../../lib/api";
import { getControlSessionState } from "../../../lib/session";


type PageProps = {
  params: Promise<{ symbol: string }>;
};

export default async function MarketSymbolPage({ params }: PageProps) {
  const session = await getControlSessionState();
  const { symbol } = await params;
  const normalizedSymbol = symbol.toUpperCase();
  let items: MarketCandle[] = [];
  let chartData: MarketChartData | null = null;
  let latestResearch = getLatestResearchFallback().item;

  try {
    const response = await getMarketChart(symbol);
    if (!response.error) {
      chartData = response.data;
      items = response.data.items;
    }
  } catch {
    // API 暂时不可用时保留空状态。
  }

  try {
    const response = await getLatestResearch();
    if (!response.error) {
      latestResearch = response.data.item;
    }
  } catch {
    // API 暂时不可用时保留研究兜底数据。
  }

  const symbolResearch = latestResearch.symbols[normalizedSymbol] ?? null;
  const latestTraining = asRecord(latestResearch.latest_training);
  const latestInference = asRecord(latestResearch.latest_inference);
  const latestInferenceSummaryRecord = asRecord(latestInference["summary"]);
  const explanation = formatText(
    symbolResearch?.explanation ?? latestResearch.detail,
    "暂无当前 symbol 的研究解释，先运行研究训练和研究推理。",
  );
  const strategyContext = chartData?.strategy_context ?? getEmptyStrategyContext();
  const freqtradeReadiness = chartData?.freqtrade_readiness ?? getEmptyFreqtradeReadiness();
  const markers = chartData?.markers ?? { signals: [], entries: [], stops: [] };
  const research_cockpit = chartData?.research_cockpit ?? getEmptyResearchCockpit();
  const researchGate = asRecord(research_cockpit.research_gate);
  const signalCount = Number(research_cockpit.signal_count ?? markers.signals.length);
  const entryHint = formatText(research_cockpit.entry_hint, formatLatestMarkerPrice(markers.entries));
  const stopHint = formatText(research_cockpit.stop_hint, formatLatestMarkerPrice(markers.stops));
  const overlay_summary = formatText(
    research_cockpit.overlay_summary,
    `${String(signalCount)} 个信号点 / 入场 ${entryHint} / 止损 ${stopHint}`,
  );
  const recommendedStrategy = research_cockpit.recommended_strategy || strategyContext.recommended_strategy;
  const primaryReason = formatText(research_cockpit.primary_reason || strategyContext.primary_reason, "n/a");
  const confidence = formatConfidence(research_cockpit.confidence);

  return (
    <AppShell
      title={normalizedSymbol}
      subtitle="这里先展示最小图表摘要，后续再接入完整图表交互。"
      currentPath="/market"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="图表"
        title={`${normalizedSymbol} 单币页`}
        description="当前页的重点不只是看 K 线，而是把策略判断、止损参考和下一步动作放到一条线上。"
      />

      <CandleChart
        symbol={symbol}
        items={items}
        signalCount={signalCount}
        entryHint={entryHint}
        stopHint={stopHint}
        researchBias={formatResearchBias(research_cockpit.research_bias)}
      />

      <MetricGrid
        items={[
          { label: "研究状态", value: formatText(latestResearch.status, "n/a"), detail: formatText(latestResearch.detail, "n/a") },
          { label: "研究分数", value: formatText(symbolResearch?.score, "n/a"), detail: formatText(symbolResearch?.signal, "研究结果") },
          {
            label: "模型版本",
            value: formatText(symbolResearch?.model_version ?? latestTraining["model_version"], "n/a"),
            detail: formatText(latestInferenceSummaryRecord["signal_count"], "最近推理结果"),
          },
          {
            label: "推荐策略",
            value: formatPreferredStrategy(recommendedStrategy),
            detail: `${formatTrendState(strategyContext.trend_state)} / ${formatResearchBias(research_cockpit.research_bias)}`,
          },
        ]}
      />

      <section className="panel">
        <p className="eyebrow">图表图层摘要</p>
        <h3>先看图上的关键位置，再决定要不要继续执行</h3>
        <p>{overlay_summary}</p>
        <p>研究倾向：{formatResearchBias(research_cockpit.research_bias)}</p>
        <p>推荐策略：{formatPreferredStrategy(recommendedStrategy)}</p>
        <p>判断信心：{confidence}</p>
        <p>研究门控：{formatText(researchGate.status, "unavailable")}</p>
      </section>

      <section className="panel">
        <p className="eyebrow">当前判断</p>
        <h3>{normalizedSymbol} 当前更适合怎么处理</h3>
        <p>推荐策略：{formatPreferredStrategy(recommendedStrategy)} / {formatTrendState(strategyContext.trend_state)}</p>
        <p>主判断：{primaryReason}</p>
        <p>推荐下一步：{formatText(strategyContext.next_step, "先继续观察。")}</p>
      </section>

      <MetricGrid
        items={[
          {
            label: "突破判断",
            value: formatDecision(strategyContext.evaluations.trend_breakout),
            detail: formatReason(strategyContext.evaluations.trend_breakout),
          },
          {
            label: "回调判断",
            value: formatDecision(strategyContext.evaluations.trend_pullback),
            detail: formatReason(strategyContext.evaluations.trend_pullback),
          },
          {
            label: "信号点",
            value: String(signalCount),
            detail: "当前图表页返回的策略信号标记数量",
          },
          {
            label: "止损参考",
            value: stopHint,
            detail: "当前最该盯住的失效位或保护位",
          },
        ]}
      />

      <section className="panel">
        <p className="eyebrow">止损参考</p>
        <h3>先确认失效位，再考虑是否继续执行</h3>
        <p>最新入场参考：{entryHint}</p>
        <p>最新止损参考：{stopHint}</p>
        <p>信号标记数量：{String(signalCount)}</p>
      </section>

      <section className="panel">
        <p className="eyebrow">研究解释</p>
        <h3>{normalizedSymbol} 的研究解释</h3>
        <p>研究倾向：{formatResearchBias(research_cockpit.research_bias)}</p>
        <p>{formatText(research_cockpit.research_explanation, explanation)}</p>
        <p>生成时间：{formatText(research_cockpit.generated_at || symbolResearch?.generated_at, "n/a")}</p>
      </section>

      <section className="panel">
        <p className="eyebrow">Freqtrade 准备情况</p>
        <h3>这一步决定你能不能继续做真实 dry-run 联调</h3>
        <p>当前后端：{freqtradeReadiness.backend}</p>
        <p>当前模式：{freqtradeReadiness.runtime_mode}</p>
        <p>是否已经具备真实 Freqtrade dry-run 条件：{freqtradeReadiness.ready_for_real_freqtrade ? "ready" : "not_ready"}</p>
        <p>下一步：{formatText(freqtradeReadiness.next_step, "n/a")}</p>
      </section>

      <section className="panel">
        <p className="eyebrow">下一步动作</p>
        <h3>先完成图表确认，再进入策略中心</h3>
        <p>如果这里已经出现明确策略和止损参考，就继续去策略中心执行 dry-run；如果还在 watch，就先回市场页观察其他白名单币种。</p>
        <p><a href="/strategies">前往策略中心</a></p>
      </section>
    </AppShell>
  );
}

function getEmptyStrategyContext(): MarketChartData["strategy_context"] {
  return {
    recommended_strategy: "none",
    trend_state: "neutral",
    next_step: "",
    primary_reason: "",
    evaluations: {},
  };
}

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

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}

function formatPreferredStrategy(value: MarketChartData["strategy_context"]["recommended_strategy"]): string {
  if (value === "trend_breakout") {
    return "趋势突破";
  }
  if (value === "trend_pullback") {
    return "趋势回调";
  }
  return "继续观察";
}

function formatConfidence(value: string): string {
  if (value === "high") {
    return "high / 高";
  }
  if (value === "medium") {
    return "medium / 中";
  }
  return "low / 低";
}

function formatTrendState(value: MarketChartData["strategy_context"]["trend_state"]): string {
  if (value === "uptrend") {
    return "uptrend / 上行趋势";
  }
  if (value === "pullback") {
    return "pullback / 回调观察";
  }
  return "neutral / 中性";
}

function formatDecision(item: Record<string, unknown> | undefined): string {
  return formatText(item?.decision, "n/a");
}

function formatReason(item: Record<string, unknown> | undefined): string {
  return formatText(item?.reason, "暂无原因");
}

function formatLatestMarkerPrice(items: Array<Record<string, unknown>>): string {
  const latest = items[items.length - 1];
  return formatText(latest?.price, "n/a");
}

function formatResearchBias(value: string): string {
  if (value === "bullish") {
    return "bullish / 偏多";
  }
  if (value === "bearish") {
    return "bearish / 偏空";
  }
  if (value === "neutral") {
    return "neutral / 中性";
  }
  return "unavailable / 暂不可用";
}
