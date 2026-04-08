/* 这个文件负责渲染策略研究工作台，让研究模板、标签和实验参数直接可见。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ResearchRuntimePanel } from "../../components/research-runtime-panel";
import { ConfigField, ConfigInput, ConfigSelect, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { FormSubmitButton } from "../../components/form-submit-button";
import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { getResearchRuntimeStatus, getResearchRuntimeStatusFallback, getResearchWorkspace, getResearchWorkspaceFallback } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";
import { WorkbenchConfigStatusCard } from "../../components/workbench-config-status-card";

const MODEL_LABELS: Record<string, string> = {
  heuristic_v1: "heuristic_v1 / 基础启发式",
  trend_bias_v2: "trend_bias_v2 / 趋势偏置",
  balanced_v3: "balanced_v3 / 平衡评分",
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

const DEFAULT_RESEARCH_PRESETS = ["baseline_balanced", "trend_following", "conservative_validation"];

export default async function ResearchPage() {
  const session = await getControlSessionState();
  const [workspaceResponse, runtimeResponse] = await Promise.allSettled([getResearchWorkspace(), getResearchRuntimeStatus()]);
  const workspace =
    workspaceResponse.status === "fulfilled" && !workspaceResponse.value.error
      ? workspaceResponse.value.data.item
      : getResearchWorkspaceFallback();
  const runtimeStatus =
    runtimeResponse.status === "fulfilled" && !runtimeResponse.value.error
      ? runtimeResponse.value.data.item
      : getResearchRuntimeStatusFallback();
  const configAlignment = asRecord(workspace.config_alignment);
  const controls = asRecord(workspace.controls);
  const configEditable = true;
  const unavailableConfigReason = "工作台暂时不可用，先恢复研究接口再保存配置。";
  const hasResearchResults = workspace.status !== "unavailable";
  const readinessTrainLabel = hasResearchResults
    ? (workspace.readiness.train_ready ? "可以" : "还不行")
    : (workspace.readiness.train_ready ? "可以启动首轮训练" : "还不行");
  const readinessInferLabel = hasResearchResults
    ? (workspace.readiness.infer_ready ? "可以" : "还不行")
    : "还不行";
  const readinessBlockers = workspace.readiness.blocking_reasons.length
    ? workspace.readiness.blocking_reasons.join(" / ")
    : hasResearchResults
      ? "当前没有研究配置阻塞"
      : "当前没有配置阻塞，但研究结果还没生成。";
  const readinessInferReason = hasResearchResults
    ? (workspace.readiness.infer_reason || "当前没有推理说明")
    : "当前还没有训练和推理结果，先启动首轮研究训练。";
  const readinessNextStep = hasResearchResults
    ? (workspace.readiness.next_step || "继续观察当前研究状态")
    : "先保存右侧配置，再运行研究训练，首轮结果会自动进入评估中心。";
  const researchStatus = String(configAlignment.status ?? (workspace.status || "unavailable"));
  const researchNote =
    String(configAlignment.note ?? "") || readinessNextStep || "当前还没有可用对齐说明。";
  const researchStaleFields = Array.isArray(configAlignment.stale_fields) ? configAlignment.stale_fields.map(String) : [];
  const resolvedLabelMode = LABEL_MODE_LABELS[workspace.labeling.label_mode] || workspace.labeling.label_mode || "未设置";
  const resolvedLabelTriggerBasis =
    LABEL_TRIGGER_BASIS_LABELS[String(controls.label_trigger_basis ?? "close")] || String(controls.label_trigger_basis ?? "close");
  const selectedModelKey = String(controls.model_key ?? workspace.model.model_version ?? "heuristic_v1");
  const labelTargetPctValue = displayValue(workspace.controls.label_target_pct, "未设置");
  const labelStopPctValue = displayValue(workspace.controls.label_stop_pct, "未设置");
  const modelCatalog = Array.isArray(controls.model_catalog)
    ? controls.model_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const researchPresetCatalog = Array.isArray(controls.research_preset_catalog)
    ? controls.research_preset_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const labelPresetCatalog = Array.isArray(controls.label_preset_catalog)
    ? controls.label_preset_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const availableLabelPresets = Array.isArray(controls.available_label_presets)
    ? controls.available_label_presets.map(String)
    : ["balanced_window", "breakout_path", "closing_confirmation", "majority_filter"];
  const labelModeCatalog = Array.isArray(controls.label_mode_catalog)
    ? controls.label_mode_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const labelTriggerCatalog = Array.isArray(controls.label_trigger_catalog)
    ? controls.label_trigger_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const holdingWindowCatalog = Array.isArray(controls.holding_window_catalog)
    ? controls.holding_window_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const splitPreviewRows = buildSplitPreviewRows({
    sampleWindow: workspace.sample_window,
    trainRatio: String(controls.train_split_ratio ?? "0.6"),
    validationRatio: String(controls.validation_split_ratio ?? "0.2"),
    testRatio: String(controls.test_split_ratio ?? "0.2"),
  });
  const weightSummaries = [
    { label: "趋势权重", value: workspace.controls.trend_weight },
    { label: "动量权重", value: workspace.controls.momentum_weight },
    { label: "量能权重", value: workspace.controls.volume_weight },
    { label: "震荡权重", value: workspace.controls.oscillator_weight },
    { label: "波动权重", value: workspace.controls.volatility_weight },
    { label: "严格惩罚权重", value: workspace.controls.strict_penalty_weight },
    { label: "信心阈值", value: workspace.controls.signal_confidence_floor },
  ];
  const selectedLabelPresetKey = String(controls.label_preset_key ?? "balanced_window");

  return (
    <AppShell
      title="策略研究工作台"
      subtitle="把当前正在研究的模板、标签定义、训练窗口和实验参数直接摊开，不再只看最后结论。"
      currentPath="/research"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="策略研究工作台"
        title="先搞清楚当前研究到底在研究什么，再决定要不要继续训练、推理和进入执行。"
        description="这里直接回答三件事：当前研究模板是什么，标签定义怎么来的，训练/验证/回测窗口和模型参数又是什么。"
      />

      <MetricGrid
        items={[
          { label: "持有周期", value: workspace.overview.holding_window || "未写入", detail: "当前标签定义使用的持有窗口" },
          { label: "候选数量", value: String(workspace.overview.candidate_count), detail: workspace.overview.recommended_symbol || "当前没有推荐标的" },
          { label: "当前模型", value: workspace.model.model_version || "未生成", detail: workspace.model.backend },
          { label: "下一步", value: workspace.overview.recommended_action || "先运行研究训练", detail: "研究结果会决定接下来是继续研究还是进入验证" },
        ]}
      />

      <WorkbenchConfigStatusCard
        scope="研究"
        status={researchStatus}
        note={researchNote}
        staleFields={researchStaleFields}
        editable={configEditable}
      />

      <ResearchRuntimePanel initialStatus={runtimeStatus} />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_380px]">
        <div className="space-y-5">
          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>研究准备状态</CardTitle>
              <CardDescription>这里直接说明现在能不能继续训练、能不能继续推理，以及下一步该做什么。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="可训练" value={readinessTrainLabel} />
              <InfoBlock label="可推理" value={readinessInferLabel} />
              <InfoBlock label="当前阻塞" value={readinessBlockers} />
              <InfoBlock label="推理说明" value={readinessInferReason} />
              <InfoBlock label="下一步" value={readinessNextStep} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>研究模板</CardTitle>
              <CardDescription>这些就是当前研究链里实际会产出的策略模板。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {workspace.strategy_templates.length ? workspace.strategy_templates.map((item) => (
                <Badge key={item}>{item}</Badge>
              )) : <p className="text-sm leading-6 text-muted-foreground">当前还没有研究模板，请先运行研究训练和推理。</p>}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>标签定义</CardTitle>
              <CardDescription>先把 buy / sell / watch 是怎么来的讲清楚。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="标签列" value={workspace.labeling.label_columns.join(" / ") || "未生成"} />
              <InfoBlock label="标签模式" value={resolvedLabelMode} />
              <InfoBlock label="标签触发基础" value={resolvedLabelTriggerBasis} />
              <InfoBlock label="目标 / 止损" value={`${labelTargetPctValue} / ${labelStopPctValue}`} />
              <InfoBlock label="定义" value={workspace.labeling.definition || "当前没有标签定义"} />
            </CardContent>
          </Card>

          <DataTable
            columns={["模型目录", "更适合什么", "当前是否选中", "说明"]}
            rows={modelCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "当前没有适用场景说明"),
                String(item.key ?? "") === selectedModelKey ? "当前模型" : "可切换",
                String(item.detail ?? "当前没有模型说明"),
              ],
            }))}
            emptyTitle="当前还没有模型目录"
            emptyDetail="先恢复研究工作台，系统才会给出模型目录。"
          />

          <DataTable
            columns={["标签预设", "更适合什么", "当前是否选中", "说明"]}
            rows={labelPresetCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "当前没有适用场景说明"),
                String(item.key ?? "") === selectedLabelPresetKey ? "当前标签预设" : "可切换",
                String(item.detail ?? "当前没有标签预设说明"),
              ],
            }))}
            emptyTitle="当前还没有标签预设目录"
            emptyDetail="先恢复研究工作台，系统才会给出标签预设目录。"
          />

          <DataTable
            columns={["标签方式说明", "更适合什么", "当前是否选中", "说明"]}
            rows={labelModeCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "当前没有适用场景说明"),
                String(item.key ?? "") === String(controls.label_mode ?? "") ? "当前标签方式" : "可切换",
                String(item.detail ?? "当前没有标签说明"),
              ],
            }))}
            emptyTitle="当前还没有标签方式目录"
            emptyDetail="先恢复研究工作台，系统才会给出标签方式目录。"
          />

          <DataTable
            columns={["触发基础说明", "更适合什么", "当前是否选中", "说明"]}
            rows={labelTriggerCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "当前没有适用场景说明"),
                String(item.key ?? "") === String(controls.label_trigger_basis ?? "close") ? "当前触发基础" : "可切换",
                String(item.detail ?? "当前没有触发说明"),
              ],
            }))}
            emptyTitle="当前还没有触发基础目录"
            emptyDetail="先恢复研究工作台，系统才会给出触发基础目录。"
          />

          <DataTable
            columns={["持有窗口说明", "更适合什么", "当前是否选中", "说明"]}
            rows={holdingWindowCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "当前没有适用场景说明"),
                String(item.key ?? "") === String(controls.holding_window_label ?? "1-3d") ? "当前持有窗口" : "可切换",
                String(item.detail ?? "当前没有持有窗口说明"),
              ],
            }))}
            emptyTitle="当前还没有持有窗口目录"
            emptyDetail="先恢复研究工作台，系统才会给出持有窗口目录。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>研究分数与权重</CardTitle>
              <CardDescription>把趋势、动量、量能和严格模板的权重直接看出来，不用再猜当前研究偏向。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              {weightSummaries.map((row) => (
                <InfoBlock key={row.label} label={row.label} value={displayValue(row.value)} />
              ))}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前结果与配置对齐</CardTitle>
              <CardDescription>先确认页面上的配置和当前研究结果是不是同一轮产物。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="对齐状态" value={String(configAlignment.status ?? "unavailable")} />
              <InfoBlock label="说明" value={String(configAlignment.note ?? "当前还没有可用对齐说明")} />
              <InfoBlock label="变更字段" value={Array.isArray(configAlignment.stale_fields) && configAlignment.stale_fields.length ? configAlignment.stale_fields.map(String).join(" / ") : "当前没有发现漂移字段"} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前配置快照</CardTitle>
              <CardDescription>把数据、特征、研究、门槛和长期运行配置压成一屏，先确认这一轮到底按什么口径在跑。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="数据快照" value={workspace.execution_preview.data_scope || "当前没有数据范围摘要"} />
              <InfoBlock label="特征快照" value={workspace.execution_preview.factor_mix || "当前没有因子组合摘要"} />
              <InfoBlock label="研究快照" value={workspace.execution_preview.label_scope || "当前没有研究范围摘要"} />
              <InfoBlock
                label="门槛快照"
                value={`${workspace.execution_preview.dry_run_gate || "当前没有 dry-run 门槛摘要"} / ${workspace.execution_preview.live_gate || "当前没有 live 门槛摘要"}`}
              />
              <InfoBlock label="长期运行快照" value="研究动作会先在后台运行，再由任务页继续承接自动化、告警和人工接管状态。" />
            </CardContent>
          </Card>

          <DataTable
            columns={["窗口", "样本摘要"]}
            rows={Object.entries(workspace.sample_window).map(([name, payload]) => ({
              id: name,
              cells: [name, formatWindow(payload)],
            }))}
            emptyTitle="还没有训练窗口"
            emptyDetail="先运行研究训练，窗口摘要才会在这里出现。"
          />

          <DataTable
            columns={["训练切分说明", "当前配置", "按当前样本大致会怎样切"]}
            rows={splitPreviewRows}
            emptyTitle="当前还没有切分预览"
            emptyDetail="先生成一轮训练窗口，系统才会把训练/验证/测试切分预览出来。"
          />
        </div>

        <div className="space-y-5">
          <WorkbenchConfigCard
            title="研究预设"
            description="先套用一整套研究配置，再继续微调模型、标签和权重。"
            scope="research"
            returnTo="/research"
            disabled={!configEditable}
            disabledReason={unavailableConfigReason}
          >
            <ConfigField label="一键套用" hint="预设会一起改研究模板、模型、标签方式、持有窗口和主要权重。">
              <ConfigSelect
                name="research_preset_key"
                defaultValue={String(controls.research_preset_key ?? "baseline_balanced")}
                options={((workspace.controls.available_research_presets?.length
                  ? workspace.controls.available_research_presets
                  : DEFAULT_RESEARCH_PRESETS) || []).map((item) => ({
                  value: item,
                  label: item,
                }))}
              />
            </ConfigField>
            <DataTable
              columns={["研究预设", "适用场景", "说明"]}
              rows={researchPresetCatalog.map((item, index) => ({
                id: `${item.key ?? index}`,
                cells: [
                  String(item.key ?? "n/a"),
                  String(item.fit ?? "当前没有适用场景说明"),
                  String(item.detail ?? "当前没有预设说明"),
                ],
              }))}
              emptyTitle="当前还没有研究预设"
              emptyDetail="先恢复研究工作台，系统才会给出一键研究预设。"
            />
          </WorkbenchConfigCard>

          <WorkbenchConfigCard
            title="研究参数配置"
            description="这里改的是训练、推理和标签定义本身，保存后下一轮研究会按这里的参数运行。"
            scope="research"
            returnTo="/research"
            disabled={!configEditable}
            disabledReason={unavailableConfigReason}
          >
            <ConfigField label="研究模板" hint="先在更宽松和更严格的单币择时模板之间切换。">
              <ConfigSelect
                name="research_template"
                defaultValue={workspace.controls.research_template}
                options={workspace.controls.available_research_templates.map((item) => ({ value: item, label: item }))}
              />
            </ConfigField>
            <ConfigField label="模型" hint="现在支持基础启发式和更偏趋势权重的版本。">
              <ConfigSelect
                name="model_key"
                defaultValue={workspace.controls.model_key}
                options={workspace.controls.available_models.map((item) => ({
                  value: item,
                  label: MODEL_LABELS[item] || item,
                }))}
              />
            </ConfigField>
            <ConfigField label="标签方式" hint="用未来窗口里的目标收益和止损阈值定义 buy / sell / watch。">
              <ConfigSelect
                name="label_preset_key"
                defaultValue={selectedLabelPresetKey}
                options={availableLabelPresets.map((item) => ({
                  value: item,
                  label: item,
                }))}
              />
              <div className="grid gap-3">
                <ConfigSelect
                  name="label_mode"
                  defaultValue={workspace.controls.label_mode}
                  options={workspace.controls.available_label_modes.map((item) => ({
                    value: item,
                    label: LABEL_MODE_LABELS[item] || item,
                  }))}
                />
                <ConfigSelect
                  name="label_trigger_basis"
                  defaultValue={String(controls.label_trigger_basis ?? "close")}
                  options={(workspace.controls.available_label_trigger_bases || ["close", "high_low"]).map((item) => ({
                    value: item,
                    label: LABEL_TRIGGER_BASIS_LABELS[item] || item,
                  }))}
                />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="label_target_pct" defaultValue={workspace.controls.label_target_pct} placeholder="目标收益 %" />
                <ConfigInput name="label_stop_pct" defaultValue={workspace.controls.label_stop_pct} placeholder="止损阈值 %" />
              </div>
            </ConfigField>
            <ConfigField label="验证放行方式" hint="可以保持统一门控，也可以临时强制把当前最优候选送去验证。">
              <ConfigSelect
                name="force_validation_top_candidate"
                defaultValue={workspace.controls.force_validation_top_candidate ? "true" : "false"}
                options={[
                  { value: "false", label: "按统一门控自然筛选" },
                  { value: "true", label: "强制验证当前最优候选" },
                ]}
              />
            </ConfigField>
            <ConfigField label="持有窗口" hint="这会决定标签在未来几天里寻找最早命中结果。">
              <ConfigSelect
                name="holding_window_label"
                defaultValue={String(controls.holding_window_label ?? "1-3d")}
                options={workspace.controls.available_holding_windows.map((item) => ({ value: item, label: item }))}
              />
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="min_holding_days" type="number" min={1} max={7} defaultValue={String(workspace.controls.min_holding_days)} />
                <ConfigInput name="max_holding_days" type="number" min={1} max={7} defaultValue={String(workspace.controls.max_holding_days)} />
              </div>
            </ConfigField>
            <ConfigField label="训练/验证/测试切分比例" hint="保存后下一轮研究会按这个比例切训练集、验证集和测试集。">
              <div className="grid gap-3 md:grid-cols-3">
                <ConfigInput name="train_split_ratio" defaultValue={String(controls.train_split_ratio ?? "0.6")} placeholder="训练比例" />
                <ConfigInput name="validation_split_ratio" defaultValue={String(controls.validation_split_ratio ?? "0.2")} placeholder="验证比例" />
                <ConfigInput name="test_split_ratio" defaultValue={String(controls.test_split_ratio ?? "0.2")} placeholder="测试比例" />
              </div>
            </ConfigField>
            <ConfigField label="研究分数与因子权重" hint="这里决定分数门槛和各类因子的权重分配，下一轮研究会按这里重新打分。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="signal_confidence_floor" defaultValue={String(controls.signal_confidence_floor ?? "0.55")} placeholder="最低置信度" />
                <ConfigInput name="strict_penalty_weight" defaultValue={String(controls.strict_penalty_weight ?? "1")} placeholder="严格模板惩罚权重" />
                <ConfigInput name="trend_weight" defaultValue={String(controls.trend_weight ?? "1.3")} placeholder="趋势权重" />
                <ConfigInput name="momentum_weight" defaultValue={String(controls.momentum_weight ?? "1")} placeholder="动量权重" />
                <ConfigInput name="volume_weight" defaultValue={String(controls.volume_weight ?? "1.1")} placeholder="量能权重" />
                <ConfigInput name="oscillator_weight" defaultValue={String(controls.oscillator_weight ?? "0.7")} placeholder="震荡权重" />
                <ConfigInput name="volatility_weight" defaultValue={String(controls.volatility_weight ?? "0.9")} placeholder="波动权重" />
              </div>
            </ConfigField>
          </WorkbenchConfigCard>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前配置会怎么影响下一步</CardTitle>
              <CardDescription>你现在改的数据、因子、标签和门槛，最终会直接影响能不能进入 dry-run 和小额 live。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="数据范围" value={workspace.execution_preview.data_scope || "当前没有数据范围摘要"} />
              <InfoBlock label="因子组合" value={workspace.execution_preview.factor_mix || "当前没有因子组合摘要"} />
              <InfoBlock label="标签定义" value={workspace.execution_preview.label_scope || "当前没有标签定义摘要"} />
              <InfoBlock label="dry-run 门槛" value={workspace.execution_preview.dry_run_gate || "当前没有 dry-run 门槛摘要"} />
              <InfoBlock label="live 门槛" value={workspace.execution_preview.live_gate || "当前没有 live 门槛摘要"} />
              <InfoBlock label="验证放行方式" value={workspace.execution_preview.validation_policy || "当前没有验证放行说明"} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前模型</CardTitle>
              <CardDescription>这里展示当前实验依赖的模型版本和研究后端。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="模型版本" value={workspace.model.model_version || "未生成"} />
              <InfoBlock label="研究后端" value={workspace.model.backend} />
              <InfoBlock label="研究标的" value={workspace.selectors.symbols.join(" / ") || "未写入"} />
              <InfoBlock label="训练周期" value={workspace.selectors.timeframes.join(" / ") || "未写入"} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>模型和标签怎么影响结果</CardTitle>
              <CardDescription>先看模型适合什么场景，再看标签方式会把哪种走势优先判成 buy / sell / watch。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="当前模型说明" value={describeModel(selectedModelKey)} />
              <InfoBlock label="标签方式说明" value={describeLabelMode(String(controls.label_mode ?? workspace.labeling.label_mode ?? ""))} />
              <InfoBlock label="触发基础说明" value={describeLabelTriggerBasis(String(controls.label_trigger_basis ?? "close"))} />
              <InfoBlock label="持有窗口说明" value={describeHoldingWindow(String(controls.holding_window_label ?? workspace.overview.holding_window ?? "1-3d"))} />
            </CardContent>
          </Card>

          <DataTable
            columns={["模型说明", "适合什么场景", "当前是否选中", "说明"]}
            rows={modelCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "n/a"),
                String(item.key ?? "") === selectedModelKey ? "当前模型" : "可切换",
                String(item.detail ?? "当前没有额外说明"),
              ],
            }))}
            emptyTitle="当前还没有模型目录"
            emptyDetail="先恢复工作台配置选项，模型说明才会在这里出现。"
          />

          <DataTable
            columns={["标签方式说明", "更适合什么", "当前是否选中", "说明"]}
            rows={labelModeCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "n/a"),
                String(item.key ?? "") === String(controls.label_mode ?? workspace.labeling.label_mode ?? "") ? "当前方式" : "可切换",
                String(item.detail ?? "当前没有额外说明"),
              ],
            }))}
            emptyTitle="当前还没有标签方式目录"
            emptyDetail="先恢复工作台配置选项，标签方式说明才会在这里出现。"
          />

          <DataTable
            columns={["触发基础说明", "更适合什么", "当前是否选中", "说明"]}
            rows={labelTriggerCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "n/a"),
                String(item.key ?? "") === String(controls.label_trigger_basis ?? "close") ? "当前方式" : "可切换",
                String(item.detail ?? "当前没有额外说明"),
              ],
            }))}
            emptyTitle="当前还没有触发基础目录"
            emptyDetail="先恢复工作台配置选项，触发基础说明才会在这里出现。"
          />

          <DataTable
            columns={["持有窗口说明", "更适合什么", "当前是否选中", "说明"]}
            rows={holdingWindowCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "n/a"),
                String(item.key ?? "") === String(controls.holding_window_label ?? workspace.overview.holding_window ?? "1-3d") ? "当前窗口" : "可切换",
                String(item.detail ?? "当前没有额外说明"),
              ],
            }))}
            emptyTitle="当前还没有持有窗口目录"
            emptyDetail="先恢复工作台配置选项，持有窗口说明才会在这里出现。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>标签目标与止损说明</CardTitle>
              <CardDescription>把未来命中规则、目标收益和止损口径直接讲清楚，避免只盯着字段名猜含义。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="未来命中规则" value={workspace.label_rule_summary?.headline || "当前还没有标签规则摘要"} />
              <InfoBlock label="标签解释" value={workspace.label_rule_summary?.detail || "当前还没有标签解释"} />
              <InfoBlock label="下一步怎么调" value={workspace.label_rule_summary?.next_step || "先确认这一轮标签口径是否和你的目标一致。"} />
            </CardContent>
          </Card>

          <DataTable
            columns={["参数名", "参数值"]}
            rows={Object.entries(workspace.parameters).map(([name, value]) => ({
              id: name,
              cells: [name, value],
            }))}
            emptyTitle="还没有实验参数"
            emptyDetail="当前训练上下文还没有写出实验参数。"
          />

          <ActionCard action="run_research_training" label="研究训练" />
          <ActionCard action="run_research_inference" label="研究推理" />
        </div>
      </section>
    </AppShell>
  );
}

function ActionCard({ action, label }: { action: string; label: string }) {
  return (
    <Card className="bg-card/90">
      <CardContent className="p-4">
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value={action} />
          <input type="hidden" name="returnTo" value="/research" />
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-6 text-muted-foreground">通过控制平面提交研究动作，页面返回后会自动刷新当前研究工作台。</p>
          </div>
          <FormSubmitButton
            type="submit"
            size="sm"
            idleLabel={label}
            pendingLabel={`${label}运行中…`}
            pendingHint="研究动作已发出，页面返回后会更新最新上下文。"
          />
        </form>
      </CardContent>
    </Card>
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

function displayValue(value: unknown, fallback = "n/a") {
  if (value === null || value === undefined) {
    return fallback;
  }
  const normalized = String(value).trim();
  return normalized.length ? normalized : fallback;
}

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
  const rows = ["training", "validation", "test"].map((name) => {
    const window = payloadRecord(sampleWindow[name]);
    const count = Number(window.count ?? 0);
    const ratio =
      name === "training"
        ? trainRatio
        : name === "validation"
          ? validationRatio
          : testRatio;
    const label =
      name === "training" ? "训练窗口" : name === "validation" ? "验证窗口" : "测试窗口";
    return {
      id: name,
      cells: [
        label,
        `${ratio} / ${formatWindow(window)}`,
        count > 0 ? `当前大约 ${count} 条样本` : "当前还没有样本数",
      ],
    };
  });
  return rows;
}

function payloadRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function describeModel(modelKey: string) {
  switch (modelKey) {
    case "trend_bias_v2":
      return "更偏顺趋势确认，适合把趋势、量能和突破一致的标的优先排前。";
    case "balanced_v3":
      return "会同时看趋势、动量、波动和震荡，适合拿来比较多种市场状态下的均衡表现。";
    case "heuristic_v1":
    default:
      return "最基础的启发式模型，适合先跑通一轮研究，再观察配置变化会怎么影响推荐。";
  }
}

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

function describeLabelTriggerBasis(triggerBasis: string) {
  switch (triggerBasis) {
    case "high_low":
      return "按窗口内的高低点命中来判断，更接近盘中先碰目标或止损就退出。";
    case "close":
    default:
      return "按收盘价判断，口径更稳，但会弱化盘中先冲高或先下探的路径差异。";
  }
}

function describeHoldingWindow(holdingWindow: string) {
  switch (holdingWindow) {
    case "1-2d":
      return "更短，更偏快节奏择时，推荐会更敏感，但也更容易被短期波动影响。";
    case "3-5d":
      return "更偏中短波段，会优先观察更完整的一段走势，推荐更稳，但短线信号会更慢一些。";
    case "2-4d":
      return "更长，更偏耐心持有，推荐会更稳，但对短期强信号的反应会慢一点。";
    case "1-3d":
    default:
      return "当前默认窗口，兼顾快速命中和持有稳定性，也是这套单币择时研究的主目标。";
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}
