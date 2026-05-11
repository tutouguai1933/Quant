"use client";

/**
 * 自动化周期候选卡片
 * 显示ML模型评分的候选币种及其入场状态
 * 数据来源：自动化周期历史的 candidates 字段
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
  dry_run_gate_status: string;
  live_gate_status: string;
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
          if (fallbackSymbols.length > 0) {
            setCandidates(fallbackSymbols.map(symbol => ({
              symbol,
              score: 0,
              status: "unknown",
              blocked_reason: "",
              dry_run_gate_status: "",
              live_gate_status: "",
            })));
          }
        } else {
          const items = response.data.items || [];
          let latestCandidates: CandidateWithScore[] = [];

          for (const item of items) {
            if (item.candidates && item.candidates.length > 0) {
              latestCandidates = item.candidates.map((c: AutomationCycleCandidate) => ({
                symbol: c.symbol,
                score: parseFloat(c.score) || 0,
                status: c.status || "unknown",
                blocked_reason: c.blocked_reason || "",
                dry_run_gate_status: c.dry_run_gate_status || "",
                live_gate_status: c.live_gate_status || "",
              }));
              break;
            }
          }

          if (latestCandidates.length === 0 && fallbackSymbols.length > 0) {
            latestCandidates = fallbackSymbols.map(symbol => ({
              symbol,
              score: 0,
              status: "pending",
              blocked_reason: "",
              dry_run_gate_status: "",
              live_gate_status: "",
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
              blocked_reason: "",
              dry_run_gate_status: "",
              live_gate_status: "",
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

  const getStatusColor = (status: string, dryRunGate: string, liveGate: string) => {
    if (liveGate === "passed") return "text-green-400";
    if (dryRunGate === "passed") return "text-yellow-400";
    if (dryRunGate === "failed" || liveGate === "failed") return "text-red-400";
    return "text-[var(--terminal-muted)]";
  };

  const getStatusLabel = (status: string, dryRunGate: string, liveGate: string) => {
    if (liveGate === "passed") return "可Live";
    if (dryRunGate === "passed") return "可Dry";
    if (dryRunGate === "failed" || liveGate === "failed") return "已阻止";
    return "待评估";
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.9) return "text-green-400";
    if (score >= 0.7) return "text-yellow-400";
    return "text-[var(--terminal-muted)]";
  };

  if (isLoading) {
    return (
      <TerminalCard title="自动化周期候选">
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
    <TerminalCard title="自动化周期候选">
      <div className="text-[var(--terminal-muted)] text-[12px] mb-3 flex justify-between">
        <span>
          {candidates.length} 个候选币种
          <span className="ml-2 text-[var(--terminal-cyan)]">ML模型评分</span>
        </span>
        {lastUpdate && <span className="opacity-60">更新: {lastUpdate}</span>}
      </div>

      {error && candidates.length === 0 ? (
        <div className="text-sm text-red-500">⚠️ {error}</div>
      ) : candidates.length === 0 ? (
        <div className="text-sm text-[var(--terminal-muted)]">暂无候选数据</div>
      ) : (
        <div className="space-y-2">
          {candidates.slice(0, 6).map((candidate) => {
            const statusColor = getStatusColor(
              candidate.status,
              candidate.dry_run_gate_status,
              candidate.live_gate_status
            );
            const statusLabel = getStatusLabel(
              candidate.status,
              candidate.dry_run_gate_status,
              candidate.live_gate_status
            );

            return (
              <div
                key={candidate.symbol}
                className="flex items-center justify-between p-2 rounded border border-[var(--terminal-border)]/50 hover:border-[var(--terminal-cyan)]/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-[var(--terminal-text)]">
                    {candidate.symbol.replace("USDT", "")}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${statusColor} bg-current/10`}>
                    {statusLabel}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  {candidate.score > 0 && (
                    <span className="text-[var(--terminal-muted)]">
                      ML评分: <span className={getScoreColor(candidate.score)}>{candidate.score.toFixed(2)}</span>
                    </span>
                  )}
                  {candidate.blocked_reason && (
                    <span className="text-red-400/70 text-[10px] max-w-[100px] truncate" title={candidate.blocked_reason}>
                      {candidate.blocked_reason}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </TerminalCard>
  );
}
