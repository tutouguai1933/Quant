"use client";

/**
 * 策略交易记录卡片
 * 支持按策略筛选交易记录：
 * - EnhancedStrategy: strategy="EnhancedStrategy" 且 enter_tag 为空
 * - 自动化周期: enter_tag="quant-control-plane"
 * 支持分页，每页5条，倒序排列
 */

import { useEffect, useState, useMemo } from "react";
import { getFreqtradeTrades, type FreqtradeTrade } from "../lib/api";
import { TerminalCard } from "./terminal";

type StrategyType = "enhanced" | "automation";

const PAGE_SIZE = 5;

interface TradeHistorySummaryCardProps {
  strategyType: StrategyType;
  refreshInterval?: number;
}

export function TradeHistorySummaryCard({
  strategyType,
  refreshInterval = 60000
}: TradeHistorySummaryCardProps) {
  const [items, setItems] = useState<FreqtradeTrade[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const getTitle = () => {
    return strategyType === "enhanced" ? "EnhancedStrategy 交易" : "自动化周期交易";
  };

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const response = await getFreqtradeTrades(200);
        if (cancelled) return;

        if (response.error) {
          setError(response.error.message || "获取交易记录失败");
        } else {
          const allTrades = response.data.trades || [];

          // 按策略筛选
          const filteredTrades = allTrades.filter((trade) => {
            const isAutomation = trade.enter_tag === "quant-control-plane";
            if (strategyType === "automation") {
              return isAutomation;
            } else {
              // EnhancedStrategy: 策略名是 EnhancedStrategy 且不是自动化触发的
              return trade.strategy === "EnhancedStrategy" && !isAutomation;
            }
          });

          // 按时间倒序排列（最新的在前）
          const sortedTrades = filteredTrades.sort((a, b) => {
            const dateA = new Date(a.close_date || a.open_date).getTime();
            const dateB = new Date(b.close_date || b.open_date).getTime();
            return dateB - dateA;
          });

          setItems(sortedTrades);
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
  }, [strategyType, refreshInterval]);

  // 分页数据
  const totalPages = Math.ceil(items.length / PAGE_SIZE);
  const paginatedItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, page]);

  // 重置页码当数据变化
  useEffect(() => {
    setPage(1);
  }, [strategyType]);

  const formatPnL = (pnlPct: number) => {
    const sign = pnlPct >= 0 ? "+" : "";
    return `${sign}${pnlPct.toFixed(2)}%`;
  };

  const getPnLColor = (pnlPct: number) => {
    return pnlPct >= 0 ? "text-green-500" : "text-red-500";
  };

  const getSideLabel = (side: string) => {
    return side.toLowerCase() === "buy" ? "买入" : "卖出";
  };

  const getSideColor = (side: string) => {
    return side.toLowerCase() === "buy" ? "text-green-500" : "text-red-500";
  };

  if (isLoading) {
    return (
      <TerminalCard title={getTitle()}>
        <div className="animate-pulse space-y-2">
          <div className="h-4 w-32 bg-[var(--terminal-border)] rounded" />
        </div>
      </TerminalCard>
    );
  }

  if (error) {
    return (
      <TerminalCard title={getTitle()}>
        <div className="text-sm text-red-500">⚠️ {error}</div>
      </TerminalCard>
    );
  }

  const winningTrades = items.filter((i) => i.profit_pct > 0);
  const losingTrades = items.filter((i) => i.profit_pct < 0);

  return (
    <TerminalCard title={getTitle()}>
      <div className="flex items-center justify-between mb-3">
        <div className="space-y-1">
          <div className="flex gap-4 text-xs">
            <span className="text-[var(--terminal-muted)]">
              总计: <span className="text-[var(--terminal-fg)] font-medium">{items.length}</span> 条
            </span>
            <span className="text-green-500">
              盈利: <span className="font-medium">{winningTrades.length}</span>
            </span>
            <span className="text-red-500">
              亏损: <span className="font-medium">{losingTrades.length}</span>
            </span>
          </div>
        </div>
        <div className="text-xs text-[var(--terminal-muted)]">
          更新: {lastUpdate}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="text-sm text-[var(--terminal-muted)]">
          {strategyType === "enhanced" ? "暂无 EnhancedStrategy 交易记录" : "暂无自动化周期交易记录"}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--terminal-border)] text-left text-xs text-[var(--terminal-muted)]">
                <th className="pb-2 font-medium">时间</th>
                <th className="pb-2 font-medium">币种</th>
                <th className="pb-2 font-medium">方向</th>
                <th className="pb-2 font-medium text-right">入场价</th>
                <th className="pb-2 font-medium text-right">出场价</th>
                <th className="pb-2 font-medium text-right">盈亏</th>
              </tr>
            </thead>
            <tbody>
              {paginatedItems.map((item) => (
                <tr key={item.trade_id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-border)]/10">
                  <td className="py-2 text-xs text-[var(--terminal-muted)]">
                    {item.close_date || item.open_date}
                  </td>
                  <td className="py-2 font-medium">{item.base_currency}</td>
                  <td className={`py-2 font-medium ${getSideColor(item.is_open ? "buy" : "sell")}`}>
                    {item.is_open ? "持仓中" : getSideLabel("sell")}
                  </td>
                  <td className="py-2 text-right font-mono text-xs">{item.open_rate}</td>
                  <td className="py-2 text-right font-mono text-xs">
                    {item.close_rate ? (
                      item.close_rate
                    ) : (
                      <span className="text-[var(--terminal-muted)]">-</span>
                    )}
                  </td>
                  <td className={`py-2 text-right font-mono font-medium ${getPnLColor(item.profit_pct)}`}>
                    {item.is_open ? "持仓中" : formatPnL(item.profit_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* 分页控件 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-3 pt-2 border-t border-[var(--terminal-border)]/30">
              <div className="text-xs text-[var(--terminal-muted)]">
                第 {page}/{totalPages} 页，共 {items.length} 条
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-2 py-1 text-xs rounded border border-[var(--terminal-border)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--terminal-border)]/20 transition-colors"
                >
                  上一页
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-2 py-1 text-xs rounded border border-[var(--terminal-border)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--terminal-border)]/20 transition-colors"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </TerminalCard>
  );
}
