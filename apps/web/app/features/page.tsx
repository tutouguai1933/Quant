/* 这个文件负责渲染特征工作台，让因子分组、角色和预处理规则在前端可见。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ConfigCheckboxGrid, ConfigField, ConfigSelect, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { WorkbenchConfigStatusCard } from "../../components/workbench-config-status-card";
import { getFeatureWorkspace } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";

export default async function FeaturePage() {
  const session = await getControlSessionState();
  const response = await getFeatureWorkspace();
  const workspace = response.data.item;
  const configEditable = workspace.status !== "unavailable";
  const unavailableConfigReason = "工作台暂时不可用，先恢复研究接口再保存配置。";
  const featureStatus = workspace.status || "unavailable";
  const featureNote = workspace.overview.feature_version
    ? `特征版本 ${workspace.overview.feature_version} / 持有周期 ${workspace.overview.holding_window || "n/a"}`
    : "当前还没有生成特征版本";

  const categoryRows = Object.entries(workspace.categories).map(([name, items]) => ({
    id: name,
    cells: [name, items.join(" / ") || "当前无因子"],
  }));
  const timeframeRows = Object.entries(workspace.timeframe_profiles).map(([interval, params]) => ({
    id: interval,
    cells: [interval, formatProfile(params)],
  }));

  return (
    <AppShell
      title="特征工作台"
      subtitle="把因子层从“后端存在”变成“前端可见”，让你直接看懂当前启用了哪些因子、为什么这么配。"
      currentPath="/features"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="特征工作台"
        title="先把因子分组、角色、预处理规则和周期参数讲清楚。"
        description="这里直接展示当前研究主链正在使用的因子协议：哪些是主判断因子，哪些是辅助确认因子，预处理规则是什么，参数又怎样适配 1 到 3 天的持有周期。"
      />

      <MetricGrid
        items={[
          { label: "特征版本", value: workspace.overview.feature_version || "未生成", detail: "训练和推理共用同一份因子协议" },
          { label: "因子总数", value: String(workspace.overview.factor_count), detail: "当前协议里纳入的因子数量" },
          { label: "主判断因子", value: String(workspace.overview.primary_count), detail: "优先参与研究判断" },
          { label: "辅助确认因子", value: String(workspace.overview.auxiliary_count), detail: workspace.overview.holding_window || "当前持有周期未写入" },
        ]}
      />

      <WorkbenchConfigStatusCard
        scope="特征"
        status={featureStatus}
        note={featureNote}
        editable={configEditable}
      />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_380px]">
        <div className="space-y-5">
          <DataTable
            columns={["因子分组", "包含因子"]}
            rows={categoryRows}
            emptyTitle="还没有因子分组"
            emptyDetail="先运行一次 Qlib 研究训练，特征协议才会在这里出现。"
          />

          <DataTable
            columns={["因子名", "类别", "角色", "说明"]}
            rows={workspace.factors.map((item) => ({
              id: item.name,
              cells: [item.name, item.category, item.role, item.description || "当前没有说明"],
            }))}
            emptyTitle="还没有可展示的因子"
            emptyDetail="当前研究报告还没有写出因子明细。"
          />
        </div>

        <div className="space-y-5">
          <WorkbenchConfigCard
            title="因子组合配置"
            description="这里选的主判断因子和辅助因子，会真正进入研究评分和解释，不只是页面展示。"
            scope="features"
            returnTo="/features"
            disabled={!configEditable}
            disabledReason={unavailableConfigReason}
          >
            <ConfigField label="主判断因子" hint="这些因子会直接参与当前模型的打分。">
              <ConfigCheckboxGrid
                name="primary_factors"
                options={workspace.controls.available_primary_factors.map((item) => ({
                  value: item,
                  label: item,
                  checked: workspace.controls.primary_factors.includes(item),
                }))}
              />
            </ConfigField>
            <ConfigField label="辅助因子" hint="这些因子只做确认和解释，不单独决定最终推荐。">
              <ConfigCheckboxGrid
                name="auxiliary_factors"
                options={workspace.controls.available_auxiliary_factors.map((item) => ({
                  value: item,
                  label: item,
                  checked: workspace.controls.auxiliary_factors.includes(item),
                }))}
              />
            </ConfigField>
            <ConfigField label="预处理规则" hint="这里改的是因子进入训练前的清洗方式，保存后下一轮训练和推理都会按这里重算。">
              <div className="grid gap-3 md:grid-cols-3">
                <ConfigSelect
                  name="missing_policy"
                  defaultValue={workspace.controls.missing_policy}
                  options={workspace.controls.available_missing_policies.map((item) => ({
                    value: item,
                    label: item === "strict_drop" ? "严格丢弃缺失行" : "中性值补齐",
                  }))}
                />
                <ConfigSelect
                  name="outlier_policy"
                  defaultValue={workspace.controls.outlier_policy}
                  options={workspace.controls.available_outlier_policies.map((item) => ({ value: item, label: item }))}
                />
                <ConfigSelect
                  name="normalization_policy"
                  defaultValue={workspace.controls.normalization_policy}
                  options={workspace.controls.available_normalization_policies.map((item) => ({ value: item, label: item }))}
                />
              </div>
            </ConfigField>
          </WorkbenchConfigCard>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>主判断因子</CardTitle>
              <CardDescription>这些因子直接参与当前研究判断。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {workspace.roles.primary.length ? workspace.roles.primary.map((item) => (
                <Badge key={item}>{item}</Badge>
              )) : <p className="text-sm leading-6 text-muted-foreground">当前没有主判断因子。</p>}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>辅助确认因子</CardTitle>
              <CardDescription>这些因子用于补充确认，不单独决定推荐。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {workspace.roles.auxiliary.length ? workspace.roles.auxiliary.map((item) => (
                <Badge key={item} variant="outline">{item}</Badge>
              )) : <p className="text-sm leading-6 text-muted-foreground">当前没有辅助确认因子。</p>}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>预处理规则</CardTitle>
              <CardDescription>这三条规则决定了因子进入训练前会怎样被清洗。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="缺失处理" value={workspace.preprocessing.missing_policy || "未设置"} />
              <InfoBlock label="去极值" value={workspace.preprocessing.outlier_policy || "未设置"} />
              <InfoBlock label="标准化" value={workspace.preprocessing.normalization_policy || "未设置"} />
              <InfoBlock
                label="当前配置"
                value={`缺失=${workspace.controls.missing_policy || "neutral_fill"} / 去极值=${workspace.controls.outlier_policy || "clip"} / 标准化=${workspace.controls.normalization_policy || "fixed_4dp"}`}
              />
            </CardContent>
          </Card>

          <DataTable
            columns={["周期", "参数映射"]}
            rows={timeframeRows}
            emptyTitle="还没有周期参数"
            emptyDetail="当前研究协议还没有写出周期参数映射。"
          />
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

function formatProfile(profile: Record<string, unknown>) {
  const items = Object.entries(profile).map(([key, value]) => `${key}=${String(value)}`);
  return items.join(" / ") || "当前没有参数";
}
