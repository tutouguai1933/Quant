/**
 * 因子研究页面
 * 复刻参考图 3 的终端化布局
 * 顶部：参数条
 * 中间：指标卡
 * 底部：分位组合净值图 + IC 时间序列图
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
  MetricStrip,
  QuantileNetChart,
  IcBarChart,
} from "../../components/terminal";
import { readFeedback } from "../../lib/feedback";
import {
  getFeatureWorkspace,
  getFeatureWorkspaceFallback,
  type FeatureWorkspaceModel,
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
  { value: "ytd", label: "YTD" },
];

/* 因子分类 */
const FACTOR_CATEGORIES = [
  { key: "trend", label: "趋势" },
  { key: "momentum", label: "动量" },
  { key: "oscillator", label: "震荡" },
  { key: "volume", label: "量能" },
  { key: "volatility", label: "波动" },
];

/* 页面主组件 */
export default function FeaturesPage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  // 状态管理
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [workspace, setWorkspace] = useState<FeatureWorkspaceModel>(getFeatureWorkspaceFallback());
  const [isLoading, setIsLoading] = useState(true);

  // 表单状态
  const [selectedFactor, setSelectedFactor] = useState("mom_20");
  const [selectedDateRange, setSelectedDateRange] = useState("5y");
  const [forward, setForward] = useState("5");

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

    getFeatureWorkspace(controller.signal)
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

  // 构建因子选项
  const factorOptions = useMemo(() => {
    const factors = workspace.controls.available_primary_factors || [];
    if (factors.length === 0) {
      return [
        { value: "mom_20", label: "mom_20 — 20根K线动量" },
        { value: "rsi_14", label: "rsi_14 — 14根K线 RSI" },
        { value: "vol_20", label: "vol_20 — 20根K线波动" },
      ];
    }
    return factors.map((f) => ({
      value: f,
      label: f,
    }));
  }, [workspace]);

  // 构建币种池选项
  const universeOptions = useMemo(() => {
    return [
      { value: "research_candidates", label: "研究候选池 (16)" },
      { value: "live_allowed", label: "执行篮子 (5)" },
    ];
  }, []);

  // 构建指标卡数据
  const metrics = useMemo(() => {
    const eff = (workspace.effectiveness_summary as Record<string, unknown>) || {};
    const readValue = (key: string): string => {
      const v = eff[key];
      if (v === null || v === undefined) return "--";
      if (typeof v === "string" || typeof v === "number") return String(v);
      return "--";
    };

    return [
      {
        label: "IC 均值",
        value: readValue("ic_mean"),
        colorType: "neutral" as const,
      },
      {
        label: "IC 标准差",
        value: readValue("ic_std"),
        colorType: "neutral" as const,
      },
      {
        label: "IR",
        value: readValue("ir"),
        colorType: "neutral" as const,
      },
      {
        label: "IC 胜率",
        value: readValue("ic_win_rate"),
        colorType: "neutral" as const,
      },
      {
        label: "币种池",
        value: String(workspace.factors?.length || 0),
        colorType: "neutral" as const,
      },
    ];
  }, [workspace]);

  return (
    <TerminalShell
      breadcrumb="研究 / 因子研究"
      title="因子研究"
      subtitle="IC / IR / 分位组合"
      currentPath="/features"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      {isLoading && <LoadingBanner />}

      {/* 顶部参数条 */}
      <ControlPanel title="参数配置">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <FieldRow label="因子">
            <TerminalSelect
              value={selectedFactor}
              onChange={setSelectedFactor}
              options={factorOptions}
            />
          </FieldRow>
          <FieldRow label="币种池">
            <TerminalSelect
              value="research_candidates"
              onChange={() => {}}
              options={universeOptions}
            />
          </FieldRow>
          <FieldRow label="开始日期">
            <TerminalInput value="2021/04/26" onChange={() => {}} type="date" />
          </FieldRow>
          <FieldRow label="结束日期">
            <TerminalInput value="2026/04/26" onChange={() => {}} type="date" />
          </FieldRow>
          <FieldRow label="Forward（天）">
            <TerminalInput value={forward} onChange={setForward} type="number" />
          </FieldRow>
        </div>

        <div className="mt-3 flex items-center justify-between">
          <SegmentedControl
            value={selectedDateRange}
            onChange={setSelectedDateRange}
            options={QUICK_DATE_RANGES}
            size="small"
          />
          <button type="button" className="terminal-btn" disabled={!session.isAuthenticated}>
            运行分析
          </button>
        </div>
      </ControlPanel>

      {/* 指标卡 */}
      <MetricStrip metrics={metrics} />

      {/* 图表区：左右两张图 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <QuantileNetChart data={[]} height={300} />
        <IcBarChart data={[]} height={300} />
      </div>
    </TerminalShell>
  );
}
