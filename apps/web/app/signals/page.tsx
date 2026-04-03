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
          <div className="terminal-action-stack">
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

      <section className="terminal-layout">
        <div className="terminal-side">
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

          <section className="panel terminal-panel">
            <p className="eyebrow">研究动作</p>
            <h3>先训练，再推理</h3>
            <p>研究动作全部留在左侧，避免和统一研究报告抢主视线。</p>
            <div className="terminal-action-stack">
              <ActionForm action="run_research_training" label="研究训练" returnTo="/signals" />
              <ActionForm action="run_research_inference" label="研究推理" returnTo="/signals" />
            </div>
          </section>
        </div>

        <div className="terminal-main">
          <section className="panel terminal-panel terminal-panel-strong">
            <p className="eyebrow">最近研究结果</p>
            <h3>最近实验摘要</h3>
            <p>当前可进入 dry-run：{String(researchReport.overview.ready_count)}，被拦下：{String(researchReport.overview.blocked_count)}。</p>
            <div className="terminal-summary-grid">
              <div>
                <strong>研究状态</strong>
                <p>{formatText(researchReport.status, "n/a")} / {formatText(researchReport.backend, "n/a")}</p>
              </div>
              <div>
                <strong>筛选通过率</strong>
                <p>{researchReport.overview.pass_rate_pct}%</p>
              </div>
              <div>
                <strong>当前最佳候选</strong>
                <p>{formatText(researchReport.overview.top_candidate_symbol, "n/a")}</p>
              </div>
              <div>
                <strong>最近推理信号数</strong>
                <p>{String(researchReport.overview.signal_count)}</p>
              </div>
            </div>
            <div className="terminal-report-grid">
              <div className="terminal-report-card">
                <p className="eyebrow">训练摘要</p>
                <h4>研究训练</h4>
                <p>状态：{formatText(trainingExperiment["status"], "unavailable")}</p>
                <p>模型版本：{formatText(latestTraining["model_version"], "n/a")}</p>
              </div>
              <div className="terminal-report-card">
                <p className="eyebrow">推理摘要</p>
                <h4>研究推理</h4>
                <p>状态：{formatText(inferenceExperiment["status"], "unavailable")}</p>
                <p>生成时间：{formatText(researchReport.overview.generated_at, "n/a")}</p>
              </div>
            </div>
          </section>

          <section className="panel terminal-panel">
            <p className="eyebrow">最新信号</p>
            <h3>标准化 signal 列表</h3>
            <DataTable
              columns={["Symbol", "Source", "Generated", "Status"]}
              rows={items.map((item) => ({
                id: item.id,
                cells: [item.symbol, item.source, item.generatedAt, <StatusBadge key={item.id} value={item.status} />],
              }))}
              emptyTitle="还没有 signal"
              emptyDetail="先运行信号流水线，再回到这里确认是否已经产生最新信号。"
            />
          </section>
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
