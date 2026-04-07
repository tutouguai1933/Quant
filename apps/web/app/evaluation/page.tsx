/* 这个文件负责渲染评估与实验中心，让推荐原因、淘汰原因和实验账本直接可见。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ConfigField, ConfigInput, WorkbenchConfigCard } from "../../components/workbench-config-card";
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
  const executionAlignment = asRecord(workspace.execution_alignment);
  const alignmentDetails = asRecord(workspace.alignment_details);
  const comparisonSummary = asRecord(workspace.comparison_summary);
  const configAlignment = asRecord(workspace.config_alignment);
  const controls = asRecord(workspace.controls);
  const executionMetrics = asRecord(executionAlignment.execution);
  const executionBacktest = asRecord(executionAlignment.backtest);
  const configEditable = workspace.status !== "unavailable";
  const unavailableConfigReason = "工作台暂时不可用，先恢复研究接口再保存配置。";
  const executionAlignmentNarrative = buildExecutionAlignmentNarrative({
    executionAlignment,
    executionMetrics,
    executionBacktest,
    researchReview,
    overview: workspace.overview,
    comparisonSummary,
  });

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
          <WorkbenchConfigCard
            title="准入门槛配置"
            description="这里改的是进入 dry-run 和进入小额 live 的门槛，保存后候选排序和自动化放行都会按新规则执行。"
            scope="thresholds"
            returnTo="/evaluation"
            disabled={!configEditable}
            disabledReason={unavailableConfigReason}
          >
            <ConfigField label="dry-run 门槛" hint="先决定一个候选要满足什么条件，才允许进入 dry-run。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="dry_run_min_score" defaultValue={workspace.controls.dry_run_min_score} placeholder="最低分数" />
                <ConfigInput name="dry_run_min_positive_rate" defaultValue={workspace.controls.dry_run_min_positive_rate} placeholder="最低验证正收益比例" />
                <ConfigInput name="dry_run_min_net_return_pct" defaultValue={workspace.controls.dry_run_min_net_return_pct} placeholder="最低净收益 %" />
                <ConfigInput name="dry_run_min_sharpe" defaultValue={workspace.controls.dry_run_min_sharpe} placeholder="最低 Sharpe" />
                <ConfigInput name="dry_run_max_drawdown_pct" defaultValue={workspace.controls.dry_run_max_drawdown_pct} placeholder="最大回撤 %" />
                <ConfigInput name="dry_run_max_loss_streak" defaultValue={workspace.controls.dry_run_max_loss_streak} placeholder="最大连续亏损段" />
                <ConfigInput name="dry_run_min_win_rate" defaultValue={String(controls.dry_run_min_win_rate ?? "0.5")} placeholder="最低胜率" />
                <ConfigInput name="dry_run_max_turnover" defaultValue={String(controls.dry_run_max_turnover ?? "0.6")} placeholder="最高换手" />
                <ConfigInput name="dry_run_min_sample_count" defaultValue={String(controls.dry_run_min_sample_count ?? "20")} placeholder="最低样本数" />
                <ConfigInput name="validation_min_sample_count" defaultValue={String(controls.validation_min_sample_count ?? "12")} placeholder="验证最少样本数" />
              </div>
            </ConfigField>
            <ConfigField label="live 门槛" hint="这里更严格，自动小额 live 会额外检查这些条件。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="live_min_score" defaultValue={workspace.controls.live_min_score} placeholder="最低 live 分数" />
                <ConfigInput name="live_min_positive_rate" defaultValue={workspace.controls.live_min_positive_rate} placeholder="最低 live 正收益比例" />
                <ConfigInput name="live_min_net_return_pct" defaultValue={workspace.controls.live_min_net_return_pct} placeholder="最低 live 净收益 %" />
                <ConfigInput name="live_min_win_rate" defaultValue={String(controls.live_min_win_rate ?? "0.55")} placeholder="最低 live 胜率" />
                <ConfigInput name="live_max_turnover" defaultValue={String(controls.live_max_turnover ?? "0.45")} placeholder="最高 live 换手" />
                <ConfigInput name="live_min_sample_count" defaultValue={String(controls.live_min_sample_count ?? "24")} placeholder="最低 live 样本数" />
              </div>
            </ConfigField>
          </WorkbenchConfigCard>

          <DataTable
            columns={["实验排行榜", "推荐原因", "下一步动作", "淘汰原因"]}
            rows={workspace.leaderboard.map((item, index) => {
              const row = asRecord(item);
              const reasons = String(row.elimination_reason ?? "已通过");
              return {
                id: `${row.symbol ?? index}`,
                cells: [
                  String(row.symbol ?? "n/a"),
                  String(row.recommendation_reason ?? row.score ?? row.review_status ?? "n/a"),
                  String(row.next_action ?? "continue_research"),
                  reasons,
                ],
              };
            })}
            emptyTitle="还没有实验排行榜"
            emptyDetail="先运行研究训练和研究推理，再回到这里比较候选。"
          />

          <DataTable
            columns={["实验对照", "状态", "模型版本", "数据快照", "信号数"]}
            rows={workspace.experiment_comparison.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${row.run_type ?? index}-${row.run_id ?? index}`,
                cells: [
                  String(row.run_type ?? "n/a"),
                  String(row.status ?? "n/a"),
                  String(row.model_version ?? "n/a"),
                  String(row.dataset_snapshot_id ?? "n/a"),
                  String(row.signal_count ?? "n/a"),
                ],
              };
            })}
            emptyTitle="当前还没有实验对照"
            emptyDetail="先运行研究训练和推理，系统才会把训练、推理和最近运行放到同一张对照表里。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>实验一致性</CardTitle>
              <CardDescription>先确认训练、推理、配置和执行是不是还站在同一轮，再决定要不要继续放行。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="训练运行 ID" value={String(comparisonSummary.training_run_id ?? "n/a")} />
              <InfoBlock label="推理运行 ID" value={String(comparisonSummary.inference_run_id ?? "n/a")} />
              <InfoBlock label="配置对齐" value={String(comparisonSummary.config_alignment_status ?? "unavailable")} />
              <InfoBlock label="执行对齐" value={String(comparisonSummary.execution_alignment_status ?? "unavailable")} />
              <InfoBlock label="模型一致" value={toYesNo(comparisonSummary.model_aligned)} />
              <InfoBlock label="数据快照一致" value={toYesNo(comparisonSummary.dataset_aligned)} />
              <InfoBlock label="研究复盘" value={String(comparisonSummary.review_result ?? "n/a")} />
              <InfoBlock label="下一步动作" value={String(comparisonSummary.next_action ?? "continue_research")} />
              <InfoBlock
                label="一致性说明"
                value={String(comparisonSummary.note ?? "当前还没有可展示的一致性说明")}
              />
            </CardContent>
          </Card>

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
              <CardTitle>淘汰原因说明</CardTitle>
              <CardDescription>这里直接解释被拦住的候选最主要卡在哪个门槛。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {workspace.leaderboard.length ? workspace.leaderboard.map((item, index) => {
                const row = asRecord(item);
                return (
                  <p key={`${row.symbol ?? index}`}>
                    {String(row.symbol ?? "n/a")}：{String(row.elimination_reason ?? "已通过")}
                  </p>
                );
              }) : <p>当前还没有可解释的候选淘汰记录。</p>}
            </CardContent>
          </Card>

          <DataTable
            columns={["门控分解", "规则门", "验证门", "回测门", "一致性门", "当前卡点"]}
            rows={workspace.gate_matrix.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${row.symbol ?? index}`,
                cells: [
                  String(row.symbol ?? "n/a"),
                  String(row.rule_gate ?? "n/a"),
                  String(row.validation_gate ?? "n/a"),
                  String(row.backtest_gate ?? "n/a"),
                  String(row.consistency_gate ?? "n/a"),
                  String(row.primary_reason ?? row.blocking_gate ?? "n/a"),
                ],
              };
            })}
            emptyTitle="当前还没有门控分解"
            emptyDetail="先完成训练和推理，系统才会把每个候选卡在哪一层门槛拆开给你看。"
          />

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

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>最近两轮对比</CardTitle>
              <CardDescription>参数与结果一起看，先确认这一轮到底是模型变了、数据变了，还是结果本身变了。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {workspace.run_deltas.length ? (
                <DataTable
                  columns={["最近两轮对比", "模型变化", "数据变化", "配置变化", "净收益差", "Sharpe 差", "胜率差", "说明"]}
                  rows={workspace.run_deltas.map((item, index) => {
                    const row = asRecord(item);
                    const changedFieldsStatus = String(row.changed_fields_status ?? "ready");
                    const changedFieldsNote = String(row.changed_fields_note ?? "");
                    const changedFields = Array.isArray(row.changed_fields)
                      ? row.changed_fields.map(String).filter(Boolean).join(" / ")
                      : "";
                    return {
                      id: `${row.run_type ?? index}`,
                      cells: [
                        `${String(row.run_type ?? "run")} / ${String(row.previous_run_id ?? "n/a")} → ${String(row.current_run_id ?? "n/a")}`,
                        String(row.model_changed ?? "否"),
                        String(row.dataset_changed ?? "否"),
                        changedFieldsStatus === "unavailable"
                          ? (changedFieldsNote || "当前实验账本缺少配置快照，暂时无法比较。")
                          : (changedFields || "当前没有配置变化"),
                        String(row.net_return_delta ?? "n/a"),
                        String(row.sharpe_delta ?? "n/a"),
                        String(row.win_rate_delta ?? "n/a"),
                        String(row.note ?? "当前还没有说明"),
                      ],
                    };
                  })}
                  emptyTitle="当前还没有最近两轮对比"
                  emptyDetail="先积累至少两轮同类型训练或推理，系统才会自动给出差异。"
                />
              ) : (
                <p className="text-sm leading-6 text-muted-foreground">当前还没有足够的实验账本，暂时无法比较最近两轮差异。</p>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前结果与配置对齐</CardTitle>
              <CardDescription>先确认当前评估结果是不是仍然基于这页右上角的最新门槛。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="对齐状态" value={String(configAlignment.status ?? "unavailable")} />
              <InfoBlock label="说明" value={String(configAlignment.note ?? "当前还没有可用对齐说明")} />
              <InfoBlock label="变更字段" value={Array.isArray(configAlignment.stale_fields) && configAlignment.stale_fields.length ? configAlignment.stale_fields.map(String).join(" / ") : "当前没有发现漂移字段"} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">研究与执行对齐</p>
              <CardTitle>研究结果 vs 执行结果</CardTitle>
              <CardDescription>这里不只显示 matched / unmatched，而是把对齐结论、对齐解释、最近执行摘要和建议动作直接讲清楚。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="对齐结论" value={executionAlignmentNarrative.result} />
              <InfoBlock label="研究结论" value={executionAlignmentNarrative.researchSummary} />
              <InfoBlock label="执行现状" value={executionAlignmentNarrative.executionSummary} />
              <InfoBlock label="建议动作" value={executionAlignmentNarrative.nextStep} />
              <InfoBlock label="对齐解释 / 差异说明" value={executionAlignmentNarrative.detail} />
              <InfoBlock label="最近执行摘要" value={executionAlignmentNarrative.executionCounts} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>执行对齐明细</CardTitle>
              <CardDescription>把研究标的、最近订单标的和最近持仓标的直接摆出来，避免只看到 matched 却不知道具体对齐到了什么。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="对齐状态" value={String(alignmentDetails.alignment_state ?? "当前没有执行对齐明细")} />
              <InfoBlock label="研究标的" value={String(alignmentDetails.research_symbol ?? "n/a")} />
              <InfoBlock label="最近订单标的" value={String(alignmentDetails.last_order_symbol ?? "n/a")} />
              <InfoBlock label="最近持仓标的" value={String(alignmentDetails.last_position_symbol ?? "n/a")} />
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

function buildExecutionAlignmentNarrative({
  executionAlignment,
  executionMetrics,
  executionBacktest,
  researchReview,
  overview,
  comparisonSummary,
}: {
  executionAlignment: Record<string, unknown>;
  executionMetrics: Record<string, unknown>;
  executionBacktest: Record<string, unknown>;
  researchReview: Record<string, unknown>;
  overview: {
    recommended_symbol: string;
    recommended_action: string;
    candidate_count: number;
  };
  comparisonSummary: Record<string, unknown>;
}) {
  const status = readText(executionAlignment.status, "unavailable");
  const researchSymbol = overview.recommended_symbol || readText(executionAlignment.symbol, "未推荐");
  const researchAction = readText(researchReview.next_action, overview.recommended_action || "继续研究");
  const reviewResult = readText(researchReview.result, readText(comparisonSummary.review_result, "未生成"));
  const runtimeMode = readText(executionMetrics.runtime_mode, "unknown");
  const latestSyncStatus = readText(executionMetrics.latest_sync_status, "unknown");
  const matchedOrderCount = Number(executionMetrics.matched_order_count ?? 0);
  const matchedPositionCount = Number(executionMetrics.matched_position_count ?? 0);
  const executionNote = readText(executionAlignment.note, "当前还没有可展示的研究与执行对齐结果");
  const netReturn = readText(executionBacktest.net_return_pct, "");
  const drawdown = readText(executionBacktest.max_drawdown_pct, "");

  if (status === "matched") {
    return {
      result: "研究建议和执行结果已经对上",
      researchSummary: `${researchSymbol} / ${researchAction} / ${reviewResult}`,
      executionSummary: `${formatRuntimeMode(runtimeMode)} / 同步 ${formatSyncStatus(latestSyncStatus)}`,
      nextStep: runtimeMode === "live" ? "保留小额 live，继续看复盘结果。" : "继续观察 dry-run，再决定是否进入 live。",
      detail: executionNote,
      executionCounts: buildExecutionCountsSummary({ matchedOrderCount, matchedPositionCount, latestSyncStatus, netReturn, drawdown }),
    };
  }

  if (status === "waiting_research") {
    return {
      result: "研究还没放行到执行",
      researchSummary: `${researchSymbol} / ${researchAction} / ${reviewResult}`,
      executionSummary: `${formatRuntimeMode(runtimeMode)} / 同步 ${formatSyncStatus(latestSyncStatus)}`,
      nextStep: "先回到研究、回测和评估链补强候选，再决定是否放行。",
      detail: executionNote,
      executionCounts: buildExecutionCountsSummary({ matchedOrderCount, matchedPositionCount, latestSyncStatus, netReturn, drawdown }),
    };
  }

  if (status === "attention_required") {
    return {
      result: "研究允许执行，但执行链需要先排障",
      researchSummary: `${researchSymbol} / ${researchAction} / ${reviewResult}`,
      executionSummary: `${formatRuntimeMode(runtimeMode)} / 同步 ${formatSyncStatus(latestSyncStatus)}`,
      nextStep: "先恢复执行器和同步，再重新核对研究结论。",
      detail: executionNote,
      executionCounts: buildExecutionCountsSummary({ matchedOrderCount, matchedPositionCount, latestSyncStatus, netReturn, drawdown }),
    };
  }

  if (status === "no_execution") {
    return {
      result: "研究已有候选，但执行侧还没跟上",
      researchSummary: `${researchSymbol} / ${researchAction} / ${reviewResult}`,
      executionSummary: `${formatRuntimeMode(runtimeMode)} / 同步 ${formatSyncStatus(latestSyncStatus)}`,
      nextStep: "先去任务页和策略页确认是否已派发、是否被人工暂停。",
      detail: executionNote,
      executionCounts: buildExecutionCountsSummary({ matchedOrderCount, matchedPositionCount, latestSyncStatus, netReturn, drawdown }),
    };
  }

  return {
    result: "当前还没有足够结果可对齐",
    researchSummary: `${researchSymbol || "未推荐"} / ${researchAction} / ${reviewResult}`,
    executionSummary: `${formatRuntimeMode(runtimeMode)} / 同步 ${formatSyncStatus(latestSyncStatus)}`,
    nextStep: "先补研究结果、执行同步或 dry-run，再回来复核。",
    detail: executionNote,
    executionCounts: buildExecutionCountsSummary({ matchedOrderCount, matchedPositionCount, latestSyncStatus, netReturn, drawdown }),
  };
}

function buildExecutionCountsSummary({
  matchedOrderCount,
  matchedPositionCount,
  latestSyncStatus,
  netReturn,
  drawdown,
}: {
  matchedOrderCount: number;
  matchedPositionCount: number;
  latestSyncStatus: string;
  netReturn: string;
  drawdown: string;
}) {
  const parts = [
    `同步 ${formatSyncStatus(latestSyncStatus)}`,
    `订单 ${matchedOrderCount}`,
    `持仓 ${matchedPositionCount}`,
  ];
  if (netReturn) {
    parts.push(`净收益 ${netReturn}`);
  }
  if (drawdown) {
    parts.push(`最大回撤 ${drawdown}`);
  }
  return parts.join(" / ");
}

function formatRuntimeMode(mode: string) {
  const mapping: Record<string, string> = {
    live: "当前在小额 live",
    dry_run: "当前在 dry-run",
    manual: "当前在手动模式",
    unavailable: "当前还没有执行模式",
    unknown: "当前执行模式未知",
  };
  return mapping[mode] ?? mode;
}

function formatSyncStatus(status: string) {
  const mapping: Record<string, string> = {
    succeeded: "已同步",
    failed: "同步失败",
    waiting: "等待同步",
    unknown: "同步状态未知",
  };
  return mapping[status] ?? status;
}

function readText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}

function toYesNo(value: unknown): string {
  return value ? "是" : "否";
}
