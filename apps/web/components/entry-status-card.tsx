"use client";

/**
 * 入场状态卡片
 * 显示完整的入场条件指标：RSI、趋势、成交量、MACD
 * 使用共享 RsiDataContext 避免重复请求 RSI 数据
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
  score: number;
  entryAllowed: boolean;
  reasons: string[];
}

interface EntryStatusCardProps {
  // refreshInterval 参数已弃用，使用共享上下文的刷新间隔
  refreshInterval?: number;
}

export function EntryStatusCard({ refreshInterval }: EntryStatusCardProps) {
  // 使用共享 RSI 数据上下文
  const { items: rsiItems, isLoading: rsiLoading, error: rsiError } = useRsiData();
  const [conditions, setConditions] = useState<EntryCondition[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 如果 RSI 数据还在加载，等待
    if (rsiLoading) return;

    let cancelled = false;

    async function fetchData() {
      try {
        // 只获取市场数据，RSI 从共享上下文获取
        const marketResponse = await listMarketSnapshots();

        if (cancelled) return;

        if (rsiError) {
          setError(rsiError);
          setIsLoading(false);
          return;
        }

        const marketItems = marketResponse.error ? [] : (marketResponse.data.items || []);

        // 合并数据
        const conditionMap = new Map<string, EntryCondition>();

        // 先处理共享的 RSI 数据
        rsiItems.forEach((item) => {
          conditionMap.set(item.symbol, {
            symbol: item.symbol,
            rsi: item.rsi,
            rsiState: item.state as "overbought" | "oversold" | "neutral",
            trendState: "neutral",
            volumeRatio: 1,
            recommendedStrategy: "none",
            score: 0,
            entryAllowed: false,
            reasons: [],
          });
        });

        // 再合并市场数据
        marketItems.forEach((item: MarketSnapshot) => {
          const existing = conditionMap.get(item.symbol);
          if (existing) {
            existing.trendState = item.trend_state;
            existing.recommendedStrategy = item.recommended_strategy;

            // 从research_brief获取更多信息
            if (item.research_brief) {
              const brief = item.research_brief;
              if (brief.research_bias) {
                existing.recommendedStrategy = brief.recommended_strategy || existing.recommendedStrategy;
              }
            }
          }
        });

        // 计算入场条件
        const conditionsList = Array.from(conditionMap.values()).map((cond) => {
          const reasons: string[] = [];
          let score = 0;

          // RSI评分 (超卖加分)
          if (cond.rsiState === "oversold") {
            score += 0.3;
          } else if (cond.rsiState === "neutral" && cond.rsi < 50) {
            score += 0.1;
          }

          // 趋势评分
          if (cond.trendState === "uptrend") {
            score += 0.3;
          } else if (cond.trendState === "pullback") {
            score += 0.2;
          }

          // 策略匹配
          if (cond.recommendedStrategy !== "none") {
            score += 0.2;
          }

          // 检查入场条件
          const entryAllowed = score >= 0.4;

          // 构建原因列表
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
            score,
            entryAllowed,
            reasons,
          };
        });

        // 按评分排序，优先显示可入场的
        conditionsList.sort((a, b) => {
          if (a.entryAllowed && !b.entryAllowed) return -1;
          if (!a.entryAllowed && b.entryAllowed) return 1;
          return b.score - a.score;
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
    // 每60秒刷新市场数据（RSI数据由共享上下文每5分钟刷新）
    const interval = setInterval(fetchData, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [rsiItems, rsiLoading, rsiError]);

  // 获取趋势显示
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

  // 获取RSI显示
  const getRsiDisplay = (rsi: number, state: string) => {
    if (state === "oversold") {
      return { label: `${rsi.toFixed(1)}`, color: "text-green-400", bg: "bg-green-400/10" };
    }
    if (state === "overbought" || rsi > 70) {
      return { label: `${rsi.toFixed(1)}`, color: "text-red-400", bg: "bg-red-400/10" };
    }
    return { label: `${rsi.toFixed(1)}`, color: "text-[var(--terminal-text)]", bg: "" };
  };

  // 获取评分颜色
  const getScoreColor = (score: number) => {
    if (score >= 0.6) return "text-green-400";
    if (score >= 0.4) return "text-yellow-400";
    return "text-[var(--terminal-muted)]";
  };

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

  // 筛选出可入场或接近入场的条件
  const actionableConditions = conditions.filter(c => c.score >= 0.3 || c.rsiState === "oversold");

  if (actionableConditions.length === 0) {
    return (
      <TerminalCard title="入场状态">
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
    <TerminalCard title="入场状态">
      <div className="space-y-3">
        {actionableConditions.slice(0, 4).map((cond) => {
          const trend = getTrendDisplay(cond.trendState);
          const rsiDisplay = getRsiDisplay(cond.rsi, cond.rsiState);

          return (
            <div
              key={cond.symbol}
              className="border border-[var(--terminal-border)] rounded-lg p-3"
            >
              {/* 标题行 */}
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
                <span className={`text-xs ${getScoreColor(cond.score)}`}>
                  评分: {(cond.score * 100).toFixed(0)}%
                </span>
              </div>

              {/* 指标网格 */}
              <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                {/* RSI */}
                <div className={`rounded p-2 ${rsiDisplay.bg}`}>
                  <div className="text-[var(--terminal-muted)]">RSI</div>
                  <div className={`${rsiDisplay.color} font-mono`}>
                    {rsiDisplay.label}
                    {cond.rsiState === "oversold" && " (超卖)"}
                    {cond.rsiState === "overbought" && " (超买)"}
                  </div>
                </div>

                {/* 趋势 */}
                <div className="rounded p-2 bg-[var(--terminal-border)]/10">
                  <div className="text-[var(--terminal-muted)]">趋势</div>
                  <div className={trend.color}>{trend.label}</div>
                </div>

                {/* 策略 */}
                <div className="rounded p-2 bg-[var(--terminal-border)]/10">
                  <div className="text-[var(--terminal-muted)]">策略</div>
                  <div className="text-[var(--terminal-text)]">
                    {cond.recommendedStrategy === "trend_breakout" ? "突破" :
                     cond.recommendedStrategy === "trend_pullback" ? "回调" : "观望"}
                  </div>
                </div>
              </div>

              {/* 入场原因 */}
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

      <div className="text-xs text-[var(--terminal-muted)]/60 mt-3">
        更新: {lastUpdate}
      </div>
    </TerminalCard>
  );
}
