/**
 * 因子知识库页面
 * 复刻参考图 4 的终端化布局
 * 顶部：术语速查
 * 中间：分类 chip + 搜索框
 * 底部：因子卡网格
 */
"use client";

import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";

import {
  TerminalShell,
  ChipList,
  FactorCardGrid,
  TermGrid,
} from "../../components/terminal";
import { readFeedback } from "../../lib/feedback";
import {
  getFeatureWorkspace,
  getFeatureWorkspaceFallback,
  type FeatureWorkspaceModel,
} from "../../lib/api";
import { FeedbackBanner } from "../../components/feedback-banner";
import { LoadingBanner } from "../../components/loading-banner";

/* 因子分类 */
const FACTOR_CATEGORIES = [
  "全部",
  "波动",
  "技术指标",
  "量能",
  "动量",
  "价格形态",
  "反转",
];

/* 示例因子数据 */
const SAMPLE_FACTORS = [
  {
    name: "rsi_14",
    category: "技术指标",
    description: "14根K线 RSI",
    formula: "相对强弱指数，14根K线。范围 0-100。",
    whyEffective: "衡量过去14根K线涨跌力量对比。>70 过热，<30 超卖。",
    howToUse: "方向=-1（低值做多）。RSI<30 时做多，RSI>50 时卖出。",
    pitfalls: "趋势币种可以长期保持 RSI > 80。",
    recommendedWith: "经典 RSI 反转策略",
    currentRole: "primary",
  },
  {
    name: "mom_20",
    category: "动量",
    description: "20根K线动量",
    formula: "close / close_20 - 1",
    whyEffective: "衡量过去20根K线的价格变化幅度。",
    howToUse: "方向=+1，动量越大越可能延续。",
    pitfalls: "震荡市里动量信号会频繁失效。",
  },
  {
    name: "vol_20",
    category: "波动",
    description: "20根K线波动率",
    formula: "std(close, 20) / mean(close, 20)",
    whyEffective: "低波动币种更稳定，适合风险控制。",
    howToUse: "方向=-1，选低波动币种。",
    pitfalls: "和 range_pct 有冗余。",
  },
  {
    name: "volume_ratio",
    category: "量能",
    description: "成交量比率",
    formula: "volume / sma(volume, 20)",
    whyEffective: "放量突破更可靠。",
    howToUse: "方向=+1，配合突破信号。",
    pitfalls: "币种间成交量差异大，需要标准化。",
  },
];

/* 页面主组件 */
export default function FactorKnowledgePage() {
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

  // 筛选状态
  const [selectedCategory, setSelectedCategory] = useState("全部");
  const [searchQuery, setSearchQuery] = useState("");

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

  // 构建因子列表
  const factors = useMemo(() => {
    // 如果后端有因子数据，使用后端数据
    if (workspace.factors && workspace.factors.length > 0) {
      return workspace.factors.map((f) => ({
        name: f.name,
        category: f.category,
        description: f.description,
        currentRole: f.role,
      }));
    }
    // 否则使用示例数据
    return SAMPLE_FACTORS;
  }, [workspace]);

  // 筛选后的因子
  const filteredFactors = useMemo(() => {
    return factors.filter((f) => {
      const matchCategory = selectedCategory === "全部" || f.category === selectedCategory;
      const matchSearch = !searchQuery ||
        f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchCategory && matchSearch;
    });
  }, [factors, selectedCategory, searchQuery]);

  // 分类 chip 列表
  const categoryChips = useMemo(() => {
    return FACTOR_CATEGORIES.map((cat) => ({
      label: cat,
      value: cat,
      active: selectedCategory === cat,
    }));
  }, [selectedCategory]);

  return (
    <TerminalShell
      breadcrumb="数据 / 因子知识库"
      title="因子知识库"
      subtitle="已注册因子"
      currentPath="/factor-knowledge"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      {isLoading && <LoadingBanner />}

      <div className="space-y-4">
        {/* 术语速查 */}
        <div className="terminal-card p-4">
          <h3 className="text-[var(--terminal-text)] text-[14px] font-bold mb-3">
            量化术语速查
          </h3>
          <TermGrid />
        </div>

        {/* 分类和搜索 */}
        <div className="terminal-card p-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <ChipList
              items={categoryChips}
              onChange={(value) => setSelectedCategory(value)}
            />
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索因子名或关键词..."
                className="terminal-input w-64"
              />
              <span className="text-[var(--terminal-dim)] text-[11px]">
                共 {factors.length} 个因子，已展示 {filteredFactors.length}
              </span>
            </div>
          </div>
        </div>

        {/* 因子卡网格 */}
        <FactorCardGrid factors={filteredFactors} />
      </div>
    </TerminalShell>
  );
}
