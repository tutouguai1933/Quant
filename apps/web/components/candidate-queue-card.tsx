"use client";

/**
 * 候选队列卡片
 * 显示最新的候选币种及其评分和状态
 */

import { useEffect, useState } from "react";
import { TerminalCard } from "./terminal";
import { getAutomationCycleHistory, type AutomationCycleCandidate } from "../lib/api";

interface CandidateQueueCardProps {
  refreshInterval?: number;
  fallbackSymbols?: string[];
}

interface CandidateWithScore {
  symbol: string;
  score: number;
  status: string;
  blocked_reason: string;
}

export function CandidateQueueCard({
  refreshInterval = 60000,
  fallbackSymbols = []
}: CandidateQueueCardProps) {
  const [candidates, setCandidates] = useState<CandidateWithScore[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const response = await getAutomationCycleHistory(10);
        if (cancelled) return;

        if (response.error) {
          setError(response.error.message || "获取候选数据失败");
          // 使用fallback数据
          if (fallbackSymbols.length > 0) {
            setCandidates(fallbackSymbols.map(symbol => ({
              symbol,
              score: 0,
              status: "unknown",
              blocked_reason: ""
            })));
          }
        } else {
          const items = response.data.items || [];

          // 从最新的记录中提取候选
          let latestCandidates: CandidateWithScore[] = [];

          for (const item of items) {
            if (item.candidates && item.candidates.length > 0) {
              latestCandidates = item.candidates.map((c: AutomationCycleCandidate) => ({
                symbol: c.symbol,
                score: parseFloat(c.score) || 0,
                status: c.status || "unknown",
                blocked_reason: c.blocked_reason || ""
              }));
              break;
            }
          }

          // 如果没有候选数据，使用fallback
          if (latestCandidates.length === 0 && fallbackSymbols.length > 0) {
            latestCandidates = fallbackSymbols.map(symbol => ({
              symbol,
              score: 0,
              status: "pending",
              blocked_reason: ""
            }));
          }

          setCandidates(latestCandidates);
          setLastUpdate(new Date().toLocaleTimeString("zh-CN", { timeZone: "Asia/Shanghai" }));
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError("获取候选数据失败");
          if (fallbackSymbols.length > 0) {
            setCandidates(fallbackSymbols.map(symbol => ({
              symbol,
              score: 0,
              status: "unknown",
              blocked_reason: ""
            })));
          }
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
  }, [refreshInterval, fallbackSymbols]);

  // 获取状态颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case "ready":
      case "live_ready":
        return "text-green-400";
      case "blocked":
        return "text-red-400";
      case "skipped":
        return "text-yellow-400";
      default:
        return "text-[var(--terminal-muted)]";
    }
  };

  // 获取状态标签
  const getStatusLabel = (status: string) => {
    switch (status) {
      case "ready":
      case "live_ready":
        return "可入场";
      case "blocked":
        return "已阻止";
      case "skipped":
        return "已跳过";
      case "pending":
        return "待评估";
      default:
        return "未知";
    }
  };

  // 获取评分颜色
  const getScoreColor = (score: number) => {
    if (score >= 0.7) return "text-green-400";
    if (score >= 0.5) return "text-yellow-400";
    return "text-[var(--terminal-muted)]";
  };

  if (isLoading) {
    return (
      <TerminalCard title="最近候选队列">
        <div className="animate-pulse space-y-2">
          <div className="h-4 w-32 bg-[var(--terminal-border)] rounded" />
          <div className="flex gap-2">
            <div className="h-6 w-16 bg-[var(--terminal-border)]/30 rounded" />
            <div className="h-6 w-16 bg-[var(--terminal-border)]/30 rounded" />
          </div>
        </div>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard title="最近候选队列">
      {/* 候选数量 */}
      <div className="text-[var(--terminal-muted)] text-[12px] mb-3">
        {candidates.length} 个候选币种
        {lastUpdate && <span className="ml-2 opacity-60">更新: {lastUpdate}</span>}
      </div>

      {error && candidates.length === 0 ? (
        <div className="text-sm text-red-500">⚠️ {error}</div>
      ) : candidates.length === 0 ? (
        <div className="text-sm text-[var(--terminal-muted)]">暂无候选数据</div>
      ) : (
        <div className="space-y-2">
          {candidates.slice(0, 6).map((candidate) => (
            <div
              key={candidate.symbol}
              className="flex items-center justify-between p-2 rounded border border-[var(--terminal-border)]/50 hover:border-[var(--terminal-cyan)]/50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-[var(--terminal-text)]">
                  {candidate.symbol.replace("USDT", "")}
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${getStatusColor(candidate.status)} bg-current/10`}>
                  {getStatusLabel(candidate.status)}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs">
                {candidate.score > 0 && (
                  <span className="text-[var(--terminal-muted)]">
                    评分: <span className={getScoreColor(candidate.score)}>{candidate.score.toFixed(2)}</span>
                  </span>
                )}
                {candidate.blocked_reason && (
                  <span className="text-red-400/70 text-[10px] max-w-[100px] truncate" title={candidate.blocked_reason}>
                    {candidate.blocked_reason}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </TerminalCard>
  );
}
