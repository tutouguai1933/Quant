/* 数据分析页面，展示交易统计、盈亏归因和策略表现。 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { BarChart3, TrendingUp, TrendingDown, Activity, Calendar, Clock } from "lucide-react";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { PageHero } from "../../components/page-hero";
import { Skeleton } from "../../components/ui/skeleton";
import { StatusBar } from "../../components/status-bar";
import { StatusBadge } from "../../components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { readFeedback } from "../../lib/feedback";
import {
  getAnalyticsStatus,
  getAnalyticsStatusFallback,
  getAnalyticsDailySummary,
  getAnalyticsDailySummaryFallback,
  getAnalyticsWeeklySummary,
  getAnalyticsWeeklySummaryFallback,
  getAnalyticsPnlAttribution,
  getAnalyticsStrategyPerformance,
  getAnalyticsTradeHistory,
  AnalyticsServiceStatus,
  AnalyticsDailySummary,
  AnalyticsWeeklySummary,
  AnalyticsPnlAttribution,
  AnalyticsStrategyPerformance,
  AnalyticsTradeRecord,
} from "../../lib/api";

export default function AnalyticsPage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);

  const [serviceStatus, setServiceStatus] = useState<AnalyticsServiceStatus>(getAnalyticsStatusFallback());
  const [dailySummary, setDailySummary] = useState<AnalyticsDailySummary>(getAnalyticsDailySummaryFallback());
  const [weeklySummary, setWeeklySummary] = useState<AnalyticsWeeklySummary>(getAnalyticsWeeklySummaryFallback());
  const [pnlAttribution, setPnlAttribution] = useState<AnalyticsPnlAttribution | null>(null);
  const [strategyPerformances, setStrategyPerformances] = useState<AnalyticsStrategyPerformance[]>([]);
  const [tradeHistory, setTradeHistory] = useState<AnalyticsTradeRecord[]>([]);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {
        // Keep default session state
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    Promise.allSettled([
      getAnalyticsStatus(controller.signal),
      getAnalyticsDailySummary(undefined, controller.signal),
      getAnalyticsWeeklySummary(undefined, controller.signal),
      getAnalyticsPnlAttribution(undefined, controller.signal),
      getAnalyticsStrategyPerformance(undefined, controller.signal),
      getAnalyticsTradeHistory({ limit: 50 }, controller.signal),
    ])
      .then(([statusRes, dailyRes, weeklyRes, attributionRes, performanceRes, historyRes]) => {
        clearTimeout(timeoutId);

        if (statusRes.status === "fulfilled" && !statusRes.value.error) {
          setServiceStatus(statusRes.value.data?.status || getAnalyticsStatusFallback());
        }
        if (dailyRes.status === "fulfilled" && !dailyRes.value.error) {
          setDailySummary(dailyRes.value.data?.summary || getAnalyticsDailySummaryFallback());
        }
        if (weeklyRes.status === "fulfilled" && !weeklyRes.value.error) {
          setWeeklySummary(weeklyRes.value.data?.summary || getAnalyticsWeeklySummaryFallback());
        }
        if (attributionRes.status === "fulfilled" && !attributionRes.value.error) {
          setPnlAttribution(attributionRes.value.data?.attribution || null);
        }
        if (performanceRes.status === "fulfilled" && !performanceRes.value.error) {
          setStrategyPerformances(performanceRes.value.data?.performances || []);
        }
        if (historyRes.status === "fulfilled" && !historyRes.value.error) {
          setTradeHistory(historyRes.value.data?.trades || []);
        }

        setIsLoading(false);
      })
      .catch(() => {
        clearTimeout(timeoutId);
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  const statusItems = [
    {
      label: "服务状态",
      value: serviceStatus.status,
      status: serviceStatus.status === "ready" ? "success" : "waiting",
      detail: `历史${serviceStatus.history_days}天`,
    },
    {
      label: "交易记录",
      value: String(serviceStatus.trade_count),
      status: serviceStatus.trade_count > 0 ? "active" : "waiting",
      detail: serviceStatus.last_sync_at ? `最近同步: ${formatTime(serviceStatus.last_sync_at)}` : "等待同步",
    },
    {
      label: "今日盈亏",
      value: formatPnl(dailySummary.total_pnl),
      status: parseFloat(dailySummary.total_pnl) >= 0 ? "success" : "error",
      detail: `${dailySummary.trade_count}笔交易`,
    },
    {
      label: "本周盈亏",
      value: formatPnl(weeklySummary.total_pnl),
      status: parseFloat(weeklySummary.total_pnl) >= 0 ? "success" : "error",
      detail: `胜率: ${formatPercent(weeklySummary.win_rate)}`,
    },
  ];

  const symbolAttributionList = pnlAttribution ? Object.values(pnlAttribution.by_symbol) : [];
  const strategyAttributionList = pnlAttribution ? Object.values(pnlAttribution.by_strategy) : [];

  return (
    <AppShell
      title="数据分析"
      subtitle="交易统计、盈亏归因、策略表现和交易历史"
      currentPath="/analytics"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="Analytics"
        title="交易数据分析"
        description="查看每日/每周统计、盈亏归因分析、策略表现对比和交易历史记录"
      />

      <StatusBar items={statusItems} />

      {isLoading ? (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-48 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
          </div>
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* 每日/每周统计卡片 */}
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="bg-card/90">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <Calendar className="size-4 text-primary" />
                  <p className="eyebrow">每日统计</p>
                </div>
                <CardTitle>{dailySummary.date}</CardTitle>
                <CardDescription>
                  {dailySummary.trade_count}笔交易 | 胜率 {formatPercent(dailySummary.win_rate)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <InfoBlock label="总盈亏" value={formatPnl(dailySummary.total_pnl)} />
                  <InfoBlock label="胜率" value={formatPercent(dailySummary.win_rate)} />
                  <InfoBlock label="盈利笔数" value={String(dailySummary.win_count)} />
                  <InfoBlock label="亏损笔数" value={String(dailySummary.loss_count)} />
                  <InfoBlock label="平均盈亏" value={formatPnl(dailySummary.avg_pnl)} />
                  <InfoBlock label="最大盈利" value={formatPnl(dailySummary.max_profit)} />
                </div>
                {dailySummary.symbols.length > 0 && (
                  <div className="pt-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">交易标的</p>
                    <p className="mt-2 text-sm text-foreground">{dailySummary.symbols.join(", ")}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="bg-card/90">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <Calendar className="size-4 text-primary" />
                  <p className="eyebrow">每周统计</p>
                </div>
                <CardTitle>{weeklySummary.week_start} ~ {weeklySummary.week_end}</CardTitle>
                <CardDescription>
                  {weeklySummary.trade_count}笔交易 | 胜率 {formatPercent(weeklySummary.win_rate)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <InfoBlock label="总盈亏" value={formatPnl(weeklySummary.total_pnl)} />
                  <InfoBlock label="胜率" value={formatPercent(weeklySummary.win_rate)} />
                  <InfoBlock label="盈利笔数" value={String(weeklySummary.win_count)} />
                  <InfoBlock label="亏损笔数" value={String(weeklySummary.loss_count)} />
                  <InfoBlock label="最佳日" value={weeklySummary.best_day || "无"} />
                  <InfoBlock label="最差日" value={weeklySummary.worst_day || "无"} />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 盈亏归因分析 */}
          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <BarChart3 className="size-4 text-primary" />
                <p className="eyebrow">盈亏归因</p>
              </div>
              <CardTitle>盈亏归因分析</CardTitle>
              <CardDescription>
                按标的和策略分组分析盈亏来源
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="symbol">
                <TabsList>
                  <TabsTrigger value="symbol">按标的</TabsTrigger>
                  <TabsTrigger value="strategy">按策略</TabsTrigger>
                  <TabsTrigger value="top">最佳/最差</TabsTrigger>
                </TabsList>

                <TabsContent value="symbol" className="mt-4">
                  <DataTable
                    columns={["标的", "交易数", "买入", "卖出", "总盈亏"]}
                    rows={symbolAttributionList.map((item) => ({
                      id: item.symbol,
                      cells: [
                        item.symbol,
                        String(item.trade_count),
                        String(item.buy_count),
                        String(item.sell_count),
                        <PnlValue key={item.symbol} value={item.total_pnl} />,
                      ],
                    }))}
                    emptyTitle="暂无归因数据"
                    emptyDetail="等待交易记录"
                  />
                </TabsContent>

                <TabsContent value="strategy" className="mt-4">
                  <DataTable
                    columns={["策略", "交易数", "总盈亏"]}
                    rows={strategyAttributionList.map((item) => ({
                      id: String(item.strategy_id || "unknown"),
                      cells: [
                        item.strategy_name,
                        String(item.trade_count),
                        <PnlValue key={String(item.strategy_id)} value={item.total_pnl} />,
                      ],
                    }))}
                    emptyTitle="暂无归因数据"
                    emptyDetail="等待交易记录"
                  />
                </TabsContent>

                <TabsContent value="top" className="mt-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <Card className="bg-[color:var(--panel-strong)]/80">
                      <CardHeader>
                        <div className="flex items-center gap-2">
                          <TrendingUp className="size-4 text-green-500" />
                          <CardTitle className="text-base">盈利标的 TOP 5</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent>
                        {(pnlAttribution?.top_profit_symbols?.length ?? 0) > 0 ? (
                          <ul className="space-y-2">
                            {pnlAttribution?.top_profit_symbols?.map((item, idx) => (
                              <li key={item.symbol} className="flex items-center justify-between text-sm">
                                <span>{idx + 1}. {item.symbol}</span>
                                <span className="text-green-500 font-medium">{item.total_pnl}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-sm text-muted-foreground">暂无盈利记录</p>
                        )}
                      </CardContent>
                    </Card>

                    <Card className="bg-[color:var(--panel-strong)]/80">
                      <CardHeader>
                        <div className="flex items-center gap-2">
                          <TrendingDown className="size-4 text-red-500" />
                          <CardTitle className="text-base">亏损标的 TOP 5</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent>
                        {(pnlAttribution?.top_loss_symbols?.length ?? 0) > 0 ? (
                          <ul className="space-y-2">
                            {pnlAttribution?.top_loss_symbols?.map((item, idx) => (
                              <li key={item.symbol} className="flex items-center justify-between text-sm">
                                <span>{idx + 1}. {item.symbol}</span>
                                <span className="text-red-500 font-medium">{item.total_pnl}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-sm text-muted-foreground">暂无亏损记录</p>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          {/* 策略表现对比 */}
          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Activity className="size-4 text-primary" />
                <p className="eyebrow">策略表现</p>
              </div>
              <CardTitle>策略表现对比</CardTitle>
              <CardDescription>
                按策略维度对比交易表现、胜率和收益
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DataTable
                columns={["策略", "交易数", "总盈亏", "胜率", "平均盈亏", "Sharpe"]}
                rows={strategyPerformances.map((item) => ({
                  id: String(item.strategy_id || "unknown"),
                  cells: [
                    item.strategy_name,
                    String(item.trade_count),
                    <PnlValue key={String(item.strategy_id)} value={item.total_pnl} />,
                    formatPercent(item.win_rate),
                    formatPnl(item.avg_pnl),
                    item.sharpe_ratio ? formatDecimal(item.sharpe_ratio) : "N/A",
                  ],
                }))}
                emptyTitle="暂无策略表现数据"
                emptyDetail="等待交易记录"
              />
            </CardContent>
          </Card>

          {/* 交易历史 */}
          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Clock className="size-4 text-primary" />
                <p className="eyebrow">交易历史</p>
              </div>
              <CardTitle>交易历史记录</CardTitle>
              <CardDescription>
                最近 {tradeHistory.length} 笔交易记录
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DataTable
                columns={["时间", "标的", "方向", "数量", "价格", "盈亏"]}
                rows={tradeHistory.map((item) => ({
                  id: item.trade_id,
                  cells: [
                    formatTime(item.executed_at),
                    item.symbol,
                    <StatusBadge key={item.trade_id} value={item.side} />,
                    item.quantity,
                    item.price,
                    <PnlValue key={item.trade_id} value={item.pnl} />,
                  ],
                }))}
                emptyTitle="暂无交易历史"
                emptyDetail="等待交易执行"
              />
            </CardContent>
          </Card>
        </div>
      )}
    </AppShell>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-base font-semibold text-foreground">{value}</p>
    </div>
  );
}

function PnlValue({ value }: { value: string }) {
  const num = parseFloat(value);
  const isPositive = num >= 0;
  const colorClass = num > 0 ? "text-green-500" : num < 0 ? "text-red-500" : "text-foreground";
  return (
    <span className={`font-medium ${colorClass}`}>
      {isPositive ? "+" : ""}{formatDecimal(value)}
    </span>
  );
}

function formatPnl(value: string): string {
  const num = parseFloat(value);
  const sign = num >= 0 ? "+" : "";
  return `${sign}${formatDecimal(value)}`;
}

function formatPercent(value: string): string {
  const num = parseFloat(value);
  return `${(num * 100).toFixed(1)}%`;
}

function formatDecimal(value: string): string {
  const num = parseFloat(value);
  if (Math.abs(num) < 0.0001) return "0";
  return num.toFixed(8);
}

function formatTime(value: string): string {
  try {
    const date = new Date(value);
    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}