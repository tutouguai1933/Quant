"use client";

/**
 * 自动化周期历史卡片
 * 显示每轮自动化运行的历史记录，支持点击查看详情
 */

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, ChevronDown, ChevronUp } from "lucide-react";
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
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

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

  // 显示状态颜色
  const getDisplayStatusColor = (displayStatus: string) => {
    switch (displayStatus) {
      case "succeeded":
        return "text-green-500";
      case "blocked":
        return "text-orange-500";
      case "cooldown":
        return "text-blue-400";
      case "failed":
        return "text-red-500";
      default:
        return "text-yellow-500";
    }
  };

  // 显示状态标签
  const getDisplayStatusLabel = (displayStatus: string) => {
    switch (displayStatus) {
      case "succeeded":
        return "✅ 成功";
      case "blocked":
        return "🚫 拦阻";
      case "cooldown":
        return "⏸️ 冷却";
      case "failed":
        return "❌ 失败";
      case "limited":
        return "📊 限额";
      default:
        return "⏳ 等待";
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
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs mb-3 pb-3 border-b border-[var(--terminal-border)]">
          <span className="text-[var(--terminal-muted)]">
            总计: <span className="text-[var(--terminal-text)] font-medium">{summary.total}</span> 轮
          </span>
          <span className="text-green-500">
            成功: <span className="font-medium">{summary.succeeded_count}</span>
          </span>
          <span className="text-orange-500">
            拦阻: <span className="font-medium">{summary.blocked_count}</span>
          </span>
          <span className="text-yellow-500">
            等待: <span className="font-medium">{summary.waiting_count}</span>
          </span>
          {summary.failed_count > 0 && (
            <span className="text-red-500">
              失败: <span className="font-medium">{summary.failed_count}</span>
            </span>
          )}
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
        <div className="space-y-1">
          {pageItems.map((item, idx) => {
            const globalIdx = startIndex + idx;
            const isExpanded = expandedIndex === globalIdx;
            const displayStatus = item.display_status || "waiting";

            return (
              <div key={`${item.recorded_at}-${idx}`} className="border border-[var(--terminal-border)]/50 rounded">
                {/* 主行 - 可点击 */}
                <button
                  onClick={() => setExpandedIndex(isExpanded ? null : globalIdx)}
                  className="w-full flex items-center justify-between py-2 px-3 hover:bg-[var(--terminal-border)]/20 text-left"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-[var(--terminal-muted)] w-20">
                      {formatTime(item.recorded_at)}
                    </span>
                    <span className={`text-xs font-medium ${getDisplayStatusColor(displayStatus)}`}>
                      {getDisplayStatusLabel(displayStatus)}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    {item.recommended_symbol && (
                      <span className="text-sm font-mono text-[var(--terminal-text)]">
                        {item.recommended_symbol.replace("USDT", "")}
                      </span>
                    )}
                    <span className="text-xs text-[var(--terminal-muted)] max-w-[150px] truncate">
                      {item.message || item.failure_reason}
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-[var(--terminal-muted)]" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-[var(--terminal-muted)]" />
                    )}
                  </div>
                </button>

                {/* 详情面板 */}
                {isExpanded && (
                  <div className="px-3 pb-3 pt-1 border-t border-[var(--terminal-border)]/30 bg-[var(--terminal-bg)]/50">
                    {/* 候选币种 */}
                    {item.candidates && item.candidates.length > 0 && (
                      <div className="mb-3">
                        <p className="text-xs text-[var(--terminal-muted)] mb-1">候选币种:</p>
                        <div className="flex flex-wrap gap-2">
                          {item.candidates.map((c, i) => (
                            <span
                              key={i}
                              className="text-xs px-2 py-0.5 rounded border border-[var(--terminal-border)] bg-[var(--terminal-border)]/20"
                            >
                              <span className="font-mono">{c.symbol.replace("USDT", "")}</span>
                              {c.blocked_reason && (
                                <span className="text-[var(--terminal-muted)] ml-1">({c.blocked_reason})</span>
                              )}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 任务执行状态 */}
                    {item.task_summary && Object.keys(item.task_summary).length > 0 && (
                      <div className="mb-3">
                        <p className="text-xs text-[var(--terminal-muted)] mb-1">任务状态:</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(item.task_summary).map(([name, task]) => (
                            <span
                              key={name}
                              className="text-xs px-2 py-0.5 rounded border border-[var(--terminal-border)]"
                            >
                              {name}:{" "}
                              <span
                                className={
                                  task.status === "succeeded"
                                    ? "text-green-500"
                                    : task.status === "failed"
                                    ? "text-red-500"
                                    : "text-yellow-500"
                                }
                              >
                                {task.status}
                              </span>
                              {task.duration_seconds > 0 && (
                                <span className="text-[var(--terminal-muted)] ml-1">
                                  ({Math.round(task.duration_seconds)}s)
                                </span>
                              )}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* RSI 快照 */}
                    {item.rsi_snapshot && Object.keys(item.rsi_snapshot).length > 0 && (
                      <div>
                        <p className="text-xs text-[var(--terminal-muted)] mb-1">RSI 快照:</p>
                        <div className="flex flex-wrap gap-2 text-xs">
                          {Object.entries(item.rsi_snapshot).slice(0, 6).map(([symbol, value]) => (
                            <span
                              key={symbol}
                              className="px-2 py-0.5 rounded border border-[var(--terminal-border)] bg-[var(--terminal-border)]/10"
                            >
                              <span className="font-mono">{symbol}</span>: {String(value)}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 详细信息 */}
                    <div className="mt-2 text-xs text-[var(--terminal-muted)]">
                      <div>模式: {item.mode}</div>
                      {item.failure_reason && <div>原因: {item.failure_reason}</div>}
                      {item.next_action && <div>建议: {item.next_action}</div>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
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
