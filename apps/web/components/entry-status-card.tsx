"use client";

import { useEffect, useState } from "react";
import { getRsiSummary, type RsiSummaryItem } from "../lib/api";
import { TerminalCard } from "./terminal";

interface EntryBlocker {
  symbol: string;
  rsi: number;
  reason: string;
}

interface EntryStatusCardProps {
  refreshInterval?: number;
}

export function EntryStatusCard({ refreshInterval = 60000 }: EntryStatusCardProps) {
  const [blockers, setBlockers] = useState<EntryBlocker[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const response = await getRsiSummary("1d");
        if (cancelled) return;

        if (response.error) {
          setError(response.error.message || "获取数据失败");
          return;
        }

        const items = response.data.items || [];

        // 找出超卖的币种
        const oversoldItems = items.filter((item) => item.state === "oversold");

        // 构建阻塞原因列表
        const blockerList: EntryBlocker[] = oversoldItems.map((item) => ({
          symbol: item.symbol,
          rsi: item.rsi,
          reason: "入场评分未达阈值或信号未生成",
        }));

        setBlockers(blockerList);
        setLastUpdate(new Date().toLocaleTimeString("zh-CN", { timeZone: "Asia/Shanghai" }));
        setError(null);
      } catch {
        if (!cancelled) {
          setError("获取入场状态失败");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [refreshInterval]);

  if (isLoading) {
    return (
      <TerminalCard title="入场状态">
        <div className="animate-pulse space-y-2">
          <div className="h-4 w-32 bg-[var(--terminal-border)] rounded" />
        </div>
      </TerminalCard>
    );
  }

  if (error) {
    return (
      <TerminalCard title="入场状态">
        <div className="text-sm text-red-500">⚠️ {error}</div>
      </TerminalCard>
    );
  }

  // 如果没有超卖币种
  if (blockers.length === 0) {
    return (
      <TerminalCard title="入场状态">
        <div className="text-sm text-[var(--terminal-muted)]">
          当前没有超卖信号，无需入场
        </div>
        <div className="text-xs text-[var(--terminal-muted)]/60 mt-2">
          更新: {lastUpdate}
        </div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title="入场状态">
      <div className="space-y-3">
        {blockers.map((blocker) => (
          <div
            key={blocker.symbol}
            className="border border-[var(--terminal-border)] rounded-lg p-3"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-green-500">
                {blocker.symbol.replace("USDT", "")}
              </span>
              <span className="text-xs text-[var(--terminal-muted)]">
                RSI: {blocker.rsi.toFixed(1)} (超卖)
              </span>
            </div>
            <div className="text-xs text-yellow-500 bg-yellow-500/10 rounded p-2">
              ⚠️ 未入场: {blocker.reason}
            </div>
          </div>
        ))}
      </div>
      <div className="text-xs text-[var(--terminal-muted)]/60 mt-3">
        更新: {lastUpdate}
      </div>
    </TerminalCard>
  );
}
