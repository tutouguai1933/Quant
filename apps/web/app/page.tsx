/* 这个文件负责渲染首页驾驶舱，精简版：移除冗余卡片，提升信息密度。 */
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AppShell } from "../components/app-shell";
import { FeedbackBanner } from "../components/feedback-banner";
import { PageHero } from "../components/page-hero";
import { StatusBar } from "../components/status-bar";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
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
  listRiskEvents,
  listSignals,
  listStrategies,
} from "../lib/api";

export default function HomePage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [signals, setSignals] = useState<Array<{ symbol?: string; status?: string }>>([]);
  const [orders, setOrders] = useState<Array<{ symbol?: string; status?: string; side?: string }>>([]);
  const [strategies, setStrategies] = useState<Array<{ status?: string }>>([]);
  const [riskEvents, setRiskEvents] = useState<Array<{ ruleName?: string }>>([]);
  const [researchRuntime, setResearchRuntime] = useState(getResearchRuntimeStatusFallback());
  const [evaluationWorkspace, setEvaluationWorkspace] = useState(getEvaluationWorkspaceFallback());
  const [automationStatus, setAutomationStatus] = useState(getAutomationStatusFallback().item);

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
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    Promise.allSettled([
      listSignals(controller.signal).then((res) => res.error ? [] : res.data.items),
      listOrders(controller.signal).then((res) => res.error ? [] : res.data.items),
      session.isAuthenticated && session.token
        ? listStrategies(session.token, controller.signal).then((res) => res.error ? [] : res.data.items)
        : Promise.resolve([]),
      session.isAuthenticated && session.token
        ? listRiskEvents(session.token, controller.signal).then((res) => res.error ? [] : res.data.items)
        : Promise.resolve([]),
      getResearchRuntimeStatus(controller.signal).then((res) => res.error ? getResearchRuntimeStatusFallback() : res.data.item),
      getEvaluationWorkspace(controller.signal).then((res) => res.error ? getEvaluationWorkspaceFallback() : res.data.item),
      session.isAuthenticated && session.token
        ? getAutomationStatus(session.token, controller.signal).then((res) => res.error ? getAutomationStatusFallback().item : res.data.item)
        : Promise.resolve(getAutomationStatusFallback().item),
    ])
      .then(([signalsRes, ordersRes, strategiesRes, risksRes, runtimeRes, evalRes, autoRes]) => {
        clearTimeout(timeoutId);
        if (signalsRes.status === "fulfilled") setSignals(signalsRes.value);
        if (ordersRes.status === "fulfilled") setOrders(ordersRes.value);
        if (strategiesRes.status === "fulfilled") setStrategies(strategiesRes.value);
        if (risksRes.status === "fulfilled") setRiskEvents(risksRes.value);
        if (runtimeRes.status === "fulfilled") setResearchRuntime(runtimeRes.value);
        if (evalRes.status === "fulfilled") setEvaluationWorkspace(evalRes.value);
        if (autoRes.status === "fulfilled") setAutomationStatus(autoRes.value);
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
  }, [session.isAuthenticated, session.token]);

  const latestSignal = signals[0];
  const latestOrder = orders[0];
  const latestStrategy = strategies[0];
  const latestRisk = riskEvents[0];

  const researchHref = session.isAuthenticated ? "/research" : "/login?next=%2Fresearch";
  const evaluationHref = session.isAuthenticated ? "/evaluation" : "/login?next=%2Fevaluation";
  const strategiesHref = session.isAuthenticated ? "/strategies" : "/login?next=%2Fstrategies";
  const tasksHref = session.isAuthenticated ? "/tasks" : "/login?next=%2Ftasks";

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
  const researchValue = latestSignal?.symbol ?? normalizeStageLabel(researchStatus);

  const executionStatus = latestStrategy?.status || (session.isAuthenticated ? "idle" : "需登录");
  const executionValue = latestOrder?.symbol ?? executionStatus;

  const riskValue = latestRisk?.ruleName ?? (session.isAuthenticated ? "无风险" : "需登录");

  const automationMode = automationStatus.mode || "manual";
  const automationValue = automationStatus.paused ? "已暂停" : automationStatus.manualTakeover ? "人工接管" : automationMode;

  return (
    <AppShell
      title="驾驶舱"
      subtitle="快速决策入口，显示当前状态和下一步动作"
      currentPath="/"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="决策优先"
        title={`当前推荐：${currentRecommendationSymbol}`}
        description={automationHandoff.headline}
      />

      {isLoading ? (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-32 rounded-xl" />
        </div>
      ) : (
        <>
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
        </>
      )}
    </AppShell>
  );
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