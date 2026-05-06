"use client";

import { useEffect, useState } from "react";
import { getRsiSummary, type RsiSummaryItem } from "../lib/api";
import { TerminalCard } from "./terminal";

interface RsiSummaryCardProps {
  refreshInterval?: number; // 毫秒
}

export function RsiSummaryCard({ refreshInterval = 300000 }: RsiSummaryCardProps) {
  const [items, setItems] = useState<RsiSummaryItem[]>([]);
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
          setError(response.error.message || "获取RSI概览失败");
        } else {
          setItems(response.data.items || []);
          setLastUpdate(new Date().toLocaleTimeString("zh-CN", { timeZone: "Asia/Shanghai" }));
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError("网络请求失败");
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

  const getStateColor = (state: string) => {
    switch (state) {
      case "overbought":
        return "text-red-500";
      case "oversold":
        return "text-green-500";
      default:
        return "text-[var(--terminal-muted)]";
    }
  };

  const getStateBgColor = (state: string) => {
    switch (state) {
      case "overbought":
        return "bg-red-500/10 border-red-500/30";
      case "oversold":
        return "bg-green-500/10 border-green-500/30";
      default:
        return "bg-[var(--terminal-muted)]/10 border-[var(--terminal-border)]";
    }
  };

  if (isLoading) {
    return (
      <TerminalCard title="RSI概览 (1D周期)">
        <div className="animate-pulse space-y-2">
          <div className="h-4 w-32 bg-[var(--terminal-border)] rounded" />
          <div className="grid grid-cols-4 gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-[var(--terminal-border)]/30 rounded" />
            ))}
          </div>
        </div>
      </TerminalCard>
    );
  }

  if (error) {
    return (
      <TerminalCard title="RSI概览 (1D周期)">
        <div className="text-sm text-red-500">⚠️ {error}</div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard
      title="RSI概览 (1D周期)"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="space-y-1">
          {/* 统计概览 */}
          <div className="flex gap-4 text-xs">
            <span className="text-[var(--terminal-muted)]">
              总计: <span className="text-[var(--terminal-fg)] font-medium">{items.length}</span> 个币种
            </span>
            <span className="text-red-500">
              超买: <span className="font-medium">{items.filter((i) => i.state === "overbought").length}</span>
            </span>
            <span className="text-green-500">
              超卖: <span className="font-medium">{items.filter((i) => i.state === "oversold").length}</span>
            </span>
            <span className="text-[var(--terminal-muted)]">
              中性: <span className="font-medium">{items.filter((i) => i.state === "neutral").length}</span>
            </span>
          </div>
        </div>
        <div className="text-xs text-[var(--terminal-muted)]">
          更新: {lastUpdate}
        </div>
      </div>

        {/* RSI列表 */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
          {items.map((item) => (
            <div
              key={item.symbol}
              className={`rounded-lg border p-3 ${getStateBgColor(item.state)}`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">{item.symbol.replace("USDT", "")}</span>
                <span className={`text-sm font-bold ${getStateColor(item.state)}`}>
                  {item.rsi.toFixed(1)}
                </span>
              </div>
              <div className="text-xs text-[var(--terminal-muted)]">
                {item.state === "overbought" && "🔥 超买"}
                {item.state === "oversold" && "💚 超卖"}
                {item.state === "neutral" && "○ 中性"}
              </div>
              <div className="text-xs text-[var(--terminal-muted)]/60 mt-1">
                {item.time}
              </div>
            </div>
          ))}
        </div>

        {items.length === 0 && (
          <div className="text-sm text-[var(--terminal-muted)]">暂无数据</div>
        )}
    </TerminalCard>
  );
}