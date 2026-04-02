/* 这个文件负责渲染市场总览页。 */

import { Suspense } from "react";

import { AppShell } from "../../components/app-shell";
import { MarketFilterBar } from "../../components/market-filter-bar";
import { PageHero } from "../../components/page-hero";
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
      subtitle="先秒开骨架，再补市场数据，尽快进入单币图表页。"
      currentPath="/market"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="市场"
        title="市场筛选入口"
        description="这里先做第一轮筛选：先找优先关注和高信心目标，再看多周期状态、研究倾向和判断信心。"
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
