/* 这个文件负责渲染评估与实验中心，让推荐原因、淘汰原因和实验账本直接可见。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { getEvaluationWorkspace } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";

export default async function EvaluationPage() {
  const session = await getControlSessionState();
  const response = await getEvaluationWorkspace();
  const workspace = response.data.item;
  const evaluation = asRecord(workspace.evaluation);
  const candidateStatus = asRecord(evaluation.candidate_status);
  const eliminationRules = asRecord(evaluation.elimination_rules);
  const recommendedCandidate = asRecord(evaluation.recommended_candidate);
  const researchReview = asRecord(asRecord(workspace.reviews).research);

  return (
    <AppShell
      title="评估与实验中心"
      subtitle="把推荐理由、淘汰理由、样本外稳定性和实验账本放到同一页，方便直接比较。"
      currentPath="/evaluation"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="评估与实验中心"
        title="先看推荐原因和淘汰原因，再决定是否允许进入 dry-run 或继续研究。"
        description="这里不再只看分数，而是把推荐理由、淘汰原因、样本外稳定性和最近实验记录放到一起，方便你直接决定下一步。"
      />

      <MetricGrid
        items={[
          { label: "推荐标的", value: workspace.overview.recommended_symbol || "未推荐", detail: workspace.overview.recommended_action || "当前无下一步动作" },
          { label: "候选数量", value: String(workspace.overview.candidate_count), detail: `可进 dry-run ${String(candidateStatus.ready_count ?? 0)}` },
          { label: "推荐原因", value: String(researchReview.result ?? "未生成"), detail: String(researchReview.next_action ?? "继续研究") },
          { label: "样本外稳定性", value: String(candidateStatus.pass_rate_pct ?? "n/a"), detail: "当前按统一评估口径整理" },
        ]}
      />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_380px]">
        <div className="space-y-5">
          <DataTable
            columns={["实验排行榜", "推荐原因", "下一步动作", "淘汰原因"]}
            rows={workspace.leaderboard.map((item, index) => {
              const row = asRecord(item);
              const reasons = Array.isArray(row.failure_reasons) ? row.failure_reasons.map(String).join(" / ") : "已通过"
              return {
                id: `${row.symbol ?? index}`,
                cells: [
                  String(row.symbol ?? "n/a"),
                  String(row.score ?? row.review_status ?? "n/a"),
                  String(row.next_action ?? "continue_research"),
                  reasons,
                ],
              };
            })}
            emptyTitle="还没有实验排行榜"
            emptyDetail="先运行研究训练和研究推理，再回到这里比较候选。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>推荐原因</CardTitle>
              <CardDescription>这里直接展示系统为什么推荐这个币继续进入下一步。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="推荐标的" value={String((recommendedCandidate.symbol ?? workspace.overview.recommended_symbol) || "未推荐")} />
              <InfoBlock label="推荐动作" value={String((researchReview.next_action ?? workspace.overview.recommended_action) || "继续研究")} />
              <InfoBlock label="推荐分数" value={String(recommendedCandidate.score ?? "n/a")} />
              <InfoBlock label="进入 dry-run" value={String(candidateStatus.ready_count ?? 0)} />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>淘汰原因</CardTitle>
              <CardDescription>把主要阻断理由集中看，不用再回头翻各页细节。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {Object.entries(asRecord(eliminationRules.blocked_reason_counts)).length ? Object.entries(asRecord(eliminationRules.blocked_reason_counts)).map(([key, value]) => (
                <p key={key}>{key}：{String(value)}</p>
              )) : <p>当前没有淘汰原因，说明候选还没生成或都已通过。</p>}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>最近实验摘要</CardTitle>
              <CardDescription>这里只保留最小实验账本，方便回看最近训练和推理。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {workspace.recent_runs.length ? workspace.recent_runs.map((item, index) => {
                const row = asRecord(item);
                return (
                  <p key={`${row.run_id ?? index}`}>
                    {String(row.run_type ?? "run")} / {String(row.run_id ?? "n/a")} / {String(row.status ?? "n/a")}
                  </p>
                );
              }) : <p>当前还没有实验账本。</p>}
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-foreground break-all">{value}</p>
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}
