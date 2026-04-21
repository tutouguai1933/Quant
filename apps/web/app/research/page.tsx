/* 这个文件负责渲染策略研究工作台，把默认首屏收成当前状态、当前配置摘要和当前产物三张摘要卡。 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "../../components/app-shell";
import { LoadingBanner } from "../../components/loading-banner";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { PageHero } from "../../components/page-hero";
import { type ResearchFocusCard, ResearchFocusGrid } from "../../components/research-focus-grid";
import { ResearchPrimaryActionSection } from "../../components/research-primary-action-section";
import { ResearchRuntimePanel } from "../../components/research-runtime-panel";
import { ConfigField, ConfigInput, ConfigSelect, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { getResearchRuntimeStatus, getResearchRuntimeStatusFallback, getResearchWorkspace, getResearchWorkspaceFallback } from "../../lib/api";
import { readFeedback } from "../../lib/feedback";

const MODEL_LABELS: Record<string, string> = {
  heuristic_v1: "heuristic_v1 / 基础启发式",
  trend_bias_v2: "trend_bias_v2 / 趋势偏置",
  balanced_v3: "balanced_v3 / 平衡评分",
  momentum_drive_v4: "momentum_drive_v4 / 动量推进",
  stability_guard_v5: "stability_guard_v5 / 稳定守门",
};

const LABEL_MODE_LABELS: Record<string, string> = {
  earliest_hit: "earliest_hit / 最早命中",
  close_only: "close_only / 只看窗口结束",
  window_majority: "window_majority / 多数窗口表决",
};

const LABEL_TRIGGER_BASIS_LABELS: Record<string, string> = {
  close: "close / 按收盘价判断",
  high_low: "high_low / 按高低点命中",
};

const DEFAULT_RESEARCH_PRESETS = ["baseline_balanced", "trend_following", "conservative_validation", "momentum_breakout", "stability_first"];

export default function ResearchPage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [workspace, setWorkspace] = useState(getResearchWorkspaceFallback());
  const [runtimeStatus, setRuntimeStatus] = useState(getResearchRuntimeStatusFallback());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {
        // Keep default session state
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    Promise.allSettled([
      getResearchWorkspace(controller.signal),
      getResearchRuntimeStatus(controller.signal),
    ])
      .then(([workspaceResponse, runtimeResponse]) => {
        clearTimeout(timeoutId);

        if (workspaceResponse.status === "fulfilled" && !workspaceResponse.value.error) {
          setWorkspace(workspaceResponse.value.data.item);
        }
        if (runtimeResponse.status === "fulfilled" && !runtimeResponse.value.error) {
          setRuntimeStatus(runtimeResponse.value.data.item);
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
  }, []);
  const configAlignment = asRecord(workspace.config_alignment);
  const controls = asRecord(workspace.controls);
  const selectionStory = asRecord(workspace.selection_story);
  const selectedResearchPreset = asRecord(selectionStory.research_preset);
  const selectedResearchTemplate = asRecord(selectionStory.research_template);
  const selectedModelStory = asRecord(selectionStory.model);
  const selectedLabelPreset = asRecord(selectionStory.label_preset);
  const selectedLabelMode = asRecord(selectionStory.label_mode);
  const selectedLabelTrigger = asRecord(selectionStory.label_trigger_basis);
  const selectedHoldingWindow = asRecord(selectionStory.holding_window);

  const configEditable = session.isAuthenticated && workspace.status !== "unavailable";
  const unavailableConfigReason = !session.isAuthenticated ? "请先登录后再保存配置。" : "工作台暂时不可用，先恢复研究接口再保存配置。";
  const disabledSaveLabel = !session.isAuthenticated ? "登录后可保存配置" : "当前不可保存";
  const hasResearchResults = workspace.status !== "unavailable";

  const researchPresetKey = readPlainText(controls.research_preset_key, "baseline_balanced");
  const researchTemplateKey = readPlainText(controls.research_template, "single_asset_timing");
  const selectedModelKey = readPlainText(controls.model_key, workspace.model.model_version || "heuristic_v1");
  const selectedLabelPresetKey = readPlainText(controls.label_preset_key, "balanced_window");
  const labelModeKey = readPlainText(controls.label_mode, workspace.labeling.label_mode || "earliest_hit");
  const labelTriggerBasisKey = readPlainText(controls.label_trigger_basis, "close");
  const holdingWindowLabel = readPlainText(controls.holding_window_label, workspace.overview.holding_window || "1-3d");
  const trainSplitRatio = readPlainText(controls.train_split_ratio, "0.6");
  const validationSplitRatio = readPlainText(controls.validation_split_ratio, "0.2");
  const testSplitRatio = readPlainText(controls.test_split_ratio, "0.2");
  const signalConfidenceFloor = readPlainText(controls.signal_confidence_floor, "0.55");
  const strictPenaltyWeight = readPlainText(controls.strict_penalty_weight, "1");
  const trendWeight = readPlainText(controls.trend_weight, "1.3");
  const momentumWeight = readPlainText(controls.momentum_weight, "1");
  const volumeWeight = readPlainText(controls.volume_weight, "1.1");
  const oscillatorWeight = readPlainText(controls.oscillator_weight, "0.7");
  const volatilityWeight = readPlainText(controls.volatility_weight, "0.9");
  const labelTargetPctValue = readPlainText(controls.label_target_pct, "未设置");
  const labelStopPctValue = readPlainText(controls.label_stop_pct, "未设置");
  const forceValidationTopCandidate = controls.force_validation_top_candidate === true || String(controls.force_validation_top_candidate ?? "") === "true";
  const minHoldingDaysValue = String(Number(controls.min_holding_days ?? workspace.controls.min_holding_days ?? 1) || 1);
  const maxHoldingDaysValue = String(Number(controls.max_holding_days ?? workspace.controls.max_holding_days ?? 3) || 3);

  const blockingReasons = toStringArray(workspace.readiness.blocking_reasons);
  const readinessTrainLabel = hasResearchResults
    ? (workspace.readiness.train_ready ? "可以" : "还不行")
    : (workspace.readiness.train_ready ? "可以启动首轮训练" : "还不行");
  const readinessInferLabel = hasResearchResults
    ? (workspace.readiness.infer_ready ? "可以" : "还不行")
    : "还不行";
  const readinessBlockers = blockingReasons.length
    ? blockingReasons.join(" / ")
    : hasResearchResults
      ? "当前没有研究配置阻塞"
      : "当前没有配置阻塞，但研究结果还没生成。";
  const readinessInferReason = hasResearchResults
    ? (readPlainText(workspace.readiness.infer_reason, "当前没有推理说明"))
    : "当前还没有训练和推理结果，先启动首轮研究训练。";
  const readinessNextStep = hasResearchResults
    ? (readPlainText(workspace.readiness.next_step, "继续观察当前研究状态"))
    : "先保存配置，再运行研究训练，首轮结果会自动进入评估中心。";

  const researchStatus = readPlainText(configAlignment.status, workspace.status || "unavailable");
  const researchNote = readPlainText(configAlignment.note, readinessNextStep) || readinessNextStep || "当前还没有可用对齐说明。";
  const researchStaleFields = toStringArray(configAlignment.stale_fields);
  const researchStaleFieldsSummary = researchStaleFields.length ? researchStaleFields.join(" / ") : "当前没有发现漂移字段";

  const resolvedLabelMode = LABEL_MODE_LABELS[labelModeKey] || labelModeKey || "未设置";
  const resolvedLabelTriggerBasis = LABEL_TRIGGER_BASIS_LABELS[labelTriggerBasisKey] || labelTriggerBasisKey;

  const modelCatalog = toRecordArray(controls.model_catalog);
  const researchPresetCatalog = toRecordArray(controls.research_preset_catalog);
  const researchTemplateCatalog = toRecordArray(controls.research_template_catalog);
  const labelPresetCatalog = toRecordArray(controls.label_preset_catalog);
  const labelModeCatalog = toRecordArray(controls.label_mode_catalog);
  const labelTriggerCatalog = toRecordArray(controls.label_trigger_catalog);
  const holdingWindowCatalog = toRecordArray(controls.holding_window_catalog);

  const availableResearchPresets = toStringArray(workspace.controls.available_research_presets, DEFAULT_RESEARCH_PRESETS);
  const availableResearchTemplates = toStringArray(workspace.controls.available_research_templates);
  const availableModels = toStringArray(workspace.controls.available_models);
  const availableLabelPresets = toStringArray(controls.available_label_presets, [
    "balanced_window",
    "breakout_path",
    "closing_confirmation",
    "majority_filter",
    "pullback_reclaim",
    "volatility_breakout",
  ]);
  const availableLabelModes = toStringArray(workspace.controls.available_label_modes);
  const availableLabelTriggerBases = toStringArray(workspace.controls.available_label_trigger_bases, ["close", "high_low"]);
  const availableHoldingWindows = toStringArray(workspace.controls.available_holding_windows);

  const splitPreviewRows = buildSplitPreviewRows({
    sampleWindow: workspace.sample_window,
    trainRatio: trainSplitRatio,
    validationRatio: validationSplitRatio,
    testRatio: testSplitRatio,
  });
  const weightSummaries = [
    { label: "趋势权重", value: trendWeight },
    { label: "动量权重", value: momentumWeight },
    { label: "量能权重", value: volumeWeight },
    { label: "震荡权重", value: oscillatorWeight },
    { label: "波动权重", value: volatilityWeight },
    { label: "严格惩罚权重", value: strictPenaltyWeight },
    { label: "信心阈值", value: signalConfidenceFloor },
  ];

  const candidateScope = workspace.candidate_scope;
  const candidateScopeHeadline = readPlainText(candidateScope.headline, "当前还没有候选范围说明");
  const candidateScopeDetail = readPlainText(candidateScope.detail, "当前还没有候选篮子和执行篮子的统一说明");
  const candidateScopeNextStep = readPlainText(candidateScope.next_step, "先确认候选篮子，再决定执行篮子");
  const candidateSymbols = toStringArray(candidateScope.candidate_symbols);
  const liveAllowedSymbols = toStringArray(candidateScope.live_allowed_symbols);
  const strategyTemplates = toStringArray(workspace.strategy_templates);
  const labelColumns = toStringArray(workspace.labeling.label_columns);
  const selectorSymbols = toStringArray(workspace.selectors.symbols);
  const selectorTimeframes = toStringArray(workspace.selectors.timeframes);
  const parameterRows = Object.entries(workspace.parameters ?? {}).map(([name, value]) => ({
    id: name,
    cells: [name, readPlainText(value, "n/a")],
  }));

  const artifactTemplates = workspace.artifact_templates;
  const configHeadline = [
    readPlainText(selectedResearchPreset.label, researchPresetKey),
    readPlainText(selectedResearchTemplate.label, researchTemplateKey),
    readPlainText(selectedModelStory.label, MODEL_LABELS[selectedModelKey] || selectedModelKey),
  ].join(" / ");
  const configDetail = [
    `标签：${readPlainText(selectedLabelPreset.label, selectedLabelPresetKey)}`,
    `持有窗口：${readPlainText(selectedHoldingWindow.label, holdingWindowLabel)}`,
    `切分：${trainSplitRatio} / ${validationSplitRatio} / ${testSplitRatio}`,
  ].join(" / ");
  const artifactHeadline = readPlainText(artifactTemplates.alignment_status, "missing");
  const artifactDetail = readPlainText(artifactTemplates.note, "当前还没有模板对齐说明");
  const primaryActionLabel = readPlainText(workspace.overview.recommended_action, "先运行研究训练");
  const primaryActionDetail = readinessNextStep || "先看研究运行状态，再决定是否继续训练或推理。";

  const evaluationHref = session.isAuthenticated ? "/evaluation" : "/login?next=%2Fevaluation";
  const strategiesHref = session.isAuthenticated ? "/strategies" : "/login?next=%2Fstrategies";
  const tasksHref = session.isAuthenticated ? "/tasks" : "/login?next=%2Ftasks";

  const statusDetailContent = (
    <div className="space-y-5">
      <DetailSection title="研究准备状态" description="先确认现在能不能继续训练、推理，以及下一步该做什么。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="可训练" value={readinessTrainLabel} />
          <InfoBlock label="可推理" value={readinessInferLabel} />
          <InfoBlock label="当前阻塞" value={readinessBlockers} />
          <InfoBlock label="推理说明" value={readinessInferReason} />
          <InfoBlock label="下一步" value={readinessNextStep} />
        </div>
      </DetailSection>

      <DetailSection title="当前结果与配置对齐" description="这里确认页面上的配置和当前研究结果是不是同一轮产物。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="对齐状态" value={researchStatus} />
          <InfoBlock label="当前说明" value={researchNote} />
          <InfoBlock label="变更字段" value={researchStaleFieldsSummary} />
        </div>
      </DetailSection>
    </div>
  );

  const configContent = (
    <div className="space-y-5">
      <DetailSection title="当前配置摘要" description="确认当前预设、模板、模型和切分比例。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="当前组合" value={configHeadline} />
          <InfoBlock label="组合说明" value={configDetail} />
          <InfoBlock label="当前状态" value={researchStatus} />
          <InfoBlock label="当前下一步" value={readinessNextStep} />
          <InfoBlock label="训练是否可启动" value={readinessTrainLabel} />
          <InfoBlock label="推理是否可启动" value={readinessInferLabel} />
        </div>
      </DetailSection>

      <div className="grid gap-5 xl:grid-cols-2">
        <WorkbenchConfigCard
          title="研究预设"
          description="先套用一整套研究配置，再继续微调模型、标签和权重。"
          scope="research"
          returnTo="/research"
          disabled={!configEditable}
          disabledReason={unavailableConfigReason}
          disabledLabel={disabledSaveLabel}
        >
          <ConfigField label="一键套用" hint="预设会一起改研究模板、模型、标签方式、持有窗口和主要权重。">
            <ConfigSelect
              name="research_preset_key"
              defaultValue={researchPresetKey}
              options={availableResearchPresets.map((item) => ({ value: item, label: item }))}
            />
          </ConfigField>
          <DataTable
            columns={["研究预设", "适用场景", "说明"]}
            rows={researchPresetCatalog.map((item, index) => ({
              id: `${readPlainText(item.key, String(index))}`,
              cells: [
                readPlainText(item.key, "n/a"),
                readPlainText(item.fit, "当前没有适用场景说明"),
                readPlainText(item.detail, "当前没有预设说明"),
              ],
            }))}
            emptyTitle="当前还没有研究预设"
            emptyDetail="恢复工作台后可用"
          />
        </WorkbenchConfigCard>

        <WorkbenchConfigCard
          title="研究参数配置"
          description="这里改的是训练、推理和标签定义本身，保存后下一轮研究会按这里的参数运行。"
          scope="research"
          returnTo="/research"
          disabled={!configEditable}
          disabledReason={unavailableConfigReason}
          disabledLabel={disabledSaveLabel}
        >
          <ConfigField label="研究模板" hint="先在更宽松和更严格的单币择时模板之间切换。">
            <ConfigSelect
              name="research_template"
              defaultValue={researchTemplateKey}
              options={availableResearchTemplates.map((item) => ({ value: item, label: item }))}
            />
          </ConfigField>
          <ConfigField label="模型" hint="现在支持基础启发式和更偏趋势权重的版本。">
            <ConfigSelect
              name="model_key"
              defaultValue={selectedModelKey}
              options={availableModels.map((item) => ({
                value: item,
                label: MODEL_LABELS[item] || item,
              }))}
            />
          </ConfigField>
          <ConfigField label="标签方式" hint="用未来窗口里的目标收益和止损阈值定义 buy / sell / watch。">
            <ConfigSelect
              name="label_preset_key"
              defaultValue={selectedLabelPresetKey}
              options={availableLabelPresets.map((item) => ({ value: item, label: item }))}
            />
            <div className="grid gap-3">
              <ConfigSelect
                name="label_mode"
                defaultValue={labelModeKey}
                options={availableLabelModes.map((item) => ({
                  value: item,
                  label: LABEL_MODE_LABELS[item] || item,
                }))}
              />
              <ConfigSelect
                name="label_trigger_basis"
                defaultValue={labelTriggerBasisKey}
                options={availableLabelTriggerBases.map((item) => ({
                  value: item,
                  label: LABEL_TRIGGER_BASIS_LABELS[item] || item,
                }))}
              />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <ConfigInput name="label_target_pct" defaultValue={labelTargetPctValue} placeholder="目标收益 %" />
              <ConfigInput name="label_stop_pct" defaultValue={labelStopPctValue} placeholder="止损阈值 %" />
            </div>
          </ConfigField>
          <ConfigField label="验证放行方式" hint="可以保持统一门控，也可以临时强制把当前最优候选送去验证。">
            <ConfigSelect
              name="force_validation_top_candidate"
              defaultValue={forceValidationTopCandidate ? "true" : "false"}
              options={[
                { value: "false", label: "按统一门控自然筛选" },
                { value: "true", label: "强制验证当前最优候选" },
              ]}
            />
          </ConfigField>
          <ConfigField label="持有窗口" hint="这会决定标签在未来几天里寻找最早命中结果。">
            <ConfigSelect
              name="holding_window_label"
              defaultValue={holdingWindowLabel}
              options={availableHoldingWindows.map((item) => ({ value: item, label: item }))}
            />
            <div className="grid gap-3 md:grid-cols-2">
              <ConfigInput name="min_holding_days" type="number" min={1} max={7} defaultValue={minHoldingDaysValue} />
              <ConfigInput name="max_holding_days" type="number" min={1} max={7} defaultValue={maxHoldingDaysValue} />
            </div>
          </ConfigField>
          <ConfigField label="训练/验证/测试切分比例" hint="保存后下一轮研究会按这个比例切训练集、验证集和测试集。">
            <div className="grid gap-3 md:grid-cols-3">
              <ConfigInput name="train_split_ratio" defaultValue={trainSplitRatio} placeholder="训练比例" />
              <ConfigInput name="validation_split_ratio" defaultValue={validationSplitRatio} placeholder="验证比例" />
              <ConfigInput name="test_split_ratio" defaultValue={testSplitRatio} placeholder="测试比例" />
            </div>
          </ConfigField>
          <ConfigField label="研究分数与因子权重" hint="这里决定分数门槛和各类因子的权重分配，下一轮研究会按这里重新打分。">
            <div className="grid gap-3 md:grid-cols-2">
              <ConfigInput name="signal_confidence_floor" defaultValue={signalConfidenceFloor} placeholder="最低置信度" />
              <ConfigInput name="strict_penalty_weight" defaultValue={strictPenaltyWeight} placeholder="严格模板惩罚权重" />
              <ConfigInput name="trend_weight" defaultValue={trendWeight} placeholder="趋势权重" />
              <ConfigInput name="momentum_weight" defaultValue={momentumWeight} placeholder="动量权重" />
              <ConfigInput name="volume_weight" defaultValue={volumeWeight} placeholder="量能权重" />
              <ConfigInput name="oscillator_weight" defaultValue={oscillatorWeight} placeholder="震荡权重" />
              <ConfigInput name="volatility_weight" defaultValue={volatilityWeight} placeholder="波动权重" />
            </div>
          </ConfigField>
        </WorkbenchConfigCard>
      </div>
    </div>
  );

  const configGuideContent = (
    <div className="space-y-5">
      <DetailSection title="当前研究选择" description="说明实际采用的预设、模板、模型和标签组合。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="当前组合" value={readPlainText(selectionStory.headline, "当前还没有研究组合摘要")} />
          <InfoBlock label="当前组合说明" value={readPlainText(selectionStory.detail, "当前还没有组合说明")} />
          <InfoBlock
            label="研究预设"
            value={`${readPlainText(selectedResearchPreset.label, researchPresetKey)} / ${readPlainText(selectedResearchPreset.fit, "当前没有适用场景说明")}`}
          />
          <InfoBlock
            label="研究模板"
            value={`${readPlainText(selectedResearchTemplate.label, researchTemplateKey)} / ${readPlainText(selectedResearchTemplate.fit, "当前没有适用场景说明")}`}
          />
          <InfoBlock
            label="模型选择"
            value={`${readPlainText(selectedModelStory.label, MODEL_LABELS[selectedModelKey] || selectedModelKey)} / ${readPlainText(selectedModelStory.fit, "当前没有适用场景说明")}`}
          />
          <InfoBlock
            label="标签预设"
            value={`${readPlainText(selectedLabelPreset.label, selectedLabelPresetKey)} / ${readPlainText(selectedLabelPreset.fit, "当前没有适用场景说明")}`}
          />
          <InfoBlock
            label="标签方式"
            value={`${readPlainText(selectedLabelMode.label, resolvedLabelMode)} / ${readPlainText(selectedLabelMode.fit, "当前没有适用场景说明")}`}
          />
          <InfoBlock
            label="触发基础"
            value={`${readPlainText(selectedLabelTrigger.label, resolvedLabelTriggerBasis)} / ${readPlainText(selectedLabelTrigger.fit, "当前没有适用场景说明")}`}
          />
          <InfoBlock
            label="持有窗口"
            value={`${readPlainText(selectedHoldingWindow.label, holdingWindowLabel)} / ${readPlainText(selectedHoldingWindow.fit, "当前没有适用场景说明")}`}
          />
          <InfoBlock label="目标 / 止损" value={`${labelTargetPctValue} / ${labelStopPctValue}`} />
        </div>
      </DetailSection>

      <DetailSection title="候选范围契约" description="各模块共用同一份候选篮子与执行篮子说明。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="统一说明" value={candidateScopeHeadline} />
          <InfoBlock label="为什么这样分层" value={candidateScopeDetail} />
          <InfoBlock label="研究 / dry-run 候选篮子" value={candidateSymbols.length ? candidateSymbols.join(" / ") : "当前未配置"} />
          <InfoBlock label="候选篮子预设" value={readPlainText(candidateScope.candidate_pool_preset_detail, "当前没有候选篮子预设说明")} />
          <InfoBlock label="执行篮子" value={liveAllowedSymbols.length ? liveAllowedSymbols.join(" / ") : "当前未配置"} />
          <InfoBlock label="下一步" value={candidateScopeNextStep} />
        </div>
      </DetailSection>

      <DetailSection title="标签与模型说明" description="解释模型、标签方式、触发基础和持有窗口的影响。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="当前模型" value={MODEL_LABELS[selectedModelKey] || selectedModelKey} />
          <InfoBlock label="当前标签预设" value={selectedLabelPresetKey} />
          <InfoBlock label="标签方式说明" value={describeLabelMode(labelModeKey)} />
          <InfoBlock label="触发基础说明" value={describeLabelTriggerBasis(labelTriggerBasisKey)} />
          <InfoBlock label="持有窗口说明" value={describeHoldingWindow(holdingWindowLabel)} />
          <InfoBlock label="模型说明" value={describeModel(selectedModelKey)} />
          <InfoBlock label="数据范围" value={readPlainText(workspace.execution_preview.data_scope, "当前没有数据范围摘要")} />
          <InfoBlock label="因子组合" value={readPlainText(workspace.execution_preview.factor_mix, "当前没有因子组合摘要")} />
          <InfoBlock label="标签定义" value={readPlainText(workspace.execution_preview.label_scope, "当前没有标签定义摘要")} />
          <InfoBlock label="dry-run 门槛" value={readPlainText(workspace.execution_preview.dry_run_gate, "当前没有 dry-run 门槛摘要")} />
          <InfoBlock label="live 门槛" value={readPlainText(workspace.execution_preview.live_gate, "当前没有 live 门槛摘要")} />
          <InfoBlock label="验证放行方式" value={readPlainText(workspace.execution_preview.validation_policy, "当前没有验证放行说明")} />
        </div>
      </DetailSection>

      <DataTable
        columns={["研究模板说明", "更适合什么", "当前是否选中", "说明"]}
        rows={buildCatalogRows(researchTemplateCatalog, researchTemplateKey, "当前模板", "当前没有适用场景说明", "当前没有模板说明")}
        emptyTitle="当前还没有研究模板目录"
        emptyDetail="恢复工作台后可用"
      />

      <DataTable
        columns={["模型目录", "更适合什么", "当前是否选中", "说明"]}
        rows={buildCatalogRows(modelCatalog, selectedModelKey, "当前模型", "当前没有适用场景说明", "当前没有模型说明")}
        emptyTitle="当前还没有模型目录"
        emptyDetail="恢复工作台后可用"
      />

      <DataTable
        columns={["标签预设", "更适合什么", "当前是否选中", "说明"]}
        rows={buildCatalogRows(labelPresetCatalog, selectedLabelPresetKey, "当前标签预设", "当前没有适用场景说明", "当前没有标签预设说明")}
        emptyTitle="当前还没有标签预设目录"
        emptyDetail="恢复工作台后可用"
      />

      <DataTable
        columns={["标签方式说明", "更适合什么", "当前是否选中", "说明"]}
        rows={buildCatalogRows(labelModeCatalog, labelModeKey, "当前标签方式", "当前没有适用场景说明", "当前没有标签说明")}
        emptyTitle="当前还没有标签方式目录"
        emptyDetail="恢复工作台后可用"
      />

      <DataTable
        columns={["触发基础说明", "更适合什么", "当前是否选中", "说明"]}
        rows={buildCatalogRows(labelTriggerCatalog, labelTriggerBasisKey, "当前触发基础", "当前没有适用场景说明", "当前没有触发说明")}
        emptyTitle="当前还没有触发基础目录"
        emptyDetail="恢复工作台后可用"
      />

      <DataTable
        columns={["持有窗口说明", "更适合什么", "当前是否选中", "说明"]}
        rows={buildCatalogRows(holdingWindowCatalog, holdingWindowLabel, "当前持有窗口", "当前没有适用场景说明", "当前没有持有窗口说明")}
        emptyTitle="当前还没有持有窗口目录"
        emptyDetail="恢复工作台后可用"
      />
    </div>
  );

  const artifactDetailContent = (
    <div className="space-y-5">
      <DetailSection title="模板产物对齐" description="确认配置、训练、推理模板是否同一条主线。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="当前配置模板" value={`${readPlainText(artifactTemplates.current.label, "未选择")} / ${readPlainText(artifactTemplates.current.fit, "当前没有模板说明")}`} />
          <InfoBlock label="最近训练模板" value={`${readPlainText(artifactTemplates.training.label, "未生成")} / ${readPlainText(artifactTemplates.training.fit, "当前还没有训练产物")}`} />
          <InfoBlock label="最近推理模板" value={`${readPlainText(artifactTemplates.inference.label, "未生成")} / ${readPlainText(artifactTemplates.inference.fit, "当前还没有推理产物")}`} />
          <InfoBlock label="模板对齐状态" value={artifactHeadline} />
          <InfoBlock label="模板对齐说明" value={artifactDetail} />
        </div>
      </DetailSection>

      <DetailSection title="当前研究模板与标签定义" description="这里保留当前产物实际使用的模板清单和标签口径。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="研究模板" value={strategyTemplates.length ? strategyTemplates.join(" / ") : "当前还没有研究模板，请先运行研究训练和推理。"} />
          <InfoBlock label="标签列" value={labelColumns.length ? labelColumns.join(" / ") : "未生成"} />
          <InfoBlock label="标签模式" value={resolvedLabelMode} />
          <InfoBlock label="标签触发基础" value={resolvedLabelTriggerBasis} />
          <InfoBlock label="目标 / 止损" value={`${labelTargetPctValue} / ${labelStopPctValue}`} />
          <InfoBlock label="定义" value={readPlainText(workspace.labeling.definition, "当前没有标签定义")} />
        </div>
      </DetailSection>

      <DetailSection title="研究后端与标的" description="这里说明当前产物依赖的模型版本、研究后端和研究标的。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="模型版本" value={readPlainText(workspace.model.model_version, "未生成")} />
          <InfoBlock label="研究后端" value={readPlainText(workspace.model.backend, "qlib-fallback")} />
          <InfoBlock label="研究标的" value={selectorSymbols.length ? selectorSymbols.join(" / ") : "未写入"} />
          <InfoBlock label="训练周期" value={selectorTimeframes.length ? selectorTimeframes.join(" / ") : "未写入"} />
        </div>
      </DetailSection>
    </div>
  );

  const experimentContent = (
    <div className="space-y-5">
      <DetailSection title="训练切分说明" description="实验窗口和切分摘要；完整实验中心在评估页。">
        <div className="space-y-4">
          <DataTable
            columns={["窗口", "样本摘要"]}
            rows={Object.entries(workspace.sample_window).map(([name, payload]) => ({
              id: name,
              cells: [name, formatWindow(payloadRecord(payload))],
            }))}
            emptyTitle="还没有训练窗口"
            emptyDetail="运行后产生"
          />
          <DataTable
            columns={["训练切分说明", "当前配置", "按当前样本大致会怎样切"]}
            rows={splitPreviewRows}
            emptyTitle="当前还没有切分预览"
            emptyDetail="运行后产生"
          />
        </div>
      </DetailSection>

      <DetailSection title="研究分数与权重" description="这里集中看本轮研究当前偏向哪类因子和分数门槛。">
        <div className="grid gap-3 md:grid-cols-2">
          {weightSummaries.map((row) => (
            <InfoBlock key={row.label} label={row.label} value={row.value} />
          ))}
        </div>
      </DetailSection>

      <DetailSection title="标签目标与止损说明" description="这里集中说明未来命中规则、目标收益和止损口径。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="未来命中规则" value={readPlainText(workspace.label_rule_summary?.headline, "当前还没有标签规则摘要")} />
          <InfoBlock label="标签解释" value={readPlainText(workspace.label_rule_summary?.detail, "当前还没有标签解释")} />
          <InfoBlock label="下一步怎么调" value={readPlainText(workspace.label_rule_summary?.next_step, "先确认这一轮标签口径是否和你的目标一致。")} />
        </div>
      </DetailSection>

      <DetailSection title="实验参数" description="实验参数快照；完整对比在评估页。">
        <DataTable
          columns={["参数名", "参数值"]}
          rows={parameterRows}
          emptyTitle="还没有实验参数"
          emptyDetail="运行后产生"
        />
      </DetailSection>
    </div>
  );

  const focusCards: ResearchFocusCard[] = [
    {
      id: "status",
      eyebrow: "当前状态",
      title: "当前状态",
      summary: "先回答现在能不能继续训练或推理，避免还没准备好就继续往下推。",
      detail: researchNote,
      digests: [
        { label: "当前状态", value: researchStatus, detail: researchNote },
        { label: "训练 / 推理", value: `${readinessTrainLabel} / ${readinessInferLabel}`, detail: readinessInferReason },
        { label: "当前阻塞", value: readinessBlockers, detail: readinessNextStep },
      ],
      actions: [
        {
          key: "status-detail",
          label: "查看状态详情",
          title: "研究状态详情",
          description: "把训练准备度、推理准备度和配置对齐情况收进这里，默认不再单独铺满一页。",
          content: statusDetailContent,
          footer: "触发训练或推理后，研究运行状态会立刻在页面核心区刷新。",
          mode: "drawer",
        },
      ],
    },
    {
      id: "config",
      eyebrow: "当前配置",
      title: "当前配置摘要",
      summary: "先确认这轮研究真正采用的配置，再决定是否需要改预设、模型、标签或切分。",
      detail: configDetail,
      digests: [
        { label: "当前组合", value: configHeadline, detail: configDetail },
        { label: "标签 / 持有", value: `${readPlainText(selectedLabelPreset.label, selectedLabelPresetKey)} / ${readPlainText(selectedHoldingWindow.label, holdingWindowLabel)}`, detail: `${resolvedLabelMode} / ${resolvedLabelTriggerBasis}` },
        { label: "训练切分", value: `${trainSplitRatio} / ${validationSplitRatio} / ${testSplitRatio}`, detail: readPlainText(workspace.execution_preview.validation_policy, "当前没有验证放行说明") },
      ],
      actions: [
        {
          key: "config-panel",
          label: "查看完整配置",
          title: "研究配置详情",
          description: "完整配置表单统一收进这里，默认页不再被大块表单占满。",
          content: configContent,
          footer: "保存配置后，当前研究页和后续评估、执行承接都会按新口径刷新。",
          mode: "drawer",
        },
        {
          key: "config-guide",
          label: "查看配置说明",
          title: "研究配置说明",
          description: "模板、模型、标签和候选范围说明统一下沉到这里，需要时再展开。",
          content: configGuideContent,
          footer: "研究页只保留当前组合和摘要；更完整的说明目录都从这里进入。",
          mode: "drawer",
        },
      ],
    },
    {
      id: "artifact",
      eyebrow: "当前产物",
      title: "当前产物",
      summary: "先确认当前模板对齐和产物承接，再决定是否进入评估、执行或继续研究。",
      detail: artifactDetail,
      digests: [
        { label: "模板对齐", value: artifactHeadline, detail: artifactDetail },
        {
          label: "研究模板",
          value: strategyTemplates.length ? strategyTemplates.join(" / ") : "当前还没有研究模板",
          detail: candidateScopeHeadline,
        },
        {
          label: "研究后端",
          value: readPlainText(workspace.model.backend, "qlib-fallback"),
          detail: readPlainText(workspace.model.model_version, "当前还没有模型版本"),
        },
      ],
      actions: [
        {
          key: "artifact-detail",
          label: "查看产物详情",
          title: "研究产物详情",
          description: "把模板对齐、标签定义和研究后端说明收进这里，默认页只保留摘要。",
          content: artifactDetailContent,
          footer: "如果要继续看完整研究报告和候选排序，优先回信号页和评估页。",
          mode: "drawer",
        },
        {
          key: "experiments",
          label: "打开实验弹窗",
          title: "研究实验详情",
          description: "训练窗口、切分预览、权重和实验参数都集中放进这一层，研究页不再承担完整实验中心职责。",
          content: experimentContent,
          footer: "需要更完整的实验对比和推进判断时，继续去评估与实验中心。",
          mode: "dialog",
        },
      ],
    },
  ];

  return (
    <AppShell
      title="策略研究工作台"
      subtitle="先看状态、配置和产物，细节按需展开。"
      currentPath="/research"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      {isLoading && <LoadingBanner />}

      <PageHero
        badge="策略研究工作台"
        title="先看这轮研究现在在做什么，再决定是否继续训练、推理或改配置。"
        description="研究页默认只回答三件事：现在状态如何、当前配置是什么、当前产物承接到哪里。其余说明和实验细节都按需展开。"
      />

      <ResearchPrimaryActionSection
        primaryActionLabel={primaryActionLabel}
        primaryActionDetail={primaryActionDetail}
        researchStatus={researchStatus}
        researchStatusDetail={researchNote}
        trainReadinessLabel={readinessTrainLabel}
        inferReadinessLabel={readinessInferLabel}
        configHeadline={configHeadline}
        configDetail={configDetail}
        artifactHeadline={artifactHeadline}
        artifactDetail={artifactDetail}
        modelExplanation={describeModel(selectedModelKey)}
        labelModeExplanation={describeLabelMode(labelModeKey)}
        triggerBasisExplanation={describeLabelTriggerBasis(labelTriggerBasisKey)}
        holdingWindowExplanation={describeHoldingWindow(holdingWindowLabel)}
        signalsHref="/signals"
        evaluationHref={evaluationHref}
        backtestHref="/backtest"
        strategiesHref={strategiesHref}
        tasksHref={tasksHref}
      />

      <ResearchRuntimePanel initialStatus={runtimeStatus} />

      <ResearchFocusGrid cards={focusCards} />
    </AppShell>
  );
}

/* 渲染统一的信息块。 */
function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-foreground break-all">{value}</p>
    </div>
  );
}

/* 渲染抽屉和弹窗里的细节分组。 */
function DetailSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-border/60 bg-muted/10 p-4">
      <div className="space-y-2">
        <p className="eyebrow">{title}</p>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

/* 读取可直接展示的文本，避免把对象直接渲染成 [object Object]。 */
function readPlainText(value: unknown, fallback = "n/a"): string {
  if (value === null || value === undefined) {
    return fallback;
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return displayValue(String(value), fallback);
  }
  if (Array.isArray(value)) {
    const items: string[] = value.map((item) => readPlainText(item, "")).filter(Boolean);
    return items.length ? items.join(" / ") : fallback;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    return (
      readPlainText(record.label, "") ||
      readPlainText(record.headline, "") ||
      readPlainText(record.title, "") ||
      readPlainText(record.detail, "") ||
      readPlainText(record.note, "") ||
      fallback
    );
  }
  return fallback;
}

/* 格式化普通文本值。 */
function displayValue(value: unknown, fallback = "n/a") {
  if (value === null || value === undefined) {
    return fallback;
  }
  const normalized = String(value).trim();
  return normalized.length ? normalizeBasketTerms(normalized) : fallback;
}

/* 统一前端候选范围术语，不改后端字段名。 */
function normalizeBasketTerms(value: string): string {
  return value.replaceAll("候选池", "候选篮子").replaceAll("live 子集", "执行篮子");
}

/* 读取统一字符串数组。 */
function toStringArray(value: unknown, fallback: string[] = []) {
  if (!Array.isArray(value)) {
    return fallback;
  }
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

/* 读取统一目录数组。 */
function toRecordArray(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && !Array.isArray(item)));
}

/* 把目录数据转成表格行。 */
function buildCatalogRows(
  items: Record<string, unknown>[],
  currentKey: string,
  currentLabel: string,
  fitFallback: string,
  detailFallback: string,
) {
  return items.map((item, index) => ({
    id: `${readPlainText(item.key, String(index))}`,
    cells: [
      readPlainText(item.label ?? item.key, "n/a"),
      readPlainText(item.fit, fitFallback),
      readPlainText(item.key, "") === currentKey ? currentLabel : "可切换",
      readPlainText(item.detail, detailFallback),
    ],
  }));
}

/* 格式化样本窗口摘要。 */
function formatWindow(payload: Record<string, unknown>) {
  const parts: string[] = [];
  if (payload.start !== undefined) {
    parts.push(`start=${String(payload.start)}`);
  }
  if (payload.end !== undefined) {
    parts.push(`end=${String(payload.end)}`);
  }
  if (payload.count !== undefined) {
    parts.push(`count=${String(payload.count)}`);
  }
  return parts.join(" / ") || "当前没有窗口信息";
}

/* 生成训练/验证/测试切分预览。 */
function buildSplitPreviewRows({
  sampleWindow,
  trainRatio,
  validationRatio,
  testRatio,
}: {
  sampleWindow: Record<string, unknown>;
  trainRatio: string;
  validationRatio: string;
  testRatio: string;
}) {
  return ["training", "validation", "test"].map((name) => {
    const window = payloadRecord(sampleWindow[name]);
    const count = Number(window.count ?? 0);
    const ratio =
      name === "training"
        ? trainRatio
        : name === "validation"
          ? validationRatio
          : testRatio;
    const label = name === "training" ? "训练窗口" : name === "validation" ? "验证窗口" : "测试窗口";
    return {
      id: name,
      cells: [
        label,
        `${ratio} / ${formatWindow(window)}`,
        count > 0 ? `当前大约 ${count} 条样本` : "当前还没有样本数",
      ],
    };
  });
}

/* 把未知值安全转成对象。 */
function payloadRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

/* 把未知值安全转成对象。 */
function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

/* 解释当前模型。 */
function describeModel(modelKey: string) {
  switch (modelKey) {
    case "momentum_drive_v4":
      return "更偏短节奏突破和动量延续，适合先找最近放量、加速、最可能快速走一段的候选。";
    case "stability_guard_v5":
      return "更偏稳定收益和波动控制，适合进 live 前先筛掉回撤大、稳定性差的候选。";
    case "trend_bias_v2":
      return "更偏顺趋势确认，适合把趋势、量能和突破一致的标的优先排前。";
    case "balanced_v3":
      return "会同时看趋势、动量、波动和震荡，适合拿来比较多种市场状态下的均衡表现。";
    case "heuristic_v1":
    default:
      return "最基础的启发式模型，适合先跑通一轮研究，再观察配置变化会怎么影响推荐。";
  }
}

/* 解释标签方式。 */
function describeLabelMode(labelMode: string) {
  switch (labelMode) {
    case "close_only":
      return "只看窗口结束时的最终结果，更适合验证持有到期的稳定性，但对中间命中的走势不敏感。";
    case "window_majority":
      return "按整个窗口里的多数结果表决，更适合过滤单根极端波动，但信号会更保守。";
    case "earliest_hit":
    default:
      return "谁先命中目标或止损就优先按谁记账，更接近当前 1 到 3 天择时的真实退出逻辑。";
  }
}

/* 解释标签触发基础。 */
function describeLabelTriggerBasis(triggerBasis: string) {
  switch (triggerBasis) {
    case "high_low":
      return "按窗口内的高低点命中来判断，更接近盘中先碰目标或止损就退出。";
    case "close":
    default:
      return "按收盘价判断，口径更稳，但会弱化盘中先冲高或先下探的路径差异。";
  }
}

/* 解释持有窗口。 */
function describeHoldingWindow(holdingWindow: string) {
  switch (holdingWindow) {
    case "1-2d":
      return "更短，更偏快节奏择时，推荐会更敏感，但也更容易被短期波动影响。";
    case "2-5d":
      return "会给走势修复和收盘确认更多时间，更适合进 live 前先看稳定性是不是站住。";
    case "3-5d":
      return "更偏中短波段，会优先观察更完整的一段走势，推荐更稳，但短线信号会更慢一些。";
    case "2-4d":
      return "更长，更偏耐心持有，推荐会更稳，但对短期强信号的反应会慢一点。";
    case "1-3d":
    default:
      return "当前默认窗口，兼顾快速命中和持有稳定性，也是这套单币择时研究的主目标。";
  }
}
