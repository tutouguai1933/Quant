/* 这个文件负责渲染市场总览页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { listMarketSnapshots, type MarketSnapshot } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


export default async function MarketPage() {
  const session = await getControlSessionState();
  let items: MarketSnapshot[] = [];

  try {
    const response = await listMarketSnapshots();
    if (!response.error) {
      items = response.data.items;
    }
  } catch {
    // API 暂时不可用时保留空状态。
  }

  return (
    <AppShell
      title="市场"
      subtitle="先看第一批白名单币种的基础行情，再进入单币图表页。"
      currentPath="/market"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="市场"
        title="市场总览"
        description="这里不只看价格，还会先告诉你每个币种当前更适合哪套策略，以及它处在什么趋势状态。"
      />

      <MetricGrid
        items={[
          { label: "白名单币种", value: String(items.length), detail: "当前只观察固定币种池，不做大范围扫描" },
          { label: "更适合突破", value: String(items.filter((item) => item.research_brief.recommended_strategy === "trend_breakout").length), detail: "优先去看突破参考线和放量情况" },
          { label: "更适合回调", value: String(items.filter((item) => item.research_brief.recommended_strategy === "trend_pullback").length), detail: "优先去看回踩位和失效位" },
          { label: "中性观察", value: String(items.filter((item) => item.research_brief.recommended_strategy === "none").length), detail: "当前没有明显优势策略，先观察" },
        ]}
      />

      <section className="panel">
        <p className="eyebrow">统一研究口径</p>
        <h3>先看研究倾向、推荐策略和判断信心</h3>
        <p>市场页这一层先帮你做快速筛选。看完研究倾向、推荐策略和主判断，再进入单币页确认图上关键位置。</p>
      </section>

      <DataTable
        columns={["Symbol", "Last Price", "24h Change", "研究倾向", "推荐策略", "判断信心", "主判断", "Action"]}
        rows={items.map((item) => ({
          id: item.symbol,
          cells: [
            item.symbol,
            item.last_price,
            item.change_percent,
            formatResearchBias(item.research_brief.research_bias),
            formatPreferredStrategy(item.research_brief.recommended_strategy),
            formatConfidence(item.research_brief.confidence),
            formatPrimaryReason(item),
            <a key={item.symbol} href={`/market/${encodeURIComponent(item.symbol)}`}>
              看图表并继续判断
            </a>,
          ],
        }))}
        emptyTitle="暂无市场数据"
        emptyDetail="请先确认市场 API 已启动，再刷新这里查看白名单币种行情。"
      />
    </AppShell>
  );
}

function formatPreferredStrategy(value: MarketSnapshot["recommended_strategy"]): string {
  if (value === "trend_breakout") {
    return "趋势突破";
  }
  if (value === "trend_pullback") {
    return "趋势回调";
  }
  return "继续观察";
}

function formatTrendState(value: MarketSnapshot["trend_state"]): string {
  if (value === "uptrend") {
    return "uptrend / 上行趋势";
  }
  if (value === "pullback") {
    return "pullback / 回调观察";
  }
  return "neutral / 中性";
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

function formatPrimaryReason(item: MarketSnapshot): string {
  const reason = String(item.research_brief.primary_reason ?? "").trim();
  if (reason) {
    return reason;
  }
  if (item.research_brief.recommended_strategy === "trend_breakout") {
    return `${String(item.strategy_summary.trend_breakout?.reason ?? "等待突破确认")} / ${formatTrendState(item.trend_state)}`;
  }
  if (item.research_brief.recommended_strategy === "trend_pullback") {
    return `${String(item.strategy_summary.trend_pullback?.reason ?? "等待回踩确认")} / ${formatTrendState(item.trend_state)}`;
  }
  return "当前没有明显优势策略";
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
