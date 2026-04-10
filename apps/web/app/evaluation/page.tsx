/* 这个文件负责渲染评估与实验中心，让推荐原因、淘汰原因和实验账本直接可见。 */

import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { EvaluationDecisionCenter } from "../../components/evaluation-decision-center";
import { FormSubmitButton } from "../../components/form-submit-button";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ConfigField, ConfigInput, ConfigSelect, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { getAutomationStatus, getAutomationStatusFallback, getEvaluationWorkspace } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";
import { WorkbenchConfigStatusCard } from "../../components/workbench-config-status-card";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function EvaluationPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const [response, automationResponse] = await Promise.all([
    getEvaluationWorkspace(),
    session.token ? getAutomationStatus(session.token) : Promise.resolve(null),
  ]);
  const workspace = response.data.item;
  const automation =
    automationResponse && !automationResponse.error
      ? automationResponse.data.item
      : getAutomationStatusFallback().item;
  const evaluation = asRecord(workspace.evaluation);
  const candidateScope = asRecord(workspace.candidate_scope);
  const candidateSymbols = toStringArray(candidateScope.candidate_symbols);
  const liveAllowedSymbols = toStringArray(candidateScope.live_allowed_symbols);
  const candidatePoolPresetKey = readText(candidateScope.candidate_pool_preset_key, "top10_liquid");
  const candidatePoolPresetDetail = readText(candidateScope.candidate_pool_preset_detail, "当前还没有候选池预设说明。");
  const liveSubsetPresetKey = readText(candidateScope.live_subset_preset_key, "core_live");
  const liveSubsetPresetDetail = readText(candidateScope.live_subset_preset_detail, "当前还没有 live 子集预设说明。");
  const candidateScopeHeadline = readText(candidateScope.headline, "当前还没有统一候选池说明。");
  const candidateScopeDetail = readText(candidateScope.detail, "当前还没有候选池和 live 子集的统一解释。");
  const candidateScopeNextStep = readText(candidateScope.next_step, "先恢复候选池与 live 子集配置。");
  const candidateStatus = asRecord(evaluation.candidate_status);
  const eliminationRules = asRecord(evaluation.elimination_rules);
  const recommendedCandidate = asRecord(evaluation.recommended_candidate);
  const researchReview = asRecord(asRecord(workspace.reviews).research);
  const executionAlignment = asRecord(workspace.execution_alignment);
  const alignmentDetails = asRecord(workspace.alignment_details);
  const alignmentGaps = Array.isArray(workspace.alignment_gaps) ? workspace.alignment_gaps.filter((item) => item && typeof item === "object") : [];
  const alignmentActions = Array.isArray(workspace.alignment_actions) ? workspace.alignment_actions.filter((item) => item && typeof item === "object") : [];
  const comparisonSummary = asRecord(workspace.comparison_summary);
  const deltaOverview = asRecord(workspace.delta_overview);
  const configAlignment = asRecord(workspace.config_alignment);
  const selectionStory = asRecord(workspace.selection_story);
  const controls = asRecord(workspace.controls);
  const operations = asRecord(workspace.operations);
  const operationsPresetKey = readText(operations.operations_preset_key, "balanced_guard");
  const operationsPresetDetail = readText(operations.operations_preset_detail, "当前还没有长期运行预设说明。");
  const automationPresetKey = readText(operations.automation_preset_key, "balanced_runtime");
  const automationPresetDetail = readText(operations.automation_preset_detail, "当前还没有自动化运行预设说明。");
  const bestExperiment = asRecord(workspace.best_experiment);
  const bestStageCandidates = asRecord(workspace.best_stage_candidates);
  const decisionBoard = asRecord(workspace.decision_board);
  const bestDryRunCandidate = asRecord(bestStageCandidates.dry_run);
  const bestLiveCandidate = asRecord(bestStageCandidates.live);
  const recommendationExplanation = asRecord(workspace.recommendation_explanation);
  const eliminationExplanation = asRecord(workspace.elimination_explanation);
  const recommendationTemplateFit = asRecord(recommendationExplanation.template_fit);
  const eliminationTemplateFit = asRecord(eliminationExplanation.template_fit);
  const alignmentStory = asRecord(workspace.alignment_story);
  const selectedThresholdPreset = asRecord(selectionStory.threshold_preset);
  const alignmentMetricRows = Array.isArray(workspace.alignment_metric_rows)
    ? workspace.alignment_metric_rows.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const reviewLimit = readText(operations.review_limit, "10");
  const comparisonRunLimit = readText(operations.comparison_run_limit, "5");
  const executionMetrics = asRecord(executionAlignment.execution);
  const executionBacktest = asRecord(executionAlignment.backtest);
  const gateMatrixRows = Array.isArray(workspace.gate_matrix)
    ? workspace.gate_matrix.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const gateMatrixBySymbol = new Map(
    gateMatrixRows.map((item) => [String(item.symbol ?? ""), item] as const).filter(([key]) => key.length > 0),
  );
  const recentReviewTasks = Array.isArray(workspace.recent_review_tasks)
    ? workspace.recent_review_tasks.filter((item) => item && typeof item === "object")
    : [];
  const configEditable = workspace.status !== "unavailable";
  const unavailableConfigReason = "工作台暂时不可用，先恢复研究接口再保存配置。";
  const experimentAlignmentNote = readText(comparisonSummary.experiment_alignment_note, "当前还没有实验对比说明");
  const trainingModelVersion = readText(comparisonSummary.training_model_version, "n/a");
  const inferenceModelVersion = readText(comparisonSummary.inference_model_version, "n/a");
  const trainingDatasetSnapshot = readText(comparisonSummary.training_dataset_snapshot, "n/a");
  const inferenceDatasetSnapshot = readText(comparisonSummary.inference_dataset_snapshot, "n/a");
  const experimentAlignmentContent = `${trainingModelVersion} / ${inferenceModelVersion} / ${trainingDatasetSnapshot} / ${inferenceDatasetSnapshot}`;
  const configAlignmentStatus = readText(configAlignment.status, "unavailable");
  const configAlignmentCallout =
    configAlignmentStatus === "aligned"
      ? "当前研究结果仍然基于这页右上角的最新门槛。"
      : configAlignmentStatus === "unavailable"
        ? "评估系统还没拿到配置快照，无法确认与当前门槛的关系。"
        : "检测到配置与研究结果之间可能存在漂移，请参照右侧字段进一步核对。";
  const thresholdPresetCatalog = Array.isArray(controls.threshold_preset_catalog)
    ? controls.threshold_preset_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const thresholdCatalog = Array.isArray(workspace.threshold_catalog)
    ? workspace.threshold_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const comparisonOptions = buildExperimentCompareOptions({
    trainingRuns: workspace.recent_training_runs,
    inferenceRuns: workspace.recent_inference_runs,
    limit: Number(comparisonRunLimit),
  });
  const compareA = readSearchParam(params.compareA, comparisonOptions[0]?.id ?? "");
  const compareB = readSearchParam(
    params.compareB,
    comparisonOptions.find((item) => item.id !== compareA)?.id ?? comparisonOptions[0]?.id ?? "",
  );
  const stageView = resolveStageView(readSearchParam(params.stageView, "all"));
  const manualCompare = buildManualExperimentComparison({
    left: comparisonOptions.find((item) => item.id === compareA),
    right: comparisonOptions.find((item) => item.id === compareB),
  });
  const executionAlignmentNarrative = buildExecutionAlignmentNarrative({
    executionAlignment,
    executionMetrics,
    executionBacktest,
    researchReview,
    overview: workspace.overview,
    comparisonSummary,
  });
  const latestRunDelta = workspace.run_deltas.length ? asRecord(workspace.run_deltas[0]) : {};
  const configDiffSections = buildConfigDiffSections(latestRunDelta);
  const evaluationStatus = String(configAlignment.status ?? workspace.status ?? "unavailable");
  const evaluationStaleFields = Array.isArray(configAlignment.stale_fields) ? configAlignment.stale_fields.map(String) : [];
  const filteredLeaderboard = workspace.leaderboard.filter((item) => {
    const row = asRecord(item);
    const symbol = String(row.symbol ?? "");
    return matchesStageView({
      row,
      gateRow: gateMatrixBySymbol.get(symbol),
      stageView,
    });
  });
  const filteredGateMatrixRows = gateMatrixRows.filter((item) =>
    matchesStageView({
      gateRow: asRecord(item),
      row: workspace.leaderboard.find((entry) => String(asRecord(entry).symbol ?? "") === String(asRecord(item).symbol ?? "")),
      stageView,
    }),
  );
  const stageFilterSummary = buildStageFilterSummary({
    leaderboard: workspace.leaderboard,
    gateMatrixBySymbol,
    currentStageView: stageView,
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
          {
            label: "推荐原因",
            value: String(recommendationExplanation.headline ?? "未生成"),
            detail: String(recommendationExplanation.detail ?? researchReview.result ?? "继续研究"),
          },
          { label: "样本外稳定性", value: String(candidateStatus.pass_rate_pct ?? "n/a"), detail: "当前按统一评估口径整理" },
        ]}
      />

      <WorkbenchConfigStatusCard
        scope="评估"
        status={evaluationStatus}
        note={configAlignmentCallout}
        staleFields={evaluationStaleFields}
        editable={workspace.status !== "unavailable"}
      />

      <EvaluationDecisionCenter
        arbitration={asRecord(automation.arbitration)}
        decisionBoard={decisionBoard}
        stageDecisionSummary={asRecord(workspace.stage_decision_summary)}
        bestExperiment={bestExperiment}
        recommendationExplanation={recommendationExplanation}
      />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_380px]">
        <div className="space-y-5">
          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前准入选择</CardTitle>
              <CardDescription>先看清这轮评估现在按什么门槛放行，再去判断为什么只到 dry-run、为什么还不能进 live。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="当前准入组合" value={readText(selectionStory.headline, "当前还没有准入组合摘要")} />
              <InfoBlock label="当前口径说明" value={readText(selectionStory.detail, "当前还没有口径说明")} />
              <InfoBlock
                label="准入预设"
                value={`${readText(selectedThresholdPreset.label, String(controls.threshold_preset_key ?? "standard_gate"))} / ${readText(selectedThresholdPreset.fit, "当前没有适用场景说明")}`}
              />
              <InfoBlock label="dry-run 口径" value={readText(selectionStory.dry_run_summary, "当前还没有 dry-run 摘要")} />
              <InfoBlock label="validation 口径" value={readText(selectionStory.validation_summary, "当前还没有验证摘要")} />
              <InfoBlock label="consistency 口径" value={readText(selectionStory.consistency_summary, "当前还没有一致性摘要")} />
              <InfoBlock label="live 口径" value={readText(selectionStory.live_summary, "当前还没有 live 摘要")} />
              <InfoBlock label="当前门控" value={readText(selectionStory.gate_summary, "当前还没有门控摘要")} />
            </CardContent>
          </Card>

          <WorkbenchConfigCard
            title="准入预设"
            description="先切换一整套放行口径，再决定要不要继续手动微调 dry-run 和 live 的每个门。"
            scope="thresholds"
            returnTo="/evaluation"
            disabled={!configEditable}
            disabledReason={unavailableConfigReason}
          >
            <ConfigField label="一键套用" hint="预设会一起改 dry-run、验证、一致性和 live 门槛，适合先快速切到标准、严格或探索口径。">
              <ConfigSelect
                name="threshold_preset_key"
                defaultValue={String(controls.threshold_preset_key ?? "standard_gate")}
                options={(workspace.controls.available_threshold_presets || []).map((item) => ({
                  value: item,
                  label: item,
                }))}
              />
            </ConfigField>
            <DataTable
              columns={["准入预设", "适用场景", "说明"]}
              rows={thresholdPresetCatalog.map((item, index) => ({
                id: `${item.key ?? index}`,
                cells: [
                  String(item.key ?? "n/a"),
                  String(item.fit ?? "当前没有适用场景说明"),
                  String(item.detail ?? "当前没有预设说明"),
                ],
              }))}
              emptyTitle="当前还没有准入预设"
              emptyDetail="先恢复评估工作台，系统才会给出一键门槛预设。"
            />
          </WorkbenchConfigCard>

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
                <ConfigInput name="validation_min_avg_future_return_pct" defaultValue={String(controls.validation_min_avg_future_return_pct ?? "-0.1")} placeholder="验证最低未来收益 %" />
              </div>
            </ConfigField>
            <ConfigField label="规则门与一致性门" hint="这里改的是趋势确认、波动限制和训练/验证/回测漂移容忍度。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="rule_min_ema20_gap_pct" defaultValue={String(controls.rule_min_ema20_gap_pct ?? "0")} placeholder="EMA20 最低偏离 %" />
                <ConfigInput name="rule_min_ema55_gap_pct" defaultValue={String(controls.rule_min_ema55_gap_pct ?? "0")} placeholder="EMA55 最低偏离 %" />
                <ConfigInput name="rule_max_atr_pct" defaultValue={String(controls.rule_max_atr_pct ?? "5")} placeholder="ATR 最高波动 %" />
                <ConfigInput name="rule_min_volume_ratio" defaultValue={String(controls.rule_min_volume_ratio ?? "1")} placeholder="最低量能比" />
                <ConfigInput name="strict_rule_min_ema20_gap_pct" defaultValue={String(controls.strict_rule_min_ema20_gap_pct ?? "1.2")} placeholder="严格模板 EMA20 最低偏离 %" />
                <ConfigInput name="strict_rule_min_ema55_gap_pct" defaultValue={String(controls.strict_rule_min_ema55_gap_pct ?? "1.8")} placeholder="严格模板 EMA55 最低偏离 %" />
                <ConfigInput name="strict_rule_max_atr_pct" defaultValue={String(controls.strict_rule_max_atr_pct ?? "4.5")} placeholder="严格模板 ATR 最高波动 %" />
                <ConfigInput name="strict_rule_min_volume_ratio" defaultValue={String(controls.strict_rule_min_volume_ratio ?? "1.05")} placeholder="严格模板最低量能比" />
                <ConfigInput name="consistency_max_validation_backtest_return_gap_pct" defaultValue={String(controls.consistency_max_validation_backtest_return_gap_pct ?? "1.5")} placeholder="验证/回测最大收益差 %" />
                <ConfigInput name="consistency_max_training_validation_positive_rate_gap" defaultValue={String(controls.consistency_max_training_validation_positive_rate_gap ?? "0.2")} placeholder="训练/验证最大正收益比例差" />
                <ConfigInput name="consistency_max_training_validation_return_gap_pct" defaultValue={String(controls.consistency_max_training_validation_return_gap_pct ?? "1.5")} placeholder="训练/验证最大收益差 %" />
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
            <ConfigField label="门控开关" hint="这里可以明确控制规则门、验证门、回测门、一致性门和 live 门是否参与放行。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigSelect
                  name="enable_rule_gate"
                  defaultValue={String(Boolean(controls.enable_rule_gate))}
                  options={[
                    { value: "true", label: "开启规则门" },
                    { value: "false", label: "关闭规则门" },
                  ]}
                />
                <ConfigSelect
                  name="enable_validation_gate"
                  defaultValue={String(Boolean(controls.enable_validation_gate))}
                  options={[
                    { value: "true", label: "开启验证门" },
                    { value: "false", label: "关闭验证门" },
                  ]}
                />
                <ConfigSelect
                  name="enable_backtest_gate"
                  defaultValue={String(Boolean(controls.enable_backtest_gate))}
                  options={[
                    { value: "true", label: "开启回测门" },
                    { value: "false", label: "关闭回测门" },
                  ]}
                />
                <ConfigSelect
                  name="enable_consistency_gate"
                  defaultValue={String(Boolean(controls.enable_consistency_gate))}
                  options={[
                    { value: "true", label: "开启一致性门" },
                    { value: "false", label: "关闭一致性门" },
                  ]}
                />
                <ConfigSelect
                  name="enable_live_gate"
                  defaultValue={String(Boolean(controls.enable_live_gate))}
                  options={[
                    { value: "true", label: "开启 live 门" },
                    { value: "false", label: "关闭 live 门" },
                  ]}
                />
              </div>
            </ConfigField>
          </WorkbenchConfigCard>

          <WorkbenchConfigCard
            title="实验对比与复盘窗口"
            description="这里改的是评估中心一次展示多少轮实验和多少条复盘，保存后这页会按新的窗口重新整理。"
            scope="operations"
            returnTo="/evaluation"
            disabled={!configEditable}
            disabledReason={unavailableConfigReason}
          >
            <ConfigField label="实验对比窗口" hint="这里决定评估中心会保留最近多少轮训练、推理和最近两轮变化记录。">
              <ConfigInput name="comparison_run_limit" type="number" min={1} max={20} step={1} defaultValue={comparisonRunLimit} />
            </ConfigField>
            <ConfigField label="复盘窗口" hint="这里决定评估中心和任务页最多展示最近多少条统一复盘记录。">
              <ConfigInput name="review_limit" type="number" min={1} max={100} step={1} defaultValue={reviewLimit} />
            </ConfigField>
          </WorkbenchConfigCard>

          <DataTable
            columns={["准入门槛目录", "当前口径", "为什么重要", "说明"]}
            rows={thresholdCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                readText(item.label, "n/a"),
                readText(item.current, "当前没有门槛摘要"),
                readText(item.effect, "当前没有影响说明"),
                readText(item.detail, "当前没有额外说明"),
              ],
            }))}
            emptyTitle="当前还没有准入门槛目录"
            emptyDetail="先恢复评估工作台，系统才会把 dry-run、验证、一致性和 live 的口径整理出来。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>阶段筛选</CardTitle>
              <CardDescription>先决定现在只看继续研究、可进 dry-run，还是已经够格进入 live 的候选，再往下看推荐和淘汰原因。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form method="get" action="/evaluation" className="grid gap-3 rounded-2xl border border-border/60 bg-background/40 p-4 md:grid-cols-[minmax(0,1fr)_auto]">
                <div className="space-y-2">
                  <p className="eyebrow">当前只看哪一层</p>
                  <select
                    name="stageView"
                    defaultValue={stageView}
                    className="flex h-11 w-full rounded-xl border border-border/70 bg-background px-3 text-sm text-foreground shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  >
                    <option value="all">全部候选</option>
                    <option value="research">继续研究</option>
                    <option value="dry_run">可进 dry-run</option>
                    <option value="live">可进 live</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <FormSubmitButton
                    type="submit"
                    variant="terminal"
                    size="sm"
                    idleLabel="更新阶段视图"
                    pendingLabel="更新阶段视图中…"
                    pendingHint="页面会按你选的阶段重新整理候选、门控和推进板。"
                  />
                </div>
              </form>

              <div className="grid gap-3 md:grid-cols-2">
                <InfoBlock label="当前阶段视图" value={stageFilterSummary.currentLabel} />
                <InfoBlock label="当前视图候选数" value={String(filteredLeaderboard.length)} />
                <InfoBlock label="继续研究" value={String(stageFilterSummary.researchCount)} />
                <InfoBlock label="可进 dry-run" value={String(stageFilterSummary.dryRunCount)} />
                <InfoBlock label="可进 live" value={String(stageFilterSummary.liveCount)} />
                <InfoBlock label="阶段说明" value={stageFilterSummary.detail} />
              </div>
            </CardContent>
          </Card>

          <DataTable
            columns={["实验排行榜", "模板适配", "推荐原因", "下一步动作", "淘汰原因"]}
            rows={filteredLeaderboard.map((item, index) => {
              const row = asRecord(item);
              const reasons = String(row.elimination_reason ?? "已通过");
              return {
                id: `${row.symbol ?? index}`,
                cells: [
                  String(row.symbol ?? "n/a"),
                  String(row.template_fit_headline ?? row.template_fit_detail ?? "当前还没有模板适配说明"),
                  String(row.recommendation_reason ?? row.score ?? row.review_status ?? "n/a"),
                  String(row.next_action ?? "continue_research"),
                  reasons,
                ],
              };
            })}
            emptyTitle="还没有实验排行榜"
            emptyDetail="当前阶段视图下还没有候选，先切回全部候选，或重新运行研究训练和推理。"
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
              <CardTitle>实验对齐概况</CardTitle>
              <CardDescription>不只是数据，而是把训练、推理、模型和快照一起讲清楚，缺上下文也能直接看出。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm leading-6 text-muted-foreground">{experimentAlignmentNote}</p>
              <div className="grid gap-3 md:grid-cols-2">
                <InfoBlock label="训练模型" value={trainingModelVersion} />
                <InfoBlock label="推理模型" value={inferenceModelVersion} />
                <InfoBlock label="训练数据快照" value={trainingDatasetSnapshot} />
                <InfoBlock label="推理数据快照" value={inferenceDatasetSnapshot} />
              </div>
              <p className="text-xs leading-5 text-foreground/70">对齐内容：{experimentAlignmentContent}</p>
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>最近两轮变化焦点</CardTitle>
              <CardDescription>先抓住这一轮最核心的变化，再决定要不要继续放量或回退配置。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="关键变化" value={String(deltaOverview.headline ?? "当前还没有变化焦点")} />
              <InfoBlock label="不可直接比较原因" value={String(deltaOverview.detail ?? "当前没有额外说明")} />
              <InfoBlock label="当前状态" value={formatComparisonReadiness(String(deltaOverview.status ?? "unavailable"))} />
              <InfoBlock label="补充说明" value={String(deltaOverview.note ?? "当前没有补充说明")} />
            </CardContent>
          </Card>

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
              <p className="eyebrow">为什么推荐</p>
              <CardTitle>推荐原因</CardTitle>
              <CardDescription>这里直接展示系统为什么推荐这个币继续进入下一步。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="统一范围契约" value={candidateScopeHeadline} />
              <InfoBlock label="为什么这样分层" value={candidateScopeDetail} />
              <InfoBlock
                label="研究候选池"
                value={candidateSymbols.length ? candidateSymbols.join(" / ") : "当前未配置"}
              />
              <InfoBlock label="候选池预设" value={`${candidatePoolPresetKey} / ${candidatePoolPresetDetail}`} />
              <InfoBlock
                label="live 子集"
                value={liveAllowedSymbols.length ? liveAllowedSymbols.join(" / ") : "当前未配置"}
              />
              <InfoBlock label="live 子集预设" value={`${liveSubsetPresetKey} / ${liveSubsetPresetDetail}`} />
              <InfoBlock label="推荐标的" value={String((recommendedCandidate.symbol ?? workspace.overview.recommended_symbol) || "未推荐")} />
              <InfoBlock label="推荐动作" value={String((bestExperiment.next_action ?? researchReview.next_action ?? workspace.overview.recommended_action) || "继续研究")} />
              <InfoBlock label="推荐分数" value={String(recommendedCandidate.score ?? "n/a")} />
              <InfoBlock label="更适合哪套模板" value={String(recommendationTemplateFit.headline ?? "当前还没有模板适配结论。")} />
              <InfoBlock label="为什么先推进" value={String(recommendationExplanation.detail ?? "当前还没有推荐理由说明。")} />
              <InfoBlock label="模板适配说明" value={String(recommendationTemplateFit.detail ?? "当前还没有模板适配说明。")} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>运行口径对照</CardTitle>
              <CardDescription>把候选池、live 子集、长期运行预设和自动化运行预设放在一起看，方便直接判断这轮为什么推荐、为什么还不能继续放量。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="当前范围说明" value={candidateScopeHeadline} />
              <InfoBlock label="下一步" value={candidateScopeNextStep} />
              <InfoBlock label="候选池预设" value={`${candidatePoolPresetKey} / ${candidatePoolPresetDetail}`} />
              <InfoBlock label="live 子集预设" value={`${liveSubsetPresetKey} / ${liveSubsetPresetDetail}`} />
              <InfoBlock label="长期运行预设" value={`${operationsPresetKey} / ${operationsPresetDetail}`} />
              <InfoBlock label="自动化运行预设" value={`${automationPresetKey} / ${automationPresetDetail}`} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">推荐摘要</p>
              <CardTitle>{String(recommendationExplanation.headline ?? "当前还没有推荐摘要")}</CardTitle>
              <CardDescription>{String(recommendationExplanation.detail ?? "先完成训练和推理，系统才会把推荐理由压成一句话。")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-6 text-muted-foreground">
              <div className="grid gap-3 md:grid-cols-2">
                <InfoBlock label="这一轮更值得推进什么" value={String(recommendationExplanation.headline ?? workspace.overview.recommended_symbol ?? "当前还没有明确推荐")} />
                <InfoBlock label="先推荐谁" value={String(workspace.overview.recommended_symbol ?? recommendedCandidate.symbol ?? "当前还没有推荐标的")} />
                <InfoBlock label="更适合哪套模板" value={String(recommendationTemplateFit.headline ?? "当前还没有模板适配结论。")} />
                <InfoBlock label="为什么推荐" value={String(recommendationExplanation.detail ?? researchReview.result ?? "当前还没有推荐理由说明。")} />
                <InfoBlock label="模板适配说明" value={String(recommendationTemplateFit.detail ?? "当前还没有模板适配说明。")} />
                <InfoBlock label="推荐下一步" value={String(bestExperiment.next_action ?? researchReview.next_action ?? workspace.overview.recommended_action ?? "继续研究")} />
              </div>
              {(Array.isArray(recommendationExplanation.evidence) ? recommendationExplanation.evidence : []).length ? (
                (recommendationExplanation.evidence as unknown[]).map((item, index) => (
                  <p key={`recommendation-evidence-${index}`}>{String(item)}</p>
                ))
              ) : (
                <p>当前还没有推荐证据。</p>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前最佳实验</CardTitle>
              <CardDescription>这里是研究侧的最佳实验记录，用来解释当前结论为什么成立，但它不是当前动作本身。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="最佳标的" value={String(bestExperiment.symbol ?? "未推荐")} />
              <InfoBlock label="推荐阶段" value={String(bestExperiment.recommended_stage ?? "dry_run")} />
              <InfoBlock
                label="更值得进入 dry-run"
                value={
                  String(bestExperiment.recommended_stage ?? "dry_run") === "dry_run"
                    ? String(bestExperiment.reason ?? "当前这一轮更适合先进入 dry-run。")
                    : "当前不是 dry-run 优先实验。"
                }
              />
              <InfoBlock
                label="更值得进入 live"
                value={
                  String(bestExperiment.recommended_stage ?? "") === "live"
                    ? String(bestExperiment.reason ?? "当前这一轮更适合直接进入 live。")
                    : "当前还没有实验足够稳到直接进入 live。"
                }
              />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>分阶段最佳候选</CardTitle>
              <CardDescription>把 dry-run 和 live 两个阶段拆开看，先分清是应该继续验证，还是已经够格进入更严格阶段。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock
                label="为什么先看候选池"
                value="研究推荐会先在这组共享候选池里比较，只有通过更严门控的子集，后面才会继续进入 live。"
              />
              <InfoBlock
                label="为什么这里只到 dry-run"
                value={
                  liveAllowedSymbols.length
                    ? `当前 live 只放行 ${liveAllowedSymbols.join(" / ")} 这组更严子集，其他推荐先停在 dry-run。`
                    : "当前还没有配置 live 子集，所以推荐只会先停在 dry-run。"
                }
              />
              <InfoBlock
                label="更值得进入 dry-run"
                value={`${readText(bestDryRunCandidate.symbol, "当前还没有 dry-run 候选")} / ${readText(bestDryRunCandidate.reason, "当前还没有足够候选满足 dry-run 放行条件。")}`}
              />
              <InfoBlock
                label="更值得进入 live"
                value={`${readText(bestLiveCandidate.symbol, "当前还没有 live 候选")} / ${readText(bestLiveCandidate.reason, "当前还没有足够候选满足 live 放行条件。")}`}
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>研究侧当前摘要</CardTitle>
              <CardDescription>这一组只解释研究侧现在怎么想，真正当前动作以上面的仲裁结论为准。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="当前推荐候选" value={readText(workspace.overview.recommended_symbol, "当前还没有推荐候选")} />
              <InfoBlock label="当前判断" value={readText(workspace.stage_decision_summary?.headline, "当前还没有阶段判断")} />
              <InfoBlock label="推荐原因" value={readText(workspace.stage_decision_summary?.why_recommended, "当前还没有推荐原因")} />
              <InfoBlock label="模板适配" value={readText(workspace.stage_decision_summary?.template_fit, "当前还没有模板适配说明")} />
              <InfoBlock label="研究与执行差异" value={readText(workspace.stage_decision_summary?.execution_gap, "当前还没有差异摘要")} />
              <InfoBlock label="下一步" value={readText(workspace.stage_decision_summary?.next_step, "continue_research")} />
            </CardContent>
          </Card>

          <DataTable
            columns={["研究 / 回测 / 执行对照", "研究结论", "回测结论", "执行结果", "为什么要看它"]}
            rows={alignmentMetricRows.map((item, index) => ({
              id: `${String(item.metric ?? index)}-${index}`,
              cells: [
                String(item.metric ?? "对照项"),
                String(item.research ?? "当前没有研究结论"),
                String(item.backtest ?? "当前没有回测结论"),
                String(item.execution ?? "当前没有执行结果"),
                String(item.impact ?? "当前没有额外说明"),
              ],
            }))}
            emptyTitle="当前还没有研究 / 回测 / 执行对照"
            emptyDetail="先生成研究、回测和执行结果，这里才会按同一张表对照。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>研究侧主要阻塞</CardTitle>
              <CardDescription>这一组只解释研究门控为什么拦住候选，不直接代替当前仲裁动作。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="当前主要阻塞" value={readText(workspace.stage_decision_summary?.why_blocked, "当前没有明显阻塞")} />
              <InfoBlock label="修复方向" value={readText(eliminationExplanation.next_step, readText(workspace.alignment_story?.next_step, "先继续观察。"))} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">为什么淘汰</p>
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
              <p className="eyebrow">淘汰摘要</p>
              <CardTitle>{String(eliminationExplanation.headline ?? "当前还没有淘汰摘要")}</CardTitle>
              <CardDescription>{String(eliminationExplanation.detail ?? "先积累足够候选，系统才会把淘汰原因压成一句话。")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-6 text-muted-foreground">
              <div className="grid gap-3 md:grid-cols-2">
                <InfoBlock label="先淘汰谁" value={String(eliminationExplanation.primary_symbol ?? eliminationExplanation.symbol ?? "当前还没有淘汰标的")} />
                <InfoBlock label="当前卡在哪个门" value={String(eliminationExplanation.primary_gate ?? "当前还没有主要门控")} />
                <InfoBlock label="当前模板为什么先不适合" value={String(eliminationTemplateFit.headline ?? "当前还没有模板适配结论。")} />
                <InfoBlock label="为什么淘汰" value={String(eliminationExplanation.detail ?? "当前还没有淘汰原因说明。")} />
                <InfoBlock label="模板适配说明" value={String(eliminationTemplateFit.detail ?? "当前还没有模板适配说明。")} />
                <InfoBlock label="先怎么修" value={String(eliminationExplanation.next_step ?? "当前还没有修复方向。")} />
              </div>
              {(Array.isArray(eliminationExplanation.evidence) ? eliminationExplanation.evidence : []).length ? (
                (eliminationExplanation.evidence as unknown[]).map((item, index) => (
                  <p key={`elimination-evidence-${index}`}>{String(item)}</p>
                ))
              ) : (
                <p>当前还没有淘汰证据。</p>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>淘汰原因说明</CardTitle>
              <CardDescription>这里直接解释被拦住的候选最主要卡在哪个门槛。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {filteredLeaderboard.length ? filteredLeaderboard.map((item, index) => {
                const row = asRecord(item);
                return (
                  <p key={`${row.symbol ?? index}`}>
                    {String(row.symbol ?? "n/a")}：{String(row.elimination_reason ?? "已通过")}
                  </p>
                );
              }) : <p>当前阶段视图下还没有可解释的候选淘汰记录。</p>}
            </CardContent>
          </Card>

          <DataTable
            columns={["门控分解", "规则门", "验证门", "回测门", "一致性门", "live 门", "当前卡点"]}
            rows={filteredGateMatrixRows.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${row.symbol ?? index}`,
                cells: [
                  String(row.symbol ?? "n/a"),
                  String(row.rule_gate ?? "n/a"),
                  String(row.validation_gate ?? "n/a"),
                  String(row.backtest_gate ?? "n/a"),
                  String(row.consistency_gate ?? "n/a"),
                  String(row.live_gate ?? "n/a"),
                  String(row.primary_reason ?? row.blocking_gate ?? "n/a"),
                ],
              };
            })}
            emptyTitle="当前还没有门控分解"
            emptyDetail="当前阶段视图下还没有门控分解，先切回全部候选或重新运行研究。"
          />

          <DataTable
            columns={["候选推进板", "更适合哪套模板", "更适合去哪一层", "dry-run / live", "当前卡点", "为什么推荐或淘汰", "下一步"]}
            rows={filteredLeaderboard.map((item, index) => {
              const row = asRecord(item);
              const symbol = String(row.symbol ?? `candidate-${index}`);
              const gateRow = gateMatrixBySymbol.get(symbol) ?? {};
              const nextAction = String(row.next_action ?? "continue_research");
              const suggestedStage = nextAction.includes("live")
                ? "live"
                : nextAction.includes("dry")
                  ? "dry-run"
                  : "继续研究";
              const dryRunFit = gateRow.allowed_to_dry_run ? "可进" : "未过";
              const liveFit = gateRow.allowed_to_live ? "可进" : "未过";
              const why = String(row.recommendation_reason ?? row.elimination_reason ?? row.review_status ?? "当前没有额外说明");
              const block = String(gateRow.primary_reason ?? gateRow.blocking_gate ?? row.elimination_reason ?? "当前没有明显阻断");
              return {
                id: symbol,
                cells: [
                  `${symbol} / ${String(row.score ?? "n/a")}`,
                  String(row.template_fit_headline ?? row.template_fit_detail ?? "当前还没有模板适配说明"),
                  suggestedStage,
                  `${dryRunFit} / ${liveFit}`,
                  block,
                  why,
                  nextAction,
                ],
              };
            })}
            emptyTitle="当前还没有候选推进板"
            emptyDetail="当前阶段视图下还没有候选推进板，先切回全部候选，或重新完成研究训练和推理。"
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

          <DataTable
            columns={["最近训练实验快照", "模型", "数据快照", "持有窗口", "净收益 / Sharpe", "验证放行"]}
            rows={workspace.recent_training_runs.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${row.run_id ?? index}`,
                cells: [
                  `${String(row.run_id ?? "n/a")} / ${String(row.status ?? "n/a")}`,
                  `${String(row.model_key ?? "n/a")} / ${String(row.model_version ?? "n/a")}`,
                  String(row.dataset_snapshot_id ?? "n/a"),
                  String(row.holding_window ?? "n/a"),
                  `${String(row.net_return_pct ?? "n/a")} / ${String(row.sharpe ?? "n/a")}`,
                  String(row.force_validation_top_candidate ?? "否"),
                ],
              };
            })}
            emptyTitle="当前还没有最近训练实验快照"
            emptyDetail={`先跑训练，系统才会把最近 ${comparisonRunLimit} 轮训练快照整理到这里。`}
          />

          <DataTable
            columns={["最近推理实验快照", "模型", "数据快照", "标签方式", "信号数 / 胜率", "验证放行"]}
            rows={workspace.recent_inference_runs.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${row.run_id ?? index}`,
                cells: [
                  `${String(row.run_id ?? "n/a")} / ${String(row.status ?? "n/a")}`,
                  `${String(row.model_key ?? "n/a")} / ${String(row.model_version ?? "n/a")}`,
                  String(row.dataset_snapshot_id ?? "n/a"),
                  `${String(row.label_mode ?? "n/a")} / ${String(row.window_mode ?? "n/a")}`,
                  `${String(row.signal_count ?? "n/a")} / ${String(row.win_rate ?? "n/a")}`,
                  String(row.force_validation_top_candidate ?? "否"),
                ],
              };
            })}
            emptyTitle="当前还没有最近推理实验快照"
            emptyDetail={`先跑推理，系统才会把最近 ${comparisonRunLimit} 轮推理快照整理到这里。`}
          />

          <DataTable
            columns={["研究到执行时间线", "最近状态", "最近完成时间", "说明"]}
            rows={workspace.workflow_alignment_timeline.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${row.task_type ?? index}`,
                cells: [
                  String(row.label ?? row.task_type ?? "task"),
                  String(row.status ?? "waiting"),
                  String(row.finished_at ?? row.requested_at ?? "n/a"),
                  String(row.detail ?? "当前没有额外说明"),
                ],
              };
            })}
            emptyTitle="当前还没有研究到执行时间线"
            emptyDetail="先跑一轮研究、执行和复盘，系统才会把最近时间线整理到这里。"
          />

          <DataTable
            columns={["最近复盘记录", "状态", "完成时间", "结果摘要"]}
            rows={recentReviewTasks.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${row.task_type ?? index}-${row.finished_at ?? index}`,
                cells: [
                  String(row.task_type ?? "review"),
                  String(row.status ?? "waiting"),
                  String(row.finished_at ?? row.requested_at ?? "n/a"),
                  String(row.result_summary ?? "当前没有结果摘要"),
                ],
              };
            })}
            emptyTitle="当前还没有最近复盘记录"
            emptyDetail={`先积累几轮研究、执行和复盘，系统才会把最近 ${reviewLimit} 条记录整理到这里。`}
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>最近两轮对比</CardTitle>
              <CardDescription>{`参数与结果一起看，再把关键变化、配置变化和不可直接比较原因拆开看。这里最多展示最近 ${comparisonRunLimit} 组同类型变化。`}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {workspace.run_deltas.length ? (
                <DataTable
                  columns={["最近两轮对比", "关键变化", "可比性判断", "不可直接比较原因", "净收益差", "Sharpe 差", "胜率差", "说明"]}
                  rows={workspace.run_deltas.map((item, index) => {
                    const row = asRecord(item);
                    const changedFields = buildChangedFieldSummary(row);
                    return {
                      id: `${row.run_type ?? index}`,
                      cells: [
                        `${String(row.run_type ?? "run")} / ${String(row.previous_run_id ?? "n/a")} → ${String(row.current_run_id ?? "n/a")}`,
                        String(row.change_summary ?? "当前没有变化摘要"),
                        formatComparisonReadiness(String(row.comparison_readiness ?? "unavailable")),
                        String(row.comparison_reason ?? "当前没有额外说明"),
                        String(row.net_return_delta ?? "n/a"),
                        String(row.sharpe_delta ?? "n/a"),
                        String(row.win_rate_delta ?? "n/a"),
                        `${changedFields} / ${String(row.note ?? "当前还没有说明")}`,
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
              <CardTitle>自选实验对比</CardTitle>
              <CardDescription>不只看系统默认最近两轮，你也可以手动挑两轮训练或推理，直接比较哪一轮更值得继续推进。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form method="get" action="/evaluation" className="grid gap-3 rounded-2xl border border-border/60 bg-background/40 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                <div className="space-y-2">
                  <p className="eyebrow">对比对象 A</p>
                  <select
                    name="compareA"
                    defaultValue={compareA}
                    className="flex h-11 w-full rounded-xl border border-border/70 bg-background px-3 text-sm text-foreground shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  >
                    {comparisonOptions.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <p className="eyebrow">对比对象 B</p>
                  <select
                    name="compareB"
                    defaultValue={compareB}
                    className="flex h-11 w-full rounded-xl border border-border/70 bg-background px-3 text-sm text-foreground shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  >
                    {comparisonOptions.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-end">
                  <FormSubmitButton
                    type="submit"
                    variant="terminal"
                    size="sm"
                    idleLabel="更新对比"
                    pendingLabel="更新对比中…"
                    pendingHint="页面会按你选的两轮实验重新整理对比结果。"
                    disabled={comparisonOptions.length < 2}
                  />
                </div>
              </form>

              <div className="grid gap-3 md:grid-cols-2">
                <InfoBlock label="可比性判断" value={manualCompare.readiness} />
                <InfoBlock label="说明" value={manualCompare.note} />
                <InfoBlock label="更值得推进哪一轮" value={manualCompare.preferredRun} />
                <InfoBlock label="当前建议" value={manualCompare.nextAction} />
              </div>

              <DataTable
                columns={["自选实验对比", "对比对象 A", "对比对象 B", "变化说明"]}
                rows={manualCompare.rows}
                emptyTitle="当前还没有足够实验可供手动对比"
                emptyDetail="先至少积累两轮训练或推理，再回来挑选你想比较的两轮。"
              />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前结果与配置对齐</CardTitle>
              <CardDescription>先确认当前评估结果是不是仍然基于这页右上角的最新门槛。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm leading-6 text-muted-foreground">{configAlignmentCallout}</p>
              <div className="grid gap-3 md:grid-cols-2">
                <InfoBlock label="对齐状态" value={String(configAlignment.status ?? "unavailable")} />
                <InfoBlock label="说明" value={String(configAlignment.note ?? "当前还没有可用对齐说明")} />
                <InfoBlock label="配置变化" value={Array.isArray(configAlignment.stale_fields) && configAlignment.stale_fields.length ? configAlignment.stale_fields.map(String).join(" / ") : "当前没有发现漂移字段"} />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>配置差异拆解</CardTitle>
              <CardDescription>不只告诉你“变了”，而是直接按数据、特征、研究、回测和门槛拆开，方便判断这两轮还能不能直接比。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="数据配置" value={configDiffSections.data} />
              <InfoBlock label="特征配置" value={configDiffSections.features} />
              <InfoBlock label="研究配置" value={configDiffSections.research} />
              <InfoBlock label="回测配置" value={configDiffSections.backtest} />
              <InfoBlock label="门槛配置" value={configDiffSections.thresholds} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">研究和执行差在哪里</p>
              <CardTitle>{String(alignmentStory.headline ?? "当前还没有差异摘要")}</CardTitle>
              <CardDescription>{String(alignmentStory.detail ?? "先完成研究和执行，系统才会把差异压成一句话。")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {(Array.isArray(alignmentStory.evidence) ? alignmentStory.evidence : []).length ? (
                (alignmentStory.evidence as unknown[]).map((item, index) => (
                  <p key={`alignment-story-${index}`}>{String(item)}</p>
                ))
              ) : (
                <p>当前还没有研究和执行差异证据。</p>
              )}
            </CardContent>
          </Card>

          <DataTable
            columns={["差异条目", "当前差在哪", "会影响什么", "修复优先级"]}
            rows={alignmentGaps.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${String(row.code ?? "gap")}-${index}`,
                cells: [
                  String(row.label ?? row.code ?? "差异"),
                  String(row.detail ?? "当前没有差异说明"),
                  String(row.impact ?? "当前没有影响说明"),
                  String(row.priority ?? "normal"),
                ],
              };
            })}
            emptyTitle="当前没有研究与执行差异条目"
            emptyDetail="如果研究结果和执行结果一致，这里会保持为空。"
          />

          <DataTable
            columns={["修复动作", "先处理什么", "为什么要先做", "下一步去哪"]}
            rows={alignmentActions.map((item, index) => {
              const row = asRecord(item);
              return {
                id: `${String(row.code ?? "action")}-${index}`,
                cells: [
                  String(row.label ?? row.code ?? "动作"),
                  String(row.detail ?? "当前没有动作说明"),
                  String(row.reason ?? "当前没有原因说明"),
                  String(row.target ?? row.next_step ?? "继续评估"),
                ],
              };
            })}
            emptyTitle="当前没有额外修复动作"
            emptyDetail="如果当前研究和执行已经对齐，这里不会再给额外修复动作。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">差异摘要</p>
              <p className="eyebrow">研究与执行对齐</p>
              <CardTitle>研究结果 vs 执行结果</CardTitle>
              <CardDescription>这里不只显示 matched / unmatched，而是把对齐结论、对齐解释、最近执行摘要和建议动作直接讲清楚。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="研究和执行差几步" value={String(alignmentStory.headline ?? executionAlignmentNarrative.result ?? "当前还没有阶段差异说明")} />
              <InfoBlock label="研究和执行差在哪里" value={String(alignmentStory.detail ?? executionAlignmentNarrative.detail ?? "当前还没有差异说明")} />
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

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>研究与执行差异</CardTitle>
              <CardDescription>把当前差在哪、严重程度和先处理什么讲清楚，避免只看到“未对齐”。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="当前差在哪" value={String(alignmentDetails.difference_summary ?? "当前没有差异摘要")} />
              <InfoBlock label="严重程度" value={formatGapSeverity(String(alignmentDetails.difference_severity ?? "low"))} />
              <InfoBlock
                label="差异明细"
                value={
                  alignmentGaps.length
                    ? alignmentGaps.map((item) => String(asRecord(item).detail ?? "")).filter(Boolean).join(" / ")
                    : "当前没有差异明细"
                }
              />
              <InfoBlock label="先处理什么" value={String(alignmentDetails.next_step ?? "继续观察当前评估结果")} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>下一步动作</CardTitle>
              <CardDescription>按当前对齐状态，直接给出下一步应该回哪一层处理。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {alignmentActions.length ? alignmentActions.map((item, index) => {
                const row = asRecord(item);
                return (
                  <p key={`${String(row.label ?? index)}-${index}`}>
                    {index + 1}. {String(row.label ?? "继续处理")}：{String(row.detail ?? "")}
                  </p>
                );
              }) : <p>当前还没有明确下一步动作。</p>}
              <div className="flex flex-wrap gap-3 pt-2">
                <Button asChild variant="outline">
                  <Link href="/research">回到研究工作台</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href="/backtest">去回测工作台</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href="/strategies">去策略页看执行</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href="/tasks">去任务页看自动化</Link>
                </Button>
              </div>
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

function formatComparisonReadiness(value: string): string {
  const mapping: Record<string, string> = {
    ready: "可以直接比",
    limited: "只能看方向，不能直接归因",
    unavailable: "当前还不能直接比",
  };
  return mapping[value] ?? "当前还不能直接比";
}

function formatGapSeverity(value: string): string {
  const mapping: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
    unknown: "待确认",
  };
  return mapping[value] ?? "待确认";
}

function readSearchParam(value: string | string[] | undefined, fallback: string): string {
  if (Array.isArray(value)) {
    return String(value[0] ?? fallback).trim() || fallback;
  }
  return String(value ?? fallback).trim() || fallback;
}

function buildExperimentCompareOptions({
  trainingRuns,
  inferenceRuns,
  limit,
}: {
  trainingRuns: unknown[];
  inferenceRuns: unknown[];
  limit: number;
}) {
  const rows = [...(Array.isArray(trainingRuns) ? trainingRuns : []), ...(Array.isArray(inferenceRuns) ? inferenceRuns : [])]
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    .slice(0, Math.max(limit, 2));

  return rows.map((row, index) => {
    const runType = readText(row.run_type, index < (Array.isArray(trainingRuns) ? trainingRuns.length : 0) ? "training" : "inference");
    const runId = readText(row.run_id, `run-${index + 1}`);
    const model = readText(row.model_key, "n/a");
    const snapshot = readText(row.dataset_snapshot_id, "n/a");
    return {
      id: `${runType}:${runId}`,
      runType,
      runId,
      label: `${runType} / ${runId} / ${model} / ${snapshot}`,
      row,
    };
  });
}

function buildManualExperimentComparison({
  left,
  right,
}: {
  left: { id: string; runType: string; runId: string; label: string; row: Record<string, unknown> } | undefined;
  right: { id: string; runType: string; runId: string; label: string; row: Record<string, unknown> } | undefined;
}) {
  if (!left || !right) {
    return {
      readiness: "当前还不能直接比",
      note: "先至少保留两轮训练或推理快照，再回来手动挑选。",
      preferredRun: "当前没有可比较的实验",
      nextAction: "继续积累实验",
      rows: [] as Array<{ id: string; cells: string[] }>,
    };
  }

  const comparable = left.runType === right.runType;
  const leftNet = readMetric(left.row.net_return_pct);
  const rightNet = readMetric(right.row.net_return_pct);
  const leftSharpe = readMetric(left.row.sharpe);
  const rightSharpe = readMetric(right.row.sharpe);
  const leftWin = readMetric(left.row.win_rate);
  const rightWin = readMetric(right.row.win_rate);
  const preferredRun =
    comparable && leftNet !== null && rightNet !== null
      ? leftNet >= rightNet
        ? left.label
        : right.label
      : "先按同类型实验比较后再决定";
  const nextAction = comparable ? "先看净收益和 Sharpe，再决定是否继续推进。" : "当前建议先挑同类型实验再比较。";

  return {
    readiness: comparable ? "可以直接比" : "只能看方向，不能直接归因",
    note: comparable
      ? "当前两轮属于同一种实验类型，可以直接比较收益、Sharpe 和配置差异。"
      : "当前选择的是不同类型实验，只适合先看方向差异，不适合直接归因到模型或标签。",
    preferredRun,
    nextAction,
    rows: [
      buildManualCompareRow("实验类型", left.runType, right.runType, comparable ? "同类型，可直接比较。" : "不同类型，只适合先看方向。"),
      buildManualCompareRow("研究预设", readText(left.row.research_preset_key, "n/a"), readText(right.row.research_preset_key, "n/a"), compareText(readText(left.row.research_preset_key, "n/a"), readText(right.row.research_preset_key, "n/a"))),
      buildManualCompareRow("模型选择", readText(left.row.model_key, "n/a"), readText(right.row.model_key, "n/a"), compareText(readText(left.row.model_key, "n/a"), readText(right.row.model_key, "n/a"))),
      buildManualCompareRow("标签预设", readText(left.row.label_preset_key, "n/a"), readText(right.row.label_preset_key, "n/a"), compareText(readText(left.row.label_preset_key, "n/a"), readText(right.row.label_preset_key, "n/a"))),
      buildManualCompareRow("标签方式", readText(left.row.label_mode, "n/a"), readText(right.row.label_mode, "n/a"), compareText(readText(left.row.label_mode, "n/a"), readText(right.row.label_mode, "n/a"))),
      buildManualCompareRow("标签触发口径", readText(left.row.label_trigger_basis, "n/a"), readText(right.row.label_trigger_basis, "n/a"), compareText(readText(left.row.label_trigger_basis, "n/a"), readText(right.row.label_trigger_basis, "n/a"))),
      buildManualCompareRow("持有窗口", readText(left.row.holding_window, "n/a"), readText(right.row.holding_window, "n/a"), compareText(readText(left.row.holding_window, "n/a"), readText(right.row.holding_window, "n/a"))),
      buildManualCompareRow("数据快照", readText(left.row.dataset_snapshot_id, "n/a"), readText(right.row.dataset_snapshot_id, "n/a"), compareText(readText(left.row.dataset_snapshot_id, "n/a"), readText(right.row.dataset_snapshot_id, "n/a"))),
      buildManualCompareRow("净收益", formatMetricValue(left.row.net_return_pct), formatMetricValue(right.row.net_return_pct), compareNumericText(leftNet, rightNet, "%")),
      buildManualCompareRow("Sharpe", formatMetricValue(left.row.sharpe), formatMetricValue(right.row.sharpe), compareNumericText(leftSharpe, rightSharpe, "")),
      buildManualCompareRow("胜率", formatMetricValue(left.row.win_rate), formatMetricValue(right.row.win_rate), compareNumericText(leftWin, rightWin, "")),
      buildManualCompareRow(
        "当前建议",
        readText(left.row.force_validation_top_candidate, "否"),
        readText(right.row.force_validation_top_candidate, "否"),
        "如果两轮都稳，再继续看推荐原因和执行对齐。",
      ),
    ],
  };
}

function buildManualCompareRow(label: string, left: string, right: string, note: string) {
  return {
    id: label,
    cells: [label, left, right, note],
  };
}

function readMetric(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatMetricValue(value: unknown): string {
  const numeric = readMetric(value);
  return numeric === null ? readText(value, "n/a") : `${numeric}`;
}

function compareText(left: string, right: string): string {
  return left === right ? "两轮一致。" : `A=${left}，B=${right}。`;
}

function compareNumericText(left: number | null, right: number | null, suffix: string): string {
  if (left === null || right === null) {
    return "当前没有足够数值可比较。";
  }
  const diff = (left - right).toFixed(2);
  return `A-B=${diff}${suffix}`.replace("..", ".");
}

function resolveStageView(value: string) {
  if (value === "research" || value === "dry_run" || value === "live") {
    return value;
  }
  return "all";
}

function matchesStageView({
  row,
  gateRow,
  stageView,
}: {
  row?: Record<string, unknown> | undefined;
  gateRow?: Record<string, unknown> | undefined;
  stageView: string;
}) {
  if (stageView === "all") {
    return true;
  }
  const nextAction = String(row?.next_action ?? "").toLowerCase();
  const dryAllowed = Boolean(gateRow?.allowed_to_dry_run);
  const liveAllowed = Boolean(gateRow?.allowed_to_live);
  if (stageView === "live") {
    return liveAllowed || nextAction.includes("live");
  }
  if (stageView === "dry_run") {
    return (dryAllowed || nextAction.includes("dry")) && !liveAllowed;
  }
  return !dryAllowed && !liveAllowed && !nextAction.includes("dry") && !nextAction.includes("live");
}

function buildStageFilterSummary({
  leaderboard,
  gateMatrixBySymbol,
  currentStageView,
}: {
  leaderboard: Array<Record<string, unknown>>;
  gateMatrixBySymbol: Map<string, Record<string, unknown>>;
  currentStageView: string;
}) {
  const counts = {
    research: 0,
    dry_run: 0,
    live: 0,
  };
  leaderboard.forEach((item) => {
    const row = asRecord(item);
    const gateRow = gateMatrixBySymbol.get(String(row.symbol ?? "")) ?? {};
    if (matchesStageView({ row, gateRow, stageView: "live" })) {
      counts.live += 1;
      return;
    }
    if (matchesStageView({ row, gateRow, stageView: "dry_run" })) {
      counts.dry_run += 1;
      return;
    }
    counts.research += 1;
  });
  const labels: Record<string, string> = {
    all: "全部候选",
    research: "继续研究",
    dry_run: "可进 dry-run",
    live: "可进 live",
  };
  const detailMap: Record<string, string> = {
    all: "先总览全部候选，再决定要往研究、dry-run 还是 live 收缩。",
    research: "这里只保留还没过门的候选，适合先看为什么被拦下。",
    dry_run: "这里只保留已经够格进入 dry-run、但还没到 live 的候选。",
    live: "这里只保留已经够格进入小额 live 的候选。",
  };
  return {
    currentLabel: labels[currentStageView] ?? labels.all,
    detail: detailMap[currentStageView] ?? detailMap.all,
    researchCount: counts.research,
    dryRunCount: counts.dry_run,
    liveCount: counts.live,
  };
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item ?? "").trim()).filter((item) => item.length > 0);
}

function buildChangedFieldSummary(row: Record<string, unknown>) {
  const status = String(row.changed_fields_status ?? "ready");
  if (status === "unavailable") {
    return String(row.changed_fields_note ?? "当前实验账本缺少配置快照，暂时无法比较。");
  }
  const changedFields = normalizeChangedFields(row);
  return changedFields.length ? changedFields.join(" / ") : "当前没有额外配置变化";
}

function buildConfigDiffSections(row: Record<string, unknown>) {
  const status = String(row.changed_fields_status ?? "ready");
  if (status === "unavailable") {
    const note = String(row.changed_fields_note ?? "当前实验账本缺少配置快照，暂时无法比较最近两轮配置变化。");
    return {
      data: note,
      features: note,
      research: note,
      backtest: note,
      thresholds: note,
    };
  }
  const changedFields = normalizeChangedFields(row);
  const grouped = {
    data: [] as string[],
    features: [] as string[],
    research: [] as string[],
    backtest: [] as string[],
    thresholds: [] as string[],
  };
  changedFields.forEach((field) => {
    if (["样本长度", "回看天数", "窗口模式", "固定日期范围"].includes(field)) {
      grouped.data.push(field);
      return;
    }
    if (["缺失处理", "去极值", "标准化", "主判断因子", "辅助确认因子"].includes(field)) {
      grouped.features.push(field);
      return;
    }
    if (
      [
        "研究模板",
        "模型选择",
        "标签口径",
        "持有窗口",
        "最短持有天数",
        "最长持有天数",
        "训练比例",
        "验证比例",
        "测试比例",
        "最低置信度",
        "严格模板惩罚权重",
        "趋势权重",
        "量能权重",
        "震荡权重",
        "波动权重",
        "强制验证当前最优候选",
      ].includes(field)
    ) {
      grouped.research.push(field);
      return;
    }
    if (["回测手续费", "回测滑点", "成本模型"].includes(field)) {
      grouped.backtest.push(field);
      return;
    }
    grouped.thresholds.push(field);
  });
  return {
    data: grouped.data.length ? grouped.data.join(" / ") : "当前没有数据配置变化",
    features: grouped.features.length ? grouped.features.join(" / ") : "当前没有特征配置变化",
    research: grouped.research.length ? grouped.research.join(" / ") : "当前没有研究配置变化",
    backtest: grouped.backtest.length ? grouped.backtest.join(" / ") : "当前没有回测配置变化",
    thresholds: grouped.thresholds.length ? grouped.thresholds.join(" / ") : "当前没有门槛配置变化",
  };
}

function normalizeChangedFields(row: Record<string, unknown>) {
  const labelMap: Record<string, string> = {
    research_template: "研究模板",
    model_key: "模型选择",
    label_mode: "标签口径",
    force_validation_top_candidate: "强制验证当前最优候选",
    holding_window_label: "持有窗口",
    holding_window_min_days: "最短持有天数",
    holding_window_max_days: "最长持有天数",
    sample_limit: "样本长度",
    lookback_days: "回看天数",
    window_mode: "窗口模式",
    start_date: "固定日期范围",
    end_date: "固定日期范围",
    missing_policy: "缺失处理",
    outlier_policy: "去极值",
    normalization_policy: "标准化",
    primary_factors: "主判断因子",
    auxiliary_factors: "辅助确认因子",
    train_split_ratio: "训练比例",
    validation_split_ratio: "验证比例",
    test_split_ratio: "测试比例",
    signal_confidence_floor: "最低置信度",
    strict_penalty_weight: "严格模板惩罚权重",
    trend_weight: "趋势权重",
    volume_weight: "量能权重",
    oscillator_weight: "震荡权重",
    volatility_weight: "波动权重",
    backtest_fee_bps: "回测手续费",
    backtest_slippage_bps: "回测滑点",
    backtest_cost_model: "成本模型",
    rule_min_ema20_gap_pct: "EMA20 最低偏离",
    rule_min_ema55_gap_pct: "EMA55 最低偏离",
    rule_max_atr_pct: "ATR 最高波动",
    rule_min_volume_ratio: "最低量能比",
    enable_rule_gate: "规则门开关",
    enable_validation_gate: "验证门开关",
    enable_backtest_gate: "回测门开关",
    enable_consistency_gate: "一致性门开关",
    enable_live_gate: "live 门开关",
    dry_run_min_score: "dry-run 最低分数",
    dry_run_min_positive_rate: "dry-run 最低验证正收益比例",
    dry_run_min_net_return_pct: "dry-run 最低净收益",
    dry_run_min_sharpe: "dry-run 最低 Sharpe",
    dry_run_max_drawdown_pct: "dry-run 最大回撤",
    dry_run_max_loss_streak: "dry-run 最大连续亏损段",
    dry_run_min_win_rate: "dry-run 最低胜率",
    dry_run_max_turnover: "dry-run 最高换手",
    dry_run_min_sample_count: "dry-run 最低样本数",
    validation_min_sample_count: "验证最少样本数",
    validation_min_avg_future_return_pct: "验证最低未来收益",
    consistency_max_validation_backtest_return_gap_pct: "验证/回测最大收益差",
    consistency_max_training_validation_positive_rate_gap: "训练/验证最大正收益比例差",
    consistency_max_training_validation_return_gap_pct: "训练/验证最大收益差",
    live_min_score: "live 最低分数",
    live_min_positive_rate: "live 最低正收益比例",
    live_min_net_return_pct: "live 最低净收益",
    live_min_win_rate: "live 最低胜率",
    live_max_turnover: "live 最高换手",
    live_min_sample_count: "live 最低样本数",
  };
  const changedFields = Array.isArray(row.changed_fields) ? row.changed_fields.map((item) => String(item)).filter(Boolean) : [];
  const labels: string[] = [];
  changedFields.forEach((field) => {
    const label = labelMap[field] ?? field;
    if (!labels.includes(label)) {
      labels.push(label);
    }
  });
  return labels;
}
