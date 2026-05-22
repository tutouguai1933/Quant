"use client";

/**
 * 市场入场信号卡片
 * 展示 EnhancedStrategy 的4个入场条件检查结果
 */

import { useEffect, useState } from "react";
import { getEntryConditions, type EntryConditionItem } from "../lib/api";
import { TerminalCard } from "./terminal";

export function EntryStatusCard() {
  const [items, setItems] = useState<EntryConditionItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const response = await getEntryConditions();
        if (cancelled) return;

        if (response.error) {
          setError(response.error.message || "获取失败");
          setIsLoading(false);
          return;
        }

        setItems(response.data.items || []);
        setLastUpdate(new Date().toLocaleTimeString("zh-CN", { timeZone: "Asia/Shanghai" }));
        setError(null);
      } catch {
        if (!cancelled) setError("获取入场条件失败");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchData();
    const interval = setInterval(fetchData, 120000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (isLoading) {
    return (
      <TerminalCard title="市场入场信号">
        <div className="animate-pulse space-y-2">
          <div className="h-4 w-48 bg-[var(--terminal-border)] rounded" />
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

  if (items.length === 0) {
    return (
      <TerminalCard title="市场入场信号">
        <div className="text-sm text-[var(--terminal-muted)]">暂无数据</div>
      </TerminalCard>
    );
  }

  // 优先展示可能通过的（通过条件最多的排在前面）
  const sorted = [...items].sort((a, b) => {
    const aPass = Object.values(a.conditions).filter((c) => c.pass).length;
    const bPass = Object.values(b.conditions).filter((c) => c.pass).length;
    return bPass - aPass;
  });

  return (
    <TerminalCard title="市场入场信号">
      <div className="flex items-center gap-3 mb-3 text-xs">
        <span className="text-[var(--terminal-muted)]">
          监控 {items.length} 币种 · 通过 {items.filter((i) => i.all_pass).length} 个
        </span>
        <span className="text-[var(--terminal-muted)]/60">更新: {lastUpdate}</span>
      </div>

      <div className="space-y-2 max-h-[500px] overflow-y-auto">
        {sorted.map((item) => {
          const conds = item.conditions;
          const passCount = Object.values(conds).filter((c) => c.pass).length;

          return (
            <div
              key={item.symbol}
              className={`border rounded-lg p-2.5 ${
                item.all_pass
                  ? "border-green-500/30 bg-green-500/5"
                  : "border-[var(--terminal-border)]"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-[var(--terminal-text)]">
                  {item.symbol.replace("USDT", "")}
                </span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded ${
                    item.all_pass
                      ? "bg-green-500/20 text-green-400"
                      : passCount >= 2
                        ? "bg-yellow-500/10 text-yellow-400"
                        : "bg-red-500/10 text-red-400"
                  }`}
                >
                  {item.all_pass ? "可入场" : `${passCount}/4`}
                </span>
              </div>

              {/* 4个条件横向排列 */}
              <div className="grid grid-cols-4 gap-1.5">
                {Object.entries(conds).map(([key, c]) => (
                  <ConditionBadge
                    key={key}
                    label={c.label}
                    value={c.value}
                    threshold={c.threshold}
                    pass={c.pass}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="text-[10px] text-[var(--terminal-muted)]/50 mt-2">
        EnhancedStrategy 入场条件: RSI {"<"} 32 + 4H趋势向上 + 4H RSI {"<"} 70 + 成交量 ≥ 同时段60%
      </div>
    </TerminalCard>
  );
}

function ConditionBadge({
  label,
  value,
  threshold,
  pass,
}: {
  label: string;
  value: string;
  threshold: string;
  pass: boolean;
}) {
  return (
    <div
      className={`rounded p-1.5 text-center text-[11px] ${
        pass ? "bg-green-500/10 text-green-300" : "bg-[var(--terminal-border)]/10 text-[var(--terminal-muted)]"
      }`}
    >
      <div className="truncate">{label}</div>
      <div className={`font-mono ${pass ? "text-green-400" : "text-red-400/70"}`}>
        {value}
      </div>
      <div className="text-[9px] opacity-50">
        {pass ? "✅" : `需 ${threshold}`}
      </div>
    </div>
  );
}
