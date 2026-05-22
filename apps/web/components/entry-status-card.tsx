"use client";

/**
 * 市场入场信号卡片 - 紧凑版
 * 每行展示一个币种的4个入场条件检查结果
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
        <div className="animate-pulse h-4 w-48 bg-[var(--terminal-border)] rounded" />
      </TerminalCard>
    );
  }

  if (error) {
    return (
      <TerminalCard title="市场入场信号">
        <div className="text-xs text-red-500">⚠️ {error}</div>
      </TerminalCard>
    );
  }

  if (items.length === 0) {
    return (
      <TerminalCard title="市场入场信号">
        <div className="text-xs text-[var(--terminal-muted)]">暂无数据</div>
      </TerminalCard>
    );
  }

  const sorted = [...items].sort((a, b) => {
    const aPass = Object.values(a.conditions).filter((c) => c.pass).length;
    const bPass = Object.values(b.conditions).filter((c) => c.pass).length;
    return bPass - aPass;
  });

  // 只显示有超卖信号或通过条件 >=1 的币种
  const visible = sorted.filter((i) => {
    const passCount = Object.values(i.conditions).filter((c) => c.pass).length;
    return passCount >= 1 || i.rsi_1h < 40;
  }).slice(0, 8);

  return (
    <TerminalCard title={`市场入场信号 (${items.filter((i) => i.all_pass).length}/${items.length})`}>
      {/* 表头 */}
      <div className="grid grid-cols-[1fr_52px_52px_52px_52px] gap-0.5 mb-1 text-[10px] text-[var(--terminal-muted)]">
        <span>币种</span>
        <span className="text-center">RSI</span>
        <span className="text-center">趋势</span>
        <span className="text-center">4H RSI</span>
        <span className="text-center">成交量</span>
      </div>

      {/* 数据行 */}
      <div className="space-y-px">
        {visible.map((item) => {
          const c = item.conditions;
          return (
            <div
              key={item.symbol}
              className={`grid grid-cols-[1fr_52px_52px_52px_52px] gap-0.5 py-1 px-1 rounded text-[11px] ${
                item.all_pass ? "bg-green-500/10" : ""
              }`}
            >
              <span className="font-medium truncate">{item.symbol.replace("USDT", "")}</span>
              <ConditionCell label={c.rsi_oversold.label} value={c.rsi_oversold.value} pass={c.rsi_oversold.pass} />
              <ConditionCell label={c.trend_4h.label} value={c.trend_4h.value} pass={c.trend_4h.pass} />
              <ConditionCell label={c.rsi_4h_ok.label} value={c.rsi_4h_ok.value} pass={c.rsi_4h_ok.pass} />
              <ConditionCell label={c.volume_ok.label} value={c.volume_ok.value} pass={c.volume_ok.pass} />
            </div>
          );
        })}
      </div>

      <div className="text-[9px] text-[var(--terminal-muted)]/40 mt-1.5 flex justify-between">
        <span>RSI&lt;32 · 4H价格&gt;SMA200 · 4H RSI&lt;70 · 成交量≥同时段60%</span>
        <span>{lastUpdate}</span>
      </div>
    </TerminalCard>
  );
}

function ConditionCell({ value, pass }: { label: string; value: string; pass: boolean }) {
  return (
    <span className={`text-center font-mono ${pass ? "text-green-400" : "text-red-400/60"}`}>
      {value}
    </span>
  );
}
