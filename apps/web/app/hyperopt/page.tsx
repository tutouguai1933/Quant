/**
 * 参数优化页面
 * Freqtrade Hyperopt 参数优化
 */
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import {
  TerminalShell,
  TerminalCard,
  MetricCard,
  InfoBlock,
} from "../../components/terminal";
import { Button } from "../../components/ui/button";
import { StatusBadge } from "../../components/status-badge";
import { Skeleton } from "../../components/ui/skeleton";
import {
  getHyperoptStatus,
  listHyperoptJobs,
  startHyperopt,
  stopHyperopt,
  type HyperoptStatus,
  type HyperoptJob,
} from "../../lib/api";

export default function HyperoptPage() {
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [status, setStatus] = useState<HyperoptStatus>({ status: "idle" });
  const [jobs, setJobs] = useState<HyperoptJob[]>([]);
  const [isStarting, setIsStarting] = useState(false);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!session.isAuthenticated) {
      setIsLoading(false);
      return;
    }

    const fetchStatus = async () => {
      const statusRes = await getHyperoptStatus();
      if (!statusRes.error && statusRes.data) {
        setStatus(statusRes.data);
      }

      const jobsRes = await listHyperoptJobs(20);
      if (!jobsRes.error && jobsRes.data?.jobs) {
        setJobs(jobsRes.data.jobs);
      }
    };

    fetchStatus();
    setIsLoading(false);

    // Poll every 5 seconds when running
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [session.isAuthenticated]);

  const handleStartHyperopt = async () => {
    setIsStarting(true);
    try {
      const result = await startHyperopt("EnhancedStrategy", 100, ["buy", "sell", "roi", "stoploss"], "1h");
      if (!result.error && result.data) {
        setStatus(result.data);
      }
    } catch (error) {
      console.error("Failed to start hyperopt:", error);
    }
    setIsStarting(false);
  };

  const handleStopHyperopt = async () => {
    try {
      await stopHyperopt();
      setStatus((prev) => ({ ...prev, status: "idle" }));
    } catch (error) {
      console.error("Failed to stop hyperopt:", error);
    }
  };

  const statusMetrics = [
    {
      label: "优化状态",
      value: status.status === "running" ? "运行中" : status.status === "completed" ? "已完成" : "空闲",
      colorType: status.status === "running" ? ("positive" as const) : status.status === "failed" ? ("negative" as const) : ("neutral" as const),
    },
    {
      label: "当前轮次",
      value: status.current_epoch && status.total_epochs ? `${status.current_epoch}/${status.total_epochs}` : "--",
      colorType: "neutral" as const,
    },
    {
      label: "最佳收益",
      value: status.best_result ? `${(status.best_result * 100).toFixed(2)}%` : "--",
      colorType: status.best_result && status.best_result > 0 ? ("positive" as const) : ("neutral" as const),
    },
    {
      label: "历史任务",
      value: String(jobs.length),
      colorType: "neutral" as const,
    },
  ];

  return (
    <TerminalShell
      breadcrumb="研究 / 参数优化"
      title="参数优化"
      subtitle="Freqtrade Hyperopt 策略参数调优"
      currentPath="/hyperopt"
      isAuthenticated={session.isAuthenticated}
    >
      {!session.isAuthenticated ? (
        <TerminalCard title="需要登录">
          <div className="space-y-3">
            <p className="text-sm text-[var(--terminal-muted)]">
              登录后才能使用参数优化功能。
            </p>
            <Button asChild variant="terminal">
              <Link href="/login?next=%2Fhyperopt">先去登录</Link>
            </Button>
          </div>
        </TerminalCard>
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-20 rounded-lg" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
      ) : (
        <>
          {/* 状态指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {statusMetrics.map((metric) => (
              <MetricCard
                key={metric.label}
                label={metric.label}
                value={metric.value}
                colorType={metric.colorType}
              />
            ))}
          </div>

          {/* 控制面板 */}
          <TerminalCard>
            <div className="flex items-center gap-3 mb-4">
              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">优化控制</span>
            </div>

            <div className="flex gap-3 mb-4">
              <Button
                variant="terminal"
                size="sm"
                disabled={status.status === "running" || isStarting}
                onClick={handleStartHyperopt}
              >
                {isStarting ? "启动中..." : "启动优化"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={status.status !== "running"}
                onClick={handleStopHyperopt}
              >
                停止优化
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/tasks">查看任务</Link>
              </Button>
            </div>

            {status.status === "running" && (
              <div className="rounded border border-[var(--terminal-cyan)]/50 bg-[var(--terminal-cyan)]/10 p-3">
                <div className="flex items-center gap-2 text-sm text-[var(--terminal-cyan)]">
                  <div className="w-2 h-2 rounded-full bg-[var(--terminal-cyan)] animate-pulse" />
                  <span>正在优化中，预计完成时间：{status.total_epochs && status.current_epoch ?
                    `${Math.ceil((status.total_epochs - (status.current_epoch || 0)) * 0.5)} 分钟` : "计算中..."}</span>
                </div>
              </div>
            )}
          </TerminalCard>

          {/* 当前优化结果 */}
          {status.status !== "idle" && (
            <TerminalCard title="优化结果">
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                <InfoBlock label="状态" value={status.status} />
                <InfoBlock
                  label="进度"
                  value={status.current_epoch && status.total_epochs
                    ? `${status.current_epoch} / ${status.total_epochs}`
                    : "--"}
                />
                <InfoBlock
                  label="最佳收益"
                  value={status.best_result
                    ? `${(status.best_result * 100).toFixed(2)}%`
                    : "--"}
                />
                <InfoBlock
                  label="开始时间"
                  value={status.started_at
                    ? new Date(status.started_at).toLocaleString("zh-CN")
                    : "--"}
                />
              </div>

              {status.parameters && Object.keys(status.parameters).length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)] mb-2">最佳参数</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[12px]">
                      <thead>
                        <tr className="border-b border-[var(--terminal-border)]">
                          <th className="text-left py-2 px-2 text-[var(--terminal-dim)]">参数名</th>
                          <th className="text-left py-2 px-2 text-[var(--terminal-dim)]">参数值</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(status.parameters).map(([key, value]) => (
                          <tr key={key} className="border-b border-[var(--terminal-border)]/50">
                            <td className="py-2 px-2 text-[var(--terminal-text)]">{key}</td>
                            <td className="py-2 px-2 text-[var(--terminal-accent)] font-mono">{String(value)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </TerminalCard>
          )}

          {/* 历史任务 */}
          <TerminalCard title="历史优化任务">
            {jobs.length === 0 ? (
              <div className="text-center py-8 text-[var(--terminal-muted)]">
                暂无历史优化任务，点击"启动优化"开始第一次参数调优
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-[var(--terminal-border)]">
                      <th className="text-left py-2 px-2 text-[var(--terminal-dim)]">策略</th>
                      <th className="text-center py-2 px-2 text-[var(--terminal-dim)]">周期</th>
                      <th className="text-center py-2 px-2 text-[var(--terminal-dim)]">轮次</th>
                      <th className="text-center py-2 px-2 text-[var(--terminal-dim)]">最佳收益</th>
                      <th className="text-center py-2 px-2 text-[var(--terminal-dim)]">状态</th>
                      <th className="text-center py-2 px-2 text-[var(--terminal-dim)]">时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => (
                      <tr key={job.id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-bg-hover)]">
                        <td className="py-2 px-2 text-[var(--terminal-text)]">{job.strategy}</td>
                        <td className="py-2 px-2 text-center text-[var(--terminal-text)]">{job.timeframe}</td>
                        <td className="py-2 px-2 text-center text-[var(--terminal-text)]">{job.epochs}</td>
                        <td className="py-2 px-2 text-center">
                          <span className={job.best_profit && job.best_profit > 0
                            ? "text-[var(--terminal-green)]"
                            : "text-[var(--terminal-text)]"}>
                            {job.best_profit ? `${(job.best_profit * 100).toFixed(2)}%` : "--"}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-center">
                          <StatusBadge value={job.status} />
                        </td>
                        <td className="py-2 px-2 text-center text-[var(--terminal-muted)]">
                          {new Date(job.created_at).toLocaleString("zh-CN")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </TerminalCard>

          {/* 使用说明 */}
          <TerminalCard title="使用说明">
            <div className="space-y-2 text-sm text-[var(--terminal-muted)]">
              <p>1. 参数优化使用 Freqtrade Hyperopt 功能，自动寻找最优策略参数</p>
              <p>2. 优化过程会运行多轮回测，每轮尝试不同的参数组合</p>
              <p>3. 优化完成后，最佳参数会自动保存到策略配置</p>
              <p>4. 建议在非交易时段运行优化，避免影响实盘交易</p>
            </div>
          </TerminalCard>
        </>
      )}
    </TerminalShell>
  );
}
