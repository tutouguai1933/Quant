/* 这个文件负责把单币页组织成客户端交易工作区。 */

"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";

import {
  getMarketChart,
  getRsiHistory,
  getTradeHistory,
  type MarketChartData,
  type ResearchCandidateItem,
  type RsiHistoryData,
  type TradeHistoryData,
} from "../lib/api";
import { DataTable } from "./data-table";
import { MultiTimeframeSummary } from "./multi-timeframe-summary";
import { ResearchSidecard } from "./research-sidecard";
import { StatusBadge } from "./status-badge";
import { TradingChartPanel } from "./trading-chart-panel";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Skeleton } from "./ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";


type MarketSymbolWorkspaceProps = {
  symbol: string;
  initialData: MarketChartData;
  candidate: ResearchCandidateItem | null;
};

const chartCache = new Map<string, MarketChartData>();

/* 用客户端状态把主图区、研究侧卡和多周期摘要串起来。 */
export function MarketSymbolWorkspace({ symbol, initialData, candidate }: MarketSymbolWorkspaceProps) {
  const [chartData, setChartData] = useState(initialData);
  const [pendingInterval, setPendingInterval] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [activeTab, setActiveTab] = useState("chart");
  const [rsiHistory, setRsiHistory] = useState<RsiHistoryData | null>(null);
  const [rsiLoading, setRsiLoading] = useState(false);
  const [rsiError, setRsiError] = useState<string | null>(null);
  const [tradeHistory, setTradeHistory] = useState<TradeHistoryData | null>(null);
  const [tradeLoading, setTradeLoading] = useState(false);
  const [tradeError, setTradeError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    setChartData(initialData);
    chartCache.set(`${symbol}:${initialData.active_interval}`, initialData);
  }, [initialData, symbol]);

  // Fetch RSI history when tab is activated
  useEffect(() => {
    if (activeTab !== "rsi" || rsiHistory !== null || rsiLoading) return;

    setRsiLoading(true);
    setRsiError(null);
    getRsiHistory(symbol, chartData.active_interval)
      .then((response) => {
        if (response.error) {
          setRsiError(response.error.message || "获取RSI历史失败");
        } else {
          setRsiHistory(response.data);
        }
      })
      .catch(() => setRsiError("获取RSI历史失败，请稍后重试"))
      .finally(() => setRsiLoading(false));
  }, [activeTab, symbol, chartData.active_interval, rsiHistory, rsiLoading]);

  // Fetch trade history when tab is activated
  useEffect(() => {
    if (activeTab !== "trades" || tradeHistory !== null || tradeLoading) return;

    setTradeLoading(true);
    setTradeError(null);
    getTradeHistory(symbol, 50)
      .then((response) => {
        if (response.error) {
          setTradeError(response.error.message || "获取交易历史失败");
        } else {
          setTradeHistory(response.data);
        }
      })
      .catch(() => setTradeError("获取交易历史失败，请稍后重试"))
      .finally(() => setTradeLoading(false));
  }, [activeTab, symbol, tradeHistory, tradeLoading]);

  function handleIntervalSelect(nextInterval: string) {
    if (nextInterval === chartData.active_interval) {
      return;
    }

    requestIdRef.current += 1;
    const requestId = requestIdRef.current;
    const cacheKey = `${symbol}:${nextInterval}`;
    const cached = chartCache.get(cacheKey);
    if (cached) {
      setChartData(cached);
      setPendingInterval("");
      setErrorMessage("");
      syncIntervalToAddressBar(symbol, cached.active_interval);
      return;
    }

    setPendingInterval(nextInterval);
    setErrorMessage("");

    void getMarketChart(symbol, nextInterval)
      .then((response) => {
        if (requestIdRef.current !== requestId) {
          return;
        }

        if (response.error) {
          setErrorMessage(response.error.message || "切换周期失败。");
          return;
        }

        chartCache.set(cacheKey, response.data);
        setChartData(response.data);
        syncIntervalToAddressBar(symbol, response.data.active_interval);
      })
      .catch(() => {
        if (requestIdRef.current === requestId) {
          setErrorMessage("图表切换失败，请稍后再试。");
        }
      })
      .finally(() => {
        if (requestIdRef.current === requestId) {
          setPendingInterval("");
        }
      });
  }

  const freqtradeReadiness = chartData.freqtrade_readiness;

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-5">
      <TabsList>
        <TabsTrigger value="chart">图表</TabsTrigger>
        <TabsTrigger value="rsi">RSI历史</TabsTrigger>
        <TabsTrigger value="trades">交易历史</TabsTrigger>
      </TabsList>

      <TabsContent value="chart" className="space-y-5">
        <TradingChartPanel
          symbol={symbol}
          interval={chartData.active_interval}
          supportedIntervals={chartData.supported_intervals}
          onSelectInterval={handleIntervalSelect}
          pendingInterval={pendingInterval}
          items={chartData.items}
          overlays={chartData.overlays}
          markers={chartData.markers}
        />

        {errorMessage ? (
          <section className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5">
            <p className="eyebrow">切换反馈</p>
            <h3 className="text-lg font-semibold">图表没有切过去</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{errorMessage}</p>
          </section>
        ) : null}

        <section className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_340px] lg:items-start">
          <div className="space-y-5">
            <MultiTimeframeSummary items={chartData.multi_timeframe_summary} />
          </div>

          <div className="grid gap-4 lg:sticky lg:top-6">
            <ResearchSidecard cockpit={chartData.research_cockpit} nextStep={chartData.strategy_context.next_step} />
            <CompactDecisionCard
              symbol={symbol}
              candidate={candidate}
              entryHint={chartData.research_cockpit.entry_hint}
              stopHint={chartData.research_cockpit.stop_hint}
              nextStep={chartData.strategy_context.next_step}
              freqtradeReadiness={freqtradeReadiness}
            />
          </div>
        </section>
      </TabsContent>

      <TabsContent value="rsi">
        <RsiHistoryTabContent
          data={rsiHistory}
          loading={rsiLoading}
          error={rsiError}
          symbol={symbol}
          interval={chartData.active_interval}
        />
      </TabsContent>

      <TabsContent value="trades">
        <TradeHistoryTabContent
          data={tradeHistory}
          loading={tradeLoading}
          error={tradeError}
          symbol={symbol}
        />
      </TabsContent>
    </Tabs>
  );
}

function CompactDecisionCard({
  symbol,
  candidate,
  entryHint,
  stopHint,
  nextStep,
  freqtradeReadiness,
}: {
  symbol: string;
  candidate: ResearchCandidateItem | null;
  entryHint?: string;
  stopHint?: string;
  nextStep?: string;
  freqtradeReadiness: MarketChartData["freqtrade_readiness"];
}) {
  const gateValue = candidate ? (candidate.allowed_to_dry_run ? "ready_for_dry_run" : candidate.dry_run_gate.status) : "unavailable";
  const gateReasons = candidate?.dry_run_gate.reasons.length ? candidate.dry_run_gate.reasons.join(" / ") : "无";

  return (
    <Card className="bg-card/92">
      <CardHeader className="gap-3">
        <p className="eyebrow">执行摘要</p>
        <CardTitle>把判断压缩成一组可执行结论</CardTitle>
        <CardDescription>这里不再拉长页面，只保留当前这个币最关键的研究结论、执行准备和下一步动作。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          <CompactStat label="研究分数" value={candidate?.score ?? "n/a"} />
          <CompactStat label="研究门" valueNode={<StatusBadge value={gateValue} />} />
          <CompactStat label="入场参考" value={formatText(entryHint, "n/a")} />
          <CompactStat label="止损参考" value={formatText(stopHint, "n/a")} />
          <CompactStat label="执行模式" value={freqtradeReadiness.runtime_mode} />
          <CompactStat label="真实 dry-run" value={freqtradeReadiness.ready_for_real_freqtrade ? "ready" : "not_ready"} />
        </div>

        {candidate ? (
          <div className="rounded-2xl border border-border/70 bg-background/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">{candidate.symbol}</p>
                <p className="text-xs text-muted-foreground">{candidate.strategy_template}</p>
              </div>
              <StatusBadge value={gateValue} />
            </div>
            <div className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2 lg:grid-cols-1">
              <p>回测收益：<span className="text-foreground">{readMetric(candidate, "total_return_pct")}%</span></p>
              <p>最大回撤：<span className="text-foreground">{readMetric(candidate, "max_drawdown_pct")}%</span></p>
              <p>Sharpe：<span className="text-foreground">{readMetric(candidate, "sharpe")}</span></p>
            </div>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">失败原因：<span className="text-foreground">{gateReasons}</span></p>
          </div>
        ) : null}

        <div className="rounded-2xl border border-border/70 bg-background/50 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">下一步动作</p>
          <p className="mt-2 text-sm leading-6 text-foreground">{formatText(nextStep, "先继续观察。")}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <Button asChild>
              <Link href={`/strategies?symbol=${encodeURIComponent(symbol.toUpperCase())}`}>进入策略中心</Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href="/signals">返回信号页继续研究</Link>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CompactStat({
  label,
  value,
  valueNode,
}: {
  label: string;
  value?: string;
  valueNode?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/35 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <div className="mt-2 text-sm font-medium text-foreground">{valueNode ?? value}</div>
    </div>
  );
}

function readMetric(candidate: ResearchCandidateItem, key: string): string {
  return String(candidate.backtest.metrics[key] || "n/a");
}

/* 只更新浏览器地址栏里的周期参数，不触发整页刷新。 */
function syncIntervalToAddressBar(symbol: string, interval: string) {
  if (typeof window === "undefined") {
    return;
  }

  const url = new URL(window.location.href);
  url.pathname = `/market/${encodeURIComponent(symbol)}`;
  url.searchParams.set("interval", interval);
  window.history.replaceState(window.history.state, "", url.toString());
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}

/* RSI历史Tab内容组件 */
function RsiHistoryTabContent({
  data,
  loading,
  error,
  symbol,
  interval,
}: {
  data: RsiHistoryData | null;
  loading: boolean;
  error: string | null;
  symbol: string;
  interval: string;
}) {
  if (loading) {
    return (
      <Card className="bg-card/80">
        <CardHeader>
          <CardTitle>加载中...</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bg-card/80">
        <CardHeader>
          <p className="eyebrow">错误</p>
          <CardTitle>获取数据失败</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const rows = data?.items?.map((item) => ({
    id: String(item.timestamp),
    cells: [
      item.time,
      item.rsi_value,
      <StatusBadge key="state" value={item.state} />,
      <RsiSignalBadge key="signal" value={item.signal} />,
    ],
  })) ?? [];

  return (
    <section className="space-y-4">
      <Card className="bg-card/80">
        <CardHeader>
          <p className="eyebrow">技术指标</p>
          <CardTitle>{symbol} RSI 历史记录</CardTitle>
          <CardDescription>
            当前周期: {interval} | 共 {data?.total ?? 0} 条记录 | RSI(14)序列，超买区域(&gt;=70)和超卖区域(&lt;=30)标记。
          </CardDescription>
        </CardHeader>
      </Card>
      <DataTable
        columns={["时间", "RSI值", "状态", "信号"]}
        rows={rows}
        emptyTitle="暂无RSI历史"
        emptyDetail={`当前 ${symbol} 在 ${interval} 周期下暂无足够数据计算RSI序列（需要至少15根K线）。`}
        emptyEyebrow="数据不足"
      />
    </section>
  );
}

/* RSI信号Badge组件 */
function RsiSignalBadge({ value }: { value: string }) {
  const labelMap: Record<string, string> = {
    potential_buy: "潜在买入",
    potential_sell: "潜在卖出",
    hold: "观望",
  };

  const variantMap: Record<string, "success" | "danger" | "accent"> = {
    potential_buy: "success",
    potential_sell: "danger",
    hold: "accent",
  };

  return <StatusBadge value={labelMap[value] ?? value} />;
}

/* 交易历史Tab内容组件 */
function TradeHistoryTabContent({
  data,
  loading,
  error,
  symbol,
}: {
  data: TradeHistoryData | null;
  loading: boolean;
  error: string | null;
  symbol: string;
}) {
  if (loading) {
    return (
      <Card className="bg-card/80">
        <CardHeader>
          <CardTitle>加载中...</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bg-card/80">
        <CardHeader>
          <p className="eyebrow">错误</p>
          <CardTitle>获取数据失败</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const rows = data?.items?.map((item) => ({
    id: String(item.trade_id),
    cells: [
      formatTradeTime(item.entry_time),
      <StatusBadge key="side" value={item.side === "buy" ? "aligned" : "attention"} />,
      item.entry_price,
      item.exit_price ?? "未平仓",
      <PnlBadge key="pnl" value={item.pnl_percent} />,
      formatHoldingDuration(item.holding_duration_seconds),
      item.stop_loss_reason ?? "-",
    ],
  })) ?? [];

  return (
    <section className="space-y-4">
      <Card className="bg-card/80">
        <CardHeader>
          <p className="eyebrow">执行记录</p>
          <CardTitle>{symbol} 交易历史</CardTitle>
          <CardDescription>
            共 {data?.total_returned ?? 0} 条记录 | 显示入场价、出场价、盈亏和止损原因。
          </CardDescription>
        </CardHeader>
      </Card>
      <DataTable
        columns={["入场时间", "方向", "入场价", "出场价", "盈亏%", "持仓时长", "止损原因"]}
        rows={rows}
        emptyTitle="暂无交易记录"
        emptyDetail={`当前 ${symbol} 暂无已记录的交易历史。`}
        emptyEyebrow="无交易"
      />
    </section>
  );
}

/* 盈亏Badge组件 */
function PnlBadge({ value }: { value: string }) {
  const num = parseFloat(value);
  const isPositive = num > 0;
  const isNegative = num < 0;

  const label = isPositive ? `+${value}%` : `${value}%`;
  const variant = isPositive ? "success" : isNegative ? "danger" : "accent";

  return <StatusBadge value={label} />;
}

/* 格式化交易时间（北京时间） */
function formatTradeTime(isoString: string): string {
  try {
    const dt = new Date(isoString);
    return dt.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Shanghai",
    });
  } catch {
    return isoString;
  }
}

/* 格式化持仓时长 */
function formatHoldingDuration(seconds: number | null): string {
  if (seconds === null) return "-";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}
