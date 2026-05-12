"use client";

/**
 * 当前持仓详情卡片
 * 按策略分组展示 Freqtrade 实时持仓信息
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
  current_rate: number;
  open_trade_value: number;
  profit_pct: number;
  profit_abs: number;
  open_date: string;
  stop_loss_abs: number | null;
  strategy: string;
  source: "enhanced_strategy" | "automation_cycle";
};

type OpenTradesResponse = {
  items: OpenTrade[];
  total_stake: number;
  total_market_value?: number;
  total_profit: number;
  total_profit_pct: number;
  count: number;
};

interface OpenPositionsCardProps {
  refreshInterval?: number;
}

const STRATEGY_LABELS: Record<string, { name: string; color: string; border: string }> = {
  enhanced_strategy: {
    name: "EnhancedStrategy 独立策略",
    color: "text-purple-400",
    border: "border-purple-500/30",
  },
  automation_cycle: {
    name: "自动化周期策略",
    color: "text-cyan-400",
    border: "border-cyan-500/30",
  },
};

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
          setUpdatedAt(
            new Date().toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })
          );
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
          {updatedAt && (
            <span className="text-[var(--terminal-dim)] text-[11px]">{updatedAt}</span>
          )}
        </div>
      </TerminalCard>
    );
  }

  const esTrades = data.items.filter((t) => t.source === "enhanced_strategy");
  const acTrades = data.items.filter((t) => t.source === "automation_cycle");

  const groups = [
    { key: "enhanced_strategy", trades: esTrades },
    { key: "automation_cycle", trades: acTrades },
  ].filter((g) => g.trades.length > 0);

  return (
    <TerminalCard title={`当前持仓 (${data.count})`}>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-[var(--terminal-border)]">
              <th className="text-left py-1.5 px-1.5 text-[var(--terminal-dim)]">币种</th>
              <th className="text-right py-1.5 px-1.5 text-[var(--terminal-dim)]">数量</th>
              <th className="text-right py-1.5 px-1.5 text-[var(--terminal-dim)]">入场价</th>
              <th className="text-right py-1.5 px-1.5 text-[var(--terminal-dim)]">当前价</th>
              <th className="text-right py-1.5 px-1.5 text-[var(--terminal-dim)]">市值</th>
              <th className="text-right py-1.5 px-1.5 text-[var(--terminal-dim)]">成本</th>
              <th className="text-right py-1.5 px-1.5 text-[var(--terminal-dim)]">盈亏</th>
              <th className="text-right py-1.5 px-1.5 text-[var(--terminal-dim)]">开仓时间</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group, gi) => {
              const cfg = STRATEGY_LABELS[group.key];
              const groupTotalStake = group.trades.reduce((s, t) => s + t.stake_amount, 0);
              const groupTotalValue = group.trades.reduce((s, t) => s + (t.open_trade_value || 0), 0);
              const groupTotalProfit = group.trades.reduce((s, t) => s + t.profit_abs, 0);
              const groupProfitPct = groupTotalStake > 0 ? (groupTotalProfit / groupTotalStake) * 100 : 0;

              return (
                <tbody key={group.key}>
                  {/* 策略分组标题行 */}
                  <tr>
                    <td colSpan={8} className="py-1.5 px-1.5">
                      <div className={`flex items-center gap-2 border-l-2 ${cfg.border} pl-2`}>
                        <span className={`text-[11px] font-semibold ${cfg.color}`}>
                          {cfg.name}
                        </span>
                        <span className="text-[10px] text-[var(--terminal-dim)]">
                          {group.trades.length} 笔 | 成本 {groupTotalStake.toFixed(2)} | 市值 {groupTotalValue.toFixed(2)} | 浮盈{" "}
                          <span className={groupTotalProfit >= 0 ? "text-green-400" : "text-red-400"}>
                            {groupTotalProfit >= 0 ? "+" : ""}{groupTotalProfit.toFixed(3)} ({groupProfitPct >= 0 ? "+" : ""}{groupProfitPct.toFixed(2)}%)
                          </span>
                        </span>
                      </div>
                    </td>
                  </tr>
                  {group.trades.map((trade) => (
                    <tr
                      key={trade.trade_id}
                      className="border-b border-[var(--terminal-border)]/20 hover:bg-[var(--terminal-bg-hover)]"
                    >
                      <td className="py-1.5 px-1.5">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[var(--terminal-text)] font-medium">
                            {trade.symbol}
                          </span>
                          <span
                            className={`px-1 py-0.5 rounded text-[9px] ${
                              trade.side === "long"
                                ? "bg-green-500/20 text-green-400"
                                : "bg-red-500/20 text-red-400"
                            }`}
                          >
                            {trade.side === "long" ? "多" : "空"}
                          </span>
                        </div>
                      </td>
                      <td className="py-1.5 px-1.5 text-right text-[var(--terminal-text)] font-mono">
                        {formatAmount(trade.amount)} <span className="text-[var(--terminal-dim)]">{trade.symbol}</span>
                      </td>
                      <td className="py-1.5 px-1.5 text-right text-[var(--terminal-text)] font-mono">
                        {formatPrice(trade.open_rate)}
                      </td>
                      <td className="py-1.5 px-1.5 text-right text-[var(--terminal-text)] font-mono">
                        {trade.current_rate ? formatPrice(trade.current_rate) : "-"}
                      </td>
                      <td className="py-1.5 px-1.5 text-right text-[var(--terminal-text)] font-mono">
                        {trade.open_trade_value ? trade.open_trade_value.toFixed(2) : "-"} USDT
                      </td>
                      <td className="py-1.5 px-1.5 text-right text-[var(--terminal-muted)] font-mono">
                        {trade.stake_amount.toFixed(2)} USDT
                      </td>
                      <td
                        className={`py-1.5 px-1.5 text-right font-mono ${
                          trade.profit_pct >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        <div>{trade.profit_pct >= 0 ? "+" : ""}{trade.profit_pct.toFixed(2)}%</div>
                        <div className="text-[10px] opacity-70">
                          {trade.profit_abs >= 0 ? "+" : ""}{trade.profit_abs.toFixed(3)}
                        </div>
                      </td>
                      <td className="py-1.5 px-1.5 text-right text-[var(--terminal-dim)] text-[10px]">
                        {formatDate(trade.open_date)}
                      </td>
                    </tr>
                  ))}
                  {/* 分组间留空 */}
                  {gi < groups.length - 1 && (
                    <tr>
                      <td colSpan={8} className="py-1" />
                    </tr>
                  )}
                </tbody>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 底部汇总 */}
      <div className="mt-2 pt-2 border-t border-[var(--terminal-border)]/30 flex justify-between items-center text-[11px]">
        <div className="flex items-center gap-3">
          <span className="text-[var(--terminal-muted)]">
            总成本: <span className="text-[var(--terminal-text)]">{data.total_stake.toFixed(2)} USDT</span>
          </span>
          <span className="text-[var(--terminal-dim)]">|</span>
          <span className="text-[var(--terminal-muted)]">
            总市值: <span className="text-[var(--terminal-text)]">{data.total_market_value?.toFixed(2) || "-"} USDT</span>
          </span>
          <span className="text-[var(--terminal-dim)]">|</span>
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

function formatAmount(amount: number): string {
  if (amount >= 1000) return amount.toFixed(2);
  if (amount >= 1) return amount.toFixed(4);
  if (amount >= 0.01) return amount.toFixed(6);
  return amount.toFixed(8);
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "-";
  // "2026-05-11 05:36:25" -> "05/11 05:36"
  const parts = dateStr.split(" ");
  if (parts.length < 2) return dateStr;
  const dateParts = parts[0].split("-");
  const timeParts = parts[1].split(":");
  return `${dateParts[1]}/${dateParts[2]} ${timeParts[0]}:${timeParts[1]}`;
}
