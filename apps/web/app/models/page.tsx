/**
 * 模型管理页面
 * 展示模型版本、对比、提升功能
 */
"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Box,
  GitBranch,
  ArrowUpRight,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  GitCompare,
  ChevronDown,
  ChevronUp,
  Zap,
} from "lucide-react";

import {
  TerminalShell,
  TerminalCard,
  MetricStrip,
  InfoBlock,
} from "../../components/terminal";
import { Skeleton } from "../../components/ui/skeleton";
import { Button } from "../../components/ui/button";
import { StatusBadge } from "../../components/status-badge";
import {
  getMLModels,
  getProductionModel,
  promoteMLModel,
  compareMLModels,
  type MLModelRecord,
  type MLModelComparison,
} from "../../lib/api";

export default function ModelsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [models, setModels] = useState<MLModelRecord[]>([]);
  const [productionModel, setProductionModel] = useState<MLModelRecord | null>(null);
  const [total, setTotal] = useState(0);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [comparison, setComparison] = useState<MLModelComparison | null>(null);
  const [expandedModel, setExpandedModel] = useState<string | null>(null);

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
    try {
      const [modelsRes, productionRes] = await Promise.all([
        getMLModels(20),
        getProductionModel(),
      ]);
      if (!modelsRes.error && modelsRes.data) {
        setModels(modelsRes.data.models);
        setTotal(modelsRes.data.total);
      }
      if (!productionRes.error && productionRes.data) {
        setProductionModel(productionRes.data);
      }
    } catch {
      // Ignore errors
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handlePromote = async (versionId: string, stage: string) => {
    try {
      await promoteMLModel(versionId, stage);
      fetchData();
    } catch {
      // Ignore errors
    }
  };

  const handleSelectModel = (versionId: string) => {
    setSelectedModels((prev) => {
      if (prev.includes(versionId)) {
        return prev.filter((id) => id !== versionId);
      }
      if (prev.length >= 2) {
        return [prev[1], versionId];
      }
      return [...prev, versionId];
    });
    setComparison(null);
  };

  const handleCompare = async () => {
    if (selectedModels.length !== 2) return;
    try {
      const res = await compareMLModels(selectedModels[0], selectedModels[1]);
      if (!res.error && res.data) {
        setComparison(res.data);
      }
    } catch {
      // Ignore errors
    }
  };

  const productionCount = models.filter((m) => m.stage === "production").length;
  const stagingCount = models.filter((m) => m.stage === "staging").length;
  const archivedCount = models.filter((m) => m.stage === "archived").length;

  const metrics = [
    {
      label: "总模型数",
      value: String(total),
      colorType: "neutral" as const,
    },
    {
      label: "生产模型",
      value: String(productionCount),
      colorType: productionCount > 0 ? "positive" as const : "neutral" as const,
    },
    {
      label: "待发布",
      value: String(stagingCount),
      colorType: "neutral" as const,
    },
    {
      label: "已归档",
      value: String(archivedCount),
      colorType: "neutral" as const,
    },
  ];

  return (
    <TerminalShell
      breadcrumb="研究 / 模型管理"
      title="模型管理"
      subtitle="ML 模型版本管理与发布"
      currentPath="/models"
      isAuthenticated={isAuthenticated}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {selectedModels.length > 0 && (
            <span className="text-xs text-[var(--terminal-muted)]">
              已选择 {selectedModels.length} 个模型
            </span>
          )}
          {selectedModels.length === 2 && (
            <Button variant="outline" size="sm" onClick={handleCompare}>
              <GitCompare className="size-3 mr-1" />
              对比
            </Button>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={isLoading}>
          <RefreshCw className={`size-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
          刷新
        </Button>
      </div>

      {/* 生产模型概览 */}
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
                <div className="text-[10px] text-[var(--terminal-muted)] uppercase">验证 AUC</div>
                <div className="text-sm font-mono text-green-500">
                  {(productionModel.metrics.validation_auc || productionModel.metrics.val_auc || 0).toFixed(4)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-[var(--terminal-muted)] uppercase">类型</div>
                <div className="text-sm font-mono">{productionModel.model_type}</div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-[var(--terminal-muted)] uppercase">来源</div>
                <div className="text-sm font-mono">
                  {String(productionModel.training_context?.source || "unknown")}
                </div>
              </div>
            </div>
          </div>
        </TerminalCard>
      )}

      <MetricStrip metrics={metrics} />

      {/* 模型对比结果 */}
      {comparison && (
        <TerminalCard className="mb-4">
          <div className="flex items-center gap-3 mb-4">
            <GitCompare className="size-4 text-[var(--terminal-accent)]" />
            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">模型对比</span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="p-3 rounded border border-[var(--terminal-border)]">
              <div className="text-xs text-[var(--terminal-muted)]">模型 A</div>
              <div className="text-sm font-mono mt-1">{comparison.version_a}</div>
            </div>
            <div className="p-3 rounded border border-[var(--terminal-border)]">
              <div className="text-xs text-[var(--terminal-muted)]">模型 B</div>
              <div className="text-sm font-mono mt-1">{comparison.version_b}</div>
            </div>
            <div className="p-3 rounded border border-[var(--terminal-border)]">
              <div className="text-xs text-[var(--terminal-muted)]">胜出者</div>
              <div className="text-sm font-mono mt-1 text-green-500">
                {comparison.winner === "a" ? comparison.version_a :
                 comparison.winner === "b" ? comparison.version_b : "平局"}
              </div>
            </div>
          </div>
          {comparison.metrics_diff && Object.keys(comparison.metrics_diff).length > 0 && (
            <div className="mt-4 grid gap-2 sm:grid-cols-2 md:grid-cols-3">
              {Object.entries(comparison.metrics_diff).map(([key, value]) => (
                <div key={key} className="text-xs">
                  <span className="text-[var(--terminal-muted)]">{key}: </span>
                  <span className={Number(value) >= 0 ? "text-green-500" : "text-red-500"}>
                    {Number(value) >= 0 ? "+" : ""}{Number(value).toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
          )}
          {comparison.recommendation && (
            <p className="mt-4 text-sm text-[var(--terminal-muted)]">{comparison.recommendation}</p>
          )}
        </TerminalCard>
      )}

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-64 rounded-lg" />
        </div>
      ) : models.length === 0 ? (
        <TerminalCard>
          <div className="flex flex-col items-center justify-center py-12 text-[var(--terminal-muted)]">
            <Box className="size-12 mb-4 opacity-50" />
            <p>暂无模型记录</p>
            <p className="text-sm mt-2">执行研究训练后会自动注册模型</p>
          </div>
        </TerminalCard>
      ) : (
        <TerminalCard>
          <div className="flex items-center gap-3 mb-4">
            <GitBranch className="size-4 text-[var(--terminal-accent)]" />
            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">模型版本列表</span>
          </div>
          <div className="space-y-2">
            {models.map((model) => (
              <ModelCard
                key={model.version_id}
                model={model}
                onPromote={handlePromote}
                isSelected={selectedModels.includes(model.version_id)}
                onSelect={handleSelectModel}
                isExpanded={expandedModel === model.version_id}
                onToggleExpand={() => setExpandedModel(
                  expandedModel === model.version_id ? null : model.version_id
                )}
              />
            ))}
          </div>
        </TerminalCard>
      )}
    </TerminalShell>
  );
}

function ModelCard({
  model,
  onPromote,
  isSelected,
  onSelect,
  isExpanded,
  onToggleExpand,
}: {
  model: MLModelRecord;
  onPromote: (versionId: string, stage: string) => void;
  isSelected: boolean;
  onSelect: (versionId: string) => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
}) {
  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const auc = model.metrics?.val_auc ?? model.metrics?.validation_auc;
  const trainAuc = model.metrics?.train_auc;
  const f1 = model.metrics?.val_f1 ?? model.metrics?.validation_f1;
  const trainF1 = model.metrics?.train_f1;
  const source = String(model.training_context?.source || "unknown");
  const sampleCount = model.training_context?.sample_count as number | undefined;
  const featureCount = model.training_context?.feature_count as number | undefined;
  const duration = model.training_context?.duration_seconds as number | undefined;

  return (
    <div
      className={`rounded border transition-colors ${
        isSelected
          ? "border-[var(--terminal-accent)] bg-[var(--terminal-accent)]/5"
          : model.stage === "production"
          ? "border-green-500/30 bg-green-500/5"
          : "border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50"
      }`}
    >
      <div className="p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onSelect(model.version_id)}
              className="rounded border-[var(--terminal-border)]"
            />
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono font-medium text-[var(--terminal-text)]">
                {model.version_id}
              </span>
              <StatusBadge value={model.stage} />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-xs text-[var(--terminal-muted)] hidden sm:block">
              验证 AUC: <span className={auc && auc > 0.7 ? "text-green-500" : ""}>{auc?.toFixed(4) ?? "n/a"}</span>
            </div>
            <div className="text-xs text-[var(--terminal-muted)] hidden md:block">
              来源: {source === "automation_cycle" ? "自动化周期" : source === "manual" ? "手动触发" : source}
            </div>
            <Button variant="ghost" size="sm" onClick={onToggleExpand}>
              {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            </Button>
          </div>
        </div>
      </div>

      {isExpanded && (
        <div className="px-3 pb-3 border-t border-[var(--terminal-border)] pt-3">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <InfoBlock label="模型类型" value={model.model_type} />
            <InfoBlock label="训练 AUC" value={trainAuc?.toFixed(4) ?? "n/a"} />
            <InfoBlock label="验证 AUC" value={auc?.toFixed(4) ?? "n/a"} />
            <InfoBlock label="训练 F1" value={trainF1?.toFixed(4) ?? "n/a"} />
            <InfoBlock label="验证 F1" value={f1?.toFixed(4) ?? "n/a"} />
            <InfoBlock label="样本数" value={sampleCount?.toString() ?? "n/a"} />
            <InfoBlock label="特征数" value={featureCount?.toString() ?? "n/a"} />
            <InfoBlock label="训练时长" value={duration ? `${duration.toFixed(1)}s` : "n/a"} />
          </div>
          <div className="mt-3 flex items-center justify-between">
            <div className="text-xs text-[var(--terminal-dim)]">
              创建于 {formatDate(model.created_at)}
            </div>
            <div className="flex items-center gap-2">
              {model.stage === "staging" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPromote(model.version_id, "production")}
                >
                  <ArrowUpRight className="size-3 mr-1" />
                  发布
                </Button>
              )}
              {model.stage === "production" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPromote(model.version_id, "archived")}
                >
                  归档
                </Button>
              )}
            </div>
          </div>
          {model.tags && model.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              {model.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-0.5 text-[10px] rounded bg-[var(--terminal-accent)]/10 text-[var(--terminal-accent)]"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
