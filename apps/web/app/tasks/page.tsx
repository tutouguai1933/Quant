/* 这个文件负责渲染任务与自动化控制台。 */

import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { AutomationLastCycleCard } from "../../components/automation-last-cycle-card";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { ConfigCheckboxGrid, ConfigField, ConfigInput, ConfigSelect, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { readFeedback } from "../../lib/feedback";
import { getAutomationStatus, getAutomationStatusFallback, getEvaluationWorkspace, getEvaluationWorkspaceFallback, getValidationReview, getTasksPageModel, listTasks } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function TasksPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { isAuthenticated, token } = session;
  const feedback = readFeedback(params);
  let items = getTasksPageModel().items;
  let automation = getAutomationStatusFallback().item;
  let evaluation = getEvaluationWorkspaceFallback();
  let review: Record<string, unknown> = {};

  if (token) {
    const [tasksResponse, automationResponse, reviewResponse, evaluationResponse] = await Promise.allSettled([
      listTasks(token),
      getAutomationStatus(token),
      getValidationReview(token),
      getEvaluationWorkspace(),
    ]);
    if (tasksResponse.status === "fulfilled" && !tasksResponse.value.error) {
      items = tasksResponse.value.data.items;
    }
    if (automationResponse.status === "fulfilled" && !automationResponse.value.error) {
      automation = automationResponse.value.data.item;
    }
    if (reviewResponse.status === "fulfilled" && !reviewResponse.value.error) {
      review = reviewResponse.value.data.item;
    }
    if (evaluationResponse.status === "fulfilled" && !evaluationResponse.value.error) {
      evaluation = evaluationResponse.value.data.item;
    }
  }

  const latestAlert = automation.alerts[0];
  const reviewOverview = asRecord(review.overview);
  const evaluationReview = asRecord(asRecord(evaluation.reviews).research);
  const executionHealth = asRecord(automation.executionHealth);
  const automationHealth = asRecord(automation.health);
  const lastCycle = asRecord(automation.lastCycle);
  const dispatch = asRecord(lastCycle.dispatch);
  const dispatchMeta = asRecord(dispatch.meta);
  const dispatchItem = asRecord(dispatch.item);
  const dispatchOrder = asRecord(dispatchItem.order);
  const cycleMessageRaw = readText(lastCycle.message, "");
  const failureReasonRaw = readText(lastCycle.failure_reason, "");
  const cycleMessage = cycleMessageRaw || "当前还没有新的自动化判断。";
  const failureReason = failureReasonRaw || "当前没有新的失败原因。";
  const executionState = asRecord(executionHealth.execution_state);
  const executionStateName = readText(executionState.state, "unknown");
  const executionStateDetail = readText(executionState.detail, "当前没有执行状态说明。");
  const activeBlockers = Array.isArray(automationHealth.active_blockers)
    ? automationHealth.active_blockers.filter((item) => item && typeof item === "object")
    : [];
  const operatorActions = Array.isArray(automationHealth.operator_actions)
    ? automationHealth.operator_actions.filter((item) => item && typeof item === "object")
    : [];
  const focusCards = asRecord(automationHealth.focus_cards);
  const takeoverSummary = asRecord(automationHealth.takeover_summary);
  const alertSummary = asRecord(automationHealth.alert_summary);
  const alertGroups = Array.isArray(alertSummary.groups)
    ? alertSummary.groups.filter((item) => item && typeof item === "object").map((item) => asRecord(item))
    : [];
  const runHealth = asRecord(automationHealth.run_health);
  const severitySummary = asRecord(automation.severitySummary);
  const resumeChecklist = Array.isArray(automation.resumeChecklist)
    ? automation.resumeChecklist.filter((item) => item && typeof item === "object").map((item) => asRecord(item))
    : [];
  const operations = asRecord(automation.operations);
  const runtimeWindow = asRecord(automation.runtimeWindow);
  const primaryOperatorAction = asRecord(operatorActions[0]);
  const primaryOperatorLabel = readText(primaryOperatorAction.label, "当前可以继续下一轮自动化");
  const primaryOperatorDetail = readText(primaryOperatorAction.detail, "当前没有额外阻塞说明。");
  const pauseReasonRaw = readText(automation.pauseReason, "");
  const takeoverReason = pauseReasonRaw || "当前没有接管原因。";
  const recoveryAction = readText(executionHealth.recovery_action, "healthy");
  const takeoverStateLabel = describeTakeoverState(automation.mode, automation.manualTakeover, automation.pauseReason);
  const recoveryActionLabel = formatRecoveryAction(recoveryAction);
  const latestFailedSync = asRecord(executionHealth.latest_failed_sync);
  const lastSyncFailureAt = readText(latestFailedSync.finished_at, "");
  const lastSyncFailureMessage = readText(latestFailedSync.error_message, readText(executionHealth.latest_error_message, "当前没有同步失败说明。"));
  const pausedSince = readText(takeoverSummary.paused_since, automation.pausedAt);
  const takeoverSince = readText(takeoverSummary.takeover_since, automation.manualTakeoverAt);
  const lastFailureAt = readText(takeoverSummary.last_failure_at, automation.lastFailureAt);
  const syncFailureCount = Number(runHealth.sync_failure_count ?? 0);
  const primaryBlocker = asRecord(activeBlockers[0]);
  const guidanceCurrentBlock = buildCurrentBlockSummary({
    primaryBlocker,
    cycleMessage: cycleMessageRaw,
    executionStateDetail,
    cycleCount: Number(automation.dailySummary.cycle_count ?? 0),
  });
  const guidanceTakeover = buildTakeoverGuidanceSummary({
    takeoverSummary,
    takeoverStateLabel,
    pauseReason: pauseReasonRaw,
    failureReason: failureReasonRaw,
  });
  const guidanceRecovery = buildRecoverySummary({
    operatorActions,
    recoveryActionLabel,
    recoveryAction,
  });
  const guidanceAlert = buildAlertSummaryCard({
    alertSummary,
    latestAlert,
    cycleCount: Number(automation.dailySummary.cycle_count ?? 0),
    latestSyncStatus: String(executionHealth.latest_sync_status ?? "unknown"),
  });
  const alertFocus = resolveFocusCard(asRecord(focusCards.alert), guidanceAlert);
  const takeoverFocus = resolveFocusCard(asRecord(focusCards.takeover), guidanceTakeover);
  const recoveryFocus = resolveFocusCard(asRecord(focusCards.recovery), guidanceRecovery);
  const operationsConfig = {
    operationsPresetKey: readText(operations.operations_preset_key, "balanced_guard"),
    operationsPresetDetail: readText(operations.operations_preset_detail, "当前还没有长期运行预设说明。"),
    pauseAfterFailures: readText(operations.pause_after_consecutive_failures, "2"),
    staleSyncThreshold: readText(operations.stale_sync_failure_threshold, "1"),
    autoPauseOnError: String(operations.auto_pause_on_error ?? true) === "false" ? "false" : "true",
    reviewLimit: readText(operations.review_limit, "10"),
    comparisonRunLimit: readText(operations.comparison_run_limit, "5"),
    cycleCooldownMinutes: readText(operations.cycle_cooldown_minutes, "15"),
    maxDailyCycleCount: readText(operations.max_daily_cycle_count, "8"),
  };
  const automationConfig = asRecord(automation.automationConfig);
  const automationConfigSummary = {
    automationPresetKey: readText(automationConfig.automation_preset_key, "balanced_runtime"),
    automationPresetDetail: readText(automationConfig.automation_preset_detail, "当前还没有自动化运行预设说明。"),
    longRunSeconds: readText(automationConfig.long_run_seconds, "300"),
    alertCleanupMinutes: readText(automationConfig.alert_cleanup_minutes, "15"),
  };
  const runtimeWindowSummary = {
    currentCycleCount: readText(runtimeWindow.current_cycle_count, "0"),
    dailyLimit: readText(runtimeWindow.daily_limit, operationsConfig.maxDailyCycleCount),
    remainingDailyCycles: readText(runtimeWindow.remaining_daily_cycle_count, operationsConfig.maxDailyCycleCount),
    cooldownRemainingMinutes: readText(runtimeWindow.cooldown_remaining_minutes, "0"),
    nextAction: readText(runtimeWindow.next_action, "run_next_cycle"),
    nextRunAt: readText(runtimeWindow.next_run_at, ""),
    takeoverReviewDueAt: readText(runtimeWindow.takeover_review_due_at, ""),
    blockedReason: readText(runtimeWindow.blocked_reason, ""),
    note: readText(runtimeWindow.note, "当前没有额外长期运行说明。"),
    readyForCycle: Boolean(runtimeWindow.ready_for_cycle),
  };
  const resumeReadyCount = resumeChecklist.filter((item) => String(item.status ?? "ready") === "ready").length;
  const resumeBlockedItems = resumeChecklist
    .filter((item) => String(item.status ?? "ready") !== "ready")
    .map((item) => readText(item.label, "检查项"));
  const schedulerPreview = automation.schedulerPlan.slice(0, 3);
  const schedulerPlanRows = buildSchedulerPlanRows(automation.schedulerPlan);
  const failurePolicyRows = buildFailurePolicyRows(automation.failurePolicy);
  const restoreConclusion = buildRestoreConclusion({
    readyForCycle: runtimeWindowSummary.readyForCycle,
    nextAction: runtimeWindowSummary.nextAction,
    blockedItems: resumeBlockedItems,
    manualTakeover: automation.manualTakeover,
    latestAlert,
    fallbackLabel: primaryOperatorLabel,
    fallbackDetail: primaryOperatorDetail,
  });
  const primaryAlertSummary = buildPrimaryAlertSummary({
    alertSummary,
    latestAlert,
    restoreConclusion,
    runtimeWindowSummary,
  });
  const executionPolicy = asRecord(automation.executionPolicy);
  const candidateSymbols = toStringArray(executionPolicy.candidate_symbols);
  const executionAllowedSymbols = toStringArray(executionPolicy.live_allowed_symbols);
  const executionSymbolOptions = Array.from(new Set([...candidateSymbols, ...executionAllowedSymbols])).map((item) => ({
    value: item,
    label: item,
    checked: executionAllowedSymbols.includes(item),
  }));
  const activeAlerts = filterActiveAlerts(automation.alerts, automationConfigSummary.alertCleanupMinutes);
  const latestAlertId = Number(latestAlert?.id ?? 0);
  const latestAlertIdValue = latestAlertId > 0 ? String(latestAlertId) : "";
  const hasClearableAlerts = activeAlerts.some((item) => {
    const level = String(item.level ?? "").toLowerCase();
    return level === "info" || level === "warning";
  });
  const takeoverTimelineRows = buildTakeoverTimelineRows({
    lastFailureAt,
    pausedSince,
    takeoverSince,
    pauseReason: pauseReasonRaw,
    recoveryActionLabel,
  });
  const recentReviewTasks = Array.isArray(evaluation.recent_review_tasks)
    ? evaluation.recent_review_tasks.filter((item) => item && typeof item === "object").map((item) => asRecord(item))
    : [];
  const executionConfig = {
    candidatePoolPresetKey: readText(executionPolicy.candidate_pool_preset_key, "top10_liquid"),
    candidatePoolPresetDetail: readText(executionPolicy.candidate_pool_preset_detail, "当前还没有候选池预设说明。"),
    liveSubsetPresetKey: readText(executionPolicy.live_subset_preset_key, "core_live"),
    liveSubsetPresetDetail: readText(executionPolicy.live_subset_preset_detail, "当前还没有 live 子集预设说明。"),
    candidateSymbols,
    liveAllowedSymbols: executionAllowedSymbols,
    liveMaxStakeUsdt: readText(executionPolicy.live_max_stake_usdt, "6"),
    liveMaxOpenTrades: readText(executionPolicy.live_max_open_trades, "1"),
  };
  const liveSubsetPresetCatalog = Array.isArray(executionPolicy.live_subset_preset_catalog)
    ? executionPolicy.live_subset_preset_catalog.filter((item) => item && typeof item === "object").map((item) => asRecord(item))
    : [];
  const operationsPresetCatalog = Array.isArray(operations.operations_preset_catalog)
    ? operations.operations_preset_catalog.filter((item) => item && typeof item === "object").map((item) => asRecord(item))
    : [];
  const automationPresetCatalog = Array.isArray(automationConfig.automation_preset_catalog)
    ? automationConfig.automation_preset_catalog.filter((item) => item && typeof item === "object").map((item) => asRecord(item))
    : [];

  return (
    <AppShell
      title="任务"
      subtitle="任务页现在先回答自动化有没有开、是否暂停、最近一轮做到哪里，再看底部任务列表。"
      currentPath="/tasks"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} fallbackTitle="任务反馈" />

      <PageHero
        badge="自动化控制台"
        title="先确认自动化模式，再决定要不要触发下一轮工作流。"
        description="这页把自动化模式、停机入口、健康摘要和统一复盘放到一起，避免训练、推理、执行和复盘分散在不同页面里。"
      />

      {!isAuthenticated ? (
        <Card>
          <CardHeader>
            <p className="eyebrow">任务反馈</p>
            <CardTitle>任务页需要管理员登录</CardTitle>
            <CardDescription>登录后才能切换自动化模式、暂停自动化、手动触发一轮工作流和查看复盘。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="terminal">
              <a href="/login?next=%2Ftasks">前往登录</a>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <MetricGrid
            items={[
              { label: "自动化模式", value: formatMode(automation.mode), detail: automation.paused ? "当前已暂停" : "当前允许继续推进" },
              { label: "最近工作流", value: String(asRecord(automation.lastCycle).status ?? "waiting"), detail: "看最近一轮有没有真正推进到执行和复盘" },
              { label: "最近同步", value: String(executionHealth.latest_sync_status ?? "unknown"), detail: "自动化执行后先看同步有没有成功" },
              { label: "推荐动作", value: String(reviewOverview.recommended_action ?? automation.researchOverview.recommended_action ?? "n/a"), detail: "统一复盘会告诉你下一步该继续研究、dry-run 还是 live" },
            ]}
          />

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.9fr)]">
            <section className="grid gap-5">
              <Card>
                <CardHeader>
                  <p className="eyebrow">自动化模式</p>
                  <CardTitle>三种模式和一个停机开关</CardTitle>
                  <CardDescription>先决定是手动、自动 dry-run 还是自动小额 live；真正有风险时，直接暂停自动化。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-3">
                  <ActionCard action="automation_mode_manual" label="手动模式" detail="只保留人工操作，不再自动推进。" />
                  <ActionCard action="automation_mode_auto_dry_run" label="自动 dry-run" detail="研究通过后自动进入 dry-run，先不碰真实资金。" />
                  <ActionCard action="automation_mode_auto_live" label="自动小额 live" detail="在保留安全门的前提下自动进入小额 live。" />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">统一调度入口</p>
                  <CardTitle>一键跑完整一轮自动化工作流</CardTitle>
                  <CardDescription>这轮会统一串起训练、推理、筛选、执行和复盘，不再靠你一页页点。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-3">
                  <ActionCard action="automation_run_cycle" label="运行自动化工作流" detail="按当前模式推进一轮训练、推理、执行和复盘。" />
                  <ActionCard action="automation_pause" label="暂停自动化" detail="停止后续自动推进，切回人工接管。" danger />
                  <ActionCard action="automation_manual_takeover" label="人工立即接管" detail="立刻切到人工接管并暂停后续自动推进，先人工确认，再决定是否恢复。" danger />
                  <ActionCard action="automation_resume" label="恢复自动化" detail="恢复当前模式，让系统继续自动推进。" />
                  <ActionCard action="automation_dry_run_only" label="dry-run only" detail="只保留自动 dry-run，不再继续自动小额 live。" />
                  <ActionCard action="automation_kill_switch" label="Kill Switch" detail="一键停机，立即切回人工接管。" danger />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">长期运行窗口</p>
                  <CardTitle>这一轮之后还能不能继续自动跑</CardTitle>
                  <CardDescription>把今日轮次、冷却时间和下一步动作压成一块，先判断现在该继续、该等待还是该人工接管。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <GuidanceBlock
                    label="今日轮次"
                    value={`${runtimeWindowSummary.currentCycleCount} / ${runtimeWindowSummary.dailyLimit}`}
                    detail={`还剩 ${runtimeWindowSummary.remainingDailyCycles} 轮可跑`}
                  />
                  <GuidanceBlock
                    label="冷却剩余"
                    value={`${runtimeWindowSummary.cooldownRemainingMinutes} 分钟`}
                    detail={runtimeWindowSummary.readyForCycle ? "当前已经可以继续下一轮" : "还在等待下一轮窗口"}
                  />
                  <GuidanceBlock
                    label="下一步动作"
                    value={formatRuntimeWindowAction(runtimeWindowSummary.nextAction)}
                    detail={runtimeWindowSummary.note}
                    tone={runtimeWindowSummary.readyForCycle ? "supportive" : "warning"}
                  />
                  <GuidanceBlock
                    label="最早恢复时间"
                    value={formatMoment(runtimeWindowSummary.nextRunAt)}
                    detail={runtimeWindowSummary.nextRunAt ? "到了这个时间点后，系统才会结束当前冷却窗口。" : "当前没有额外冷却限制。"}
                    tone={runtimeWindowSummary.nextRunAt ? "warning" : "supportive"}
                  />
                  <GuidanceBlock
                    label="接管复核截止"
                    value={formatMoment(runtimeWindowSummary.takeoverReviewDueAt)}
                    detail={runtimeWindowSummary.takeoverReviewDueAt ? "超过这个时间还在人工接管，就先做接管复核，不要直接恢复。" : "当前没有长时间接管复核限制。"}
                    tone={runtimeWindowSummary.takeoverReviewDueAt ? "warning" : "default"}
                  />
                  <GuidanceBlock
                    label="当前状态"
                    value={runtimeWindowSummary.readyForCycle ? "可以继续下一轮" : "先不要继续"}
                    detail={runtimeWindowSummary.readyForCycle ? "当前没有冷却和轮次阻塞" : describeRuntimeBlockedReason(runtimeWindowSummary.blockedReason)}
                    tone={runtimeWindowSummary.readyForCycle ? "supportive" : "warning"}
                  />
                </CardContent>
              </Card>

              <WorkbenchConfigCard
                title="长期运行配置"
                description="这里改的是长期运行时的健康阈值、停机建议和复盘窗口，先把系统怎么判断风险讲清楚。"
                scope="operations"
                returnTo="/tasks"
              >
                <ConfigField label="长期运行预设" hint="先选一套长期运行口径，再决定要不要继续微调连续失败、冷却和每日轮次。">
                  <ConfigSelect
                    name="operations_preset_key"
                    defaultValue={operationsConfig.operationsPresetKey}
                    options={operationsPresetCatalog.map((item) => ({
                      value: readText(item.key, "balanced_guard"),
                      label: readText(item.label, readText(item.key, "balanced_guard")),
                    }))}
                  />
                </ConfigField>
                <ConfigField label="连续失败阈值" hint="连续失败达到这里时，这一轮会先停在人工复核或人工接管，不会再继续自动推进。">
                  <ConfigInput
                    name="pause_after_consecutive_failures"
                    type="number"
                    min={1}
                    max={20}
                    step={1}
                    defaultValue={operationsConfig.pauseAfterFailures}
                  />
                </ConfigField>
                <ConfigField label="同步陈旧阈值" hint="连续同步失败达到这里时，下一轮会先停在同步复核，不会继续自动推进。">
                  <ConfigInput
                    name="stale_sync_failure_threshold"
                    type="number"
                    min={1}
                    max={20}
                    step={1}
                    defaultValue={operationsConfig.staleSyncThreshold}
                  />
                </ConfigField>
                <ConfigField label="失败后自动暂停" hint="打开后会在关键失败时自动切到人工接管；关闭后只给出复盘建议。">
                  <ConfigSelect
                    name="auto_pause_on_error"
                    defaultValue={operationsConfig.autoPauseOnError}
                    options={[
                      { value: "true", label: "开启自动暂停" },
                      { value: "false", label: "只给复盘建议" },
                    ]}
                  />
                </ConfigField>
                <ConfigField label="复盘条数" hint="统一复盘和自动化摘要最多展示最近多少条记录。">
                  <ConfigInput name="review_limit" type="number" min={1} max={100} step={1} defaultValue={operationsConfig.reviewLimit} />
                </ConfigField>
                <ConfigField label="实验对比窗口" hint="评估中心和研究页会按这里展示最近多少轮实验变化。">
                  <ConfigInput name="comparison_run_limit" type="number" min={1} max={20} step={1} defaultValue={operationsConfig.comparisonRunLimit} />
                </ConfigField>
                <ConfigField label="自动化冷却时间" hint="每轮自动化之间至少间隔多久，避免短时间内连续重跑。">
                  <ConfigInput name="cycle_cooldown_minutes" type="number" min={0} max={1440} step={1} defaultValue={operationsConfig.cycleCooldownMinutes} />
                </ConfigField>
                <ConfigField label="每日最大轮次" hint="当天自动化最多跑几轮，超过后会自动停在等待状态。">
                    <ConfigInput name="max_daily_cycle_count" type="number" min={1} max={200} step={1} defaultValue={operationsConfig.maxDailyCycleCount} />
                  </ConfigField>
                <DataTable
                  columns={["长期运行预设", "适用场景", "当前是否选中", "说明"]}
                  rows={operationsPresetCatalog.map((item, index) => ({
                    id: `${readText(item.key, `operations-${index}`)}-${index}`,
                    cells: [
                      readText(item.label, readText(item.key, "未设置")),
                      readText(item.fit, "当前没有适用场景说明"),
                      readText(item.key, "") === operationsConfig.operationsPresetKey ? "当前预设" : "可切换",
                      readText(item.detail, "当前没有预设说明"),
                    ],
                  }))}
                  emptyTitle="当前还没有长期运行预设目录"
                  emptyDetail="先恢复自动化状态接口，系统才会给出长期运行预设目录。"
                />
              </WorkbenchConfigCard>

              <WorkbenchConfigCard
                title="自动化运行参数"
                description="这里改的是长期运行时真正会消费的接管时长和告警清理窗口，用来决定多久必须人工复核、多久前的旧告警不再算活跃告警。"
                scope="automation"
                returnTo="/tasks"
              >
                <ConfigField label="自动化运行预设" hint="先选一套接管和告警窗口口径，再决定要不要继续微调运行秒数和活跃告警窗口。">
                  <ConfigSelect
                    name="automation_preset_key"
                    defaultValue={automationConfigSummary.automationPresetKey}
                    options={automationPresetCatalog.map((item) => ({
                      value: readText(item.key, "balanced_runtime"),
                      label: readText(item.label, readText(item.key, "balanced_runtime")),
                    }))}
                  />
                </ConfigField>
                <ConfigField label="长时间接管阈值" hint="人工接管持续超过这个秒数后，系统会把下一步动作切到 review_takeover。">
                  <ConfigInput
                    name="long_run_seconds"
                    type="number"
                    min={60}
                    max={86400}
                    step={60}
                    defaultValue={automationConfigSummary.longRunSeconds}
                  />
                </ConfigField>
                <ConfigField label="活跃告警窗口" hint="只把最近这段时间内的告警算作活跃告警，超过窗口的旧告警仍保留历史，但不再提高当前风险等级。">
                  <ConfigInput
                    name="alert_cleanup_minutes"
                    type="number"
                    min={1}
                    max={1440}
                    step={1}
                    defaultValue={automationConfigSummary.alertCleanupMinutes}
                  />
                </ConfigField>
                <DataTable
                  columns={["自动化运行预设", "适用场景", "当前是否选中", "说明"]}
                  rows={automationPresetCatalog.map((item, index) => ({
                    id: `${readText(item.key, `automation-${index}`)}-${index}`,
                    cells: [
                      readText(item.label, readText(item.key, "未设置")),
                      readText(item.fit, "当前没有适用场景说明"),
                      readText(item.key, "") === automationConfigSummary.automationPresetKey ? "当前预设" : "可切换",
                      readText(item.detail, "当前没有预设说明"),
                    ],
                  }))}
                  emptyTitle="当前还没有自动化运行预设目录"
                  emptyDetail="先恢复自动化状态接口，系统才会给出自动化运行预设目录。"
                />
              </WorkbenchConfigCard>

              <DataTable
                columns={["长期运行与人工接管策略", "当前口径", "会影响什么", "现在建议怎么用"]}
                rows={buildLongRunPolicyRows({
                  operationsConfig,
                  automationConfigSummary,
                  runtimeWindowSummary,
                })}
                emptyTitle="当前还没有长期运行策略说明"
                emptyDetail="先保存长期运行参数，系统才会按当前口径给出长期运行和人工接管说明。"
              />

              <Card>
                <CardHeader>
                  <p className="eyebrow">当前自动化建议动作</p>
                  <CardTitle>先处理最会影响下一轮自动化的那一件事</CardTitle>
                  <CardDescription>这里把接管、告警和恢复建议压成一张卡，先告诉你当前最该先做什么。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>最该先做什么：{restoreConclusion.actionLabel}</p>
                  <p>原因：{restoreConclusion.summary}</p>
                  <p>最重要告警：{primaryAlertSummary.value}</p>
                  <p>当前接管：{readText(takeoverSummary.state_label, takeoverStateLabel)} / {readText(takeoverSummary.note, "当前没有额外接管说明。")}</p>
                  <p>恢复前先做什么：{restoreConclusion.detail}</p>
                </CardContent>
              </Card>

              <DataTable
                columns={["当前处理队列", "建议动作", "为什么先做", "下一步去哪里"]}
                rows={operatorActions.map((item, index) => {
                  const row = asRecord(item);
                  const action = String(row.action ?? `step-${index}`);
                  return {
                    id: `${action}-${index}`,
                    cells: [
                      String(row.label ?? "继续处理"),
                      action,
                      String(row.detail ?? "当前没有额外说明"),
                      action.includes("sync")
                        ? "/tasks"
                        : action.includes("takeover")
                          ? "/tasks"
                          : action.includes("resume")
                            ? "/tasks"
                            : "/evaluation",
                    ],
                  };
                })}
                emptyTitle="当前没有额外处理队列"
                emptyDetail="最近没有新的高风险告警时，这里会保持空白。"
              />

              <DataTable
                columns={["恢复检查项", "当前状态", "为什么重要", "当前值"]}
                rows={resumeChecklist.map((item, index) => ({
                  id: `${String(item.label ?? index)}-${index}`,
                  cells: [
                    readText(item.label, "检查项"),
                    readText(item.status, "ready"),
                    readText(item.detail, "当前没有额外说明"),
                    readText(item.value, "n/a"),
                  ],
                }))}
                emptyTitle="当前没有恢复检查项"
                emptyDetail="当前没有新的阻塞时，这里会保持空白。"
              />

              <Card>
                <CardHeader>
                  <p className="eyebrow">头号告警</p>
                  <CardTitle>{primaryAlertSummary.value}</CardTitle>
                  <CardDescription>{primaryAlertSummary.detail}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>当前建议：{primaryAlertSummary.actionLabel}</p>
                  <p>优先处理页：{primaryAlertSummary.targetPage}</p>
                  <div className="flex flex-wrap gap-3">
                    <Button asChild variant="outline" size="sm">
                      <Link href={primaryAlertSummary.targetHref}>去处理</Link>
                    </Button>
                    <Button asChild variant="outline" size="sm">
                      <Link href="/tasks">留在任务页继续观察</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">告警处理建议</p>
                  <CardTitle>头号告警怎么先处理</CardTitle>
                  <CardDescription>先把当前先做什么、恢复前还差什么讲清楚，再决定要不要恢复自动化。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <GuidanceBlock
                    label="当前先做什么"
                    value={latestAlert ? formatAlertAction(readText(latestAlert.level, "info")) : "先看最近一轮自动化判断"}
                    detail={latestAlert ? readText(latestAlert.message, "当前没有额外告警原因") : "当前没有活跃告警，先看最近一轮执行和复盘。"}
                    tone={latestAlert ? resolveAlertTone(readText(latestAlert.level, "info")) : "default"}
                  />
                  <GuidanceBlock
                    label="恢复前还差什么"
                    value={resumeBlockedItems.length ? resumeBlockedItems.join(" / ") : "当前恢复清单已经全部通过"}
                    detail={latestAlert ? `头号告警：${readText(latestAlert.message, "当前没有额外说明")}` : "当前没有新的头号告警。"}
                    tone={resumeBlockedItems.length ? "warning" : "supportive"}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">恢复导航</p>
                  <CardTitle>现在先处理什么、调度什么时候继续、人工接管后怎么恢复</CardTitle>
                  <CardDescription>把当前最该做的动作、调度窗口和接管恢复顺序放在一起，减少来回切页判断。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-3">
                  <GuidanceBlock
                    label="现在先处理什么"
                    value={primaryAlertSummary.actionLabel}
                    detail={primaryAlertSummary.detail}
                    tone="warning"
                  />
                  <GuidanceBlock
                    label="调度什么时候继续"
                    value={formatRuntimeWindowAction(runtimeWindowSummary.nextAction)}
                    detail={runtimeWindowSummary.readyForCycle ? "当前已经可以继续下一轮。" : runtimeWindowSummary.note}
                    tone={runtimeWindowSummary.readyForCycle ? "ok" : "warning"}
                  />
                  <GuidanceBlock
                    label="人工接管后怎么恢复"
                    value={restoreConclusion.actionLabel}
                    detail={restoreConclusion.detail}
                    tone={automation.manualTakeover ? "critical" : "info"}
                  />
                </CardContent>
              </Card>

              <WorkbenchConfigCard
                title="执行安全门"
                description="研究推荐出来的币会先进入研究 / dry-run 候选池；这里只有更严格的 live 子集、单笔金额上限和最大持仓数。"
                scope="execution"
                returnTo="/tasks"
              >
                <ConfigField label="live 子集预设" hint="研究和 dry-run 会共用候选池；这里先选更严格的 live 子集，再决定哪些币真的允许进入小额实盘。">
                  <ConfigSelect
                    name="live_subset_preset_key"
                    defaultValue={executionConfig.liveSubsetPresetKey}
                    options={liveSubsetPresetCatalog.map((item) => ({
                      value: readText(item.key, "core_live"),
                      label: readText(item.label, readText(item.key, "core_live")),
                    }))}
                  />
                </ConfigField>
                <ConfigField label="live_allowed_symbols" hint="只允许这些币种进入自动小额 live，没勾选的标的即使研究通过也不会放行。">
                  <ConfigCheckboxGrid name="live_allowed_symbols" options={executionSymbolOptions} />
                </ConfigField>
                <ConfigField label="当前 live 金额上限" hint="单笔真实下单最多用多少 USDT，超过这里会被本地安全门拦下。">
                  <ConfigInput name="live_max_stake_usdt" type="number" min={0.1} step={0.1} defaultValue={executionConfig.liveMaxStakeUsdt} />
                </ConfigField>
                <ConfigField label="最大打开仓位数" hint="自动小额 live 最多同时保留几笔持仓。">
                  <ConfigInput name="live_max_open_trades" type="number" min={1} max={20} step={1} defaultValue={executionConfig.liveMaxOpenTrades} />
                </ConfigField>
                <DataTable
                  columns={["候选池 / live 子集", "当前口径", "为什么这样设", "说明"]}
                  rows={[
                    {
                      id: "candidate-pool-preset",
                      cells: [
                        "研究 / dry-run 候选池",
                        executionConfig.candidatePoolPresetKey,
                        "先在更大的共享候选池里筛推荐，再决定要不要继续推进到 live。",
                        executionConfig.candidatePoolPresetDetail,
                      ],
                    },
                    {
                      id: "live-subset-preset",
                      cells: [
                        "live 子集",
                        executionConfig.liveSubsetPresetKey,
                        "live 会比候选池更严，先用更小的子集控制真实风险。",
                        executionConfig.liveSubsetPresetDetail,
                      ],
                    },
                  ]}
                  emptyTitle="当前还没有候选池和 live 子集说明"
                  emptyDetail="先恢复执行配置，系统才会说明候选池和 live 子集怎么衔接。"
                />
              </WorkbenchConfigCard>

              <Card>
                <CardHeader>
                  <p className="eyebrow">统一复盘</p>
                  <CardTitle>这轮工作流做到哪里了</CardTitle>
                  <CardDescription>先看训练、推理、筛选、dry-run、live、复盘六个阶段，再决定下一步。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  {buildReviewSteps(review).map((step) => (
                    <div key={step.key} className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-foreground">{step.label}</p>
                        <StatusBadge value={step.status} />
                      </div>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.detail}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <DataTable
                columns={["最近复盘记录", "状态", "完成时间", "结果摘要"]}
                rows={recentReviewTasks.map((item, index) => ({
                  id: `${item.task_type ?? index}-${item.finished_at ?? index}`,
                  cells: [
                    String(item.task_type ?? "review"),
                    String(item.status ?? "waiting"),
                    String(item.finished_at ?? item.requested_at ?? "n/a"),
                    String(item.result_summary ?? "当前没有结果摘要"),
                  ],
                }))}
                emptyTitle="当前还没有最近复盘记录"
                emptyDetail={`这里最多显示最近 ${operationsConfig.reviewLimit} 条复盘，先积累几轮研究、执行和复盘。`}
              />
            </section>

            <aside className="grid gap-5">
              <AutomationLastCycleCard initialCycle={lastCycle} />

              <Card>
                <CardHeader>
                  <p className="eyebrow">健康摘要</p>
                  <CardTitle>长期运行与人工接管</CardTitle>
                  <CardDescription>把为什么停下、是否该人工接管、恢复前先做什么和最近告警压成一块，避免长期运行时来回找信息。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <GuidanceBlock label="告警强度" value={alertFocus.value} detail={alertFocus.detail} tone={alertFocus.tone} />
                    <GuidanceBlock label="人工接管原因" value={takeoverFocus.value} detail={takeoverFocus.detail} tone={takeoverFocus.tone} />
                    <GuidanceBlock label="恢复前先做什么" value={recoveryFocus.value} detail={recoveryFocus.detail} tone={recoveryFocus.tone} />
                    <GuidanceBlock label="当前阻塞" value={guidanceCurrentBlock.value} detail={guidanceCurrentBlock.detail} />
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 p-4 text-sm leading-6 text-muted-foreground">
                    <p>当前模式：{formatMode(automation.mode)}，暂停：{automation.paused ? "是" : "否"}，人工介入：{automation.manualTakeover ? "是" : "否"}</p>
                    <p>当前控制：{readText(takeoverSummary.state_label, takeoverStateLabel)}，接管原因：{readText(takeoverSummary.reason_label, takeoverReason)}</p>
                    <p>执行器状态：{executionStateName}，说明：{executionStateDetail}</p>
                    <p>最近 armed 候选：{automation.armedSymbol || "n/a"}，最近复盘：{String(executionHealth.latest_review_status ?? "unknown")}</p>
                    <p>连续失败：{String(runHealth.consecutive_failure_count ?? 0)}，升级级别：{String(runHealth.escalation_level ?? "normal")}</p>
                    <p>同步新鲜度：{String(runHealth.stale_sync_state ?? "fresh")}，同步失败次数：{String(syncFailureCount)}</p>
                    <p>最后成功时间：{readText(runHealth.last_success_at, "当前还没有成功记录")}，最近失败时间：{lastFailureAt || "当前还没有失败记录"}</p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">接管快捷动作</p>
                  <CardTitle>先去最该处理的那一页</CardTitle>
                  <CardDescription>这里不再只告诉你有问题，而是直接给出下一步最短路径。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 p-4 text-sm leading-6 text-muted-foreground">
                    <p>当前首要动作：{restoreConclusion.actionLabel}</p>
                    <p>为什么先做它：{restoreConclusion.detail}</p>
                    <p>当前结论：{restoreConclusion.summary}</p>
                  </div>
                  <div className="grid gap-3">
                    <ActionCard action="automation_manual_takeover" label="先人工接管" detail="出现执行器异常、同步失败或高风险告警时，先停在人工接管，不再继续自动推进。" danger />
                    <ActionCard action="automation_dry_run_only" label="只恢复到 dry-run" detail="如果研究链已经恢复，但你还不想放开真实资金，先切回只保留 dry-run。" />
                    <ActionCard action="automation_resume" label="确认后恢复自动化" detail="只有在告警已处理、同步已恢复、接管原因已清除后，才恢复当前自动化模式。" />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Button asChild variant="outline" size="sm">
                      <Link href="/evaluation">去评估页看淘汰原因</Link>
                    </Button>
                    <Button asChild variant="outline" size="sm">
                      <Link href="/research">去研究页重跑训练</Link>
                    </Button>
                    <Button asChild variant="outline" size="sm">
                      <Link href="/backtest">去回测页看门槛</Link>
                    </Button>
                    <Button asChild variant="outline" size="sm">
                      <Link href="/strategies">去策略页确认执行</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">恢复确认</p>
                  <CardTitle>恢复自动化前先把这几项过一遍</CardTitle>
                  <CardDescription>把恢复清单、调度状态和下一步动作压在一起，先确认现在适不适合继续放开自动化。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <GuidanceBlock
                    label="清单通过情况"
                    value={`${resumeReadyCount} / ${resumeChecklist.length || 0} 项已通过`}
                    detail={resumeBlockedItems.length ? `还没通过：${resumeBlockedItems.join(" / ")}` : "当前恢复清单已经全部通过。"}
                    tone={resumeBlockedItems.length ? "warning" : "supportive"}
                  />
                  <GuidanceBlock
                    label="调度状态"
                    value={runtimeWindowSummary.readyForCycle ? "可以继续下一轮" : formatRuntimeWindowAction(runtimeWindowSummary.nextAction)}
                    detail={runtimeWindowSummary.note}
                    tone={runtimeWindowSummary.readyForCycle ? "supportive" : "warning"}
                  />
                  <GuidanceBlock
                    label="调度预览"
                    value={schedulerPreview.length ? schedulerPreview.map((step) => String(step.task_type ?? "task")).join(" -> ") : "当前没有调度步骤"}
                    detail={schedulerPreview.length ? "恢复后会按这条顺序继续推进。" : "当前还没有可用调度顺序。"}
                  />
                  <GuidanceBlock
                    label="恢复前先做什么"
                    value={readText(takeoverSummary.next_step, primaryOperatorLabel)}
                    detail={`${restoreConclusion.detail} ${readText(takeoverSummary.note, primaryOperatorDetail)}`}
                    tone={resumeBlockedItems.length ? "warning" : "default"}
                  />
                </CardContent>
              </Card>

              <section className="grid gap-5 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <p className="eyebrow">风险等级摘要</p>
                    <CardTitle>{readText(severitySummary.label, "当前还没有风险等级摘要")}</CardTitle>
                    <CardDescription>{readText(severitySummary.detail, "当前没有额外风险说明。")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                    <p>当前等级：{String(severitySummary.level ?? "normal")}</p>
                    <p>最近告警：{readText(severitySummary.latest_alert_code, "当前没有新告警")}</p>
                    <p>主要阻塞：{readText(severitySummary.primary_blocker, "当前没有明显阻塞")}</p>
                    <p>severitySummary：系统会先按这里决定是否建议人工接管。</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <p className="eyebrow">恢复清单</p>
                    <CardTitle>恢复前先把这几项过一遍</CardTitle>
                    <CardDescription>resumeChecklist 会把恢复自动化前最小检查项固定下来，避免凭感觉恢复。</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {resumeChecklist.length ? resumeChecklist.map((item, index) => (
                      <div key={`${String(item.label ?? index)}-${index}`} className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-foreground">{String(item.label ?? "检查项")}</p>
                          <StatusBadge value={String(item.status ?? "ready")} />
                        </div>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">{String(item.detail ?? "当前没有额外说明。")}</p>
                      </div>
                    )) : (
                      <p className="text-sm leading-6 text-muted-foreground">当前没有额外恢复清单，可以继续观察。</p>
                    )}
                  </CardContent>
                </Card>
              </section>

              <Card>
                <CardHeader>
                  <p className="eyebrow">当前阻塞</p>
                  <CardTitle>先处理卡住自动化的那几个点</CardTitle>
                  <CardDescription>这里直接列出当前最影响自动化继续推进的阻塞项，不用自己猜系统为什么停着。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  {activeBlockers.length ? activeBlockers.map((item, index) => {
                    const row = asRecord(item);
                    return (
                      <p key={`${String(row.code ?? index)}-${index}`}>
                        {String(row.code ?? "blocker")}：{String(row.detail ?? "当前没有更多说明")}
                      </p>
                    );
                  }) : <p>当前没有明显阻塞。</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">同步失败细节</p>
                  <CardTitle>先确认最近一次同步为什么失败</CardTitle>
                  <CardDescription>这里直接告诉你最近一次同步失败发生在什么时候、失败了几次、错误是什么，不用再翻任务记录。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>最近同步状态：{String(executionHealth.latest_sync_status ?? "unknown")}</p>
                  <p>最近同步失败：{lastSyncFailureAt ? `${lastSyncFailureAt}（${formatRelativeMoment(lastSyncFailureAt)}）` : "当前没有同步失败记录"}</p>
                  <p>同步失败次数：{String(syncFailureCount)}</p>
                  <p>失败说明：{lastSyncFailureMessage}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">人工接管时间线</p>
                  <CardTitle>先确认这次接管已经持续了多久</CardTitle>
                  <CardDescription>长期运行时，先分清是刚刚接管，还是已经挂了很久，再决定恢复还是继续停住。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>暂停开始：{pausedSince ? `${pausedSince}（${formatRelativeMoment(pausedSince)}）` : "当前没有暂停时间"}</p>
                  <p>已接管多久：{takeoverSince ? formatRelativeMoment(takeoverSince) : "当前没有人工接管时间"}</p>
                  <p>最近失败时间：{lastFailureAt ? `${lastFailureAt}（${formatRelativeMoment(lastFailureAt)}）` : "当前还没有失败记录"}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">接管建议</p>
                  <CardTitle>{readText(takeoverSummary.state_label, "当前无需接管")}</CardTitle>
                  <CardDescription>{readText(takeoverSummary.note, "当前没有额外接管说明。")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>当前模式：{formatMode(automation.mode)}</p>
                  <p>建议模式：{formatMode(readText(takeoverSummary.suggested_mode, automation.mode))}</p>
                  <p>接管原因：{readText(takeoverSummary.reason_label, takeoverReason)}</p>
                  <p>恢复前确认：{readText(takeoverSummary.next_step, "可以继续下一轮自动化")}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">恢复步骤</p>
                  <CardTitle>按这个顺序恢复最稳妥</CardTitle>
                  <CardDescription>这里是系统当前给出的最小恢复动作，不需要再自己翻日志找下一步。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  {operatorActions.length ? operatorActions.map((item, index) => {
                    const row = asRecord(item);
                    return (
                      <p key={`${String(row.action ?? index)}-${index}`}>
                        {index + 1}. {String(row.label ?? "继续处理")}：{String(row.detail ?? "")}
                      </p>
                    );
                  }) : <p>当前没有额外恢复步骤，可以继续观察。</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">最近告警</p>
                  <CardTitle>{latestAlert ? latestAlert.code : "当前没有新告警"}</CardTitle>
                  <CardDescription>{latestAlert ? latestAlert.message : "训练失败、推理失败、执行失败和同步失败都会显示在这里。"}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 px-4 py-4">
                    <span className="text-sm text-muted-foreground">告警级别</span>
                    <StatusBadge value={latestAlert?.level || "ok"} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">告警摘要</p>
                  <CardTitle>先看最近异常有多严重</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>错误告警：{String(alertSummary.error_count ?? 0)}</p>
                  <p>警告告警：{String(alertSummary.warning_count ?? 0)}</p>
                  <p>信息提示：{String(alertSummary.info_count ?? 0)}</p>
                  <p>活跃错误：{String(alertSummary.active_error_count ?? alertSummary.error_count ?? 0)}</p>
                  <p>活跃警告：{String(alertSummary.active_warning_count ?? alertSummary.warning_count ?? 0)}</p>
                  <p>活跃信息：{String(alertSummary.active_info_count ?? alertSummary.info_count ?? 0)}</p>
                  <p>活跃告警窗口：{String(alertSummary.cleanup_minutes ?? automationConfigSummary.alertCleanupMinutes)} 分钟</p>
                  <p>最近错误：{readText(alertSummary.latest_code, "当前没有错误告警")}</p>
                  <p>最近说明：{readText(alertSummary.latest_message, "当前没有额外说明")}</p>
                </CardContent>
              </Card>

              <DataTable
                columns={["告警等级处理口径", "当前数量", "系统会怎么做", "你下一步去哪看"]}
                rows={[
                  {
                    id: "error",
                    cells: [
                      "错误告警",
                      String(alertSummary.active_error_count ?? alertSummary.error_count ?? 0),
                      "优先建议人工接管或暂停，先别继续自动推进。",
                      "/tasks / /evaluation",
                    ],
                  },
                  {
                    id: "warning",
                    cells: [
                      "警告告警",
                      String(alertSummary.active_warning_count ?? alertSummary.warning_count ?? 0),
                      "先看告警详情和恢复步骤，再决定是否继续下一轮。",
                      "/tasks / /research",
                    ],
                  },
                  {
                    id: "info",
                    cells: [
                      "提示告警",
                      String(alertSummary.active_info_count ?? alertSummary.info_count ?? 0),
                      "只做提示，不直接拦住主流程；确认后可以清理。",
                      "/tasks",
                    ],
                  },
                ]}
                emptyTitle="当前没有告警等级口径"
                emptyDetail="恢复自动化状态接口后，这里会继续按当前活跃告警窗口展示。"
              />

              <Card>
                <CardHeader>
                  <p className="eyebrow">今日摘要</p>
                  <CardTitle>今天自动化跑了多少轮</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>日期：{String(automation.dailySummary.date ?? "n/a")}</p>
                  <p>轮数：{String(automation.dailySummary.cycle_count ?? 0)}</p>
                  <p>告警数：{String(automation.dailySummary.alert_count ?? 0)}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">长期运行参数</p>
                  <CardTitle>当前自动化到底按什么阈值在跑</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>连续失败阈值：{operationsConfig.pauseAfterFailures}</p>
                  <p>同步陈旧阈值：{operationsConfig.staleSyncThreshold}</p>
                  <p>失败后自动暂停：{operationsConfig.autoPauseOnError === "true" ? "开启" : "关闭"}</p>
                  <p>复盘条数：{operationsConfig.reviewLimit}</p>
                  <p>实验对比窗口：{operationsConfig.comparisonRunLimit}</p>
                  <p>自动化冷却时间：{operationsConfig.cycleCooldownMinutes} 分钟</p>
                  <p>每日最大轮次：{operationsConfig.maxDailyCycleCount}</p>
                  <p>长时间接管阈值：{automationConfigSummary.longRunSeconds} 秒</p>
                  <p>活跃告警窗口：{automationConfigSummary.alertCleanupMinutes} 分钟</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">最近告警历史</p>
                  <CardTitle>先判断是偶发抖动还是持续性问题</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  {automation.alerts.length ? automation.alerts.slice(0, 5).map((item, index) => (
                    <p key={`${item.code}-${item.createdAt}-${index}`}>
                      {index + 1}. [{item.level}] {item.code} / {item.message} / {item.createdAt || "n/a"}
                    </p>
                  )) : <p>当前还没有新的自动化告警。</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">告警快捷处理</p>
                  <CardTitle>先把最会干扰判断的告警处理掉</CardTitle>
                  <CardDescription>错误告警先人工处理；信息和警告告警可以在这里直接确认或清理，避免它们一直挂在任务页上干扰判断。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <ActionCard
                    action="automation_confirm_alert"
                    label="确认头号告警"
                    detail="把当前最靠前那条告警标记为已处理，适合告警已经人工确认、不需要继续占住头号位置的时候使用。"
                    hiddenFields={{ alert_id: latestAlertIdValue }}
                    disabled={!latestAlertIdValue}
                    disabledHint="当前没有可确认的头号告警。"
                  />
                  <ActionCard
                    action="automation_clear_non_error_alerts"
                    label="清理非错误告警"
                    detail="批量清掉 info 和 warning，只把真正需要人工处理的 error 留在列表里。"
                    hiddenFields={{ levels: "info,warning" }}
                    disabled={!hasClearableAlerts}
                    disabledHint="当前没有可清理的 info / warning 告警。"
                  />
                </CardContent>
              </Card>

              <DataTable
                columns={["活跃告警", "级别", "多久前", "建议动作", "建议页面", "说明"]}
                rows={activeAlerts.map((item, index) => ({
                  id: `${item.code}-${item.createdAt}-${index}`,
                  cells: [
                    item.code || "alert",
                    item.level || "info",
                    item.createdAt ? formatRelativeMoment(item.createdAt) : "n/a",
                    describeAlertNextStep(item),
                    mapAlertTargetPage(item),
                    item.message || "当前没有额外说明",
                  ],
                }))}
                emptyTitle="当前没有活跃告警"
                emptyDetail={`这里按最近 ${automationConfigSummary.alertCleanupMinutes} 分钟窗口显示仍然算活跃的告警。`}
              />

              <DataTable
                columns={["活跃告警", "首次出现", "最近一次出现", "重复次数"]}
                rows={alertGroups.map((item, index) => ({
                  id: `${String(item.code ?? "alert")}-${index}`,
                  cells: [
                    String(item.code ?? "alert"),
                    String(item.first_seen_at ?? "n/a"),
                    String(item.last_seen_at ?? "n/a"),
                    String(item.occurrence_count ?? "1"),
                  ],
                }))}
                emptyTitle="当前没有活跃告警生命周期记录"
                emptyDetail="告警开始重复出现后，这里会帮你看出它是偶发问题还是持续性问题。"
              />

              <DataTable
                columns={["人工接管时间线", "时间", "当前说明"]}
                rows={takeoverTimelineRows.map((item, index) => ({
                  id: `${item.label}-${index}`,
                  cells: [item.label, item.when, item.detail],
                }))}
                emptyTitle="当前没有人工接管时间线"
                emptyDetail="还没有失败、暂停或人工接管记录时，这里会保持空白。"
              />

              <Card>
                <CardHeader>
                  <p className="eyebrow">执行安全门</p>
                  <CardTitle>当前放行口径</CardTitle>
                  <CardDescription>自动化切到 live 前，会先按这里的白名单、单笔金额和最大持仓数做最后一道本地检查。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>研究 / dry-run 候选池：{executionConfig.candidateSymbols.length ? executionConfig.candidateSymbols.join(" / ") : "当前未配置"}</p>
                  <p>live 子集：{executionConfig.liveAllowedSymbols.length ? executionConfig.liveAllowedSymbols.join(" / ") : "当前未配置"}</p>
                  <p>live_allowed_symbols：{executionConfig.liveAllowedSymbols.length ? executionConfig.liveAllowedSymbols.join(" / ") : "当前未配置"}</p>
                  <p>live_max_stake_usdt：{executionConfig.liveMaxStakeUsdt}</p>
                  <p>live_max_open_trades：{executionConfig.liveMaxOpenTrades}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">调度顺序</p>
                  <CardTitle>固定自动化编排</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <DataTable
                    columns={["调度顺序矩阵", "任务", "当前说明", "为什么要先做"]}
                    rows={schedulerPlanRows}
                    emptyTitle="当前还没有调度顺序"
                    emptyDetail="自动化链恢复后，这里会按真实顺序列出下一轮编排。"
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">失败规则</p>
                  <CardTitle>失败后怎么处理</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <DataTable
                    columns={["失败规则矩阵", "失败阶段", "系统动作", "恢复前要看什么"]}
                    rows={failurePolicyRows}
                    emptyTitle="当前还没有失败规则"
                    emptyDetail="自动化规则恢复后，这里会告诉你失败后系统会怎么处理。"
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">研究与执行对齐</p>
                  <CardTitle>当前推荐和下一步动作</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>推荐标的：{String(reviewOverview.recommended_symbol ?? automation.researchOverview.recommended_symbol ?? "n/a")}</p>
                  <p>推荐动作：{String(reviewOverview.recommended_action ?? automation.researchOverview.recommended_action ?? "n/a")}</p>
                  <p>候选数量：{String(reviewOverview.candidate_count ?? automation.researchOverview.candidate_count ?? 0)}</p>
                  <p>可进 dry-run：{String(reviewOverview.ready_count ?? automation.researchOverview.ready_count ?? 0)}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">回到研究链</p>
                  <CardTitle>先回到研究链，再决定自动化动作</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>评估中心推荐：{readText(evaluation.overview.recommended_symbol, "n/a")}</p>
                  <p>推荐原因：{readText(evaluationReview.result, "未生成")}</p>
                  <div className="flex flex-wrap gap-3">
                    <Button asChild variant="outline">
                      <Link href="/research">回到研究链</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/backtest">去回测工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/evaluation">去评估与实验中心</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </aside>
          </section>

          <DataTable
            columns={["Task", "Source", "Status"]}
            rows={items.map((item) => ({
              id: item.id,
              cells: [item.taskType, item.source, <StatusBadge key={item.id} value={item.status} />],
            }))}
            emptyTitle="当前没有任务记录"
            emptyDetail="先运行一轮自动化工作流，再回到这里确认训练、同步、复盘是不是已经留下记录。"
          />
        </>
      )}
    </AppShell>
  );
}

function ActionCard({
  action,
  label,
  detail,
  danger = false,
  hiddenFields = {},
  disabled = false,
  disabledHint = "",
}: {
  action: string;
  label: string;
  detail: string;
  danger?: boolean;
  hiddenFields?: Record<string, string>;
  disabled?: boolean;
  disabledHint?: string;
}) {
  return (
    <Card className={danger ? "border-rose-500/30 bg-rose-500/10" : "bg-[color:var(--panel-strong)]/80"}>
      <CardContent className="p-4">
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value={action} />
          <input type="hidden" name="returnTo" value="/tasks" />
          {Object.entries(hiddenFields).map(([name, value]) => (
            <input key={name} type="hidden" name={name} value={value} />
          ))}
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
          <FormSubmitButton
            type="submit"
            variant={danger ? "danger" : "terminal"}
            size="sm"
            idleLabel={label}
            pendingLabel={`${label}运行中…`}
            pendingHint="自动化动作已提交，页面会在状态更新后自动刷新。"
            disabled={disabled}
          />
          {disabled && disabledHint ? <p className="text-xs leading-5 text-muted-foreground">{disabledHint}</p> : null}
        </form>
      </CardContent>
    </Card>
  );
}

function GuidanceBlock({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  const toneClass = resolveGuidanceToneClass(tone);
  return (
    <div className={`rounded-2xl border p-4 ${toneClass}`}>
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}

function buildReviewSteps(review: Record<string, unknown>) {
  const rawSteps = Array.isArray(review.steps) ? review.steps : [];
  const labelMap: Record<string, string> = {
    training: "研究训练",
    inference: "研究推理",
    screening: "研究筛选",
    dry_run: "dry-run",
    live: "小额 live",
    review: "统一复盘",
  };
  return rawSteps.map((item) => {
    const row = asRecord(item);
    const key = String(row.key ?? "");
    return {
      key,
      label: labelMap[key] || key || "步骤",
      status: String(row.status ?? "waiting"),
      detail: String(row.detail ?? ""),
    };
  });
}

function buildRestoreConclusion({
  readyForCycle,
  nextAction,
  blockedItems,
  manualTakeover,
  latestAlert,
  fallbackLabel,
  fallbackDetail,
}: {
  readyForCycle: boolean;
  nextAction: string;
  blockedItems: string[];
  manualTakeover: boolean;
  latestAlert: { level?: string; message?: string } | undefined;
  fallbackLabel: string;
  fallbackDetail: string;
}) {
  if (manualTakeover) {
    return {
      actionLabel: "先人工接管",
      summary: "建议先人工接管，确认执行器、同步和接管原因都已收口。",
      detail: "告警已处理、同步已恢复、接管原因已清除后，再点恢复。",
    };
  }
  if (blockedItems.length) {
    return {
      actionLabel: "先不要恢复",
      summary: `现在先不要恢复，原因：${blockedItems.join(" / ")} 还没处理完。`,
      detail: "先把恢复清单里未通过的检查项处理完，再考虑继续自动化。",
    };
  }
  if (latestAlert?.level === "error") {
    return {
      actionLabel: "先人工接管",
      summary: "建议立即人工接管，先处理执行器或同步异常。",
      detail: latestAlert.message || "最近仍有错误级告警，先不要继续放开自动化。",
    };
  }
  if (!readyForCycle) {
    return {
      actionLabel: "等待调度窗口",
      summary: `调度状态：${formatRuntimeWindowAction(nextAction)}。`,
      detail: "当前还在等待冷却、轮次窗口或调度恢复，不需要额外重复点击。",
    };
  }
  return {
    actionLabel: fallbackLabel || "可以继续自动化",
    summary: "当前可以继续自动化，最近没有高风险告警。",
    detail: fallbackDetail || "如果你已经看过评估、研究和回测结果，这一轮可以继续按当前模式推进。",
  };
}

function buildCurrentBlockSummary({
  primaryBlocker,
  cycleMessage,
  executionStateDetail,
  cycleCount,
}: {
  primaryBlocker: Record<string, unknown>;
  cycleMessage: string;
  executionStateDetail: string;
  cycleCount: number;
}) {
  const label = readText(primaryBlocker.label, "");
  const detail = readText(primaryBlocker.detail, "");
  if (label || detail) {
    return {
      value: label || "当前有阻塞",
      detail: detail || executionStateDetail,
    };
  }
  if (cycleMessage) {
    return {
      value: cycleCount > 0 ? `今天已跑 ${cycleCount} 轮` : "等待下一轮",
      detail: cycleMessage,
    };
  }
  return {
    value: "等待首轮工作流",
    detail: executionStateDetail,
  };
}

function buildTakeoverGuidanceSummary({
  takeoverSummary,
  takeoverStateLabel,
  pauseReason,
  failureReason,
}: {
  takeoverSummary: Record<string, unknown>;
  takeoverStateLabel: string;
  pauseReason: string;
  failureReason: string;
}) {
  const stateLabel = readText(takeoverSummary.state_label, takeoverStateLabel);
  const note = readText(takeoverSummary.note, "");
  const nextStep = readText(takeoverSummary.next_step, "");
  if (stateLabel === "人工接管中" || stateLabel === "已暂停" || takeoverStateLabel === "风险接管") {
    return {
      tone: "critical",
      value: stateLabel,
      detail: note || nextStep || (pauseReason ? `当前原因：${pauseReason}` : "问题没查清前先不要恢复自动化。"),
    };
  }
  if (failureReason) {
    return {
      tone: "warning",
      value: "建议人工复核",
      detail: `先看失败原因：${failureReason}`,
    };
  }
  return {
    tone: "ok",
    value: "暂不需要接管",
    detail: note || nextStep || "当前没有明显风险，自动化可以继续按计划运行。",
  };
}

function buildRecoverySummary({
  operatorActions,
  recoveryActionLabel,
  recoveryAction,
}: {
  operatorActions: object[];
  recoveryActionLabel: string;
  recoveryAction: string;
}) {
  const steps = operatorActions
    .map((item) => {
      const row = asRecord(item);
      const label = readText(row.label, "");
      const detail = readText(row.detail, "");
      return label ? `${label}${detail ? `：${detail}` : ""}` : "";
    })
    .filter((item) => item.length > 0);

  if (steps.length > 0) {
    return {
      tone: "warning",
      value: steps.length > 1 ? `先做前 ${steps.length} 步` : "先做这一步",
      detail: steps.join(" / "),
    };
  }

  return {
    tone: recoveryAction === "healthy" ? "ok" : "warning",
    value: recoveryActionLabel,
    detail: recoveryAction === "healthy" ? "当前没有额外恢复步骤，可以继续观察下一轮自动化结果。" : "先按当前恢复建议处理，再决定是否恢复自动化。",
  };
}

function buildAlertSummaryCard({
  alertSummary,
  latestAlert,
  cycleCount,
  latestSyncStatus,
}: {
  alertSummary: Record<string, unknown>;
  latestAlert: { level: string; code: string; message: string; createdAt: string } | undefined;
  cycleCount: number;
  latestSyncStatus: string;
}) {
  const latestCode = readText(alertSummary.latest_code, latestAlert?.code || "");
  const latestLevel = readText(alertSummary.latest_level, latestAlert?.level || "");
  const latestMessage = readText(alertSummary.latest_message, latestAlert?.message || "");
  const errorCount = Number(alertSummary.error_count ?? 0);
  const warningCount = Number(alertSummary.warning_count ?? 0);
  const infoCount = Number(alertSummary.info_count ?? 0);
  const value = latestCode ? `${formatAlertLevel(latestLevel)} / ${latestCode}` : "当前没有新告警";

  return {
    tone: latestLevel === "error" ? "critical" : latestLevel === "warning" ? "warning" : latestLevel === "info" ? "info" : "ok",
    value,
    detail: latestMessage || `今天已跑 ${cycleCount} 轮；错误 ${errorCount} 条，警告 ${warningCount} 条，提示 ${infoCount} 条；最近同步 ${latestSyncStatus}。`,
  };
}

function buildPrimaryAlertSummary({
  alertSummary,
  latestAlert,
  restoreConclusion,
  runtimeWindowSummary,
}: {
  alertSummary: Record<string, unknown>;
  latestAlert: { level: string; code: string; message: string; createdAt: string } | undefined;
  restoreConclusion: { actionLabel: string; summary: string; detail: string };
  runtimeWindowSummary: { nextAction: string; blockedReason: string };
}) {
  const latestCode = readText(alertSummary.latest_code, latestAlert?.code || "");
  const latestLevel = readText(alertSummary.latest_level, latestAlert?.level || "");
  const latestSource = readText(alertSummary.latest_source, "tasks");
  const latestMessage = readText(alertSummary.latest_message, latestAlert?.message || "");
  const hasActiveAlert = latestCode.length > 0 || latestLevel.length > 0 || latestMessage.length > 0;
  if (!hasActiveAlert) {
    return {
      value: "当前没有头号告警",
      detail: "最近没有新的高优先级异常，当前可以继续按恢复清单和调度窗口判断下一步。",
      actionLabel: restoreConclusion.actionLabel,
      targetPage: "任务页",
      targetHref: "/tasks",
    };
  }
  const target = resolveAlertTarget(latestSource, runtimeWindowSummary.nextAction, runtimeWindowSummary.blockedReason);
  return {
    value: `${formatAlertLevel(latestLevel)} / ${latestCode || "alert"}`,
    detail: latestMessage || "当前没有额外告警说明。",
    actionLabel: target.actionLabel,
    targetPage: target.page,
    targetHref: target.href,
  };
}

function resolveFocusCard(
  value: Record<string, unknown>,
  fallback: { tone?: string; value: string; detail: string },
) {
  return {
    tone: readText(value.tone, fallback.tone ?? "neutral"),
    value: readText(value.value, fallback.value),
    detail: readText(value.detail, fallback.detail),
  };
}

function resolveGuidanceToneClass(tone: string) {
  const mapping: Record<string, string> = {
    critical: "border-rose-500/30 bg-rose-500/10",
    warning: "border-amber-500/30 bg-amber-500/10",
    info: "border-sky-500/30 bg-sky-500/10",
    ok: "border-emerald-500/30 bg-emerald-500/10",
    neutral: "border-border/70 bg-[color:var(--panel-strong)]/70",
  };
  return mapping[tone] ?? mapping.neutral;
}

function formatMode(mode: string) {
  if (mode === "auto_dry_run") {
    return "自动 dry-run";
  }
  if (mode === "auto_live") {
    return "自动小额 live";
  }
  return "手动";
}

function describeTakeoverState(mode: string, manualTakeover: boolean, pauseReason: string) {
  if (!manualTakeover) {
    return "未接管";
  }
  if (pauseReason === "kill_switch") {
    return "风险接管";
  }
  if (pauseReason) {
    return "人工接管";
  }
  if (mode === "manual") {
    return "手动模式";
  }
  return "人工暂停";
}

function formatRecoveryAction(action: string) {
  const mapping: Record<string, string> = {
    healthy: "当前无需处理",
    reconnect_executor: "先恢复执行器连接",
    retry_sync: "先重试同步",
    review_dust: "先检查零头资产",
    watch_pending_exit: "先等待平仓完成",
    resume_after_review: "人工确认后再恢复",
    manual_takeover: "保持人工接管",
  };
  return mapping[action] ?? action;
}

function formatRuntimeWindowAction(action: string) {
  const mapping: Record<string, string> = {
    run_next_cycle: "继续下一轮",
    wait_cooldown: "等待冷却",
    wait_next_window: "等待下一窗口",
    manual_takeover: "先人工接管",
    resume_after_review: "先复核再恢复",
  };
  return mapping[action] ?? action;
}

function describeRuntimeBlockedReason(reason: string) {
  const mapping: Record<string, string> = {
    manual_takeover_active: "当前还在人工接管中，先处理接管原因再决定是否恢复。",
    paused_waiting_review: "当前处于暂停待复核状态，先看恢复清单和同步失败细节。",
    daily_limit_reached: "今日轮次已用完，等下一个时间窗口再继续。",
    cooldown_active: "当前还在冷却中，等最早恢复时间到了再继续。",
  };
  return mapping[reason] ?? "先处理冷却、暂停或轮次上限。";
}

function formatAlertAction(severity: string) {
  if (severity === "error") {
    return "先人工接管，再处理执行或同步错误";
  }
  if (severity === "warning") {
    return "先做复盘确认，再决定是否继续自动化";
  }
  return "先看最新摘要，再决定要不要继续";
}

function describeAlertNextStep(alert: { level?: string; code?: string; message?: string }) {
  const level = String(alert.level ?? "").toLowerCase();
  const code = String(alert.code ?? "").toLowerCase();
  if (level === "error") {
    if (code.includes("sync")) {
      return "先查同步失败，再决定是否恢复";
    }
    if (code.includes("research") || code.includes("train") || code.includes("infer")) {
      return "先去研究页重跑，再回任务页复核";
    }
    return "先人工接管，再核对执行和复盘";
  }
  if (level === "warning") {
    return "先去评估页确认门槛和淘汰原因";
  }
  return "先确认或清理，再继续观察";
}

function mapAlertTargetPage(alert: { level?: string; code?: string; message?: string }) {
  const level = String(alert.level ?? "").toLowerCase();
  const code = String(alert.code ?? "").toLowerCase();
  if (code.includes("research") || code.includes("train") || code.includes("infer")) {
    return "/research";
  }
  if (code.includes("backtest") || code.includes("gate") || code.includes("evaluation")) {
    return "/evaluation";
  }
  if (level === "warning") {
    return "/evaluation";
  }
  if (code.includes("dispatch") || code.includes("execution") || code.includes("order") || code.includes("position")) {
    return "/strategies";
  }
  return "/tasks";
}

function resolveAlertTone(severity: string) {
  if (severity === "error") {
    return "critical";
  }
  if (severity === "warning") {
    return "warning";
  }
  if (severity === "info") {
    return "info";
  }
  return "neutral";
}

function resolveAlertTarget(source: string, nextAction: string, blockedReason: string) {
  const normalizedSource = String(source || "").toLowerCase();
  if (normalizedSource.includes("research")) {
    return { actionLabel: "先回研究页处理", page: "研究工作台", href: "/research" };
  }
  if (normalizedSource.includes("dispatch") || normalizedSource.includes("execution")) {
    return { actionLabel: "先去策略页检查执行", page: "策略页", href: "/strategies" };
  }
  if (normalizedSource.includes("review") || normalizedSource.includes("evaluation")) {
    return { actionLabel: "先去评估页复核", page: "评估与实验中心", href: "/evaluation" };
  }
  if (nextAction === "review_takeover" || blockedReason === "manual_takeover_active") {
    return { actionLabel: "先留在任务页处理接管", page: "任务页", href: "/tasks" };
  }
  return { actionLabel: "先留在任务页处理", page: "任务页", href: "/tasks" };
}

function formatWorkflowSource(value: string): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "自动化工作流";
  }
  if (normalized === "manual_pipeline") {
    return "手动信号流水线";
  }
  if (normalized === "automation") {
    return "自动化工作流";
  }
  return normalized;
}

function formatAlertLevel(level: string) {
  const mapping: Record<string, string> = {
    error: "错误告警",
    warning: "警告告警",
    info: "提示告警",
    ok: "正常",
  };
  return mapping[level] ?? (level || "告警");
}

function filterActiveAlerts(
  alerts: Array<{ id?: number; level: string; code: string; message: string; createdAt: string }>,
  cleanupMinutes: string,
) {
  const minutes = Number.parseInt(cleanupMinutes, 10);
  if (!Number.isFinite(minutes) || minutes <= 0) {
    return alerts.slice(0, 5);
  }
  const cutoff = Date.now() - minutes * 60 * 1000;
  return alerts.filter((item) => {
    const timestamp = Date.parse(item.createdAt || "");
    return Number.isFinite(timestamp) && timestamp >= cutoff;
  }).slice(0, 5);
}

function buildTakeoverTimelineRows({
  lastFailureAt,
  pausedSince,
  takeoverSince,
  pauseReason,
  recoveryActionLabel,
}: {
  lastFailureAt: string;
  pausedSince: string;
  takeoverSince: string;
  pauseReason: string;
  recoveryActionLabel: string;
}) {
  const rows: Array<{ label: string; when: string; detail: string }> = [];
  if (lastFailureAt) {
    rows.push({
      label: "最近失败时间",
      when: lastFailureAt,
      detail: "先从这一次失败往回看任务、同步和告警。",
    });
  }
  if (pausedSince) {
    rows.push({
      label: "开始暂停",
      when: pausedSince,
      detail: pauseReason ? `暂停原因：${pauseReason}` : "当前没有额外暂停原因。",
    });
  }
  if (takeoverSince) {
    rows.push({
      label: "进入人工接管",
      when: takeoverSince,
      detail: `建议动作：${recoveryActionLabel}`,
    });
  }
  return rows;
}

function buildLongRunPolicyRows({
  operationsConfig,
  automationConfigSummary,
  runtimeWindowSummary,
}: {
  operationsConfig: {
    pauseAfterFailures: string;
    staleSyncThreshold: string;
    autoPauseOnError: string;
    reviewLimit: string;
    comparisonRunLimit: string;
    cycleCooldownMinutes: string;
    maxDailyCycleCount: string;
  };
  automationConfigSummary: {
    longRunSeconds: string;
    alertCleanupMinutes: string;
  };
  runtimeWindowSummary: {
    readyForCycle: boolean;
    cooldownRemainingMinutes: string;
    nextAction: string;
    blockedReason: string;
  };
}) {
  return [
    {
      id: "pause_after_consecutive_failures",
      cells: [
        "连续失败阈值",
        `${operationsConfig.pauseAfterFailures} 次`,
        "达到这个次数后，系统会先停在人工复核或人工接管。",
        "如果最近频繁失败，先降低自动推进频率，再决定要不要恢复。",
      ],
    },
    {
      id: "stale_sync_failure_threshold",
      cells: [
        "同步陈旧阈值",
        `${operationsConfig.staleSyncThreshold} 次`,
        "连续同步失败达到这里后，会优先停在同步复核，不再继续自动推进。",
        "如果最近同步失败在增加，先处理同步问题，不要继续跑下一轮。",
      ],
    },
    {
      id: "auto_pause_on_error",
      cells: [
        "失败后自动暂停",
        operationsConfig.autoPauseOnError === "true" ? "开启自动暂停" : "只给复盘建议",
        "决定关键失败后是直接停机，还是只记录风险并继续人工判断。",
        operationsConfig.autoPauseOnError === "true" ? "当前更保守，适合先稳住系统。" : "当前更激进，恢复前先看最近告警。",
      ],
    },
    {
      id: "cycle_window",
      cells: [
        "调度节奏",
        `${operationsConfig.cycleCooldownMinutes} 分钟 / 每日 ${operationsConfig.maxDailyCycleCount} 轮`,
        "决定多久后才能继续下一轮，以及当天最多自动推进多少次。",
        runtimeWindowSummary.readyForCycle
          ? "当前已经可以继续下一轮。"
          : `当前还要等 ${runtimeWindowSummary.cooldownRemainingMinutes} 分钟，或先处理阻塞：${describeRuntimeBlockedReason(runtimeWindowSummary.blockedReason)}`,
      ],
    },
    {
      id: "takeover_review_window",
      cells: [
        "人工接管复核",
        `${automationConfigSummary.longRunSeconds} 秒`,
        "接管持续超过这个时间后，会把下一步动作切到人工复核。",
        "如果接管已经持续较久，先做复核，不要直接恢复自动化。",
      ],
    },
    {
      id: "alert_cleanup_window",
      cells: [
        "活跃告警窗口",
        `${automationConfigSummary.alertCleanupMinutes} 分钟`,
        "只把这个窗口内的告警算作当前风险，超出的旧告警保留历史但不再提高当前风险等级。",
        "如果当前告警很多，先清理旧告警，再看真正还在发生的问题。",
      ],
    },
    {
      id: "review_windows",
      cells: [
        "复盘与实验窗口",
        `复盘 ${operationsConfig.reviewLimit} 条 / 实验 ${operationsConfig.comparisonRunLimit} 轮`,
        "决定任务页和评估页一次展示多少历史，避免只看单轮结果。",
        "如果最近变化很多，先把窗口调大；如果想更聚焦当前结果，再调小。",
      ],
    },
  ];
}

function buildSchedulerPlanRows(plan: Array<Record<string, unknown>>) {
  return (plan || []).map((step, index) => ({
    id: `${String(step.task_type ?? index)}-${index}`,
    cells: [
      `第 ${index + 1} 步`,
      String(step.task_type ?? "task"),
      String(step.detail ?? "当前没有额外说明"),
      describeSchedulerStep(String(step.task_type ?? "")),
    ],
  }));
}

function buildFailurePolicyRows(policy: Record<string, unknown>) {
  return Object.entries(policy || {}).map(([stage, action]) => ({
    id: stage,
    cells: [
      formatFailureStage(stage),
      stage,
      String(action ?? "n/a"),
      describeFailurePolicy(String(stage), String(action ?? "")),
    ],
  }));
}

function describeSchedulerStep(taskType: string) {
  const mapping: Record<string, string> = {
    research_train: "先生成训练结果，后面的推理、评估和执行才有基础。",
    research_infer: "训练完成后立刻推理，才能知道当前哪一轮值得继续。",
    signal_output: "把研究结论整理成信号，再决定是否继续推进到执行。",
    dispatch: "真正把候选推进到 dry-run 或 live 之前的执行环节。",
    sync: "执行后先同步订单、持仓和余额，不然复盘没有依据。",
    review: "最后统一复盘，决定下一轮是继续、暂停还是人工接管。",
  };
  return mapping[taskType] ?? "当前没有额外调度说明。";
}

function formatFailureStage(stage: string) {
  const mapping: Record<string, string> = {
    research_train: "研究训练",
    research_infer: "研究推理",
    signal_output: "信号输出",
    dispatch: "执行派发",
    sync: "执行同步",
    review: "统一复盘",
  };
  return mapping[stage] ?? stage;
}

function describeFailurePolicy(stage: string, action: string) {
  const stageLabel = formatFailureStage(stage);
  const actionMap: Record<string, string> = {
    continue: "先记录下来，留给下一轮复盘判断。",
    retry_sync: "先重试同步，确认执行结果有没有真正落盘。",
    resume_after_review: "先做人工复核，再决定是否恢复自动化。",
    manual_takeover: "直接切到人工接管，避免系统继续自动推进。",
    pause: "先暂停自动化，查清楚原因再恢复。",
  };
  return `${stageLabel} 失败后会先执行 ${action || "continue"}；${actionMap[action] ?? "当前没有额外恢复说明。"}`;
}

function formatRelativeMoment(value: string) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    return "时间格式不可用";
  }
  const diffMs = Date.now() - timestamp;
  const diffMinutes = Math.round(diffMs / 60000);
  if (diffMinutes <= 1) {
    return "刚刚";
  }
  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} 小时前`;
  }
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} 天前`;
}

function formatMoment(value: string) {
  const normalized = String(value || "").trim();
  return normalized || "当前没有明确时间";
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

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item ?? "").trim()).filter((item) => item.length > 0);
}
