/* 这个文件负责渲染首页驾驶舱，精简版：移除冗余卡片，提升信息密度。 */

import Link from "next/link";
import { AppShell } from "../components/app-shell";
import { ApiErrorFallback } from "../components/api-error-fallback";
import { FeedbackBanner } from "../components/feedback-banner";
import { PageHero } from "../components/page-hero";
import { StatusBar } from "../components/status-bar";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { buildAutomationHandoffSummary } from "../lib/automation-handoff";
import { readFeedback } from "../lib/feedback";
import {
  DEFAULT_API_TIMEOUT,
  getAutomationStatus,
  getAutomationStatusFallback,
  getEvaluationWorkspace,
  getEvaluationWorkspaceFallback,
  getResearchRuntimeStatus,
  getResearchRuntimeStatusFallback,
  listOrders,
  listRiskEvents,
  listSignals,
  listStrategies,
} from "../lib/api";
import { getControlSessionState } from "../lib/session";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function HomePage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { token, isAuthenticated } = session;
  const feedback = readFeedback(params);

  const [signals, orders, strategies, riskEvents, researchRuntime, evaluationWorkspace, automationStatus] = await Promise.all([
    safeLoad((signal) => listSignals(signal), []),
    safeLoad((signal) => listOrders(signal), []),
    isAuthenticated ? safeLoad((signal) => listStrategies(token, signal), []) : Promise.resolve([]),
    isAuthenticated ? safeLoad((signal) => listRiskEvents(token, signal), []) : Promise.resolve([]),
    safeLoadItem((signal) => getResearchRuntimeStatus(signal), getResearchRuntimeStatusFallback()),
    safeLoadItem((signal) => getEvaluationWorkspace(signal), getEvaluationWorkspaceFallback()),
    isAuthenticated
      ? safeLoadItem((signal) => getAutomationStatus(token, signal), getAutomationStatusFallback().item)
      : Promise.resolve(getAutomationStatusFallback().item),
  ]);

  const hasApiErrors = signals.length === 0 && orders.length === 0 && (isAuthenticated && strategies.length === 0);

  const latestSignal = signals[0];
  const latestOrder = orders[0];
  const latestStrategy = strategies[0];
  const latestRisk = riskEvents[0];

  const researchHref = isAuthenticated ? "/research" : "/login?next=%2Fresearch";
  const evaluationHref = isAuthenticated ? "/evaluation" : "/login?next=%2Fevaluation";
  const strategiesHref = isAuthenticated ? "/strategies" : "/login?next=%2Fstrategies";
  const tasksHref = isAuthenticated ? "/tasks" : "/login?next=%2Ftasks";

  const currentRecommendationSymbol = evaluationWorkspace.overview.recommended_symbol || latestSignal?.symbol || "无推荐";
  const arbitration = asRecord(automationStatus.arbitration);
  const suggestedAction = asRecord(arbitration.suggested_action);

  const automationHandoff = buildAutomationHandoffSummary({
    automation: automationStatus,
    tasksHref,
    fallbackTargetHref: readText(suggestedAction, "target_page", researchHref),
    fallbackTargetLabel: readText(suggestedAction, "label", "按当前建议继续"),
    fallbackHeadline: readText(arbitration, "headline", "当前还没有自动化仲裁结论"),
    fallbackDetail: readText(arbitration, "detail", "先看研究、执行和任务状态，再决定下一步。"),
  });

  const researchStatus = researchRuntime.status || "idle";
  const researchValue = latestSignal ? latestSignal.symbol : normalizeStageLabel(researchStatus);

  const executionStatus = latestStrategy?.status || (isAuthenticated ? "idle" : "需登录");
  const executionValue = latestOrder ? `${latestOrder.symbol}` : executionStatus;

  const riskValue = latestRisk ? latestRisk.ruleName : (isAuthenticated ? "无风险" : "需登录");

  const automationMode = automationStatus.mode || "manual";
  const automationValue = automationStatus.paused ? "已暂停" : automationStatus.manualTakeover ? "人工接管" : automationMode;

  return (
    <AppShell
      title="驾驶舱"
      subtitle="快速决策入口，显示当前状态和下一步动作"
      currentPath="/"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      {hasApiErrors && (
        <ApiErrorFallback
          title="部分数据加载失败"
          message="后端 API 暂时不可用，当前显示降级数据"
          detail="驾驶舱正在使用本地 fallback 数据，请稍后刷新页面重试。"
        />
      )}

      <PageHero
        badge="决策优先"
        title={`当前推荐：${currentRecommendationSymbol}`}
        description={automationHandoff.headline}
      />

      <StatusBar
        items={[
          {
            label: "研究",
            value: researchValue,
            status: researchStatus === "running" ? "running" : researchStatus === "completed" ? "success" : "waiting",
            detail: latestSignal ? `最新候选` : "等待研究",
          },
          {
            label: "执行",
            value: executionValue,
            status: latestOrder ? "success" : executionStatus === "running" ? "running" : "waiting",
            detail: latestOrder ? `最近订单` : "等待执行",
          },
          {
            label: "风险",
            value: riskValue,
            status: latestRisk ? "error" : "safe",
            detail: latestRisk ? "需要处理" : "无风险事件",
          },
          {
            label: "自动化",
            value: automationValue,
            status: automationStatus.paused || automationStatus.manualTakeover ? "waiting" : "active",
            detail: automationHandoff.runtimeHeadline,
          },
        ]}
      />

      <Card>
        <CardHeader>
          <CardTitle>下一步动作</CardTitle>
          <CardDescription>{automationHandoff.detail.replaceAll("候选池", "候选篮子").replaceAll("live 子集", "执行篮子")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button asChild variant="terminal">
            <Link href={automationHandoff.targetHref || researchHref}>
              {automationHandoff.targetLabel || "按当前建议继续"}
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={evaluationHref}>去评估中心</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={strategiesHref}>去策略页</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={tasksHref}>去任务页</Link>
          </Button>
          <Button asChild variant="secondary">
            <Link href="/signals">查看研究报告</Link>
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <p className="eyebrow">研究状态</p>
            <CardTitle>{researchValue}</CardTitle>
            <CardDescription>
              {researchRuntime.message || "当前没有研究任务在运行"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>当前阶段：{normalizeStageLabel(researchRuntime.current_stage)}</p>
            <p>进度：{researchRuntime.progress_pct}%</p>
            <p>信号数量：{signals.length}</p>
            <div className="pt-2">
              <Button asChild variant="outline" size="sm">
                <Link href={researchHref}>去研究工作台</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <p className="eyebrow">执行状态</p>
            <CardTitle>{executionValue}</CardTitle>
            <CardDescription>
              {latestOrder ? `${latestOrder.status} / ${latestOrder.side}` : "等待执行确认"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>执行器：{latestStrategy?.status || "未启动"}</p>
            <p>订单数量：{orders.length}</p>
            <p>候选篮子：{evaluationWorkspace.overview.candidate_count || 0} 个</p>
            <div className="pt-2">
              <Button asChild variant="outline" size="sm">
                <Link href={strategiesHref}>去策略页</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {(latestRisk || automationStatus.alerts.length > 0) && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader>
            <p className="eyebrow">风险与告警</p>
            <CardTitle>{latestRisk ? latestRisk.ruleName : `${automationStatus.alerts.length} 个告警`}</CardTitle>
            <CardDescription>
              {latestRisk ? `最近风险事件` : automationStatus.alerts[0]?.message || "需要关注"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link href={tasksHref}>去任务页处理</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </AppShell>
  );
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
  loader: (signal: AbortSignal) => Promise<{ data: { item: T }; error: unknown }>,
  fallback: T,
  timeoutMs = DEFAULT_API_TIMEOUT,
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

function createTimeoutController(timeoutMs: number) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cleanup: () => clearTimeout(timer),
  };
}

function readText(record: Record<string, unknown>, key: string, fallback: string) {
  const value = record[key];
  if (value === null || value === undefined) {
    return fallback;
  }
  const normalized = String(value).trim();
  return normalized.length ? normalized : fallback;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function normalizeStageLabel(value: string) {
  const normalized = value.trim();
  if (!normalized) {
    return "空闲";
  }
  return normalized.replaceAll("_", " ");
}
