/* 这个文件负责渲染信号页，并提供最小信号流水线入口。 */

import { FlaskConical, ScanSearch, Sparkles } from "lucide-react";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ResearchCandidateBoard } from "../../components/research-candidate-board";
import { ResearchRuntimePanel } from "../../components/research-runtime-panel";
import { StatusBadge } from "../../components/status-badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { readFeedback } from "../../lib/feedback";
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
import { getControlSessionState } from "../../lib/session";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function SignalsPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const feedback = readFeedback(params);
  const session = await getControlSessionState();
  let items = getSignalsPageFallback().items;
  let researchReport = getResearchReportFallback().item;
  let runtimeStatus = getResearchRuntimeStatusFallback();
  let automation = getAutomationStatusFallback().item;
  let evaluationWorkspace = getEvaluationWorkspaceFallback();

  const [signalsResult, researchReportResult, runtimeResult, automationResult, evaluationResult] = await Promise.allSettled([
    listSignals(),
    getResearchReport(),
    getResearchRuntimeStatus(),
    session.token ? getAutomationStatus(session.token) : Promise.resolve(null),
    getEvaluationWorkspace(),
  ]);
  if (signalsResult.status === "fulfilled") {
    items = signalsResult.value.data.items;
  }
  if (researchReportResult.status === "fulfilled" && !researchReportResult.value.error) {
    researchReport = researchReportResult.value.data.item;
  }
  if (runtimeResult.status === "fulfilled" && !runtimeResult.value.error) {
    runtimeStatus = runtimeResult.value.data.item;
  }
  if (automationResult.status === "fulfilled" && automationResult.value && !automationResult.value.error) {
    automation = automationResult.value.data.item;
  }
  if (evaluationResult.status === "fulfilled" && !evaluationResult.value.error) {
    evaluationWorkspace = evaluationResult.value.data.item;
  }

  const latestTraining = asRecord(researchReport.latest_training);
  const latestInference = asRecord(researchReport.latest_inference);
  const trainingExperiment = asRecord(researchReport.experiments.training);
  const inferenceExperiment = asRecord(researchReport.experiments.inference);
  const automationCycle = asRecord(automation.lastCycle);
  const recommendationExplanation = asRecord(evaluationWorkspace.recommendation_explanation);
  const recommendationTemplateFit = asRecord(recommendationExplanation.template_fit);
  const stageDecisionSummary = asRecord(evaluationWorkspace.stage_decision_summary);
  const inferenceGeneratedAt = formatText(
    latestInference["generated_at"],
    formatText(inferenceExperiment["generated_at"], formatText(researchReport.overview.generated_at, "n/a")),
  );

  return (
    <AppShell
      title="信号"
      subtitle="左侧先判断哪些候选值得跟进，右侧再看统一研究报告和实验结果。"
      currentPath="/signals"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="研究终端"
        title="先看候选，再看报告，不把研究信息一路往下堆。"
        description="信号页现在只做两件事：左边给你候选和动作，右边给你统一研究报告和最近实验。"
        aside={
          <div className="grid gap-2">
            <ActionForm action="run_pipeline" label="运行 Qlib 信号流水线" returnTo="/signals" />
            <ActionForm action="run_mock_pipeline" label="运行演示信号流水线" returnTo="/signals" />
          </div>
        }
      />

      <MetricGrid
        items={[
          { label: "信号总数", value: String(items.length), detail: "当前页只展示标准化 signal" },
          { label: "最新来源", value: items[0]?.source ?? "n/a", detail: "用于快速判断输出来自 Qlib、mock 还是其他生产者" },
          { label: "最新状态", value: items[0]?.status ?? "waiting", detail: "决定是否需要继续到策略和任务页" },
        ]}
      />

      <ResearchRuntimePanel initialStatus={runtimeStatus} />

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(420px,0.95fr)]">
        <div className="space-y-6">
          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <ScanSearch className="size-4 text-primary" />
                <p className="eyebrow">自动化入口</p>
              </div>
              <CardTitle>先确认这一轮会不会继续往下跑</CardTitle>
              <CardDescription>研究页先告诉你自动化现在是手动、dry-run 还是小额 live，再决定是否继续提交动作。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <InfoBlock label="当前模式" value={formatText(automation.mode, "manual")} />
              <InfoBlock label="最近一轮" value={formatText(automationCycle.status, "waiting")} />
              <InfoBlock label="推荐标的" value={formatText(automationCycle.recommended_symbol, "n/a")} />
              <InfoBlock label="下一步动作" value={formatText(automationCycle.next_action, "continue_research")} />
            </CardContent>
          </Card>

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

          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <FlaskConical className="size-4 text-primary" />
                <p className="eyebrow">研究动作</p>
              </div>
              <CardTitle>先训练，再推理</CardTitle>
              <CardDescription>研究动作全部留在左侧，避免和统一研究报告抢主视线。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <ActionForm action="run_research_training" label="研究训练" returnTo="/signals" />
              <ActionForm action="run_research_inference" label="研究推理" returnTo="/signals" />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Sparkles className="size-4 text-primary" />
                <p className="eyebrow">统一研究报告</p>
              </div>
              <CardTitle>最近研究结果</CardTitle>
              <CardDescription>
                当前可进入 dry-run：{String(researchReport.overview.ready_count)}，被拦下：{String(researchReport.overview.blocked_count)}。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-2">
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
                  <DataTable
                    columns={["Symbol", "Source", "Generated", "Status"]}
                    rows={items.map((item) => ({
                      id: item.id,
                      cells: [item.symbol, item.source, item.generatedAt, <StatusBadge key={item.id} value={item.status} />],
                    }))}
                    emptyTitle="还没有 signal"
                    emptyDetail="先运行信号流水线，再回到这里确认是否已经产生最新信号。"
                  />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>模板适配判断</CardTitle>
              <CardDescription>这里直接回答当前推荐为什么更适合这套研究模板，不用切到评估页再拼上下文。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="当前推荐" value={formatText(researchReport.overview.top_candidate_symbol, "n/a")} />
              <InfoBlock label="更适合哪套模板" value={formatText(recommendationTemplateFit.headline, "当前还没有模板适配结论")} />
              <InfoBlock label="模板适配说明" value={formatText(recommendationTemplateFit.detail, "当前还没有模板适配说明")} />
              <InfoBlock label="下一步动作" value={formatText(stageDecisionSummary.next_step, "continue_research")} />
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}

type ActionFormProps = {
  action: string;
  label: string;
  returnTo: string;
};

function ActionForm({ action, label, returnTo }: ActionFormProps) {
  return (
    <Card className="bg-[color:var(--panel-strong)]/80">
      <CardContent className="p-4">
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value={action} />
          <input type="hidden" name="returnTo" value={returnTo} />
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-6 text-muted-foreground">通过控制平面提交研究动作，不直接碰后端实现。</p>
          </div>
          <FormSubmitButton
            type="submit"
            size="sm"
            idleLabel={label}
            pendingLabel={`${label}运行中…`}
            pendingHint="研究动作已发出，页面会在结果返回后自动刷新。"
          />
        </form>
      </CardContent>
    </Card>
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
    <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <h4 className="mt-3 text-base font-semibold text-foreground">{title}</h4>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">状态：{status}</p>
      <p className="text-sm leading-6 text-muted-foreground">{meta}</p>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-3 text-base font-semibold text-foreground">{value}</p>
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
