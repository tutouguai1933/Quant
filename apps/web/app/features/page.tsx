"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FeaturesFactorDetailDrawer, type FeatureFactorDetailItem } from "../../components/features-factor-detail-drawer";
import { FeaturesFocusGrid, type FeaturesFocusCard } from "../../components/features-focus-grid";
import { FeatureFlowLinks, FeaturesPrimaryActionSection } from "../../components/features-primary-action-section";
import { PageHero } from "../../components/page-hero";
import { Skeleton } from "../../components/ui/skeleton";
import { ConfigCheckboxGrid, ConfigField, ConfigInput, ConfigSelect, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { getFeatureWorkspace } from "../../lib/api";
import { readFeedback } from "../../lib/feedback";

const CATEGORY_META = [
  { key: "trend", label: "趋势" },
  { key: "momentum", label: "动量" },
  { key: "oscillator", label: "震荡" },
  { key: "volume", label: "成交量" },
  { key: "volatility", label: "波动率" },
  { key: "extension", label: "扩展因子" },
] as const;

const REDUNDANCY_GROUPS = [
  { key: "trend", label: "趋势延续组", factors: ["trend_gap_pct", "ema20_gap_pct", "ema55_gap_pct"] },
  { key: "momentum", label: "动量推进组", factors: ["close_return_pct", "body_pct", "breakout_strength", "roc6"] },
  { key: "oscillator", label: "震荡确认组", factors: ["rsi14", "cci20", "stoch_k14"] },
  { key: "volatility", label: "波动风控组", factors: ["range_pct", "atr_pct"] },
  { key: "volume", label: "量能确认组", factors: ["volume_ratio"] },
] as const;

type SessionState = {
  isAuthenticated: boolean;
};

type WorkspaceData = Awaited<ReturnType<typeof getFeatureWorkspace>>["data"]["item"];

export default function FeaturePage() {
  const searchParams = useSearchParams();
  const [isLoading, setIsLoading] = useState(true);
  const [session, setSession] = useState<SessionState>({ isAuthenticated: false });
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 15000);

    fetch("/api/control/session", { signal: abortController.signal })
      .then((response) => response.json())
      .then((data) => {
        setSession({ isAuthenticated: data?.isAuthenticated ?? false });
      })
      .catch(() => {
        setSession({ isAuthenticated: false });
      });

    return () => {
      clearTimeout(timeoutId);
      abortController.abort();
    };
  }, []);

  useEffect(() => {
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 15000);

    setIsLoading(true);
    getFeatureWorkspace(abortController.signal)
      .then((response) => {
        setWorkspace(response.data.item);
      })
      .catch(() => {
        setWorkspace(null);
      })
      .finally(() => {
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      abortController.abort();
    };
  }, []);

  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  if (isLoading || !workspace) {
    return (
      <AppShell
        title="因子工作台"
        subtitle="先看因子分类、当前启用、有效性、冗余和总分解释，细节按需展开。"
        currentPath="/features"
        isAuthenticated={session.isAuthenticated}
      >
        <PageHero
          badge="因子工作台"
          title="先把多因子体系讲清楚，再决定哪些因子值得继续进入研究评分。"
          description="因子页默认不再只是权重配置页，而是先回答五件事：因子怎么分、现在启用了什么、当前有效性如何、哪些地方可能重复、总分主要被谁拉动。"
        />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-48 rounded-2xl" />
        </div>
      </AppShell>
    );
  }
  const selectionStory = asRecord(workspace.selection_story);
  const selectedFeaturePreset = asRecord(selectionStory.feature_preset);
  const preprocessingStory = asRecord(selectionStory.preprocessing);

  const featurePresetCatalog = toRecordArray(workspace.controls.feature_preset_catalog);
  const categoryCatalog = toRecordArray(workspace.category_catalog);
  const availableFeaturePresets = toStringArray(workspace.controls.available_feature_presets);
  const availableMissingPolicies = toStringArray(workspace.controls.available_missing_policies);
  const availableOutlierPolicies = toStringArray(workspace.controls.available_outlier_policies);
  const availableNormalizationPolicies = toStringArray(workspace.controls.available_normalization_policies);

  const configEditable = session.isAuthenticated && workspace.status !== "unavailable";
  const unavailableConfigReason = !session.isAuthenticated ? "请先登录后再保存配置。" : "工作台暂时不可用，先恢复研究接口再保存配置。";
  const disabledSaveLabel = !session.isAuthenticated ? "登录后可保存配置" : "当前不可保存";

  const featureStatus = workspace.status || "unavailable";
  const featureNote = workspace.overview.feature_version
    ? `特征版本 ${workspace.overview.feature_version} / 持有周期 ${workspace.overview.holding_window || "n/a"}`
    : "当前还没有生成特征版本";

  const primaryFactors = toStringArray(workspace.controls.primary_factors);
  const auxiliaryFactors = toStringArray(workspace.controls.auxiliary_factors);
  const primaryFactorSet = new Set(primaryFactors);
  const auxiliaryFactorSet = new Set(auxiliaryFactors);
  const selectedFactorSet = new Set([...primaryFactors, ...auxiliaryFactors]);

  const categories = buildCategoryOverview(workspace.categories, primaryFactorSet, auxiliaryFactorSet);
  const totalCategoryCount = categories.length;
  const activeCategoryCount = categories.filter((item) => item.total > 0).length;
  const totalFactorCount = categories.reduce((sum, current) => sum + current.total, 0);
  const dominantCategory = categories.reduce<(typeof categories)[number] | undefined>((prev, current) => {
    if (!prev) {
      return current;
    }
    return current.total > prev.total ? current : prev;
  }, undefined);
  const averagePerGroup = activeCategoryCount ? Math.round(totalFactorCount / activeCategoryCount) : 0;

  const categoryRows = categories.map((item) => ({
    id: item.key,
    cells: [item.label, item.factors.length ? item.factors.join(" / ") : "当前无因子"],
  }));
  const timeframeRows = Object.entries(workspace.timeframe_profiles).map(([interval, params]) => ({
    id: interval,
    cells: [interval, formatProfile(params)],
  }));

  const categoryWeightRows = categoryCatalog.length
    ? categoryCatalog.map((item, index) => ({
        id: String(item.key ?? index),
        cells: [
          readPlainText(item.label ?? item.key, "n/a"),
          readPlainText(item.current_mix, "当前没有启用摘要"),
          readPlainText(item.weight_entry, "研究页统一评分"),
          readPlainText(item.effect, "当前没有影响说明"),
          readPlainText(item.detail, "当前没有额外说明"),
        ],
      }))
    : categories.map((summary) => ({
        id: summary.key,
        cells: [summary.label, summary.currentMix, summary.weightEntry, summary.effect, summary.detail],
      }));

  const selectionMatrixRows = Array.isArray(workspace.selection_matrix)
    ? workspace.selection_matrix.map((item) => ({
        id: String(item.name ?? ""),
        cells: [
          String(item.name ?? "n/a"),
          String(item.category ?? "未分类"),
          String(item.protocol_role ?? "未定义"),
          String(item.current_role ?? "未启用"),
          String(item.description ?? "当前没有说明"),
        ],
      }))
    : [];
  const currentRoleByFactor = new Map(selectionMatrixRows.map((item) => [item.id, String(item.cells[3] ?? "未启用")]));

  const weightSummary = buildWeightSummary(workspace.controls);
  const topWeightedCategories = [...categories]
    .sort((left, right) => parseNumeric(right.currentWeight) - parseNumeric(left.currentWeight))
    .filter((item) => parseNumeric(item.currentWeight) > 0);
  const leadCategory = topWeightedCategories[0] ?? categories[0];
  const secondCategory = topWeightedCategories[1];
  const timeframeSummary = displayValue(selectionStory.timeframe_summary, "当前还没有周期摘要");
  const preprocessingHeadline = displayValue(preprocessingStory.headline, "当前还没有预处理摘要");
  const preprocessingDetail = displayValue(preprocessingStory.detail, "当前还没有预处理说明");

  const effectivenessRows = categories.map((item) => ({
    key: item.key,
    label: item.label,
    currentWeight: item.currentWeight,
    currentMix: item.currentMix,
    icNote: item.primaryCount
      ? `${item.label} 当前承担 ${item.primaryCount} 个主判断因子，先作为研究总分里最值得盯的信号组。`
      : `${item.label} 当前没有主判断因子，暂时更多承担辅助解释。`,
    bucketNote: item.effect,
    stabilityNote: `${preprocessingHeadline}；${timeframeSummary}`,
    detail: item.detail,
  }));
  const effectivenessHeadline = leadCategory
    ? `${leadCategory.label} 当前最影响研究打分`
    : "当前还没有可解释的主导类别";
  const effectivenessDetail = leadCategory
    ? `${leadCategory.label} 现在是最重的权重入口，${secondCategory ? `${secondCategory.label} 紧跟在后。` : "当前没有第二个明显主导类别。"}`
    : "先恢复因子协议，再看哪类因子最影响研究打分。";
  const icStory = leadCategory
    ? `${leadCategory.label} 当前最值得先看，主判断覆盖 ${leadCategory.primaryCount} 个因子。`
    : "当前还没有可用 IC 观察组。";
  const bucketStory = leadCategory ? leadCategory.effect : "当前还没有可用分组收益摘要。";
  const stabilityStory = `${preprocessingHeadline}；${timeframeSummary}`;

  const overlapGroups = REDUNDANCY_GROUPS.map((group) => {
    const active = group.factors.filter((factor) => selectedFactorSet.has(factor));
    const redundancyLevel = active.length >= 3 ? "高重合" : active.length === 2 ? "中重合" : "低重合";
    const dedupStatus =
      active.length >= 3
        ? `当前同组启用了 ${active.length} 个，建议至少保留 1 到 2 个主判断，再把其余改成辅助或移出。`
        : active.length === 2
          ? `当前同组启用了 2 个，建议确认是否都需要继续参与主判断。`
          : active.length === 1
            ? "当前只启用了 1 个，同组没有明显重复。"
            : "当前这一组没有启用，暂时没有重合压力。";
    return {
      ...group,
      active,
      redundancyLevel,
      dedupStatus,
      note: active.length ? `当前启用：${active.join(" / ")}` : `当前未启用 ${group.label}。`,
    };
  });
  const leadingOverlapGroup = overlapGroups.find((item) => item.active.length >= 2) ?? overlapGroups[0];
  const redundancyHeadline = leadingOverlapGroup?.active.length >= 2
    ? `${leadingOverlapGroup.label} 当前最需要去重`
    : "当前没有明显高重合因子组";
  const redundancyDetail = leadingOverlapGroup?.dedupStatus || "先恢复因子协议，再看当前哪些因子组需要去重。";
  const redundancyNextStep = leadingOverlapGroup?.active.length >= 2
    ? `先处理 ${leadingOverlapGroup.label}，再看其他同类因子是不是还要同时保留。`
    : "先确认哪些因子真的需要进入主判断，再决定是否补更多同类因子。";

  const scoreContributors = topWeightedCategories.slice(0, 5).map((item) => ({
    label: item.label,
    weight: item.currentWeight,
    currentMix: item.currentMix,
    effect: item.effect,
  }));
  const scoreHeadline = leadCategory ? `${leadCategory.label} 当前最影响总分` : "当前总分先看统一评分";
  const scoreDetail = `候选篮子总分会先看 ${scoreContributors.slice(0, 3).map((item) => `${item.label}(${item.weight})`).join(" / ") || "当前没有权重摘要"}，执行篮子再用严格惩罚和最低置信度收口。`;
  const scoreExplanation = `主判断 ${workspace.overview.primary_count} 个 / 辅助 ${workspace.overview.auxiliary_count} 个；候选篮子总分会优先反映 ${leadCategory?.label || "当前主导类别"} 的权重，执行篮子继续按严格惩罚和最低置信度收口。`;
  const factorCatalog = workspace.factors.length
    ? workspace.factors
    : selectionMatrixRows.map((item) => ({
        name: item.id,
        category: String(item.cells[1] ?? "未分类"),
        role: String(item.cells[2] ?? "未定义"),
        description: String(item.cells[4] ?? "当前没有说明"),
      }));
  const activeFactorCatalog = factorCatalog.filter((item) => selectedFactorSet.has(item.name));
  const factorDetails: FeatureFactorDetailItem[] = (activeFactorCatalog.length ? activeFactorCatalog : factorCatalog).map((factor) => {
    const categoryKey = normalizeCategoryKey(factor.category);
    const categorySummary = categories.find((item) => item.key === categoryKey);
    const categoryLabel = categorySummary?.label || factor.category || "未分类";
    const currentRole = currentRoleByFactor.get(factor.name) || (selectedFactorSet.has(factor.name) ? "已启用" : "未启用");
    const overlapGroup = overlapGroups.find(
      (item) => item.active.some((entry) => entry === factor.name) || item.factors.some((entry) => entry === factor.name),
    );
    return {
      id: factor.name,
      name: factor.name,
      categoryLabel,
      currentRole,
      description: factor.description || "当前没有说明",
      timeSeries: describeFactorTimeSeries(categoryKey, workspace.controls.timeframe_profiles),
      icSummary: describeFactorIcSummary({
        factorName: factor.name,
        currentRole,
        categoryLabel,
        weightEntry: categorySummary?.weightEntry || "研究页统一评分",
      }),
      bucketSummary: describeFactorBucketSummary({
        factorName: factor.name,
        currentRole,
        effect: categorySummary?.effect || "当前先按统一评分观察。",
      }),
      stabilitySummary: describeFactorStabilitySummary({
        currentRole,
        preprocessingHeadline,
        timeframeSummary,
      }),
      correlationSummary: describeFactorCorrelationSummary({
        factorName: factor.name,
        overlapGroup,
      }),
    };
  });

  const primaryActionLabel = featureStatus === "ready" ? "先确认当前因子协议" : "先恢复因子协议";
  const primaryActionDetail =
    featureStatus === "ready"
      ? "默认首屏不再把因子明细和配置表单直接摊开，先看分类、启用、有效性、冗余和总分解释。"
      : "当前因子协议还没准备好，先恢复特征工作台，再继续看分类、启用和总分解释。";

  const configContent = (
    <div className="space-y-5">
      <DetailSection title="当前因子配置摘要" description="先确认这轮因子协议当前使用了哪套预设、哪些主判断因子和预处理规则。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="当前组合" value={displayValue(selectionStory.headline, "当前还没有因子组合摘要")} />
          <InfoBlock label="当前组合说明" value={displayValue(selectionStory.detail, "当前还没有因子组合说明")} />
          <InfoBlock label="因子预设" value={`${displayValue(selectedFeaturePreset.label, String(workspace.controls.feature_preset_key ?? "balanced_default"))} / ${displayValue(selectedFeaturePreset.fit, "当前没有适用场景说明")}`} />
          <InfoBlock label="预处理摘要" value={preprocessingHeadline} />
          <InfoBlock label="预处理说明" value={preprocessingDetail} />
          <InfoBlock label="周期摘要" value={timeframeSummary} />
        </div>
      </DetailSection>

      <div className="grid gap-5 xl:grid-cols-2">
        <WorkbenchConfigCard
          title="因子预设"
          description="先选一套因子组合预设，再决定要不要继续手动勾选具体因子。"
          scope="features"
          returnTo="/features"
          disabled={!configEditable}
          disabledReason={unavailableConfigReason}
          disabledLabel={disabledSaveLabel}
        >
          <ConfigField label="一键套用" hint="预设会先改主判断、辅助因子和预处理规则，再由下面的细项继续微调。">
            <ConfigSelect
              name="feature_preset_key"
              defaultValue={String(workspace.controls.feature_preset_key ?? "balanced_default")}
              options={availableFeaturePresets.map((item) => ({ value: item, label: item }))}
            />
          </ConfigField>
          <DataTable
            columns={["因子预设", "适用场景", "说明"]}
            rows={featurePresetCatalog.map((item, index) => ({
              id: `${readPlainText(item.key, String(index))}`,
              cells: [
                readPlainText(item.key, "n/a"),
                readPlainText(item.fit, "当前没有适用场景说明"),
                readPlainText(item.detail, "当前没有预设说明"),
              ],
            }))}
            emptyTitle="当前还没有因子预设"
            emptyDetail="恢复工作台后可用"
          />
        </WorkbenchConfigCard>

        <WorkbenchConfigCard
          title="因子组合配置"
          description="这里选的主判断因子和辅助因子，会真正进入研究评分和解释，不只是页面展示。"
          scope="features"
          returnTo="/features"
          disabled={!configEditable}
          disabledReason={unavailableConfigReason}
          disabledLabel={disabledSaveLabel}
        >
          <ConfigField label="按因子类别选择" hint="按类别浏览因子，并在主判断 / 辅助之间批量配置。">
            {categories.some((item) => item.total > 0) ? (
              <div className="space-y-4">
                {categories.map((category) => (
                  <div key={category.key} className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-foreground">{category.label}</p>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">{category.total} 个因子</p>
                    </div>
                    <p className="text-xs leading-5 text-muted-foreground">{category.factors.length ? category.factors.join(" / ") : "当前没有因子"}</p>
                    <div className="grid gap-2 pt-3 md:grid-cols-2">
                      <CategoryCheckboxGroup
                        title="主判断因子"
                        name="primary_factors"
                        factors={category.factors}
                        selected={primaryFactors}
                      />
                      <CategoryCheckboxGroup
                        title="辅助因子"
                        name="auxiliary_factors"
                        factors={category.factors}
                        selected={auxiliaryFactors}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-muted-foreground">当前还没有因子类别。</p>
            )}
          </ConfigField>
        </WorkbenchConfigCard>
      </div>

      <WorkbenchConfigCard
        title="类别权重配置"
        description="这里把趋势、动量、量能、震荡和波动五类因子的权重直接放出来，方便你细调研究偏向。"
        scope="research"
        returnTo="/features"
        disabled={!configEditable}
        disabledReason={unavailableConfigReason}
        disabledLabel={disabledSaveLabel}
      >
        <ConfigField label="类别权重" hint="先决定哪一类因子在研究打分里更重要，再让研究页去承接模板和标签。">
          <div className="grid gap-3 md:grid-cols-2">
            <LabeledConfigInput label="趋势权重" name="trend_weight" defaultValue={String(workspace.controls.trend_weight ?? "1.3")} />
            <LabeledConfigInput label="动量权重" name="momentum_weight" defaultValue={String(workspace.controls.momentum_weight ?? "1")} />
            <LabeledConfigInput label="量能权重" name="volume_weight" defaultValue={String(workspace.controls.volume_weight ?? "1.1")} />
            <LabeledConfigInput label="震荡权重" name="oscillator_weight" defaultValue={String(workspace.controls.oscillator_weight ?? "0.7")} />
            <LabeledConfigInput label="波动权重" name="volatility_weight" defaultValue={String(workspace.controls.volatility_weight ?? "0.9")} />
            <LabeledConfigInput label="严格模板惩罚权重" name="strict_penalty_weight" defaultValue={String(workspace.controls.strict_penalty_weight ?? "1")} />
            <LabeledConfigInput label="最低置信度" name="signal_confidence_floor" defaultValue={String(workspace.controls.signal_confidence_floor ?? "0.55")} />
          </div>
        </ConfigField>
        <ConfigField label="预处理规则" hint="这里改的是因子进入训练前的清洗方式，保存后下一轮训练和推理都会按这里重算。">
          <div className="grid gap-3 md:grid-cols-3">
            <ConfigSelect
              name="missing_policy"
              defaultValue={workspace.controls.missing_policy}
              options={availableMissingPolicies.map((item) => ({
                value: item,
                label: item === "strict_drop" ? "严格丢弃缺失行" : "中性值补齐",
              }))}
            />
            <ConfigSelect
              name="outlier_policy"
              defaultValue={workspace.controls.outlier_policy}
              options={availableOutlierPolicies.map((item) => ({ value: item, label: item }))}
            />
            <ConfigSelect
              name="normalization_policy"
              defaultValue={workspace.controls.normalization_policy}
              options={availableNormalizationPolicies.map((item) => ({ value: item, label: item }))}
            />
          </div>
        </ConfigField>
        <ConfigField label="周期参数" hint="这里可以直接调整 1h 和 4h 的趋势、动量、震荡、量能和突破窗口，让同一组因子更贴近当前节奏。">
          <div className="grid gap-4">
            <TimeframeProfileCard interval="4h" params={workspace.controls.timeframe_profiles["4h"] ?? {}} />
            <TimeframeProfileCard interval="1h" params={workspace.controls.timeframe_profiles["1h"] ?? {}} />
          </div>
        </ConfigField>
      </WorkbenchConfigCard>
    </div>
  );

  const guideContent = (
    <div className="space-y-5">
      <DetailSection title="因子协议说明" description="这里把当前 preset、预处理和周期参数压成一屏说明。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="当前组合" value={displayValue(selectionStory.headline, "当前还没有因子组合摘要")} />
          <InfoBlock label="当前组合说明" value={displayValue(selectionStory.detail, "当前还没有因子组合说明")} />
          <InfoBlock label="预处理摘要" value={preprocessingHeadline} />
          <InfoBlock label="预处理说明" value={preprocessingDetail} />
          <InfoBlock label="周期摘要" value={timeframeSummary} />
          <InfoBlock label="当前状态" value={featureNote} />
        </div>
      </DetailSection>

      <DetailSection title="因子说明" description="这里保留当前因子协议明细和当前选中角色。">
        <DataTable
          columns={["因子明细表", "类别", "协议角色", "当前选中角色", "说明"]}
          rows={selectionMatrixRows}
          emptyTitle="当前还没有因子明细"
          emptyDetail="恢复工作台后可用"
        />
      </DetailSection>

      <DetailSection title="时间序列 / 周期参数" description="时间序列节奏当前先用 1h / 4h 周期参数来解释。">
        <DataTable
          columns={["周期", "参数映射"]}
          rows={timeframeRows}
          emptyTitle="还没有周期参数"
          emptyDetail="当前研究协议还没有写出周期参数映射。"
        />
      </DetailSection>

      <DetailSection title="IC / 分组收益 / 稳定性 / 相关性" description="当前先按协议级摘要解释因子效果，不把完整实验中心搬到因子页。">
        <div className="space-y-4">
          {effectivenessRows.map((row) => (
            <div key={row.key} className="rounded-2xl border border-border/60 bg-muted/10 p-4">
              <p className="eyebrow">{row.label}</p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <InfoBlock label="IC" value={row.icNote} />
                <InfoBlock label="分组收益" value={row.bucketNote} />
                <InfoBlock label="稳定性" value={row.stabilityNote} />
                <InfoBlock
                  label="相关性"
                  value={overlapGroups.find((item) => item.key === row.key)?.dedupStatus || "当前没有明显相关性提示"}
                />
              </div>
            </div>
          ))}
        </div>
      </DetailSection>
    </div>
  );

  const flowContent = (
    <div className="space-y-5">
      <DetailSection title="因子怎么进入候选篮子" description="因子页先决定哪些因子启用、权重怎么配，再交给研究页生成候选篮子。">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoBlock label="当前分类摘要" value={`${activeCategoryCount} 类因子 / ${totalFactorCount} 个因子`} />
          <InfoBlock label="当前启用摘要" value={`主判断 ${workspace.overview.primary_count} 个 / 辅助 ${workspace.overview.auxiliary_count} 个`} />
          <InfoBlock label="当前最重类别" value={scoreHeadline} />
          <InfoBlock label="候选篮子承接" value={scoreExplanation} />
        </div>
      </DetailSection>

      <DetailSection title="下一步去哪" description="因子页只回答协议和打分逻辑，候选篮子由研究页承接，执行篮子由评估页收口。">
        <FeatureFlowLinks
          researchHref={session.isAuthenticated ? "/research" : "/login?next=%2Fresearch"}
          evaluationHref={session.isAuthenticated ? "/evaluation" : "/login?next=%2Fevaluation"}
        />
      </DetailSection>
    </div>
  );

  const focusCards: FeaturesFocusCard[] = [
    {
      id: "category-overview",
      eyebrow: "因子分类",
      title: "因子分类总览",
      summary: "先按六类把因子体系看懂，再决定要不要改具体组合。",
      detail: `${activeCategoryCount} 类已启用 / ${totalFactorCount} 个因子${dominantCategory ? `；当前最密集的是 ${dominantCategory.label}` : ""}`,
      triggerLabel: "查看分类详情",
      drawerTitle: "因子分类详情",
      drawerDescription: "把分类清单、每类当前混合和研究权重入口统一放到这里。",
      drawerContent: (
        <div className="space-y-5">
          <DetailSection title="因子分类清单" description="默认六类都会显式保留，没启用的类别也会保留位置。">
            <DataTable
              columns={["因子分组", "包含因子"]}
              rows={categoryRows}
              emptyTitle="还没有因子分组"
              emptyDetail="先运行一次 Qlib 研究训练，特征协议才会在这里出现。"
            />
          </DetailSection>
          <DetailSection title="分类权重入口" description="这里说明每类因子在研究页里由哪档权重承接。">
            <DataTable
              columns={["因子类别", "当前角色分布", "研究页权重入口", "主要影响什么", "说明"]}
              rows={categoryWeightRows}
              emptyTitle="当前还没有类别权重解释"
              emptyDetail="先生成一轮特征协议，再回来看每个因子类别在研究页里由哪一档权重控制。"
            />
          </DetailSection>
        </div>
      ),
      drawerFooter: "默认首屏只保留分类摘要；完整分类目录和权重入口都从这里展开。",
      digests: [
        { label: "分类数量", value: String(activeCategoryCount), detail: `默认保留 ${totalCategoryCount} 类展示位` },
        { label: "因子总数", value: String(totalFactorCount || workspace.overview.factor_count), detail: "当前协议里纳入的因子数量" },
        { label: "最密集分组", value: dominantCategory ? `${dominantCategory.label} (${dominantCategory.total})` : "当前没有", detail: `平均每组 ${averagePerGroup || 0} 个因子` },
      ],
    },
    {
      id: "enabled-factors",
      eyebrow: "当前启用",
      title: "当前启用因子",
      summary: "这一块直接回答现在有哪些主判断因子、哪些只是辅助确认。",
      detail: `主判断 ${workspace.overview.primary_count} 个 / 辅助 ${workspace.overview.auxiliary_count} 个`,
      triggerLabel: "查看启用详情",
      drawerTitle: "当前启用详情",
      drawerDescription: "主判断、辅助因子和当前组合故事都统一收在这里。",
      drawerContent: (
        <div className="space-y-5">
          <DetailSection title="当前因子选择" description="把这轮因子 preset、预处理规则和周期参数压成一屏。">
            <div className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="当前组合" value={displayValue(selectionStory.headline, "当前还没有因子组合摘要")} />
              <InfoBlock label="当前组合说明" value={displayValue(selectionStory.detail, "当前还没有因子组合说明")} />
              <InfoBlock label="因子预设" value={`${displayValue(selectedFeaturePreset.label, String(workspace.controls.feature_preset_key ?? "balanced_default"))} / ${displayValue(selectedFeaturePreset.fit, "当前没有适用场景说明")}`} />
              <InfoBlock label="预处理摘要" value={preprocessingHeadline} />
              <InfoBlock label="预处理说明" value={preprocessingDetail} />
              <InfoBlock label="周期摘要" value={timeframeSummary} />
            </div>
          </DetailSection>
          <DetailSection title="主判断因子" description="这些因子会直接参与当前研究判断。">
            <InfoBlock label="主判断因子" value={primaryFactors.length ? primaryFactors.join(" / ") : "当前没有主判断因子。"} />
          </DetailSection>
          <DetailSection title="辅助确认因子" description="这些因子只做补充确认，不单独决定推荐。">
            <InfoBlock label="辅助确认因子" value={auxiliaryFactors.length ? auxiliaryFactors.join(" / ") : "当前没有辅助确认因子。"} />
          </DetailSection>
          <DetailSection title="当前选中角色" description="完整因子角色关系从这里回看。">
            <DataTable
              columns={["因子名", "类别", "协议角色", "当前选中角色", "说明"]}
              rows={selectionMatrixRows}
              emptyTitle="当前还没有因子明细"
              emptyDetail="恢复工作台后可用"
            />
          </DetailSection>
        </div>
      ),
      drawerFooter: "默认首屏只回答启用概况；完整角色分配和组合说明都放到这里。",
      digests: [
        { label: "主判断因子", value: String(workspace.overview.primary_count), detail: primaryFactors.length ? primaryFactors.slice(0, 3).join(" / ") : "当前没有主判断因子" },
        { label: "辅助确认因子", value: String(workspace.overview.auxiliary_count), detail: auxiliaryFactors.length ? auxiliaryFactors.slice(0, 3).join(" / ") : "当前没有辅助因子" },
        { label: "当前预设", value: displayValue(selectedFeaturePreset.label, String(workspace.controls.feature_preset_key ?? "balanced_default")), detail: preprocessingHeadline },
      ],
    },
    {
      id: "effectiveness",
      eyebrow: "因子有效性",
      title: "因子有效性摘要",
      summary: "先把哪类因子最该先看、为什么这样配、稳定性来自哪里讲清楚。",
      detail: effectivenessDetail,
      triggerLabel: "查看有效性详情",
      drawerTitle: "因子有效性详情",
      drawerDescription: "把协议级 IC、分组收益和稳定性摘要统一放到这里。",
      drawerContent: (
        <div className="space-y-5">
          <DetailSection title="当前有效性摘要" description="当前先用协议级摘要解释因子效果，不把完整实验中心搬到因子页。">
            <div className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="IC 摘要" value={icStory} />
              <InfoBlock label="分组收益" value={bucketStory} />
              <InfoBlock label="稳定性" value={stabilityStory} />
              <InfoBlock label="当前最强类别" value={effectivenessHeadline} />
            </div>
          </DetailSection>
          <DetailSection title="分类有效性明细" description="按类别看当前混合、权重入口和协议级效果。">
            <DataTable
              columns={["类别", "当前混合", "当前权重", "IC 摘要", "分组收益", "稳定性"]}
              rows={effectivenessRows.map((row) => ({
                id: row.key,
                cells: [row.label, row.currentMix, row.currentWeight, row.icNote, row.bucketNote, row.stabilityNote],
              }))}
              emptyTitle="当前还没有有效性摘要"
              emptyDetail="恢复工作台后可用"
            />
          </DetailSection>
        </div>
      ),
      drawerFooter: "这里解释的是协议级效果；真正候选层面的得分表现继续去研究页和评估页看。",
      digests: [
        { label: "当前最强类别", value: effectivenessHeadline, detail: effectivenessDetail },
        { label: "IC 摘要", value: icStory, detail: "当前按主判断覆盖和权重入口先解释，不把完整 IC 面板直接铺在首屏。" },
        { label: "稳定性", value: stabilityStory, detail: preprocessingDetail },
      ],
    },
    {
      id: "redundancy",
      eyebrow: "因子冗余",
      title: "因子冗余摘要",
      summary: "这里先回答当前哪些同类因子可能过度重合，应该先去重哪里。",
      detail: redundancyDetail,
      triggerLabel: "查看冗余详情",
      drawerTitle: "因子冗余详情",
      drawerDescription: "把高重合组、去重状态和下一步统一收进这里。",
      drawerContent: (
        <div className="space-y-5">
          <DetailSection title="当前冗余摘要" description="先按同组启用情况判断哪一组最需要去重。">
            <div className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="当前最需要处理" value={redundancyHeadline} />
              <InfoBlock label="当前去重状态" value={redundancyDetail} />
              <InfoBlock label="下一步" value={redundancyNextStep} />
            </div>
          </DetailSection>
          <DetailSection title="重合组清单" description="这里显化趋势、动量、震荡、波动和量能里明显相近的一组因子。">
            <DataTable
              columns={["重合组", "当前启用", "重合程度", "去重状态", "说明"]}
              rows={overlapGroups.map((item) => ({
                id: item.key,
                cells: [
                  item.label,
                  item.active.length ? item.active.join(" / ") : "当前未启用",
                  item.redundancyLevel,
                  item.dedupStatus,
                  item.note,
                ],
              }))}
              emptyTitle="当前还没有冗余摘要"
              emptyDetail="恢复工作台后可用"
            />
          </DetailSection>
        </div>
      ),
      drawerFooter: "因子页先把“哪里可能重复了”说清楚；更细的相关矩阵后续再补。",
      digests: [
        { label: "当前最需要处理", value: redundancyHeadline, detail: redundancyDetail },
        { label: "高重合组", value: leadingOverlapGroup?.label || "当前没有", detail: leadingOverlapGroup?.note || "当前没有明显高重合组" },
        { label: "下一步", value: redundancyNextStep, detail: "先把同类高重合因子压下去，再继续调权重。" },
      ],
    },
    {
      id: "score-entry",
      eyebrow: "总分解释",
      title: "总分解释入口",
      summary: "这里不直接给候选篮子或执行篮子排行，而是先解释候选篮子总分会被哪些因子类别拉动。",
      detail: scoreDetail,
      triggerLabel: "查看总分解释",
      drawerTitle: "总分解释详情",
      drawerDescription: "把当前最影响总分的类别、权重顺序和候选/执行篮子承接说明统一收进这里。",
      drawerContent: (
        <div className="space-y-5">
          <DetailSection title="总分解释" description="先说明候选篮子总分现在主要看哪几类因子，再说明为什么。">
            <div className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="当前最影响总分的类别" value={scoreHeadline} />
              <InfoBlock label="当前总分说明" value={scoreDetail} />
              <InfoBlock label="候选/执行承接" value={scoreExplanation} />
            </div>
          </DetailSection>
          <DetailSection title="当前贡献顺序" description="这里按权重和当前启用混合解释总分贡献顺序。">
            <DataTable
              columns={["类别", "当前权重", "当前混合", "主要影响什么"]}
              rows={scoreContributors.map((item, index) => ({
                id: `${item.label}-${index}`,
                cells: [item.label, item.weight, item.currentMix, item.effect],
              }))}
              emptyTitle="当前还没有总分贡献摘要"
              emptyDetail="恢复工作台后可用"
            />
          </DetailSection>
        </div>
      ),
      drawerFooter: "因子页只解释总分来源；候选篮子排行与执行篮子推进继续由研究页、评估页承接。",
      digests: [
        { label: "当前最影响总分的类别", value: scoreHeadline, detail: scoreDetail },
        { label: "权重前三", value: scoreContributors.slice(0, 3).map((item) => `${item.label}(${item.weight})`).join(" / ") || "当前没有", detail: "这里先看顺序，不直接替代候选篮子排行。" },
        { label: "候选/执行承接", value: scoreExplanation, detail: "候选篮子总分进入研究页后会按这套顺序继续承接。" },
      ],
    },
  ];

  return (
    <AppShell
      title="因子工作台"
      subtitle="先看因子分类、当前启用、有效性、冗余和总分解释，细节按需展开。"
      currentPath="/features"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="因子工作台"
        title="先把多因子体系讲清楚，再决定哪些因子值得继续进入研究评分。"
        description="因子页默认不再只是权重配置页，而是先回答五件事：因子怎么分、现在启用了什么、当前有效性如何、哪些地方可能重复、总分主要被谁拉动。"
      />

      <FeaturesPrimaryActionSection
        primaryActionLabel={primaryActionLabel}
        primaryActionDetail={primaryActionDetail}
        featureStatus={featureStatus}
        featureStatusDetail={featureNote}
        categoryHeadline={`${activeCategoryCount} 类已启用`}
        categoryDetail={dominantCategory ? `${dominantCategory.label} 当前最密集` : "当前还没有主导类别"}
        selectionHeadline={`主判断 ${workspace.overview.primary_count} 个 / 辅助 ${workspace.overview.auxiliary_count} 个`}
        selectionDetail={displayValue(selectionStory.detail, "当前还没有因子组合说明")}
        scoreHeadline={scoreHeadline}
        scoreDetail={scoreExplanation}
        configContent={configContent}
        guideContent={guideContent}
        flowContent={flowContent}
        detailAction={(
          <FeaturesFactorDetailDrawer
            items={factorDetails}
            primaryCount={workspace.overview.primary_count}
            auxiliaryCount={workspace.overview.auxiliary_count}
            preprocessingSummary={preprocessingHeadline}
            timeframeSummary={timeframeSummary}
          />
        )}
      />

      <FeaturesFocusGrid cards={focusCards} />
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

/* 渲染抽屉里的细节分组。 */
function DetailSection({ title, description, children }: { title: string; description: string; children: ReactNode }) {
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

/* 把因子类别整理成默认六类摘要。 */
function buildCategoryOverview(
  categories: Record<string, string[]>,
  primaryFactorSet: Set<string>,
  auxiliaryFactorSet: Set<string>,
) {
  return CATEGORY_META.map((meta) => {
    const factors = toStringArray(categories[meta.key] ?? []);
    const primaryCount = factors.filter((factor) => primaryFactorSet.has(factor)).length;
    const auxiliaryCount = factors.filter((factor) => auxiliaryFactorSet.has(factor)).length;
    const description = describeCategoryWeight(meta.key);
    return {
      key: meta.key,
      label: meta.label,
      factors,
      total: factors.length,
      primaryCount,
      auxiliaryCount,
      currentMix: `${primaryCount} 主判断 / ${auxiliaryCount} 辅助 / ${factors.length} 总计`,
      currentWeight: description.currentWeight,
      weightEntry: description.weightEntry,
      effect: description.effect,
      detail: description.detail,
    };
  });
}

/* 读取权重摘要。 */
function buildWeightSummary(controls: Record<string, unknown>) {
  return {
    trend: displayValue(controls.trend_weight, "1.3"),
    momentum: displayValue(controls.momentum_weight, "1"),
    volume: displayValue(controls.volume_weight, "1.1"),
    oscillator: displayValue(controls.oscillator_weight, "0.7"),
    volatility: displayValue(controls.volatility_weight, "0.9"),
    strictPenalty: displayValue(controls.strict_penalty_weight, "1"),
    confidenceFloor: displayValue(controls.signal_confidence_floor, "0.55"),
  };
}

/* 格式化周期参数摘要。 */
function formatProfile(profile: Record<string, unknown>) {
  const items = Object.entries(profile).map(([key, value]) => `${key}=${String(value)}`);
  return items.join(" / ") || "当前没有参数";
}

/* 按类别解释研究权重入口。 */
function describeCategoryWeight(category: string) {
  const name = category.toLowerCase();
  if (name.includes("trend") || category.includes("趋势")) {
    return {
      currentWeight: "1.3",
      weightEntry: "研究页 trend_weight",
      effect: "决定顺势强弱，通常最先影响能不能继续跟随趋势。",
      detail: "重点看均线偏离和趋势方向，更适合先判断是不是仍在主趋势里。",
    };
  }
  if (name.includes("momentum") || category.includes("动量")) {
    return {
      currentWeight: "1",
      weightEntry: "研究页 momentum_weight",
      effect: "决定加速和放缓的分数，影响什么时候追、什么时候收手。",
      detail: "重点看推进速度和短期加速，更适合判断这段走势还有没有继续冲的动力。",
    };
  }
  if (name.includes("volume") || category.includes("量")) {
    return {
      currentWeight: "1.1",
      weightEntry: "研究页 volume_weight",
      effect: "决定量价是否配合，常用来确认突破是不是有真成交支撑。",
      detail: "重点看成交量放大和量价同步，更适合确认突破是不是有真实成交支持。",
    };
  }
  if (name.includes("osc") || name.includes("oscillator") || category.includes("震荡")) {
    return {
      currentWeight: "0.7",
      weightEntry: "研究页 oscillator_weight",
      effect: "决定超买超卖和反转提示，更适合提醒什么时候不要追。",
      detail: "重点看超买超卖和回摆位置，更适合过滤追高或过度回撤时段。",
    };
  }
  if (name.includes("vol") || category.includes("波动")) {
    return {
      currentWeight: "0.9",
      weightEntry: "研究页 volatility_weight",
      effect: "决定波动惩罚和风险折扣，直接影响这轮信号敢不敢放行。",
      detail: "重点看波动幅度和风险压力，更适合在进 dry-run 或 live 前先压掉过度波动。",
    };
  }
  return {
    currentWeight: "1",
    weightEntry: "研究页统一评分",
    effect: "当前先按统一评分处理，后面再继续拆得更细。",
    detail: "这类因子暂时没有单独权重入口，会先按统一评分逻辑参与研究判断。",
  };
}

/* 安全读取对象。 */
function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

/* 安全读取字符串目录。 */
function toStringArray(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

/* 安全读取对象目录。 */
function toRecordArray(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && !Array.isArray(item)));
}

/* 安全读取纯文本，避免直接渲染对象。 */
function readPlainText(value: unknown, fallback: string) {
  const text = String(value ?? "").trim();
  return text || fallback;
}

/* 读取页面文案。 */
function displayValue(value: unknown, fallback: string) {
  const text = String(value ?? "").trim();
  return text || fallback;
}

/* 把字符串权重大致转成数字方便排序。 */
function parseNumeric(value: string) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

/* 渲染带标题的配置输入框，让权重和阈值字段更容易辨认。 */
function LabeledConfigInput({
  label,
  name,
  defaultValue,
}: {
  label: string;
  name: string;
  defaultValue: string;
}) {
  return (
    <label className="grid gap-2 text-sm text-foreground">
      <span>{label}</span>
      <ConfigInput aria-label={label} name={name} defaultValue={defaultValue} placeholder={label} />
    </label>
  );
}

/* 渲染带周期标题的参数卡。 */
function TimeframeProfileCard({ interval, params }: { interval: string; params: Record<string, unknown> }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">{interval} 参数</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <ConfigInput name={`timeframe_profiles.${interval}.trend_window`} defaultValue={String(params.trend_window ?? "")} placeholder="趋势窗口" />
        <ConfigInput name={`timeframe_profiles.${interval}.volume_window`} defaultValue={String(params.volume_window ?? "")} placeholder="量能窗口" />
        <ConfigInput name={`timeframe_profiles.${interval}.atr_period`} defaultValue={String(params.atr_period ?? "")} placeholder="ATR 周期" />
        <ConfigInput name={`timeframe_profiles.${interval}.rsi_period`} defaultValue={String(params.rsi_period ?? "")} placeholder="RSI 周期" />
        <ConfigInput name={`timeframe_profiles.${interval}.roc_period`} defaultValue={String(params.roc_period ?? "")} placeholder="ROC 周期" />
        <ConfigInput name={`timeframe_profiles.${interval}.cci_period`} defaultValue={String(params.cci_period ?? "")} placeholder="CCI 周期" />
        <ConfigInput name={`timeframe_profiles.${interval}.stoch_period`} defaultValue={String(params.stoch_period ?? "")} placeholder="随机指标周期" />
        <ConfigInput name={`timeframe_profiles.${interval}.breakout_lookback`} defaultValue={String(params.breakout_lookback ?? "")} placeholder="突破回看窗口" />
      </div>
    </div>
  );
}

/* 渲染按类别分组的复选配置。 */
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

/* 统一类别名，方便把协议类别映射到页面既定六类。 */
function normalizeCategoryKey(category: string) {
  const value = category.toLowerCase();
  if (value.includes("trend")) {
    return "trend";
  }
  if (value.includes("momentum")) {
    return "momentum";
  }
  if (value.includes("osc") || value.includes("rsi") || value.includes("cci") || value.includes("stoch")) {
    return "oscillator";
  }
  if (value.includes("volume")) {
    return "volume";
  }
  if (value.includes("volatility") || value.includes("atr")) {
    return "volatility";
  }
  return "extension";
}

/* 按因子类别抽取最相关的周期参数，压成一行时间序列说明。 */
function describeFactorTimeSeries(categoryKey: string, timeframeProfiles: Record<string, Record<string, unknown>>) {
  const relevantKeys = pickTimeframeKeys(categoryKey);
  const parts = Object.entries(timeframeProfiles)
    .map(([interval, profile]) => {
      const entries = relevantKeys
        .filter((key) => key in profile)
        .map((key) => `${key}=${String(profile[key] ?? "")}`)
        .filter((item) => !item.endsWith("="));
      const fallbackEntries = entries.length ? entries : Object.entries(profile).slice(0, 2).map(([key, value]) => `${key}=${String(value)}`);
      return fallbackEntries.length ? `${interval}: ${fallbackEntries.join(" / ")}` : "";
    })
    .filter(Boolean);
  return parts.join("；") || "当前没有周期参数。";
}

/* 读取不同类别最该看的时间序列参数。 */
function pickTimeframeKeys(categoryKey: string) {
  if (categoryKey === "trend") {
    return ["trend_window", "ema_fast", "ema_slow"];
  }
  if (categoryKey === "momentum") {
    return ["roc_period", "breakout_lookback", "trend_window"];
  }
  if (categoryKey === "oscillator") {
    return ["rsi_period", "cci_period", "stoch_period"];
  }
  if (categoryKey === "volume") {
    return ["volume_window"];
  }
  if (categoryKey === "volatility") {
    return ["atr_period"];
  }
  return ["trend_window", "volume_window"];
}

/* 生成单因子的 IC 说明。 */
function describeFactorIcSummary({
  factorName,
  currentRole,
  categoryLabel,
  weightEntry,
}: {
  factorName: string;
  currentRole: string;
  categoryLabel: string;
  weightEntry: string;
}) {
  if (currentRole === "主判断") {
    return `${factorName} 当前直接进入主判断，先看 ${categoryLabel} 在 ${weightEntry} 下对排序的拉动。`;
  }
  if (currentRole === "辅助确认") {
    return `${factorName} 当前只做辅助确认，IC 先作为旁证，不单独决定候选排序。`;
  }
  return `${factorName} 当前未启用，先不进入这轮 IC 观察。`;
}

/* 生成单因子的分组收益说明。 */
function describeFactorBucketSummary({
  factorName,
  currentRole,
  effect,
}: {
  factorName: string;
  currentRole: string;
  effect: string;
}) {
  if (currentRole === "未启用") {
    return `${factorName} 还没进入当前候选篮子，分组收益先不参与比较。`;
  }
  return `${factorName} 当前沿用所属类别口径：${effect}`;
}

/* 生成单因子的稳定性说明。 */
function describeFactorStabilitySummary({
  currentRole,
  preprocessingHeadline,
  timeframeSummary,
}: {
  currentRole: string;
  preprocessingHeadline: string;
  timeframeSummary: string;
}) {
  const rolePrefix = currentRole === "主判断" ? "主判断优先看稳定延续" : currentRole === "辅助确认" ? "辅助因子优先看口径一致" : "未启用因子暂不进入当前稳定性判断";
  return `${rolePrefix}；${preprocessingHeadline}；${timeframeSummary}`;
}

/* 生成单因子的相关性说明。 */
function describeFactorCorrelationSummary({
  factorName,
  overlapGroup,
}: {
  factorName: string;
  overlapGroup?: (typeof REDUNDANCY_GROUPS)[number] & {
    active: string[];
    redundancyLevel: string;
    dedupStatus: string;
    note: string;
  };
}) {
  if (!overlapGroup) {
    return `${factorName} 当前没有识别到明显高重合组。`;
  }
  const siblingFactors = overlapGroup.active.filter((item) => item !== factorName);
  if (siblingFactors.length) {
    return `${factorName} 属于 ${overlapGroup.label}，当前与 ${siblingFactors.join(" / ")} 同组，${overlapGroup.dedupStatus}`;
  }
  return `${factorName} 属于 ${overlapGroup.label}，${overlapGroup.note}`;
}
