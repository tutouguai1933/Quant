"use client";

/**
 * 系统状态卡片
 * 显示定时巡检、自动化、代理等核心服务的运行状态
 */

import { useEffect, useState } from "react";
import { TerminalCard } from "./terminal";
import { getSystemStatus, type SystemStatus } from "../lib/api";

// 默认状态（用于加载中或出错时）
const defaultStatus: SystemStatus = {
  patrol: { running: false, interval_minutes: 0, last_run_at: null, last_run_status: null, total_runs: 0, failed_runs: 0 },
  automation: { mode: "manual", paused: false, manual_takeover: false, armed_symbol: "", consecutive_failure_count: 0, last_cycle_status: "" },
  proxy: { connected: false, current_node: "", exit_ip: "" },
  daily_summary: { date: "", cycle_count: 0, alert_count: 0 },
};

// 状态指示灯
function StatusDot({ status }: { status: "ok" | "warning" | "error" | "unknown" }) {
  const colors = {
    ok: "bg-green-500",
    warning: "bg-yellow-500",
    error: "bg-red-500",
    unknown: "bg-gray-500",
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status]} mr-2`} />;
}

// 格式化时间
function formatTime(iso: string | null): string {
  if (!iso) return "--";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      timeZone: "Asia/Shanghai",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

interface SystemStatusCardProps {
  refreshInterval?: number;
}

export function SystemStatusCard({ refreshInterval = 30000 }: SystemStatusCardProps) {
  const [status, setStatus] = useState<SystemStatus>(defaultStatus);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const response = await getSystemStatus();
        if (cancelled) return;

        if (response.error) {
          setError(response.error.message || "获取系统状态失败");
        } else {
          setStatus(response.data);
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

  // 计算各组件状态
  const patrolStatus = status.patrol.running ? "ok" : status.patrol.error ? "error" : "warning";
  const automationStatus = status.automation.paused
    ? "warning"
    : status.automation.error
    ? "error"
    : status.automation.mode === "auto_live" || status.automation.mode === "auto_dry_run"
    ? "ok"
    : "warning";
  const proxyStatus = status.proxy.connected ? "ok" : status.proxy.error ? "error" : "warning";

  // 计算整体状态
  const overallStatus: "ok" | "warning" | "error" =
    patrolStatus === "error" || automationStatus === "error" || proxyStatus === "error"
      ? "error"
      : patrolStatus === "warning" || automationStatus === "warning" || proxyStatus === "warning"
      ? "warning"
      : "ok";

  const statusLabels = {
    ok: "运行中",
    warning: "需关注",
    error: "异常",
  };

  if (isLoading) {
    return (
      <TerminalCard title="系统状态">
        <div className="text-[var(--terminal-muted)] text-[12px]">加载中...</div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title="系统状态">
      {error && <div className="text-red-400 text-[11px] mb-2">{error}</div>}

      {/* 整体状态标签 */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-[var(--terminal-border)]/30">
        <span className="text-[var(--terminal-muted)] text-[11px]">整体状态</span>
        <span
          className={`text-[11px] px-2 py-0.5 rounded ${
            overallStatus === "ok"
              ? "bg-green-500/20 text-green-400"
              : overallStatus === "warning"
              ? "bg-yellow-500/20 text-yellow-400"
              : "bg-red-500/20 text-red-400"
          }`}
        >
          {statusLabels[overallStatus]}
        </span>
      </div>

      <div className="space-y-3">
        {/* 定时巡检 */}
        <div className="flex items-start justify-between">
          <div className="flex items-center">
            <StatusDot status={patrolStatus} />
            <span className="text-[var(--terminal-text)] text-[12px]">定时巡检</span>
          </div>
          <div className="text-right">
            <div className="text-[var(--terminal-text)] text-[12px]">
              {status.patrol.running
                ? `${status.patrol.interval_minutes}分钟间隔`
                : "已停止"}
            </div>
            {status.patrol.last_run_at && (
              <div className="text-[var(--terminal-muted)] text-[11px]">
                上次: {formatTime(status.patrol.last_run_at)}
                {status.patrol.last_run_status && ` (${status.patrol.last_run_status})`}
              </div>
            )}
          </div>
        </div>

        {/* 自动化 */}
        <div className="flex items-start justify-between">
          <div className="flex items-center">
            <StatusDot status={automationStatus} />
            <span className="text-[var(--terminal-text)] text-[12px]">自动化</span>
          </div>
          <div className="text-right">
            <div className="text-[var(--terminal-text)] text-[12px]">
              {status.automation.paused
                ? "已暂停"
                : status.automation.mode === "auto_live"
                ? "自动Live"
                : status.automation.mode === "auto_dry_run"
                ? "自动Dry-run"
                : "手动模式"}
            </div>
            {status.daily_summary.cycle_count > 0 && (
              <div className="text-[var(--terminal-muted)] text-[11px]">
                今日 {status.daily_summary.cycle_count} 轮
              </div>
            )}
          </div>
        </div>

        {/* 代理 */}
        <div className="flex items-start justify-between">
          <div className="flex items-center">
            <StatusDot status={proxyStatus} />
            <span className="text-[var(--terminal-text)] text-[12px]">代理</span>
          </div>
          <div className="text-right">
            <div className="text-[var(--terminal-text)] text-[12px]">
              {status.proxy.connected ? status.proxy.current_node || "已连接" : "未连接"}
            </div>
            {status.proxy.exit_ip && (
              <div className="text-[var(--terminal-muted)] text-[11px]">
                {status.proxy.exit_ip}
              </div>
            )}
          </div>
        </div>

        {/* 今日统计 */}
        {(status.daily_summary.cycle_count > 0 || status.daily_summary.alert_count > 0) && (
          <div className="pt-2 border-t border-[var(--terminal-border)]/30 flex justify-between text-[11px]">
            <span className="text-[var(--terminal-muted)]">
              周期: <span className="text-[var(--terminal-text)]">{status.daily_summary.cycle_count}</span>
            </span>
            <span className={status.daily_summary.alert_count > 0 ? "text-yellow-400" : "text-[var(--terminal-muted)]"}>
              告警: <span className={status.daily_summary.alert_count > 0 ? "text-yellow-400" : "text-[var(--terminal-text)]"}>{status.daily_summary.alert_count}</span>
            </span>
          </div>
        )}
      </div>
    </TerminalCard>
  );
}
