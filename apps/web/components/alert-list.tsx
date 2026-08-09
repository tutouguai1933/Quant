/* 告警列表组件，展示最近的告警记录。 */
"use client";

import { AlertTriangle, Bell } from "lucide-react";

import { TerminalCard } from "./terminal/terminal-card";
import { Badge } from "./ui/badge";

export type AlertLevel = "critical" | "warning" | "info";

export type AlertItem = {
  id: number;
  level: AlertLevel;
  code: string;
  message: string;
  created_at: string;
  service?: string;
  resolved?: boolean;
  resolved_at?: string;
};

export type AlertListProps = {
  alerts: AlertItem[];
  limit?: number;
};

const levelConfig: Record<AlertLevel, { variant: "danger" | "warning" | "neutral"; label: string }> = {
  critical: { variant: "danger", label: "严重" },
  warning: { variant: "warning", label: "警告" },
  info: { variant: "neutral", label: "信息" },
};

export function AlertList({ alerts, limit = 10 }: AlertListProps) {
  const displayAlerts = alerts.slice(0, limit);

  return (
    <TerminalCard
      title="最近告警"
      actions={<span className="text-sm text-[var(--terminal-muted)]">{alerts.length > limit ? `显示最近 ${limit} 条` : `${alerts.length} 条`}</span>}
    >
      {displayAlerts.length === 0 ? (
        <div className="rounded-lg border border-border/60 bg-muted/30 px-4 py-6 text-center">
          <Bell className="mx-auto size-6 text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">暂无告警记录</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {displayAlerts.map((alert) => (
            <li key={alert.id} className="rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <AlertTriangle className={`size-4 mt-0.5 ${alert.level === "critical" ? "text-[var(--terminal-red)]" : alert.level === "warning" ? "text-[var(--terminal-yellow)]" : "text-muted-foreground"}`} />
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant={levelConfig[alert.level].variant}>{levelConfig[alert.level].label}</Badge>
                        <span className="text-xs font-medium text-muted-foreground">{alert.code}</span>
                      </div>
                      <p className="text-sm text-foreground">{alert.message}</p>
                      {alert.service && (
                        <p className="text-xs text-muted-foreground">服务: {alert.service}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className="text-xs text-muted-foreground">{formatTime(alert.created_at)}</span>
                    {alert.resolved && (
                      <Badge variant="success" className="text-xs">已解决</Badge>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
    </TerminalCard>
  );
}

function formatTime(value: string): string {
  try {
    const date = new Date(value);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "刚刚";
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 7) return `${diffDays} 天前`;

    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

export function AlertListSkeleton() {
  return (
    <TerminalCard title="最近告警">
      <ul className="space-y-3">
        {[1, 2, 3].map((i) => (
          <li key={i} className="rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
            <div className="flex items-start gap-3">
              <div className="size-4 rounded bg-muted/40 animate-pulse" />
              <div className="space-y-2 flex-1">
                <div className="flex items-center gap-2">
                  <div className="h-4 w-8 rounded bg-muted/40 animate-pulse" />
                  <div className="h-3 w-16 rounded bg-muted/40 animate-pulse" />
                </div>
                <div className="h-4 w-48 rounded bg-muted/40 animate-pulse" />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </TerminalCard>
  );
}

export function getAlertListFallback(): AlertItem[] {
  return [];
}

export type AlertListResponse = {
  alerts: AlertItem[];
  total: number;
};