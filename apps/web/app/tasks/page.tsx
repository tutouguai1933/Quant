/* 任务与自动化控制台：精简版 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { LoadingBanner } from "../../components/loading-banner";
import { ArbitrationHandoffCard } from "../../components/arbitration-handoff-card";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { OpenclawActionConfirmDialog } from "../../components/openclaw-action-confirm-dialog";
import { PageHero } from "../../components/page-hero";
import { StatusBar } from "../../components/status-bar";
import { StatusBadge } from "../../components/status-badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { readFeedback } from "../../lib/feedback";
import {
  DEFAULT_API_TIMEOUT,
  getAutomationStatus,
  getAutomationStatusFallback,
  getOpenclawSnapshot,
  getOpenclawAuditRecords,
  getOpenclawPatrolHistory,
  listTasks,
} from "../../lib/api";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default function TasksPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [automation, setAutomation] = useState<Record<string, unknown>>(getAutomationStatusFallback().item);
  const [openclawSnapshot, setOpenclawSnapshot] = useState<Record<string, unknown>>({});
  const [openclawAuditRecords, setOpenclawAuditRecords] = useState<Array<Record<string, unknown>>>([]);
  const [openclawPatrolHistory, setOpenclawPatrolHistory] = useState<Array<Record<string, unknown>>>([]);
  const [isLoading, setIsLoading] = useState(true);

  // 确认弹窗状态
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    action: string;
    label: string;
    riskLevel: "safe" | "medium" | "danger" | "critical";
  } | null>(null);

  // 动作风险等级映射
  const getActionRiskLevel = (action: string): "safe" | "medium" | "danger" | "critical" => {
    if (action === "automation_clear_non_error_alerts" || action === "automation_confirm_alert") {
      return "safe";
    }
    if (action === "automation_run_cycle" || action === "automation_dry_run_only") {
      return "medium";
    }
    if (action.startsWith("system_restart_")) {
      return "danger";
    }
    return "medium";
  };

  const openConfirmDialog = (action: string, label: string) => {
    setConfirmDialog({
      open: true,
      action,
      label,
      riskLevel: getActionRiskLevel(action),
    });
  };

  const closeConfirmDialog = () => {
    setConfirmDialog(null);
  };

  const executeAction = () => {
    if (confirmDialog) {
      router.push(`/actions?action=${confirmDialog.action}&returnTo=/tasks`);
    }
  };

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

  useEffect(() => {
    if (!session.token) {
      setIsLoading(false);
      return;
    }

    Promise.all([
      safeLoad((signal) => listTasks(session.token!, signal), []),
      safeLoad(
        async (signal) => {
          const response = await getAutomationStatus(session.token!, signal);
          return { data: { items: [response.data.item] }, error: response.error };
        },
        [],
      ),
      safeLoadSnapshot((signal) => getOpenclawSnapshot(session.token!, signal), {}),
      safeLoadAudit((signal) => getOpenclawAuditRecords(signal), []),
      safeLoadPatrol((signal) => getOpenclawPatrolHistory(signal), []),
    ])
      .then(([tasksResult, automationResult, openclawResult, auditResult, patrolResult]) => {
        setItems(tasksResult);
        const automationData = (automationResult[0] as Record<string, unknown>) ?? getAutomationStatusFallback().item;
        setAutomation(automationData);
        setOpenclawSnapshot(openclawResult);
        setOpenclawAuditRecords(auditResult);
        setOpenclawPatrolHistory(patrolResult);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  }, [session.token]);

  const arbitration = asRecord(automation.arbitration);
  const lastCycle = asRecord(automation.lastCycle);
  const recoveryReview = asRecord(automation.recoveryReview);
  const runtimeGuard = asRecord(automation.runtimeGuard);
  const dailySummary = asRecord(automation.dailySummary);

  const automationMode = readText(automation.mode, "manual");
  const isPaused = Boolean(automation.paused);
  const isManualTakeover = Boolean(automation.manualTakeover);
  const lastCycleStatus = readText(lastCycle.status, "waiting");
  const lastCycleMessage = readText(lastCycle.message, "暂无周期信息");

  const recoveryStatus = readText(recoveryReview.status, "unknown");
  const recoveryHeadline = readText(recoveryReview.headline, "当前可以继续自动化");
  const recoveryDetail = readText(recoveryReview.detail, "");
  const recoveryNextAction = readText(recoveryReview.next_action, "");
  const recoveryBlockers = Array.isArray(recoveryReview.blockers)
    ? recoveryReview.blockers.map((item) => readText(asRecord(item).label, ""))
    : [];
  const recoveryOperatorSteps = Array.isArray(recoveryReview.operator_steps)
    ? recoveryReview.operator_steps.map((item) => readText(typeof item === "string" ? item : asRecord(item).step ?? "", ""))
    : [];
  const recoveryAutoRecoverable = recoveryReview.auto_recoverable;
  const recoveryManualRequiredReason = readText(recoveryReview.manual_required_reason, "");

  const runtimeStatus = readText(runtimeGuard.status, "unknown");
  const runtimeHeadline = readText(runtimeGuard.headline, "当前运行正常");
  const runtimeDetail = readText(runtimeGuard.detail, "");
  const degradeMode = readText(runtimeGuard.degrade_mode, "none");
  const runtimeReasonLabel = readText(runtimeGuard.reason_label, "");
  const runtimeAlertContext = asRecord(runtimeGuard.alert_context);
  const takeoverReviewDueAt = readText(runtimeGuard.takeover_review_due_at, "");
  const cooldownEndsAt = readText(runtimeGuard.cooldown_ends_at, "");
  const lastCycleAt = readText(runtimeGuard.last_cycle_at, "");
  const degradeReason = readText(runtimeGuard.degrade_reason, "");
  // 新增 runtime_guard 字段
  const runtimeBlockersFull = Array.isArray(runtimeGuard.blockers)
    ? runtimeGuard.blockers.map((item) => {
        const blocker = asRecord(item);
        return {
          code: readText(blocker.code, ""),
          label: readText(blocker.label, ""),
          severity: readText(blocker.severity, "info"),
        };
      })
    : [];
  const runtimeBlockers = runtimeBlockersFull.map((b) => b.label);
  const runtimeSuggestedAction = readText(runtimeGuard.suggested_action, "");
  const runtimeSuggestedActionReason = readText(runtimeGuard.suggested_action_reason, "");
  const runtimeAutoRunAllowed = runtimeGuard.auto_run_allowed;
  const runtimeCyclesToday = Number(runtimeGuard.cycles_today ?? 0);

  const cycleCount = Number(dailySummary.cycle_count ?? 0);
  const successCount = Number(dailySummary.success_count ?? 0);
  const failureCount = Number(dailySummary.failure_count ?? 0);

  const openclawOverallStatus = readText(openclawSnapshot?.overall_status, "unknown");
  const openclawAllowedActions = Array.isArray(openclawSnapshot?.allowed_safe_actions)
    ? openclawSnapshot.allowed_safe_actions.map((item) => asRecord(item))
    : [];
  const openclawRuntimeGuard = asRecord(openclawSnapshot?.runtime_guard);
  const openclawReadyForCycle = Boolean(openclawRuntimeGuard?.ready_for_cycle);
  const openclawBlockedReason = readText(openclawRuntimeGuard?.blocked_reason, "");
  const openclawDegradeMode = readText(openclawSnapshot?.degrade_mode, "none");
  const openclawSuggestedAction = asRecord(openclawSnapshot?.suggested_action);
  const openclawSuggestedActionName = readText(openclawSuggestedAction?.action, "");
  const openclawSuggestedActionReason = readText(openclawSuggestedAction?.reason, "");
  const openclawAutoRunAllowed = Boolean(openclawSuggestedAction?.auto_run_allowed);

  const statusItems = [
    {
      label: "自动化模式",
      value: isManualTakeover ? "人工接管" : isPaused ? "已暂停" : automationMode,
      status: (isManualTakeover || isPaused ? "waiting" : "active") as "waiting" | "active",
      detail: isManualTakeover ? "接管中" : isPaused ? "已暂停" : "运行中",
    },
    {
      label: "最近一轮",
      value: lastCycleStatus,
      status: (lastCycleStatus === "success" ? "success" : lastCycleStatus === "error" ? "error" : "waiting") as "success" | "error" | "waiting",
      detail: lastCycleMessage,
    },
    {
      label: "今日周期",
      value: `${cycleCount} 轮`,
      status: (cycleCount > 0 ? "active" : "waiting") as "active" | "waiting",
      detail: `成功 ${successCount} / 失败 ${failureCount}`,
    },
    {
      label: "恢复状态",
      value: recoveryStatus === "ready" ? "可恢复" : recoveryStatus === "attention_required" ? "需处理" : "等待中",
      status: (recoveryStatus === "ready" ? "success" : recoveryStatus === "attention_required" ? "error" : "waiting") as "success" | "error" | "waiting",
      detail: recoveryHeadline,
    },
  ];

  return (
    <AppShell
      title="任务"
      subtitle="自动化监控与恢复操作入口。"
      currentPath="/tasks"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      {isLoading && <LoadingBanner />}

      <PageHero
        badge="自动化控制台"
        title="先看状态，再决定要不要干预"
        description="任务页只回答三件事：当前自动化在什么状态、有没有阻塞、需要什么操作。"
      />

      <ArbitrationHandoffCard
        arbitration={arbitration}
        isAuthenticated={session.isAuthenticated}
        surfaceLabel="任务页"
        showActions={!session.isAuthenticated}
      />

      {!session.isAuthenticated ? (
        <Card>
          <CardHeader>
            <p className="eyebrow">动作反馈</p>
            <CardTitle>当前页面需要登录</CardTitle>
            <CardDescription>登录后才能看到真实自动化状态和控制动作。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="terminal">
              <Link href="/login?next=%2Ftasks">先去登录</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <StatusBar items={statusItems} />

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <p className="eyebrow">当前恢复建议</p>
                <CardTitle>{recoveryHeadline}</CardTitle>
                <CardDescription>{recoveryDetail}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                <p>恢复状态：{recoveryStatus}</p>
                <p>下一步动作：{recoveryNextAction || "当前可以继续自动化"}</p>
                {recoveryBlockers.length > 0 ? (
                  <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">当前阻塞</p>
                    <ul className="mt-2 space-y-1 text-sm">
                      {recoveryBlockers.map((blocker, idx) => (
                        <li key={idx}>• {blocker}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {recoveryOperatorSteps.length > 0 ? (
                  <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">恢复步骤清单</p>
                    <ol className="mt-2 space-y-1 text-sm list-decimal list-inside">
                      {recoveryOperatorSteps.map((step, idx) => (
                        <li key={idx}>{step}</li>
                      ))}
                    </ol>
                  </div>
                ) : null}
                <div className="flex items-center gap-2">
                  <span>自动恢复：</span>
                  {recoveryAutoRecoverable === true ? (
                    <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">可自动恢复</span>
                  ) : recoveryAutoRecoverable === false ? (
                    <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/30 dark:text-red-400">需人工处理</span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-800 dark:bg-gray-800 dark:text-gray-300">未知</span>
                  )}
                </div>
                {recoveryAutoRecoverable === false && recoveryManualRequiredReason ? (
                  <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3">
                    <p className="font-medium text-red-600 dark:text-red-400">必须人工处理</p>
                    <p className="mt-1 text-red-600/80 dark:text-red-400/80">{recoveryManualRequiredReason}</p>
                  </div>
                ) : null}
                {recoveryStatus === "attention_required" ? (
                  <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-3">
                    <p className="font-medium text-yellow-600 dark:text-yellow-400">需要人工处理</p>
                    <p className="mt-1 text-yellow-600/80 dark:text-yellow-400/80">{recoveryDetail}</p>
                  </div>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  当前原因、告警升级和接管复核时间统一在长期运行状态卡片查看。
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <p className="eyebrow">长期运行状态</p>
                <CardTitle>{runtimeHeadline}</CardTitle>
                <CardDescription>{runtimeDetail}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                <p>运行状态：{runtimeStatus}</p>
                <p>运行模式：{degradeMode === "none" ? "完全自动" : degradeMode === "manual_only" ? "手动控制" : degradeMode === "window_wait" ? "等待窗口" : degradeMode}</p>
                {degradeReason ? <p>模式原因：{degradeReason}</p> : null}
                {runtimeReasonLabel ? <p>当前原因：{runtimeReasonLabel}</p> : null}
                {takeoverReviewDueAt ? <p>接管复核截止：{takeoverReviewDueAt}</p> : null}
                {cooldownEndsAt ? <p>冷却结束时间：{cooldownEndsAt}</p> : null}
                {lastCycleAt ? <p>上一周期结束：{lastCycleAt}</p> : null}
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">今日周期数</p>
                    <p className="mt-2 text-lg font-semibold text-foreground">{runtimeCyclesToday}</p>
                  </div>
                  <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">自动运行</p>
                    <p className="mt-2 text-lg font-semibold">
                      {runtimeAutoRunAllowed === true ? (
                        <span className="text-green-600 dark:text-green-400">允许</span>
                      ) : runtimeAutoRunAllowed === false ? (
                        <span className="text-red-600 dark:text-red-400">禁止</span>
                      ) : (
                        <span className="text-muted-foreground">未知</span>
                      )}
                    </p>
                  </div>
                </div>
                {runtimeBlockersFull.length > 0 ? (
                  <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">阻塞列表</p>
                    <ul className="mt-2 space-y-1 text-sm">
                      {runtimeBlockersFull.map((blocker, idx) => (
                        <li key={idx} className="flex items-center gap-2">
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            blocker.severity === "error" ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                            : blocker.severity === "warning" ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                            : "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400"
                          }`}>
                            {blocker.severity}
                          </span>
                          <span>{blocker.label}</span>
                          {blocker.code ? <span className="text-muted-foreground text-xs">({blocker.code})</span> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {runtimeSuggestedAction ? (
                  <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">程序建议动作</p>
                    <div className="mt-2 flex items-center gap-2">
                      <span className="inline-flex items-center rounded-md bg-blue-600 px-2.5 py-1 text-sm font-semibold text-white">{runtimeSuggestedAction}</span>
                    </div>
                    {runtimeSuggestedActionReason ? (
                      <p className="mt-2 text-sm text-blue-600/80 dark:text-blue-400/80">原因：{runtimeSuggestedActionReason}</p>
                    ) : null}
                  </div>
                ) : null}
                {runtimeStatus === "attention_required" || runtimeStatus === "degraded" ? (
                  <div className="rounded-lg border border-orange-500/20 bg-orange-500/10 p-3">
                    <p className="font-medium text-orange-600 dark:text-orange-400">运行异常</p>
                    <p className="mt-1 text-orange-600/80 dark:text-orange-400/80">{runtimeDetail}</p>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <p className="eyebrow">最近一轮</p>
              <CardTitle>最近自动化周期</CardTitle>
              <CardDescription>
                状态：{lastCycleStatus} / 今日已运行 {cycleCount} 轮
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              <p>{lastCycleMessage}</p>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">今日周期</p>
                  <p className="mt-2 text-lg font-semibold text-foreground">{cycleCount}</p>
                </div>
                <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">成功</p>
                  <p className="mt-2 text-lg font-semibold text-green-600 dark:text-green-400">{successCount}</p>
                </div>
                <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">失败</p>
                  <p className="mt-2 text-lg font-semibold text-red-600 dark:text-red-400">{failureCount}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <p className="eyebrow">定时巡检</p>
              <CardTitle>OpenClaw 运维巡检</CardTitle>
              <CardDescription>
                最近巡检状态和动作记录
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {openclawPatrolHistory.length > 0 ? (
                <>
                  {(() => {
                    const latestPatrol = asRecord(openclawPatrolHistory[0]);
                    const patrolStatus = readText(latestPatrol.status, "unknown");
                    const patrolMessage = readText(latestPatrol.message, "");
                    const patrolType = readText(latestPatrol.patrol_type, "");
                    const executedAt = readText(latestPatrol.executed_at, "");
                    const actionsTaken = Array.isArray(latestPatrol.actions_taken) ? latestPatrol.actions_taken : [];
                    return (
                      <>
                        <div className="flex items-center gap-2">
                          <span>状态：</span>
                          <StatusBadge value={patrolStatus === "normal" ? "正常" : patrolStatus === "action_taken" ? "已执行动作" : patrolStatus === "throttled" ? "已节流" : patrolStatus} />
                        </div>
                        {patrolMessage ? <p>{patrolMessage}</p> : null}
                        {executedAt ? <p className="text-xs text-muted-foreground">执行时间：{executedAt}</p> : null}
                        {actionsTaken.length > 0 ? (
                          <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">执行动作</p>
                            <ul className="mt-2 space-y-1 text-sm">
                              {actionsTaken.slice(0, 3).map((action, idx) => {
                                const actionRecord = asRecord(action);
                                const actionName = readText(actionRecord.action, "");
                                const actionSuccess = Boolean(actionRecord.success);
                                return (
                                  <li key={idx} className="flex items-center gap-2">
                                    <span className={`inline-flex h-2 w-2 rounded-full ${actionSuccess ? "bg-green-500" : "bg-red-500"}`} />
                                    <span className="font-medium">{actionName}</span>
                                    <span className={actionSuccess ? "text-green-600" : "text-red-600"}>{actionSuccess ? "成功" : "失败"}</span>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        ) : null}
                      </>
                    );
                  })()}
                </>
              ) : (
                <p className="text-muted-foreground">暂无巡检记录</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <p className="eyebrow">Openclaw 安全动作</p>
              <CardTitle>统一动作网关</CardTitle>
              <CardDescription>
                当前状态：{openclawOverallStatus} / 可执行周期：{openclawReadyForCycle ? "是" : "否"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              <p>运行时守卫：{openclawReadyForCycle ? "就绪" : "阻塞中"}</p>
              {openclawBlockedReason ? <p>阻塞原因：{openclawBlockedReason}</p> : null}
              <p>运行模式：{openclawDegradeMode === "none" ? "完全自动" : openclawDegradeMode === "manual_only" ? "手动控制" : openclawDegradeMode}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">自动运行</p>
                  <p className="mt-2 text-lg font-semibold">
                    {openclawAutoRunAllowed ? (
                      <span className="text-green-600 dark:text-green-400">允许</span>
                    ) : (
                      <span className="text-red-600 dark:text-red-400">禁止</span>
                    )}
                  </p>
                </div>
                <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">程序建议</p>
                  <p className="mt-2 text-sm font-medium">{openclawSuggestedActionName || "暂无建议"}</p>
                  {openclawSuggestedActionReason ? (
                    <p className="text-xs text-muted-foreground">{openclawSuggestedActionReason}</p>
                  ) : null}
                </div>
              </div>
              {openclawAllowedActions.length > 0 ? (
                <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">可用动作</p>
                  <ul className="mt-2 space-y-1 text-sm">
                    {openclawAllowedActions.map((action, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <span className="font-medium">{readText(action.action, "")}</span>
                        {action.reason ? <span className="text-muted-foreground"> - {readText(action.reason, "")}</span> : null}
                        <div className="flex items-center gap-1 ml-2">
                          {action.auto_execute !== undefined ? (
                            <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs ${Boolean(action.auto_execute) ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400" : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"}`}>
                              {Boolean(action.auto_execute) ? "自动" : "需确认"}
                            </span>
                          ) : null}
                          {action.priority !== undefined ? (
                            <span className="inline-flex items-center rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                              P{Number(action.priority)}
                            </span>
                          ) : null}
                          {action.preconditions_met !== undefined ? (
                            <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs ${Boolean(action.preconditions_met) ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
                              {Boolean(action.preconditions_met) ? "可执行" : "前置条件不满足"}
                            </span>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-muted-foreground">当前没有可用的安全动作</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <p className="eyebrow">动作历史</p>
              <CardTitle>OpenClaw 运维动作</CardTitle>
              <CardDescription>展示最近 5 条动作记录</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {openclawAuditRecords.length > 0 ? (
                <div className="space-y-2">
                  {openclawAuditRecords.slice(0, 5).map((record, idx) => {
                    const actionName = readText(record.action, "未知动作");
                    const success = Boolean(record.success);
                    const executedAt = readText(record.executed_at || record.recorded_at, "");
                    const reason = readText(record.reason || "", "");
                    return (
                      <div key={idx} className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/30 p-2">
                        <div className="flex items-center gap-2">
                          <span className={`inline-flex h-2 w-2 rounded-full ${success ? "bg-green-500" : "bg-red-500"}`} />
                          <span className="font-medium">{actionName}</span>
                        </div>
                        <div className="text-right">
                          <span className={success ? "text-green-600" : "text-red-600"}>{success ? "成功" : "失败"}</span>
                          {executedAt ? <span className="ml-2 text-muted-foreground text-xs">{executedAt}</span> : null}
                        </div>
                        {reason ? <p className="text-xs text-muted-foreground mt-1">{reason}</p> : null}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-muted-foreground">暂无动作记录</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <p className="eyebrow">控制动作</p>
              <CardTitle>自动化控制</CardTitle>
              <CardDescription>恢复、暂停、切换模式等操作。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button variant="terminal" size="sm" onClick={() => openConfirmDialog("automation_resume", "恢复自动化")}>
                恢复自动化
              </Button>
              <Button variant="outline" size="sm" onClick={() => openConfirmDialog("automation_pause", "暂停自动化")}>
                暂停自动化
              </Button>
              <Button variant="outline" size="sm" onClick={() => openConfirmDialog("automation_run_cycle", "运行一轮")}>
                运行一轮
              </Button>
              <Button variant="secondary" size="sm" onClick={() => openConfirmDialog("automation_dry_run_only", "切换到 dry-run")}>
                切换到 dry-run
              </Button>
            </CardContent>
          </Card>

          {confirmDialog?.open && (
            <OpenclawActionConfirmDialog
              action={confirmDialog.action}
              label={confirmDialog.label}
              riskLevel={confirmDialog.riskLevel}
              onConfirm={executeAction}
              onCancel={closeConfirmDialog}
            />
          )}

          <Card>
            <CardHeader>
              <p className="eyebrow">任务记录</p>
              <CardTitle>最近任务</CardTitle>
              <CardDescription>展示最近 3 条任务摘要。</CardDescription>
            </CardHeader>
            <CardContent>
              <DataTable
                columns={["任务", "状态", "创建时间", "完成时间"]}
                rows={items.slice(0, 3).map((item, index) => ({
                  id: String(item.id ?? index),
                  cells: [
                    String(item.task_type ?? "unknown"),
                    <StatusBadge key={String(item.id ?? index)} value={String(item.status ?? "pending")} />,
                    String(item.created_at ?? ""),
                    String(item.finished_at ?? ""),
                  ],
                }))}
                emptyTitle="当前还没有任务"
                emptyDetail="运行后产生"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <p className="eyebrow">相关页面</p>
              <CardTitle>跨页入口</CardTitle>
              <CardDescription>回到其他工作台查看详细信息。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link href="/">回到首页</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/strategies">策略中心</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/evaluation">评估中心</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/research">研究工作台</Link>
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </AppShell>
  );
}

function readText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function createTimeoutController(timeoutMs: number) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cleanup: () => clearTimeout(timeoutId),
  };
}

async function safeLoad<T>(
  loader: (signal: AbortSignal) => Promise<{ data: { items: T[] }; error: unknown }>,
  fallback: T[],
  timeoutMs = DEFAULT_API_TIMEOUT,
): Promise<T[]> {
  const { signal, cleanup } = createTimeoutController(timeoutMs);
  try {
    const response = await loader(signal);
    return response.error ? fallback : response.data.items;
  } catch {
    return fallback;
  } finally {
    cleanup();
  }
}

async function safeLoadItem<T>(
  loader: (signal: AbortSignal) => Promise<{ data: T; error: unknown }>,
  fallback: T,
  timeoutMs = DEFAULT_API_TIMEOUT,
): Promise<T> {
  const { signal, cleanup } = createTimeoutController(timeoutMs);
  try {
    const response = await loader(signal);
    return response.error ? fallback : response.data;
  } catch {
    return fallback;
  } finally {
    cleanup();
  }
}

async function safeLoadSnapshot(
  loader: (signal: AbortSignal) => Promise<{ data: { snapshot: Record<string, unknown> }; error: unknown }>,
  fallback: Record<string, unknown>,
  timeoutMs = DEFAULT_API_TIMEOUT,
): Promise<Record<string, unknown>> {
  const { signal, cleanup } = createTimeoutController(timeoutMs);
  try {
    const response = await loader(signal);
    return response.error ? fallback : response.data.snapshot;
  } catch {
    return fallback;
  } finally {
    cleanup();
  }
}

async function safeLoadAudit(
  loader: (signal: AbortSignal) => Promise<{ data: { items: Array<Record<string, unknown>> }; error: unknown }>,
  fallback: Array<Record<string, unknown>>,
  timeoutMs = DEFAULT_API_TIMEOUT,
): Promise<Array<Record<string, unknown>>> {
  const { signal, cleanup } = createTimeoutController(timeoutMs);
  try {
    const response = await loader(signal);
    return response.error ? fallback : response.data.items;
  } catch {
    return fallback;
  } finally {
    cleanup();
  }
}

async function safeLoadPatrol(
  loader: (signal: AbortSignal) => Promise<{ data: { items: Array<Record<string, unknown>> }; error: unknown }>,
  fallback: Array<Record<string, unknown>>,
  timeoutMs = DEFAULT_API_TIMEOUT,
): Promise<Array<Record<string, unknown>>> {
  const { signal, cleanup } = createTimeoutController(timeoutMs);
  try {
    const response = await loader(signal);
    return response.error ? fallback : response.data.items;
  } catch {
    return fallback;
  } finally {
    cleanup();
  }
}
