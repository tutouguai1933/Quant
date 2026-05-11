"use client";

/**
 * 市场入场信号卡片
 * 显示通用市场入场条件：RSI、趋势、成交量
 * 注意：这是市场层面的简单分析，不等同于自动化周期ML评分
 */

import { useEffect, useState } from "react";
import { listMarketSnapshots, type MarketSnapshot } from "../lib/api";
import { useRsiData } from "../lib/rsi-data-context";
import { TerminalCard } from "./terminal";

interface EntryCondition {
  symbol: string;
  rsi: number;
  rsiState: "overbought" | "oversold" | "neutral";
  trendState: "uptrend" | "pullback" | "neutral";
  volumeRatio: number;
  recommendedStrategy: string;
  entryAllowed: boolean;
  reasons: string[];
}

interface EntryStatusCardProps {
  refreshInterval?: number;
}

export function EntryStatusCard({ refreshInterval }: EntryStatusCardProps) {
  const { items: rsiItems, isLoading: rsiLoading, error: rsiError } = useRsiData();
  const [conditions, setConditions] = useState<EntryCondition[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (rsiLoading) return;

    let cancelled = false;

    async function fetchData() {
      try {
        const marketResponse = await listMarketSnapshots();

        if (cancelled) return;

        if (rsiError) {
          setError(rsiError);
          setIsLoading(false);
          return;
        }

        const marketItems = marketResponse.error ? [] : (marketResponse.data.items || []);
        const conditionMap = new Map<string, EntryCondition>();

        rsiItems.forEach((item) => {
          conditionMap.set(item.symbol, {
            symbol: item.symbol,
            rsi: item.rsi,
            rsiState: item.state as "overbought" | "oversold" | "neutral",
            trendState: "neutral",
            volumeRatio: 1,
            recommendedStrategy: "none",
            entryAllowed: false,
            reasons: [],
          });
        });

        marketItems.forEach((item: MarketSnapshot) => {
          const existing = conditionMap.get(item.symbol);
          if (existing) {
            existing.trendState = item.trend_state;
            existing.recommendedStrategy = item.recommended_strategy;

            if (item.research_brief) {
              const brief = item.research_brief;
              if (brief.research_bias) {
                existing.recommendedStrategy = brief.recommended_strategy || existing.recommendedStrategy;
              }
            }
          }
        });

        const conditionsList = Array.from(conditionMap.values()).map((cond) => {
          const reasons: string[] = [];
          let signalCount = 0;

          if (cond.rsiState === "oversold") {
            signalCount += 1;
          } else if (cond.rsiState === "neutral" && cond.rsi < 50) {
            signalCount += 0.5;
          }

          if (cond.trendState === "uptrend") {
            signalCount += 1;
          } else if (cond.trendState === "pullback") {
            signalCount += 0.5;
          }

          const entryAllowed = signalCount >= 1;

          if (cond.rsiState === "oversold") {
            reasons.push("RSI超卖");
          } else if (cond.rsi > 70) {
            reasons.push("RSI超买");
          }

          if (cond.trendState === "uptrend") {
            reasons.push("趋势看涨");
          } else if (cond.trendState === "pullback") {
            reasons.push("趋势回调中");
          }

          return {
            ...cond,
            entryAllowed,
            reasons,
          };
        });

        conditionsList.sort((a, b) => {
          if (a.entryAllowed && !b.entryAllowed) return -1;
          if (!a.entryAllowed && b.entryAllowed) return 1;
          return a.rsi - b.rsi;
        });

        setConditions(conditionsList);
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
    const interval = setInterval(fetchData, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [rsiItems, rsiLoading, rsiError]);

  const getTrendDisplay = (state: string) => {
    switch (state) {
      case "uptrend":
        return { label: "↑看涨", color: "text-green-400" };
      case "pullback":
        return { label: "→回调", color: "text-yellow-400" };
      default:
        return { label: "→中性", color: "text-[var(--terminal-muted)]" };
    }
  };

  const getRsiDisplay = (rsi: number, state: string) => {
    if (state === "oversold") {
      return { label: `${rsi.toFixed(1)}`, color: "text-green-400", bg: "bg-green-400/10" };
    }
    if (state === "overbought" || rsi > 70) {
      return { label: `${rsi.toFixed(1)}`, color: "text-red-400", bg: "bg-red-400/10" };
    }
    return { label: `${rsi.toFixed(1)}`, color: "text-[var(--terminal-text)]", bg: "" };
  };

  if (isLoading) {
    return (
      <TerminalCard title="市场入场信号">
        <div className="animate-pulse space-y-2">
          <div className="h-4 w-32 bg-[var(--terminal-border)] rounded" />
        </div>
      </TerminalCard>
    );
  }

  if (error) {
    return (
      <TerminalCard title="市场入场信号">
        <div className="text-sm text-red-500">⚠️ {error}</div>
      </TerminalCard>
    );
  }

  const actionableConditions = conditions.filter(c => c.entryAllowed || c.rsiState === "oversold");

  if (actionableConditions.length === 0) {
    return (
      <TerminalCard title="市场入场信号">
        <div className="text-sm text-[var(--terminal-muted)]">
          当前没有满足入场条件的信号
        </div>
        <div className="text-xs text-[var(--terminal-muted)]/60 mt-2">
          更新: {lastUpdate}
        </div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title="市场入场信号">
      <div className="space-y-3">
        {actionableConditions.slice(0, 4).map((cond) => {
          const trend = getTrendDisplay(cond.trendState);
          const rsiDisplay = getRsiDisplay(cond.rsi, cond.rsiState);

          return (
            <div
              key={cond.symbol}
              className="border border-[var(--terminal-border)] rounded-lg p-3"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--terminal-text)]">
                    {cond.symbol.replace("USDT", "")}
                  </span>
                  {cond.entryAllowed && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">
                      可入场
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                <div className={`rounded p-2 ${rsiDisplay.bg}`}>
                  <div className="text-[var(--terminal-muted)]">RSI</div>
                  <div className={`${rsiDisplay.color} font-mono`}>
                    {rsiDisplay.label}
                    {cond.rsiState === "oversold" && " (超卖)"}
                    {cond.rsiState === "overbought" && " (超买)"}
                  </div>
                </div>

                <div className="rounded p-2 bg-[var(--terminal-border)]/10">
                  <div className="text-[var(--terminal-muted)]">趋势</div>
                  <div className={trend.color}>{trend.label}</div>
                </div>

                <div className="rounded p-2 bg-[var(--terminal-border)]/10">
                  <div className="text-[var(--terminal-muted)]">建议</div>
                  <div className="text-[var(--terminal-text)]">
                    {cond.recommendedStrategy === "trend_breakout" ? "突破" :
                     cond.recommendedStrategy === "trend_pullback" ? "回调" : "观望"}
                  </div>
                </div>
              </div>

              {cond.reasons.length > 0 && (
                <div className="text-xs text-[var(--terminal-muted)] flex flex-wrap gap-1">
                  {cond.reasons.map((reason, i) => (
                    <span key={i} className="px-1.5 py-0.5 rounded bg-[var(--terminal-border)]/20">
                      {reason}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="text-xs text-[var(--terminal-muted)]/60 mt-3 flex justify-between">
        <span>通用市场信号，供参考</span>
        <span>更新: {lastUpdate}</span>
      </div>
    </TerminalCard>
  );
}
