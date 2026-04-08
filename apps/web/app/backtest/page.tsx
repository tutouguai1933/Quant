/* 这个文件负责渲染回测工作台，让成本模型、净收益、回撤和动作段直接可见。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ConfigField, ConfigInput, ConfigSelect, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { getBacktestWorkspace } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";
import { WorkbenchConfigStatusCard } from "../../components/workbench-config-status-card";

export default async function BacktestPage() {
  const session = await getControlSessionState();
  const response = await getBacktestWorkspace();
  const workspace = response.data.item;
  const backtestStatus = workspace.status || "unavailable";
  const backtestNote =
    workspace.training_backtest.metrics && Object.keys(workspace.training_backtest.metrics).length
      ? `净收益 ${metric(workspace.training_backtest.metrics, "net_return_pct")} / Sharpe ${metric(workspace.training_backtest.metrics, "sharpe")}`
      : "当前还没有回测结果";
  const metrics = workspace.training_backtest.metrics;
  const workspaceRecord = asRecord(workspace);
  const backtestControls = asRecord(workspace.controls);
  const gatePreview = backtestControls;
  const costModelCatalog = Array.isArray(backtestControls.cost_model_catalog)
    ? backtestControls.cost_model_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const backtestPresetCatalog = Array.isArray(backtestControls.backtest_preset_catalog)
    ? backtestControls.backtest_preset_catalog.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const stageAssessment = Array.isArray(workspaceRecord.stage_assessment)
    ? workspaceRecord.stage_assessment.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const configEditable = workspace.status !== "unavailable";
  const unavailableConfigReason = "工作台暂时不可用，先恢复研究接口再保存配置。";
  const gateStates = [
    { label: "规则门", key: "enable_rule_gate", enabled: workspace.controls.enable_rule_gate },
    { label: "验证门", key: "enable_validation_gate", enabled: workspace.controls.enable_validation_gate },
    { label: "回测门", key: "enable_backtest_gate", enabled: workspace.controls.enable_backtest_gate },
    { label: "一致性门", key: "enable_consistency_gate", enabled: workspace.controls.enable_consistency_gate },
    { label: "live 门", key: "enable_live_gate", enabled: workspace.controls.enable_live_gate },
  ];

  return (
    <AppShell
      title="回测工作台"
      subtitle="把回测结果拆开讲清楚：成本模型是什么，净收益是多少，成本影响、回撤和动作段又分别代表什么。"
      currentPath="/backtest"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="回测工作台"
        title="先确认净收益、成本影响和动作段，再决定这套研究结果值不值得进入验证。"
        description="这里不会只给一个回测分数，而是直接把成本模型、净收益、回撤、Sharpe 和动作段统计摊开，方便你判断这次回测到底靠不靠谱。"
      />

      <MetricGrid
        items={[
          { label: "净收益", value: metric(metrics, "net_return_pct"), detail: `${workspace.overview.holding_window || "未写入"} / ${workspace.backend}` },
          { label: "成本影响", value: metric(metrics, "cost_impact_pct"), detail: "把手续费和滑点单独摊开看" },
          { label: "最大回撤", value: metric(metrics, "max_drawdown_pct"), detail: "亏损最深的那一段" },
          { label: "动作段统计", value: metric(metrics, "action_segment_count"), detail: `方向切换 ${metric(metrics, "direction_switch_count")}` },
        ]}
      />

      <WorkbenchConfigStatusCard
        scope="回测"
        status={backtestStatus}
        note={backtestNote}
        editable={configEditable}
      />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_380px]">
        <div className="space-y-5">
          <DataTable
            columns={["标的", "模板", "净收益", "成本影响", "最大回撤", "Sharpe"]}
            rows={workspace.leaderboard.map((item) => ({
              id: item.symbol,
              cells: [
                item.symbol,
                item.strategy_template || "未标注",
                valueOrFallback(item.backtest.net_return_pct),
                valueOrFallback(item.backtest.cost_impact_pct),
                valueOrFallback(item.backtest.max_drawdown_pct),
                valueOrFallback(item.backtest.sharpe),
              ],
            }))}
            emptyTitle="还没有候选回测"
            emptyDetail="先运行研究训练和推理，再回到这里比较候选回测。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>交易明细</CardTitle>
              <CardDescription>当前最小回测先展示动作段和切换统计，逐笔明细后续再继续补齐。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="动作段统计" value={metric(metrics, "action_segment_count")} />
              <InfoBlock label="方向切换" value={metric(metrics, "direction_switch_count")} />
              <InfoBlock label="胜率" value={metric(metrics, "win_rate")} />
              <InfoBlock label="连续亏损段" value={metric(metrics, "max_loss_streak")} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>成本与过滤拆解</CardTitle>
              <CardDescription>把成本来源、动作段明细和过滤影响拆开讲清楚，避免只看到一串净收益。</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <DataTable
                columns={["拆解项", "当前口径", "会影响什么"]}
                rows={buildBacktestBreakdownRows(workspace, metrics, gateStates)}
                emptyTitle="当前还没有回测拆解"
                emptyDetail="先保存回测参数并跑一轮训练，这里才会按当前配置解释成本和过滤影响。"
              />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>严格规则</CardTitle>
              <CardDescription>研究候选只有同时满足这四条严格规则，才会被认为有突破辨识度。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="EMA20 最低偏离" value={valueOrFallback(workspace.controls.strict_rule_min_ema20_gap_pct)} />
              <InfoBlock label="EMA55 最低偏离" value={valueOrFallback(workspace.controls.strict_rule_min_ema55_gap_pct)} />
              <InfoBlock label="最高 ATR 波动" value={valueOrFallback(workspace.controls.strict_rule_max_atr_pct)} />
              <InfoBlock label="最低量能比" value={valueOrFallback(workspace.controls.strict_rule_min_volume_ratio)} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>门控开关</CardTitle>
              <CardDescription>五个门控可以临时开/关，用来快速排查是哪一层阻止了候选。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {gateStates.map((gate) => (
                <Badge key={gate.key} variant={gate.enabled ? undefined : "outline"}>
                  {gate.label}: {gate.enabled ? "开启" : "关闭"}
                </Badge>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <WorkbenchConfigCard
            title="回测预设"
            description="先套用一套回测口径，再继续微调手续费、滑点和门槛。"
            scope="backtest"
            returnTo="/backtest"
            disabled={!configEditable}
            disabledReason={unavailableConfigReason}
          >
            <ConfigField label="一键套用" hint="预设会先改成本模型、手续费和滑点，让你快速切换到标准、压力或基线口径。">
              <ConfigSelect
                name="backtest_preset_key"
                defaultValue={String(workspace.controls.backtest_preset_key ?? "realistic_standard")}
                options={(workspace.controls.available_backtest_presets || []).map((item) => ({
                  value: item,
                  label: item,
                }))}
              />
            </ConfigField>
            <DataTable
              columns={["回测预设", "适用场景", "说明"]}
              rows={backtestPresetCatalog.map((item, index) => ({
                id: `${item.key ?? index}`,
                cells: [
                  String(item.key ?? "n/a"),
                  String(item.fit ?? "当前没有适用场景说明"),
                  String(item.detail ?? "当前没有预设说明"),
                ],
              }))}
              emptyTitle="当前还没有回测预设"
              emptyDetail="先恢复回测工作台，系统才会给出一键回测预设。"
            />
          </WorkbenchConfigCard>

          <WorkbenchConfigCard
            title="回测参数配置"
            description="这里改的是成本模型，保存后下一轮训练、回测和评估都会按这里的口径重算。"
            scope="backtest"
            returnTo="/backtest"
            disabled={!configEditable}
            disabledReason={unavailableConfigReason}
          >
            <ConfigField label="成本模型" hint="先定清楚成本是按单边、双边还是零成本基线计算。">
              <ConfigSelect
                name="cost_model"
                defaultValue={workspace.controls.cost_model}
                options={workspace.controls.available_cost_models.map((item) => ({ value: item, label: item }))}
              />
            </ConfigField>
            <ConfigField label="手续费和滑点" hint="先把成本口径定清楚，再看净收益和回撤。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="fee_bps" defaultValue={workspace.controls.fee_bps} placeholder="手续费 bps" />
                <ConfigInput name="slippage_bps" defaultValue={workspace.controls.slippage_bps} placeholder="滑点 bps" />
              </div>
            </ConfigField>
            <ConfigField label="dry-run 门槛" hint="这里控制一轮回测至少要达到什么水平，才允许继续进入 dry-run。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="dry_run_min_score" defaultValue={workspace.controls.dry_run_min_score} placeholder="最低分数" />
                <ConfigInput name="dry_run_min_positive_rate" defaultValue={workspace.controls.dry_run_min_positive_rate} placeholder="最低正收益比例" />
                <ConfigInput name="dry_run_min_net_return_pct" defaultValue={workspace.controls.dry_run_min_net_return_pct} placeholder="最低净收益 %" />
                <ConfigInput name="dry_run_min_sharpe" defaultValue={workspace.controls.dry_run_min_sharpe} placeholder="最低 Sharpe" />
                <ConfigInput name="dry_run_max_drawdown_pct" defaultValue={workspace.controls.dry_run_max_drawdown_pct} placeholder="最大回撤 %" />
                <ConfigInput name="dry_run_max_loss_streak" defaultValue={workspace.controls.dry_run_max_loss_streak} placeholder="最大连续亏损段" />
                <ConfigInput name="dry_run_min_win_rate" defaultValue={workspace.controls.dry_run_min_win_rate} placeholder="最低胜率" />
                <ConfigInput name="dry_run_max_turnover" defaultValue={workspace.controls.dry_run_max_turnover} placeholder="最高换手" />
                <ConfigInput name="dry_run_min_sample_count" defaultValue={workspace.controls.dry_run_min_sample_count} placeholder="最低样本数" />
              </div>
            </ConfigField>
            <ConfigField label="验证与 live 门槛" hint="这里继续补齐验证和 live 的最小放行条件。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="validation_min_sample_count" defaultValue={workspace.controls.validation_min_sample_count} placeholder="验证最少样本数" />
                <ConfigInput name="validation_min_avg_future_return_pct" defaultValue={workspace.controls.validation_min_avg_future_return_pct} placeholder="验证最低未来收益 %" />
                <ConfigInput name="live_min_score" defaultValue={workspace.controls.live_min_score} placeholder="live 最低分数" />
                <ConfigInput name="live_min_positive_rate" defaultValue={workspace.controls.live_min_positive_rate} placeholder="live 最低正收益比例" />
                <ConfigInput name="live_min_net_return_pct" defaultValue={workspace.controls.live_min_net_return_pct} placeholder="live 最低净收益 %" />
                <ConfigInput name="live_min_win_rate" defaultValue={workspace.controls.live_min_win_rate} placeholder="live 最低胜率" />
                <ConfigInput name="live_max_turnover" defaultValue={workspace.controls.live_max_turnover} placeholder="live 最高换手" />
                <ConfigInput name="live_min_sample_count" defaultValue={workspace.controls.live_min_sample_count} placeholder="live 最低样本数" />
              </div>
            </ConfigField>
            <ConfigField label="规则门与一致性门" hint="这里控制趋势确认、波动上限、量能要求，以及训练/验证/回测之间允许出现多大漂移。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="rule_min_ema20_gap_pct" defaultValue={workspace.controls.rule_min_ema20_gap_pct} placeholder="EMA20 最低偏离 %" />
                <ConfigInput name="rule_min_ema55_gap_pct" defaultValue={workspace.controls.rule_min_ema55_gap_pct} placeholder="EMA55 最低偏离 %" />
                <ConfigInput name="rule_max_atr_pct" defaultValue={workspace.controls.rule_max_atr_pct} placeholder="ATR 最高波动 %" />
                <ConfigInput name="rule_min_volume_ratio" defaultValue={workspace.controls.rule_min_volume_ratio} placeholder="最低量能比" />
                <ConfigInput name="strict_rule_min_ema20_gap_pct" defaultValue={String(workspace.controls.strict_rule_min_ema20_gap_pct ?? "1.2")} placeholder="严格模板 EMA20 最低偏离 %" />
                <ConfigInput name="strict_rule_min_ema55_gap_pct" defaultValue={String(workspace.controls.strict_rule_min_ema55_gap_pct ?? "1.8")} placeholder="严格模板 EMA55 最低偏离 %" />
                <ConfigInput name="strict_rule_max_atr_pct" defaultValue={String(workspace.controls.strict_rule_max_atr_pct ?? "4.5")} placeholder="严格模板 ATR 最高波动 %" />
                <ConfigInput name="strict_rule_min_volume_ratio" defaultValue={String(workspace.controls.strict_rule_min_volume_ratio ?? "1.05")} placeholder="严格模板最低量能比" />
                <ConfigInput name="consistency_max_validation_backtest_return_gap_pct" defaultValue={workspace.controls.consistency_max_validation_backtest_return_gap_pct} placeholder="验证/回测最大收益差 %" />
                <ConfigInput name="consistency_max_training_validation_positive_rate_gap" defaultValue={workspace.controls.consistency_max_training_validation_positive_rate_gap} placeholder="训练/验证最大正收益比例差" />
                <ConfigInput name="consistency_max_training_validation_return_gap_pct" defaultValue={workspace.controls.consistency_max_training_validation_return_gap_pct} placeholder="训练/验证最大收益差 %" />
              </div>
            </ConfigField>
            <ConfigField label="门控开关" hint="这里可以临时关闭某一层门控，方便判断到底是规则、验证、回测还是一致性在拦住候选。">
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigSelect
                  name="enable_rule_gate"
                  defaultValue={String(Boolean(workspace.controls.enable_rule_gate))}
                  options={[
                    { value: "true", label: "开启规则门" },
                    { value: "false", label: "关闭规则门" },
                  ]}
                />
                <ConfigSelect
                  name="enable_validation_gate"
                  defaultValue={String(Boolean(workspace.controls.enable_validation_gate))}
                  options={[
                    { value: "true", label: "开启验证门" },
                    { value: "false", label: "关闭验证门" },
                  ]}
                />
                <ConfigSelect
                  name="enable_backtest_gate"
                  defaultValue={String(Boolean(workspace.controls.enable_backtest_gate))}
                  options={[
                    { value: "true", label: "开启回测门" },
                    { value: "false", label: "关闭回测门" },
                  ]}
                />
                <ConfigSelect
                  name="enable_consistency_gate"
                  defaultValue={String(Boolean(workspace.controls.enable_consistency_gate))}
                  options={[
                    { value: "true", label: "开启一致性门" },
                    { value: "false", label: "关闭一致性门" },
                  ]}
                />
                <ConfigSelect
                  name="enable_live_gate"
                  defaultValue={String(Boolean(workspace.controls.enable_live_gate))}
                  options={[
                    { value: "true", label: "开启 live 门" },
                    { value: "false", label: "关闭 live 门" },
                  ]}
                />
              </div>
            </ConfigField>
          </WorkbenchConfigCard>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>成本模型</CardTitle>
              <CardDescription>先确认手续费、滑点和回合成本是怎么算的。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="手续费" value={valueOrFallback(workspace.assumptions.fee_bps)} />
              <InfoBlock label="滑点" value={valueOrFallback(workspace.assumptions.slippage_bps)} />
              <InfoBlock label="回合成本" value={valueOrFallback(workspace.assumptions.round_trip_cost_pct)} />
              <InfoBlock label="成本模型" value={valueOrFallback(workspace.assumptions.cost_model)} />
            </CardContent>
          </Card>

          <DataTable
            columns={["成本模型说明", "更适合什么", "当前是否选中", "说明"]}
            rows={costModelCatalog.map((item, index) => ({
              id: `${String(item.key ?? index)}`,
              cells: [
                String(item.label ?? item.key ?? "n/a"),
                String(item.fit ?? "n/a"),
                String(item.key ?? "") === String(workspace.controls.cost_model ?? "") ? "当前口径" : "可切换",
                String(item.detail ?? "当前没有额外说明"),
              ],
            }))}
            emptyTitle="当前还没有成本模型目录"
            emptyDetail="先恢复工作台配置选项，成本模型说明才会在这里出现。"
          />

          <DataTable
            columns={["准入阶段", "先看什么", "当前结果", "说明"]}
            rows={stageAssessment.map((item, index) => ({
              id: `${String(item.stage ?? index)}`,
              cells: [
                String(item.stage ?? "n/a"),
                String(item.focus ?? "当前没有门槛摘要"),
                String(item.current ?? "当前没有结果"),
                String(item.headline ?? "当前没有阶段说明"),
              ],
            }))}
            emptyTitle="当前还没有阶段门槛对照"
            emptyDetail="先生成一轮回测结果，系统才会按 dry-run / 验证 / live 三层给出对照。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>回测摘要</CardTitle>
              <CardDescription>把关键结果压成一眼能看懂的最小摘要。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="总收益" value={metric(metrics, "total_return_pct")} />
              <InfoBlock label="毛收益" value={metric(metrics, "gross_return_pct")} />
              <InfoBlock label="净收益" value={metric(metrics, "net_return_pct")} />
              <InfoBlock label="Sharpe" value={metric(metrics, "sharpe")} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>准入门槛预览</CardTitle>
              <CardDescription>这些门槛会直接影响候选是否能从回测进入 dry-run 或 live。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="dry_run_min_win_rate" value={valueOrFallback(asOptionalString(gatePreview.dry_run_min_win_rate))} />
              <InfoBlock label="dry_run_max_turnover" value={valueOrFallback(asOptionalString(gatePreview.dry_run_max_turnover))} />
              <InfoBlock label="dry_run_min_sample_count" value={valueOrFallback(asOptionalString(gatePreview.dry_run_min_sample_count))} />
              <InfoBlock label="live_min_win_rate" value={valueOrFallback(asOptionalString(gatePreview.live_min_win_rate))} />
              <InfoBlock label="live_max_turnover" value={valueOrFallback(asOptionalString(gatePreview.live_max_turnover))} />
              <InfoBlock label="live_min_sample_count" value={valueOrFallback(asOptionalString(gatePreview.live_min_sample_count))} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>完整准入门槛</CardTitle>
              <CardDescription>把 dry-run、验证和 live 三层门槛一次看全，先确认这轮结果到底卡在哪一层。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="dry_run_min_score" value={valueOrFallback(asOptionalString(gatePreview.dry_run_min_score))} />
              <InfoBlock label="dry_run_min_positive_rate" value={valueOrFallback(asOptionalString(gatePreview.dry_run_min_positive_rate))} />
              <InfoBlock label="dry_run_min_net_return_pct" value={valueOrFallback(asOptionalString(gatePreview.dry_run_min_net_return_pct))} />
              <InfoBlock label="dry_run_min_sharpe" value={valueOrFallback(asOptionalString(gatePreview.dry_run_min_sharpe))} />
              <InfoBlock label="dry_run_max_drawdown_pct" value={valueOrFallback(asOptionalString(gatePreview.dry_run_max_drawdown_pct))} />
              <InfoBlock label="dry_run_max_loss_streak" value={valueOrFallback(asOptionalString(gatePreview.dry_run_max_loss_streak))} />
              <InfoBlock label="dry_run_min_win_rate" value={valueOrFallback(asOptionalString(gatePreview.dry_run_min_win_rate))} />
              <InfoBlock label="dry_run_max_turnover" value={valueOrFallback(asOptionalString(gatePreview.dry_run_max_turnover))} />
              <InfoBlock label="dry_run_min_sample_count" value={valueOrFallback(asOptionalString(gatePreview.dry_run_min_sample_count))} />
              <InfoBlock label="validation_min_sample_count" value={valueOrFallback(asOptionalString(gatePreview.validation_min_sample_count))} />
              <InfoBlock label="validation_min_avg_future_return_pct" value={valueOrFallback(asOptionalString(gatePreview.validation_min_avg_future_return_pct))} />
              <InfoBlock label="rule_min_ema20_gap_pct" value={valueOrFallback(asOptionalString(gatePreview.rule_min_ema20_gap_pct))} />
              <InfoBlock label="rule_min_ema55_gap_pct" value={valueOrFallback(asOptionalString(gatePreview.rule_min_ema55_gap_pct))} />
              <InfoBlock label="rule_max_atr_pct" value={valueOrFallback(asOptionalString(gatePreview.rule_max_atr_pct))} />
              <InfoBlock label="rule_min_volume_ratio" value={valueOrFallback(asOptionalString(gatePreview.rule_min_volume_ratio))} />
              <InfoBlock label="consistency_max_validation_backtest_return_gap_pct" value={valueOrFallback(asOptionalString(gatePreview.consistency_max_validation_backtest_return_gap_pct))} />
              <InfoBlock label="consistency_max_training_validation_positive_rate_gap" value={valueOrFallback(asOptionalString(gatePreview.consistency_max_training_validation_positive_rate_gap))} />
              <InfoBlock label="consistency_max_training_validation_return_gap_pct" value={valueOrFallback(asOptionalString(gatePreview.consistency_max_training_validation_return_gap_pct))} />
              <InfoBlock label="live_min_score" value={valueOrFallback(asOptionalString(gatePreview.live_min_score))} />
              <InfoBlock label="live_min_positive_rate" value={valueOrFallback(asOptionalString(gatePreview.live_min_positive_rate))} />
              <InfoBlock label="live_min_net_return_pct" value={valueOrFallback(asOptionalString(gatePreview.live_min_net_return_pct))} />
              <InfoBlock label="live_min_win_rate" value={valueOrFallback(asOptionalString(gatePreview.live_min_win_rate))} />
              <InfoBlock label="live_max_turnover" value={valueOrFallback(asOptionalString(gatePreview.live_max_turnover))} />
              <InfoBlock label="live_min_sample_count" value={valueOrFallback(asOptionalString(gatePreview.live_min_sample_count))} />
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

function metric(metrics: Record<string, string>, key: string) {
  return valueOrFallback(metrics[key]);
}

function valueOrFallback(value: string | undefined) {
  return value && value.length > 0 ? value : "n/a";
}

function asOptionalString(value: unknown): string | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  return String(value);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function buildBacktestBreakdownRows(
  workspace: {
    assumptions: Record<string, string>;
  },
  metrics: Record<string, string>,
  gateStates: Array<{ label: string; key: string; enabled: boolean }>,
) {
  const gateSummary = gateStates.map((gate) => `${gate.label}${gate.enabled ? "开启" : "关闭"}`).join(" / ") || "当前没有门控说明";
  return [
    {
      id: "cost-model",
      cells: [
        "成本来源",
        valueOrFallback(workspace.assumptions.cost_model),
        "决定净收益是按零成本、单边成本还是双边回合成本来扣减。",
      ],
    },
    {
      id: "fee",
      cells: [
        "手续费",
        valueOrFallback(workspace.assumptions.fee_bps),
        "直接影响每次开平仓后的净收益，频繁切换时影响更明显。",
      ],
    },
    {
      id: "slippage",
      cells: [
        "滑点",
        valueOrFallback(workspace.assumptions.slippage_bps),
        "用来模拟真实成交时拿不到理想价格的那部分损耗。",
      ],
    },
    {
      id: "round-trip",
      cells: [
        "回合成本",
        valueOrFallback(workspace.assumptions.round_trip_cost_pct),
        "把一开一平的总摩擦成本压成一项，方便和毛收益直接对照。",
      ],
    },
    {
      id: "action-segments",
      cells: [
        "动作段明细",
        `${metric(metrics, "action_segment_count")} / 切换 ${metric(metrics, "direction_switch_count")}`,
        "动作段越多、切换越频繁，越容易把成本模型放大成净收益压力。",
      ],
    },
    {
      id: "loss-streak",
      cells: [
        "过滤影响",
        gateSummary,
        "规则门、验证门、回测门、一致性门和 live 门共同决定这轮结果能不能继续进入验证或执行。",
      ],
    },
  ];
}
