/* 策略中心：精简版，提升信息密度 */

import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { ApiErrorFallback } from "../../components/api-error-fallback";
import { ArbitrationHandoffCard } from "../../components/arbitration-handoff-card";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { PageHero } from "../../components/page-hero";
import { StatusBar } from "../../components/status-bar";
import { StatusBadge } from "../../components/status-badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { buildAutomationHandoffSummary } from "../../lib/automation-handoff";
import { readFeedback } from "../../lib/feedback";
import {
  getAutomationStatus,
  getAutomationStatusFallback,
  getStrategyWorkspace,
  getStrategyWorkspaceFallback,
  isTechnicalError,
  type StrategyWorkspaceCard,
  type WorkspaceAccountState,
} from "../../lib/api";
import { getControlSessionState } from "../../lib/session";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function StrategiesPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { token, isAuthenticated } = session;
  const feedback = readFeedback(params);

  let workspace = getStrategyWorkspaceFallback();
  let automation = getAutomationStatusFallback().item;

  const [workspaceResult, automationResult] = await Promise.allSettled([
    token ? getStrategyWorkspace(token) : Promise.resolve(null),
    token ? getAutomationStatus(token) : Promise.resolve(null),
  ]);

  const hasApiErrors = [workspaceResult, automationResult].some(
    (result) => result.status === "rejected" || (result.status === "fulfilled" && result.value && isTechnicalError(result.value.error))
  );

  if (workspaceResult.status === "fulfilled" && workspaceResult.value && !workspaceResult.value.error) {
    workspace = workspaceResult.value.data;
  }
  if (automationResult.status === "fulfilled" && automationResult.value && !automationResult.value.error) {
    automation = automationResult.value.data.item;
  }

  const arbitration = asRecord(automation.arbitration);
  const arbitrationSuggestedAction = asRecord(arbitration.suggested_action);
  const tasksHref = isAuthenticated ? "/tasks" : "/login?next=%2Ftasks";

  const automationHandoff = buildAutomationHandoffSummary({
    automation,
    tasksHref,
    fallbackTargetHref: readText(arbitrationSuggestedAction.target_page, "/research"),
    fallbackTargetLabel: workspace.research_recommendation?.next_action || "先进入 dry-run 观察。",
    fallbackHeadline: readText(arbitration.headline, "当前自动化可以继续推进"),
    fallbackDetail: readText(arbitration.detail, "当前自动化可以继续推进"),
  });

  const executorRuntimeStatus = readText(workspace.executor_runtime.status, "ready");
  const executorRuntimeDetail = readText(workspace.executor_runtime.detail, "");
  const executorConnectionStatus = readText(workspace.executor_runtime.connection_status, "unknown");
  const executorStatusLabel = [
    workspace.executor_runtime.executor,
    workspace.executor_runtime.backend,
    workspace.executor_runtime.mode,
  ].filter(Boolean).join(" / ") || "未配置";

  const accountStateStatus = readText(workspace.account_state.status, "ready");
  const accountStateDetail = readText(workspace.account_state.detail, "");

  const recentSignals = Array.isArray(workspace.recent_signals) ? workspace.recent_signals : [];
  const recentOrders = Array.isArray(workspace.recent_orders) ? workspace.recent_orders : [];
  const strategyCards = Array.isArray(workspace.strategies) ? workspace.strategies : [];

  const isManualTakeover = Boolean(automation.manualTakeover);
  const takeoverReason = readText(automation.pauseReason, "");

  const statusItems = [
    {
      label: "执行器",
      value: executorRuntimeStatus === "unavailable" ? "不可用" : executorStatusLabel,
      status: (executorRuntimeStatus === "unavailable" ? "error" : "success") as "error" | "success",
      detail: executorRuntimeStatus === "unavailable" ? executorRuntimeDetail : executorConnectionStatus,
    },
    {
      label: "自动化",
      value: isManualTakeover ? "人工接管" : automationHandoff.headline,
      status: (isManualTakeover ? "error" : automation.paused ? "waiting" : "active") as "error" | "waiting" | "active",
      detail: isManualTakeover ? takeoverReason : automationHandoff.detail,
    },
    {
      label: "账户",
      value: accountStateStatus === "unavailable" ? "不可用" : `${workspace.account_state.summary.balance_count} 余额`,
      status: (accountStateStatus === "unavailable" ? "error" : "success") as "error" | "success",
      detail: accountStateStatus === "unavailable" ? accountStateDetail : `${workspace.account_state.summary.order_count} 订单 / ${workspace.account_state.summary.position_count} 持仓`,
    },
    {
      label: "最近信号",
      value: String(recentSignals.length),
      status: (recentSignals.length > 0 ? "active" : "waiting") as "active" | "waiting",
      detail: recentSignals.length > 0 ? "有新信号" : "暂无信号",
    },
  ];

  return (
    <AppShell
      title="策略"
      subtitle="策略中心先回答三件事：哪套策略在运行、它现在怎么看市场、最近有没有真正走到执行。"
      currentPath="/strategies"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      {hasApiErrors && (
        <ApiErrorFallback
          title="部分数据加载失败"
          message="后端 API 暂时不可用，当前显示降级数据"
          detail="策略页正在使用本地 fallback 数据，请稍后刷新页面重试。"
        />
      )}

      <PageHero
        badge="策略中心"
        title="先看判断，再决定要不要派发"
        description="左侧先看推荐执行、研究候选和下一步动作，右侧只看执行器状态、账户收口和执行动作。"
      />

      <ArbitrationHandoffCard
        arbitration={arbitration}
        isAuthenticated={isAuthenticated}
        surfaceLabel="策略页"
        showActions={!isAuthenticated}
      />

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
          <StatusBar items={statusItems} />

          <Card>
            <CardHeader>
              <p className="eyebrow">当前执行器状态</p>
              <CardTitle>执行器连接</CardTitle>
              <CardDescription>
                {executorRuntimeStatus === "unavailable" ? "执行器暂时不可用" : executorStatusLabel}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              <p>连接状态：{executorConnectionStatus}</p>
              {executorRuntimeStatus === "unavailable" ? (
                <p className="text-red-600 dark:text-red-400">当前异常：{executorRuntimeDetail || "先恢复执行器接口"}</p>
              ) : null}
              <p>最近信号：{recentSignals.length} 条</p>
              <p>最近订单：{recentOrders.length} 条</p>
            </CardContent>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <p className="eyebrow">当前推荐</p>
                <CardTitle>{workspace.research_recommendation?.symbol || "暂无推荐"}</CardTitle>
                <CardDescription>
                  {workspace.research_recommendation?.dry_run_gate?.status || "先完成研究和评估"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                <p>下一步动作：{automationHandoff.targetLabel || "继续观察"}</p>
                <div className="flex gap-2">
                  <Button asChild variant="terminal" size="sm">
                    <Link href={automationHandoff.targetHref}>{automationHandoff.targetLabel || "继续"}</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/research">回到研究</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <p className="eyebrow">执行状态</p>
                <CardTitle>最近执行结果</CardTitle>
                <CardDescription>
                  {recentOrders.length > 0 ? `${recentOrders.length} 条订单` : "暂无执行结果"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                <p>最近信号：{recentSignals.length} 条</p>
                <p>最近订单：{recentOrders.length} 条</p>
                <div className="flex gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link href="/signals">查看信号</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/orders">查看订单</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <p className="eyebrow">策略判断</p>
              <CardTitle>两套首批波段策略</CardTitle>
              <CardDescription>具体策略判断下沉到这里，默认页不再继续铺开。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 xl:grid-cols-2">
              {strategyCards.length ? strategyCards.map((item) => (
                <StrategyCard key={item.key} item={item} />
              )) : (
                <div className="rounded-2xl border border-dashed border-border/70 bg-muted/35 p-5 text-sm leading-6 text-muted-foreground xl:col-span-2">
                  <p className="font-medium text-foreground">当前还没有可评估的策略对象</p>
                  <p>统一候选篮子还是空的，所以策略页不会再回退到旧白名单假装继续评估。</p>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <DataTable
              columns={["最近信号", "Symbol", "Status", "Generated"]}
              rows={recentSignals.map((item, index) => ({
                id: String(item.signal_id ?? index),
                cells: [
                  String(item.strategy_id ?? "n/a"),
                  String(item.symbol ?? ""),
                  <StatusBadge key={String(item.signal_id ?? index)} value={String(item.status ?? "")} />,
                  String(item.generated_at ?? ""),
                ],
              }))}
              emptyTitle="当前还没有最近信号"
              emptyDetail="还没有新的持久化 signal 时，可以先看执行器状态和候选推进结论。"
            />

            <DataTable
              columns={["最近执行结果", "Side", "Type", "Status"]}
              rows={recentOrders.map((item, index) => ({
                id: String(item.id ?? index),
                cells: [
                  String(item.symbol ?? ""),
                  String(item.side ?? ""),
                  String(item.orderType ?? item.order_type ?? ""),
                  <StatusBadge key={String(item.id ?? index)} value={String(item.status ?? "")} />,
                ],
              }))}
              emptyTitle="当前还没有最近执行结果"
              emptyDetail="先启动策略并派发最新信号，再回到这里确认执行链路有没有真正走通。"
            />
          </div>

          <Card>
            <CardHeader>
              <p className="eyebrow">工具详情</p>
              <CardTitle>查看完整数据</CardTitle>
              <CardDescription>余额、订单、持仓、风险事件等详细数据都在工具页。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link href="/balances">余额</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/orders">订单</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/positions">持仓</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/risk">风险</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/tasks">任务</Link>
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

function StrategyCard({ item }: { item: StrategyWorkspaceCard }) {
  const executionHint = formatExecutionHint(item.current_evaluation);
  const researchScore = formatResearchScore(item.research_summary.score);
  const modelVersion = item.research_summary.model_version || "暂无训练产物";
  const preferredStrategy = formatPreferredStrategy(item.research_cockpit.recommended_strategy);
  const latestSignal = formatLatestSignal(item.latest_signal);

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
        <p>研究分数：{researchScore}</p>
        <p>模型版本：{modelVersion}</p>
        <p>推荐策略：{preferredStrategy}</p>
        <p>执行建议：{executionHint}</p>
        <p>观察币种：{item.symbols.join(" / ")}</p>
        <p>最近信号：{latestSignal}</p>
      </div>
    </article>
  );
}

function formatLatestSignal(item: Record<string, unknown> | null): string {
  if (!item) {
    return "暂无持久化信号";
  }
  return `${String(item.symbol ?? "")} / ${String(item.status ?? "")}`;
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
