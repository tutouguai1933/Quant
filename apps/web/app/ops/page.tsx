/* 运维监控页面，展示服务健康状态、告警记录和巡检控制。 */
"use client";

import { useEffect, useState } from "react";

import { Play, Square, Clock, RefreshCw, Server, Shield } from "lucide-react";

import { AppShell } from "../../components/app-shell";
import { PageHero } from "../../components/page-hero";
import { Skeleton } from "../../components/ui/skeleton";
import { StatusBar } from "../../components/status-bar";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  HealthStatusCard,
  HealthStatusSkeleton,
  HealthServiceStatus,
  HealthStatus,
  getHealthStatusFallback,
} from "../../components/health-status-card";
import {
  AlertList,
  AlertListSkeleton,
  AlertItem,
  getAlertListFallback,
} from "../../components/alert-list";
import { useWebSocket } from "../../lib/websocket-context";
import {
  fetchJson,
  resolveControlPlaneUrl,
} from "../../lib/api";

type PatrolStatus = {
  is_running: boolean;
  started_at?: string;
  last_completed_at?: string;
  next_scheduled_at?: string;
  schedule_enabled: boolean;
  interval_minutes: number;
};

type PatrolSchedule = {
  enabled: boolean;
  interval_minutes: number;
  next_run_at?: string;
  last_run_at?: string;
};

export default function OpsPage() {
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState<HealthServiceStatus>(getHealthStatusFallback());
  const [alerts, setAlerts] = useState<AlertItem[]>(getAlertListFallback());
  const [patrolStatus, setPatrolStatus] = useState<PatrolStatus>({
    is_running: false,
    schedule_enabled: false,
    interval_minutes: 60,
  });
  const [patrolSchedule, setPatrolSchedule] = useState<PatrolSchedule>({
    enabled: false,
    interval_minutes: 60,
  });

  const { subscribe, unsubscribe, channelMessages } = useWebSocket();

  // Subscribe to health_status channel for real-time updates
  useEffect(() => {
    subscribe("health_status");
    return () => unsubscribe("health_status");
  }, [subscribe, unsubscribe]);

  // Handle WebSocket messages for health status updates
  useEffect(() => {
    const healthMessage = channelMessages["health_status"];
    if (healthMessage && healthMessage.data) {
      const data = healthMessage.data as HealthServiceStatus;
      setHealthStatus(data);
    }
  }, [channelMessages]);

  // Fetch session
  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {
        // Keep default session state
      });
  }, []);

  // Fetch health status, alerts, and patrol status
  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    Promise.allSettled([
      fetchHealthStatus(controller.signal),
      fetchAlerts(controller.signal),
      fetchPatrolStatus(controller.signal),
      fetchPatrolSchedule(controller.signal),
    ])
      .then(([healthRes, alertsRes, patrolRes, scheduleRes]) => {
        clearTimeout(timeoutId);

        if (healthRes.status === "fulfilled" && !healthRes.value.error) {
          setHealthStatus(healthRes.value.data || getHealthStatusFallback());
        }
        if (alertsRes.status === "fulfilled" && !alertsRes.value.error) {
          setAlerts(alertsRes.value.data?.alerts || []);
        }
        if (patrolRes.status === "fulfilled" && !patrolRes.value.error) {
          setPatrolStatus(patrolRes.value.data?.status || patrolStatus);
        }
        if (scheduleRes.status === "fulfilled" && !scheduleRes.value.error) {
          setPatrolSchedule(scheduleRes.value.data?.schedule || patrolSchedule);
        }

        setIsLoading(false);
      })
      .catch(() => {
        clearTimeout(timeoutId);
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  const handleStartPatrol = async () => {
    try {
      const response = await fetch(await resolveControlPlaneUrl("/api/v1/patrol/start"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        setPatrolStatus((prev) => ({ ...prev, is_running: true, started_at: new Date().toISOString() }));
      }
    } catch (error) {
      console.error("Failed to start patrol:", error);
    }
  };

  const handleStopPatrol = async () => {
    try {
      const response = await fetch(await resolveControlPlaneUrl("/api/v1/patrol/stop"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        setPatrolStatus((prev) => ({ ...prev, is_running: false }));
      }
    } catch (error) {
      console.error("Failed to stop patrol:", error);
    }
  };

  const statusItems = [
    {
      label: "整体健康",
      value: healthStatus.overall_status === "healthy" ? "正常" : healthStatus.overall_status === "warning" ? "警告" : "异常",
      status: healthStatus.overall_status === "healthy" ? "success" : healthStatus.overall_status === "warning" ? "waiting" : "error",
      detail: `${healthStatus.services.length} 个服务`,
    },
    {
      label: "活跃告警",
      value: String(alerts.filter((a) => !a.resolved).length),
      status: alerts.some((a) => a.level === "critical" && !a.resolved) ? "error" : alerts.some((a) => !a.resolved) ? "waiting" : "success",
      detail: `共 ${alerts.length} 条`,
    },
    {
      label: "巡检状态",
      value: patrolStatus.is_running ? "运行中" : patrolStatus.schedule_enabled ? "已调度" : "待机",
      status: patrolStatus.is_running ? "active" : patrolStatus.schedule_enabled ? "success" : "waiting",
      detail: patrolStatus.is_running ? "手动巡检" : `间隔 ${patrolStatus.interval_minutes} 分钟`,
    },
    {
      label: "下次巡检",
      value: patrolStatus.next_scheduled_at ? formatTime(patrolStatus.next_scheduled_at) : "未调度",
      status: patrolStatus.schedule_enabled ? "success" : "waiting",
      detail: patrolStatus.schedule_enabled ? `上次: ${patrolStatus.last_completed_at ? formatTime(patrolStatus.last_completed_at) : "无"}` : "",
    },
  ];

  return (
    <AppShell
      title="运维监控"
      subtitle="服务健康状态、告警记录和巡检控制"
      currentPath="/ops"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="Operations"
        title="系统运维监控"
        description="查看所有服务健康状态、管理告警记录和控制巡检计划"
      />

      <StatusBar items={statusItems} />

      {isLoading ? (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <HealthStatusSkeleton key={i} />
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <AlertListSkeleton />
            <Skeleton className="h-64 rounded-xl" />
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* 服务健康状态卡片网格 */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {healthStatus.services.map((service) => (
              <HealthStatusCard
                key={service.name}
                serviceName={service.name}
                status={service.status}
                responseTime={service.response_time}
                lastCheck={service.last_check}
                detail={service.detail}
              />
            ))}
          </div>

          {/* 告警列表和巡检控制面板 */}
          <div className="grid gap-4 lg:grid-cols-2">
            <AlertList alerts={alerts} limit={10} />

            {/* 巡检控制面板 */}
            <Card className="bg-card/90">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <RefreshCw className="size-4 text-primary" />
                  <CardTitle className="text-base">巡检控制</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-2">
                <div className="space-y-4">
                  {/* 当前状态 */}
                  <div className="rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Clock className="size-4 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">当前状态</span>
                      </div>
                      <Badge variant={patrolStatus.is_running ? "accent" : patrolStatus.schedule_enabled ? "success" : "neutral"}>
                        {patrolStatus.is_running ? "正在运行" : patrolStatus.schedule_enabled ? "已调度" : "待机"}
                      </Badge>
                    </div>
                  </div>

                  {/* 手动控制 */}
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleStartPatrol}
                      disabled={patrolStatus.is_running}
                      className="flex items-center gap-2"
                    >
                      <Play className="size-4" />
                      启动巡检
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleStopPatrol}
                      disabled={!patrolStatus.is_running}
                      className="flex items-center gap-2"
                    >
                      <Square className="size-4" />
                      停止巡检
                    </Button>
                  </div>

                  {/* 调度信息 */}
                  <div className="grid gap-3 sm:grid-cols-2">
                    <InfoBlock
                      label="调度状态"
                      value={patrolSchedule.enabled ? "已启用" : "已禁用"}
                    />
                    <InfoBlock
                      label="巡检间隔"
                      value={`${patrolSchedule.interval_minutes} 分钟`}
                    />
                    {patrolSchedule.last_run_at && (
                      <InfoBlock
                        label="上次运行"
                        value={formatTime(patrolSchedule.last_run_at)}
                      />
                    )}
                    {patrolSchedule.next_run_at && (
                      <InfoBlock
                        label="下次运行"
                        value={formatTime(patrolSchedule.next_run_at)}
                      />
                    )}
                  </div>

                  {/* 运行历史链接 */}
                  <div className="rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
                    <p className="text-xs text-muted-foreground">
                      点击下方按钮查看巡检历史记录和执行详情
                    </p>
                    <div className="mt-3 flex items-center gap-2">
                      <Button variant="outline" size="sm" asChild>
                        <a href="/tasks?tab=patrol">查看巡检历史</a>
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 系统概览 */}
          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Server className="size-4 text-primary" />
                <CardTitle className="text-base">系统概览</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-2">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <InfoBlock
                  label="健康服务"
                  value={String(healthStatus.services.filter((s) => s.status === "healthy").length)}
                />
                <InfoBlock
                  label="警告服务"
                  value={String(healthStatus.services.filter((s) => s.status === "warning").length)}
                />
                <InfoBlock
                  label="异常服务"
                  value={String(healthStatus.services.filter((s) => s.status === "unhealthy").length)}
                />
                <InfoBlock
                  label="检查时间"
                  value={formatTime(healthStatus.checked_at)}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </AppShell>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-base font-semibold text-foreground">{value}</p>
    </div>
  );
}

function formatTime(value: string): string {
  try {
    const date = new Date(value);
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

async function fetchHealthStatus(signal?: AbortSignal): Promise<{ data: HealthServiceStatus | null; error: { code: string; message: string } | null }> {
  try {
    const response = await fetch(await resolveControlPlaneUrl("/api/v1/health"), {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal,
    });

    if (!response.ok) {
      return {
        data: null,
        error: { code: `http_${response.status}`, message: `健康状态请求失败: ${response.statusText}` },
      };
    }

    const json = await response.json();
    return { data: json.data?.status || json.data || null, error: null };
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return { data: null, error: { code: "request_timeout", message: "请求超时" } };
    }
    return { data: null, error: { code: "network_error", message: error instanceof Error ? error.message : "网络连接失败" } };
  }
}

async function fetchAlerts(signal?: AbortSignal): Promise<{ data: { alerts: AlertItem[] } | null; error: { code: string; message: string } | null }> {
  try {
    const response = await fetch(await resolveControlPlaneUrl("/api/v1/alerts?limit=20"), {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal,
    });

    if (!response.ok) {
      return { data: null, error: { code: `http_${response.status}`, message: `告警请求失败: ${response.statusText}` } };
    }

    const json = await response.json();
    return { data: json.data || { alerts: [] }, error: null };
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return { data: null, error: { code: "request_timeout", message: "请求超时" } };
    }
    return { data: null, error: { code: "network_error", message: error instanceof Error ? error.message : "网络连接失败" } };
  }
}

async function fetchPatrolStatus(signal?: AbortSignal): Promise<{ data: { status: PatrolStatus } | null; error: { code: string; message: string } | null }> {
  try {
    const response = await fetch(await resolveControlPlaneUrl("/api/v1/patrol/status"), {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal,
    });

    if (!response.ok) {
      return { data: null, error: { code: `http_${response.status}`, message: `巡检状态请求失败: ${response.statusText}` } };
    }

    const json = await response.json();
    return { data: json.data || { status: { is_running: false, schedule_enabled: false, interval_minutes: 60 } }, error: null };
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return { data: null, error: { code: "request_timeout", message: "请求超时" } };
    }
    return { data: null, error: { code: "network_error", message: error instanceof Error ? error.message : "网络连接失败" } };
  }
}

async function fetchPatrolSchedule(signal?: AbortSignal): Promise<{ data: { schedule: PatrolSchedule } | null; error: { code: string; message: string } | null }> {
  try {
    const response = await fetch(await resolveControlPlaneUrl("/api/v1/patrol/schedule"), {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal,
    });

    if (!response.ok) {
      return { data: null, error: { code: `http_${response.status}`, message: `巡检计划请求失败: ${response.statusText}` } };
    }

    const json = await response.json();
    return { data: json.data || { schedule: { enabled: false, interval_minutes: 60 } }, error: null };
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return { data: null, error: { code: "request_timeout", message: "请求超时" } };
    }
    return { data: null, error: { code: "network_error", message: error instanceof Error ? error.message : "网络连接失败" } };
  }
}