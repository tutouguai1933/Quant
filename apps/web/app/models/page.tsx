/**
 * 模型管理页面
 * 展示模型版本、对比、提升功能
 */
"use client";

import { useEffect, useState } from "react";
import {
  Box,
  GitBranch,
  ArrowUpRight,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
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
  promoteMLModel,
  type MLModelRecord,
} from "../../lib/api";

export default function ModelsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [models, setModels] = useState<MLModelRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setIsAuthenticated(Boolean(data.isAuthenticated));
      })
      .catch(() => {});
  }, []);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const res = await getMLModels(20);
      if (!res.error && res.data) {
        setModels(res.data.models);
        setTotal(res.data.total);
      }
    } catch {
      // Ignore errors
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handlePromote = async (versionId: string, stage: string) => {
    try {
      await promoteMLModel(versionId, stage);
      fetchData();
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

  const getStageIcon = (stage: string) => {
    switch (stage) {
      case "production":
        return <CheckCircle className="size-4 text-green-500" />;
      case "staging":
        return <Clock className="size-4 text-yellow-500" />;
      case "archived":
        return <XCircle className="size-4 text-gray-500" />;
      default:
        return <Box className="size-4" />;
    }
  };

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

  return (
    <TerminalShell
      breadcrumb="研究 / 模型管理"
      title="模型管理"
      subtitle="ML 模型版本管理与发布"
      currentPath="/models"
      isAuthenticated={isAuthenticated}
    >
      <div className="flex items-center justify-end mb-4">
        <Button variant="outline" size="sm" onClick={fetchData} disabled={isLoading}>
          <RefreshCw className={`size-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
          刷新
        </Button>
      </div>

      <MetricStrip metrics={metrics} />

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
        <div className="space-y-4">
          {/* 生产模型高亮 */}
          {models.filter((m) => m.stage === "production").length > 0 && (
            <TerminalCard>
              <div className="flex items-center gap-3 mb-4">
                <CheckCircle className="size-4 text-green-500" />
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">当前生产模型</span>
              </div>
              {models
                .filter((m) => m.stage === "production")
                .map((model) => (
                  <ModelCard
                    key={model.version_id}
                    model={model}
                    onPromote={handlePromote}
                    isProduction
                  />
                ))}
            </TerminalCard>
          )}

          {/* 所有模型列表 */}
          <TerminalCard>
            <div className="flex items-center gap-3 mb-4">
              <GitBranch className="size-4 text-[var(--terminal-accent)]" />
              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">模型版本列表</span>
            </div>
            <div className="space-y-3">
              {models.map((model) => (
                <ModelCard
                  key={model.version_id}
                  model={model}
                  onPromote={handlePromote}
                />
              ))}
            </div>
          </TerminalCard>
        </div>
      )}
    </TerminalShell>
  );
}

function ModelCard({
  model,
  onPromote,
  isProduction = false,
}: {
  model: MLModelRecord;
  onPromote: (versionId: string, stage: string) => void;
  isProduction?: boolean;
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
  const accuracy = model.metrics?.val_accuracy ?? model.metrics?.validation_accuracy;

  return (
    <div
      className={`p-4 rounded border ${
        isProduction
          ? "border-green-500/30 bg-green-500/5"
          : "border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono font-medium text-[var(--terminal-text)]">
              {model.version_id}
            </span>
            <StatusBadge value={model.stage} />
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-3 text-xs text-[var(--terminal-muted)]">
            <span>类型: {model.model_type}</span>
            <span>AUC: {auc?.toFixed(4) ?? "n/a"}</span>
            <span>准确率: {accuracy?.toFixed(4) ?? "n/a"}</span>
          </div>
          <div className="mt-1 text-xs text-[var(--terminal-dim)]">
            创建于 {formatDate(model.created_at)}
          </div>
          {model.description && (
            <p className="mt-2 text-xs text-[var(--terminal-muted)]">{model.description}</p>
          )}
          {model.tags && model.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
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
    </div>
  );
}
