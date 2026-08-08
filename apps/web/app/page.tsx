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
import { CoreNumberCard, HomeMoreDetails } from "../components/home-workbench-grid";
import { readFeedback } from "../lib/feedback";
import { RsiSummaryCard } from "../components/rsi-summary-card";
import { TradeHistorySummaryCard } from "../components/trade-history-summary-card";
import { EntryStatusCard } from "../components/entry-status-card";
import { AutomationCycleHistoryCard } from "../components/automation-cycle-history-card";
import { DualStrategyCard } from "../components/dual-strategy-card";
import { CandidateQueueCard } from "../components/candidate-queue-card";
import {
  getAutomationStatus,
  getAutomationStatusFallback,
  getResearchRuntimeStatus,
  getResearchRuntimeStatusFallback,
  getPublicExecutorStatus,
  fetchJson,
} from "../lib/api";
import type { PublicExecutorStatus } from "../lib/api";
import { FeedbackBanner } from "../components/feedback-banner";
import { Loader2 } from "lucide-react";
import { ErrorBanner } from "../components/error-banner";
import { OpenPositionsCard } from "../components/open-positions-card";

/* 持仓汇总（/freqtrade/open-trades 返回的汇总字段） */
type OpenTradesSummary = {
  total_profit: number;
  total_profit_pct: number;
  total_stake: number;
  count: number;
};

/* 加载持仓汇总：失败时标记降级，页面显示"数据暂不可用" */
async function getPositionsSummary(token?: string, signal?: AbortSignal) {
  const response = await fetchJson<OpenTradesSummary>("/freqtrade/open-trades", token, signal);
  if (response.error) {
    return { data: null as OpenTradesSummary | null, degraded: true };
  }
  return { data: response.data, degraded: false };
}

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
  const [executorStatus, setExecutorStatus] = useState<PublicExecutorStatus | null>(null);
  const [positionsSummary, setPositionsSummary] = useState<OpenTradesSummary | null>(null);
  // 三个核心数字的数据是否降级（接口失败时置 true，卡片显示"数据暂不可用"）
  const [positionsDegraded, setPositionsDegraded] = useState(false);
  const [automationDegraded, setAutomationDegraded] = useState(false);
  const [executorDegraded, setExecutorDegraded] = useState(false);

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
      getPublicExecutorStatus(controller.signal),
      getPositionsSummary(token, controller.signal),
    ])
      .then(([automationRes, runtimeRes, executorRes, positionsRes]) => {
        clearTimeout(timeoutId);

        const errors: string[] = [];

        if (automationRes.status === "fulfilled" && !automationRes.value.error) {
          setAutomationStatus(automationRes.value.data.item);
        } else if (automationRes.status === "fulfilled" && automationRes.value.error) {
          errors.push(`自动化状态加载失败: ${automationRes.value.error.message}`);
          setAutomationDegraded(true);
        }

        if (runtimeRes.status === "fulfilled" && !runtimeRes.value.error) {
          setResearchRuntime(runtimeRes.value.data.item);
        } else if (runtimeRes.status === "fulfilled" && runtimeRes.value.error) {
          errors.push(`研究运行状态加载失败: ${runtimeRes.value.error.message}`);
        }

        if (executorRes.status === "fulfilled" && !executorRes.value.error) {
          setExecutorStatus(executorRes.value.data);
        } else if (executorRes.status === "fulfilled" && executorRes.value.error) {
          setExecutorDegraded(true);
        }

        if (positionsRes.status === "fulfilled") {
          setPositionsSummary(positionsRes.value.data);
          setPositionsDegraded(positionsRes.value.degraded);
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
    const connectionStatus = executorStatus?.connection_status || "unknown";
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
  }, [automationStatus, researchRuntime, executorStatus]);

  // 首屏 3 个核心数字：持仓盈亏 / 自动化状态 / 执行器健康
  const coreNumbers = useMemo(() => {
    // 1. 持仓盈亏：总盈亏 USDT + 浮盈 %
    const profit = positionsSummary?.total_profit;
    const profitPct = positionsSummary?.total_profit_pct;
    const positionsValue =
      profit !== undefined && profit !== null
        ? `${profit >= 0 ? "+" : ""}${profit.toFixed(3)} USDT`
        : "--";
    const positionsDetail =
      profitPct !== undefined && profitPct !== null
        ? `浮盈 ${profitPct >= 0 ? "+" : ""}${profitPct.toFixed(2)}% · ${positionsSummary?.count ?? 0} 笔持仓`
        : `${positionsSummary?.count ?? 0} 笔持仓`;

    // 2. 自动化状态：模式 + 今日周期数
    const runtimeGuard = (automationStatus.runtimeGuard ?? {}) as Record<string, unknown>;
    const cyclesToday = Number(runtimeGuard.cycles_today ?? 0);
    const modeLabel =
      automationStatus.mode === "auto_live"
        ? "自动实盘"
        : automationStatus.mode === "auto_dry_run"
          ? "自动模拟"
          : "手动";
    const automationDetail = `${cyclesToday > 0 ? `今日 ${cyclesToday} 次周期 · ` : ""}${automationStatus.paused ? "已暂停" : "运行中"}`;

    // 3. 执行器健康：freqtrade 连接状态 + 持仓数
    const connectionStatus =
      executorStatus?.connection_status || "unknown";
    const isConnected = connectionStatus === "connected";
    const executorValue = executorStatus ? (isConnected ? "已连接" : "断开") : "未知";
    const executorDetail = executorStatus
      ? `${executorStatus.position_count || 0} 个持仓 · ${executorStatus.mode || ""}`
      : "暂无执行器信息";

    return { positionsValue, positionsDetail, modeLabel, automationDetail, executorValue, executorDetail };
  }, [positionsSummary, automationStatus, executorStatus]);

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
      {/* 紧凑加载指示：不阻塞首屏，卡片始终渲染（fallback 值），数据到位后渐进更新 */}
      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>数据加载中...</span>
        </div>
      )}
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

        {/* 第二行：首屏 3 个核心数字 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <CoreNumberCard
            label="持仓盈亏"
            value={coreNumbers.positionsValue}
            detail={coreNumbers.positionsDetail}
            href="/positions"
            tone={positionsSummary && positionsSummary.total_profit >= 0 ? "positive" : "negative"}
            degraded={positionsDegraded}
          />
          <CoreNumberCard
            label="自动化状态"
            value={coreNumbers.modeLabel}
            detail={coreNumbers.automationDetail}
            href="/tasks"
            tone={automationStatus.mode === "manual" ? "negative" : "positive"}
            degraded={automationDegraded}
          />
          <CoreNumberCard
            label="执行器健康"
            value={coreNumbers.executorValue}
            detail={coreNumbers.executorDetail}
            href="/strategies"
            tone={coreNumbers.executorValue === "已连接" ? "positive" : "negative"}
            degraded={executorDegraded}
          />
        </div>

        {/* 第三行：快速导航 */}
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

        {/* 更多详情：完整卡片收进折叠区，默认收起减少首屏信息量 */}
        <HomeMoreDetails title="更多详情">
          {/* 双策略状态 + 市场入场信号 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <DualStrategyCard refreshInterval={30000} />
            <EntryStatusCard />
          </div>

          {/* 当前持仓详情 */}
          <OpenPositionsCard refreshInterval={30000} />

          {/* RSI概览 */}
          <RsiSummaryCard refreshInterval={300000} />

          {/* 两个策略的交易记录 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <TradeHistorySummaryCard strategyType="enhanced" refreshInterval={60000} />
            <TradeHistorySummaryCard strategyType="automation" refreshInterval={60000} />
          </div>

          {/* 自动化周期候选 */}
          <CandidateQueueCard
            refreshInterval={60000}
            fallbackSymbols={[]}
          />

          {/* 自动化周期历史 */}
          <AutomationCycleHistoryCard refreshInterval={60000} />
        </HomeMoreDetails>
      </div>
    </TerminalShell>
  );
}
