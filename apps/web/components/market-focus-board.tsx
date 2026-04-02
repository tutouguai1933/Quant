/* 这个文件负责渲染市场页右侧的优先关注板。 */

import type { MarketSnapshot } from "../lib/api";


type MarketFocusBoardProps = {
  items: MarketSnapshot[];
};

/* 渲染优先关注和高信心目标。 */
export function MarketFocusBoard({ items }: MarketFocusBoardProps) {
  const focusItems = items
    .slice()
    .sort((left, right) => {
      const confidenceScore = getConfidenceScore(right.research_brief.confidence) - getConfidenceScore(left.research_brief.confidence);
      if (confidenceScore !== 0) {
        return confidenceScore;
      }
      return getStrategyScore(right.recommended_strategy) - getStrategyScore(left.recommended_strategy);
    })
    .slice(0, 3);

  if (!focusItems.length) {
    return (
      <aside className="panel">
        <p className="eyebrow">优先关注</p>
        <h3>等待市场数据</h3>
        <p>市场接口恢复后，这里会先告诉你哪些币值得优先点开。</p>
      </aside>
    );
  }

  return (
    <aside className="panel">
      <p className="eyebrow">优先关注</p>
      <h3>先看这些目标</h3>
      <div className="metric-grid">
        {focusItems.map((item) => (
          <article key={item.symbol} className="metric-card">
            <p className="metric-label">{item.symbol}</p>
            <p className="metric-value">{formatConfidence(item.research_brief.confidence)}</p>
            <p className="metric-detail">
              {formatPreferredStrategy(item.recommended_strategy)} / {formatTrendState(item.trend_state)}
            </p>
            <a href={`/market/${encodeURIComponent(item.symbol)}`}>看单币页</a>
          </article>
        ))}
      </div>
    </aside>
  );
}

/* 把研究信心转换成优先级分数。 */
function getConfidenceScore(value: string): number {
  if (value === "high") {
    return 3;
  }
  if (value === "medium") {
    return 2;
  }
  return 1;
}

/* 把推荐策略转换成优先级分数。 */
function getStrategyScore(value: MarketSnapshot["recommended_strategy"]): number {
  if (value === "trend_breakout" || value === "trend_pullback") {
    return 2;
  }
  return 1;
}

/* 格式化推荐策略文案。 */
function formatPreferredStrategy(value: MarketSnapshot["recommended_strategy"]): string {
  if (value === "trend_breakout") {
    return "趋势突破";
  }
  if (value === "trend_pullback") {
    return "趋势回调";
  }
  return "继续观察";
}

/* 格式化趋势状态文案。 */
function formatTrendState(value: MarketSnapshot["trend_state"]): string {
  if (value === "uptrend") {
    return "上行趋势";
  }
  if (value === "pullback") {
    return "回调观察";
  }
  return "中性观察";
}

/* 格式化研究信心文案。 */
function formatConfidence(value: string): string {
  if (value === "high") {
    return "高信心";
  }
  if (value === "medium") {
    return "中等信心";
  }
  return "低信心";
}
