"use client";

import { useEffect, useState } from "react";
import { TerminalCard } from "./terminal";

interface EntryBlocker {
  symbol: string;
  rsi: number;
  reason: string;
  score?: number;
  threshold?: number;
}

interface EntryStatusCardProps {
  refreshInterval?: number;
}

export function EntryStatusCard({ refreshInterval = 60000 }: EntryStatusCardProps) {
  const [blockers, setBlockers] = useState<EntryBlocker[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [automationMode, setAutomationMode] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        // 获取RSI概览和自动化状态
        const [rsiRes, autoRes] = await Promise.all([
          fetch("/api/v1/market/rsi-summary"),
          fetch("/api/v1/tasks/automation"),
        ]);

        if (cancelled) return;

        const rsiData = await rsiRes.json();
        const autoData = await autoRes.json();

        // 获取自动化模式
        const mode = autoData?.data?.item?.state?.mode || "unknown";
        setAutomationMode(mode);

        // 找出超卖的币种
        const oversoldItems = (rsiData?.data?.items || []).filter(
          (item: { state: string }) => item.state === "oversold"
        );

        // 对于每个超卖币种，检查入场状态
        const blockerList: EntryBlocker[] = [];

        for (const item of oversoldItems) {
          const symbol = item.symbol;
          const rsi = item.rsi;

          // 默认阻塞原因
          let reason = "等待入场信号";
          let score: number | undefined;
          let threshold: number | undefined;

          // 尝试获取入场评分
          try {
            const scoreRes = await fetch(
              `/api/v1/strategies/1/entry-score?symbol=${symbol}&signal_side=long`,
              { method: "POST" }
            );
            const scoreData = await scoreRes.json();

            if (scoreData?.data?.entry_decision) {
              const decision = scoreData.data.entry_decision;
              if (!decision.allowed) {
                reason = decision.reason || "入场条件未满足";
                score = decision.score;
                threshold = decision.threshold || 0.6;
              }
            }
          } catch {
            // 如果无法获取评分，使用默认原因
            if (mode === "manual") {
              reason = "自动化处于手动模式";
            } else if (mode === "auto_dry_run") {
              reason = "仅模拟模式，不会实盘买入";
            }
          }

          blockerList.push({
            symbol,
            rsi,
            reason,
            score,
            threshold,
          });
        }

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
          自动化模式: {automationMode} · 更新: {lastUpdate}
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
              {blocker.score !== undefined && blocker.threshold !== undefined && (
                <span className="text-[var(--terminal-muted)] ml-1">
                  (评分 {blocker.score.toFixed(2)} &lt; 阈值 {blocker.threshold.toFixed(2)})
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="text-xs text-[var(--terminal-muted)]/60 mt-3">
        自动化模式: {automationMode} · 更新: {lastUpdate}
      </div>
    </TerminalCard>
  );
}
