"use client";

/**
 * 当前持仓详情卡片
 * 显示 Freqtrade 实时持仓信息
 */

import { useEffect, useState } from "react";
import { TerminalCard } from "./terminal";

type OpenTrade = {
  trade_id: number;
  symbol: string;
  pair: string;
  side: "long" | "short";
  open_rate: number;
  amount: number;
  stake_amount: number;
  profit_pct: number;
  profit_abs: number;
  open_date: string;
  source: "enhanced_strategy" | "automation_cycle";
};

type OpenTradesResponse = {
  items: OpenTrade[];
  total_stake: number;
  total_profit: number;
  total_profit_pct: number;
  count: number;
};

interface OpenPositionsCardProps {
  refreshInterval?: number;
}

export function OpenPositionsCard({ refreshInterval = 30000 }: OpenPositionsCardProps) {
  const [data, setData] = useState<OpenTradesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const res = await fetch("/api/v1/freqtrade/open-trades");
        const json = await res.json();
        if (!cancelled && !json.error) {
          setData(json.data);
          setUpdatedAt(new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
        }
      } catch {
        // 忽略错误
      } finally {
        if (!cancelled) setIsLoading(false);
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
      <TerminalCard title="当前持仓">
        <div className="text-[var(--terminal-muted)] text-[12px]">加载中...</div>
      </TerminalCard>
    );
  }

  if (!data || data.count === 0) {
    return (
      <TerminalCard title="当前持仓">
        <div className="flex justify-between items-center">
          <span className="text-[var(--terminal-muted)] text-[12px]">暂无持仓</span>
          {updatedAt && <span className="text-[var(--terminal-dim)] text-[11px]">{updatedAt}</span>}
        </div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title={`当前持仓 (${data.count})`}>
      {/* 持仓表格 */}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-[var(--terminal-border)]">
              <th className="text-left py-1.5 px-2 text-[var(--terminal-dim)]">币种</th>
              <th className="text-center py-1.5 px-2 text-[var(--terminal-dim)]">方向</th>
              <th className="text-right py-1.5 px-2 text-[var(--terminal-dim)]">入场价</th>
              <th className="text-right py-1.5 px-2 text-[var(--terminal-dim)]">盈亏</th>
              <th className="text-right py-1.5 px-2 text-[var(--terminal-dim)]">金额</th>
              <th className="text-center py-1.5 px-2 text-[var(--terminal-dim)]">来源</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((trade) => (
              <tr key={trade.trade_id} className="border-b border-[var(--terminal-border)]/30 hover:bg-[var(--terminal-bg-hover)]">
                <td className="py-1.5 px-2 text-[var(--terminal-text)] font-medium">
                  {trade.symbol}
                </td>
                <td className="py-1.5 px-2 text-center">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                    trade.side === "long"
                      ? "bg-green-500/20 text-green-400"
                      : "bg-red-500/20 text-red-400"
                  }`}>
                    {trade.side === "long" ? "多" : "空"}
                  </span>
                </td>
                <td className="py-1.5 px-2 text-right text-[var(--terminal-text)] font-mono">
                  {formatPrice(trade.open_rate)}
                </td>
                <td className={`py-1.5 px-2 text-right font-mono ${
                  trade.profit_pct >= 0 ? "text-green-400" : "text-red-400"
                }`}>
                  {trade.profit_pct >= 0 ? "+" : ""}{trade.profit_pct.toFixed(2)}%
                </td>
                <td className="py-1.5 px-2 text-right text-[var(--terminal-muted)]">
                  {trade.stake_amount.toFixed(2)} USDT
                </td>
                <td className="py-1.5 px-2 text-center">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                    trade.source === "automation_cycle"
                      ? "bg-cyan-500/20 text-cyan-400"
                      : "bg-purple-500/20 text-purple-400"
                  }`}>
                    {trade.source === "automation_cycle" ? "AC" : "ES"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 汇总 */}
      <div className="mt-2 pt-2 border-t border-[var(--terminal-border)]/30 flex justify-between items-center text-[11px]">
        <div>
          <span className="text-[var(--terminal-muted)]">
            合计: {data.total_stake.toFixed(2)} USDT
          </span>
          <span className="mx-2 text-[var(--terminal-dim)]">|</span>
          <span className={data.total_profit >= 0 ? "text-green-400" : "text-red-400"}>
            浮盈: {data.total_profit >= 0 ? "+" : ""}{data.total_profit.toFixed(3)} USDT ({data.total_profit_pct >= 0 ? "+" : ""}{data.total_profit_pct.toFixed(2)}%)
          </span>
        </div>
        {updatedAt && <span className="text-[var(--terminal-dim)]">{updatedAt}</span>}
      </div>
    </TerminalCard>
  );
}

function formatPrice(price: number): string {
  if (price >= 1000) return price.toFixed(2);
  if (price >= 1) return price.toFixed(4);
  if (price >= 0.0001) return price.toFixed(6);
  return price.toFixed(8);
}
