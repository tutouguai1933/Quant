/**
 * 任务与自动化控制台
 * 终端风格重构
 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";

import {
  TerminalShell,
  TerminalCard,
  MetricStrip,
} from "../../components/terminal";
import { LoadingBanner } from "../../components/loading-banner";
import { ArbitrationHandoffCard } from "../../components/arbitration-handoff-card";
import { FeedbackBanner } from "../../components/feedback-banner";
import { OpenclawActionConfirmDialog } from "../../components/openclaw-action-confirm-dialog";
import { StatusBadge } from "../../components/status-badge";
import { Button } from "../../components/ui/button";
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

  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    action: string;
    label: string;
    riskLevel: "safe" | "medium" | "danger" | "critical";
  } | null>(null);

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
      .catch(() => {});
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
  const takeoverReviewDueAt = readText(runtimeGuard.takeover_review_due_at, "");
  const cooldownEndsAt = readText(runtimeGuard.cooldown_ends_at, "");
  const lastCycleAt = readText(runtimeGuard.last_cycle_at, "");
  const degradeReason = readText(runtimeGuard.degrade_reason, "");
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

  const statusMetrics = [
    {
      label: "自动化模式",
      value: isManualTakeover ? "人工接管" : isPaused ? "已暂停" : automationMode,
      colorType: isManualTakeover || isPaused ? ("neutral" as const) : ("positive" as const),
    },
    {
      label: "最近一轮",
      value: lastCycleStatus,
      colorType: lastCycleStatus === "success" ? ("positive" as const) : lastCycleStatus === "error" ? ("negative" as const) : ("neutral" as const),
    },
    {
      label: "今日周期",
      value: `${cycleCount} 轮`,
      colorType: cycleCount > 0 ? ("positive" as const) : ("neutral" as const),
    },
    {
      label: "恢复状态",
      value: recoveryStatus === "ready" ? "可恢复" : recoveryStatus === "attention_required" ? "需处理" : "等待中",
      colorType: recoveryStatus === "ready" ? ("positive" as const) : recoveryStatus === "attention_required" ? ("negative" as const) : ("neutral" as const),
    },
  ];

  return (
    <TerminalShell
      breadcrumb="运维 / 任务"
      title="任务"
      subtitle="自动化监控与恢复操作入口"
      currentPath="/tasks"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      {isLoading && <LoadingBanner />}

      <ArbitrationHandoffCard
        arbitration={arbitration}
        isAuthenticated={session.isAuthenticated}
        surfaceLabel="任务页"
        showActions={!session.isAuthenticated}
      />

      {!session.isAuthenticated ? (
        <TerminalCard title="需要登录">
          <div className="space-y-3">
            <p className="text-sm text-[var(--terminal-muted)]">登录后才能看到真实自动化状态和控制动作。</p>
            <Button asChild variant="terminal">
              <Link href="/login?next=%2Ftasks">先去登录</Link>
            </Button>
          </div>
        </TerminalCard>
      ) : (
        <>
          <MetricStrip metrics={statusMetrics} />

          <div className="grid gap-4 lg:grid-cols-2">
            {/* 当前恢复建议 */}
            <TerminalCard title={recoveryHeadline}>
              <div className="space-y-3 text-sm">
                <p className="text-[var(--terminal-muted)]">{recoveryDetail}</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <InfoBlock label="恢复状态" value={recoveryStatus} />
                  <InfoBlock label="下一步动作" value={recoveryNextAction || "当前可以继续自动化"} />
                </div>
                {recoveryBlockers.length > 0 && (
                  <div className="rounded border border-[var(--terminal-border)] p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">当前阻塞</p>
                    <ul className="mt-2 space-y-1 text-xs">
                      {recoveryBlockers.map((blocker, idx) => (
                        <li key={idx} className="text-[var(--terminal-text)]">• {blocker}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {recoveryOperatorSteps.length > 0 && (
                  <div className="rounded border border-[var(--terminal-border)] p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">恢复步骤清单</p>
                    <ol className="mt-2 space-y-1 text-xs list-decimal list-inside">
                      {recoveryOperatorSteps.map((step, idx) => (
                        <li key={idx} className="text-[var(--terminal-text)]">{step}</li>
                      ))}
                    </ol>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[var(--terminal-muted)]">自动恢复：</span>
                  {recoveryAutoRecoverable === true ? (
                    <span className="text-xs text-[var(--terminal-green)]">可自动恢复</span>
                  ) : recoveryAutoRecoverable === false ? (
                    <span className="text-xs text-[var(--terminal-red)]">需人工处理</span>
                  ) : (
                    <span className="text-xs text-[var(--terminal-muted)]">未知</span>
                  )}
                </div>
              </div>
            </TerminalCard>

            {/* 长期运行状态 */}
            <TerminalCard title={runtimeHeadline}>
              <div className="space-y-3 text-sm">
                <p className="text-[var(--terminal-muted)]">{runtimeDetail}</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <InfoBlock label="运行状态" value={runtimeStatus} />
                  <InfoBlock label="运行模式" value={degradeMode === "none" ? "完全自动" : degradeMode === "manual_only" ? "手动控制" : degradeMode} />
                </div>
                {degradeReason && <p className="text-xs text-[var(--terminal-muted)]">模式原因：{degradeReason}</p>}
                {takeoverReviewDueAt && <p className="text-xs text-[var(--terminal-muted)]">接管复核截止：{takeoverReviewDueAt}</p>}
                {cooldownEndsAt && <p className="text-xs text-[var(--terminal-muted)]">冷却结束时间：{cooldownEndsAt}</p>}
                {lastCycleAt && <p className="text-xs text-[var(--terminal-muted)]">上一周期结束：{lastCycleAt}</p>}
                <div className="grid gap-2 sm:grid-cols-2">
                  <InfoBlock label="今日周期数" value={String(runtimeCyclesToday)} />
                  <InfoBlock label="自动运行" value={runtimeAutoRunAllowed === true ? "允许" : runtimeAutoRunAllowed === false ? "禁止" : "未知"} />
                </div>
                {runtimeBlockersFull.length > 0 && (
                  <div className="rounded border border-[var(--terminal-border)] p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">阻塞列表</p>
                    <ul className="mt-2 space-y-1 text-xs">
                      {runtimeBlockersFull.map((blocker, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-[var(--terminal-text)]">
                          <span className={`text-xs ${blocker.severity === "error" ? "text-[var(--terminal-red)]" : blocker.severity === "warning" ? "text-[var(--terminal-yellow)]" : "text-[var(--terminal-accent)]"}`}>
                            [{blocker.severity}]
                          </span>
                          <span>{blocker.label}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {runtimeSuggestedAction && (
                  <div className="rounded border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10 p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-accent)]">程序建议动作</p>
                    <p className="mt-1 text-sm text-[var(--terminal-text)]">{runtimeSuggestedAction}</p>
                    {runtimeSuggestedActionReason && (
                      <p className="mt-1 text-xs text-[var(--terminal-muted)]">原因：{runtimeSuggestedActionReason}</p>
                    )}
                  </div>
                )}
              </div>
            </TerminalCard>
          </div>

          {/* 最近一轮 */}
          <TerminalCard title="最近自动化周期">
            <div className="space-y-3">
              <p className="text-sm text-[var(--terminal-muted)]">{lastCycleMessage}</p>
              <div className="grid gap-3 sm:grid-cols-3">
                <InfoBlock label="今日周期" value={String(cycleCount)} />
                <InfoBlock label="成功" value={String(successCount)} />
                <InfoBlock label="失败" value={String(failureCount)} />
              </div>
            </div>
          </TerminalCard>

          {/* 定时巡检 */}
          <TerminalCard title="OpenClaw 运维巡检">
            <div className="space-y-3 text-sm">
              {openclawPatrolHistory.length > 0 ? (
                (() => {
                  const latestPatrol = asRecord(openclawPatrolHistory[0]);
                  const patrolStatus = readText(latestPatrol.status, "unknown");
                  const patrolMessage = readText(latestPatrol.message, "");
                  const executedAt = readText(latestPatrol.executed_at, "");
                  const actionsTaken = Array.isArray(latestPatrol.actions_taken) ? latestPatrol.actions_taken : [];
                  return (
                    <>
                      <div className="flex items-center gap-2">
                        <span className="text-[var(--terminal-muted)]">状态：</span>
                        <StatusBadge value={patrolStatus === "normal" ? "正常" : patrolStatus === "action_taken" ? "已执行动作" : patrolStatus === "throttled" ? "已节流" : patrolStatus} />
                      </div>
                      {patrolMessage && <p className="text-[var(--terminal-text)]">{patrolMessage}</p>}
                      {executedAt && <p className="text-xs text-[var(--terminal-muted)]">执行时间：{executedAt}</p>}
                      {actionsTaken.length > 0 && (
                        <div className="rounded border border-[var(--terminal-border)] p-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">执行动作</p>
                          <ul className="mt-2 space-y-1 text-xs">
                            {actionsTaken.slice(0, 3).map((action, idx) => {
                              const actionRecord = asRecord(action);
                              const actionName = readText(actionRecord.action, "");
                              const actionSuccess = Boolean(actionRecord.success);
                              return (
                                <li key={idx} className="flex items-center gap-2 text-[var(--terminal-text)]">
                                  <span className={`inline-flex h-2 w-2 rounded-full ${actionSuccess ? "bg-[var(--terminal-green)]" : "bg-[var(--terminal-red)]"}`} />
                                  <span className="font-medium">{actionName}</span>
                                  <span className={actionSuccess ? "text-[var(--terminal-green)]" : "text-[var(--terminal-red)]"}>{actionSuccess ? "成功" : "失败"}</span>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}
                    </>
                  );
                })()
              ) : (
                <p className="text-[var(--terminal-muted)]">暂无巡检记录</p>
              )}
            </div>
          </TerminalCard>

          {/* Openclaw 安全动作 */}
          <TerminalCard title="统一动作网关">
            <div className="space-y-3 text-sm">
              <div className="grid gap-2 sm:grid-cols-2">
                <InfoBlock label="当前状态" value={openclawOverallStatus} />
                <InfoBlock label="可执行周期" value={openclawReadyForCycle ? "是" : "否"} />
              </div>
              {openclawBlockedReason && <p className="text-[var(--terminal-muted)]">阻塞原因：{openclawBlockedReason}</p>}
              <p className="text-[var(--terminal-muted)]">运行模式：{openclawDegradeMode === "none" ? "完全自动" : openclawDegradeMode === "manual_only" ? "手动控制" : openclawDegradeMode}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                <InfoBlock label="自动运行" value={openclawAutoRunAllowed ? "允许" : "禁止"} />
                <InfoBlock label="程序建议" value={openclawSuggestedActionName || "暂无建议"} />
              </div>
              {openclawAllowedActions.length > 0 && (
                <div className="rounded border border-[var(--terminal-border)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">可用动作</p>
                  <ul className="mt-2 space-y-1 text-xs">
                    {openclawAllowedActions.map((action, idx) => (
                      <li key={idx} className="flex items-center gap-2 text-[var(--terminal-text)]">
                        <span className="font-medium">{readText(action.action, "")}</span>
                        {action.reason ? <span className="text-[var(--terminal-muted)]"> - {String(action.reason)}</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </TerminalCard>

          {/* 动作历史 */}
          <TerminalCard title="OpenClaw 运维动作">
            <div className="space-y-2 text-sm">
              {openclawAuditRecords.length > 0 ? (
                openclawAuditRecords.slice(0, 5).map((record, idx) => {
                  const actionName = readText(record.action, "未知动作");
                  const success = Boolean(record.success);
                  const executedAt = readText(record.executed_at || record.recorded_at, "");
                  return (
                    <div key={idx} className="flex items-center justify-between rounded border border-[var(--terminal-border)] p-2">
                      <div className="flex items-center gap-2">
                        <span className={`inline-flex h-2 w-2 rounded-full ${success ? "bg-[var(--terminal-green)]" : "bg-[var(--terminal-red)]"}`} />
                        <span className="font-medium text-[var(--terminal-text)]">{actionName}</span>
                      </div>
                      <div className="text-right">
                        <span className={success ? "text-[var(--terminal-green)]" : "text-[var(--terminal-red)]"}>{success ? "成功" : "失败"}</span>
                        {executedAt && <span className="ml-2 text-xs text-[var(--terminal-muted)]">{executedAt}</span>}
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-[var(--terminal-muted)]">暂无动作记录</p>
              )}
            </div>
          </TerminalCard>

          {/* 控制动作 */}
          <TerminalCard title="自动化控制">
            <div className="flex flex-wrap gap-2">
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
            </div>
          </TerminalCard>

          {confirmDialog?.open && (
            <OpenclawActionConfirmDialog
              action={confirmDialog.action}
              label={confirmDialog.label}
              riskLevel={confirmDialog.riskLevel}
              onConfirm={executeAction}
              onCancel={closeConfirmDialog}
            />
          )}

          {/* 任务记录 */}
          <TerminalCard title="最近任务">
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-[var(--terminal-border)]">
                    <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">任务</th>
                    <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">状态</th>
                    <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">创建时间</th>
                    <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">完成时间</th>
                  </tr>
                </thead>
                <tbody>
                  {items.slice(0, 3).length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-[var(--terminal-muted)]">当前还没有任务</td>
                    </tr>
                  ) : (
                    items.slice(0, 3).map((item, index) => (
                      <tr key={String(item.id ?? index)} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-bg-hover)]">
                        <td className="py-2 px-3 text-[var(--terminal-text)]">{String(item.task_type ?? "unknown")}</td>
                        <td className="py-2 px-3 text-center">
                          <StatusBadge value={String(item.status ?? "pending")} />
                        </td>
                        <td className="py-2 px-3 text-[var(--terminal-text)]">{String(item.created_at ?? "")}</td>
                        <td className="py-2 px-3 text-[var(--terminal-text)]">{String(item.finished_at ?? "")}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </TerminalCard>

          {/* 相关页面 */}
          <TerminalCard title="跨页入口">
            <div className="flex flex-wrap gap-2">
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
            </div>
          </TerminalCard>
        </>
      )}
    </TerminalShell>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--terminal-border)]/60 bg-[var(--terminal-bg)]/30 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">{label}</p>
      <p className="mt-2 text-sm text-[var(--terminal-text)]">{value}</p>
    </div>
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
