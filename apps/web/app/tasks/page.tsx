/* 这个文件负责渲染任务与自动化控制台。 */

import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
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
  const takeoverSummary = asRecord(automationHealth.takeover_summary);
  const alertSummary = asRecord(automationHealth.alert_summary);
  const runHealth = asRecord(automationHealth.run_health);
  const pauseReasonRaw = readText(automation.pauseReason, "");
  const takeoverReason = pauseReasonRaw || "当前没有接管原因。";
  const recoveryAction = readText(executionHealth.recovery_action, "healthy");
  const takeoverStateLabel = describeTakeoverState(automation.mode, automation.manualTakeover, automation.pauseReason);
  const recoveryActionLabel = formatRecoveryAction(recoveryAction);
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
                  <ActionCard action="automation_manual_takeover" label="人工立即接管" detail="立刻触发全局暂停，并尽量暂停执行器，先人工确认再恢复。" danger />
                  <ActionCard action="automation_resume" label="恢复自动化" detail="恢复当前模式，让系统继续自动推进。" />
                  <ActionCard action="automation_dry_run_only" label="dry-run only" detail="只保留自动 dry-run，不再继续自动小额 live。" />
                  <ActionCard action="automation_kill_switch" label="Kill Switch" detail="一键停机，立即切回人工接管。" danger />
                </CardContent>
              </Card>

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
            </section>

            <aside className="grid gap-5">
              <Card>
                <CardHeader>
                  <p className="eyebrow">本轮自动化判断</p>
                  <CardTitle>先看为什么推荐、为什么阻塞、为什么执行</CardTitle>
                  <CardDescription>这里直接收口最近一轮自动化工作流的关键判断，不需要自己翻任务列表和复盘结果去拼。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>推荐标的：{readText(lastCycle.recommended_symbol, "n/a")}</p>
                  <p>推荐策略实例：{readText(lastCycle.recommended_strategy_id, "n/a")}</p>
                  <p>派发结果：{readText(dispatch.status, "waiting")}</p>
                  <p>最近订单：{readText(dispatchOrder.symbol, "n/a")} / {readText(dispatchOrder.status, "n/a")}</p>
                  <p>失败原因：{failureReason}</p>
                  <p>本轮说明：{cycleMessage}</p>
                  <p>下一步：{readText(lastCycle.next_action, "n/a")}</p>
                  <p>触发来源：{readText(dispatchMeta.source, "n/a")}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">健康摘要</p>
                  <CardTitle>长期运行与人工接管</CardTitle>
                  <CardDescription>把为什么停下、是否该人工接管、恢复前先做什么和最近告警压成一块，避免长期运行时来回找信息。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <GuidanceBlock label="当前阻塞" value={guidanceCurrentBlock.value} detail={guidanceCurrentBlock.detail} />
                    <GuidanceBlock label="接管建议" value={guidanceTakeover.value} detail={guidanceTakeover.detail} />
                    <GuidanceBlock label="恢复步骤" value={guidanceRecovery.value} detail={guidanceRecovery.detail} />
                    <GuidanceBlock label="告警摘要" value={guidanceAlert.value} detail={guidanceAlert.detail} />
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 p-4 text-sm leading-6 text-muted-foreground">
                    <p>当前模式：{formatMode(automation.mode)}，暂停：{automation.paused ? "是" : "否"}，人工介入：{automation.manualTakeover ? "是" : "否"}</p>
                    <p>当前控制：{takeoverStateLabel}，接管原因：{takeoverReason}</p>
                    <p>执行器状态：{executionStateName}，说明：{executionStateDetail}</p>
                    <p>最近 armed 候选：{automation.armedSymbol || "n/a"}，最近复盘：{String(executionHealth.latest_review_status ?? "unknown")}</p>
                    <p>连续失败：{String(runHealth.consecutive_failure_count ?? 0)}，升级级别：{String(runHealth.escalation_level ?? "normal")}</p>
                    <p>同步新鲜度：{String(runHealth.stale_sync_state ?? "fresh")}，最后成功时间：{readText(runHealth.last_success_at, "当前还没有成功记录")}</p>
                  </div>
                </CardContent>
              </Card>

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
                  <p className="eyebrow">接管建议</p>
                  <CardTitle>{readText(takeoverSummary.state_label, "当前无需接管")}</CardTitle>
                  <CardDescription>{readText(takeoverSummary.note, "当前没有额外接管说明。")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>当前模式：{formatMode(automation.mode)}</p>
                  <p>建议模式：{formatMode(readText(takeoverSummary.suggested_mode, automation.mode))}</p>
                  <p>接管原因：{readText(takeoverSummary.reason, takeoverReason)}</p>
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
                  <p>最近错误：{readText(alertSummary.latest_code, "当前没有错误告警")}</p>
                  <p>最近说明：{readText(alertSummary.latest_message, "当前没有额外说明")}</p>
                </CardContent>
              </Card>

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
                  <p className="eyebrow">调度顺序</p>
                  <CardTitle>固定自动化编排</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  {(automation.schedulerPlan.length > 0 ? automation.schedulerPlan : []).map((step, index) => (
                    <p key={`${String(step.task_type ?? index)}-${index}`}>
                      {index + 1}. {String(step.task_type ?? "task")} / {String(step.detail ?? "")}
                    </p>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">失败规则</p>
                  <CardTitle>失败后怎么处理</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  {Object.entries(automation.failurePolicy).map(([key, value]) => (
                    <p key={key}>
                      {key}：{String(value)}
                    </p>
                  ))}
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
}: {
  action: string;
  label: string;
  detail: string;
  danger?: boolean;
}) {
  return (
    <Card className={danger ? "border-rose-500/30 bg-rose-500/10" : "bg-[color:var(--panel-strong)]/80"}>
      <CardContent className="p-4">
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value={action} />
          <input type="hidden" name="returnTo" value="/tasks" />
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
          />
        </form>
      </CardContent>
    </Card>
  );
}

function GuidanceBlock({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 p-4">
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
      value: stateLabel,
      detail: note || nextStep || (pauseReason ? `当前原因：${pauseReason}` : "问题没查清前先不要恢复自动化。"),
    };
  }
  if (failureReason) {
    return {
      value: "建议人工复核",
      detail: `先看失败原因：${failureReason}`,
    };
  }
  return {
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
      value: steps.length > 1 ? `先做前 ${steps.length} 步` : "先做这一步",
      detail: steps.join(" / "),
    };
  }

  return {
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
    value,
    detail: latestMessage || `今天已跑 ${cycleCount} 轮；错误 ${errorCount} 条，警告 ${warningCount} 条，提示 ${infoCount} 条；最近同步 ${latestSyncStatus}。`,
  };
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
  if (pauseReason === "kill_switch" || pauseReason === "manual_takeover") {
    return "风险接管";
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

function formatAlertLevel(level: string) {
  const mapping: Record<string, string> = {
    error: "错误告警",
    warning: "警告告警",
    info: "提示告警",
    ok: "正常",
  };
  return mapping[level] ?? (level || "告警");
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
