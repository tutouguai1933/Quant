/* 这个文件负责渲染信号页，并提供最小信号流水线入口。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ResearchCandidateBoard } from "../../components/research-candidate-board";
import { StatusBadge } from "../../components/status-badge";
import { readFeedback } from "../../lib/feedback";
import { getResearchReport, getResearchReportFallback, getSignalsPageFallback, listSignals } from "../../lib/api";
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

  try {
    const response = await listSignals();
    items = response.data.items;
  } catch {
    // API 不可用时仍然保留演示数据。
  }

  try {
    const response = await getResearchReport();
    if (!response.error) {
      researchReport = response.data.item;
    }
  } catch {
    // API 不可用时仍然保留研究兜底数据。
  }

  const latestTraining = asRecord(researchReport.latest_training);
  const latestInference = asRecord(researchReport.latest_inference);
  const trainingExperiment = asRecord(researchReport.experiments.training);
  const inferenceExperiment = asRecord(researchReport.experiments.inference);

  return (
    <AppShell
      title="信号"
      subtitle="先看信号是否生成，再决定是否继续进入策略控制与执行链路。"
      currentPath="/signals"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="信号"
        title="最新信号"
        description="这里先回答两个问题：有没有信号？最新信号能不能进入下一步？如果没有，就直接从这里运行信号流水线。"
        aside={
          <div className="action-grid">
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

      <section className="panel">
        <p className="eyebrow">最近研究结果</p>
        <h3>研究训练 / 研究推理</h3>
        <p>当前研究后端：{formatText(researchReport.backend, "n/a")}，研究状态：{formatText(researchReport.status, "n/a")}。</p>
        <p>最新训练模型：{formatText(latestTraining["model_version"], "n/a")}，最近推理信号数：{String(researchReport.overview.signal_count)}。</p>
        <div className="action-grid">
          <ActionForm action="run_research_training" label="研究训练" returnTo="/signals" />
          <ActionForm action="run_research_inference" label="研究推理" returnTo="/signals" />
        </div>
      </section>

      <section className="panel">
        <p className="eyebrow">统一研究报告</p>
        <h3>最近实验摘要</h3>
        <p>候选总数：{String(researchReport.overview.candidate_count)}，可进入 dry-run：{String(researchReport.overview.ready_count)}。</p>
        <p>筛选通过率：{researchReport.overview.pass_rate_pct}% ，当前最佳候选：{formatText(researchReport.overview.top_candidate_symbol, "n/a")}。</p>
        <p>训练状态：{formatText(trainingExperiment["status"], "unavailable")}，推理状态：{formatText(inferenceExperiment["status"], "unavailable")}。</p>
        <p>模型版本：{formatText(researchReport.overview.model_version, "n/a")}，生成时间：{formatText(researchReport.overview.generated_at, "n/a")}。</p>
      </section>

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
        nextStep="下一步动作：优先看可进入 dry-run 的候选，再去策略中心确认是否继续派发。"
      />

      <section className="panel">
        <p className="eyebrow">动作反馈</p>
        <h3>从信号页进入执行链路</h3>
        <p>推荐先运行 Qlib 信号流水线看研究结果；如果要重复验证执行链路，就运行演示信号流水线，再切到 Strategies 页启动策略并派发最新信号。</p>
        <p>最近研究结果会同步回到这里，方便继续看研究训练和研究推理的最新状态。</p>
      </section>

      <DataTable
        columns={["Symbol", "Source", "Generated", "Status"]}
        rows={items.map((item) => ({
          id: item.id,
          cells: [item.symbol, item.source, item.generatedAt, <StatusBadge key={item.id} value={item.status} />],
        }))}
        emptyTitle="还没有 signal"
        emptyDetail="先运行信号流水线，再回到这里确认是否已经产生最新信号。"
      />
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
    <form action="/actions" method="post" className="action-card">
      <input type="hidden" name="action" value={action} />
      <input type="hidden" name="returnTo" value={returnTo} />
      <button type="submit">{label}</button>
      <p>通过控制平面提交研究动作，不直接碰后端实现。</p>
    </form>
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
