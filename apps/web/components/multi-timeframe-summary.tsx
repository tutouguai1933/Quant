/* 这个文件负责渲染单币页的多周期摘要骨架。 */

import { StatusBadge } from "./status-badge";
import type { MultiTimeframeSummaryItem } from "../lib/api";


type MultiTimeframeSummaryProps = {
  items: MultiTimeframeSummaryItem[];
};

/* 渲染固定周期列表的轻量摘要。 */
export function MultiTimeframeSummary({ items }: MultiTimeframeSummaryProps) {
  if (!items.length) {
    return (
      <section className="panel">
        <p className="eyebrow">多周期摘要</p>
        <h3>当前还没有可展示的多周期判断</h3>
        <p>先确认市场接口已经返回周期摘要，再继续进入更细的图表分析。</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <p className="eyebrow">多周期摘要</p>
      <h3>同一个币，先横向看四个关键周期</h3>
      <div className="action-grid">
        {items.map((item) => (
          <article key={item.interval} className="action-card">
            <strong>{item.interval}</strong>
            <p>趋势：{item.trend_state}</p>
            <p>研究：{item.research_bias}</p>
            <p>策略：{item.recommended_strategy}</p>
            <p>信心：<StatusBadge value={item.confidence} /></p>
            <p>主判断：{formatText(item.primary_reason, "n/a")}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
