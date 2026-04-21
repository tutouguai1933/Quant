"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { PageHero } from "../../components/page-hero";
import { StatusBar } from "../../components/status-bar";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { buildAutomationHandoffSummary } from "../../lib/automation-handoff";
import {
  getAutomationStatus,
  getAutomationStatusFallback,
  getEvaluationWorkspace,
  getEvaluationWorkspaceFallback,
} from "../../lib/api";

type EvaluationClientProps = {
  token: string | null;
  isAuthenticated: boolean;
};

export function EvaluationClient({ token, isAuthenticated }: EvaluationClientProps) {
  const [workspace, setWorkspace] = useState(getEvaluationWorkspaceFallback());
  const [automation, setAutomation] = useState(getAutomationStatusFallback().item);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    Promise.allSettled([
      getEvaluationWorkspace(controller.signal),
      token ? getAutomationStatus(token, controller.signal) : Promise.resolve(null),
    ])
      .then(([workspaceResult, automationResult]) => {
        clearTimeout(timeoutId);

        // Always use available data, no degraded mode banner needed
        if (workspaceResult.status === "fulfilled" && workspaceResult.value?.data?.item) {
          setWorkspace(workspaceResult.value.data.item);
        }
        if (automationResult.status === "fulfilled" && automationResult.value?.data?.item) {
          setAutomation(automationResult.value.data.item);
        }
      })
      .catch(() => {
        clearTimeout(timeoutId);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [token]);

  const tasksHref = isAuthenticated ? "/tasks" : "/login?next=%2Ftasks";
  const overview = asRecord(workspace.overview);
  const candidateScope = asRecord(workspace.candidate_scope);
  const stageDecisionSummary = asRecord(workspace.stage_decision_summary);
  const recommendationExplanation = asRecord(workspace.recommendation_explanation);
  const eliminationExplanation = asRecord(workspace.elimination_explanation);
  const alignmentDetails = asRecord(workspace.alignment_details);
  const configAlignment = asRecord(workspace.config_alignment);

  const recommendedSymbol = readText(overview.recommended_symbol, "暂无推荐");
  const recommendedAction = readText(overview.recommended_action, "continue_research");
  const candidateCount = Number(overview.candidate_count ?? 0);
  const readyCount = Number(overview.ready_count ?? 0);
  const blockedCount = Number(overview.blocked_count ?? 0);

  const whyRecommended = readText(stageDecisionSummary.why_recommended, "暂无推荐原因");
  const whyEliminated = readText(stageDecisionSummary.why_eliminated, "暂无淘汰原因");
  const executionGap = readText(stageDecisionSummary.execution_gap, "暂无差异说明");
  const nextStep = readText(stageDecisionSummary.next_step, "continue_research");

  const recommendationDetail = readText(recommendationExplanation.detail, "暂无推荐说明");
  const eliminationDetail = readText(eliminationExplanation.detail, "暂无淘汰说明");

  const candidateScopeHeadline = readText(candidateScope.headline, "候选篮子覆盖研究与 dry-run");
  const candidateScopeDetail = readText(candidateScope.detail, "暂无候选范围说明");

  const researchSymbol = readText(alignmentDetails.research_symbol, "");
  const researchAction = readText(alignmentDetails.research_action, "");
  const configAlignmentStatus = readText(configAlignment.status, "unknown");
  const configAlignmentStaleFields = Array.isArray(configAlignment.stale_fields)
    ? configAlignment.stale_fields.map(String)
    : [];

  const automationHandoff = buildAutomationHandoffSummary({
    automation,
    tasksHref,
    fallbackTargetHref: "/research",
    fallbackTargetLabel: "回到研究",
    fallbackHeadline: "当前可以继续自动化",
    fallbackDetail: "",
  });

  const statusItems = [
    {
      label: "候选总数",
      value: String(candidateCount),
      status: (candidateCount > 0 ? "success" : "waiting") as "success" | "waiting",
      detail: `${readyCount} 可进入 dry-run`,
    },
    {
      label: "推荐标的",
      value: recommendedSymbol,
      status: (recommendedSymbol !== "暂无推荐" ? "success" : "waiting") as "success" | "waiting",
      detail: recommendedAction,
    },
    {
      label: "门控状态",
      value: `${readyCount} 通过 / ${blockedCount} 拦下`,
      status: (readyCount > 0 ? "success" : "waiting") as "success" | "waiting",
      detail: "门控判断",
    },
    {
      label: "自动化",
      value: automationHandoff.headline,
      status: (automation.manualTakeover ? "waiting" : "active") as "waiting" | "active",
      detail: automationHandoff.detail,
    },
  ];

  return (
    <>
      <PageHero
        badge="评估与实验中心"
        title="先看推荐，再看原因"
        description="评估页只做两件事：左边给你推荐和淘汰原因，右边给你候选队列和门控判断。"
      />

      <StatusBar items={statusItems} />

      <Card>
        <CardHeader>
          <p className="eyebrow">当前推荐</p>
          <CardTitle>{recommendedSymbol}</CardTitle>
          <CardDescription>推荐动作：{recommendedAction}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>推荐原因：{whyRecommended}</p>
          <p>淘汰原因：{whyEliminated}</p>
          <p>执行差异：{executionGap}</p>
          <p>下一步：{nextStep}</p>
          <div className="flex gap-2">
            <Button asChild variant="terminal" size="sm">
              <Link href="/strategies">去策略中心</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/research">回到研究</Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <p className="eyebrow">推荐原因</p>
            <CardTitle>为什么推荐 {recommendedSymbol}</CardTitle>
            <CardDescription>{whyRecommended}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
            <p>{recommendationDetail}</p>
            <div className="flex gap-2">
              <Button asChild variant="terminal" size="sm">
                <Link href="/strategies">去策略中心</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/research">回到研究</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <p className="eyebrow">淘汰原因</p>
            <CardTitle>为什么淘汰其他候选</CardTitle>
            <CardDescription>{whyEliminated}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
            <p>{eliminationDetail}</p>
            <p>被拦下：{blockedCount} 个候选</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <p className="eyebrow">候选范围契约</p>
          <CardTitle>候选篮子与执行篮子</CardTitle>
          <CardDescription>{candidateScopeHeadline}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>{candidateScopeDetail}</p>
          <p>候选总数：{candidateCount}</p>
          <p>可进入 dry-run：{readyCount}</p>
          <p>被拦下：{blockedCount}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <p className="eyebrow">研究结果 vs 执行结果</p>
          <CardTitle>当前差异到底卡在哪</CardTitle>
          <CardDescription>{executionGap}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>推荐标的：{recommendedSymbol}</p>
          <p>推荐动作：{recommendedAction}</p>
          <p>下一步：{nextStep}</p>
          {researchSymbol ? (
            <p>
              当前研究跟进：{researchSymbol} / {researchAction}
            </p>
          ) : null}
          {configAlignmentStatus === "stale" && configAlignmentStaleFields.length > 0 ? (
            <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-3">
              <p className="font-medium text-yellow-600 dark:text-yellow-400">配置漂移</p>
              <p className="mt-1 text-yellow-600/80 dark:text-yellow-400/80">
                检测到配置漂移：{configAlignmentStaleFields.join(", ")}
              </p>
            </div>
          ) : null}
          <p className="text-xs text-muted-foreground">订单回填、持仓回填和同步回填状态统一在策略页账户收口区查看。</p>
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/strategies">去策略中心</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/tasks">去任务页</Link>
            </Button>
          </div>
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
            <Link href="/research">研究工作台</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/features">因子工作台</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/signals">信号页</Link>
          </Button>
        </CardContent>
      </Card>
    </>
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
