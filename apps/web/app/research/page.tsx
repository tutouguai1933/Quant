/**
 * 模型训练页面
 * 复刻参考图 5 的终端化布局
 * 左侧：训练配置参数栏
 * 右侧：指标卡、特征重要度、IC 图表、模型信息 JSON
 */
"use client";

import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";

import {
  TerminalShell,
  ControlPanel,
  FieldRow,
  TerminalInput,
  TerminalSelect,
  SegmentedControl,
  ChipList,
  MetricStrip,
  IcBarChart,
  FeatureImportanceChart,
  ModelJsonPanel,
} from "../../components/terminal";
import { readFeedback } from "../../lib/feedback";
import {
  getResearchWorkspace,
  getResearchWorkspaceFallback,
  getResearchRuntimeStatus,
  getResearchRuntimeStatusFallback,
  getFeatureWorkspace,
  getFeatureWorkspaceFallback,
  type ResearchWorkspaceModel,
  type ResearchRuntimeStatusModel,
  type FeatureWorkspaceModel,
} from "../../lib/api";
import { FeedbackBanner } from "../../components/feedback-banner";
import { LoadingBanner } from "../../components/loading-banner";
import { ErrorBanner } from "../../components/error-banner";

/* 模型标签映射 */
const MODEL_LABELS: Record<string, string> = {
  heuristic_v1: "heuristic_v1 · 基础启发式",
  trend_bias_v2: "trend_bias_v2 · 趋势偏置",
  balanced_v3: "balanced_v3 · 平衡评分",
  momentum_drive_v4: "momentum_drive_v4 · 动量推进",
  stability_guard_v5: "stability_guard_v5 · 稳定守门",
};

/* 标签模式映射 */
const LABEL_MODE_LABELS: Record<string, string> = {
  earliest_hit: "earliest_hit · 最早命中",
  close_only: "close_only · 只看窗口结束",
  window_majority: "window_majority · 多数窗口表决",
};

/* 时间区间快捷选项 */
const QUICK_DATE_RANGES = [
  { value: "1m", label: "近1月" },
  { value: "3m", label: "近3月" },
  { value: "1y", label: "近1年" },
  { value: "3y", label: "近3年" },
  { value: "5y", label: "近5年" },
  { value: "ytd", label: "YTD" },
];

/* 模型后端选项 */
const MODEL_BACKENDS = [
  { value: "lgbm", label: "lgbm" },
  { value: "mlp", label: "mlp" },
  { value: "lstm", label: "lstm" },
  { value: "transformer", label: "transformer" },
];

/* 损失函数选项 */
const LOSS_FUNCTIONS = [
  { value: "mse", label: "mse" },
  { value: "ic", label: "ic" },
];

/* 标签类型选项 */
const LABEL_TYPES = [
  { value: "raw", label: "raw" },
  { value: "rank", label: "rank" },
  { value: "alpha", label: "alpha" },
];

/* 页面主组件 */
export default function ResearchPage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  // 状态管理
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [workspace, setWorkspace] = useState<ResearchWorkspaceModel>(getResearchWorkspaceFallback());
  const [runtimeStatus, setRuntimeStatus] = useState<ResearchRuntimeStatusModel>(getResearchRuntimeStatusFallback());
  const [featureWorkspace, setFeatureWorkspace] = useState<FeatureWorkspaceModel>(getFeatureWorkspaceFallback());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 表单状态
  const [modelId, setModelId] = useState("");
  const [selectedDateRange, setSelectedDateRange] = useState("5y");
  const [modelBackend, setModelBackend] = useState("lgbm");
  const [lossFunction, setLossFunction] = useState("mse");
  const [labelType, setLabelType] = useState("rank");
  const [forward, setForward] = useState("5");
  const [trees, setTrees] = useState("200");
  const [learningRate, setLearningRate] = useState("0.05");
  const [selectedFactors, setSelectedFactors] = useState<string[]>([]);

  // 获取会话状态
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
        // 保持默认会话状态
      });
  }, []);

  // 获取工作区数据
  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    Promise.allSettled([
      getResearchWorkspace(controller.signal),
      getResearchRuntimeStatus(controller.signal),
      getFeatureWorkspace(controller.signal),
    ])
      .then(([workspaceRes, runtimeRes, featureRes]) => {
        clearTimeout(timeoutId);

        if (workspaceRes.status === "fulfilled" && !workspaceRes.value.error) {
          setWorkspace(workspaceRes.value.data.item);
          // 初始化表单状态
          const ws = workspaceRes.value.data.item;
          setModelId(ws.model.model_version || ws.controls.model_key || "lgbm_v1");
          setLabelType(ws.labeling.label_mode || "rank");
        }
        if (runtimeRes.status === "fulfilled" && !runtimeRes.value.error) {
          setRuntimeStatus(runtimeRes.value.data.item);
        }
        if (featureRes.status === "fulfilled" && !featureRes.value.error) {
          setFeatureWorkspace(featureRes.value.data.item);
          // 初始化选中因子
          const fw = featureRes.value.data.item;
          setSelectedFactors(fw.controls.primary_factors || []);
        }

        setIsLoading(false);
      })
      .catch((err) => {
        clearTimeout(timeoutId);
        if (err.name !== "AbortError") {
          setError("网络请求失败，请检查网络连接");
        }
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  // 构建因子 chip 列表
  const factorChips = useMemo(() => {
    const allFactors = [
      ...(featureWorkspace.controls.available_primary_factors || []),
      ...(featureWorkspace.controls.available_auxiliary_factors || []),
    ];
    return allFactors.map((factor) => ({
      label: factor,
      value: factor,
      active: selectedFactors.includes(factor),
      type: factor.includes("ml") ? ("ml" as const) : ("default" as const),
    }));
  }, [featureWorkspace, selectedFactors]);

  // 处理因子选择
  const handleFactorChange = (value: string) => {
    setSelectedFactors((prev) =>
      prev.includes(value) ? prev.filter((f) => f !== value) : [...prev, value]
    );
  };

  // 构建指标卡数据
  const metrics = useMemo(() => {
    const sampleWindow = workspace.sample_window || {};
    const trainSample = (sampleWindow.training as Record<string, unknown>) || {};
    const testSample = (sampleWindow.test as Record<string, unknown>) || {};

    return [
      {
        label: "R² (train)",
        value: "--",
        colorType: "neutral" as const,
      },
      {
        label: "R² (test)",
        value: "--",
        colorType: "neutral" as const,
      },
      {
        label: "IC (train)",
        value: "--",
        colorType: "neutral" as const,
      },
      {
        label: "IC (test)",
        value: "--",
        colorType: "neutral" as const,
      },
      {
        label: "训练样本",
        value: String(trainSample.count || "--"),
        colorType: "neutral" as const,
      },
      {
        label: "测试样本",
        value: String(testSample.count || "--"),
        colorType: "neutral" as const,
      },
      {
        label: "标签类型",
        value: labelType,
        colorType: "neutral" as const,
      },
    ];
  }, [workspace, labelType]);

  // 构建特征重要度数据（使用权重作为配置权重展示）
  const featureImportanceData = useMemo(() => {
    const weights: Record<string, string> = {
      trend_weight: featureWorkspace.controls.trend_weight,
      momentum_weight: featureWorkspace.controls.momentum_weight,
      volume_weight: featureWorkspace.controls.volume_weight,
      oscillator_weight: featureWorkspace.controls.oscillator_weight,
      volatility_weight: featureWorkspace.controls.volatility_weight,
    };

    return Object.entries(weights).map(([name, value]) => ({
      feature: name.replace("_weight", ""),
      importance: parseFloat(value) || 0,
    }));
  }, [featureWorkspace]);

  // 构建模型信息 JSON
  const modelInfoJson = useMemo(() => {
    return {
      model_id: modelId || "lgbm_v1",
      universe: workspace.candidate_scope?.candidate_symbols?.slice(0, 10) || [],
      factors: selectedFactors.length > 0 ? selectedFactors : ["mom_5", "mom_20", "vol_20", "rsi_14"],
      beg: "20220101",
      end: "20241231",
      label_horizon: parseInt(forward) || 5,
      label_type: labelType,
      n_estimators: parseInt(trees) || 200,
      learning_rate: parseFloat(learningRate) || 0.05,
    };
  }, [workspace, modelId, selectedFactors, forward, labelType, trees, learningRate]);

  return (
    <TerminalShell
      breadcrumb="研究 / 模型训练"
      title="模型训练"
      subtitle="LightGBM 因子模型训练与产物管理"
      currentPath="/research"
      isAuthenticated={session.isAuthenticated}
    >
      {/* 反馈横幅 */}
      <FeedbackBanner feedback={feedback} />

      {/* 加载状态 */}
      {isLoading && <LoadingBanner />}

      {/* 错误提示 */}
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* 主布局：左侧参数栏 + 右侧内容 */}
      <div className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        {/* 左侧：训练配置 */}
        <div className="space-y-4">
          {/* 训练配置面板 */}
          <ControlPanel title="训练配置">
            {/* Model ID */}
            <FieldRow label="Model ID">
              <TerminalInput
                value={modelId}
                onChange={setModelId}
                placeholder="lgbm_v1"
              />
            </FieldRow>

            {/* 币种池 */}
            <FieldRow label="币种池">
              <TerminalSelect
                value={workspace.candidate_scope?.candidate_pool_preset_key || "top10_liquid"}
                onChange={() => {}}
                options={[
                  { value: "top10_liquid", label: "top10_liquid — 主流币前10 (10)" },
                  { value: "research_candidates", label: "research_candidates — 研究候选 (16)" },
                ]}
              />
            </FieldRow>

            {/* 时间区间快捷 */}
            <FieldRow label="时间区间">
              <SegmentedControl
                value={selectedDateRange}
                onChange={setSelectedDateRange}
                options={QUICK_DATE_RANGES}
                size="small"
              />
            </FieldRow>

            {/* 开始/结束日期 */}
            <div className="grid grid-cols-2 gap-2">
              <FieldRow label="开始日期">
                <TerminalInput
                  value="2022/01/01"
                  onChange={() => {}}
                  type="date"
                />
              </FieldRow>
              <FieldRow label="结束日期">
                <TerminalInput
                  value="2024/12/31"
                  onChange={() => {}}
                  type="date"
                />
              </FieldRow>
            </div>

            {/* 模型后端 */}
            <FieldRow label="模型后端">
              <SegmentedControl
                value={modelBackend}
                onChange={setModelBackend}
                options={MODEL_BACKENDS}
                size="small"
              />
            </FieldRow>

            {/* 损失函数 */}
            <FieldRow label="损失函数">
              <SegmentedControl
                value={lossFunction}
                onChange={setLossFunction}
                options={LOSS_FUNCTIONS}
                size="small"
              />
            </FieldRow>

            {/* 标签类型 */}
            <FieldRow label="标签类型">
              <SegmentedControl
                value={labelType}
                onChange={setLabelType}
                options={LABEL_TYPES}
                size="small"
              />
            </FieldRow>

            {/* Forward / Trees / LR */}
            <div className="grid grid-cols-3 gap-2">
              <FieldRow label="Forward">
                <TerminalInput
                  value={forward}
                  onChange={setForward}
                  placeholder="5"
                  type="number"
                />
              </FieldRow>
              <FieldRow label="Trees">
                <TerminalInput
                  value={trees}
                  onChange={setTrees}
                  placeholder="200"
                  type="number"
                />
              </FieldRow>
              <FieldRow label="LR">
                <TerminalInput
                  value={learningRate}
                  onChange={setLearningRate}
                  placeholder="0.05"
                  type="number"
                />
              </FieldRow>
            </div>

            {/* 训练按钮 */}
            <div className="pt-2">
              <button
                type="button"
                className="terminal-btn w-full"
                disabled={!session.isAuthenticated}
              >
                训练模型
              </button>
            </div>
          </ControlPanel>

          {/* 因子选择面板 */}
          <ControlPanel title={`因子 (${selectedFactors.length})`}>
            <ChipList
              items={factorChips}
              onChange={handleFactorChange}
              multiSelect
            />
          </ControlPanel>
        </div>

        {/* 右侧：指标和图表 */}
        <div className="space-y-4">
          {/* 指标卡 */}
          <MetricStrip metrics={metrics} />

          {/* 特征重要度 */}
          <FeatureImportanceChart
            data={featureImportanceData}
            height={240}
            isConfigWeight
          />

          {/* IC 图表 */}
          <IcBarChart
            data={[]} // 后端暂无真实 IC 序列，显示空状态
            height={280}
          />

          {/* 模型信息 JSON */}
          <ModelJsonPanel
            data={modelInfoJson}
            title="模型信息"
          />
        </div>
      </div>
    </TerminalShell>
  );
}
