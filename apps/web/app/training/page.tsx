/**
 * 模型训练页面
 * 展示 ML 训练结果、训练曲线、特征重要性
 */
"use client";

import { useEffect, useState, useCallback } from "react";
import { Brain, Clock, TrendingUp, BarChart3, RefreshCw, AlertTriangle } from "lucide-react";

import {
  TerminalShell,
  TerminalCard,
  MetricStrip,
  InfoBlock,
} from "../../components/terminal";
import { TrainingCurveChart } from "../../components/charts/training-curve-chart";
import { FeatureImportanceChart } from "../../components/charts/feature-importance-chart";
import { Skeleton } from "../../components/ui/skeleton";
import { Button } from "../../components/ui/button";
import {
  getMLTrainingResult,
  getMLHyperoptStatus,
  type MLTrainingResult,
  type MLHyperoptProgress,
} from "../../lib/api";

export default function TrainingPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [trainingResult, setTrainingResult] = useState<MLTrainingResult | null>(null);
  const [hyperoptStatus, setHyperoptStatus] = useState<MLHyperoptProgress | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setIsAuthenticated(Boolean(data.isAuthenticated));
      })
      .catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [trainingRes, hyperoptRes] = await Promise.all([
        getMLTrainingResult(),
        getMLHyperoptStatus(),
      ]);

      if (trainingRes.error) {
        setError(`训练数据加载失败: ${trainingRes.error.message}`);
      } else if (trainingRes.data) {
        setTrainingResult(trainingRes.data);
      }

      if (!hyperoptRes.error && hyperoptRes.data) {
        setHyperoptStatus(hyperoptRes.data);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "未知错误");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const metrics = [
    {
      label: "模型类型",
      value: trainingResult?.model_type ?? "lightgbm",
      colorType: "neutral" as const,
    },
    {
      label: "训练 AUC",
      value: trainingResult?.metrics.train_auc?.toFixed(4) ?? "n/a",
      colorType: trainingResult?.metrics.train_auc && trainingResult.metrics.train_auc > 0.7 ? "positive" as const : "neutral" as const,
    },
    {
      label: "验证 AUC",
      value: trainingResult?.metrics.validation_auc?.toFixed(4) ?? "n/a",
      colorType: trainingResult?.metrics.validation_auc && trainingResult.metrics.validation_auc > 0.7 ? "positive" as const : "neutral" as const,
    },
    {
      label: "训练时长",
      value: trainingResult ? `${trainingResult.duration_seconds.toFixed(1)}s` : "n/a",
      colorType: "neutral" as const,
    },
  ];

  const hyperoptMetrics = hyperoptStatus
    ? [
        {
          label: "优化状态",
          value: hyperoptStatus.status,
          colorType: hyperoptStatus.status === "running" ? "positive" as const : "neutral" as const,
        },
        {
          label: "当前轮次",
          value: `${hyperoptStatus.current_trial}/${hyperoptStatus.total_trials}`,
          colorType: "neutral" as const,
        },
        {
          label: "最佳分数",
          value: hyperoptStatus.best_value ? hyperoptStatus.best_value.toFixed(4) : "n/a",
          colorType: hyperoptStatus.best_value && hyperoptStatus.best_value > 0.7 ? "positive" as const : "neutral" as const,
        },
        {
          label: "已用时间",
          value: hyperoptStatus.elapsed_seconds ? `${hyperoptStatus.elapsed_seconds.toFixed(0)}s` : "n/a",
          colorType: "neutral" as const,
        },
      ]
    : [];

  return (
    <TerminalShell
      breadcrumb="研究 / 模型训练"
      title="模型训练"
      subtitle="ML 模型训练结果与超参数优化"
      currentPath="/training"
      isAuthenticated={isAuthenticated}
    >
      <div className="flex items-center justify-end mb-4">
        <Button variant="outline" size="sm" onClick={fetchData} disabled={isLoading}>
          <RefreshCw className={`size-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
          刷新
        </Button>
      </div>

      <MetricStrip metrics={metrics} />

      {error && (
        <TerminalCard>
          <div className="flex items-center gap-3 text-red-500">
            <AlertTriangle className="size-4" />
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={fetchData} className="ml-auto">
              重试
            </Button>
          </div>
        </TerminalCard>
      )}

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-64 rounded-lg" />
          <Skeleton className="h-80 rounded-lg" />
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {/* 训练曲线 */}
          <TerminalCard>
            <div className="flex items-center gap-3 mb-4">
              <TrendingUp className="size-4 text-[var(--terminal-accent)]" />
              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">训练曲线</span>
            </div>
            {trainingResult?.training_curve && trainingResult.training_curve.length > 0 ? (
              <TrainingCurveChart series={trainingResult.training_curve} />
            ) : (
              <div className="flex h-48 items-center justify-center text-[var(--terminal-muted)]">
                暂无训练曲线数据，请先执行研究训练
              </div>
            )}
          </TerminalCard>

          {/* 特征重要性 */}
          <TerminalCard>
            <div className="flex items-center gap-3 mb-4">
              <BarChart3 className="size-4 text-[var(--terminal-accent)]" />
              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">特征重要性</span>
            </div>
            {trainingResult?.feature_importance && trainingResult.feature_importance.length > 0 ? (
              <FeatureImportanceChart series={trainingResult.feature_importance} />
            ) : (
              <div className="flex h-48 items-center justify-center text-[var(--terminal-muted)]">
                暂无特征重要性数据
              </div>
            )}
          </TerminalCard>

          {/* 训练指标详情 */}
          <TerminalCard>
            <div className="flex items-center gap-3 mb-4">
              <Brain className="size-4 text-[var(--terminal-accent)]" />
              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">训练指标</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <InfoBlock label="训练 AUC" value={trainingResult?.metrics.train_auc?.toFixed(4) ?? "n/a"} />
              <InfoBlock label="验证 AUC" value={trainingResult?.metrics.validation_auc?.toFixed(4) ?? "n/a"} />
              <InfoBlock label="训练准确率" value={trainingResult?.metrics.train_accuracy?.toFixed(4) ?? "n/a"} />
              <InfoBlock label="验证准确率" value={trainingResult?.metrics.validation_accuracy?.toFixed(4) ?? "n/a"} />
              <InfoBlock label="训练 F1" value={trainingResult?.metrics.train_f1?.toFixed(4) ?? "n/a"} />
              <InfoBlock label="验证 F1" value={trainingResult?.metrics.validation_f1?.toFixed(4) ?? "n/a"} />
              <InfoBlock label="最佳迭代" value={trainingResult?.metrics.best_iteration?.toString() ?? "n/a"} />
              <InfoBlock label="特征数量" value={trainingResult?.metrics.n_features?.toString() ?? "n/a"} />
            </div>
          </TerminalCard>

          {/* 超参数优化状态 */}
          <TerminalCard>
            <div className="flex items-center gap-3 mb-4">
              <Clock className="size-4 text-[var(--terminal-accent)]" />
              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">超参数优化</span>
            </div>
            {hyperoptMetrics.length > 0 && (
              <MetricStrip metrics={hyperoptMetrics} />
            )}
            {hyperoptStatus?.message && (
              <p className="text-sm text-[var(--terminal-muted)] mt-4">{hyperoptStatus.message}</p>
            )}
            {hyperoptStatus?.best_params && (
              <div className="mt-4 p-3 rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)] mb-2">最佳参数</p>
                <pre className="text-xs text-[var(--terminal-text)] overflow-auto">
                  {JSON.stringify(hyperoptStatus.best_params, null, 2)}
                </pre>
              </div>
            )}
          </TerminalCard>
        </div>
      )}
    </TerminalShell>
  );
}
