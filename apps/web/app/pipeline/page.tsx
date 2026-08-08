/**
 * 研究流水线页面
 * 新手友好：一个页面从上到下走完 训练→因子→选币 三步骤
 * 每步一张卡片：运行按钮 + 结果指标 + 数据说明（一句话解释数字含义）
 * 复用研究/因子/选币三个工作区接口和现有触发接口，不重写数据层
 */
"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";

import {
  TerminalShell,
  MetricStrip,
} from "../../components/terminal";
import { LoadingBanner } from "../../components/loading-banner";
import { ErrorBanner } from "../../components/error-banner";
import {
  getResearchWorkspace,
  getFeatureWorkspace,
  getEvaluationWorkspace,
  getResearchRuntimeStatus,
  runResearchTraining,
  runResearchInference,
  runQlibPipeline,
  isTechnicalError,
  type ResearchWorkspaceModel,
  type FeatureWorkspaceModel,
  type EvaluationWorkspaceModel,
} from "../../lib/api";
import { readFeedback } from "../../lib/feedback";
import { FeedbackBanner } from "../../components/feedback-banner";

/* 等待工具函数 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/* 步骤编号与文案 */
const STEPS = [
  { number: "①", key: 1, title: "训练模型", hint: "给模型喂历史行情，让它学会预测涨跌。" },
  { number: "②", key: 2, title: "因子研究", hint: "检查哪些信号（因子）真的能预测行情。" },
  { number: "③", key: 3, title: "选币回测", hint: "按预测排序选币，回放验证组合赚不赚钱。" },
] as const;

/* 等待后台任务完成的轮询参数 */
const POLL_INTERVAL_MS = 10000;
const POLL_MAX_ROUNDS = 9;

/* 页面主组件 */
export default function PipelinePage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  // 会话状态
  const [session, setSession] = useState<{ isAuthenticated: boolean }>({ isAuthenticated: false });
  // 三个工作区数据
  const [researchWorkspace, setResearchWorkspace] = useState<ResearchWorkspaceModel | null>(null);
  const [featureWorkspace, setFeatureWorkspace] = useState<FeatureWorkspaceModel | null>(null);
  const [evaluationWorkspace, setEvaluationWorkspace] = useState<EvaluationWorkspaceModel | null>(null);
  // 各步骤降级/错误提示与运行状态
  const [stepDegraded, setStepDegraded] = useState<Record<number, boolean>>({});
  const [stepMessage, setStepMessage] = useState<Record<number, string>>({});
  const [runningStep, setRunningStep] = useState<number | null>(null);
  // 长任务超时后保持"等待中"：运行中禁用所有按钮，等待态显示"刷新查看"
  const [waitingStep, setWaitingStep] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 最新数据镜像（供轮询循环读取，避免闭包拿到旧值）
  const researchWsRef = useRef<ResearchWorkspaceModel | null>(null);
  const featureWsRef = useRef<FeatureWorkspaceModel | null>(null);
  const evaluationWsRef = useRef<EvaluationWorkspaceModel | null>(null);

  // 获取会话状态
  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => setSession({ isAuthenticated: Boolean(data.isAuthenticated) }))
      .catch(() => {});
  }, []);

  // 刷新三个工作区数据（降级时标记对应步骤）
  const refreshAll = useCallback(async () => {
    const [r1, r2, r3] = await Promise.allSettled([
      getResearchWorkspace(),
      getFeatureWorkspace(),
      getEvaluationWorkspace(),
    ]);

    const nextDegraded: Record<number, boolean> = {};
    if (r1.status === "fulfilled") {
      if (r1.value.error && isTechnicalError(r1.value.error)) nextDegraded[1] = true;
      if (!r1.value.error) {
        researchWsRef.current = r1.value.data.item;
        setResearchWorkspace(r1.value.data.item);
      }
    }
    if (r2.status === "fulfilled") {
      if (r2.value.error && isTechnicalError(r2.value.error)) nextDegraded[2] = true;
      if (!r2.value.error) {
        featureWsRef.current = r2.value.data.item;
        setFeatureWorkspace(r2.value.data.item);
      }
    }
    if (r3.status === "fulfilled") {
      if (r3.value.error && isTechnicalError(r3.value.error)) nextDegraded[3] = true;
      if (!r3.value.error) {
        evaluationWsRef.current = r3.value.data.item;
        setEvaluationWorkspace(r3.value.data.item);
      }
    }
    setStepDegraded(nextDegraded);
  }, []);

  // 首次加载数据
  useEffect(() => {
    refreshAll().finally(() => setIsLoading(false));
  }, [refreshAll]);

  /* ---- 各步骤指标提取 ---- */

  // 第一步：训练样本数 / 训练AUC / 验证AUC
  const step1Metrics = (() => {
    const sampleWindow = (researchWorkspace?.sample_window || {}) as Record<string, Record<string, unknown>>;
    const training = sampleWindow.training || {};
    const count = training.count != null ? String(training.count) : "--";
    const trainAuc = researchWorkspace?.model?.train_auc;
    const valAuc = researchWorkspace?.model?.val_auc;
    return [
      { label: "训练样本", value: count, colorType: "neutral" as const },
      { label: "训练 AUC", value: trainAuc != null ? Number(trainAuc).toFixed(3) : "--", colorType: "neutral" as const },
      { label: "验证 AUC", value: valAuc != null ? Number(valAuc).toFixed(3) : "--", colorType: "neutral" as const },
    ];
  })();

  // 第二步：平均IC / IC胜率 / ICIR（来自因子工作区）
  const step2Metrics = (() => {
    const metrics = featureWorkspace?.terminal?.research?.metrics || [];
    const getMetric = (key: string): string => metrics.find((m) => m.key === key)?.value || "--";
    return [
      { label: "平均 IC", value: getMetric("mean_ic"), colorType: "neutral" as const },
      { label: "IC 胜率", value: getMetric("ic_win_rate"), colorType: "neutral" as const },
      { label: "ICIR", value: getMetric("icir"), colorType: "neutral" as const },
    ];
  })();

  // 第三步：最佳净收益 / 年化 / Sharpe / 最大回撤 + 候选数
  const step3Metrics = (() => {
    const metrics = evaluationWorkspace?.terminal?.metrics || [];
    const getMetric = (key: string): string => metrics.find((m) => m.key === key)?.value || "--";
    return [
      { label: "最佳净收益", value: getMetric("best_net_return_pct"), colorType: "neutral" as const },
      { label: "年化", value: getMetric("annual_return_pct"), colorType: "neutral" as const },
      { label: "Sharpe", value: getMetric("sharpe"), colorType: "neutral" as const },
      { label: "最大回撤", value: getMetric("best_max_drawdown_pct"), colorType: "neutral" as const },
    ];
  })();

  /* ---- 步骤完成状态（用于顶部进度指引） ---- */
  const stepDone = {
    1: (researchWorkspace?.model?.model_version ?? "") !== "",
    2: featureWorkspace?.terminal?.research?.metrics?.length ? true : false,
    3: evaluationWorkspace?.terminal?.metrics?.length ? true : false,
  } as Record<number, boolean>;

  // 从最新镜像（ref）计算签名，轮询循环里始终读到最新值
  const readStepSignature = (step: number): string => {
    if (step === 1) {
      const ws = researchWsRef.current;
      return `${ws?.model?.model_version ?? ""}|${ws?.model?.train_auc ?? ""}|${ws?.model?.val_auc ?? ""}`;
    }
    if (step === 2) {
      const metrics = featureWsRef.current?.terminal?.research?.metrics || [];
      return metrics.map((m) => m.value).join("|");
    }
    const metrics = evaluationWsRef.current?.terminal?.metrics || [];
    return metrics.map((m) => m.value).join("|") + `|${evaluationWsRef.current?.candidate_scope?.candidate_symbols?.length ?? 0}`;
  };

  // 触发后台任务并轮询刷新，直到该步骤数据变化或后台任务完成（runtime finished_at 变化）
  const runStep = async (step: number, trigger: () => Promise<unknown>) => {
    if (runningStep !== null || !session.isAuthenticated) return;
    setRunningStep(step);
    setWaitingStep(null);
    setStepMessage((prev) => ({ ...prev, [step]: "正在启动后台任务..." }));
    const beforeSignature = readStepSignature(step);
    const runtimeBefore = await getResearchRuntimeStatus().then((r) => r.error ? null : r.data.item.finished_at).catch(() => null);

    const res = (await trigger()) as { error?: { message?: string } | null } | undefined;
    const err = res && "error" in res ? res.error : null;
    if (err) {
      setStepMessage((prev) => ({ ...prev, [step]: `启动失败：${err.message ?? "未知错误"}` }));
      setRunningStep(null);
      return;
    }

    setStepMessage((prev) => ({ ...prev, [step]: "任务已在后台运行，正在等待结果（训练约 30 分钟，请耐心等待，不要重复点击）..." }));
    let changed = false;
    for (let round = 0; round < POLL_MAX_ROUNDS; round++) {
      await sleep(POLL_INTERVAL_MS);
      await refreshAll();
      // 数据签名变化或后台任务出现新的完成时间，都视为已完成
      const signatureChanged = readStepSignature(step) !== beforeSignature;
      const runtimeNow = await getResearchRuntimeStatus().then((r) => (r.error ? null : r.data.item.finished_at)).catch(() => null);
      if (signatureChanged || (runtimeNow && runtimeBefore !== null && runtimeNow !== runtimeBefore)) {
        changed = true;
        break;
      }
    }
    if (changed) {
      setStepMessage((prev) => ({ ...prev, [step]: "✓ 完成，结果已更新。" }));
      setRunningStep(null);
    } else {
      // 长任务（训练约30分钟）超出轮询窗口：保持"运行中"状态防重复点击，
      // 提供"刷新查看"按钮，后台完成后数据会自动更新
      setStepMessage((prev) => ({
        ...prev,
        [step]: "任务仍在后台运行（训练可能需要 30 分钟），点击「刷新查看」可随时查看最新进度。",
      }));
      setWaitingStep(step);
    }
  };

  // 手动刷新当前步骤结果（长任务轮询超时后使用）
  const refreshStep = async (step: number) => {
    setStepMessage((prev) => ({ ...prev, [step]: "正在刷新..." }));
    await refreshAll();
    const runtime = await getResearchRuntimeStatus().then((r) => (r.error ? null : r.data.item)).catch(() => null);
    if (runtime && runtime.status !== "running") {
      setStepMessage((prev) => ({ ...prev, [step]: "✓ 任务已完成，结果已更新。" }));
      setRunningStep(null);
      setWaitingStep(null);
    } else {
      setStepMessage((prev) => ({ ...prev, [step]: "任务仍在后台运行，请稍后再试。" }));
    }
  };

  /* 各步骤运行按钮 */
  const handleRunTraining = () => runStep(1, () => runResearchTraining("pipeline"));
  const handleRunFeatures = () => runStep(2, () => runResearchInference("pipeline"));
  const handleRunEvaluation = () => runStep(3, () => runQlibPipeline("qlib"));

  /* 通用步骤卡片渲染 */
  const renderStepCard = (
    step: (typeof STEPS)[number],
    metrics: Array<{ label: string; value: string | number | null | undefined; colorType?: "positive" | "negative" | "neutral" }>,
    explanation: string,
    runLabel: string,
    onRun: () => void,
  ) => {
    const running = runningStep === step.key;
    const waiting = waitingStep === step.key;
    const disabled = (runningStep !== null && !running) || waiting;
    const done = stepDone[step.key];
    const degraded = stepDegraded[step.key];
    const message = stepMessage[step.key];

    return (
      <div className="relative pl-6 sm:pl-8">
        {/* 步骤间连线（视觉引导） */}
        <div className="absolute left-0 top-2 bottom-0 w-px bg-[var(--terminal-border)]" aria-hidden />
        <div className="absolute left-[-4px] top-2 size-2 rounded-full bg-[var(--terminal-cyan)]" aria-hidden />

        <div className="terminal-card p-4 sm:p-5">
          {/* 卡片头：步骤编号 + 标题 + 状态 */}
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <span className="text-[var(--terminal-cyan)] text-lg">{step.number}</span>
            <h3 className="text-[15px] font-bold text-[var(--terminal-text)]">{step.title}</h3>
            {done && (
              <span className="text-[11px] text-green-400 bg-green-500/10 border border-green-500/30 rounded px-2 py-0.5">
                ✓ 已有数据
              </span>
            )}
            {(running || waiting) && (
              <span className="text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-0.5 animate-pulse">
                {running ? "运行中..." : "等待完成..."}
              </span>
            )}
            <span className="ml-auto text-[12px] text-[var(--terminal-dim)]">{step.hint}</span>
          </div>

          {/* 降级提示 */}
          {degraded && (
            <ErrorBanner
              tone="warning"
              message="数据暂不可用，可能后端正在重启，请稍后刷新或重新登录后重试。"
            />
          )}

          {/* 指标 */}
          <MetricStrip metrics={metrics} />

          {/* 数据说明（新手向一句话） */}
          <p className="mt-4 text-[12px] text-[var(--terminal-muted)] leading-relaxed">
            💡 {explanation}
          </p>

          {/* 运行按钮 + 状态消息 */}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {waiting ? (
              <button
                type="button"
                className="terminal-btn"
                disabled={!session.isAuthenticated}
                onClick={() => refreshStep(step.key)}
              >
                刷新查看
              </button>
            ) : (
              <button
                type="button"
                className="terminal-btn"
                disabled={!session.isAuthenticated || disabled}
                onClick={onRun}
              >
                {running ? "运行中..." : runLabel}
              </button>
            )}
            {message && (
              <span className={`text-[12px] ${running || waiting ? "text-amber-400" : "text-[var(--terminal-muted)]"}`}>
                {message}
              </span>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <TerminalShell
      breadcrumb="研究 / 研究流水线"
      title="研究流水线"
      subtitle="训练 → 因子 → 选币，一条链路完成研究"
      currentPath="/pipeline"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      {isLoading && <LoadingBanner />}

      {/* 顶部进度指引 */}
      <div className="terminal-card p-4 mb-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {STEPS.map((step) => (
            <div key={step.key} className="flex items-center gap-2 text-[13px]">
              <span className="text-[var(--terminal-cyan)]">{step.number}</span>
              <span className="text-[var(--terminal-text)]">{step.title}</span>
              <span className={`text-[11px] ${stepDone[step.key] ? "text-green-400" : "text-[var(--terminal-dim)]"}`}>
                {stepDone[step.key] ? "已完成" : "待运行"}
              </span>
              {step.key < 3 && <span className="text-[var(--terminal-dim)] ml-2">→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* 三个步骤卡片（垂直排列） */}
      <div className="space-y-4">
        {renderStepCard(
          STEPS[0],
          step1Metrics,
          "AUC 越接近 1，说明模型区分涨跌的能力越强；0.5 约等于瞎猜。点击「运行训练」开始训练。首次全量训练约需 30 分钟（365 天数据），期间请勿重复点击。",
          "运行训练",
          handleRunTraining,
        )}
        {renderStepCard(
          STEPS[1],
          step2Metrics,
          "IC 大于 0 说明因子有效（越大越好），一般 IC > 0.05 就算不错；胜率表示因子在多长时间内方向正确。",
          "运行因子分析",
          handleRunFeatures,
        )}
        {renderStepCard(
          STEPS[2],
          step3Metrics,
          "净收益为正说明组合能赚钱；Sharpe 越高收益越稳；最大回撤越小越抗跌。候选数与回测结果在下方汇总显示。",
          "运行选币回测",
          handleRunEvaluation,
        )}
      </div>

      {/* 第三步附加：候选数统计 */}
      <div className="terminal-card p-4 mt-4">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2 text-[13px]">
          <span className="text-[var(--terminal-dim)]">当前候选数</span>
          <span className="text-[var(--terminal-text)] font-mono">
            {evaluationWorkspace?.candidate_scope?.candidate_symbols?.length ?? 0} 个
          </span>
          <span className="text-[var(--terminal-dim)]">可进 dry-run</span>
          <span className="text-[var(--terminal-text)] font-mono">
            {evaluationWorkspace?.candidate_scope?.live_allowed_symbols?.length ?? 0} 个
          </span>
          <span className="text-[12px] text-[var(--terminal-muted)]">
            选币结果由「训练 + 推理」自动产出，点击「运行选币回测」会重新跑一遍完整研究链路刷新结果。
          </span>
        </div>
      </div>
    </TerminalShell>
  );
}
