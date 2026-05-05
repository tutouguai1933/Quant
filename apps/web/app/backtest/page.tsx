/**
 * 回测训练页面
 * 复刻参考图 1 的终端化布局
 * 左侧：策略配置/风控参数/回测区间
 * 右侧：指标卡、净值曲线图、回撤图、资金对比
 */
"use client";

import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";

import {
  TerminalShell,
  ControlPanel,
  FieldRow,
  TerminalInput,
  TerminalSelect,
  SegmentedControl,
  ChipList,
  MetricStrip,
  EquityCurveChart,
  DrawdownChart,
  FundsBridge,
  TerminalTabs,
} from "../../components/terminal";
import { readFeedback } from "../../lib/feedback";
import {
  getBacktestWorkspace,
  getBacktestWorkspaceFallback,
  type BacktestWorkspaceModel,
} from "../../lib/api";
import { FeedbackBanner } from "../../components/feedback-banner";
import { LoadingBanner } from "../../components/loading-banner";

/* 快速时间区间 */
const QUICK_DATE_RANGES = [
  { value: "1m", label: "近1月" },
  { value: "3m", label: "近3月" },
  { value: "1y", label: "近1年" },
  { value: "3y", label: "近3年" },
  { value: "5y", label: "近5年" },
];

/* 策略标签类型 */
type StrategyTag = {
  label: string;
  value: string;
  active: boolean;
  type: "ml" | "rule" | "default";
};

/* 页面主组件 */
export default function BacktestPage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  // 状态管理
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [workspace, setWorkspace] = useState<BacktestWorkspaceModel>(getBacktestWorkspaceFallback());
  const [isLoading, setIsLoading] = useState(true);

  // 表单状态
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [symbolName, setSymbolName] = useState("Bitcoin");
  const [selectedDateRange, setSelectedDateRange] = useState("5y");
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(["ma_cross"]);
  const [activeTab, setActiveTab] = useState("equity");

  // 获取会话状态
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

  // 获取工作区数据
  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    getBacktestWorkspace()
      .then((response) => {
        clearTimeout(timeoutId);
        if (!response.error) {
          setWorkspace(response.data.item);
          // 初始化表单
          if (response.data.item.overview.recommended_symbol) {
            setSymbol(response.data.item.overview.recommended_symbol);
          }
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

  // 构建策略 chip 列表
  const strategyChips = useMemo((): StrategyTag[] => {
    const strategies = workspace.leaderboard.map((item) => ({
      label: item.strategy_template || item.symbol,
      value: item.strategy_template || item.symbol,
      active: selectedStrategies.includes(item.strategy_template || item.symbol),
      type: (item.strategy_template?.includes("model") ? "ml" : "rule") as "ml" | "rule" | "default",
    }));
    return strategies.length > 0 ? strategies : [
      { label: "ma_cross", value: "ma_cross", active: true, type: "rule" },
      { label: "model_infer", value: "model_infer", active: false, type: "ml" },
      { label: "rsi_reversion", value: "rsi_reversion", active: false, type: "rule" },
      { label: "lgbm_rolling", value: "lgbm_rolling", active: false, type: "ml" },
    ];
  }, [workspace, selectedStrategies]);

  // 处理策略选择
  const handleStrategyChange = (value: string) => {
    setSelectedStrategies((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]
    );
  };

  // 构建指标卡数据
  const metrics = useMemo(() => {
    const m = workspace.training_backtest.metrics || {};
    return [
      {
        label: "年化收益",
        value: m.annual_return_pct || "--",
        detail: m.net_return_pct ? `累计 ${m.net_return_pct}` : undefined,
        colorType: m.annual_return_pct && parseFloat(m.annual_return_pct) >= 0 ? "positive" as const : "negative" as const,
      },
      {
        label: "夏普比率",
        value: m.sharpe || "--",
        detail: m.calmar || m.sortino ? `Calmar ${m.calmar || "--"} · Sortino ${m.sortino || "--"}` : undefined,
        colorType: "neutral" as const,
      },
      {
        label: "最大回撤",
        value: m.max_drawdown_pct || "--",
        detail: m.volatility ? `波动率 ${m.volatility}` : undefined,
        colorType: "negative" as const,
      },
      {
        label: "胜率 / 盈亏比",
        value: m.win_rate ? `${m.win_rate} / ${m.profit_loss_ratio || "--"}` : "--",
        detail: m.trade_count ? `交易 ${m.trade_count} 次` : undefined,
        colorType: "neutral" as const,
      },
    ];
  }, [workspace]);

  // 构建净值曲线数据（从 terminal.charts.performance.series 获取）
  const equityData = useMemo(() => {
    const series = workspace.terminal?.charts?.performance?.series || [];
    return series.map((item) => ({
      date: item.date,
      value: item.strategy_nav,
      benchmark: item.benchmark_nav,
    }));
  }, [workspace]);

  // 构建回撤数据
  const drawdownData = useMemo(() => {
    const series = workspace.terminal?.charts?.performance?.series || [];
    return series.map((item) => ({
      date: item.date,
      drawdown: item.drawdown_pct || 0,
    }));
  }, [workspace]);

  // 候选币种选项
  const symbolOptions = useMemo(() => {
    const symbols = workspace.leaderboard.map((item) => item.symbol);
    return symbols.length > 0
      ? symbols.map((s) => ({ value: s, label: s }))
      : [
          { value: "BTCUSDT", label: "BTCUSDT" },
          { value: "ETHUSDT", label: "ETHUSDT" },
          { value: "SOLUSDT", label: "SOLUSDT" },
        ];
  }, [workspace]);

  return (
    <TerminalShell
      breadcrumb="研究 / 回测训练"
      title="回测训练"
      subtitle="单标的策略回测，跑出可部署的策略版本"
      currentPath="/backtest"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      {isLoading && <LoadingBanner />}

      {/* 主布局：左侧参数栏 + 右侧内容 */}
      <div className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        {/* 左侧：参数配置 */}
        <div className="space-y-4">
          {/* 策略配置 */}
          <ControlPanel title="策略配置">
            {/* 标的代码 */}
            <FieldRow label="标的代码">
              <TerminalInput
                value={symbol}
                onChange={setSymbol}
                placeholder="BTCUSDT"
              />
            </FieldRow>

            {/* 标的名称 */}
            <FieldRow label="标的名称">
              <TerminalInput
                value={symbolName}
                onChange={setSymbolName}
                placeholder="Bitcoin"
              />
            </FieldRow>

            {/* 资产类型 */}
            <FieldRow label="资产类型">
              <TerminalSelect
                value="crypto"
                onChange={() => {}}
                options={[{ value: "crypto", label: "加密货币" }]}
              />
            </FieldRow>

            {/* 频率 */}
            <FieldRow label="频率">
              <TerminalSelect
                value="4h"
                onChange={() => {}}
                options={[
                  { value: "1h", label: "1小时" },
                  { value: "4h", label: "4小时" },
                  { value: "1d", label: "日线" },
                ]}
              />
            </FieldRow>

            {/* 策略选择 */}
            <FieldRow label="策略（可多选）">
              <ChipList
                items={strategyChips}
                onChange={handleStrategyChange}
                multiSelect
              />
            </FieldRow>

            {/* 初始资金 */}
            <FieldRow label="初始资金（USDT）">
              <TerminalInput
                value="1000"
                onChange={() => {}}
                type="number"
              />
            </FieldRow>
          </ControlPanel>

          {/* 风控参数 */}
          <ControlPanel title="风控参数">
            <div className="grid grid-cols-2 gap-2">
              <FieldRow label="最大持仓天数">
                <TerminalInput value="10" onChange={() => {}} type="number" />
              </FieldRow>
              <FieldRow label="单币仓位">
                <TerminalInput value="100%" onChange={() => {}} />
              </FieldRow>
              <FieldRow label="单币止损">
                <TerminalInput value="8%" onChange={() => {}} />
              </FieldRow>
            </div>
          </ControlPanel>

          {/* 回测区间 */}
          <ControlPanel title="回测区间">
            <FieldRow label="快速选择">
              <SegmentedControl
                value={selectedDateRange}
                onChange={setSelectedDateRange}
                options={QUICK_DATE_RANGES}
                size="small"
              />
            </FieldRow>
          </ControlPanel>
        </div>

        {/* 右侧：指标和图表 */}
        <div className="space-y-4">
          {/* 指标卡 */}
          <MetricStrip metrics={metrics} />

          {/* 图表 Tabs */}
          <div className="terminal-chart-panel">
            <TerminalTabs
              value={activeTab}
              onChange={setActiveTab}
              options={[
                { value: "equity", label: "净值曲线" },
                { value: "kline", label: "K线" },
                { value: "trades", label: "交易记录" },
                { value: "config", label: "策略配置" },
              ]}
            />
            <div className="pt-4">
              {activeTab === "equity" && (
                <>
                  <EquityCurveChart data={equityData} height={320} />
                  <DrawdownChart data={drawdownData} height={100} className="mt-4" />
                </>
              )}
              {activeTab === "kline" && (
                <div className="text-center text-[var(--terminal-muted)] py-20">
                  K线图暂未实现，请使用市场页面查看
                </div>
              )}
              {activeTab === "trades" && (
                <div className="text-center text-[var(--terminal-muted)] py-20">
                  暂无交易记录数据
                </div>
              )}
              {activeTab === "config" && (
                <div className="text-center text-[var(--terminal-muted)] py-20">
                  策略配置详情请在左侧调整
                </div>
              )}
            </div>
          </div>

          {/* 资金对比 */}
          <FundsBridge
            initialFunds={1000}
            returnPct={workspace.training_backtest.metrics?.net_return_pct || "--"}
            finalFunds="--"
            currency="USDT"
          />
        </div>
      </div>
    </TerminalShell>
  );
}
