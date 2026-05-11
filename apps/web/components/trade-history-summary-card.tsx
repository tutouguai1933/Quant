"use client";

/**
 * 策略交易记录卡片
 * 支持按策略筛选交易记录：
 * - EnhancedStrategy: strategy="EnhancedStrategy" 且 enter_tag 为空
 * - 自动化周期: enter_tag="quant-control-plane"
 */

import { useEffect, useState } from "react";
import { getFreqtradeTrades, type FreqtradeTrade } from "../lib/api";
import { TerminalCard } from "./terminal";

type StrategyType = "enhanced" | "automation";

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

  const getTitle = () => {
    return strategyType === "enhanced" ? "EnhancedStrategy 交易" : "自动化周期交易";
  };

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const response = await getFreqtradeTrades(100);
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

          setItems(filteredTrades);
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
              {items.slice(0, 5).map((item) => (
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
          {items.length > 5 && (
            <div className="text-xs text-[var(--terminal-muted)] mt-2">
              显示最近 5 条，共 {items.length} 条
            </div>
          )}
        </div>
      )}
    </TerminalCard>
  );
}
