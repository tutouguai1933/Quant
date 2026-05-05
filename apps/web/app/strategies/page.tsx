/**
 * 策略中心页面
 * 终端风格重构
 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import {
  TerminalShell,
  TerminalCard,
  MetricStrip,
  InfoBlock,
} from "../../components/terminal";
import { asRecord } from "../../lib/utils/helpers";
import { ArbitrationHandoffCard } from "../../components/arbitration-handoff-card";
import { FeedbackBanner } from "../../components/feedback-banner";
import { StatusBadge } from "../../components/status-badge";
import { Button } from "../../components/ui/button";
import { buildAutomationHandoffSummary } from "../../lib/automation-handoff";
import { readFeedback } from "../../lib/feedback";
import {
  calculateEntryScore,
  getAutomationStatus,
  getAutomationStatusFallback,
  getEntryDecisionFallback,
  getStrategyWorkspace,
  getStrategyWorkspaceFallback,
  type EntryDecisionModel,
  type StrategyWorkspaceCard,
} from "../../lib/api";

export default function StrategiesPage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [workspace, setWorkspace] = useState(getStrategyWorkspaceFallback());
  const [automation, setAutomation] = useState(getAutomationStatusFallback().item);
  const [entryScoreSymbol, setEntryScoreSymbol] = useState<string>("");
  const [entryScoreResult, setEntryScoreResult] = useState<EntryDecisionModel>(getEntryDecisionFallback());
  const [entryScoreLoading, setEntryScoreLoading] = useState(false);

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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    Promise.allSettled([
      getStrategyWorkspace(session.token!, controller.signal),
      getAutomationStatus(session.token!, controller.signal),
    ])
      .then(([workspaceResult, automationResult]) => {
        clearTimeout(timeoutId);

        if (workspaceResult.status === "fulfilled" && workspaceResult.value && !workspaceResult.value.error) {
          setWorkspace(workspaceResult.value.data);
        }
        if (automationResult.status === "fulfilled" && automationResult.value && !automationResult.value.error) {
          setAutomation(automationResult.value.data.item);
        }
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
  }, [session.token]);

  const handleCalculateEntryScore = async () => {
    if (!entryScoreSymbol.trim()) return;
    setEntryScoreLoading(true);
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      const result = await calculateEntryScore(1, entryScoreSymbol.trim(), "long", undefined, controller.signal);
      clearTimeout(timeoutId);
      if (result.error) {
        setEntryScoreResult({
          ...getEntryDecisionFallback(),
          reason: result.error.message || "计算入场评分失败",
        });
      } else {
        setEntryScoreResult(result.data.entry_decision);
      }
    } catch (error) {
      setEntryScoreResult({
        ...getEntryDecisionFallback(),
        reason: error instanceof Error ? error.message : "网络连接失败",
      });
    }
    setEntryScoreLoading(false);
  };

  const arbitration = asRecord(automation.arbitration);
  const arbitrationSuggestedAction = asRecord(arbitration.suggested_action);
  const tasksHref = session.isAuthenticated ? "/tasks" : "/login?next=%2Ftasks";

  const automationHandoff = buildAutomationHandoffSummary({
    automation,
    tasksHref,
    fallbackTargetHref: readText(arbitrationSuggestedAction, "target_page", "/research"),
    fallbackTargetLabel: workspace.research_recommendation?.next_action || "先进入 dry-run 观察。",
    fallbackHeadline: readText(arbitration, "headline", "当前自动化可以继续推进"),
    fallbackDetail: readText(arbitration, "detail", "当前自动化可以继续推进"),
  });

  const executorRuntimeStatus = readText(workspace.executor_runtime, "status", "ready");
  const executorRuntimeDetail = readText(workspace.executor_runtime, "detail", "");
  const executorConnectionStatus = readText(workspace.executor_runtime, "connection_status", "unknown");
  const executorStatusLabel = [
    workspace.executor_runtime.executor,
    workspace.executor_runtime.backend,
    workspace.executor_runtime.mode,
  ].filter(Boolean).join(" / ") || "未配置";

  const accountStateStatus = readText(workspace.account_state, "status", "ready");
  const accountStateDetail = readText(workspace.account_state, "detail", "");

  const recentSignals = Array.isArray(workspace.recent_signals) ? workspace.recent_signals : [];
  const recentOrders = Array.isArray(workspace.recent_orders) ? workspace.recent_orders : [];
  const strategyCards = Array.isArray(workspace.strategies) ? workspace.strategies : [];

  const isManualTakeover = Boolean(automation.manualTakeover);
  const takeoverReason = readText(automation, "pauseReason", "");

  const statusMetrics = [
    {
      label: "执行器",
      value: executorRuntimeStatus === "unavailable" ? "不可用" : executorStatusLabel,
      colorType: executorRuntimeStatus === "unavailable" ? ("negative" as const) : ("positive" as const),
    },
    {
      label: "自动化",
      value: isManualTakeover ? "人工接管" : automationHandoff.headline,
      colorType: isManualTakeover ? ("negative" as const) : automation.paused ? ("neutral" as const) : ("positive" as const),
    },
    {
      label: "账户",
      value: accountStateStatus === "unavailable" ? "不可用" : `${workspace.account_state.summary.balance_count} 余额`,
      colorType: accountStateStatus === "unavailable" ? ("negative" as const) : ("positive" as const),
    },
    {
      label: "最近信号",
      value: String(recentSignals.length),
      colorType: recentSignals.length > 0 ? ("positive" as const) : ("neutral" as const),
    },
  ];

  return (
    <TerminalShell
      breadcrumb="策略 / 策略中心"
      title="策略"
      subtitle="策略状态、市场判断、执行结果"
      currentPath="/strategies"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <ArbitrationHandoffCard
        arbitration={arbitration}
        isAuthenticated={session.isAuthenticated}
        surfaceLabel="策略页"
        showActions={!session.isAuthenticated}
      />

      {!session.isAuthenticated ? (
        <TerminalCard title="需要登录">
          <div className="space-y-3">
            <p className="text-sm text-[var(--terminal-muted)]">登录后才能看到真实策略状态、当前判断和最近执行结果。</p>
            <Button asChild variant="terminal">
              <Link href="/login?next=%2Fstrategies">先去登录</Link>
            </Button>
          </div>
        </TerminalCard>
      ) : (
        <>
          <MetricStrip metrics={statusMetrics} />

          {/* 执行器连接 */}
          <TerminalCard title="执行器连接">
            <div className="space-y-3 text-sm">
              <div className="grid gap-3 sm:grid-cols-2">
                <InfoBlock label="连接状态" value={executorConnectionStatus} />
                <InfoBlock label="执行器" value={executorStatusLabel} />
              </div>
              {executorRuntimeStatus === "unavailable" && (
                <p className="text-[var(--terminal-red)]">{executorRuntimeDetail || "先恢复执行器接口"}</p>
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                <InfoBlock label="最近信号" value={`${recentSignals.length} 条`} />
                <InfoBlock label="最近订单" value={`${recentOrders.length} 条`} />
              </div>
            </div>
          </TerminalCard>

          <div className="grid gap-4 lg:grid-cols-2">
            {/* 当前推荐 */}
            <TerminalCard title={workspace.research_recommendation?.symbol || "暂无推荐"}>
              <div className="space-y-3">
                <p className="text-xs text-[var(--terminal-muted)]">
                  {workspace.research_recommendation?.dry_run_gate?.status || "先完成研究和评估"}
                </p>
                <div className="flex gap-2">
                  <Button asChild variant="terminal" size="sm">
                    <Link href={automationHandoff.targetHref}>{automationHandoff.targetLabel || "继续"}</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/research">回到研究</Link>
                  </Button>
                </div>
              </div>
            </TerminalCard>

            {/* 执行状态 */}
            <TerminalCard title="最近执行结果">
              <div className="space-y-3">
                <p className="text-xs text-[var(--terminal-muted)]">
                  {recentOrders.length > 0 ? `${recentOrders.length} 条订单` : "暂无执行结果"}
                </p>
                <div className="flex gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link href="/signals">查看信号</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/orders">查看订单</Link>
                  </Button>
                </div>
              </div>
            </TerminalCard>
          </div>

          {/* 策略判断 */}
          <TerminalCard title="两套首批波段策略">
            <div className="grid gap-4 xl:grid-cols-2">
              {strategyCards.length ? strategyCards.map((item) => (
                <StrategyCard key={item.key} item={item} />
              )) : (
                <div className="rounded border border-dashed border-[var(--terminal-border)] p-4 text-sm text-[var(--terminal-muted)] xl:col-span-2">
                  <p className="font-medium text-[var(--terminal-text)]">当前还没有可评估的策略对象</p>
                  <p>统一候选篮子还是空的，所以策略页不会再回退到旧白名单假装继续评估。</p>
                </div>
              )}
            </div>
          </TerminalCard>

          {/* 入场评分 */}
          <TerminalCard title="入场评分计算">
            <div className="space-y-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={entryScoreSymbol}
                  onChange={(e) => setEntryScoreSymbol(e.target.value.toUpperCase())}
                  placeholder="输入 Symbol（如 BTCUSDT）"
                  className="flex-1 rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-3 py-2 text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-dim)] focus:border-[var(--terminal-accent)] focus:outline-none"
                />
                <Button
                  variant="terminal"
                  size="sm"
                  disabled={!entryScoreSymbol.trim() || entryScoreLoading}
                  onClick={handleCalculateEntryScore}
                >
                  {entryScoreLoading ? "计算中..." : "计算入场评分"}
                </Button>
              </div>
              {entryScoreResult.score !== "0" && (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <EntryScoreDigest
                    label="入场评分"
                    value={formatScore(entryScoreResult.score)}
                    detail={`置信度: ${entryScoreResult.confidence}`}
                    status={entryScoreResult.allowed ? "success" : "warning"}
                  />
                  <EntryScoreDigest
                    label="入场建议"
                    value={entryScoreResult.allowed ? "允许入场" : "不建议入场"}
                    detail={entryScoreResult.reason}
                    status={entryScoreResult.allowed ? "success" : "warning"}
                  />
                  <EntryScoreDigest
                    label="建议仓位"
                    value={`${formatRatio(entryScoreResult.suggested_position_ratio)}%`}
                    detail="基于评分和波动率计算"
                    status={entryScoreResult.suggested_position_ratio !== "0" ? "success" : "neutral"}
                  />
                  <EntryScoreDigest
                    label="趋势确认"
                    value={entryScoreResult.trend_confirmed ? "已确认" : "未确认"}
                    detail={entryScoreResult.research_aligned ? "研究信号一致" : "研究信号不一致"}
                    status={entryScoreResult.trend_confirmed ? "success" : "neutral"}
                  />
                </div>
              )}
            </div>
          </TerminalCard>

          {/* 信号与执行摘要 */}
          <TerminalCard title="信号与执行摘要">
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)] mb-3">最近信号</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-[var(--terminal-border)]">
                        <th className="text-left py-2 px-2 text-[var(--terminal-dim)]">信号</th>
                        <th className="text-left py-2 px-2 text-[var(--terminal-dim)]">Symbol</th>
                        <th className="text-center py-2 px-2 text-[var(--terminal-dim)]">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentSignals.slice(0, 3).length === 0 ? (
                        <tr><td colSpan={3} className="py-4 text-center text-[var(--terminal-muted)]">暂无信号</td></tr>
                      ) : (
                        recentSignals.slice(0, 3).map((item, index) => (
                          <tr key={String(item.signal_id ?? index)} className="border-b border-[var(--terminal-border)]/50">
                            <td className="py-2 px-2 text-[var(--terminal-text)]">{String(item.strategy_id ?? "n/a")}</td>
                            <td className="py-2 px-2 text-[var(--terminal-text)]">{String(item.symbol ?? "")}</td>
                            <td className="py-2 px-2 text-center"><StatusBadge value={String(item.status ?? "")} /></td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)] mb-3">最近执行</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-[var(--terminal-border)]">
                        <th className="text-left py-2 px-2 text-[var(--terminal-dim)]">执行</th>
                        <th className="text-left py-2 px-2 text-[var(--terminal-dim)]">Side</th>
                        <th className="text-center py-2 px-2 text-[var(--terminal-dim)]">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentOrders.slice(0, 3).length === 0 ? (
                        <tr><td colSpan={3} className="py-4 text-center text-[var(--terminal-muted)]">暂无执行</td></tr>
                      ) : (
                        recentOrders.slice(0, 3).map((item, index) => (
                          <tr key={String(item.id ?? index)} className="border-b border-[var(--terminal-border)]/50">
                            <td className="py-2 px-2 text-[var(--terminal-text)]">{String(item.symbol ?? "")}</td>
                            <td className="py-2 px-2 text-[var(--terminal-text)]">{String(item.side ?? "")}</td>
                            <td className="py-2 px-2 text-center"><StatusBadge value={String(item.status ?? "")} /></td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </TerminalCard>

          {/* 工具详情 */}
          <TerminalCard title="查看完整数据">
            <div className="flex flex-wrap gap-2">
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
            </div>
          </TerminalCard>
        </>
      )}
    </TerminalShell>
  );
}

function readText(obj: unknown, key: string, fallback: string): string {
  if (!obj || typeof obj !== "object") return fallback;
  const record = obj as Record<string, unknown>;
  const value = record[key];
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text.length > 0 ? text : fallback;
}

function StrategyCard({ item }: { item: StrategyWorkspaceCard }) {
  const executionHint = formatExecutionHint(item.current_evaluation);
  const researchScore = formatResearchScore(item.research_summary.score);
  const modelVersion = item.research_summary.model_version || "暂无训练产物";
  const preferredStrategy = formatPreferredStrategy(item.research_cockpit.recommended_strategy);
  const latestSignal = formatLatestSignal(item.latest_signal);

  return (
    <div className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">{item.key}</p>
      <h4 className="mt-2 text-sm font-medium text-[var(--terminal-text)]">{item.display_name}</h4>
      <p className="text-xs text-[var(--terminal-muted)]">{item.description}</p>
      <div className="mt-3 space-y-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-[var(--terminal-muted)]">运行状态：</span>
          <StatusBadge value={item.runtime_status} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[var(--terminal-muted)]">当前判断：</span>
          <StatusBadge value={String(item.current_evaluation.decision ?? "unknown")} />
        </div>
        <p className="text-[var(--terminal-muted)]">研究分数：{researchScore}</p>
        <p className="text-[var(--terminal-muted)]">模型版本：{modelVersion}</p>
        <p className="text-[var(--terminal-muted)]">推荐策略：{preferredStrategy}</p>
        <p className="text-[var(--terminal-muted)]">执行建议：{executionHint}</p>
        <p className="text-[var(--terminal-muted)]">观察币种：{item.symbols.join(" / ")}</p>
        <p className="text-[var(--terminal-muted)]">最近信号：{latestSignal}</p>
      </div>
    </div>
  );
}

function formatLatestSignal(item: Record<string, unknown> | null): string {
  if (!item) return "暂无持久化信号";
  return `${String(item.symbol ?? "")} / ${String(item.status ?? "")}`;
}

function formatResearchScore(value: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : "暂无研究分数";
}

function formatExecutionHint(item: Record<string, unknown>): string {
  const decision = String(item.decision ?? "").trim();
  if (decision === "signal") return "可以继续看最新信号并决定是否派发。";
  if (decision === "watch") return "先保持观察，暂时不要派发。";
  if (decision === "block") return "当前不适合执行，先不要派发。";
  return "先确认执行器状态和最新信号。";
}

function formatPreferredStrategy(value: StrategyWorkspaceCard["research_cockpit"]["recommended_strategy"]): string {
  if (value === "trend_breakout") return "趋势突破";
  if (value === "trend_pullback") return "趋势回调";
  return "继续观察";
}

function formatScore(value: string): string {
  const score = parseFloat(value);
  if (isNaN(score)) return "暂无评分";
  return `${(score * 100).toFixed(1)}分`;
}

function formatRatio(value: string): string {
  const ratio = parseFloat(value);
  if (isNaN(ratio)) return "0";
  return `${(ratio * 100).toFixed(0)}`;
}

function EntryScoreDigest({
  label,
  value,
  detail,
  status,
}: {
  label: string;
  value: string;
  detail: string;
  status: "success" | "warning" | "neutral";
}) {
  const statusColorMap = {
    success: "text-[var(--terminal-green)]",
    warning: "text-[var(--terminal-yellow)]",
    neutral: "text-[var(--terminal-muted)]",
  };
  return (
    <div className="rounded border border-[var(--terminal-border)]/60 bg-[var(--terminal-bg)]/30 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">{label}</p>
      <p className={`mt-2 text-sm font-medium ${statusColorMap[status]}`}>{value}</p>
      <p className="mt-1 text-xs text-[var(--terminal-muted)]">{detail}</p>
    </div>
  );
}
