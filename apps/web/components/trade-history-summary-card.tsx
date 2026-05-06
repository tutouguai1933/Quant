"use client";

import { useEffect, useState } from "react";
import { getTradeHistory, type TradeHistoryItem } from "../lib/api";
import { TerminalCard } from "./terminal";

interface TradeHistorySummaryCardProps {
  refreshInterval?: number;
}

export function TradeHistorySummaryCard({ refreshInterval = 60000 }: TradeHistorySummaryCardProps) {
  const [items, setItems] = useState<TradeHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const response = await getTradeHistory(undefined, 100);
        if (cancelled) return;

        if (response.error) {
          setError(response.error.message || "获取交易记录失败");
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

  const formatPnL = (pnlStr: string) => {
    const pnl = parseFloat(pnlStr);
    if (isNaN(pnl)) return pnlStr;
    const sign = pnl >= 0 ? "+" : "";
    return `${sign}${pnl.toFixed(2)}%`;
  };

  const getPnLColor = (pnlStr: string) => {
    const pnl = parseFloat(pnlStr);
    if (isNaN(pnl)) return "text-[var(--terminal-muted)]";
    return pnl >= 0 ? "text-green-500" : "text-red-500";
  };

  const getSideLabel = (side: string) => {
    return side.toLowerCase() === "buy" ? "买入" : "卖出";
  };

  const getSideColor = (side: string) => {
    return side.toLowerCase() === "buy" ? "text-green-500" : "text-red-500";
  };

  if (isLoading) {
    return (
      <TerminalCard title="交易记录汇总">
        <div className="animate-pulse space-y-2">
          <div className="h-4 w-32 bg-[var(--terminal-border)] rounded" />
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 bg-[var(--terminal-border)]/30 rounded" />
            ))}
          </div>
        </div>
      </TerminalCard>
    );
  }

  if (error) {
    return (
      <TerminalCard title="交易记录汇总">
        <div className="text-sm text-red-500">⚠️ {error}</div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title="交易记录汇总">
      <div className="flex items-center justify-between mb-3">
        <div className="space-y-1">
          <div className="flex gap-4 text-xs">
            <span className="text-[var(--terminal-muted)]">
              总计: <span className="text-[var(--terminal-fg)] font-medium">{items.length}</span> 条记录
            </span>
            <span className="text-green-500">
              盈利: <span className="font-medium">{items.filter((i) => parseFloat(i.pnl_percent) > 0).length}</span>
            </span>
            <span className="text-red-500">
              亏损: <span className="font-medium">{items.filter((i) => parseFloat(i.pnl_percent) < 0).length}</span>
            </span>
          </div>
        </div>
        <div className="text-xs text-[var(--terminal-muted)]">
          更新: {lastUpdate}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="text-sm text-[var(--terminal-muted)]">暂无交易记录</div>
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
              {items.map((item) => (
                <tr key={item.trade_id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-border)]/10">
                  <td className="py-2 text-xs text-[var(--terminal-muted)]">{item.exit_time || item.entry_time}</td>
                  <td className="py-2 font-medium">{item.symbol.replace("USDT", "")}</td>
                  <td className={`py-2 font-medium ${getSideColor(item.side)}`}>
                    {getSideLabel(item.side)}
                  </td>
                  <td className="py-2 text-right font-mono text-xs">{item.entry_price}</td>
                  <td className="py-2 text-right font-mono text-xs">
                    {item.exit_price ? (
                      item.exit_price
                    ) : (
                      <span className="text-[var(--terminal-muted)]">-</span>
                    )}
                  </td>
                  <td className={`py-2 text-right font-mono font-medium ${getPnLColor(item.pnl_percent)}`}>
                    {formatPnL(item.pnl_percent)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </TerminalCard>
  );
}