/* 这个文件负责渲染特征工作台，让因子分组、角色和预处理规则在前端可见。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ConfigCheckboxGrid, ConfigField, ConfigInput, ConfigSelect, WorkbenchConfigCard } from "../../components/workbench-config-card";
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
  const primaryFactorSet = new Set(workspace.controls.primary_factors ?? []);
  const auxiliaryFactorSet = new Set(workspace.controls.auxiliary_factors ?? []);
  const categorySummaries = Object.entries(workspace.categories).map(([name, items]) => {
    const primaryCount = items.filter((factor) => primaryFactorSet.has(factor)).length;
    const auxiliaryCount = items.filter((factor) => auxiliaryFactorSet.has(factor)).length;
    return {
      name,
      total: items.length,
      primaryCount,
      auxiliaryCount,
    };
  });
  const totalCategoryCount = categorySummaries.length;
  const totalFactorCount = categorySummaries.reduce((sum, current) => sum + current.total, 0);
  const dominantCategory = totalCategoryCount
    ? categorySummaries.reduce((prev, current) => (current.total > prev.total ? current : prev))
    : undefined;
  const averagePerGroup = totalCategoryCount ? Math.round(totalFactorCount / totalCategoryCount) : 0;

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

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>按类别看当前启用情况</CardTitle>
              <CardDescription>实时展示每个因子类目里现在有多少被设置为主判断、多少被设置为辅助确认。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {categorySummaries.length ? (
                categorySummaries.map((summary) => (
                  <div key={summary.name} className="rounded-2xl border border-border/60 bg-muted/15 p-4">
                    <p className="text-sm font-semibold text-foreground">{summary.name}</p>
                    <p className="text-xs leading-5 text-muted-foreground">
                      主判断 {summary.primaryCount} / {summary.total} · 辅助 {summary.auxiliaryCount} / {summary.total}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm leading-6 text-muted-foreground">当前还没有任何因子分组。</p>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>分组摘要</CardTitle>
              <CardDescription>这里汇总因子协议的分组规模与主/辅助比例。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <InfoBlock label="分组数量" value={String(totalCategoryCount || 0)} />
              <InfoBlock label="因子总数" value={String(totalFactorCount || workspace.overview.factor_count)} />
              <InfoBlock
                label="主判断 / 总数"
                value={`${workspace.overview.primary_count} / ${workspace.overview.factor_count}`}
              />
              <InfoBlock
                label="辅助确认 / 总数"
                value={`${workspace.overview.auxiliary_count} / ${workspace.overview.factor_count}`}
              />
              <InfoBlock
                label="最密集分组"
                value={dominantCategory ? `${dominantCategory.name} (${dominantCategory.total} 因子)` : "n/a"}
              />
              <InfoBlock
                label="平均每组"
                value={totalCategoryCount ? `${averagePerGroup} 个因子` : "n/a"}
              />
            </CardContent>
          </Card>

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
            <ConfigField label="按因子类别选择" hint="按类别浏览因子，并在主判断 / 辅助之间批量配置。">
              <p className="text-xs leading-5 text-muted-foreground">按类别看当前启用情况，再决定哪些因子放进主判断、哪些只做辅助确认。</p>
              {Object.entries(workspace.categories).length ? (
                <div className="space-y-4">
                  {Object.entries(workspace.categories).map(([category, items]) => (
                    <div key={category} className="rounded-2xl border border-border/60 bg-background/40 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-foreground">{category}</p>
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">{items.length} 个因子</p>
                      </div>
                      <p className="text-xs leading-5 text-muted-foreground">{items.length ? items.join(" / ") : "当前没有因子"}</p>
                      <div className="grid gap-2 pt-3 md:grid-cols-2">
                        <CategoryCheckboxGroup
                          title="主判断因子"
                          name="primary_factors"
                          factors={items}
                          selected={workspace.controls.primary_factors}
                        />
                        <CategoryCheckboxGroup
                          title="辅助因子"
                          name="auxiliary_factors"
                          factors={items}
                          selected={workspace.controls.auxiliary_factors}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm leading-6 text-muted-foreground">当前还没有因子类别。</p>
              )}
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
            <ConfigField label="周期参数" hint="这里可以直接调整 1h 和 4h 的趋势、动量、震荡、量能和突破窗口，让同一组因子更贴近当前节奏。">
              <div className="grid gap-4">
                <TimeframeProfile4hCard params={workspace.controls.timeframe_profiles["4h"] ?? {}} />
                <TimeframeProfile1hCard params={workspace.controls.timeframe_profiles["1h"] ?? {}} />
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

function TimeframeProfile4hCard({ params }: { params: Record<string, unknown> }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">4h 参数</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <ConfigInput
          name="timeframe_profiles.4h.trend_window"
          defaultValue={String(params.trend_window ?? "")}
          placeholder="趋势窗口"
        />
        <ConfigInput
          name="timeframe_profiles.4h.volume_window"
          defaultValue={String(params.volume_window ?? "")}
          placeholder="量能窗口"
        />
        <ConfigInput
          name="timeframe_profiles.4h.atr_period"
          defaultValue={String(params.atr_period ?? "")}
          placeholder="ATR 周期"
        />
        <ConfigInput
          name="timeframe_profiles.4h.rsi_period"
          defaultValue={String(params.rsi_period ?? "")}
          placeholder="RSI 周期"
        />
        <ConfigInput
          name="timeframe_profiles.4h.roc_period"
          defaultValue={String(params.roc_period ?? "")}
          placeholder="ROC 周期"
        />
        <ConfigInput
          name="timeframe_profiles.4h.cci_period"
          defaultValue={String(params.cci_period ?? "")}
          placeholder="CCI 周期"
        />
        <ConfigInput
          name="timeframe_profiles.4h.stoch_period"
          defaultValue={String(params.stoch_period ?? "")}
          placeholder="随机指标周期"
        />
        <ConfigInput
          name="timeframe_profiles.4h.breakout_lookback"
          defaultValue={String(params.breakout_lookback ?? "")}
          placeholder="突破回看窗口"
        />
      </div>
    </div>
  );
}

function TimeframeProfile1hCard({ params }: { params: Record<string, unknown> }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">1h 参数</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <ConfigInput
          name="timeframe_profiles.1h.trend_window"
          defaultValue={String(params.trend_window ?? "")}
          placeholder="趋势窗口"
        />
        <ConfigInput
          name="timeframe_profiles.1h.volume_window"
          defaultValue={String(params.volume_window ?? "")}
          placeholder="量能窗口"
        />
        <ConfigInput
          name="timeframe_profiles.1h.atr_period"
          defaultValue={String(params.atr_period ?? "")}
          placeholder="ATR 周期"
        />
        <ConfigInput
          name="timeframe_profiles.1h.rsi_period"
          defaultValue={String(params.rsi_period ?? "")}
          placeholder="RSI 周期"
        />
        <ConfigInput
          name="timeframe_profiles.1h.roc_period"
          defaultValue={String(params.roc_period ?? "")}
          placeholder="ROC 周期"
        />
        <ConfigInput
          name="timeframe_profiles.1h.cci_period"
          defaultValue={String(params.cci_period ?? "")}
          placeholder="CCI 周期"
        />
        <ConfigInput
          name="timeframe_profiles.1h.stoch_period"
          defaultValue={String(params.stoch_period ?? "")}
          placeholder="随机指标周期"
        />
        <ConfigInput
          name="timeframe_profiles.1h.breakout_lookback"
          defaultValue={String(params.breakout_lookback ?? "")}
          placeholder="突破回看窗口"
        />
      </div>
    </div>
  );
}

function CategoryCheckboxGroup({
  title,
  name,
  factors,
  selected,
}: {
  title: string;
  name: string;
  factors: string[];
  selected: string[];
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <ConfigCheckboxGrid
        name={name}
        options={factors.map((item) => ({
          value: item,
          label: item,
          checked: selected.includes(item),
        }))}
      />
    </div>
  );
}
