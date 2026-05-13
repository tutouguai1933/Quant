/**
 * 模型训练页面
 * 展示 ML 训练结果、生产模型、训练曲线、特征重要性、训练历史
 */
"use client";

import { useEffect, useState, useCallback } from "react";
import { Brain, Clock, TrendingUp, BarChart3, RefreshCw, AlertTriangle, Zap, History, ChevronRight } from "lucide-react";
import Link from "next/link";

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
  getProductionModel,
  getTrainingHistory,
  getABComparison,
  type MLTrainingResult,
  type MLHyperoptProgress,
  type MLModelRecord,
  type TrainingHistoryItem,
  type ABComparisonData,
} from "../../lib/api";

export default function TrainingPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [trainingResult, setTrainingResult] = useState<MLTrainingResult | null>(null);
  const [hyperoptStatus, setHyperoptStatus] = useState<MLHyperoptProgress | null>(null);
  const [productionModel, setProductionModel] = useState<MLModelRecord | null>(null);
  const [trainingHistory, setTrainingHistory] = useState<TrainingHistoryItem[]>([]);
  const [abComparison, setAbComparison] = useState<ABComparisonData | null>(null);
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
      const [trainingRes, hyperoptRes, productionRes, historyRes] = await Promise.all([
        getMLTrainingResult(),
        getMLHyperoptStatus(),
        getProductionModel(),
        getTrainingHistory(10),
      ]);

      if (trainingRes.error) {
        setError(`训练数据加载失败: ${trainingRes.error.message}`);
      } else if (trainingRes.data) {
        setTrainingResult(trainingRes.data);
      }

      if (!hyperoptRes.error && hyperoptRes.data) {
        setHyperoptStatus(hyperoptRes.data);
      }

      if (!productionRes.error && productionRes.data) {
        setProductionModel(productionRes.data);
      }

      if (!historyRes.error && historyRes.data) {
        setTrainingHistory(historyRes.data.items || []);
      }

      // A/B 对比（后台静默加载，失败不影响主流程）
      getABComparison().then((abRes) => {
        if (!abRes.error && abRes.data) {
          setAbComparison(abRes.data);
        }
      }).catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "未知错误");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const formatTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "n/a";
    }
  };

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

      {/* 生产模型概览卡片 */}
      {productionModel && (
        <TerminalCard className="mb-4 border-green-500/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Zap className="size-5 text-green-500" />
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">当前生产模型</div>
                <div className="text-lg font-mono text-[var(--terminal-text)] mt-1">
                  {productionModel.version_id}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-[10px] text-[var(--terminal-muted)] uppercase">AUC</div>
                <div className="text-sm font-mono text-green-500">
                  {(productionModel.metrics.train_auc || 0).toFixed(4)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-[var(--terminal-muted)] uppercase">类型</div>
                <div className="text-sm font-mono">{productionModel.model_type}</div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-[var(--terminal-muted)] uppercase">训练于</div>
                <div className="text-sm font-mono">{formatTime(productionModel.created_at)}</div>
              </div>
              <Link href="/models">
                <Button variant="outline" size="sm">
                  查看全部模型
                  <ChevronRight className="size-4 ml-1" />
                </Button>
              </Link>
            </div>
          </div>
        </TerminalCard>
      )}

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

          {/* 训练历史 */}
          <TerminalCard>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <History className="size-4 text-[var(--terminal-accent)]" />
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">训练历史</span>
              </div>
              <Link href="/models">
                <Button variant="ghost" size="sm">
                  查看全部
                  <ChevronRight className="size-4 ml-1" />
                </Button>
              </Link>
            </div>
            {trainingHistory.length > 0 ? (
              <div className="space-y-2">
                {trainingHistory.map((item) => (
                  <div
                    key={item.version_id}
                    className="flex items-center justify-between p-2 rounded border border-[var(--terminal-border)] hover:bg-[var(--terminal-bg)]/50"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${
                        item.stage === "production" ? "bg-green-500" :
                        item.stage === "staging" ? "bg-blue-500" : "bg-gray-500"
                      }`} />
                      <div>
                        <div className="text-xs font-mono">{item.version_id}</div>
                        <div className="text-[10px] text-[var(--terminal-muted)]">
                          {item.source === "automation_cycle" ? "自动化周期" :
                           item.source === "manual" ? "手动触发" :
                           item.source === "hyperopt" ? "参数优化" : item.source}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs">
                      <div className="text-right">
                        <div className="text-[10px] text-[var(--terminal-muted)]">验证 AUC</div>
                        <div className={`font-mono ${
                          (item.metrics.validation_auc || 0) > 0.7 ? "text-green-500" : ""
                        }`}>
                          {(item.metrics.validation_auc || 0).toFixed(4)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] text-[var(--terminal-muted)]">时间</div>
                        <div className="font-mono">{formatTime(item.created_at)}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex h-32 items-center justify-center text-[var(--terminal-muted)]">
                暂无训练历史
              </div>
            )}
          </TerminalCard>

          {/* 超参数优化状态 */}
          <TerminalCard className="xl:col-span-2">
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

          {/* A/B 对比 */}
          {abComparison && (abComparison.ml.count > 0 || abComparison.heuristic.count > 0) && (
            <TerminalCard className="xl:col-span-2">
              <div className="flex items-center gap-3 mb-4">
                <BarChart3 className="size-4 text-[var(--terminal-accent)]" />
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">ML vs 启发式 A/B 对比</span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: "ML 模型", data: abComparison.ml, color: "text-green-400" },
                  { label: "启发式规则", data: abComparison.heuristic, color: "text-amber-400" },
                ].map(({ label, data, color }) => (
                  <div key={label} className="p-3 rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50">
                    <p className={`text-sm font-semibold mb-2 ${color}`}>{label}</p>
                    <div className="grid gap-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-[var(--terminal-muted)]">样本数</span>
                        <span className="font-mono">{data.count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--terminal-muted)]">胜率</span>
                        <span className="font-mono">{(data.win_rate * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--terminal-muted)]">平均收益</span>
                        <span className={`font-mono ${data.mean_return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {data.mean_return_pct.toFixed(4)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--terminal-muted)]">Sharpe</span>
                        <span className="font-mono">{data.sharpe.toFixed(3)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </TerminalCard>
          )}
        </div>
      )}
    </TerminalShell>
  );
}
