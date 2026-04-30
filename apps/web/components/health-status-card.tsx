/* 服务健康状态卡片组件，展示服务运行状态和响应时间。 */
"use client";

import { Activity, Clock, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export type HealthStatus = "healthy" | "unhealthy" | "warning";

export type HealthStatusCardProps = {
  serviceName: string;
  status: HealthStatus;
  responseTime?: number;
  lastCheck: string;
  detail?: string;
};

const statusConfig: Record<HealthStatus, { color: string; bgColor: string; icon: typeof CheckCircle2; label: string }> = {
  healthy: { color: "text-green-500", bgColor: "bg-green-500", icon: CheckCircle2, label: "运行正常" },
  unhealthy: { color: "text-red-500", bgColor: "bg-red-500", icon: XCircle, label: "异常" },
  warning: { color: "text-amber-500", bgColor: "bg-amber-500", icon: AlertTriangle, label: "警告" },
};

export function HealthStatusCard({ serviceName, status, responseTime, lastCheck, detail }: HealthStatusCardProps) {
  const config = statusConfig[status];
  const IconComponent = config.icon;

  return (
    <Card className="bg-card/90">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="size-4 text-primary" />
            <CardTitle className="text-base">{serviceName}</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <span className={`size-2.5 rounded-full ${config.bgColor}`} />
            <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="grid gap-2 text-sm">
          {responseTime !== undefined && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">响应时间</span>
              <span className={`font-medium ${responseTime < 200 ? "text-green-500" : responseTime < 500 ? "text-amber-500" : "text-red-500"}`}>
                {responseTime}ms
              </span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">最近检查</span>
            <span className="text-foreground">{formatTime(lastCheck)}</span>
          </div>
          {detail && (
            <div className="mt-2 rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
              <p className="text-xs text-muted-foreground">{detail}</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
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
      second: "2-digit",
    });
  } catch {
    return value;
  }
}

export function HealthStatusSkeleton() {
  return (
    <Card className="bg-card/90">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="size-4 text-muted" />
            <div className="h-5 w-24 rounded bg-muted/40 animate-pulse" />
          </div>
          <div className="flex items-center gap-2">
            <div className="size-2.5 rounded-full bg-muted/40 animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted/40 animate-pulse" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="grid gap-2">
          <div className="flex items-center justify-between">
            <div className="h-4 w-16 rounded bg-muted/40 animate-pulse" />
            <div className="h-4 w-12 rounded bg-muted/40 animate-pulse" />
          </div>
          <div className="flex items-center justify-between">
            <div className="h-4 w-16 rounded bg-muted/40 animate-pulse" />
            <div className="h-4 w-20 rounded bg-muted/40 animate-pulse" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function getHealthStatusFallback(): HealthServiceStatus {
  return {
    services: [
      { name: "数据引擎", status: "healthy", response_time: 120, last_check: new Date().toISOString(), detail: "K线数据正常同步" },
      { name: "研究引擎", status: "healthy", response_time: 85, last_check: new Date().toISOString(), detail: "模型推理正常" },
      { name: "执行引擎", status: "healthy", response_time: 45, last_check: new Date().toISOString(), detail: "订单执行正常" },
      { name: "风控引擎", status: "healthy", response_time: 30, last_check: new Date().toISOString(), detail: "风险监控正常" },
    ],
    overall_status: "healthy",
    checked_at: new Date().toISOString(),
  };
}

export type HealthServiceItem = {
  name: string;
  status: HealthStatus;
  response_time?: number;
  last_check: string;
  detail?: string;
};

export type HealthServiceStatus = {
  services: HealthServiceItem[];
  overall_status: HealthStatus;
  checked_at: string;
};