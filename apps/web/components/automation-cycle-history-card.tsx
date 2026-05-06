"use client";

/**
 * 自动化周期历史卡片
 * 显示每轮自动化运行的历史记录
 */

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { getAutomationCycleHistory, type AutomationCycleRecord, type AutomationCycleHistorySummary } from "../lib/api";
import { TerminalCard } from "./terminal";

interface AutomationCycleHistoryCardProps {
  refreshInterval?: number;
}

const PAGE_SIZE = 10;

export function AutomationCycleHistoryCard({ refreshInterval = 60000 }: AutomationCycleHistoryCardProps) {
  const [items, setItems] = useState<AutomationCycleRecord[]>([]);
  const [summary, setSummary] = useState<AutomationCycleHistorySummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const response = await getAutomationCycleHistory(100);
        if (cancelled) return;

        if (response.error) {
          setError(response.error.message || "获取历史记录失败");
        } else {
          setItems(response.data.items || []);
          setSummary(response.data.summary || null);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError("网络请求失败");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [refreshInterval]);

  // 格式化时间
  const formatTime = (iso: string) => {
    if (!iso) return "--";
    try {
      const d = new Date(iso);
      // 转换为北京时间
      return d.toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  // 状态颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case "succeeded":
        return "text-green-500";
      case "waiting":
        return "text-yellow-500";
      case "attention_required":
      case "failed":
        return "text-red-500";
      default:
        return "text-[var(--terminal-muted)]";
    }
  };

  // 状态标签
  const getStatusLabel = (status: string) => {
    switch (status) {
      case "succeeded":
        return "✅ 成功";
      case "waiting":
        return "⏳ 等待";
      case "attention_required":
        return "⚠️ 需关注";
      case "failed":
        return "❌ 失败";
      default:
        return status;
    }
  };

  // 分页
  const totalPages = Math.ceil(items.length / PAGE_SIZE);
  const startIndex = (page - 1) * PAGE_SIZE;
  const pageItems = items.slice(startIndex, startIndex + PAGE_SIZE);

  if (isLoading) {
    return (
      <TerminalCard title="自动化周期历史">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-[var(--terminal-cyan)]" />
          <span className="ml-2 text-[var(--terminal-muted)]">加载中...</span>
        </div>
      </TerminalCard>
    );
  }

  if (error) {
    return (
      <TerminalCard title="自动化周期历史">
        <div className="text-red-500 text-sm">{error}</div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title="自动化周期历史">
      {/* 摘要 */}
      {summary && (
        <div className="flex gap-4 text-xs mb-3 pb-3 border-b border-[var(--terminal-border)]">
          <span className="text-[var(--terminal-muted)]">
            总计: <span className="text-[var(--terminal-text)] font-medium">{summary.total}</span> 轮
          </span>
          <span className="text-green-500">
            成功: <span className="font-medium">{summary.success_count}</span>
          </span>
          <span className="text-yellow-500">
            等待: <span className="font-medium">{summary.waiting_count}</span>
          </span>
          <span className="text-red-500">
            失败: <span className="font-medium">{summary.failed_count}</span>
          </span>
          {summary.last_run_at && (
            <span className="text-[var(--terminal-muted)]">
              最近运行: {formatTime(summary.last_run_at)}
            </span>
          )}
        </div>
      )}

      {/* 历史列表 */}
      {items.length === 0 ? (
        <div className="text-[var(--terminal-muted)] text-sm py-4 text-center">暂无历史记录</div>
      ) : (
        <div className="space-y-2">
          {pageItems.map((item, idx) => (
            <div
              key={`${item.recorded_at}-${idx}`}
              className="flex items-center justify-between py-2 px-3 rounded border border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-border)]/20"
            >
              <div className="flex items-center gap-3">
                <span className="text-xs text-[var(--terminal-muted)] w-20">
                  {formatTime(item.recorded_at)}
                </span>
                <span className={`text-xs font-medium ${getStatusColor(item.status)}`}>
                  {getStatusLabel(item.status)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                {item.recommended_symbol && (
                  <span className="text-sm font-mono text-[var(--terminal-text)]">
                    {item.recommended_symbol.replace("USDT", "")}
                  </span>
                )}
                <span className="text-xs text-[var(--terminal-muted)] max-w-[200px] truncate">
                  {item.message || item.next_action}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-[var(--terminal-border)]">
          <div className="text-xs text-[var(--terminal-muted)]">
            第 {page}/{totalPages} 页
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--terminal-border)] disabled:opacity-50 hover:border-[var(--terminal-cyan)]"
            >
              <ChevronLeft className="w-3 h-3" />
              上一页
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--terminal-border)] disabled:opacity-50 hover:border-[var(--terminal-cyan)]"
            >
              下一页
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </TerminalCard>
  );
}
