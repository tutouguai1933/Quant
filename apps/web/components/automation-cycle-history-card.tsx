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

// 根据 failure_reason 计算 display_status（兼容旧数据）
function computeDisplayStatus(item: AutomationCycleRecord): string {
  if (item.display_status) return item.display_status;

  const failureReason = item.failure_reason || "";
  const status = item.status || "";

  if (status === "succeeded") return "succeeded";
  if (status === "failed" || status === "attention_required") return "failed";
  if (failureReason === "candidate_blocked") return "blocked";
  if (failureReason === "cycle_cooldown_active") return "cooldown";
  if (failureReason === "daily_limit_reached") return "limited";
  return "waiting";
}

// 状态颜色
function getDisplayStatusColor(displayStatus: string): string {
  switch (displayStatus) {
    case "succeeded":
      return "text-green-500";
    case "blocked":
      return "text-orange-500";
    case "cooldown":
      return "text-blue-400";
    case "failed":
      return "text-red-500";
    case "limited":
      return "text-purple-400";
    default:
      return "text-yellow-500";
  }
}

// 状态标签
function getDisplayStatusLabel(displayStatus: string): string {
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
}

// 拦截原因中文翻译
function translateBlockReason(reason: string): string {
  const translations: Record<string, string> = {
    "volatility_too_high": "波动率过高",
    "volume_not_confirmed": "成交量不足",
    "validation_future_return_not_positive": "预测收益为负",
    "trend_broken": "趋势破位",
    "score_too_low": "评分过低",
    "validation_sample_count_too_low": "样本数不足",
    "validation_positive_rate_too_low": "胜率过低",
    "strict_template_not_confirmed": "严格模板未确认",
    "manual_mode_requires_target": "手动模式需指定目标",
    "resume_checklist_pending": "恢复清单待处理",
    "resume_requires_dry_run_only": "恢复需先dry-run",
    "cooldown_active": "冷却中",
    "daily_limit_reached": "已达日限额",
    "manual_takeover_active": "人工接管中",
    "paused_waiting_review": "暂停等待审核",
    "manual_mode": "手动模式",
    "candidate_blocked": "候选被拦阻",
  };
  return translations[reason] || reason;
}

// Gate 失败原因中文翻译
function translateGateReason(reason: string): string {
  const translations: Record<string, string> = {
    // Live Gate
    "dry_run_gate_not_passed": "dry-run 未通过",
    "live_score_too_low": "评分过低",
    "live_validation_positive_rate_too_low": "验证正确率过低",
    "live_net_return_too_low": "净收益率过低",
    "live_win_rate_too_low": "胜率过低",
    "live_turnover_too_high": "换手率过高",
    "live_sample_count_too_low": "样本数不足",
    // Dry-Run Gate
    "dry_run_score_too_low": "评分过低",
    "dry_run_positive_rate_too_low": "验证正确率过低",
    "dry_run_net_return_too_low": "净收益率过低",
    "dry_run_sharpe_too_low": "夏普比率过低",
    "dry_run_drawdown_too_high": "回撤过高",
    "dry_run_loss_streak_too_long": "连续亏损过长",
    "dry_run_win_rate_too_low": "胜率过低",
    "dry_run_turnover_too_high": "换手率过高",
    "dry_run_sample_count_too_low": "样本数不足",
    // Rule Gate
    "rule_volatility_too_high": "波动率过高",
    "rule_volume_not_confirmed": "成交量不足",
    "rule_trend_broken": "趋势破位",
    // Validation Gate
    "validation_sample_count_too_low": "验证样本不足",
    "validation_future_return_not_positive": "预测收益非正",
    // Consistency Gate
    "consistency_backtest_validation_gap_too_large": "回测验证差距过大",
    "consistency_training_validation_gap_too_large": "训练验证差距过大",
  };
  return translations[reason] || reason;
}

// 状态说明
function getStatusDescription(displayStatus: string, failureReason: string, message: string): string {
  switch (displayStatus) {
    case "succeeded":
      return "候选通过，已执行交易";
    case "blocked":
      // 如果是通用拦截码，显示具体原因（message）
      const blockReason = failureReason === "candidate_blocked" ? message : failureReason;
      return `候选被拦阻: ${translateBlockReason(blockReason) || "未知原因"}`;
    case "cooldown":
      return "冷却窗口中，等待下次运行";
    case "failed":
      return "执行失败，需要人工关注";
    case "limited":
      return "今日运行次数已达上限";
    default:
      return message || "等待条件满足";
  }
}

export function AutomationCycleHistoryCard({ refreshInterval = 60000 }: AutomationCycleHistoryCardProps) {
  const [items, setItems] = useState<AutomationCycleRecord[]>([]);
  const [summary, setSummary] = useState<AutomationCycleHistorySummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<Record<number, "basic" | "candidates" | "tasks" | "rsi">>({});

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

  // 分页
  const totalPages = Math.ceil(items.length / PAGE_SIZE);
  const startIndex = (page - 1) * PAGE_SIZE;
  const pageItems = items.slice(startIndex, startIndex + PAGE_SIZE);

  // 计算统计（兼容旧数据）
  const computedStats = items.reduce(
    (acc, item) => {
      const ds = computeDisplayStatus(item);
      switch (ds) {
        case "succeeded":
          acc.succeeded++;
          break;
        case "blocked":
          acc.blocked++;
          break;
        case "cooldown":
          acc.cooldown++;
          break;
        case "failed":
          acc.failed++;
          break;
        default:
          acc.waiting++;
      }
      return acc;
    },
    { succeeded: 0, blocked: 0, cooldown: 0, failed: 0, waiting: 0 }
  );

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
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs mb-3 pb-3 border-b border-[var(--terminal-border)]">
        <span className="text-[var(--terminal-muted)]">
          总计: <span className="text-[var(--terminal-text)] font-medium">{items.length}</span> 轮
        </span>
        <span className="text-green-500">
          成功: <span className="font-medium">{computedStats.succeeded}</span>
        </span>
        <span className="text-orange-500">
          拦阻: <span className="font-medium">{computedStats.blocked}</span>
        </span>
        {computedStats.cooldown > 0 && (
          <span className="text-blue-400">
            冷却: <span className="font-medium">{computedStats.cooldown}</span>
          </span>
        )}
        {computedStats.failed > 0 && (
          <span className="text-red-500">
            失败: <span className="font-medium">{computedStats.failed}</span>
          </span>
        )}
        {computedStats.waiting > 0 && (
          <span className="text-yellow-500">
            等待: <span className="font-medium">{computedStats.waiting}</span>
          </span>
        )}
        {items.length > 0 && items[0].recorded_at && (
          <span className="text-[var(--terminal-muted)]">
            最近运行: {formatTime(items[0].recorded_at)}
          </span>
        )}
      </div>

      {/* 历史列表 */}
      {items.length === 0 ? (
        <div className="text-[var(--terminal-muted)] text-sm py-4 text-center">暂无历史记录</div>
      ) : (
        <div className="space-y-1">
          {pageItems.map((item, idx) => {
            const globalIdx = startIndex + idx;
            const isExpanded = expandedIndex === globalIdx;
            const displayStatus = computeDisplayStatus(item);
            const statusColor = getDisplayStatusColor(displayStatus);
            const statusLabel = getDisplayStatusLabel(displayStatus);
            const statusDesc = getStatusDescription(displayStatus, item.failure_reason, item.message);

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
                    <span className={`text-xs font-medium ${statusColor}`}>
                      {statusLabel}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    {item.recommended_symbol && (
                      <span className="text-sm font-mono text-[var(--terminal-text)]">
                        {item.recommended_symbol.replace("USDT", "")}
                      </span>
                    )}
                    <span className="text-xs text-[var(--terminal-muted)] max-w-[150px] truncate hidden sm:block">
                      {item.message || item.failure_reason}
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-[var(--terminal-muted)] flex-shrink-0" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-[var(--terminal-muted)] flex-shrink-0" />
                    )}
                  </div>
                </button>

                {/* 详情面板 */}
                {isExpanded && (
                  <div className="px-3 pb-3 pt-2 border-t border-[var(--terminal-border)]/30 bg-[var(--terminal-bg)]/50 text-xs">
                    {/* 标签页导航 */}
                    <div className="flex gap-1 mb-3 pb-2 border-b border-[var(--terminal-border)]/30">
                      {[
                        { key: "basic", label: "基础" },
                        { key: "candidates", label: "候选" },
                        { key: "tasks", label: "任务" },
                        { key: "rsi", label: "RSI" },
                      ].map((tab) => (
                        <button
                          key={tab.key}
                          onClick={() => setActiveTab((prev) => ({ ...prev, [globalIdx]: tab.key as "basic" | "candidates" | "tasks" | "rsi" }))}
                          className={`px-2 py-1 rounded text-[11px] transition-colors ${
                            (activeTab[globalIdx] || "basic") === tab.key
                              ? "bg-[var(--terminal-cyan)]/20 text-[var(--terminal-cyan)] border border-[var(--terminal-cyan)]/50"
                              : "bg-[var(--terminal-border)]/30 text-[var(--terminal-muted)] hover:bg-[var(--terminal-border)]/50"
                          }`}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>

                    {/* 基础信息标签页 */}
                    {(!activeTab[globalIdx] || activeTab[globalIdx] === "basic") && (
                      <div className="space-y-2">
                        {/* 状态说明 */}
                        <div>
                          <span className="text-[var(--terminal-muted)]">状态: </span>
                          <span className={statusColor}>{statusDesc}</span>
                        </div>

                        {/* 详细信息 */}
                        <div className="space-y-1 text-[var(--terminal-muted)]">
                          <div>模式: <span className="text-[var(--terminal-text)]">{item.mode}</span></div>
                          {item.failure_reason && <div>原因: <span className="text-[var(--terminal-text)]">{item.failure_reason}</span></div>}
                          {item.next_action && <div>建议: <span className="text-[var(--terminal-text)]">{item.next_action}</span></div>}
                        </div>
                      </div>
                    )}

                    {/* 候选币种标签页 */}
                    {activeTab[globalIdx] === "candidates" && (
                      <div>
                        {item.candidates && item.candidates.length > 0 ? (
                          <div className="space-y-2">
                            {item.candidates.map((c, i) => {
                              // 判断 gate 状态
                              const dryRunPassed = c.allowed_to_dry_run || c.dry_run_gate_status === "passed";
                              const livePassed = c.allowed_to_live || c.live_gate_status === "passed";
                              const liveReasons = c.live_gate_reasons || [];
                              const dryRunReasons = c.dry_run_gate_reasons || [];

                              return (
                                <div
                                  key={i}
                                  className="p-2 rounded border border-[var(--terminal-border)] bg-[var(--terminal-border)]/10"
                                >
                                  {/* 币种和评分 */}
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="font-mono font-medium">{c.symbol.replace("USDT", "")}</span>
                                    <span className="text-[var(--terminal-muted)]">评分: {c.score}</span>
                                  </div>

                                  {/* Gate 状态 */}
                                  <div className="flex flex-wrap gap-2 text-[11px]">
                                    {/* Dry-Run Gate */}
                                    <span className={dryRunPassed ? "text-green-400" : "text-red-400"}>
                                      {dryRunPassed ? "✅ Dry-Run 通过" : "❌ Dry-Run 未通过"}
                                    </span>

                                    {/* Live Gate */}
                                    <span className={livePassed ? "text-green-400" : "text-red-400"}>
                                      {livePassed ? "✅ Live 通过" : "❌ Live 未通过"}
                                    </span>
                                  </div>

                                  {/* 失败原因 */}
                                  {!livePassed && liveReasons.length > 0 && (
                                    <div className="mt-1 text-[11px] text-[var(--terminal-muted)]">
                                      Live 失败: {liveReasons.map(translateGateReason).join(", ")}
                                    </div>
                                  )}
                                  {!dryRunPassed && dryRunReasons.length > 0 && (
                                    <div className="mt-1 text-[11px] text-[var(--terminal-muted)]">
                                      Dry-Run 失败: {dryRunReasons.map(translateGateReason).join(", ")}
                                    </div>
                                  )}

                                  {/* 兼容旧数据的 blocked_reason */}
                                  {c.blocked_reason && !liveReasons.length && !dryRunReasons.length && (
                                    <div className="mt-1 text-[11px] text-orange-400">
                                      {translateBlockReason(c.blocked_reason)}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="text-[var(--terminal-muted)]">无候选币种</div>
                        )}
                      </div>
                    )}

                    {/* 任务执行状态标签页 */}
                    {activeTab[globalIdx] === "tasks" && (
                      <div>
                        {item.task_summary && Object.keys(item.task_summary).length > 0 ? (
                          <div className="space-y-1">
                            {Object.entries(item.task_summary).map(([name, task]) => (
                              <div
                                key={name}
                                className="flex items-center justify-between px-2 py-1.5 rounded border border-[var(--terminal-border)]/50"
                              >
                                <span className="text-[var(--terminal-text)]">{name}</span>
                                <div className="flex items-center gap-2">
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
                                    <span className="text-[var(--terminal-muted)]">
                                      {Math.round(task.duration_seconds)}s
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-[var(--terminal-muted)]">无任务记录</div>
                        )}
                      </div>
                    )}

                    {/* RSI 快照标签页 */}
                    {activeTab[globalIdx] === "rsi" && (
                      <div>
                        {item.rsi_snapshot && Object.keys(item.rsi_snapshot).length > 0 ? (
                          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                            {Object.entries(item.rsi_snapshot).map(([symbol, value]) => {
                              const rsiValue = typeof value === 'number' ? value : parseFloat(String(value)) || 0;
                              const rsiColor = rsiValue >= 70 ? "text-red-400" : rsiValue <= 30 ? "text-green-400" : "text-[var(--terminal-text)]";
                              return (
                                <span
                                  key={symbol}
                                  className="px-2 py-1 rounded border border-[var(--terminal-border)] bg-[var(--terminal-border)]/10 text-center"
                                >
                                  <span className="font-mono text-[var(--terminal-muted)]">{symbol.replace("USDT", "")}</span>:{" "}
                                  <span className={rsiColor}>{rsiValue.toFixed(1)}</span>
                                </span>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="text-[var(--terminal-muted)]">无RSI快照</div>
                        )}
                      </div>
                    )}
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
