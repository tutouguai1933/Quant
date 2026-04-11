/* 这个文件负责渲染策略中心页面，统一展示策略判断和执行动作。 */

import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { ArbitrationHandoffCard } from "../../components/arbitration-handoff-card";
import { AutomationControlCard } from "../../components/automation-control-card";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ResearchCandidateBoard } from "../../components/research-candidate-board";
import { ConfigCheckboxGrid, ConfigField, ConfigInput, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { StatusBadge } from "../../components/status-badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { readFeedback } from "../../lib/feedback";
import {
  getAutomationStatus,
  getAutomationStatusFallback,
  getEvaluationWorkspace,
  getEvaluationWorkspaceFallback,
  getResearchCandidate,
  getResearchCandidates,
  getResearchCandidatesFallback,
  getStrategyWorkspace,
  getStrategyWorkspaceFallback,
  type StrategyWorkspaceCard,
  type WorkspaceAccountState,
} from "../../lib/api";
import { getControlSessionState } from "../../lib/session";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function StrategiesPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const focusSymbol = readQueryText(params.symbol).toUpperCase();
  const session = await getControlSessionState();
  const { token, isAuthenticated } = session;
  const feedback = readFeedback(params);
  let workspace = getStrategyWorkspaceFallback();
  let candidateSnapshot = getResearchCandidatesFallback();
  let automation = getAutomationStatusFallback().item;
  let evaluation = getEvaluationWorkspaceFallback();
  const [workspaceResult, candidateResult, automationResult, evaluationResult] = await Promise.allSettled([
    token ? getStrategyWorkspace(token) : Promise.resolve(null),
    focusSymbol ? getResearchCandidate(focusSymbol) : getResearchCandidates(),
    token ? getAutomationStatus(token) : Promise.resolve(null),
    getEvaluationWorkspace(),
  ]);

  if (workspaceResult.status === "fulfilled" && workspaceResult.value && !workspaceResult.value.error) {
    workspace = workspaceResult.value.data;
  }

  if (candidateResult.status === "fulfilled") {
    const response = candidateResult.value;
    if (!response.error) {
      if (focusSymbol && "item" in response.data && response.data.item) {
        candidateSnapshot = {
          items: [response.data.item],
          summary: {
            candidate_count: 1,
            ready_count: response.data.item.allowed_to_dry_run ? 1 : 0,
            blocked_count: response.data.item.allowed_to_dry_run ? 0 : 1,
            pass_rate_pct: response.data.item.allowed_to_dry_run ? "100.00" : "0.00",
            top_candidate_symbol: response.data.item.symbol,
            top_candidate_score: response.data.item.score,
          },
        };
      } else if ("items" in response.data) {
        candidateSnapshot = response.data;
      }
    }
  }
  if (automationResult.status === "fulfilled" && automationResult.value && !automationResult.value.error) {
    automation = automationResult.value.data.item;
  }
  if (evaluationResult.status === "fulfilled" && !evaluationResult.value.error) {
    evaluation = evaluationResult.value.data.item;
  }
  const automationCycle = asRecord(automation.lastCycle);
  const arbitration = asRecord(automation.arbitration);
  const arbitrationSuggestedAction = asRecord(arbitration.suggested_action);
  const controlMatrix = asRecord(automation.controlMatrix);
  const controlActions = Array.isArray(automation.controlActions)
    ? automation.controlActions.filter((item) => item && typeof item === "object").map((item) => asRecord(item))
    : [];
  const controlMatrixItems = Array.isArray(controlMatrix.items)
    ? controlMatrix.items.filter((item) => item && typeof item === "object").map((item) => asRecord(item))
    : [];
  const effectiveControlActions = controlMatrixItems.length ? controlMatrixItems : controlActions;
  const resumeAction = effectiveControlActions.find((item) => readText(item.action, "") === "automation_resume");
  const hasEnabledResumeAction = Boolean(resumeAction && String(resumeAction.enabled ?? "true") !== "false");
  const recommendationExplanation = asRecord(evaluation.recommendation_explanation);
  const stageDecisionSummary = asRecord(evaluation.stage_decision_summary);
  const alignmentDetails = asRecord(evaluation.alignment_details);
  const configuration = asRecord(workspace.configuration);
  const sharedCandidateScope = asRecord(configuration.candidate_scope);
  const executionPolicy = asRecord(automation.executionPolicy);
  const candidateSymbols = toStringArray(executionPolicy.candidate_symbols);
  const executionAllowedSymbols = toStringArray(executionPolicy.live_allowed_symbols);
  const candidateScopeCandidateSymbols = toStringArray(sharedCandidateScope.candidate_symbols);
  const candidateScopeLiveSymbols = toStringArray(sharedCandidateScope.live_allowed_symbols);
  const candidateScopeHeadline = readText(sharedCandidateScope.headline, "研究和 dry-run 先共用候选池，再由更严格的 live 子集继续放行。");
  const candidateScopeDetail = readText(sharedCandidateScope.detail, "当前还没有候选池和 live 子集的统一说明。");
  const candidateScopeNextStep = readText(sharedCandidateScope.next_step, "先确认候选池排序，再决定哪些币进入 live 子集。");
  const evaluationPriorityQueue = Array.isArray(evaluation.priority_queue) ? evaluation.priority_queue : [];
  const automationPriorityQueue = Array.isArray(automation.priorityQueue) ? automation.priorityQueue : [];
  const priorityQueue = automationPriorityQueue.length ? automationPriorityQueue : evaluationPriorityQueue;
  const priorityQueueSummary = asRecord(
    Object.keys(asRecord(automation.priorityQueueSummary)).length ? automation.priorityQueueSummary : evaluation.priority_queue_summary,
  );
  const priorityFocusSymbol = readText(
    priorityQueueSummary.active_symbol,
    workspace.research_recommendation?.symbol || readText(evaluation.overview.recommended_symbol, "当前还没有推荐标的"),
  );
  const priorityNextSymbol = readText(priorityQueueSummary.next_symbol, "当前没有下一位候选");
  const priorityHeadline = readText(priorityQueueSummary.headline, candidateScopeHeadline);
  const priorityDetail = readText(priorityQueueSummary.detail, readText(recommendationExplanation.detail, "先继续研究，确认门控和执行差异"));
  const priorityQueuePreview = priorityQueue.slice(0, 3);
  const arbitrationActionLabel = readText(
    arbitrationSuggestedAction.label,
    workspace.research_recommendation?.next_action || "先进入 dry-run 观察。",
  );
  const arbitrationTargetPage = readText(arbitrationSuggestedAction.target_page, "/research");
  const executionSymbolOptions = Array.from(
    new Set([...(candidateSymbols.length ? candidateSymbols : workspace.whitelist), ...executionAllowedSymbols]),
  ).map((item) => ({
    value: item,
    label: item,
    checked: executionAllowedSymbols.includes(item),
  }));
  const strategyReturnTo = focusSymbol ? `/strategies?symbol=${encodeURIComponent(focusSymbol)}` : "/strategies";
  const isManualMode = automation.mode === "manual" && !automation.paused && !automation.manualTakeover;

  return (
    <AppShell
      title="策略"
      subtitle="策略中心先回答三件事：哪套策略在运行、它现在怎么看市场、最近有没有真正走到执行。"
      currentPath="/strategies"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="策略中心"
        title="先看判断，再决定要不要派发"
        description="左侧先看推荐执行、研究候选和下一步动作，右侧只看执行器状态、账户收口和执行动作。"
      />

      <ArbitrationHandoffCard arbitration={arbitration} isAuthenticated={isAuthenticated} surfaceLabel="策略页" />

      {focusSymbol ? (
        <Card>
          <CardHeader>
            <p className="eyebrow">当前跟进对象</p>
            <CardTitle>{focusSymbol}</CardTitle>
            <CardDescription>你是带着这个币种从市场页或图表页进入策略中心的，先围绕它确认判断，再决定要不要继续派发。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link href={`/market/${encodeURIComponent(focusSymbol)}`}>返回这个币种的图表页</Link>
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {!isAuthenticated ? (
        <Card>
          <CardHeader>
            <p className="eyebrow">动作反馈</p>
            <CardTitle>当前页面需要登录</CardTitle>
            <CardDescription>登录后才能看到真实策略状态、当前判断和最近执行结果，也才能继续启动、暂停、停止和派发。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="terminal">
              <Link href="/login?next=%2Fstrategies">先去登录</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <p className="eyebrow">双栏布局</p>
              <CardTitle>左边看判断，右边看执行</CardTitle>
              <CardDescription>这页把判断和执行分开，避免一整屏连续往下扫。</CardDescription>
            </CardHeader>
          </Card>

          <MetricGrid
            items={[
              { label: "策略数量", value: String(workspace.overview.strategy_count), detail: "当前阶段固定只做两套首批波段策略" },
              { label: "运行中", value: String(workspace.overview.running_count), detail: "running 才能继续派发最新信号" },
              { label: "白名单", value: String(workspace.overview.whitelist_count), detail: "只在固定币种池里做最小 dry-run" },
              { label: "最近执行", value: String(workspace.overview.order_count), detail: "方便快速确认链路有没有真正走通" },
            ]}
          />

          {automation.paused || automation.manualTakeover || isManualMode ? (
            <Card>
              <CardHeader>
                <p className="eyebrow">当前自动化状态</p>
                <CardTitle>
                  {automation.manualTakeover
                    ? "当前已人工接管"
                    : automation.paused
                    ? "当前已暂停自动化"
                    : "当前处于手动模式"}
                </CardTitle>
                <CardDescription>
                  {automation.manualTakeover && hasEnabledResumeAction
                    ? "这意味着当前不应该继续自动推进。下面的快捷入口会直接给你恢复、保持手动或继续停机；任务页只用来看完整时间线。"
                    : automation.manualTakeover
                    ? "这意味着当前不应该继续自动推进。下面的快捷入口会直接给你只回 dry-run、保持手动或继续停机；任务页只用来看完整时间线。"
                    : isManualMode
                    ? "这意味着系统当前不会自动推进。下面的快捷入口会直接给你保持手动、切回 dry-run only 或继续停机；任务页只用来看完整时间线。"
                    : "这意味着当前还停在暂停恢复链里。下面的快捷入口可以直接恢复、只回 dry-run、切到手动或继续停机；任务页只用来看完整时间线。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-3">
                <AutomationInfo label="当前模式" value={readText(automation.mode, "manual")} />
                <AutomationInfo label="暂停原因" value={readText(automation.pauseReason, "当前没有暂停原因")} />
                <AutomationInfo label="最近失败时间" value={readText(automation.lastFailureAt, "当前没有失败记录")} />
                <Button asChild variant="outline">
                  <Link href="/tasks">去任务页看完整时间线</Link>
                </Button>
              </CardContent>
            </Card>
          ) : null}

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)] xl:items-start">
            <section className="grid gap-5">
              {workspace.research_recommendation ? (
                <Card>
                  <CardHeader>
                    <p className="eyebrow">当前推荐执行候选</p>
                    <CardTitle>{workspace.research_recommendation.symbol}</CardTitle>
                    <CardDescription>
                      研究门：{workspace.research_recommendation.dry_run_gate.status}
                      {"，当前仲裁动作："}
                      {arbitrationActionLabel}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="action-grid">
                    <Button asChild variant="outline">
                      <Link href={`/market/${encodeURIComponent(workspace.research_recommendation.symbol)}`}>去这个币的图表页</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/research">去研究工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/backtest">去回测工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/evaluation">去评估与实验中心</Link>
                    </Button>
                    <Button asChild variant="terminal">
                      <Link href={`/strategies?symbol=${encodeURIComponent(workspace.research_recommendation.symbol)}`}>围绕这个币继续执行</Link>
                    </Button>
                  </CardContent>
                </Card>
              ) : null}

              <Card>
                <CardHeader>
                  <p className="eyebrow">候选池摘要</p>
                  <CardTitle>这一轮优先队列已经排出来了</CardTitle>
                  <CardDescription>这里直接承接统一候选队列，先看当前先推谁、下一位是谁、为什么被跳过。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <AutomationInfo label="当前先推进谁" value={priorityFocusSymbol} />
                    <AutomationInfo label="下一位候选" value={priorityNextSymbol} />
                    <AutomationInfo label="为什么先推进" value={priorityDetail} />
                    <AutomationInfo label="当前还差什么" value={candidateScopeNextStep} />
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">队列摘要</p>
                    <p className="mt-3 text-sm font-medium leading-6 text-foreground">{priorityHeadline}</p>
                    <div className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground">
                      {priorityQueuePreview.length ? priorityQueuePreview.map((item, index) => (
                        <p key={`${String(item.symbol ?? index)}-${index}`}>
                          {index + 1}. {readText(item.symbol, "n/a")} / {readText(item.dispatch_status, readText(item.queue_status, "unknown"))} / {readText(item.dispatch_reason, readText(item.skip_reason, readText(item.why_selected, readText(item.why_blocked, "当前没有额外说明"))))}
                        </p>
                      )) : <p>当前还没有统一优先队列，先完成研究和评估。</p>}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <ResearchCandidateBoard
                title="研究候选"
                summary={candidateSnapshot.summary}
                items={candidateSnapshot.items}
                focusSymbol={focusSymbol}
                nextStep={focusSymbol ? `当前仲裁动作：${arbitrationActionLabel}；如果要继续围绕 ${focusSymbol} 判断，也先按这个动作承接。` : `当前仲裁动作：${arbitrationActionLabel}`}
              />

              <Card>
                <CardHeader>
                  <p className="eyebrow">自动化判断</p>
                  <CardTitle>这一轮会不会继续走到 dry-run 或 live</CardTitle>
                  <CardDescription>策略页不只看执行器状态，也直接告诉你当前自动化模式、最近一轮结果和下一步动作。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <AutomationInfo label="当前模式" value={readText(automation.mode, "manual")} />
                  <AutomationInfo label="最近一轮" value={readText(automationCycle.status, "waiting")} />
                  <AutomationInfo label="自动化推荐" value={readText(automationCycle.recommended_symbol, "n/a")} />
                  <AutomationInfo label="下一步动作" value={arbitrationActionLabel} />
                  <AutomationInfo label="是否暂停" value={automation.paused ? "已暂停" : "正常运行"} />
                  <AutomationInfo label="人工接管" value={automation.manualTakeover ? "人工接管中" : "当前未接管"} />
                  <AutomationInfo label="暂停原因" value={readText(automation.pauseReason, "当前没有暂停原因")} />
                  <AutomationInfo label="上次失败时间" value={readText(automation.lastFailureAt, "当前没有失败记录")} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">自动化快捷入口</p>
                  <CardTitle>
                    {automation.manualTakeover && hasEnabledResumeAction
                      ? "接管中先决定怎么恢复"
                      : automation.manualTakeover
                      ? "接管中先决定保留什么模式"
                      : isManualMode
                      ? "手动模式下决定何时重开自动化"
                      : automation.paused
                      ? "暂停后先决定怎么继续"
                      : "需要时直接停下或切回手动"}
                  </CardTitle>
                  <CardDescription>
                    {automation.manualTakeover && hasEnabledResumeAction
                      ? "策略页不必再跳回任务页找按钮，这里直接给你恢复、只回 dry-run、保持手动和停机入口。"
                      : automation.manualTakeover
                      ? "策略页不必再跳回任务页找按钮，这里直接给你只回 dry-run、保持手动和停机入口。"
                      : isManualMode
                      ? "策略页不必再跳回任务页找按钮，这里直接给你保持手动、切回 dry-run only 和停机入口。"
                      : automation.paused
                      ? "策略页不必再跳回任务页找按钮，这里直接给你恢复、只回 dry-run、切到手动和停机入口。"
                      : "如果你在策略页就确认要暂停、转人工接管或切回手动，这里可以直接处理。"}
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  {effectiveControlActions.map((item, index) => (
                    <AutomationControlCard
                      key={`${readText(item.action, "automation")}-${index}`}
                      action={readText(item.action, "automation_mode_manual")}
                      label={readText(item.label, "自动化动作")}
                      detail={readText(item.detail, "当前没有额外说明。")}
                      returnTo={strategyReturnTo}
                      danger={Boolean(item.danger)}
                      disabled={String(item.enabled ?? "true") === "false"}
                      disabledHint={readText(item.disabled_reason, "")}
                    />
                  ))}
                </CardContent>
              </Card>

              <MetricGrid
                items={[
                  { label: "研究状态", value: workspace.research.status, detail: workspace.research.detail },
                  { label: "模型版本", value: workspace.research.model_version || "n/a", detail: "最近训练产物已经回到策略工作台" },
                  { label: "研究信号", value: String(workspace.research.signal_count), detail: "最近推理结果中可用的信号数量" },
                ]}
              />

              <Card>
                <CardHeader>
                  <p className="eyebrow">下一步动作</p>
                  <CardTitle>按仲裁动作承接下一步</CardTitle>
                  <CardDescription>这块只承接当前仲裁动作，不再让策略页自己猜下一步。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm leading-6 text-muted-foreground">
                    当前仲裁建议先去：{formatTargetPage(arbitrationTargetPage)}。如果还要围绕单个币复核，也先以这一步为准。
                  </p>
                  <div className="action-grid">
                    <Button asChild variant="terminal">
                      <Link href={arbitrationTargetPage}>{arbitrationActionLabel}</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href={focusSymbol ? `/market/${encodeURIComponent(focusSymbol)}` : "/signals"}>去图表页确认</Link>
                    </Button>
                    <Button asChild variant="secondary">
                      <Link href="/signals">回到信号页复核</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">研究链入口</p>
                  <CardTitle>先看研究工作台、回测工作台和评估与实验中心</CardTitle>
                  <CardDescription>执行页继续承接研究链，而不是让你自己在多个页面之间拼结论。</CardDescription>
                </CardHeader>
              <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>评估中心推荐：{readText(evaluation.overview.recommended_symbol, "n/a")}</p>
                  <p>推荐原因：{readText(stageDecisionSummary.why_recommended, readText(recommendationExplanation.detail, "未生成"))}</p>
                  <p>研究 / 执行差异：{readText(stageDecisionSummary.execution_gap, "当前还没有差异说明")}</p>
                  <div className="flex flex-wrap gap-3">
                    <Button asChild variant="outline">
                      <Link href="/research">研究工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/backtest">回测工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/evaluation">评估与实验中心</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-card/90">
                <CardHeader>
                  <p className="eyebrow">策略判断</p>
                  <CardTitle>两套首批波段策略</CardTitle>
                  <CardDescription>只保留当前判断和执行建议，不再把页面往纵向拉长。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 xl:grid-cols-2">
                  {workspace.strategies.length ? workspace.strategies.map((item) => (
                    <StrategyCard key={item.key} item={item} />
                  )) : (
                    <div className="rounded-2xl border border-dashed border-border/70 bg-muted/35 p-5 text-sm leading-6 text-muted-foreground xl:col-span-2">
                      <p className="font-medium text-foreground">当前还没有可评估的策略对象</p>
                      <p>统一候选池还是空的，所以策略页不会再回退到旧白名单假装继续评估。</p>
                      <p>下一步：{candidateScopeNextStep}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </section>

            <aside className="grid gap-5">
              <Card>
                <CardHeader>
                  <p className="eyebrow">执行器状态</p>
                  <CardTitle>先确认当前连的是谁</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>
                    当前执行器：
                    {" "}
                    {workspace.executor_runtime.executor}
                    {" / "}
                    {workspace.executor_runtime.backend}
                    {" / "}
                    {workspace.executor_runtime.mode}
                  </p>
                  <p>连接状态：{workspace.executor_runtime.connection_status}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">当前配置摘要</p>
                  <CardTitle>先确认这轮研究和执行到底按什么口径在跑</CardTitle>
                  <CardDescription>把研究模板、验证门、执行安全门和自动化策略压成一块，避免你只看到推荐结果，却不知道它是按什么规则得出来的。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>研究范围：{readText(configuration.research_scope, "当前还没有研究范围摘要")}</p>
                  <p>研究 / dry-run 候选池：{candidateScopeCandidateSymbols.length ? candidateScopeCandidateSymbols.join(" / ") : readText(configuration.candidate_pool, workspace.whitelist.join(" / ") || "当前未设置")}</p>
                  <p>验证策略：{readText(configuration.validation_policy, "当前还没有验证策略摘要")}</p>
                  <p>live 子集：{candidateScopeLiveSymbols.length ? candidateScopeLiveSymbols.join(" / ") : executionAllowedSymbols.length ? executionAllowedSymbols.join(" / ") : "当前未设置"}</p>
                  <p>范围契约：{candidateScopeDetail}</p>
                  <p>执行策略：{readText(configuration.execution_policy, "当前还没有执行策略摘要")}</p>
                  <p>门槛策略：{readText(configuration.threshold_policy, "当前还没有门槛策略摘要")}</p>
                  <p>自动化策略：{readText(configuration.automation_policy, "当前还没有自动化策略摘要")}</p>
                </CardContent>
              </Card>

              <WorkbenchConfigCard
                title="执行安全门配置"
                description="研究推荐出来的币会先走研究 / dry-run 候选池；这里只有更严格的 live 子集、单笔金额和最大开仓数。"
                scope="execution"
                returnTo={focusSymbol ? `/strategies?symbol=${encodeURIComponent(focusSymbol)}` : "/strategies"}
              >
                <ConfigField label="live_allowed_symbols" hint="只有这里勾选的币，才允许继续自动小额 live。">
                  <ConfigCheckboxGrid name="live_allowed_symbols" options={executionSymbolOptions} />
                </ConfigField>
                <ConfigField label="单笔 live 金额" hint="这里控制单次自动小额 live 最多能下多少 USDT。">
                  <ConfigInput
                    name="live_max_stake_usdt"
                    type="number"
                    min={0.1}
                    step={0.1}
                    defaultValue={readText(executionPolicy.live_max_stake_usdt, "6")}
                  />
                </ConfigField>
                <ConfigField label="最大同时开仓数" hint="这里控制自动 live 同时最多保留多少个打开中的仓位。">
                  <ConfigInput
                    name="live_max_open_trades"
                    type="number"
                    min={1}
                    max={20}
                    step={1}
                    defaultValue={readText(executionPolicy.live_max_open_trades, "1")}
                  />
                </ConfigField>
              </WorkbenchConfigCard>

              <Card>
                <CardHeader>
                  <p className="eyebrow">账户收口</p>
                  <CardTitle>执行之后，回到同一套真实来源上看结果</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>source: {workspace.account_state.source} / truth source: {workspace.account_state.truth_source}</p>
                  <p>余额：{workspace.account_state.summary.balance_count}，可交易：{workspace.account_state.summary.tradable_balance_count}，零头：{workspace.account_state.summary.dust_count}</p>
                  <p>订单：{workspace.account_state.summary.order_count}，持仓：{workspace.account_state.summary.position_count}</p>
                  <p>
                    最近余额：{formatLatestBalance(workspace.account_state.latest_balance)}
                    {"，最近订单："}
                    {formatLatestOrder(workspace.account_state.latest_order)}
                    {"，最近持仓："}
                    {formatLatestPosition(workspace.account_state.latest_position)}
                  </p>
                  <p>
                    当前研究跟进：{readText(alignmentDetails.research_symbol, "当前还没有推荐币")} / {readText(alignmentDetails.research_action, "continue_research")}
                  </p>
                  <p>
                    订单回填：{readText(alignmentDetails.order_backfill_state, "无结果")}，{readText(alignmentDetails.order_backfill_detail, "当前轮还没有订单回填")}
                  </p>
                  <p>
                    持仓回填：{readText(alignmentDetails.position_backfill_state, "无结果")}，{readText(alignmentDetails.position_backfill_detail, "当前轮还没有持仓回填")}
                  </p>
                  <p>
                    同步回填：{readText(alignmentDetails.sync_backfill_state, "无结果")}，{readText(alignmentDetails.sync_backfill_detail, "当前还没有同步结果回填")}
                  </p>
                  <p>差异一句话：{readText(stageDecisionSummary.execution_gap, "当前还没有研究和执行差异摘要。")}</p>
                  <div className="action-grid">
                    <Button asChild variant="outline">
                      <Link href="/balances">去余额页</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/orders">去订单页</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/positions">去持仓页</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">执行动作</p>
                  <CardTitle>这些动作控制的是整台执行器</CardTitle>
                  <CardDescription>推荐顺序：先启动，再派发。当前阶段固定控制整台 Freqtrade 执行器。</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="action-grid">
                    <ActionForm action="start_strategy" label="启动策略" focusSymbol={focusSymbol} />
                    <ActionForm action="pause_strategy" label="暂停策略" focusSymbol={focusSymbol} />
                    <ActionForm action="stop_strategy" label="停止策略" focusSymbol={focusSymbol} />
                    <ActionForm action="dispatch_latest_signal" label="派发最新信号" focusSymbol={focusSymbol} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">候选池摘要</p>
                  <CardTitle>研究 / dry-run 和 live 用的是两层口径</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>{candidateScopeHeadline}</p>
                  <p>当前队列摘要：{priorityHeadline}</p>
                  <p>研究 / dry-run 候选池：{(candidateScopeCandidateSymbols.length ? candidateScopeCandidateSymbols : candidateSymbols.length ? candidateSymbols : workspace.whitelist).join(" / ")}</p>
                  <p>live 子集：{candidateScopeLiveSymbols.length ? candidateScopeLiveSymbols.join(" / ") : executionAllowedSymbols.length ? executionAllowedSymbols.join(" / ") : "当前未设置"}</p>
                  <p>下一步：{candidateScopeNextStep}</p>
                </CardContent>
              </Card>
            </aside>
          </section>

          <section className="grid gap-5 lg:grid-cols-2 lg:items-start">
            <DataTable
              columns={["Strategy", "Symbol", "Status", "Generated"]}
              rows={workspace.recent_signals.map((item, index) => ({
                id: String(item.signal_id ?? index),
                cells: [
                  String(item.strategy_id ?? "n/a"),
                  String(item.symbol ?? ""),
                  <StatusBadge key={String(item.signal_id ?? index)} value={String(item.status ?? "")} />,
                  String(item.generated_at ?? ""),
                ],
              }))}
              emptyTitle="最近信号"
              emptyDetail="还没有新的持久化 signal 时，可以先看上面的当前判断卡片。"
            />

            <DataTable
              columns={["Symbol", "Side", "Type", "Status"]}
              rows={workspace.recent_orders.map((item, index) => ({
                id: String(item.id ?? index),
                cells: [
                  String(item.symbol ?? ""),
                  String(item.side ?? ""),
                  String(item.orderType ?? item.order_type ?? ""),
                  <StatusBadge key={String(item.id ?? index)} value={String(item.status ?? "")} />,
                ],
              }))}
              emptyTitle="最近执行结果"
              emptyDetail="先启动策略并派发最新信号，再回到这里确认执行链路有没有真正走通。"
            />
          </section>
        </>
      )}
    </AppShell>
  );
}

type ActionFormProps = {
  action: string;
  label: string;
  focusSymbol: string;
};

function ActionForm({ action, label, focusSymbol }: ActionFormProps) {
  const returnTo = focusSymbol ? `/strategies?symbol=${encodeURIComponent(focusSymbol)}` : "/strategies";

  return (
    <form action="/actions" method="post" className="action-card">
      <input type="hidden" name="action" value={action} />
      <input type="hidden" name="strategyId" value="1" />
      <input type="hidden" name="returnTo" value={returnTo} />
      <FormSubmitButton
        type="submit"
        variant={action === "dispatch_latest_signal" ? "terminal" : "outline"}
        idleLabel={label}
        pendingLabel={`${label}运行中…`}
        pendingHint="执行动作已提交，页面会在状态返回后自动刷新。"
      />
      <p>{focusSymbol ? `当前跟进对象：${focusSymbol}。` : ""}把控制动作统一走控制平面，当前阶段固定控制整台执行器。</p>
    </form>
  );
}

function readQueryText(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return String(value[0] ?? "").trim();
  }
  return String(value ?? "").trim();
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
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function AutomationInfo({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-3 text-sm font-medium leading-6 text-foreground">{value}</p>
    </div>
  );
}

function StrategyCard({ item }: { item: StrategyWorkspaceCard }) {
  const executionHint = formatExecutionHint(item.current_evaluation);
  return (
    <article className="action-card strategy-card">
      <div className="stack-xs">
        <p className="eyebrow">{item.key}</p>
        <h4>{item.display_name}</h4>
        <p>{item.description}</p>
      </div>
      <div className="stack-xs">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>运行状态：</span>
          <StatusBadge value={item.runtime_status} />
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>当前判断：</span>
          <StatusBadge value={String(item.current_evaluation.decision ?? "unknown")} />
        </div>
        <p>研究分数：{formatResearchScore(item.research_summary.score)}</p>
        <p>模型版本：{item.research_summary.model_version || "暂无训练产物"}</p>
        <p>研究解释：{item.research_summary.explanation || "暂无研究解释"}</p>
        <p>推荐策略：{formatPreferredStrategy(item.research_cockpit.recommended_strategy)}</p>
        <p>执行建议：{executionHint}</p>
        <p>观察币种：{item.symbols.join(" / ")}</p>
        <p>参数摘要：{formatParamSummary(item.default_params)}</p>
        <p>最近信号：{formatLatestSignal(item.latest_signal)}</p>
      </div>
    </article>
  );
}

function formatParamSummary(params: Record<string, unknown>): string {
  return Object.entries(params)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" · ");
}

function formatLatestSignal(item: Record<string, unknown> | null): string {
  if (!item) {
    return "暂无持久化信号";
  }
  return `${String(item.symbol ?? "")} / ${String(item.status ?? "")}`;
}

function formatTargetPage(targetPage: string): string {
  const labels: Record<string, string> = {
    "/research": "研究页",
    "/tasks": "任务页",
    "/strategies": "策略页",
    "/evaluation": "评估页",
  };
  return labels[targetPage] ?? targetPage;
}

function formatResearchScore(value: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : "暂无研究分数";
}

function formatExecutionHint(item: Record<string, unknown>): string {
  const decision = String(item.decision ?? "").trim();
  if (decision === "signal") {
    return "可以继续看最新信号并决定是否派发。";
  }
  if (decision === "watch") {
    return "先保持观察，暂时不要派发。";
  }
  if (decision === "block") {
    return "当前不适合执行，先不要派发。";
  }
  return "先确认执行器状态和最新信号。";
}

function formatPreferredStrategy(value: StrategyWorkspaceCard["research_cockpit"]["recommended_strategy"]): string {
  if (value === "trend_breakout") {
    return "趋势突破";
  }
  if (value === "trend_pullback") {
    return "趋势回调";
  }
  return "继续观察";
}

function formatLatestBalance(item: WorkspaceAccountState["latest_balance"]): string {
  if (!item) {
    return "暂无余额";
  }
  return `${String(item.asset ?? "")} / ${String(item.tradeStatus ?? "")}`;
}

function formatLatestOrder(item: WorkspaceAccountState["latest_order"]): string {
  if (!item) {
    return "暂无订单";
  }
  return `${String(item.symbol ?? "")} / ${String(item.status ?? "")}`;
}

function formatLatestPosition(item: WorkspaceAccountState["latest_position"]): string {
  if (!item) {
    return "暂无持仓";
  }
  return `${String(item.symbol ?? "")} / ${String(item.side ?? "")}`;
}
