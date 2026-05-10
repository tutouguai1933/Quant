"use client";

/**
 * RSI概览卡片
 * 显示所有币种的RSI状态，支持筛选和排序
 * 使用共享 RsiDataContext 避免重复请求
 */

import { useState, useMemo } from "react";
import { type RsiSummaryItem } from "../lib/api";
import { useRsiData } from "../lib/rsi-data-context";
import { TerminalCard } from "./terminal";
import { RsiHistoryDialog } from "./rsi-history-dialog";

interface RsiSummaryCardProps {
  // refreshInterval 参数已弃用，使用共享上下文的刷新间隔
  refreshInterval?: number;
}

type FilterType = "all" | "overbought" | "oversold" | "neutral";
type SortType = "default" | "rsi_asc" | "rsi_desc";

export function RsiSummaryCard({ refreshInterval }: RsiSummaryCardProps) {
  // 使用共享 RSI 数据上下文
  const { items, isLoading, error, lastUpdate } = useRsiData();
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  // 筛选和排序状态
  const [filter, setFilter] = useState<FilterType>("all");
  const [sortBy, setSortBy] = useState<SortType>("default");

  // 筛选和排序后的数据
  const filteredItems = useMemo(() => {
    return items
      .filter((item) => {
        if (filter === "all") return true;
        return item.state === filter;
      })
      .sort((a, b) => {
        if (sortBy === "rsi_asc") return a.rsi - b.rsi;
        if (sortBy === "rsi_desc") return b.rsi - a.rsi;
        return 0;
      });
  }, [items, filter, sortBy]);

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
    <>
      <TerminalCard title="RSI概览 (1D周期)">
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

        {/* 筛选和排序控件 */}
        <div className="flex flex-wrap items-center gap-2 mb-3 pb-3 border-b border-[var(--terminal-border)]/30">
          {/* 状态筛选 */}
          <div className="flex gap-1">
            {(["all", "overbought", "oversold", "neutral"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2 py-1 text-[11px] rounded transition-colors ${
                  filter === f
                    ? "bg-[var(--terminal-cyan)]/20 text-[var(--terminal-cyan)] border border-[var(--terminal-cyan)]/50"
                    : "bg-[var(--terminal-border)]/30 text-[var(--terminal-muted)] hover:bg-[var(--terminal-border)]/50"
                }`}
              >
                {f === "all" ? "全部" : f === "overbought" ? "超买" : f === "oversold" ? "超卖" : "中性"}
              </button>
            ))}
          </div>

          {/* 排序选择 */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortType)}
            className="px-2 py-1 text-[11px] rounded bg-[var(--terminal-bg)] border border-[var(--terminal-border)] text-[var(--terminal-text)] focus:border-[var(--terminal-cyan)] focus:outline-none"
          >
            <option value="default">默认排序</option>
            <option value="rsi_asc">RSI 升序</option>
            <option value="rsi_desc">RSI 降序</option>
          </select>

          {/* 筛选结果数量 */}
          {filter !== "all" && (
            <span className="text-[10px] text-[var(--terminal-muted)]">
              显示 {filteredItems.length} 个结果
            </span>
          )}
        </div>

        {/* 提示 */}
        <div className="text-xs text-[var(--terminal-muted)] mb-3">
          💡 点击币种查看RSI历史记录
        </div>

        {/* RSI列表 */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
          {filteredItems.map((item) => (
            <button
              key={item.symbol}
              onClick={() => setSelectedSymbol(item.symbol)}
              className={`rounded-lg border p-3 text-left cursor-pointer transition-all hover:scale-105 hover:border-[var(--terminal-cyan)] ${getStateBgColor(item.state)}`}
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
            </button>
          ))}
        </div>

        {filteredItems.length === 0 && (
          <div className="text-sm text-[var(--terminal-muted)] text-center py-4">
            没有符合条件的币种
          </div>
        )}
      </TerminalCard>

      {/* RSI历史弹窗 */}
      <RsiHistoryDialog
        symbol={selectedSymbol || ""}
        open={!!selectedSymbol}
        onClose={() => setSelectedSymbol(null)}
      />
    </>
  );
}
