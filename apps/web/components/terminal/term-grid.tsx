/**
 * 术语速查组件
 * 用于因子知识库页面顶部展示量化术语解释
 */
"use client";

/* 术语项 */
export type TermItem = {
  /** 术语名称 */
  title: string;
  /** 解释内容 */
  content: string;
};

/* 默认术语列表 */
const DEFAULT_TERMS: TermItem[] = [
  {
    title: "IC（信息系数）",
    content: "每日横截面上，因子值排名与未来收益排名的 Spearman 相关系数。>0.05 为好因子，>0.10 为强因子。量化选币最核心指标，比 R² 更重要，因为我们只选 Top-K。",
  },
  {
    title: "IR（信息比率）",
    content: "IC 的稳定性 = IC 均值 / IC 标准差。IR > 0.3 算可用，>0.5 算好，>1.0 非常稀有。IC 再高，如果 IR 低，实盘一样会大幅回撤。",
  },
  {
    title: "方向（direction）",
    content: "+1 = 因子值越大越好，-1 = 因子值越小越好。例如：vol_20 方向 = -1，意思是买低波动币种。",
  },
  {
    title: "币种池（universe）",
    content: "允许选币的候选范围。限定池子是为了降噪、保证风格一致，让 Top-K 截面比较有意义。",
  },
  {
    title: "Top-K 调仓",
    content: "每个调仓日按因子打分排序，买入分数最高的 K 只，等权持有，N 天后再调。K 小风险集中但收益潜力大，K 大更稳但不够锐利。",
  },
  {
    title: "因子正交",
    content: "两个因子相关性高时，同时叠加没有意义，相当于重复下注。选因子时要注意来自不同类别的组合效果最好。",
  },
  {
    title: "rank 标签 vs raw 标签",
    content: "训练模型时，把 N 日收益率改成「当日横截面排名百分位」作为标签。抗极端值、去牛熊漂移，更符合量化选币目标。",
  },
];

/* 术语速查属性 */
export type TermGridProps = {
  /** 术语列表 */
  terms?: TermItem[];
  /** 额外的类名 */
  className?: string;
};

/* 术语速查组件 */
export function TermGrid({ terms = DEFAULT_TERMS, className = "" }: TermGridProps) {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 ${className}`}>
      {terms.map((term) => (
        <div
          key={term.title}
          className="terminal-card p-3 hover:border-[var(--terminal-cyan)] transition-colors"
        >
          <h4 className="text-[var(--terminal-cyan)] text-[12px] font-bold mb-1.5">
            {term.title}
          </h4>
          <p className="text-[var(--terminal-muted)] text-[11px] leading-relaxed">
            {term.content}
          </p>
        </div>
      ))}
    </div>
  );
}
