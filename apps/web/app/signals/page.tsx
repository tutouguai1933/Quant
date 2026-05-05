/**
 * 信号页面
 * 终端风格重构
 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { FlaskConical, ScanSearch, Sparkles } from "lucide-react";

import {
  TerminalShell,
  TerminalCard,
  MetricStrip,
  InfoBlock,
} from "../../components/terminal";
import { asRecord } from "../../lib/utils/helpers";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
import { ResearchCandidateBoard } from "../../components/research-candidate-board";
import { ResearchRuntimePanel } from "../../components/research-runtime-panel";
import { Skeleton } from "../../components/ui/skeleton";
import { StatusBadge } from "../../components/status-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { readFeedback } from "../../lib/feedback";
import { buildAutomationHandoffSummary } from "../../lib/automation-handoff";
import {
  getAutomationStatus,
  getAutomationStatusFallback,
  getEvaluationWorkspace,
  getEvaluationWorkspaceFallback,
  getResearchReport,
  getResearchReportFallback,
  getResearchRuntimeStatus,
  getResearchRuntimeStatusFallback,
  getSignalsPageFallback,
  listSignals,
} from "../../lib/api";

export default function SignalsPage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  const [session, setSession] = useState<{ token: string; isAuthenticated: boolean }>({
    token: "",
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [items, setItems] = useState(getSignalsPageFallback().items);
  const [researchReport, setResearchReport] = useState(getResearchReportFallback().item);
  const [runtimeStatus, setRuntimeStatus] = useState(getResearchRuntimeStatusFallback());
  const [automation, setAutomation] = useState(getAutomationStatusFallback().item);
  const [evaluationWorkspace, setEvaluationWorkspace] = useState(getEvaluationWorkspaceFallback());

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || "",
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    Promise.allSettled([
      listSignals(controller.signal),
      getResearchReport(),
      getResearchRuntimeStatus(controller.signal),
      session.token ? getAutomationStatus(session.token, controller.signal) : Promise.resolve(null),
      getEvaluationWorkspace(controller.signal),
    ])
      .then(([signalsResult, researchReportResult, runtimeResult, automationResult, evaluationResult]) => {
        clearTimeout(timeoutId);
        if (signalsResult.status === "fulfilled" && !signalsResult.value.error) {
          const signalItems = signalsResult.value.data?.items;
          if (Array.isArray(signalItems)) {
            setItems(signalItems);
          }
        }
        if (researchReportResult.status === "fulfilled" && !researchReportResult.value.error) {
          setResearchReport(researchReportResult.value.data.item);
        }
        if (runtimeResult.status === "fulfilled" && !runtimeResult.value.error) {
          setRuntimeStatus(runtimeResult.value.data.item);
        }
        if (automationResult.status === "fulfilled" && automationResult.value && !automationResult.value.error) {
          setAutomation(automationResult.value.data.item);
        }
        if (evaluationResult.status === "fulfilled" && !evaluationResult.value.error) {
          setEvaluationWorkspace(evaluationResult.value.data.item);
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

  const latestTraining = asRecord(researchReport.latest_training);
  const latestInference = asRecord(researchReport.latest_inference);
  const trainingExperiment = asRecord(researchReport.experiments.training);
  const inferenceExperiment = asRecord(researchReport.experiments.inference);
  const automationCycle = asRecord(automation.lastCycle);
  const automationArbitration = asRecord(automation.arbitration);
  const automationSuggestedAction = asRecord(automationArbitration.suggested_action);
  const recommendationExplanation = asRecord(evaluationWorkspace.recommendation_explanation);
  const recommendationTemplateFit = asRecord(recommendationExplanation.template_fit);
  const stageDecisionSummary = asRecord(evaluationWorkspace.stage_decision_summary);
  const tasksHref = session.isAuthenticated ? "/tasks" : "/login?next=%2Ftasks";
  const evaluationHref = "/evaluation";
  const automationHandoff = buildAutomationHandoffSummary({
    automation,
    tasksHref,
    fallbackTargetHref: formatText(automationSuggestedAction.target_page, evaluationHref),
    fallbackTargetLabel: formatText(automationSuggestedAction.label, "去评估页继续"),
    fallbackHeadline: formatText(automationArbitration.headline, "当前还没有自动化承接摘要"),
    fallbackDetail: formatText(automationArbitration.detail, "查看评估和任务页。"),
  });
  const inferenceGeneratedAt = formatText(
    latestInference["generated_at"],
    formatText(inferenceExperiment["generated_at"], formatText(researchReport.overview.generated_at, "n/a")),
  );

  const statusMetrics = [
    {
      label: "信号总数",
      value: String(items.length),
      colorType: items.length > 0 ? ("positive" as const) : ("neutral" as const),
    },
    {
      label: "研究状态",
      value: formatText(researchReport.status, "未运行"),
      colorType: researchReport.status === "completed" ? ("positive" as const) : ("neutral" as const),
    },
    {
      label: "自动化",
      value: automationHandoff.headline,
      colorType: automation.manualTakeover || automation.paused ? ("neutral" as const) : ("positive" as const),
    },
    {
      label: "最新状态",
      value: items[0]?.status ?? "waiting",
      colorType: items[0]?.status === "completed" ? ("positive" as const) : ("neutral" as const),
    },
  ];

  return (
    <TerminalShell
      breadcrumb="研究 / 信号"
      title="信号"
      subtitle="候选排行与研究报告"
      currentPath="/signals"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <MetricStrip metrics={statusMetrics} />

      <ResearchRuntimePanel initialStatus={runtimeStatus} />

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-48 rounded-lg" />
          <div className="grid gap-4 xl:grid-cols-2">
            <Skeleton className="h-64 rounded-lg" />
            <Skeleton className="h-80 rounded-lg" />
          </div>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(420px,0.95fr)]">
          <div className="space-y-4">
            {/* 自动化状态 */}
            <TerminalCard>
              <div className="flex items-center gap-3 mb-4">
                <ScanSearch className="size-4 text-[var(--terminal-accent)]" />
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">自动化入口</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 mb-4">
                <InfoBlock label="当前模式" value={formatText(automation.mode, "manual")} />
                <InfoBlock label="最近一轮" value={formatText(automationCycle.status, "waiting")} />
                <InfoBlock label="当前判断" value={automationHandoff.headline} />
                <InfoBlock label="下一步动作" value={automationHandoff.targetLabel} />
              </div>
              <p className="text-sm text-[var(--terminal-muted)] mb-4">{automationHandoff.detail}</p>
            </TerminalCard>

            {/* 候选排行榜 */}
            <ResearchCandidateBoard
              title="候选排行榜"
              summary={{
                candidate_count: researchReport.overview.candidate_count,
                ready_count: researchReport.overview.ready_count,
                blocked_count: researchReport.overview.blocked_count,
                pass_rate_pct: researchReport.overview.pass_rate_pct,
                top_candidate_symbol: researchReport.overview.top_candidate_symbol,
                top_candidate_score: researchReport.overview.top_candidate_score,
              }}
              items={researchReport.candidates}
              nextStep="下一步动作：优先看允许进入 dry-run 的候选，再进入策略中心确认是否继续派发。"
            />

            {/* 研究动作 */}
            <TerminalCard>
              <div className="flex items-center gap-3 mb-4">
                <FlaskConical className="size-4 text-[var(--terminal-accent)]" />
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">研究动作</span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <ActionForm action="run_research_training" label="研究训练" returnTo="/signals" />
                <ActionForm action="run_research_inference" label="研究推理" returnTo="/signals" />
              </div>
            </TerminalCard>
          </div>

          <div className="space-y-4">
            {/* 统一研究报告 */}
            <TerminalCard>
              <div className="flex items-center gap-3 mb-4">
                <Sparkles className="size-4 text-[var(--terminal-accent)]" />
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">统一研究报告</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 mb-4">
                <InfoBlock label="研究状态" value={`${formatText(researchReport.status, "n/a")} / ${formatText(researchReport.backend, "n/a")}`} />
                <InfoBlock label="筛选通过率" value={`${researchReport.overview.pass_rate_pct}%`} />
                <InfoBlock label="当前最佳候选" value={formatText(researchReport.overview.top_candidate_symbol, "n/a")} />
                <InfoBlock label="最近推理信号数" value={String(researchReport.overview.signal_count)} />
              </div>

              <Tabs defaultValue="experiments">
                <TabsList>
                  <TabsTrigger value="experiments">最近实验摘要</TabsTrigger>
                  <TabsTrigger value="signals">最新信号</TabsTrigger>
                </TabsList>

                <TabsContent value="experiments" className="mt-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <ExperimentCard
                      label="训练摘要"
                      title="研究训练"
                      status={formatText(trainingExperiment["status"], "unavailable")}
                      meta={`模型版本：${formatText(latestTraining["model_version"], "n/a")}`}
                    />
                    <ExperimentCard
                      label="推理摘要"
                      title="研究推理"
                      status={formatText(inferenceExperiment["status"], "unavailable")}
                      meta={`生成时间：${inferenceGeneratedAt}`}
                    />
                  </div>
                </TabsContent>

                <TabsContent value="signals" className="mt-4">
                  <div className="overflow-x-auto">
                    <table className="w-full text-[12px]">
                      <thead>
                        <tr className="border-b border-[var(--terminal-border)]">
                          <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">Symbol</th>
                          <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">Source</th>
                          <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">Generated</th>
                          <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="py-8 text-center text-[var(--terminal-muted)]">还没有 signal</td>
                          </tr>
                        ) : (
                          items.map((item) => (
                            <tr key={item.id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-bg-hover)]">
                              <td className="py-2 px-3 text-[var(--terminal-text)]">{item.symbol}</td>
                              <td className="py-2 px-3 text-[var(--terminal-text)]">{item.source}</td>
                              <td className="py-2 px-3 text-[var(--terminal-text)]">{item.generatedAt}</td>
                              <td className="py-2 px-3 text-center">
                                <StatusBadge value={item.status} />
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </TabsContent>
              </Tabs>
            </TerminalCard>

            {/* 模板适配判断 */}
            <TerminalCard title="模板适配判断">
              <div className="grid gap-3 md:grid-cols-2">
                <InfoBlock label="当前推荐" value={formatText(researchReport.overview.top_candidate_symbol, "n/a")} />
                <InfoBlock label="更适合哪套模板" value={formatText(recommendationTemplateFit.headline, "当前还没有模板适配结论")} />
                <InfoBlock label="模板适配说明" value={formatText(recommendationTemplateFit.detail, "当前还没有模板适配说明")} />
                <InfoBlock label="下一步动作" value={formatText(stageDecisionSummary.next_step, "continue_research")} />
              </div>
            </TerminalCard>
          </div>
        </div>
      )}
    </TerminalShell>
  );
}

type ActionFormProps = {
  action: string;
  label: string;
  returnTo: string;
};

function ActionForm({ action, label, returnTo }: ActionFormProps) {
  return (
    <div className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
      <form action="/actions" method="post" className="space-y-3">
        <input type="hidden" name="action" value={action} />
        <input type="hidden" name="returnTo" value={returnTo} />
        <div className="space-y-1">
          <p className="text-sm font-medium text-[var(--terminal-text)]">{label}</p>
          <p className="text-xs text-[var(--terminal-muted)]">通过控制平面提交研究动作</p>
        </div>
        <FormSubmitButton
          type="submit"
          size="sm"
          idleLabel={label}
          pendingLabel={`${label}运行中…`}
          pendingHint="研究动作已发出，页面会在结果返回后自动刷新。"
        />
      </form>
    </div>
  );
}

function ExperimentCard({
  label,
  title,
  status,
  meta,
}: {
  label: string;
  title: string;
  status: string;
  meta: string;
}) {
  return (
    <div className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">{label}</p>
      <h4 className="mt-3 text-sm font-medium text-[var(--terminal-text)]">{title}</h4>
      <p className="mt-2 text-xs text-[var(--terminal-muted)]">状态：{status}</p>
      <p className="text-xs text-[var(--terminal-muted)]">{meta}</p>
    </div>
  );
}

function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
