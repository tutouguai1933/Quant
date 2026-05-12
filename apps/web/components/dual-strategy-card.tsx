"use client";

/**
 * 双策略状态卡片
 * 显示 Freqtrade 和自动化周期两个独立策略的运行状态和收益统计
 */

import { useEffect, useState } from "react";
import { TerminalCard } from "./terminal";
import {
  getFreqtradeStatus,
  getFreqtradeProfitBySource,
  type FreqtradeStatus,
  type FreqtradeProfitBySource,
  type FreqtradeSourceStats,
} from "../lib/api";
import { getSystemStatus, type SystemStatus } from "../lib/api";

// 默认状态
const defaultFreqtradeStatus: FreqtradeStatus = {
  running: false,
  strategy: "EnhancedStrategy",
  open_trades: 0,
  open_symbols: [],
  profit: {
    total_percent: 0,
    total_ratio: 0,
    winrate: 0,
    trade_count: 0,
    winning_trades: 0,
    losing_trades: 0,
    best_pair: "",
    best_rate: 0,
    sharpe: 0,
  },
  latest_trade: "",
  bot_start_date: "",
};

const defaultSourceStats: FreqtradeSourceStats = {
  trade_count: 0,
  winning_trades: 0,
  losing_trades: 0,
  total_profit: 0,
  winrate: 0,
  open_trades: 0,
  open_symbols: [],
};

const defaultProfitBySource: FreqtradeProfitBySource = {
  enhanced_strategy: defaultSourceStats,
  automation_cycle: defaultSourceStats,
  total: defaultSourceStats,
};

const defaultSystemStatus: SystemStatus = {
  patrol: { running: false, interval_minutes: 0, last_run_at: null, last_run_status: null, total_runs: 0, failed_runs: 0 },
  openclaw: { cycle_check_interval_minutes: 15 },
  automation: { mode: "manual", paused: false, manual_takeover: false, armed_symbol: "", consecutive_failure_count: 0, last_cycle_status: "" },
  proxy: { connected: false, current_node: "", exit_ip: "" },
  daily_summary: { date: "", cycle_count: 0, alert_count: 0 },
};

// 格式化收益
function formatProfit(value: number): string {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${value.toFixed(3)} USDT`;
}

// 格式化胜率
function formatWinrate(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

// 状态指示灯
function StatusDot({ status }: { status: "ok" | "warning" | "error" }) {
  const colors = {
    ok: "bg-green-500",
    warning: "bg-yellow-500",
    error: "bg-red-500",
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status]}`} />;
}

// 收益颜色
function getProfitColor(value: number): string {
  return value >= 0 ? "text-green-400" : "text-red-400";
}

interface DualStrategyCardProps {
  refreshInterval?: number;
}

export function DualStrategyCard({ refreshInterval = 30000 }: DualStrategyCardProps) {
  const [freqtradeStatus, setFreqtradeStatus] = useState<FreqtradeStatus>(defaultFreqtradeStatus);
  const [profitBySource, setProfitBySource] = useState<FreqtradeProfitBySource>(defaultProfitBySource);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>(defaultSystemStatus);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const [ftRes, profitRes, sysRes] = await Promise.all([
          getFreqtradeStatus(),
          getFreqtradeProfitBySource(),
          getSystemStatus(),
        ]);

        if (cancelled) return;

        if (!ftRes.error && ftRes.data && ftRes.data.running !== undefined) {
          setFreqtradeStatus(ftRes.data);
        }
        if (!profitRes.error && profitRes.data && profitRes.data.total) {
          setProfitBySource(profitRes.data);
        }
        if (!sysRes.error && sysRes.data && sysRes.data.automation) {
          setSystemStatus(sysRes.data);
        }
      } catch {
        // 忽略错误
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

  // 计算 Freqtrade 状态
  const ftStatus: "ok" | "warning" | "error" = freqtradeStatus.running
    ? freqtradeStatus.profit.total_percent >= 0 ? "ok" : "warning"
    : "error";

  // 计算自动化周期状态（OpenClaw 是独立容器，只要未暂停就是运行中）
  const autoStatus: "ok" | "warning" | "error" = systemStatus.automation.paused
    ? "warning"
    : "ok";

  const { enhanced_strategy, automation_cycle, total } = profitBySource;

  if (isLoading) {
    return (
      <TerminalCard title="策略运行状态">
        <div className="text-[var(--terminal-muted)] text-[12px]">加载中...</div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title="策略运行状态">
      {/* 运行状态 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pb-3 border-b border-[var(--terminal-border)]/30">
        {/* Freqtrade */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <StatusDot status={ftStatus} />
            <span className="text-[var(--terminal-text)] text-[12px] font-medium">Freqtrade</span>
            <span className={`text-[11px] px-1.5 py-0.5 rounded ${
              ftStatus === "ok" ? "bg-green-500/20 text-green-400" :
              ftStatus === "warning" ? "bg-yellow-500/20 text-yellow-400" :
              "bg-red-500/20 text-red-400"
            }`}>
              {freqtradeStatus.running ? "运行中" : "已停止"}
            </span>
          </div>
          <div className="text-[11px] text-[var(--terminal-muted)]">
            策略: {freqtradeStatus.strategy}
          </div>
          <div className="text-[11px] text-[var(--terminal-muted)]">
            持仓: {(freqtradeStatus.open_symbols || []).map(s => s.replace("/USDT", "")).join(", ") || "无"}
          </div>
        </div>

        {/* 自动化周期 */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <StatusDot status={autoStatus} />
            <span className="text-[var(--terminal-text)] text-[12px] font-medium">自动化周期</span>
            <span className={`text-[11px] px-1.5 py-0.5 rounded ${
              autoStatus === "ok" ? "bg-green-500/20 text-green-400" :
              autoStatus === "warning" ? "bg-yellow-500/20 text-yellow-400" :
              "bg-red-500/20 text-red-400"
            }`}>
              {systemStatus.automation.paused ? "已暂停" : "运行中"}
            </span>
          </div>
          <div className="text-[11px] text-[var(--terminal-muted)]">
            模式: {systemStatus.automation.mode === "auto_live" ? "自动Live" :
                   systemStatus.automation.mode === "auto_dry_run" ? "自动Dry" : "手动"}
          </div>
          <div className="text-[11px] text-[var(--terminal-muted)]">
            周期间隔: {systemStatus.openclaw?.cycle_check_interval_minutes || 15}分钟 | 代理: {systemStatus.proxy.current_node || "无"}
          </div>
        </div>
      </div>

      {/* 收益统计 */}
      <div className="pt-3">
        <div className="text-[var(--terminal-muted)] text-[11px] mb-2">收益统计</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* EnhancedStrategy */}
          <div className="space-y-1">
            <div className="text-[var(--terminal-text)] text-[11px] font-medium">EnhancedStrategy</div>
            <div className={`text-[13px] font-mono ${getProfitColor(enhanced_strategy.total_profit)}`}>
              {formatProfit(enhanced_strategy.total_profit)}
            </div>
            <div className="text-[11px] text-[var(--terminal-muted)]">
              交易: {enhanced_strategy.trade_count}笔 ({enhanced_strategy.winning_trades}胜{enhanced_strategy.losing_trades}负)
            </div>
            <div className="text-[11px] text-[var(--terminal-muted)]">
              胜率: {formatWinrate(enhanced_strategy.winrate)}
            </div>
            <div className="text-[11px] text-[var(--terminal-muted)]">
              当前持仓: {(enhanced_strategy.open_symbols || []).join(", ") || "无"}
            </div>
          </div>

          {/* 自动化周期 */}
          <div className="space-y-1">
            <div className="text-[var(--terminal-text)] text-[11px] font-medium">自动化周期</div>
            <div className={`text-[13px] font-mono ${getProfitColor(automation_cycle.total_profit)}`}>
              {formatProfit(automation_cycle.total_profit)}
            </div>
            <div className="text-[11px] text-[var(--terminal-muted)]">
              交易: {automation_cycle.trade_count}笔 ({automation_cycle.winning_trades}胜{automation_cycle.losing_trades}负)
            </div>
            <div className="text-[11px] text-[var(--terminal-muted)]">
              胜率: {formatWinrate(automation_cycle.winrate)}
            </div>
            <div className="text-[11px] text-[var(--terminal-muted)]">
              当前持仓: {(automation_cycle.open_symbols || []).join(", ") || "无"}
            </div>
          </div>
        </div>

        {/* 总计 */}
        <div className="mt-3 pt-2 border-t border-[var(--terminal-border)]/30">
          <div className="text-[11px] text-[var(--terminal-muted)]">
            合计: <span className={getProfitColor(total.total_profit)}>{formatProfit(total.total_profit)}</span> | 交易 {total.trade_count}笔 | 胜率 {formatWinrate(total.winrate)}
          </div>
        </div>
      </div>
    </TerminalCard>
  );
}
