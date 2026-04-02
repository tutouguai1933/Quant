/* 这个文件负责市场页的数据工作区和加载骨架。 */

"use client";

import { use } from "react";

import { DataTable } from "./data-table";
import { MarketFocusBoard } from "./market-focus-board";
import type { ApiEnvelope, MarketSnapshot } from "../lib/api";


type MarketSnapshotWorkspaceProps = {
  snapshotsPromise: Promise<ApiEnvelope<{ items: MarketSnapshot[] }>>;
};

const MARKET_SNAPSHOT_CACHE_TTL_MS = 30_000;
let memoryCache: { updatedAt: number; items: MarketSnapshot[] } | null = null;

/* 渲染市场页的实时数据区。 */
export function MarketSnapshotWorkspace({ snapshotsPromise }: MarketSnapshotWorkspaceProps) {
  const cached = memoryCache;
  if (cached && Date.now() - cached.updatedAt < MARKET_SNAPSHOT_CACHE_TTL_MS) {
    return <MarketSnapshotWorkspaceBody items={cached.items} />;
  }

  const response = use(snapshotsPromise);
  const items = response.error ? [] : response.data.items;
  if (!response.error) {
    memoryCache = { updatedAt: Date.now(), items };
  }

  return <MarketSnapshotWorkspaceBody items={items} />;
}

/* 渲染市场页的数据面板。 */
function MarketSnapshotWorkspaceBody({ items }: { items: MarketSnapshot[] }) {
  return (
    <div className="trading-layout">
      {/* listMarketSnapshots 仍然是市场快照的来源，这里只负责把它展示出来。 */}
      <DataTable
        columns={["Symbol", "Last Price", "24h Change", "多周期状态", "研究倾向", "推荐策略", "判断信心", "主判断", "Action"]}
        rows={items.map((item) => ({
          id: item.symbol,
          cells: [
            item.symbol,
            item.last_price,
            item.change_percent,
            formatTrendState(item.trend_state),
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
      <MarketFocusBoard items={items} />
    </div>
  );
}

/* 渲染市场页的加载骨架。 */
export function MarketSnapshotWorkspaceSkeleton() {
  return (
    <div className="trading-layout" aria-busy="true">
      <section className="panel loading-panel">
        <p className="eyebrow">市场数据</p>
        <h3>正在加载</h3>
        <div className="loading-stack">
          <SkeletonLine width="62%" />
          <SkeletonLine width="88%" />
          <SkeletonLine width="74%" />
          <SkeletonLine width="91%" />
        </div>
        <div className="loading-grid">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </section>

      <aside className="panel loading-panel">
        <p className="eyebrow">优先关注</p>
        <h3>先看这些目标</h3>
        <div className="loading-stack">
          <SkeletonLine width="58%" />
          <SkeletonLine width="78%" />
          <SkeletonLine width="66%" />
        </div>
      </aside>
    </div>
  );
}

/* 格式化推荐策略文案。 */
function formatPreferredStrategy(value: MarketSnapshot["recommended_strategy"]): string {
  if (value === "trend_breakout") {
    return "趋势突破";
  }
  if (value === "trend_pullback") {
    return "趋势回调";
  }
  return "继续观察";
}

/* 格式化趋势状态文案。 */
function formatTrendState(value: MarketSnapshot["trend_state"]): string {
  if (value === "uptrend") {
    return "uptrend / 上行趋势";
  }
  if (value === "pullback") {
    return "pullback / 回调观察";
  }
  return "neutral / 中性";
}

/* 格式化研究信心文案。 */
function formatConfidence(value: string): string {
  if (value === "high") {
    return "high / 高";
  }
  if (value === "medium") {
    return "medium / 中";
  }
  return "low / 低";
}

/* 格式化主判断文案。 */
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

/* 格式化研究倾向文案。 */
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

/* 渲染骨架里的单行占位。 */
function SkeletonLine({ width }: { width: string }) {
  return <div style={{ width, height: 14, borderRadius: 999, background: "rgba(255,255,255,0.08)" }} />;
}

/* 渲染骨架里的卡片占位。 */
function SkeletonCard() {
  return (
    <div
      style={{
        minHeight: 72,
        borderRadius: 16,
        background: "linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03))",
      }}
    />
  );
}
