"use client";

/**
 * 当前持仓详情卡片
 * 按策略分组展示 Freqtrade 实时持仓信息
 * 采用卡片式紧凑布局
 */

import { useEffect, useState } from "react";
import { TerminalCard } from "./terminal";
import { fetchJson } from "../lib/api";

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

const STRATEGY_CONFIG: Record<string, { name: string; color: string; border: string; bg: string }> = {
  enhanced_strategy: {
    name: "EnhancedStrategy 独立策略",
    color: "text-purple-400",
    border: "border-purple-500/40",
    bg: "bg-purple-500/10",
  },
  automation_cycle: {
    name: "自动化周期策略",
    color: "text-cyan-400",
    border: "border-cyan-500/40",
    bg: "bg-cyan-500/10",
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
        const response = await fetchJson<OpenTradesResponse>("/freqtrade/open-trades");
        if (!cancelled && !response.error) {
          setData(response.data);
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
      <div className="space-y-3">
        {groups.map((group) => {
          const cfg = STRATEGY_CONFIG[group.key];
          const groupTotalStake = group.trades.reduce((s, t) => s + t.stake_amount, 0);
          const groupTotalProfit = group.trades.reduce((s, t) => s + t.profit_abs, 0);
          const groupProfitPct = groupTotalStake > 0 ? (groupTotalProfit / groupTotalStake) * 100 : 0;

          return (
            <div key={group.key} className={`rounded-lg border ${cfg.border} ${cfg.bg} p-2.5`}>
              {/* 策略标题行 */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`text-[12px] font-semibold ${cfg.color}`}>
                    {cfg.name}
                  </span>
                  <span className="text-[10px] text-[var(--terminal-dim)]">
                    {group.trades.length} 笔
                  </span>
                </div>
                <div className={`text-[11px] font-mono ${groupTotalProfit >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {groupTotalProfit >= 0 ? "+" : ""}{groupTotalProfit.toFixed(3)} USDT ({groupProfitPct >= 0 ? "+" : ""}{groupProfitPct.toFixed(2)}%)
                </div>
              </div>

              {/* 持仓卡片列表 */}
              <div className="space-y-2">
                {group.trades.map((trade) => (
                  <div
                    key={trade.trade_id}
                    className="bg-[var(--terminal-bg)]/60 rounded px-3 py-2 text-[11px]"
                  >
                    {/* 上行：币种 + 方向 + 数量 */}
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-[var(--terminal-text)] font-semibold text-[13px]">
                          {trade.symbol}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] ${
                            trade.side === "long"
                              ? "bg-green-500/20 text-green-400"
                              : "bg-red-500/20 text-red-400"
                          }`}
                        >
                          {trade.side === "long" ? "多" : "空"}
                        </span>
                        <span className="text-[var(--terminal-muted)] font-mono">
                          {formatAmount(trade.amount)}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        {/* 盈亏 */}
                        <div className={`text-right font-mono ${trade.profit_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                          <div className="text-[13px] font-semibold">
                            {trade.profit_pct >= 0 ? "+" : ""}{trade.profit_pct.toFixed(2)}%
                          </div>
                          <div className="text-[10px] opacity-70">
                            {trade.profit_abs >= 0 ? "+" : ""}{trade.profit_abs.toFixed(3)} USDT
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 下行：价格 + 金额 + 时间 - 分左右两块 */}
                    <div className="flex justify-between items-center text-[var(--terminal-muted)]">
                      {/* 左块：价格信息 */}
                      <div className="flex gap-4">
                        <div>
                          <span className="text-[var(--terminal-dim)]">入场 </span>
                          <span className="font-mono text-[var(--terminal-text)]">{formatPrice(trade.open_rate)}</span>
                        </div>
                        <div>
                          <span className="text-[var(--terminal-dim)]">现价 </span>
                          <span className="font-mono text-[var(--terminal-text)]">
                            {trade.current_rate ? formatPrice(trade.current_rate) : "-"}
                          </span>
                        </div>
                      </div>

                      {/* 右块：金额 + 时间 */}
                      <div className="flex gap-4 items-center">
                        <div>
                          <span className="text-[var(--terminal-dim)]">市值 </span>
                          <span className="font-mono text-[var(--terminal-text)]">
                            {trade.open_trade_value ? trade.open_trade_value.toFixed(2) : "-"}
                          </span>
                          <span className="text-[var(--terminal-dim)]"> / </span>
                          <span className="font-mono">{trade.stake_amount.toFixed(2)}</span>
                          <span className="text-[var(--terminal-dim)]"> USDT</span>
                        </div>
                        <div className="text-[10px] text-[var(--terminal-dim)]">
                          {formatDate(trade.open_date)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* 底部汇总 */}
      <div className="mt-3 pt-2 border-t border-[var(--terminal-border)]/30 flex justify-between items-center text-[11px]">
        <div className="flex items-center gap-3">
          <span className="text-[var(--terminal-muted)]">
            总成本: <span className="text-[var(--terminal-text)] font-mono">{data.total_stake.toFixed(2)}</span> USDT
          </span>
          <span className="text-[var(--terminal-dim)]">|</span>
          <span className="text-[var(--terminal-muted)]">
            总市值: <span className="text-[var(--terminal-text)] font-mono">{data.total_market_value?.toFixed(2) || "-"}</span> USDT
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
  const parts = dateStr.split(" ");
  if (parts.length < 2) return dateStr;
  const dateParts = parts[0].split("-");
  const timeParts = parts[1].split(":");
  return `${dateParts[1]}/${dateParts[2]} ${timeParts[0]}:${timeParts[1]}`;
}
