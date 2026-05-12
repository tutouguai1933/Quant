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
  openclaw: { cycle_check_interval_minutes: 15 },
  automation: { mode: "manual", paused: false, manual_takeover: false, armed_symbol: "", consecutive_failure_count: 0, last_cycle_status: "" },
  proxy: { connected: false, current_node: "", exit_ip: "" },
  daily_summary: { date: "", cycle_count: 0, alert_count: 0 },
};

// 状态指示灯
function StatusDot({ status }: { status: "ok" | "warning" | "error" }) {
  const colors = {
    ok: "bg-green-500",
    warning: "bg-yellow-500",
    error: "bg-red-500",
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status]}`} />;
}

// 格式化时间
function formatTime(iso: string | null): string {
  if (!iso) return "--";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      timeZone: "Asia/Shanghai",
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
    ok: "正常",
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
      <div className="flex items-center justify-between mb-2 pb-2 border-b border-[var(--terminal-border)]/30">
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

      {/* 状态列表 */}
      <div className="space-y-2 text-[12px]">
        {/* 定时巡检 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <StatusDot status={patrolStatus} />
            <span className="text-[var(--terminal-muted)]">巡检</span>
          </div>
          <div className="text-right">
            <span className="text-[var(--terminal-text)]">
              {status.patrol.running ? `${status.patrol.interval_minutes}分钟` : "已停止"}
            </span>
            {status.patrol.last_run_at && (
              <span className="text-[var(--terminal-dim)] text-[11px] ml-2">
                {formatTime(status.patrol.last_run_at)}
              </span>
            )}
          </div>
        </div>

        {/* 自动化 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <StatusDot status={automationStatus} />
            <span className="text-[var(--terminal-muted)]">自动化</span>
          </div>
          <div className="text-right">
            <span className="text-[var(--terminal-text)]">
              {status.automation.paused ? "已暂停" : status.automation.mode === "auto_live" ? "自动Live" : status.automation.mode === "auto_dry_run" ? "自动Dry" : "手动"}
            </span>
            {status.daily_summary.cycle_count > 0 && (
              <span className="text-[var(--terminal-dim)] text-[11px] ml-2">
                今日{status.daily_summary.cycle_count}轮
              </span>
            )}
          </div>
        </div>

        {/* 代理 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <StatusDot status={proxyStatus} />
            <span className="text-[var(--terminal-muted)]">代理</span>
          </div>
          <div className="text-right">
            <span className="text-[var(--terminal-text)]">
              {status.proxy.connected ? (status.proxy.current_node || "已连接") : "未连接"}
            </span>
            {status.proxy.exit_ip && (
              <span className="text-[var(--terminal-dim)] text-[11px] ml-2">
                {status.proxy.exit_ip}
              </span>
            )}
          </div>
        </div>
      </div>
    </TerminalCard>
  );
}
