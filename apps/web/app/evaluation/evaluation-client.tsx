/**
 * 选币回测页面
 * 复刻参考图 2 的终端化布局
 * 顶部：参数条、候选池 chip
 * 中间：指标卡
 * 底部：组合净值图
 */
"use client";

import { useEffect, useState, useMemo } from "react";

import {
  TerminalShell,
  ControlPanel,
  FieldRow,
  TerminalInput,
  TerminalSelect,
  SegmentedControl,
  ChipList,
  MetricStrip,
  PortfolioEquityChart,
} from "../../components/terminal";
import {
  getEvaluationWorkspace,
  getEvaluationWorkspaceFallback,
  type EvaluationWorkspaceModel,
} from "../../lib/api";
import { ErrorBanner } from "../../components/error-banner";

/* 快速时间区间 */
const QUICK_DATE_RANGES = [
  { value: "1m", label: "近1月" },
  { value: "3m", label: "近3月" },
  { value: "1y", label: "近1年" },
  { value: "3y", label: "近3年" },
  { value: "5y", label: "近5年" },
  { value: "ytd", label: "YTD" },
];

/* 页面属性 */
type EvaluationClientProps = {
  token: string | null;
  isAuthenticated: boolean;
};

/* 页面主组件 */
export function EvaluationClient({ token, isAuthenticated }: EvaluationClientProps) {
  // 状态管理
  const [workspace, setWorkspace] = useState<EvaluationWorkspaceModel>(getEvaluationWorkspaceFallback());
  const [isLoading, setIsLoading] = useState(true);

  // 表单状态
  const [mode, setMode] = useState("model"); // model 或 factor
  const [selectedDateRange, setSelectedDateRange] = useState("5y");
  const [topK, setTopK] = useState("3");
  const [rebalanceDays, setRebalanceDays] = useState("5");

  // 获取工作区数据
  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    getEvaluationWorkspace(controller.signal)
      .then((response) => {
        clearTimeout(timeoutId);
        if (!response.error) {
          setWorkspace(response.data.item);
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

  // 构建候选池 chip 列表
  const candidateChips = useMemo(() => {
    const symbols = workspace.candidate_scope?.candidate_symbols || [];
    if (symbols.length === 0) {
      return [
        { label: "BTCUSDT", value: "BTCUSDT", active: false },
        { label: "ETHUSDT", value: "ETHUSDT", active: false },
        { label: "SOLUSDT", value: "SOLUSDT", active: false },
        { label: "BNBUSDT", value: "BNBUSDT", active: false },
        { label: "XRPUSDT", value: "XRPUSDT", active: false },
      ];
    }
    return symbols.slice(0, 30).map((s) => ({
      label: s,
      value: s,
      active: false,
    }));
  }, [workspace]);

  // 构建指标卡数据（优先使用 terminal.metrics）
  const metrics = useMemo(() => {
    const terminalMetrics = workspace.terminal?.metrics || [];

    // 辅助函数：根据 key 查找指标值
    const getMetric = (key: string): string => {
      const m = terminalMetrics.find((item) => item.key === key);
      return m?.value || "--";
    };

    return [
      {
        label: "总收益",
        value: getMetric("best_net_return_pct"),
        colorType: getMetric("best_net_return_pct") && parseFloat(getMetric("best_net_return_pct")) >= 0 ? "positive" as const : "negative" as const,
      },
      {
        label: "年化",
        value: getMetric("annual_return_pct"),
        colorType: "neutral" as const,
      },
      {
        label: "Sharpe",
        value: getMetric("sharpe"),
        colorType: "neutral" as const,
      },
      {
        label: "最大回撤",
        value: getMetric("best_max_drawdown_pct"),
        colorType: "negative" as const,
      },
      {
        label: "超额收益",
        value: getMetric("excess_return_pct"),
        colorType: getMetric("excess_return_pct") && parseFloat(getMetric("excess_return_pct")) >= 0 ? "positive" as const : "negative" as const,
      },
      {
        label: "平均换手",
        value: getMetric("turnover"),
        colorType: "neutral" as const,
      },
    ];
  }, [workspace]);

  // 构建组合净值数据
  const portfolioData = useMemo(() => {
    const series = workspace.terminal?.charts?.top_candidate_nav?.series || [];
    // 转换为 PortfolioEquityChart 期望的格式，过滤掉没有 portfolio 值的数据
    return series
      .map((item) => {
        const result: { date: string; portfolio: number; benchmark?: number } = {
          date: item.date,
          portfolio: 1.0, // 默认值
        };
        // 提取第一个非日期字段作为 portfolio 值
        const keys = Object.keys(item).filter((k) => k !== "date");
        if (keys.length > 0) {
          const val = item[keys[0]];
          result.portfolio = typeof val === "number" ? val : parseFloat(String(val)) || 1.0;
          if (keys.includes("benchmark") && item.benchmark !== undefined) {
            result.benchmark = typeof item.benchmark === "number" ? item.benchmark : parseFloat(String(item.benchmark));
          }
        }
        return result;
      })
      .filter((item) => !isNaN(item.portfolio));
  }, [workspace]);

  if (isLoading) {
    return (
      <div className="text-center py-20 text-[var(--terminal-muted)]">
        加载中...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 顶部参数大卡 */}
      <ControlPanel title="参数配置">
        {/* 模式切换 */}
        <div className="mb-4">
          <SegmentedControl
            value={mode}
            onChange={setMode}
            options={[
              { value: "factor", label: "因子打分" },
              { value: "model", label: "模型打分" },
            ]}
          />
          <p className="text-[var(--terminal-dim)] text-[11px] mt-2">
            {mode === "model"
              ? "用已训练的 LightGBM 模型预测收益并排序"
              : "用单因子打分进行排序选币"}
          </p>
        </div>

        {/* 参数表单 */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <FieldRow label="候选池">
            <TerminalSelect
              value="research_top30"
              onChange={() => {}}
              options={[
                { value: "research_top30", label: "研究候选前30" },
                { value: "live_allowed", label: "执行篮子" },
              ]}
            />
          </FieldRow>
          <FieldRow label="已训练模型">
            <TerminalSelect
              value="lgbm_v1"
              onChange={() => {}}
              options={[
                { value: "lgbm_v1", label: "lgbm_v1 · rank · IC=0.08" },
                { value: "lstm_v1", label: "lstm_v1 · rank · IC=0.05" },
              ]}
            />
          </FieldRow>
          <FieldRow label="Top K">
            <TerminalInput value={topK} onChange={setTopK} type="number" />
          </FieldRow>
          <FieldRow label="调仓天数">
            <TerminalInput value={rebalanceDays} onChange={setRebalanceDays} type="number" />
          </FieldRow>
          <FieldRow label="开始日期">
            <TerminalInput value="2021/04/26" onChange={() => {}} type="date" />
          </FieldRow>
          <FieldRow label="结束日期">
            <TerminalInput value="2026/04/26" onChange={() => {}} type="date" />
          </FieldRow>
        </div>

        {/* 快速选择 */}
        <div className="mt-3">
          <SegmentedControl
            value={selectedDateRange}
            onChange={setSelectedDateRange}
            options={QUICK_DATE_RANGES}
            size="small"
          />
        </div>

        {/* 运行按钮 */}
        <div className="mt-4">
          <button type="button" className="terminal-btn" disabled={!isAuthenticated}>
            运行选币回测
          </button>
        </div>
      </ControlPanel>

      {/* 候选池成员 */}
      <div className="terminal-card p-4">
        <div className="text-[var(--terminal-muted)] text-[11px] mb-2">
          候选池成员 ({candidateChips.length})
        </div>
        <ChipList items={candidateChips} />
      </div>

      {/* 指标卡 */}
      <MetricStrip metrics={metrics} />

      {/* 组合净值图 */}
      <PortfolioEquityChart
        data={portfolioData}
        height={400}
      />
    </div>
  );
}
