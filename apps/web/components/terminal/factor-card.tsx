/**
 * 因子知识卡组件
 * 用于因子知识库页面展示因子详情
 */
"use client";

/* 因子知识卡属性 */
export type FactorCardProps = {
  /** 因子名称 */
  name: string;
  /** 分类标签 */
  category: string;
  /** 描述 */
  description: string;
  /** 公式 */
  formula?: string;
  /** 为什么有效 */
  whyEffective?: string;
  /** 怎么用 */
  howToUse?: string;
  /** 陷阱 */
  pitfalls?: string;
  /** 推荐搭配 */
  recommendedWith?: string;
  /** 当前角色 */
  currentRole?: string;
  /** 额外的类名 */
  className?: string;
};

/* 因子知识卡组件 */
export function FactorCard({
  name,
  category,
  description,
  formula,
  whyEffective,
  howToUse,
  pitfalls,
  recommendedWith,
  currentRole,
  className = "",
}: FactorCardProps) {
  return (
    <div className={`terminal-card p-4 ${className}`}>
      {/* 头部：名称和标签 */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <h4 className="text-[var(--terminal-text)] text-[14px] font-bold">{name}</h4>
          <span className="inline-block mt-1 text-[10px] font-medium text-[var(--terminal-cyan)] bg-[var(--terminal-cyan-bg)] px-1.5 py-0.5 rounded">
            {category}
          </span>
          {currentRole && (
            <span className="inline-block mt-1 ml-1.5 text-[10px] font-medium text-[var(--terminal-purple)] bg-[rgba(139,107,232,0.16)] px-1.5 py-0.5 rounded">
              {currentRole}
            </span>
          )}
        </div>
      </div>

      {/* 描述 */}
      <p className="text-[var(--terminal-muted)] text-[12px] leading-relaxed mb-3">
        {description}
      </p>

      {/* 详细信息 */}
      <div className="space-y-2 text-[11px]">
        {/* 公式 */}
        {formula && (
          <div>
            <span className="text-[var(--terminal-dim)]">公式：</span>
            <span className="text-[var(--terminal-text)] font-mono ml-1">{formula}</span>
          </div>
        )}

        {/* 为什么有效 */}
        {whyEffective && (
          <div>
            <span className="text-[var(--terminal-dim)]">为什么有效：</span>
            <span className="text-[var(--terminal-muted)] ml-1">{whyEffective}</span>
          </div>
        )}

        {/* 怎么用 */}
        {howToUse && (
          <div>
            <span className="text-[var(--terminal-dim)]">怎么用：</span>
            <span className="text-[var(--terminal-muted)] ml-1">{howToUse}</span>
          </div>
        )}

        {/* 陷阱 */}
        {pitfalls && (
          <div>
            <span className="text-[var(--terminal-dim)]">陷阱：</span>
            <span className="text-[var(--terminal-red)] ml-1">{pitfalls}</span>
          </div>
        )}

        {/* 推荐搭配 */}
        {recommendedWith && (
          <div>
            <span className="text-[var(--terminal-dim)]">推荐搭配：</span>
            <span className="text-[var(--terminal-green)] ml-1">{recommendedWith}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/* 因子知识卡网格属性 */
export type FactorCardGridProps = {
  /** 因子列表 */
  factors: Array<{
    name: string;
    category: string;
    description: string;
    formula?: string;
    whyEffective?: string;
    howToUse?: string;
    pitfalls?: string;
    recommendedWith?: string;
    currentRole?: string;
  }>;
  /** 额外的类名 */
  className?: string;
};

/* 因子知识卡网格组件 */
export function FactorCardGrid({ factors, className = "" }: FactorCardGridProps) {
  return (
    <div className={`grid grid-cols-1 lg:grid-cols-2 gap-4 ${className}`}>
      {factors.map((factor) => (
        <FactorCard
          key={factor.name}
          {...factor}
        />
      ))}
    </div>
  );
}
