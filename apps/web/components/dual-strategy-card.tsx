"use client";

/**
 * 双策略状态卡片
 * 显示 Freqtrade 和自动化周期两个独立策略的运行状态
 */

import { useEffect, useState } from "react";
import { TerminalCard } from "./terminal";
import { getFreqtradeStatus, type FreqtradeStatus } from "../lib/api";
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

const defaultSystemStatus: SystemStatus = {
  patrol: { running: false, interval_minutes: 0, last_run_at: null, last_run_status: null, total_runs: 0, failed_runs: 0 },
  automation: { mode: "manual", paused: false, manual_takeover: false, armed_symbol: "", consecutive_failure_count: 0, last_cycle_status: "" },
  proxy: { connected: false, current_node: "", exit_ip: "" },
  daily_summary: { date: "", cycle_count: 0, alert_count: 0 },
};

// 格式化百分比
function formatPercent(value: number): string {
  if (value === 0) return "0%";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
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

interface DualStrategyCardProps {
  refreshInterval?: number;
}

export function DualStrategyCard({ refreshInterval = 30000 }: DualStrategyCardProps) {
  const [freqtradeStatus, setFreqtradeStatus] = useState<FreqtradeStatus>(defaultFreqtradeStatus);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>(defaultSystemStatus);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const [ftRes, sysRes] = await Promise.all([
          getFreqtradeStatus(),
          getSystemStatus(),
        ]);

        if (cancelled) return;

        if (!ftRes.error) {
          setFreqtradeStatus(ftRes.data);
        }
        if (!sysRes.error) {
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

  // 计算自动化周期状态
  const autoStatus: "ok" | "warning" | "error" = systemStatus.automation.paused
    ? "warning"
    : systemStatus.patrol.running
    ? "ok"
    : "error";

  if (isLoading) {
    return (
      <TerminalCard title="策略运行状态">
        <div className="text-[var(--terminal-muted)] text-[12px]">加载中...</div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title="策略运行状态">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Freqtrade 策略 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between pb-2 border-b border-[var(--terminal-border)]/30">
            <div className="flex items-center gap-2">
              <StatusDot status={ftStatus} />
              <span className="text-[var(--terminal-text)] text-[12px] font-medium">Freqtrade</span>
            </div>
            <span className={`text-[11px] px-2 py-0.5 rounded ${
              ftStatus === "ok" ? "bg-green-500/20 text-green-400" :
              ftStatus === "warning" ? "bg-yellow-500/20 text-yellow-400" :
              "bg-red-500/20 text-red-400"
            }`}>
              {freqtradeStatus.running ? "运行中" : "已停止"}
            </span>
          </div>

          <div className="space-y-1.5 text-[11px]">
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">策略</span>
              <span className="text-[var(--terminal-text)]">{freqtradeStatus.strategy}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">持仓</span>
              <span className="text-[var(--terminal-text)]">
                {freqtradeStatus.open_trades > 0
                  ? freqtradeStatus.open_symbols.join(", ").replace("/USDT", "")
                  : "无"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">总收益</span>
              <span className={freqtradeStatus.profit.total_percent >= 0 ? "text-green-400" : "text-red-400"}>
                {formatPercent(freqtradeStatus.profit.total_percent)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">胜率</span>
              <span className="text-[var(--terminal-text)]">
                {(freqtradeStatus.profit.winrate * 100).toFixed(0)}%
                <span className="text-[var(--terminal-dim)] ml-1">
                  ({freqtradeStatus.profit.winning_trades}胜{freqtradeStatus.profit.losing_trades}负)
                </span>
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">交易次数</span>
              <span className="text-[var(--terminal-text)]">{freqtradeStatus.profit.trade_count}笔</span>
            </div>
          </div>
        </div>

        {/* 自动化周期 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between pb-2 border-b border-[var(--terminal-border)]/30">
            <div className="flex items-center gap-2">
              <StatusDot status={autoStatus} />
              <span className="text-[var(--terminal-text)] text-[12px] font-medium">自动化周期</span>
            </div>
            <span className={`text-[11px] px-2 py-0.5 rounded ${
              autoStatus === "ok" ? "bg-green-500/20 text-green-400" :
              autoStatus === "warning" ? "bg-yellow-500/20 text-yellow-400" :
              "bg-red-500/20 text-red-400"
            }`}>
              {systemStatus.automation.paused ? "已暂停" : systemStatus.patrol.running ? "运行中" : "已停止"}
            </span>
          </div>

          <div className="space-y-1.5 text-[11px]">
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">模式</span>
              <span className="text-[var(--terminal-text)]">
                {systemStatus.automation.mode === "auto_live" ? "自动Live" :
                 systemStatus.automation.mode === "auto_dry_run" ? "自动Dry" : "手动"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">巡检间隔</span>
              <span className="text-[var(--terminal-text)]">
                {systemStatus.patrol.running ? `${systemStatus.patrol.interval_minutes}分钟` : "未启动"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">今日执行</span>
              <span className="text-[var(--terminal-text)]">
                {systemStatus.daily_summary.cycle_count}轮
                <span className="text-[var(--terminal-dim)] ml-1">
                  ({systemStatus.daily_summary.alert_count}告警)
                </span>
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">最后状态</span>
              <span className="text-[var(--terminal-text)]">
                {systemStatus.automation.last_cycle_status || "--"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--terminal-muted)]">代理</span>
              <span className={systemStatus.proxy.connected ? "text-green-400" : "text-red-400"}>
                {systemStatus.proxy.connected
                  ? systemStatus.proxy.current_node || "已连接"
                  : "未连接"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </TerminalCard>
  );
}
