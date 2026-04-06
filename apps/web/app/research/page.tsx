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
  const configEditable = workspace.status !== "unavailable";
  const unavailableConfigReason = "工作台暂时不可用，先恢复研究接口再保存配置。";

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

      <ResearchRuntimePanel initialStatus={runtimeStatus} />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_380px]">
        <div className="space-y-5">
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
              <InfoBlock label="标签模式" value={workspace.labeling.label_mode || "未设置"} />
              <InfoBlock label="定义" value={workspace.labeling.definition || "当前没有标签定义"} />
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

          <DataTable
            columns={["窗口", "样本摘要"]}
            rows={Object.entries(workspace.sample_window).map(([name, payload]) => ({
              id: name,
              cells: [name, formatWindow(payload)],
            }))}
            emptyTitle="还没有训练窗口"
            emptyDetail="先运行研究训练，窗口摘要才会在这里出现。"
          />
        </div>

        <div className="space-y-5">
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
                options={workspace.controls.available_models.map((item) => ({ value: item, label: item }))}
              />
            </ConfigField>
            <ConfigField label="标签方式" hint="用未来窗口里的目标收益和止损阈值定义 buy / sell / watch。">
              <div className="grid gap-3">
                <ConfigSelect
                  name="label_mode"
                  defaultValue={workspace.controls.label_mode}
                  options={workspace.controls.available_label_modes.map((item) => ({ value: item, label: item }))}
                />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <ConfigInput name="label_target_pct" defaultValue={workspace.controls.label_target_pct} placeholder="目标收益 %" />
                <ConfigInput name="label_stop_pct" defaultValue={workspace.controls.label_stop_pct} placeholder="止损阈值 %" />
              </div>
            </ConfigField>
            <ConfigField label="持有窗口" hint="这会决定标签在未来几天里寻找最早命中结果。">
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
          </WorkbenchConfigCard>

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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}
