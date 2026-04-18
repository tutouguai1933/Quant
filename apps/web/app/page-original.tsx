/* 这个文件负责渲染首页驾驶舱，并把研究、执行、异常动作统一收进首页主动作区。 */

import { AppShell } from "../components/app-shell";
import { FeedbackBanner } from "../components/feedback-banner";
import { HomePrimaryActionSection } from "../components/home-primary-action-section";
import { HomeWorkbenchGrid, type HomeWorkbenchCardItem } from "../components/home-workbench-grid";
import { MetricGrid } from "../components/metric-grid";
import { PageHero } from "../components/page-hero";
import { buildAutomationHandoffSummary } from "../lib/automation-handoff";
import { readFeedback } from "../lib/feedback";
import {
  getAutomationStatus,
  getAutomationStatusFallback,
  getEvaluationWorkspace,
  getEvaluationWorkspaceFallback,
  getResearchRuntimeStatus,
  getResearchRuntimeStatusFallback,
  listOrders,
  listPositions,
  listRiskEvents,
  listSignals,
  listStrategies,
  listTasks,
} from "../lib/api";
import { getControlSessionState } from "../lib/session";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

/* 渲染首页驾驶舱。 */
export default async function HomePage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { token, isAuthenticated } = session;
  const feedback = readFeedback(params);
  const [signals, orders, positions, strategies, tasks, riskEvents, researchRuntime, evaluationWorkspace, automationStatus] = await Promise.all([
    safeLoad((signal) => listSignals(signal), []),
    safeLoad((signal) => listOrders(signal), []),
    safeLoad((signal) => listPositions(signal), []),
    isAuthenticated ? safeLoad((signal) => listStrategies(token, signal), []) : Promise.resolve([]),
    isAuthenticated ? safeLoad((signal) => listTasks(token, signal), []) : Promise.resolve([]),
    isAuthenticated ? safeLoad((signal) => listRiskEvents(token, signal), []) : Promise.resolve([]),
    safeLoadItem((signal) => getResearchRuntimeStatus(signal), getResearchRuntimeStatusFallback()),
    safeLoadItem((signal) => getEvaluationWorkspace(signal), getEvaluationWorkspaceFallback()),
    isAuthenticated
      ? safeLoadItem((signal) => getAutomationStatus(token, signal), getAutomationStatusFallback().item)
      : Promise.resolve(getAutomationStatusFallback().item),
  ]);

  const latestSignal = signals[0];
  const latestOrder = orders[0];
  const latestPosition = positions[0];
  const latestTask = tasks[0];
  const latestRisk = riskEvents[0];
  const latestStrategy = strategies[0];
  const researchHref = isAuthenticated ? "/research" : "/login?next=%2Fresearch";
  const evaluationHref = isAuthenticated ? "/evaluation" : "/login?next=%2Fevaluation";
  const strategiesHref = isAuthenticated ? "/strategies" : "/login?next=%2Fstrategies";
  const riskHref = isAuthenticated ? "/risk" : "/login?next=%2Frisk";
  const tasksHref = isAuthenticated ? "/tasks" : "/login?next=%2Ftasks";
  const successValue = latestSignal ? `最新候选：${latestSignal.symbol}` : "先生成最新研究候选";
  const successDetail = latestSignal ? "研究结果已经回到首页，先看统一研究报告，再决定是否推进策略。" : "现在还没有研究结果，先从研究动作开始。";
  const executionValue = latestStrategy ? `执行器：${latestStrategy.status}` : isAuthenticated ? "等待执行确认" : "登录后查看执行";
  const executionDetail = latestStrategy ? "如果研究已经确认，可以从执行入口启动策略或派发信号。" : isAuthenticated ? "执行器还没进入运行态，先确认候选再决定是否推进。" : "登录后再进入执行链。";
  const exceptionValue = latestRisk ? `风险：${latestRisk.ruleName}` : latestTask ? `任务：${latestTask.taskType}` : "当前没有新阻塞";
  const exceptionDetail = latestRisk ? "如果要处理风险或失败任务，异常入口统一从主动作区展开。" : latestTask ? "最近任务还在首页可见，需要时可直接下钻到任务页。" : "当前没有新风险事件，异常入口保留给按需检查。";
  const nextStepValue = latestSignal ? "先复核候选，再决定是否执行" : "先运行研究动作";
  const nextStepDetail = latestSignal ? "先看研究报告和市场页，再决定是否启动策略。" : "首页默认先把研究跑起来，再进入后续页面。";
  const arbitration = asRecord(automationStatus.arbitration);
  const suggestedAction = asRecord(arbitration.suggested_action);
  const blockingItems = Array.isArray(arbitration.blocking_items) ? arbitration.blocking_items.filter((item) => item && typeof item === "object") : [];
  const currentRecommendationSymbol = evaluationWorkspace.overview.recommended_symbol || latestSignal?.symbol || "当前还没有明确推荐";
  const currentRecommendationAction = evaluationWorkspace.overview.recommended_action || readText(arbitration, "headline", "先回研究链继续确认候选");
  const automationHeadline = readText(arbitration, "headline", "当前还没有自动化仲裁结论");
  const automationDetail = readText(arbitration, "detail", "先看研究、执行和任务状态，再决定下一步。");
  const automationHandoff = buildAutomationHandoffSummary({
    automation: automationStatus,
    tasksHref,
    fallbackTargetHref: readText(suggestedAction, "target_page", researchHref),
    fallbackTargetLabel: readText(suggestedAction, "label", "按当前建议继续"),
    fallbackHeadline: automationHeadline,
    fallbackDetail: automationDetail,
  });
  const topAlert = automationStatus.alerts[0];
  const topAlertLabel = topAlert ? `${topAlert.level} / ${topAlert.code}` : latestRisk ? latestRisk.ruleName : "当前没有新告警";
  const topAlertDetail = topAlert ? topAlert.message : latestRisk ? `最近规则：${latestRisk.ruleName}` : "当前没有新风险事件。";
  const nextActionTargetPath = automationHandoff.targetHref || readText(suggestedAction, "target_page", researchHref);
  const nextActionHref = nextActionTargetPath;
  const homeWorkbenchCards: HomeWorkbenchCardItem[] = [
    {
      id: "recommendation",
      eyebrow: "推荐",
      title: "当前推荐",
      summary: currentRecommendationSymbol,
      detail: `${currentRecommendationAction}。${evaluationWorkspace.candidate_scope.detail || "先确认候选篮子，再决定是否继续推进。"}`
        .replaceAll("候选池", "候选篮子")
        .replaceAll("live 子集", "执行篮子"),
      triggerLabel: "查看推荐详情",
      drawerTitle: "查看推荐详情",
      drawerDescription: "这里集中展示当前最值得看的候选、推荐动作和候选范围说明。",
      drawerNotes: [
        (evaluationWorkspace.candidate_scope.headline || "当前还没有统一候选篮子摘要。").replaceAll("候选池", "候选篮子").replaceAll("live 子集", "执行篮子"),
        `当前主线：${(evaluationWorkspace.candidate_scope.next_step || "先去评估与实验中心看当前推荐和阻塞。").replaceAll("候选池", "候选篮子").replaceAll("live 子集", "执行篮子")}`,
      ],
      digests: [
        { label: "当前推荐标的", value: currentRecommendationSymbol, detail: "这是首页当前最先建议你看的候选。" },
        { label: "推荐动作", value: currentRecommendationAction, detail: "先按这个动作判断要不要继续推进。" },
        { label: "候选篮子", value: String(evaluationWorkspace.overview.candidate_count), detail: "当前评估视图里仍保留在候选篮子里的标的数量。" },
        {
          label: "执行篮子",
          value: (evaluationWorkspace.candidate_scope.live_summary || "当前未配置").replaceAll("live 子集", "执行篮子"),
          detail: "已经够格继续进入执行链的更严格候选摘要。",
        },
      ],
      links: [
        { href: evaluationHref, label: "去评估与实验中心", variant: "terminal" },
        { href: "/market", label: "去市场页筛选目标" },
        { href: "/signals", label: "回到信号页看研究报告" },
      ],
    },
    {
      id: "research",
      eyebrow: "研究",
      title: "当前研究状态",
      summary: `${normalizeStageLabel(researchRuntime.status)} / ${normalizeStageLabel(researchRuntime.current_stage)}`,
      detail: researchRuntime.message || "当前没有研究任务在运行。",
      triggerLabel: "查看研究详情",
      drawerTitle: "查看研究详情",
      drawerDescription: "研究运行状态、进度和结果去向都统一收在这里。",
      drawerNotes: [
        researchRuntime.started_at ? `开始时间：${researchRuntime.started_at}` : "当前没有正在运行的研究任务。",
        researchRuntime.finished_at ? `最近完成时间：${researchRuntime.finished_at}` : "最近还没有完成时间记录。",
      ],
      digests: [
        { label: "当前动作", value: researchRuntime.action || "当前没有动作", detail: "研究链当前正在处理哪类动作。" },
        { label: "当前阶段", value: normalizeStageLabel(researchRuntime.current_stage), detail: "研究任务现在停在哪个阶段。" },
        { label: "当前进度", value: `${researchRuntime.progress_pct}%`, detail: "这是当前研究任务已经推进到的百分比。" },
        { label: "结果去向", value: researchRuntime.result_paths.join(" / ") || "/research / /evaluation / /signals", detail: "研究结果会回到这些页面继续承接。" },
      ],
      links: [
        { href: researchHref, label: "回到研究工作台", variant: "terminal" },
        { href: "/signals", label: "回到信号页看研究报告" },
        { href: evaluationHref, label: "去评估与实验中心" },
      ],
    },
    {
      id: "execution",
      eyebrow: "执行",
      title: "当前执行状态",
      summary: executionValue,
      detail: latestOrder ? `最近订单：${latestOrder.symbol} / ${latestOrder.status}` : executionDetail,
      triggerLabel: "查看执行详情",
      drawerTitle: "查看执行详情",
      drawerDescription: "执行器状态、最近订单和持仓回看都统一放在这里。",
      drawerNotes: [
        latestStrategy ? `执行器当前状态：${latestStrategy.status}` : "当前还没有执行器状态，先登录后查看。",
        latestPosition ? `最近持仓：${latestPosition.symbol} / ${latestPosition.side}` : "当前还没有持仓记录。",
      ],
      digests: [
        { label: "执行器状态", value: executionValue, detail: executionDetail },
        { label: "最近订单", value: latestOrder ? `${latestOrder.symbol} / ${latestOrder.status}` : "当前没有订单", detail: "先看最近一笔执行反馈。" },
        { label: "最近持仓", value: latestPosition ? `${latestPosition.symbol} / ${latestPosition.side}` : "当前没有持仓", detail: "如果已经建仓，会先在这里回看状态。" },
        { label: "订单数量", value: String(orders.length), detail: "当前首页已经拉回来的订单数量。" },
      ],
      links: [
        { href: strategiesHref, label: "去策略页确认执行", variant: "terminal" },
        { href: "/orders", label: "去订单页" },
        { href: "/positions", label: "去持仓页" },
        { href: "/balances", label: "去余额页" },
      ],
    },
    {
      id: "risk",
      eyebrow: "风险",
      title: "当前风险与告警",
      summary: topAlertLabel,
      detail: topAlertDetail,
      triggerLabel: "查看风险详情",
      drawerTitle: "查看风险详情",
      drawerDescription: "头号告警、最近任务和当前处理建议都集中放在这里。",
      drawerNotes: [
        readText(automationStatus.controlMatrix, "primary_action_detail", "当前没有控制矩阵建议时，先回任务页确认恢复步骤。"),
        latestTask ? `最近任务：${latestTask.taskType} / ${latestTask.status}` : "当前没有新任务。",
      ],
      digests: [
        { label: "头号告警", value: topAlertLabel, detail: topAlertDetail },
        { label: "告警数量", value: String(automationStatus.alerts.length), detail: "当前自动化状态里累计的告警数量。" },
        { label: "最近任务", value: latestTask ? `${latestTask.taskType} / ${latestTask.status}` : "当前没有新任务", detail: "最近一条任务会先在这里回看。" },
        { label: "处理建议", value: readText(automationStatus.controlMatrix, "primary_action_label", "先看任务页"), detail: "先按这条建议决定要不要继续自动化。" },
      ],
      links: [
        { href: riskHref, label: "查看风险事件", variant: "terminal" },
        { href: tasksHref, label: "去任务页看自动化" },
      ],
    },
    {
      id: "next-action",
      eyebrow: "动作",
      title: "当前下一步动作",
      summary: automationHandoff.headline,
      detail: `当前主线：${automationHandoff.detail.replaceAll("候选池", "候选篮子").replaceAll("live 子集", "执行篮子")}`,
      triggerLabel: "查看下一步详情",
      drawerTitle: "查看下一步详情",
      drawerDescription: "这里把仲裁建议、目标页面和当前阻塞统一说明清楚。",
      drawerNotes: [
        automationHandoff.runtimeHeadline,
        `当前主线：${(evaluationWorkspace.candidate_scope.next_step || "先按仲裁建议决定下一页要去哪里。").replaceAll("候选池", "候选篮子").replaceAll("live 子集", "执行篮子")}`,
      ],
      digests: [
        { label: "建议动作", value: automationHandoff.targetLabel, detail: "这是当前自动化承接层给出的直接动作建议。" },
        { label: "目标页面", value: nextActionTargetPath, detail: "首页会优先把你送到这一页继续处理。" },
        { label: "推荐阶段", value: readText(arbitration, "recommended_stage", "research"), detail: "当前建议先继续处理哪一层。" },
        { label: "当前阻塞", value: automationHandoff.runtimeHeadline, detail: automationHandoff.runtimeDetail },
      ],
      links: [
        { href: nextActionHref, label: automationHandoff.targetLabel || "按当前建议继续", variant: "terminal" },
        { href: tasksHref, label: "去任务页看自动化" },
        { href: strategiesHref, label: "去策略页确认执行" },
        { href: evaluationHref, label: "去评估与实验中心" },
      ],
    },
    {
      id: "recent-results",
      eyebrow: "回看",
      title: "最近结果回看",
      summary: latestSignal ? `研究：${latestSignal.symbol}` : latestOrder ? `订单：${latestOrder.symbol}` : "当前还没有最近结果",
      detail: latestTask ? `最近任务：${latestTask.taskType} / ${latestTask.status}` : "研究、执行和任务最近一轮结果会先在这里回看。",
      triggerLabel: "查看回看详情",
      drawerTitle: "查看回看详情",
      drawerDescription: "把最近一轮研究、执行和任务结果统一收在这里，方便直接回看。",
      drawerNotes: [
        latestRisk ? `最近风险：${latestRisk.ruleName}` : "当前没有新风险事件。",
        latestOrder ? `最近订单状态：${latestOrder.status}` : "当前没有新订单反馈。",
      ],
      digests: [
        { label: "最近研究", value: latestSignal ? `${latestSignal.symbol} / ${latestSignal.status}` : "当前没有研究结果", detail: "最近一轮研究产出的候选会先在这里出现。" },
        { label: "最近订单", value: latestOrder ? `${latestOrder.symbol} / ${latestOrder.status}` : "当前没有订单", detail: "执行链最新一笔订单反馈。" },
        { label: "最近任务", value: latestTask ? `${latestTask.taskType} / ${latestTask.status}` : "当前没有任务", detail: "自动化和手动动作最近一条任务摘要。" },
        { label: "最近风险", value: latestRisk ? latestRisk.ruleName : "当前没有风险事件", detail: "如果有新阻塞，这里会先提示最近一条风险。" },
      ],
      links: [
        { href: "/signals", label: "回到信号页看研究报告", variant: "terminal" },
        { href: "/orders", label: "去订单页" },
        { href: tasksHref, label: "去任务页看自动化" },
        { href: "/positions", label: "去持仓页" },
      ],
    },
  ];

  return (
    <AppShell
      title="驾驶舱"
      subtitle="先看当前最佳判断，再决定是否进入图表、策略和执行。首页只保留最短的决策链。"
      currentPath="/"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="决策优先"
        title="先决定该跟哪个候选，再进入图表、策略和执行。"
        description="现在首页作为系统总览，不再堆很多说明卡，而是先告诉你研究有没有出结果、执行器是否可用、异常入口在哪里。"
        aside={
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <span className="text-sm font-medium text-foreground">市场：crypto</span>
              <span className="text-sm text-muted-foreground">研究：Qlib</span>
              <span className="text-sm text-muted-foreground">执行：Freqtrade</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <HeroDigest label="成功链路" value={successValue} />
              <HeroDigest label="异常链路" value={exceptionValue} />
            </div>
          </div>
        }
      />

      <MetricGrid
        items={[
          {
            label: "Signals",
            value: String(signals.length),
            detail: latestSignal ? `最新候选：${latestSignal.symbol}` : "还没有研究信号",
          },
          {
            label: "Execution",
            value: isAuthenticated ? strategies[0]?.status ?? "idle" : "需登录",
            detail: strategies[0] ? "执行器状态已回到首页" : "登录后查看执行器状态",
          },
          {
            label: "Orders",
            value: String(orders.length),
            detail: orders[0] ? `最新反馈：${orders[0].status}` : "还没有执行反馈",
          },
          {
            label: "Risk",
            value: isAuthenticated ? String(riskEvents.length) : "需登录",
            detail: latestRisk ? `最近规则：${latestRisk.ruleName}` : isAuthenticated ? "当前没有新风险事件" : "登录后查看风险事件",
          },
        ]}
      />

      <HomePrimaryActionSection
        successValue={successValue}
        successDetail={successDetail}
        executionValue={executionValue}
        executionDetail={executionDetail}
        exceptionValue={exceptionValue}
        exceptionDetail={exceptionDetail}
        nextStepValue={nextStepValue}
        nextStepDetail={nextStepDetail}
        researchHref={researchHref}
        evaluationHref={evaluationHref}
        strategiesHref={strategiesHref}
        riskHref={riskHref}
        tasksHref={tasksHref}
      />

      <HomeWorkbenchGrid cards={homeWorkbenchCards} />
    </AppShell>
  );
}

/* 渲染头图右侧的摘要块。 */
function HeroDigest({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
    </div>
  );
}

/* 带容错地读取列表数据。 */
async function safeLoad<T>(
  loader: (signal: AbortSignal) => Promise<{ data: { items: T[] }; error: unknown }>,
  fallback: T[],
  timeoutMs = 4000,
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

/* 带容错地读取单个对象数据。 */
async function safeLoadItem<T>(
  loader: (signal: AbortSignal) => Promise<{ data: { item: T }; error: unknown }>,
  fallback: T,
  timeoutMs = 4000,
): Promise<T> {
  const { signal, cleanup } = createTimeoutController(timeoutMs);
  try {
    const response = await loader(signal);
    return response.error ? fallback : response.data.item;
  } catch {
    return fallback;
  } finally {
    cleanup();
  }
}

/* 给首页数据读取加一个短超时，并在超时后真正取消底层请求。 */
function createTimeoutController(timeoutMs: number) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cleanup: () => clearTimeout(timer),
  };
}

/* 读取弱类型对象里的文本值。 */
function readText(record: Record<string, unknown>, key: string, fallback: string) {
  const value = record[key];
  if (value === null || value === undefined) {
    return fallback;
  }
  const normalized = String(value).trim();
  return normalized.length ? normalized : fallback;
}

/* 把未知值收成对象。 */
function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

/* 把运行阶段转成人能直接看懂的词。 */
function normalizeStageLabel(value: string) {
  const normalized = value.trim();
  if (!normalized) {
    return "空闲";
  }
  return normalized.replaceAll("_", " ");
}
