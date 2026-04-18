/* 这个文件负责渲染市场总览页。 */

import { Suspense } from "react";

import { AppShell } from "../../components/app-shell";
import { MarketFilterBar } from "../../components/market-filter-bar";
import { PageHero } from "../../components/page-hero";
import { ToolDetailHub } from "../../components/tool-detail-hub";
import { listMarketSnapshots as loadMarketSnapshots } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";
import {
  MarketSnapshotWorkspace,
  MarketSnapshotWorkspaceSkeleton,
} from "../../components/market-snapshot-workspace";

const MARKET_SNAPSHOT_CACHE_TTL_MS = 30_000;
let marketSnapshotsCache: { expiresAt: number; value: Awaited<ReturnType<typeof loadMarketSnapshots>> } | null = null;
let marketSnapshotsInflight: Promise<Awaited<ReturnType<typeof loadMarketSnapshots>>> | null = null;


export default async function MarketPage() {
  const session = await getControlSessionState();
  const snapshotsPromise = getMarketSnapshotsSnapshot();

  return (
    <AppShell
      title="市场"
      subtitle="市场页现在只负责行情筛选和单币详情，不再承担主流程判断。"
      currentPath="/market"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="市场详情"
        title="市场详情页"
        description="先在主工作台确认要不要看行情，再回到这里筛选目标、查看快照和进入单币图表。"
      />

      <ToolDetailHub
        summary="先在首页、评估页或策略页做判断，再回市场页看候选的行情和图表细节。"
        detail="这里保留筛选器、市场快照和单币入口，帮助你核对某个候选值不值得继续推进，但不再把市场页当成主链起点。"
        mainHint="首页已经告诉你该先看哪个候选，再回市场页核对图表和市场快照。"
        strategiesHint="执行前如果要再看单币走势或筛选范围，回这里补看即可。"
        tasksHint="如果任务页提示要人工复核候选，可以回市场页确认图表和行情状态。"
      />

      <MarketFilterBar />

      <Suspense fallback={<MarketSnapshotWorkspaceSkeleton />}>
        <MarketSnapshotWorkspace snapshotsPromise={snapshotsPromise} />
      </Suspense>
    </AppShell>
  );
}

/* 返回带短缓存的市场快照请求。 */
function getMarketSnapshotsSnapshot(): Promise<Awaited<ReturnType<typeof loadMarketSnapshots>>> {
  const now = Date.now();
  if (marketSnapshotsCache && marketSnapshotsCache.expiresAt > now) {
    return Promise.resolve(marketSnapshotsCache.value);
  }

  if (marketSnapshotsInflight) {
    return marketSnapshotsInflight;
  }

  marketSnapshotsInflight = loadMarketSnapshots()
    .then((response) => {
      if (!response.error) {
        marketSnapshotsCache = {
          expiresAt: Date.now() + MARKET_SNAPSHOT_CACHE_TTL_MS,
          value: response,
        };
      }
      marketSnapshotsInflight = null;
      return response;
    })
    .catch((error) => {
      marketSnapshotsInflight = null;
      throw error;
    });

  return marketSnapshotsInflight;
}
