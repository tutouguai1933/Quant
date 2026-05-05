/**
 * 市场总览页面
 * 终端风格重构
 */
"use client";

import { Suspense, useEffect, useState } from "react";

import {
  TerminalShell,
  TerminalCard,
} from "../../components/terminal";
import { MarketFilterBar } from "../../components/market-filter-bar";
import { listMarketSnapshots as loadMarketSnapshots } from "../../lib/api";
import {
  MarketSnapshotWorkspace,
  MarketSnapshotWorkspaceSkeleton,
} from "../../components/market-snapshot-workspace";

type MarketSnapshotsResponse = Awaited<ReturnType<typeof loadMarketSnapshots>>;

const MARKET_SNAPSHOT_CACHE_TTL_MS = 30_000;
let marketSnapshotsCache: { expiresAt: number; value: MarketSnapshotsResponse } | null = null;
let marketSnapshotsInflight: Promise<MarketSnapshotsResponse> | null = null;

export default function MarketPage() {
  const [session, setSession] = useState<{ isAuthenticated: boolean }>({
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [snapshotsPromise, setSnapshotsPromise] = useState<Promise<MarketSnapshotsResponse> | null>(null);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({ isAuthenticated: Boolean(data.isAuthenticated) });
      })
      .catch(() => {})
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    setSnapshotsPromise(getMarketSnapshotsSnapshot());
  }, []);

  return (
    <TerminalShell
      breadcrumb="数据 / 市场"
      title="市场"
      subtitle="行情筛选和单币详情"
      currentPath="/market"
      isAuthenticated={session.isAuthenticated}
    >
      {isLoading ? (
        <div className="space-y-4">
          <div className="terminal-card p-4 animate-pulse">
            <div className="h-4 w-24 bg-[var(--terminal-border)] rounded" />
          </div>
          <MarketSnapshotWorkspaceSkeleton />
        </div>
      ) : (
        <>
          {/* 市场筛选器 */}
          <TerminalCard title="市场筛选">
            <MarketFilterBar />
          </TerminalCard>

          {/* 市场快照 */}
          {snapshotsPromise ? (
            <Suspense fallback={<MarketSnapshotWorkspaceSkeleton />}>
              <MarketSnapshotWorkspace snapshotsPromise={snapshotsPromise} />
            </Suspense>
          ) : (
            <MarketSnapshotWorkspaceSkeleton />
          )}
        </>
      )}
    </TerminalShell>
  );
}

function getMarketSnapshotsSnapshot(): Promise<MarketSnapshotsResponse> {
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
