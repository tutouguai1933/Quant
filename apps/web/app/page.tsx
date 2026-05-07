/**
 * 工作台首页
 * 终端风格总览页面
 */
"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import {
  TerminalShell,
  MetricCard,
  TerminalCard,
} from "../components/terminal";
import { readFeedback } from "../lib/feedback";
import { RsiSummaryCard } from "../components/rsi-summary-card";
import { TradeHistorySummaryCard } from "../components/trade-history-summary-card";
import { EntryStatusCard } from "../components/entry-status-card";
import { AutomationCycleHistoryCard } from "../components/automation-cycle-history-card";
import { SystemStatusCard } from "../components/system-status-card";
import {
  getAutomationStatus,
  getAutomationStatusFallback,
  getResearchRuntimeStatus,
  getResearchRuntimeStatusFallback,
  getStrategyWorkspace,
  getStrategyWorkspaceFallback,
  getPublicExecutorStatus,
} from "../lib/api";
import type { PublicExecutorStatus } from "../lib/api";
import { FeedbackBanner } from "../components/feedback-banner";
import { LoadingBanner } from "../components/loading-banner";
import { ErrorBanner } from "../components/error-banner";

/* 页面主组件 */
export default function HomePage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  // 状态管理
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [sessionLoaded, setSessionLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [automationStatus, setAutomationStatus] = useState(getAutomationStatusFallback().item);
  const [researchRuntime, setResearchRuntime] = useState(getResearchRuntimeStatusFallback());
  const [strategyWorkspace, setStrategyWorkspace] = useState(getStrategyWorkspaceFallback());
  const [executorStatus, setExecutorStatus] = useState<PublicExecutorStatus | null>(null);

  // 获取会话状态
  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
        setSessionLoaded(true);
      })
      .catch(() => {
        setSessionLoaded(true);
      });
  }, []);

  // 获取数据 - 等 session 加载完成后执行
  useEffect(() => {
    if (!sessionLoaded) {
      return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    // 使用 session token 进行认证
    const token = session.token || undefined;

    Promise.allSettled([
      getAutomationStatus(token, controller.signal),
      getResearchRuntimeStatus(controller.signal),
      getStrategyWorkspace(token, controller.signal),
      getPublicExecutorStatus(controller.signal),
    ])
      .then(([automationRes, runtimeRes, strategyRes, executorRes]) => {
        clearTimeout(timeoutId);

        const errors: string[] = [];

        if (automationRes.status === "fulfilled" && !automationRes.value.error) {
          setAutomationStatus(automationRes.value.data.item);
        } else if (automationRes.status === "fulfilled" && automationRes.value.error) {
          errors.push(`自动化状态加载失败: ${automationRes.value.error.message}`);
        }

        if (runtimeRes.status === "fulfilled" && !runtimeRes.value.error) {
          setResearchRuntime(runtimeRes.value.data.item);
        } else if (runtimeRes.status === "fulfilled" && runtimeRes.value.error) {
          errors.push(`研究运行状态加载失败: ${runtimeRes.value.error.message}`);
        }

        if (strategyRes.status === "fulfilled" && !strategyRes.value.error) {
          setStrategyWorkspace(strategyRes.value.data);
        } else if (strategyRes.status === "fulfilled" && strategyRes.value.error) {
          errors.push(`策略工作区加载失败: ${strategyRes.value.error.message}`);
        }

        if (executorRes.status === "fulfilled" && !executorRes.value.error) {
          setExecutorStatus(executorRes.value.data);
        }

        if (errors.length > 0) {
          setError(errors.join("; "));
          console.error("工作台数据加载错误:", errors);
        }

        setIsLoading(false);
      })
      .catch((err) => {
        clearTimeout(timeoutId);
        if (err.name !== "AbortError") {
          setError("网络请求失败，请检查网络连接");
          console.error("工作台网络错误:", err);
        }
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [sessionLoaded, session.token]);

  // 系统状态指标
  const systemMetrics = useMemo(() => {
    // 判断健康状态：优先检查 status 字段，否则检查 active_blockers
    const healthStatus = (automationStatus.health as Record<string, unknown>) || {};
    const isHealthy = healthStatus.status === "ok" ||
      (Array.isArray(healthStatus.active_blockers) && healthStatus.active_blockers.length === 0);

    // 优先使用公开 API 的执行器状态，否则使用 workspace 的状态
    const connectionStatus = executorStatus?.connection_status || strategyWorkspace.executor_runtime?.connection_status || "unknown";
    const isConnected = connectionStatus === "connected";

    return [
      {
        label: "数据更新",
        value: isHealthy ? "正常" : "异常",
        colorType: isHealthy ? "positive" as const : "negative" as const,
      },
      {
        label: "控程引擎",
        value: executorStatus ? `${executorStatus.position_count || 0} 持仓` : `${automationStatus.controlActions?.length || 0} 运行中`,
        colorType: "neutral" as const,
      },
      {
        label: "实盘连接",
        value: isConnected ? "已连接" : "断开",
        colorType: isConnected ? "positive" as const : "negative" as const,
      },
      {
        label: "研究状态",
        value: researchRuntime.status || "空闲",
        colorType: "neutral" as const,
      },
    ];
  }, [automationStatus, researchRuntime, strategyWorkspace, executorStatus]);

  // 快速导航
  const quickLinks = [
    { href: "/research", label: "模型训练", description: "训练因子模型" },
    { href: "/backtest", label: "回测训练", description: "策略回测验证" },
    { href: "/evaluation", label: "选币回测", description: "Top-K 组合回测" },
    { href: "/features", label: "因子研究", description: "IC/IR 分析" },
    { href: "/factor-knowledge", label: "因子知识库", description: "因子解释和用法" },
    { href: "/strategies", label: "实盘管理", description: "执行器状态" },
  ];

  return (
    <TerminalShell
      breadcrumb="研究 / 工作台"
      title="工作台"
      subtitle="研究、回测、执行和风险的当前状态"
      currentPath="/"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      {isLoading && <LoadingBanner />}
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="space-y-4">
        {/* 第一行：系统状态指标 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {systemMetrics.map((metric) => (
            <MetricCard
              key={metric.label}
              label={metric.label}
              value={metric.value}
              colorType={metric.colorType}
            />
          ))}
        </div>

        {/* 第二行：快速导航 */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {quickLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="terminal-card p-3 hover:border-[var(--terminal-cyan)] transition-colors"
            >
              <div className="text-[var(--terminal-text)] text-[13px] font-medium">
                {link.label}
              </div>
              <div className="text-[var(--terminal-dim)] text-[11px] mt-1">
                {link.description}
              </div>
            </Link>
          ))}
        </div>

        {/* 第三行：系统状态 + 入场状态 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SystemStatusCard refreshInterval={30000} />
          <EntryStatusCard refreshInterval={60000} />
        </div>

        {/* 第四行：RSI概览 */}
        <RsiSummaryCard refreshInterval={300000} />

        {/* 第五行：交易记录 + 候选队列 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TradeHistorySummaryCard refreshInterval={60000} />
          <TerminalCard title="最近候选队列">
            <div className="text-[var(--terminal-muted)] text-[12px]">
              {strategyWorkspace.research?.signal_count || 0} 个候选信号
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {strategyWorkspace.whitelist?.slice(0, 6).map((symbol) => (
                <span key={symbol} className="px-2 py-0.5 rounded bg-[var(--terminal-border)]/30 text-[var(--terminal-text)] text-[11px]">
                  {symbol.replace("USDT", "")}
                </span>
              ))}
            </div>
          </TerminalCard>
        </div>

        {/* 第六行：自动化周期历史 */}
        <AutomationCycleHistoryCard refreshInterval={60000} />
      </div>
    </TerminalShell>
  );
}
