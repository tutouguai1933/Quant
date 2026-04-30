/* 告警管理面板组件，展示告警级别、静默管理和自动恢复功能。 */
"use client";

import { useState, useEffect } from "react";
import {
  AlertTriangle,
  BellOff,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  Settings,
  Activity,
} from "lucide-react";

import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";

export type AlertLevel = "info" | "warning" | "error" | "critical";

export type AlertCounter = {
  alert_key: string;
  level: AlertLevel;
  count: number;
  first_seen_at: string;
  last_seen_at: string;
  upgraded_at?: string;
  original_level: AlertLevel;
};

export type UpgradeHistoryItem = {
  alert_key: string;
  from_level: AlertLevel;
  to_level: AlertLevel;
  triggered_at: string;
  trigger_count: number;
};

export type SilenceItem = {
  alert_key: string;
  duration_seconds: number;
  started_at: string;
  expires_at: string;
  reason: string;
  remaining_seconds: number;
};

export type RecoveryItem = {
  service_name: string;
  action: string;
  status: "success" | "failed" | "skipped" | "cooling" | "silenced";
  timestamp: string;
  duration_ms: number;
  error?: string;
  details?: Record<string, unknown>;
};

export type ServiceHealth = {
  service_name: string;
  status: string;
  health: string;
  container_id: string;
  healthy: boolean;
  checked_at: string;
  error?: string;
};

const levelConfig: Record<AlertLevel, { variant: "neutral" | "warning" | "danger"; label: string; color: string }> = {
  info: { variant: "neutral", label: "信息", color: "text-muted-foreground" },
  warning: { variant: "warning", label: "警告", color: "text-amber-500" },
  error: { variant: "danger", label: "错误", color: "text-red-500" },
  critical: { variant: "danger", label: "严重", color: "text-red-600 font-bold" },
};

const recoveryStatusConfig: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  success: { icon: CheckCircle2, color: "text-green-500", label: "成功" },
  failed: { icon: XCircle, color: "text-red-500", label: "失败" },
  skipped: { icon: Clock, color: "text-muted-foreground", label: "跳过" },
  cooling: { icon: Clock, color: "text-amber-500", label: "冷却" },
  silenced: { icon: BellOff, color: "text-muted-foreground", label: "静默" },
};

export function AlertManagementPanel() {
  const [counters, setCounters] = useState<Record<string, AlertCounter>>({});
  const [upgradeHistory, setUpgradeHistory] = useState<UpgradeHistoryItem[]>([]);
  const [silences, setSilences] = useState<SilenceItem[]>([]);
  const [recoveryHistory, setRecoveryHistory] = useState<RecoveryItem[]>([]);
  const [servicesHealth, setServicesHealth] = useState<Record<string, ServiceHealth>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [levelsRes, silencesRes, recoveryRes, healthRes] = await Promise.all([
        fetch("/api/v1/alert/level"),
        fetch("/api/v1/alert/silence"),
        fetch("/api/v1/alert/recovery/history?limit=20"),
        fetch("/api/v1/alert/recovery/health"),
      ]);

      if (levelsRes.ok) {
        const data = await levelsRes.json();
        setCounters(data.counters || {});
        setUpgradeHistory(data.upgrade_history || []);
      }

      if (silencesRes.ok) {
        const data = await silencesRes.json();
        setSilences(data.silences || []);
      }

      if (recoveryRes.ok) {
        const data = await recoveryRes.json();
        setRecoveryHistory(data.history || []);
      }

      if (healthRes.ok) {
        const data = await healthRes.json();
        setServicesHealth(data.health?.services || {});
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "获取数据失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleAddSilence = async (alertKey: string, durationSeconds: number) => {
    try {
      const res = await fetch("/api/v1/alert/silence", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_key: alertKey, duration_seconds: durationSeconds, reason: "手动添加" }),
      });
      if (res.ok) fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "添加静默失败");
    }
  };

  const handleRemoveSilence = async (alertKey: string) => {
    try {
      const res = await fetch(`/api/v1/alert/silence/${encodeURIComponent(alertKey)}`, {
        method: "DELETE",
      });
      if (res.ok) fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "移除静默失败");
    }
  };

  const handleManualRecovery = async (serviceName: string) => {
    try {
      const res = await fetch("/api/v1/alert/recovery/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_name: serviceName }),
      });
      if (res.ok) fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "恢复失败");
    }
  };

  const handleResetCounter = async (alertKey: string) => {
    try {
      const res = await fetch(`/api/v1/alert/level/reset?alert_key=${encodeURIComponent(alertKey)}`, {
        method: "POST",
      });
      if (res.ok) fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "重置失败");
    }
  };

  return (
    <div className="grid gap-4">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
          <p className="text-sm text-red-500">{error}</p>
        </div>
      )}

      {/* 服务健康状态 */}
      <Card className="bg-card/90">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity className="size-4 text-primary" />
              <CardTitle className="text-base">服务健康状态</CardTitle>
            </div>
            <Button variant="outline" size="sm" onClick={fetchData} disabled={isLoading}>
              <RefreshCw className={`size-3.5 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
              刷新
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="grid gap-2">
            {Object.entries(servicesHealth).map(([name, health]) => (
              <div key={name} className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className={`size-2 rounded-full ${health.healthy ? "bg-green-500" : "bg-red-500"}`} />
                  <span className="text-sm font-medium">{name}</span>
                  {health.container_id && (
                    <span className="text-xs text-muted-foreground">{health.container_id}</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={health.healthy ? "success" : "danger"}>
                    {health.status}
                  </Badge>
                  {!health.healthy && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleManualRecovery(name)}
                      disabled={isLoading}
                    >
                      <RefreshCw className="size-3 mr-1" />
                      恢复
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 告警级别 */}
      <Card className="bg-card/90">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <ArrowUpRight className="size-4 text-primary" />
            <CardTitle className="text-base">告警级别追踪</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          {Object.keys(counters).length === 0 ? (
            <div className="rounded-lg border border-border/60 bg-muted/30 px-4 py-4 text-center">
              <CheckCircle2 className="mx-auto size-5 text-green-500" />
              <p className="mt-2 text-sm text-muted-foreground">无活跃告警</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {Object.entries(counters).map(([key, counter]) => (
                <li key={key} className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className={`size-4 ${levelConfig[counter.level].color}`} />
                      <div>
                        <p className="text-sm font-medium">{key}</p>
                        <p className="text-xs text-muted-foreground">
                          连续 {counter.count} 次 · {formatTime(counter.last_seen_at)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={levelConfig[counter.level].variant}>
                        {levelConfig[counter.level].label}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleResetCounter(key)}
                      >
                        重置
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* 升级历史 */}
      {upgradeHistory.length > 0 && (
        <Card className="bg-card/90">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <ArrowUpRight className="size-4 text-amber-500" />
              <CardTitle className="text-base">升级历史</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <ul className="space-y-2">
              {upgradeHistory.slice(-5).map((item, idx) => (
                <li key={idx} className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">{item.alert_key}</p>
                      <p className="text-xs text-muted-foreground">
                        {levelConfig[item.from_level].label} → {levelConfig[item.to_level].label}
                        · 连续 {item.trigger_count} 次
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground">{formatTime(item.triggered_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* 告警静默 */}
      <Card className="bg-card/90">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BellOff className="size-4 text-primary" />
              <CardTitle className="text-base">告警静默</CardTitle>
            </div>
            <span className="text-sm text-muted-foreground">{silences.length} 个活跃</span>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          {silences.length === 0 ? (
            <div className="rounded-lg border border-border/60 bg-muted/30 px-4 py-4 text-center">
              <BellOff className="mx-auto size-5 text-muted-foreground" />
              <p className="mt-2 text-sm text-muted-foreground">无活跃静默</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {silences.map((silence) => (
                <li key={silence.alert_key} className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">{silence.alert_key}</p>
                      <p className="text-xs text-muted-foreground">
                        剩余 {Math.floor(silence.remaining_seconds / 60)} 分钟
                        {silence.reason && ` · ${silence.reason}`}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveSilence(silence.alert_key)}
                    >
                      移除
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* 恢复历史 */}
      <Card className="bg-card/90">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <RefreshCw className="size-4 text-primary" />
            <CardTitle className="text-base">恢复历史</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          {recoveryHistory.length === 0 ? (
            <div className="rounded-lg border border-border/60 bg-muted/30 px-4 py-4 text-center">
              <RefreshCw className="mx-auto size-5 text-muted-foreground" />
              <p className="mt-2 text-sm text-muted-foreground">无恢复记录</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {recoveryHistory.slice(-10).map((item, idx) => {
                const config = recoveryStatusConfig[item.status] || recoveryStatusConfig.skipped;
                const IconComponent = config.icon;
                return (
                  <li key={idx} className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <IconComponent className={`size-4 ${config.color}`} />
                        <div>
                          <p className="text-sm font-medium">{item.service_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {config.label} · {item.duration_ms}ms
                            {item.error && ` · ${item.error}`}
                          </p>
                        </div>
                      </div>
                      <span className="text-xs text-muted-foreground">{formatTime(item.timestamp)}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function formatTime(value: string): string {
  try {
    const date = new Date(value);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);

    if (diffMins < 1) return "刚刚";
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;

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

export function AlertManagementSkeleton() {
  return (
    <div className="grid gap-4">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i} className="bg-card/90">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div className="size-4 rounded bg-muted/40 animate-pulse" />
              <div className="h-5 w-24 rounded bg-muted/40 animate-pulse" />
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="grid gap-2">
              {[1, 2].map((j) => (
                <div key={j} className="h-10 rounded-lg bg-muted/20 animate-pulse" />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}