/* 报告查看器组件，展示日报、周报和报告历史。 */
"use client";

import { FileText, Calendar, TrendingUp, TrendingDown, BarChart3, Clock, Download, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";

type DailyReport = {
  date: string;
  generated_at: string;
  trade_summary: {
    trade_count: number;
    buy_count: number;
    sell_count: number;
    symbols: string[];
  };
  pnl_summary: {
    total_pnl: string;
    win_count: number;
    loss_count: number;
    win_rate: string;
    avg_pnl: string;
    max_profit: string;
    max_loss: string;
  };
  position_status: {
    open_positions: number;
    unrealized_pnl: string;
  };
  risk_metrics: {
    daily_pnl_ratio: number;
    max_single_loss: number;
    trade_frequency: number;
    risk_level: string;
  };
  factor_analysis: {
    top_factors: string[];
    weak_factors: string[];
    recommendations: string[];
  };
  markdown_content: string;
};

type WeeklyReport = {
  week_start: string;
  week_end: string;
  generated_at: string;
  strategy_performance: {
    strategies: Array<{
      strategy_name: string;
      trade_count: number;
      total_pnl: string;
      win_rate: string;
    }>;
    best_strategy: string | null;
    total_strategies: number;
  };
  risk_analysis: {
    week_pnl: string;
    win_rate: string;
    best_day: string;
    worst_day: string;
    pnl_volatility: string;
  };
  factor_analysis: {
    effectiveness: Array<{
      factor_name: string;
      effectiveness_score: number;
      stability_score: number;
      recommendation: string;
    }>;
    recommendations: string[];
  };
  daily_breakdown: Array<{
    date: string;
    total_pnl: string;
    trade_count: number;
  }>;
  recommendations: string[];
  markdown_content: string;
};

type ReportHistoryItem = {
  date?: string;
  week_start?: string;
  week_end?: string;
  generated_at: string;
  trade_count: number;
  total_pnl: string;
};

export function ReportViewer() {
  const [dailyReport, setDailyReport] = useState<DailyReport | null>(null);
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReport | null>(null);
  const [history, setHistory] = useState<ReportHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [selectedWeek, setSelectedWeek] = useState<string>("");
  const [viewMode, setViewMode] = useState<"json" | "markdown">("json");

  useEffect(() => {
    fetchDailyReport();
    fetchWeeklyReport();
    fetchHistory();
  }, []);

  const fetchDailyReport = async (date?: string) => {
    setLoading(true);
    setError(null);
    try {
      const url = date
        ? `/api/v1/report/daily?date=${date}&format=${viewMode}`
        : `/api/v1/report/daily?format=${viewMode}`;
      const res = await fetch(url);
      const data = await res.json();
      if (data.error) {
        setError(data.error.message);
      } else {
        setDailyReport(data.data.report);
      }
    } catch (e) {
      setError("获取日报失败");
    } finally {
      setLoading(false);
    }
  };

  const fetchWeeklyReport = async (weekStart?: string) => {
    try {
      const url = weekStart
        ? `/api/v1/report/weekly?week_start=${weekStart}&format=${viewMode}`
        : `/api/v1/report/weekly?format=${viewMode}`;
      const res = await fetch(url);
      const data = await res.json();
      if (!data.error) {
        setWeeklyReport(data.data.report);
      }
    } catch (e) {
      // 忽略周报获取失败
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/v1/report/history?limit=10");
      const data = await res.json();
      if (!data.error) {
        setHistory(data.data.history);
      }
    } catch (e) {
      // 忽略历史获取失败
    }
  };

  const handleRefresh = () => {
    fetchDailyReport(selectedDate);
    fetchWeeklyReport(selectedWeek);
    fetchHistory();
  };

  const handleDownloadMarkdown = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getPnlColor = (pnl: string) => {
    const value = parseFloat(pnl);
    if (value > 0) return "text-green-500";
    if (value < 0) return "text-red-500";
    return "text-muted-foreground";
  };

  const getRiskLevelBadge = (level: string) => {
    switch (level) {
      case "low":
        return <Badge variant="success">低风险</Badge>;
      case "medium":
        return <Badge variant="warning">中风险</Badge>;
      case "high":
        return <Badge variant="danger">高风险</Badge>;
      default:
        return <Badge variant="neutral">{level}</Badge>;
    }
  };

  return (
    <div className="space-y-4">
      {/* 控制栏 */}
      <Card className="bg-card/90">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText className="size-4 text-primary" />
              <CardTitle className="text-base">交易报告</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleRefresh}>
                <RefreshCw className="size-3 mr-1" />
                刷新
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {loading && <div className="text-center py-8 text-muted-foreground">加载中...</div>}
      {error && <div className="text-center py-8 text-red-500">{error}</div>}

      <Tabs defaultValue="daily">
        <TabsList>
          <TabsTrigger value="daily">日报</TabsTrigger>
          <TabsTrigger value="weekly">周报</TabsTrigger>
          <TabsTrigger value="history">历史</TabsTrigger>
        </TabsList>

        {/* 日报内容 */}
        <TabsContent value="daily">
          {dailyReport && (
            <div className="space-y-4">
              {/* 交易汇总 */}
              <Card className="bg-card/90">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Calendar className="size-4 text-primary" />
                      <CardTitle className="text-base">
                        日报 - {dailyReport.date}
                      </CardTitle>
                    </div>
                    {getRiskLevelBadge(dailyReport.risk_metrics.risk_level)}
                  </div>
                </CardHeader>
                <CardContent className="pt-2">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="border rounded-md p-3">
                      <div className="text-sm text-muted-foreground">交易次数</div>
                      <div className="text-xl font-bold">{dailyReport.trade_summary.trade_count}</div>
                      <div className="text-xs text-muted-foreground">
                        买 {dailyReport.trade_summary.buy_count} / 卖 {dailyReport.trade_summary.sell_count}
                      </div>
                    </div>
                    <div className="border rounded-md p-3">
                      <div className="text-sm text-muted-foreground">总盈亏</div>
                      <div className={`text-xl font-bold ${getPnlColor(dailyReport.pnl_summary.total_pnl)}`}>
                        {dailyReport.pnl_summary.total_pnl}
                      </div>
                    </div>
                    <div className="border rounded-md p-3">
                      <div className="text-sm text-muted-foreground">胜率</div>
                      <div className="text-xl font-bold">
                        {(parseFloat(dailyReport.pnl_summary.win_rate) * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground">
                        胜 {dailyReport.pnl_summary.win_count} / 负 {dailyReport.pnl_summary.loss_count}
                      </div>
                    </div>
                    <div className="border rounded-md p-3">
                      <div className="text-sm text-muted-foreground">平均盈亏</div>
                      <div className={`text-xl font-bold ${getPnlColor(dailyReport.pnl_summary.avg_pnl)}`}>
                        {dailyReport.pnl_summary.avg_pnl}
                      </div>
                    </div>
                  </div>

                  {/* 持仓状态 */}
                  <div className="mt-4 border rounded-md p-3">
                    <div className="text-sm font-medium mb-2">持仓状态</div>
                    <div className="flex items-center gap-4">
                      <span className="text-muted-foreground">
                        开仓: {dailyReport.position_status.open_positions}
                      </span>
                      <span className={`text-muted-foreground ${getPnlColor(dailyReport.position_status.unrealized_pnl)}`}>
                        未实现: {dailyReport.position_status.unrealized_pnl}
                      </span>
                    </div>
                  </div>

                  {/* 因子分析 */}
                  {dailyReport.factor_analysis.top_factors.length > 0 && (
                    <div className="mt-4">
                      <div className="text-sm font-medium mb-2">因子分析</div>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">主要因子:</span>
                        {dailyReport.factor_analysis.top_factors.map((f) => (
                          <Badge key={f} variant="success">{f}</Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Markdown下载 */}
                  <div className="mt-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDownloadMarkdown(
                        dailyReport.markdown_content,
                        `daily-report-${dailyReport.date}.md`
                      )}
                    >
                      <Download className="size-3 mr-1" />
                      下载Markdown
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* 周报内容 */}
        <TabsContent value="weekly">
          {weeklyReport && (
            <div className="space-y-4">
              {/* 策略表现 */}
              <Card className="bg-card/90">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <BarChart3 className="size-4 text-primary" />
                    <CardTitle className="text-base">
                      周报 - {weeklyReport.week_start} 至 {weeklyReport.week_end}
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="pt-2">
                  {/* 风险分析 */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="border rounded-md p-3">
                      <div className="text-sm text-muted-foreground">本周盈亏</div>
                      <div className={`text-xl font-bold ${getPnlColor(weeklyReport.risk_analysis.week_pnl)}`}>
                        {weeklyReport.risk_analysis.week_pnl}
                      </div>
                    </div>
                    <div className="border rounded-md p-3">
                      <div className="text-sm text-muted-foreground">胜率</div>
                      <div className="text-xl font-bold">
                        {(parseFloat(weeklyReport.risk_analysis.win_rate) * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="border rounded-md p-3">
                      <div className="text-sm text-muted-foreground">最佳日</div>
                      <div className="text-sm font-medium">
                        {weeklyReport.risk_analysis.best_day || "暂无"}
                      </div>
                    </div>
                    <div className="border rounded-md p-3">
                      <div className="text-sm text-muted-foreground">最差日</div>
                      <div className="text-sm font-medium">
                        {weeklyReport.risk_analysis.worst_day || "暂无"}
                      </div>
                    </div>
                  </div>

                  {/* 每日明细 */}
                  <div className="border rounded-md divide-y">
                    <div className="p-2 bg-muted/30 text-sm font-medium">每日明细</div>
                    {weeklyReport.daily_breakdown.map((day) => (
                      <div key={day.date} className="p-2 flex items-center justify-between text-sm">
                        <span>{day.date}</span>
                        <span className={getPnlColor(day.total_pnl)}>
                          PnL: {day.total_pnl}
                        </span>
                        <span className="text-muted-foreground">
                          交易: {day.trade_count}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* 策略表现 */}
                  {weeklyReport.strategy_performance.strategies.length > 0 && (
                    <div className="mt-4 border rounded-md divide-y">
                      <div className="p-2 bg-muted/30 text-sm font-medium">策略表现</div>
                      {weeklyReport.strategy_performance.strategies.map((s) => (
                        <div key={s.strategy_name} className="p-2 flex items-center justify-between text-sm">
                          <span className="font-medium">{s.strategy_name}</span>
                          <span className={getPnlColor(s.total_pnl)}>
                            {s.total_pnl}
                          </span>
                          <span className="text-muted-foreground">
                            胜率: {(parseFloat(s.win_rate) * 100).toFixed(1)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 建议 */}
                  {weeklyReport.recommendations.length > 0 && (
                    <div className="mt-4">
                      <div className="text-sm font-medium mb-2">本周建议</div>
                      <ul className="text-sm space-y-1">
                        {weeklyReport.recommendations.map((rec, i) => (
                          <li key={i} className="flex items-start gap-2">
                            {rec.includes("盈利") ? (
                              <TrendingUp className="size-3 mt-0.5 text-green-500" />
                            ) : rec.includes("亏损") ? (
                              <TrendingDown className="size-3 mt-0.5 text-red-500" />
                            ) : (
                              <Clock className="size-3 mt-0.5 text-primary" />
                            )}
                            <span className="text-muted-foreground">{rec}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Markdown下载 */}
                  <div className="mt-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDownloadMarkdown(
                        weeklyReport.markdown_content,
                        `weekly-report-${weeklyReport.week_start}.md`
                      )}
                    >
                      <Download className="size-3 mr-1" />
                      下载Markdown
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* 历史记录 */}
        <TabsContent value="history">
          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Clock className="size-4 text-primary" />
                <CardTitle className="text-base">报告历史</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-2">
              {history.length === 0 ? (
                <div className="text-center py-4 text-muted-foreground">暂无历史记录</div>
              ) : (
                <div className="border rounded-md divide-y">
                  {history.map((item, i) => (
                    <div key={i} className="p-3 flex items-center justify-between">
                      <div>
                        <span className="font-medium">
                          {item.date || `${item.week_start} ~ ${item.week_end}`}
                        </span>
                        <span className="text-xs text-muted-foreground ml-2">
                          {new Date(item.generated_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <span className={getPnlColor(item.total_pnl)}>
                          {item.total_pnl}
                        </span>
                        <span className="text-muted-foreground">
                          交易: {item.trade_count}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}